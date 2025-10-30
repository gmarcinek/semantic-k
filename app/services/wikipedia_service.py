"""
Wikipedia API Service
Handles Wikipedia search, article retrieval, and content extraction
"""

import aiohttp
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class WikipediaService:
    """Service for interacting with Wikipedia API"""

    BASE_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, language: str = "en"):
        """
        Initialize Wikipedia service

        Args:
            language: Wikipedia language code (default: 'en')
        """
        self.language = language
        self.base_url = f"https://{language}.wikipedia.org/w/api.php"

    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """
        Search Wikipedia for articles matching the query

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            List of search results with title and snippet
        """
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet|titlesnippet",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()

                    if "query" in data and "search" in data["query"]:
                        results = []
                        for item in data["query"]["search"]:
                            results.append({
                                "title": item["title"],
                                "snippet": self._clean_html(item.get("snippet", "")),
                                "pageid": item["pageid"]
                            })
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
        """
        Get article content from Wikipedia

        Args:
            title: Article title
            extract_length: Number of characters to extract

        Returns:
            Dictionary with title, extract, and url
        """
        params = {
            "action": "query",
            "prop": "extracts|info",
            "titles": title,
            "exchars": extract_length,
            "explaintext": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()

                    if "query" in data and "pages" in data["query"]:
                        pages = data["query"]["pages"]
                        page = next(iter(pages.values()))

                        if "missing" not in page:
                            return {
                                "title": page.get("title", ""),
                                "extract": page.get("extract", ""),
                                "url": page.get("fullurl", ""),
                                "pageid": page.get("pageid", "")
                            }
                    return None
        except Exception as e:
            logger.error(f"Wikipedia article retrieval error: {e}")
            return None

    async def get_article_by_pageid(
        self,
        pageid: int,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:
        """
        Get article content by page ID

        Args:
            pageid: Wikipedia page ID
            extract_length: Number of characters to extract

        Returns:
            Dictionary with title, extract, and url
        """
        params = {
            "action": "query",
            "prop": "extracts|info",
            "pageids": pageid,
            "exchars": extract_length,
            "explaintext": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()

                    if "query" in data and "pages" in data["query"]:
                        pages = data["query"]["pages"]
                        page = next(iter(pages.values()))

                        if "missing" not in page:
                            return {
                                "title": page.get("title", ""),
                                "extract": page.get("extract", ""),
                                "url": page.get("fullurl", ""),
                                "pageid": page.get("pageid", "")
                            }
                    return None
        except Exception as e:
            logger.error(f"Wikipedia article retrieval error: {e}")
            return None

    async def get_multiple_articles(
        self,
        pageids: List[int],
        extract_length: int = 500
    ) -> List[Dict[str, str]]:
        """
        Get multiple articles by page IDs

        Args:
            pageids: List of Wikipedia page IDs
            extract_length: Number of characters to extract per article

        Returns:
            List of article dictionaries
        """
        if not pageids:
            return []

        params = {
            "action": "query",
            "prop": "extracts|info",
            "pageids": "|".join(map(str, pageids)),
            "exchars": extract_length,
            "explaintext": 1,
            "inprop": "url",
            "format": "json",
            "utf8": 1
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
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
                                    "pageid": page.get("pageid", "")
                                })
                        return results
                    return []
        except Exception as e:
            logger.error(f"Wikipedia multiple articles retrieval error: {e}")
            return []

    @staticmethod
    def _clean_html(text: str) -> str:
        """
        Remove HTML tags from text

        Args:
            text: HTML text

        Returns:
            Clean text without HTML tags
        """
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
