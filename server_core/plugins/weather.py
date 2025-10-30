import os
from typing import Optional

import httpx

from .base import BasePlugin
from ..config import CONFIG


class WeatherPlugin(BasePlugin):
    topic = "WEATHER"
    name = "weather"

    def __init__(self) -> None:
        # Provider selection priority:
        # 1) WEATHER_PROVIDER env var
        # 2) config["weather"]["provider"]
        # 3) default to "open-meteo"
        self.openweather_key = os.getenv("OPENWEATHER_API_KEY", "")
        env_provider = os.getenv("WEATHER_PROVIDER")
        cfg_provider = (CONFIG.get("weather", {}) or {}).get("provider")
        base_provider = (env_provider or cfg_provider or "open-meteo").lower()
        # If user explicitly set openweather but no key, fall back to open-meteo
        if base_provider == "openweather" and not self.openweather_key:
            self.provider = "open-meteo"
        else:
            self.provider = base_provider

    def can_handle(self, prompt: str) -> bool:  # type: ignore[override]
        # For now return True for any WEATHER prompt
        return True

    def prepare_context(self, prompt: str) -> Optional[str]:  # type: ignore[override]
        """Return short context note or live data if easy to fetch.

        Strategy:
        - If provider is open-meteo and prompt includes coordinates like "lat=.., lon=..", fetch quick current weather.
        - Otherwise return a hint that plugin is ready and what is needed.
        """
        # Very simple coordinate extraction: look for "lat=.." and "lon=.."
        lat, lon = _extract_lat_lon(prompt)
        if self.provider == "open-meteo":
            # Try by coords, then city name via Open-Meteo geocoding
            try:
                if lat is not None and lon is not None:
                    current = _fetch_open_meteo_current(lat, lon)
                    daily = _fetch_open_meteo_daily(lat, lon)
                    ctx = _format_open_meteo_context(current, daily, lat=lat, lon=lon)
                    if ctx:
                        return ctx
                city_nl = _extract_city_natural(prompt)
                if city_nl:
                    geo = _geocode_open_meteo(city_nl)
                    if geo:
                        g_lat, g_lon = geo["latitude"], geo["longitude"]
                        current = _fetch_open_meteo_current(g_lat, g_lon)
                        daily = _fetch_open_meteo_daily(g_lat, g_lon)
                        ctx = _format_open_meteo_context(current, daily, city=geo.get("name"), country=geo.get("country"), lat=g_lat, lon=g_lon)
                        if ctx:
                            return ctx
            except Exception:
                pass
            return (
                "Open-Meteo ready. Podaj lokalizację (np. miasto: Warszawa) albo współrzędne lat=.., lon=.., "
                "a pobiorę bieżącą pogodę i krótką prognozę."
            )

        if self.provider == "openweather":
            if not self.openweather_key:
                return (
                    "WEATHER plugin configured for OpenWeather but OPENWEATHER_API_KEY is missing. "
                    "Provide a city name or coordinates and set the API key to enable live data."
                )
            # Try by coordinates first, then by city name
            if lat is not None and lon is not None:
                try:
                    data = _fetch_openweather_coords(lat, lon, self.openweather_key)
                    if data:
                        return _format_openweather_context(data, lat=lat, lon=lon)
                except Exception:
                    pass
            city = _extract_city(prompt)
            if city:
                try:
                    data = _fetch_openweather_city(city, self.openweather_key)
                    if data:
                        return _format_openweather_context(data, city=city)
                except Exception:
                    pass
            return (
                "OpenWeather ready. Provide location as city=<name> (np. city=Warsaw) "
                "albo lat=.., lon=.. aby pobrać bieżącą pogodę."
            )

        # Generic hint when no live fetch
        return (
            "WEATHER plugin ready. To fetch live data, provide a location (e.g., city or lat,lon). "
            "Example with coordinates: lat=52.23, lon=21.01"
        )


def _extract_lat_lon(text: str) -> tuple[Optional[float], Optional[float]]:
    import re

    lat_match = re.search(r"lat\s*=\s*([-+]?[0-9]*\.?[0-9]+)", text, re.IGNORECASE)
    lon_match = re.search(r"(lon|lng|long)\s*=\s*([-+]?[0-9]*\.?[0-9]+)", text, re.IGNORECASE)
    lat = float(lat_match.group(1)) if lat_match else None
    lon = float(lon_match.group(2)) if lon_match else None
    return lat, lon


