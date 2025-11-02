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
        return await self.search_service.search(query, limit)

    async def get_article_content(
        self,
        title: str,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:
        return await self.content_service.get_article_content(title, extract_length)

    async def get_article_by_pageid(
        self,
        pageid: int,
        extract_length: int = 500
    ) -> Optional[Dict[str, str]]:
        return await self.content_service.get_article_by_pageid(pageid, extract_length)

    async def get_full_article_by_pageid(
        self,
        pageid: int,
        max_chars: int = 50000
    ) -> Optional[Dict[str, str]]:
        return await self.content_service.get_full_article_by_pageid(pageid, max_chars)

    async def get_multiple_articles(
        self,
        pageids: List[int],
        extract_length: int = 500
    ) -> List[Dict[str, str]]:
        return await self.search_service.get_multiple_articles(pageids, extract_length)

    async def get_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:
        return await self.content_service.get_summary_by_title(title)

    async def _fetch_summary_by_title(self, title: str) -> Optional[Dict[str, str]]:
        return await self.content_service._fetch_summary_by_title(title)

    async def _fetch_media_by_title(self, title: str) -> Optional[List[str]]:
        return await self.content_service._fetch_media_by_title(title)

    @staticmethod
    def _clean_html(text: str) -> str:
        return WikipediaApiClientService._clean_html(text)

    async def get_language_links(self, pageid: int) -> Dict[str, str]:
        return await self.content_service.get_language_links(pageid)

    async def get_related_pages(self, title: str) -> List[Dict[str, str]]:
        return await self.content_service.get_related_pages(title)
