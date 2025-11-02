"""Wikipedia content service for article content and media retrieval."""
import logging
import urllib.parse
from typing import Optional, Dict, List
from app.services.wikipedia.api_client_service import WikipediaApiClientService

logger = logging.getLogger(__name__)


class WikipediaContentService:
    """Service for fetching Wikipedia article content and media."""

    def __init__(self, api_client: WikipediaApiClientService):
        """Initialize content service.

        Args:
            api_client: Wikipedia API client
        """
        self.api_client = api_client

    async def get_article_content(
        self,
        title: str,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:
        """Get article content by title.

        Args:
            title: Article title
            extract_length: Maximum extract length

        Returns:
            Article data or None
        """
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

        data = await self.api_client._make_request(params)
        if not data:
            return None

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

    async def get_article_by_pageid(
        self,
        pageid: int,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:
        """Get article content by page ID.

        Args:
            pageid: Wikipedia page ID
            extract_length: Maximum extract length

        Returns:
            Article data or None
        """
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

        data = await self.api_client._make_request(params)
        if not data:
            return None

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

    async def get_full_article_by_pageid(
        self,
        pageid: int,
        max_chars: int = 50000
    ) -> Optional[Dict[str, str]]:
        """Get full article content by page ID.

        Args:
            pageid: Wikipedia page ID
            max_chars: Maximum character count

        Returns:
            Full article data or None
        """
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

        data = await self.api_client._make_request(params)
        if not data:
            return None

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

    async def get_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:
        """Get article summary by title (public method).

        Args:
            title: Article title

        Returns:
            Summary data or None
        """
        return await self._fetch_summary_by_title(title)

    async def _fetch_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:
        """Fetch article summary using REST API.

        Args:
            title: Article title

        Returns:
            Summary with extract, URL, and thumbnail
        """
        title_enc = urllib.parse.quote(title)
        endpoint = f"page/summary/{title_enc}"
        data = await self.api_client.make_rest_request(endpoint)

        if not data:
            return None

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

    async def _fetch_media_by_title(self, title: str) -> Optional[List[str]]:
        """Fetch media images for an article.

        Args:
            title: Article title

        Returns:
            List of image URLs
        """
        title_enc = urllib.parse.quote(title)
        endpoint = f"page/media-list/{title_enc}"
        data = await self.api_client.make_rest_request(endpoint)

        if not data:
            return []

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
