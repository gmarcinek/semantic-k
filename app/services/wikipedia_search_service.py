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
        """Initialize Wikipedia search service.

        Args:
            wikipedia_service: Base Wikipedia service
            reranker_service: Reranking service
            config_service: Configuration service
            wikipedia_intent_service: Optional intent service
        """
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
        """Extract Wikipedia search queries from LLM response.

        Args:
            response: LLM response text

        Returns:
            List of extracted queries
        """
        return self.coordinator.extract_wikipedia_queries(response)

    async def search_wikipedia_multi_query(
        self,
        queries: Union[List[str], Dict[str, List[str]]],
        original_prompt: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> Tuple[Optional[str], Optional[WikipediaMetadata]]:
        """Search Wikipedia across multiple queries and languages.

        Args:
            queries: Either list of queries or dict mapping language -> queries
            original_prompt: Original user prompt
            chat_history: Optional chat history

        Returns:
            Tuple of (context string, metadata)
        """
        return await self.coordinator.search_wikipedia_multi_query(
            queries=queries,
            original_prompt=original_prompt,
            chat_history=chat_history
        )

    def build_wikipedia_context(self, articles: List[Dict]) -> str:
        """Build Wikipedia context string from articles.

        Args:
            articles: List of articles

        Returns:
            Formatted context string
        """
        return self.coordinator.build_wikipedia_context(articles)

    def build_wiki_url(self, pageid: Optional[int], language: Optional[str] = None) -> str:
        """Build Wikipedia URL.

        Args:
            pageid: Page ID
            language: Language code

        Returns:
            Wikipedia URL
        """
        return self.coordinator.build_wiki_url(pageid, language)
