"""Query normalizer service for processing multilingual Wikipedia queries."""
import logging
from typing import Dict, List, Optional, Union
from app.services.wikipedia_service import WikipediaService

logger = logging.getLogger(__name__)


class QueryNormalizerService:
    """Service for normalizing and processing multilingual Wikipedia queries."""

    def __init__(
        self,
        primary_language: str,
        fallback_languages: List[str],
        language_services: Optional[Dict[str, WikipediaService]] = None
    ):
        """Initialize query normalizer.

        Args:
            primary_language: Primary Wikipedia language code
            fallback_languages: List of fallback language codes
            language_services: Optional mapping of language -> WikipediaService
        """
        self.primary_language = primary_language
        self.fallback_languages = fallback_languages
        self._language_services = language_services or {}

    def normalize_queries_by_language(
        self,
        queries: Union[List[str], Dict[str, List[str]]],
        languages: List[str],
        fallback_prompt: str
    ) -> Dict[str, List[str]]:
        """Normalize queries by language, ensuring coverage for all target languages.

        Args:
            queries: Either a list of queries or a dict mapping language -> queries
            languages: List of target languages to support
            fallback_prompt: Fallback query if no queries provided

        Returns:
            Dictionary mapping language code -> list of queries
        """
        max_per_language = 6
        normalized: Dict[str, List[str]] = {}

        if isinstance(queries, dict):
            cleaned_input: Dict[str, List[str]] = {}
            fallback_list: Optional[List[str]] = None

            for key, values in queries.items():
                lang_code = str(key or "").strip().lower()
                if not lang_code:
                    continue
                cleaned_values = [
                    str(q or "").strip()
                    for q in (values or [])
                    if str(q or "").strip()
                ][:max_per_language]
                if cleaned_values:
                    cleaned_input[lang_code] = cleaned_values
                    if fallback_list is None:
                        fallback_list = cleaned_values

            if fallback_list is None:
                fallback_list = [fallback_prompt]

            for lang in languages:
                lang_queries = cleaned_input.get(lang) or fallback_list
                normalized[lang] = list(lang_queries[:max_per_language])

            for lang, lang_queries in cleaned_input.items():
                if lang not in normalized:
                    normalized[lang] = list(lang_queries[:max_per_language])

        else:
            cleaned_list = [
                str(q or "").strip()
                for q in (queries or [])
                if str(q or "").strip()
            ][:max_per_language]
            if not cleaned_list:
                cleaned_list = [fallback_prompt]

            for lang in languages:
                normalized[lang] = list(cleaned_list[:max_per_language])

        return normalized

    def _get_service_for_language(self, language: Optional[str]) -> WikipediaService:
        """Get or create Wikipedia service for a specific language.

        Args:
            language: Language code

        Returns:
            WikipediaService instance for the language
        """
        lang = (language or self.primary_language or 'pl').strip().lower() or 'pl'
        service = self._language_services.get(lang)
        if service:
            return service

        service = WikipediaService(language=lang)
        self._language_services[lang] = service
        return service

    @staticmethod
    def _is_low_quality(results: List[Dict]) -> bool:
        """Check if search results are low quality based on snippet length.

        Args:
            results: List of search results

        Returns:
            True if results are low quality
        """
        if not results:
            return True
        poor_snippets = sum(
            1 for res in results if len((res.get("snippet") or "").strip()) < 40
        )
        return poor_snippets >= max(1, int(len(results) * 0.75))

    def _needs_additional_results(
        self,
        primary_results: List[Dict],
        max_total: int
    ) -> bool:
        """Determine if additional results from fallback languages are needed.

        Args:
            primary_results: Results from primary language
            max_total: Maximum total results desired

        Returns:
            True if more results needed
        """
        if not primary_results:
            return True

        fallback_threshold = max(1, (max_total + 1) // 2)
        if len(primary_results) < fallback_threshold:
            return True

        return self._is_low_quality(primary_results)
