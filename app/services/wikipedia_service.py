"""Wikipedia service - Compatibility wrapper for refactored services."""
from typing import List, Dict, Optional
from app.services.wikipedia.api_client_service import WikipediaApiClientService
from app.services.wikipedia.search_service import WikipediaSearchService
from app.services.wikipedia.content_service import WikipediaContentService


class WikipediaService:
    """Compatibility wrapper combining all Wikipedia services.

    This class maintains backward compatibility while internally using
    the refactored service architecture.
    """

    BASE_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, language: str = "pl"):
        """Initialize Wikipedia service.

        Args:
            language: Wikipedia language code
        """
        self.language = language
        self.base_url = f"https://{language}.wikipedia.org/w/api.php"

        # Initialize refactored services
        self.api_client = WikipediaApiClientService(language=language)
        self.search_service = WikipediaSearchService(api_client=self.api_client)
        self.content_service = WikipediaContentService(api_client=self.api_client)

        # Expose headers for backward compatibility
        self._headers = self.api_client._headers

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
        return await self.search_service.search(query, limit)

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
        return await self.content_service.get_article_content(title, extract_length)

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
        return await self.content_service.get_article_by_pageid(pageid, extract_length)

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
        return await self.content_service.get_full_article_by_pageid(pageid, max_chars)

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
        return await self.search_service.get_multiple_articles(pageids, extract_length)

    async def get_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:
        """Get article summary by title.

        Args:
            title: Article title

        Returns:
            Summary data or None
        """
        return await self.content_service.get_summary_by_title(title)

    async def _fetch_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:
        """Fetch article summary (private method for backward compatibility).

        Args:
            title: Article title

        Returns:
            Summary data or None
        """
        return await self.content_service._fetch_summary_by_title(title)

    async def _fetch_media_by_title(self, title: str) -> Optional[List[str]]:
        """Fetch media images for an article (private method for backward compatibility).

        Args:
            title: Article title

        Returns:
            List of image URLs
        """
        return await self.content_service._fetch_media_by_title(title)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text.

        Args:
            text: Text containing HTML tags

        Returns:
            Cleaned text
        """
        return WikipediaApiClientService._clean_html(text)