def _fetch_open_meteo_current(lat: float, lon: float) -> Optional[dict]:
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m"
    )
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            js = resp.json()
            return js.get("current")
    return None


def _fetch_open_meteo_daily(lat: float, lon: float) -> Optional[dict]:
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min&forecast_days=3&timezone=auto"
    )
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            js = resp.json()
            return js.get("daily")
    return None


def _extract_city(text: str) -> Optional[str]:
    import re
    m = re.search(r"\b(city|miasto)\s*=\s*([A-Za-zÀ-ÿ\-\s]+)\b", text, re.IGNORECASE)
    if m:
        return m.group(2).strip()
    return None


def _extract_city_natural(text: str) -> Optional[str]:
    """Try to extract a city name from natural language like 'w Warszawie' or 'in Warsaw'."""
    import re
    # Common Polish/English prepositions
    patterns = [
        r"\bw\s+([A-Za-zÀ-ÿ\-\s]{2,})\b",      # w Warszawie
        r"\bdla\s+([A-Za-zÀ-ÿ\-\s]{2,})\b",    # dla Warszawy
        r"\bin\s+([A-Za-zÀ-ÿ\-\s]{2,})\b",     # in Warsaw
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip().split(",")[0]
    # Fallback to explicit city= extractor
    return _extract_city(text)


def _fetch_openweather_coords(lat: float, lon: float, api_key: str) -> Optional[dict]:
    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        f"lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=pl"
    )
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            return resp.json()
    return None


def _fetch_openweather_city(city: str, api_key: str) -> Optional[dict]:
    import urllib.parse as up
    q = up.quote(city)
    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        f"q={q}&appid={api_key}&units=metric&lang=pl"
    )
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            return resp.json()
    return None


def _format_openweather_context(data: dict, *, lat: Optional[float] = None, lon: Optional[float] = None, city: Optional[str] = None) -> str:
    main = data.get("main", {})
    wind = data.get("wind", {})
    weather_list = data.get("weather", []) or []
    desc = weather_list[0].get("description") if weather_list else None
    temp = main.get("temp")
    hum = main.get("humidity")
    wsp = wind.get("speed")
    loc = (
        f"city={city}" if city else (f"lat={lat}, lon={lon}" if lat is not None and lon is not None else "")
    )
    parts = ["Live weather (OpenWeather)"]
    if loc:
        parts.append(loc)
    if desc:
        parts.append(f"desc={desc}")
    if temp is not None:
        parts.append(f"temp={temp}°C")
    if hum is not None:
        parts.append(f"humidity={hum}%")
    if wsp is not None:
        parts.append(f"wind={wsp} m/s")
    return ", ".join(parts)


def _geocode_open_meteo(name: str) -> Optional[dict]:
    import urllib.parse as up
    q = up.quote(name)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=pl&format=json"
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            js = resp.json() or {}
            results = js.get("results") or []
            if results:
                return results[0]
    return None


def _format_open_meteo_context(current: Optional[dict], daily: Optional[dict], *, city: Optional[str] = None, country: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[str]:
    parts = ["Live weather (Open-Meteo)"]
    if city:
        parts.append(f"city={city}")
    if country:
        parts.append(f"country={country}")
    if lat is not None and lon is not None:
        parts.append(f"lat={lat}, lon={lon}")

    if current:
        t = current.get("temperature_2m")
        w = current.get("wind_speed_10m")
        if t is not None:
            parts.append(f"temp_now={t}°C")
        if w is not None:
            parts.append(f"wind_now={w} m/s")

    if daily:
        # Try to provide tomorrow min/max when available
        times = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        if len(times) >= 2:
            # Index 1 ~ tomorrow in Open-Meteo daily series
            dmax = tmax[1] if len(tmax) > 1 else None
            dmin = tmin[1] if len(tmin) > 1 else None
            label = "tomorrow"
            if dmax is not None:
                parts.append(f"{label}_max={dmax}°C")
            if dmin is not None:
                parts.append(f"{label}_min={dmin}°C")

    return ", ".join(parts) if len(parts) > 1 else None
