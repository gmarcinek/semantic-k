"""Wikipedia search service for article searching."""
import logging
from typing import List, Dict
from app.services.wikipedia.api_client_service import WikipediaApiClientService
from app.utils.colored_logger import get_plugin_logger

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'wikipedia')


class WikipediaSearchService:
    """Service for searching Wikipedia articles."""

    def __init__(self, api_client: WikipediaApiClientService):
        """Initialize search service.

        Args:
            api_client: Wikipedia API client
        """
        self.api_client = api_client

    async def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, str]]:
        """Search Wikipedia for articles.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of search results
        """
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

        data = await self.api_client._make_request(params)
        if not data:
            return []

        if "query" in data and "search" in data["query"]:
            results = []
            for item in data["query"]["search"]:
                results.append({
                    "title": item["title"],
                    "snippet": self.api_client._clean_html(item.get("snippet", "")),
                    "pageid": item["pageid"]
                })

            plugin_logger.info(f"📚 Wikipedia search returned {len(results)} results for query: '{query}'")
            for i, result in enumerate(results[:3], 1):
                plugin_logger.info(f"  [{i}] {result['title']} (pageid: {result['pageid']})")
            if len(results) > 3:
                plugin_logger.info(f"  ... and {len(results) - 3} more results")

            return results
        return []

    async def get_multiple_articles(
        self,
        pageids: List[int],
        extract_length: int = 500
    ) -> List[Dict[str, str]]:
        """Get multiple articles by page IDs.

        Args:
            pageids: List of Wikipedia page IDs
            extract_length: Maximum extract length

        Returns:
            List of articles with metadata
        """
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

        data = await self.api_client._make_request(params)
        if not data:
            return []

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

            # Import here to avoid circular dependency
            from app.services.wikipedia.content_service import WikipediaContentService
            content_service = WikipediaContentService(self.api_client)

            # Enrich articles with summaries and media
            for article in results:
                if not article.get("extract") and article.get("title"):
                    summary = await content_service.get_summary_by_title(article["title"])
                    if summary:
                        article["extract"] = summary.get("extract", "")
                        if not article.get("url"):
                            article["url"] = summary.get("url", "")
                        if summary.get("thumbnail_url"):
                            article["image_url"] = summary.get("thumbnail_url")

                if article.get("title"):
                    media = await content_service._fetch_media_by_title(article["title"])
                    if media:
                        article["images"] = media[:12]

            plugin_logger.info(f"📖 Wikipedia fetched {len(results)} full articles:")
            for article in results:
                extract_preview = article['extract'][:100] + "..." if len(article['extract']) > 100 else article['extract']
                plugin_logger.info(f"  📄 {article['title']}")
                plugin_logger.info(f"     {extract_preview}")
                plugin_logger.info(f"     🔗 {article['url']}")

            # Preserve original order
            by_id = {int(a["pageid"]): a for a in results if a.get("pageid") is not None}
            ordered = [by_id[pid] for pid in map(int, params["pageids"].split("|")) if pid in by_id]

            return ordered
        return []
