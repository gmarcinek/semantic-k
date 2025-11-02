"""Wikipedia search service - Compatibility wrapper for refactored services."""
from typing import Dict, List, Optional, Tuple, Union
from app.models import WikipediaMetadata
from app.services.wikipedia.search_coordinator_service import WikipediaSearchCoordinatorService


class WikipediaSearchService:
    """Compatibility wrapper for WikipediaSearchCoordinatorService.

    This class maintains backward compatibility while internally using
    the refactored service architecture.
    """

    def __init__(
        self,
        wikipedia_service,
        reranker_service,
        config_service,
        wikipedia_intent_service=None
    ):
        # Initialize the coordinator service
        self.coordinator = WikipediaSearchCoordinatorService(
            wikipedia_service=wikipedia_service,
            reranker_service=reranker_service,
            config_service=config_service,
            wikipedia_intent_service=wikipedia_intent_service
        )

        # Expose underlying services for compatibility
        self.wikipedia_service = wikipedia_service
        self.reranker_service = reranker_service
        self.config_service = config_service
        self.wikipedia_intent_service = wikipedia_intent_service

        # Expose coordinator properties
        self.primary_language = self.coordinator.primary_language
        self.fallback_languages = self.coordinator.fallback_languages
        self._language_services = self.coordinator._language_services

    def extract_wikipedia_queries(self, response: str) -> List[str]:
        return self.coordinator.extract_wikipedia_queries(response)

    async def search_wikipedia_multi_query(
        self,
        queries: Union[List[str], Dict[str, List[str]]],
        original_prompt: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> Tuple[Optional[str], Optional[WikipediaMetadata]]:
        return await self.coordinator.search_wikipedia_multi_query(
            queries=queries,
            original_prompt=original_prompt,
            chat_history=chat_history
        )

    def build_wikipedia_context(self, articles: List[Dict]) -> str:
        return self.coordinator.build_wikipedia_context(articles)

    def build_wiki_url(self, pageid: Optional[int], language: Optional[str] = None) -> str:
        return self.coordinator.build_wiki_url(pageid, language)

    def get_service_for_language(self, language: Optional[str]):
        return self.coordinator._get_service_for_language(language)
