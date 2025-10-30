# Pluginy: WEATHER

System pluginów znajduje się w `server_core/plugins`.

## Dostawcy

- `open-meteo` (domyślny): nie wymaga klucza API.
- `openweather`: wymaga ustawienia `OPENWEATHER_API_KEY`.

## Konfiguracja

Ustaw zmienne środowiskowe w `.env` lub w systemie:

```
WEATHER_PROVIDER=open-meteo   # albo openweather
OPENWEATHER_API_KEY=...       # tylko dla openweather
```

## Użycie

- Zapytania z topiku `WEATHER` mogą zawierać współrzędne, np.: `lat=52.23, lon=21.01`.
- Jeśli współrzędne są podane, plugin `open-meteo` spróbuje pobrać bieżące dane i dołączyć je do system promptu jako „Plugin Context”.
- Jeśli korzystasz z OpenWeather, ustaw `OPENWEATHER_API_KEY` i podawaj nazwę miasta lub współrzędne (obsługa nazw miast może być dodana w kolejnych iteracjach).

## Rozszerzanie

- Dodawaj nowe pluginy tworząc klasę dziedziczącą po `BasePlugin` i rejestruj ją w `server_core/plugins/__init__.py`.

