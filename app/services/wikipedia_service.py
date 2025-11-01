import aiohttp
from typing import List, Dict, Optional
import logging
from app.utils.colored_logger import get_plugin_logger

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'wikipedia')

class WikipediaService:

    BASE_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, language: str = "pl"):

        self.language = language
        self.base_url = f"https://{language}.wikipedia.org/w/api.php"

        self._headers = {
            "User-Agent": "semantic-k/1.0 (Wikipedia Q&A; contact: local)",
            "Accept": "application/json"
        }

    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:

        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet|titlesnippet",
            "srnamespace": 0,
            "srenablerewrites": 1,
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=self._headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Wikipedia search HTTP {response.status}: {text[:200]}")
                        return []

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        text = await response.text()
                        logger.error(f"Wikipedia search non-JSON ({content_type}): {text[:200]}")
                        return []

                    data = await response.json()

                    if "query" in data and "search" in data["query"]:
                        results = []
                        for item in data["query"]["search"]:
                            results.append({
                                "title": item["title"],
                                "snippet": self._clean_html(item.get("snippet", "")),
                                "pageid": item["pageid"]
                            })

                        plugin_logger.info(f"📚 Wikipedia search returned {len(results)} results for query: '{query}'")
                        for i, result in enumerate(results[:3], 1):
                            plugin_logger.info(f"  [{i}] {result['title']} (pageid: {result['pageid']})")
                        if len(results) > 3:
                            plugin_logger.info(f"  ... and {len(results) - 3} more results")

                        return results
                    return []
        except Exception as e:
            logger.error(f"Wikipedia search error: {e}")
            return []

    async def get_article_content(
        self,
        title: str,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:

        params = {
            "action": "query",
            "prop": "extracts|info",
            "titles": title,
            "exchars": extract_length,
            "explaintext": 1,
            "redirects": 1,
            "exintro": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=self._headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Wikipedia article HTTP {response.status}: {text[:200]}")
                        return None

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        text = await response.text()
                        logger.error(f"Wikipedia article non-JSON ({content_type}): {text[:200]}")
                        return None

                    data = await response.json()

                    if "query" in data and "pages" in data["query"]:
                        pages = data["query"]["pages"]
                        page = next(iter(pages.values()))

                        if "missing" not in page:
                            result = {
                                "title": page.get("title", ""),
                                "extract": page.get("extract", ""),
                                "url": page.get("fullurl", ""),
                                "pageid": page.get("pageid", ""),

                                "image_url": None
                            }

                            if not result["extract"]:
                                summary = await self._fetch_summary_by_title(result["title"])
                                if summary:
                                    result["extract"] = summary.get("extract", result["extract"])
                                    if not result["url"]:
                                        result["url"] = summary.get("url", result["url"])
                                    if summary.get("thumbnail_url"):
                                        result["image_url"] = summary.get("thumbnail_url")
                            return result
                    return None
        except Exception as e:
            logger.error(f"Wikipedia article retrieval error: {e}")
            return None

    async def get_article_by_pageid(
        self,
        pageid: int,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:

        params = {
            "action": "query",
            "prop": "extracts|info",
            "pageids": pageid,
            "exchars": extract_length,
            "explaintext": 1,
            "redirects": 1,
            "exintro": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=self._headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Wikipedia article by pageid HTTP {response.status}: {text[:200]}")
                        return None

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        text = await response.text()
                        logger.error(f"Wikipedia article by pageid non-JSON ({content_type}): {text[:200]}")
                        return None

                    data = await response.json()

                    if "query" in data and "pages" in data["query"]:
                        pages = data["query"]["pages"]
                        page = next(iter(pages.values()))

                        if "missing" not in page:
                            result = {
                                "title": page.get("title", ""),
                                "extract": page.get("extract", ""),
                                "url": page.get("fullurl", ""),
                                "pageid": page.get("pageid", ""),
                                "image_url": None
                            }
                            if not result["extract"]:
                                summary = await self._fetch_summary_by_title(result["title"])
                                if summary:
                                    result["extract"] = summary.get("extract", result["extract"])
                                    if not result["url"]:
                                        result["url"] = summary.get("url", result["url"])
                                    if summary.get("thumbnail_url"):
                                        result["image_url"] = summary.get("thumbnail_url")
                            return result
                    return None
        except Exception as e:
            logger.error(f"Wikipedia article retrieval error: {e}")
            return None

    async def get_full_article_by_pageid(
        self,
        pageid: int,
        max_chars: int = 50000
    ) -> Optional[Dict[str, str]]:

        params = {
            "action": "query",
            "prop": "extracts|info",
            "pageids": pageid,
            "explaintext": 1,

            "exchars": max_chars,
            "redirects": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=self._headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Wikipedia full article HTTP {response.status}: {text[:200]}")
                        return None

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        text = await response.text()
                        logger.error(f"Wikipedia full article non-JSON ({content_type}): {text[:200]}")
                        return None

                    data = await response.json()

                    if "query" in data and "pages" in data["query"]:
                        pages = data["query"]["pages"]
                        page = next(iter(pages.values()))

                        if "missing" not in page:
                            result = {
                                "title": page.get("title", ""),
                                "extract": page.get("extract", ""),
                                "url": page.get("fullurl", ""),
                                "pageid": page.get("pageid", "")
                            }
                            return result
                    return None
        except Exception as e:
            logger.error(f"Wikipedia full article retrieval error: {e}")
            return None

    async def get_multiple_articles(
        self,
        pageids: List[int],
        extract_length: int = 500
    ) -> List[Dict[str, str]]:

        if not pageids:
            return []

        params = {
            "action": "query",
            "prop": "extracts|info",
            "pageids": "|".join(map(str, pageids)),
            "exchars": extract_length,
            "explaintext": 1,
            "redirects": 1,
            "exintro": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=self._headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Wikipedia multiple articles HTTP {response.status}: {text[:200]}")
                        return []

                    content_type = response.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        text = await response.text()
                        logger.error(f"Wikipedia multiple articles non-JSON ({content_type}): {text[:200]}")
                        return []

                    data = await response.json()

                    if "query" in data and "pages" in data["query"]:
                        pages = data["query"]["pages"]
                        results = []

                        for page in pages.values():
                            if "missing" not in page:
                                results.append({
                                    "title": page.get("title", ""),
                                    "extract": page.get("extract", ""),
                                    "url": page.get("fullurl", ""),
                                    "pageid": page.get("pageid", ""),
                                    "image_url": None,
                                    "images": []
                                })

                        for i, article in enumerate(results):
                            if not article.get("extract") and article.get("title"):
                                summary = await self._fetch_summary_by_title(article["title"])
                                if summary:
                                    article["extract"] = summary.get("extract", "")
                                    if not article.get("url"):
                                        article["url"] = summary.get("url", "")
                                    if summary.get("thumbnail_url"):
                                        article["image_url"] = summary.get("thumbnail_url")

                            if article.get("title"):
                                media = await self._fetch_media_by_title(article["title"])
                                if media:

                                    article["images"] = media[:12]

                        plugin_logger.info(f"📖 Wikipedia fetched {len(results)} full articles:")
                        for article in results:
                            extract_preview = article['extract'][:100] + "..." if len(article['extract']) > 100 else article['extract']
                            plugin_logger.info(f"  📄 {article['title']}")
                            plugin_logger.info(f"     {extract_preview}")
                            plugin_logger.info(f"     🔗 {article['url']}")

                        by_id = {int(a["pageid"]): a for a in results if a.get("pageid") is not None}
                        ordered = [by_id[pid] for pid in map(int, params["pageids"].split("|")) if pid in by_id]

                        plugin_logger.info(f"📖 Wikipedia fetched {len(ordered)} full articles:")
                        for article in ordered:
                            extract_preview = article['extract'][:100] + "..." if len(article['extract']) > 100 else article['extract']
                            plugin_logger.info(f"  📄 {article['title']}")
                            plugin_logger.info(f"     {extract_preview}")
                            plugin_logger.info(f"     🔗 {article['url']}")

                        return ordered
                    return []
        except Exception as e:
            logger.error(f"Wikipedia multiple articles retrieval error: {e}")
            return []

    @staticmethod
    def _clean_html(text: str) -> str:

        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    async def _fetch_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:

        import urllib.parse
        title_enc = urllib.parse.quote(title)
        url = f"https://{self.language}.wikipedia.org/api/rest_v1/page/summary/{title_enc}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers) as resp:
                    if resp.status != 200:
                        return None
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        return None
                    data = await resp.json()
                    extract = data.get("extract") or data.get("description") or ""
                    page_url = (
                        data.get("content_urls", {})
                        .get("desktop", {})
                        .get("page", "")
                    )
                    thumb = None

                    if isinstance(data.get("originalimage"), dict):
                        thumb = data["originalimage"].get("source")
                    if not thumb and isinstance(data.get("thumbnail"), dict):
                        thumb = data["thumbnail"].get("source")
                    return {"extract": extract, "url": page_url, "thumbnail_url": thumb}
        except Exception:
            return None

    async def _fetch_media_by_title(self, title: str) -> Optional[List[str]]:

        import urllib.parse
        title_enc = urllib.parse.quote(title)
        url = f"https://{self.language}.wikipedia.org/api/rest_v1/page/media-list/{title_enc}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers) as resp:
                    if resp.status != 200:
                        return []
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "application/json" not in content_type:
                        return []
                    data = await resp.json()
                    items = data.get("items", [])
                    images: List[str] = []
                    for it in items:
                        if it.get("type") != "image":
                            continue

                        original = (it.get("original") or {}).get("source")
                        if original:
                            images.append(original)
                            continue

                        srcset = it.get("srcset") or []
                        if srcset:

                            src = sorted(srcset, key=lambda s: s.get("scale", 0), reverse=True)[0].get("src")
                            if src:
                                images.append(src)
                    return images
        except Exception:
            return []

    async def get_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:

        return await self._fetch_summary_by_title(title)
