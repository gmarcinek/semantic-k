"""Wikipedia search coordinator service for orchestrating the search process."""
import logging
import re
from typing import Dict, List, Optional, Tuple, Union
from app.models import WikipediaMetadata, WikipediaSource, WikipediaIntentResult, WikipediaIntentTopic
from app.services.wikipedia_service import WikipediaService
from app.services.reranker_service import RankedResult
from app.services.wikipedia.query_normalizer_service import QueryNormalizerService
from app.services.wikipedia.article_fetcher_service import ArticleFetcherService

logger = logging.getLogger(__name__)


class WikipediaSearchCoordinatorService:
    """Service for coordinating Wikipedia search across multiple queries and languages."""

    def __init__(
        self,
        wikipedia_service,
        reranker_service,
        config_service,
        wikipedia_intent_service=None
    ):
        """Initialize Wikipedia search coordinator.

        Args:
            wikipedia_service: Base Wikipedia service
            reranker_service: Service for reranking results
            config_service: Configuration service
            wikipedia_intent_service: Optional intent analysis service
        """
        self.wikipedia_service = wikipedia_service
        self.reranker_service = reranker_service
        self.config_service = config_service
        self.wikipedia_intent_service = wikipedia_intent_service

        wiki_cfg = self.config_service.config.get('wikipedia', {})

        # Setup primary language
        base_language = getattr(self.wikipedia_service, "language", None) or wiki_cfg.get('language', 'pl')
        self.primary_language = (base_language or 'pl').strip().lower() or 'pl'
        self.wikipedia_service.language = self.primary_language
        self.wikipedia_service.base_url = f"https://{self.primary_language}.wikipedia.org/w/api.php"

        # Setup fallback languages
        fallback_cfg = wiki_cfg.get('fallback_languages', ['en', 'de', 'es', 'fr'])
        if isinstance(fallback_cfg, str):
            fallback_cfg = [fallback_cfg]
        self.fallback_languages = [
            str(lang).strip().lower()
            for lang in (fallback_cfg or [])
            if str(lang).strip() and str(lang).strip().lower() != self.primary_language
        ]

        self._language_services: Dict[str, WikipediaService] = {self.primary_language: self.wikipedia_service}

        # Initialize sub-services
        self.query_normalizer = QueryNormalizerService(
            primary_language=self.primary_language,
            fallback_languages=self.fallback_languages,
            language_services=self._language_services
        )
        self.article_fetcher = ArticleFetcherService(primary_language=self.primary_language)

    def extract_wikipedia_queries(self, response: str) -> List[str]:
        """Extract Wikipedia search queries from LLM response.

        Args:
            response: LLM response text

        Returns:
            List of extracted queries
        """
        pattern = r'\[WIKIPEDIA_SEARCH:\s*([^\]]+)\]'
        matches = re.findall(pattern, response or "")
        return [m.strip() for m in matches if m and m.strip()]

    def _get_service_for_language(self, language: Optional[str]) -> WikipediaService:
        """Get or create Wikipedia service for a specific language.

        Args:
            language: Language code

        Returns:
            WikipediaService instance
        """
        return self.query_normalizer._get_service_for_language(language)

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
        wiki_cfg = self.config_service.config.get('wikipedia', {})
        rerank_cfg = wiki_cfg.get('reranking', {})
        search_cfg = wiki_cfg.get('search', {})

        max_total = int(search_cfg.get('max_results', 10) or 10)
        max_total = max(1, min(max_total, 10))
        per_query_limit = int(search_cfg.get('per_query_limit', max_total) or max_total)
        per_query_limit = max(1, per_query_limit)
        extract_length = int(search_cfg.get('extract_length', 50000) or 50000)

        # Normalize queries by language
        configured_languages = [self.primary_language, *self.fallback_languages]
        queries_map = self.query_normalizer.normalize_queries_by_language(
            queries,
            configured_languages,
            original_prompt
        )

        # Build fallback sequence
        fallback_sequence: List[str] = []
        for lang in self.fallback_languages:
            if lang != self.primary_language and lang not in fallback_sequence:
                fallback_sequence.append(lang)
        for lang in queries_map.keys():
            if lang != self.primary_language and lang not in fallback_sequence:
                fallback_sequence.append(lang)

        # Collect results
        combined_results: List[Dict] = []
        seen_pageids: set = set()
        seen_titles: set = set()

        primary_results = await self._collect_results_for_language(
            self.primary_language,
            queries_map.get(self.primary_language, [original_prompt]),
            per_query_limit,
            max_total,
            combined_results,
            seen_pageids,
            seen_titles
        )

        # Add fallback results if needed
        if self.query_normalizer._needs_additional_results(primary_results, max_total):
            for fallback_lang in fallback_sequence:
                if len(combined_results) >= max_total:
                    break
                fallback_queries = queries_map.get(fallback_lang, [])
                if not fallback_queries:
                    continue
                fallback_results = await self._collect_results_for_language(
                    fallback_lang,
                    fallback_queries,
                    per_query_limit,
                    max_total,
                    combined_results,
                    seen_pageids,
                    seen_titles
                )
                if fallback_results:
                    logger.info(
                        "Wikipedia fallback language '%s' contributed %d results",
                        fallback_lang,
                        len(fallback_results)
                    )

        if not combined_results:
            return None, None

        # Rerank results
        if rerank_cfg.get('enabled', True):
            ranked_results: List[RankedResult] = await self.reranker_service.rerank_results(
                query=original_prompt,
                search_results=combined_results,
                top_n=min(len(combined_results), max_total),
                model=rerank_cfg.get('model', 'gpt-4.1-mini')
            )
        else:
            ranked_results = [
                RankedResult(
                    pageid=result.get('pageid', 0),
                    title=result.get('title', ''),
                    snippet=result.get('snippet', ''),
                    relevance_score=max(0.0, 1.0 - (idx * 0.05)),
                    reasoning="Reranking disabled",
                    language=(result.get('language') or self.primary_language or "pl").lower()
                )
                for idx, result in enumerate(combined_results[:max_total])
            ]

        if not ranked_results:
            return None, None

        # Analyze intent
        intent_result = await self._analyze_intent(
            original_prompt,
            ranked_results,
            chat_history
        )

        # Match primary topic
        primary_candidate = self._match_topic(intent_result.primary, ranked_results) if intent_result else None
        if not primary_candidate and ranked_results:
            primary_candidate = ranked_results[0]
            if intent_result:
                intent_result.primary = WikipediaIntentTopic(
                    pageid=primary_candidate.pageid,
                    title=primary_candidate.title,
                    role="PRIMARY",
                    reasoning="Defaulted to top-ranked result."
                )

        if not primary_candidate:
            return None, None

        # Resolve context topics
        resolved_context_pairs = self._resolve_context_topics(
            intent_result,
            ranked_results,
            primary_candidate,
            max_total
        )

        # Fetch articles
        sources, articles = await self.article_fetcher.fetch_articles(
            primary_candidate,
            resolved_context_pairs,
            extract_length,
            max_total,
            self._get_service_for_language,
            lambda pid, lang: self.article_fetcher.build_wiki_url(
                pid,
                lang,
                getattr(self.wikipedia_service, "language", None)
            )
        )

        # Build context and metadata
        wiki_context = self.article_fetcher.build_wikipedia_context(articles)
        primary_language = articles[0].get("language", self.primary_language) if articles else self.primary_language
        languages_used = sorted({
            source.language.lower()
            for source in sources
            if getattr(source, "language", None)
        })

        query_summary_parts = [
            f"{lang}: {', '.join((lang_queries or [])[:3])}"
            for lang, lang_queries in queries_map.items()
            if lang_queries
        ]
        query_summary = "; ".join(query_summary_parts) if query_summary_parts else original_prompt
        queries_for_metadata = {
            lang: list(lang_queries)
            for lang, lang_queries in queries_map.items()
        }

        metadata = WikipediaMetadata(
            query=query_summary,
            sources=sources,
            total_results=len(combined_results),
            reranked=bool(rerank_cfg.get('enabled', True)),
            reranking_model=rerank_cfg.get('model') if rerank_cfg.get('enabled', True) else None,
            primary_topic=intent_result.primary.title if intent_result and intent_result.primary else articles[0].get("title"),
            primary_pageid=articles[0].get("pageid"),
            primary_language=primary_language,
            languages_used=languages_used,
            queries_by_language=queries_for_metadata,
            context_topics=[topic for topic, _ in resolved_context_pairs],
            intent_notes=intent_result.notes if intent_result else None
        )

        return wiki_context, metadata

    async def _collect_results_for_language(
        self,
        language: str,
        queries: List[str],
        per_query_limit: int,
        max_total: int,
        combined_results: List[Dict],
        seen_pageids: set,
        seen_titles: set
    ) -> List[Dict]:
        """Collect search results for a specific language.

        Args:
            language: Language code
            queries: List of queries to search
            per_query_limit: Limit per query
            max_total: Maximum total results
            combined_results: Combined results list to append to
            seen_pageids: Set of seen page IDs
            seen_titles: Set of seen titles

        Returns:
            List of results for this language
        """
        service = self._get_service_for_language(language)
        language_results: List[Dict] = []

        for query in queries[:3]:
            search_results = await service.search(query=query, limit=per_query_limit)
            if not search_results:
                continue

            for result in search_results:
                pid = result.get('pageid')
                title_key = (result.get('title') or '').strip().lower()

                composite_pid = f"{language}:{pid}" if pid is not None else None
                composite_title = f"{language}:{title_key}" if title_key else None

                if composite_pid and composite_pid in seen_pageids:
                    continue
                if composite_title and composite_title in seen_titles:
                    continue

                result_with_lang = dict(result)
                result_with_lang['language'] = language

                combined_results.append(result_with_lang)
                language_results.append(result_with_lang)

                if composite_pid:
                    seen_pageids.add(composite_pid)
                if composite_title:
                    seen_titles.add(composite_title)

                if len(combined_results) >= max_total:
                    return language_results

        return language_results

    async def _analyze_intent(
        self,
        prompt: str,
        candidates: List[RankedResult],
        chat_history: Optional[List[Dict]] = None
    ) -> WikipediaIntentResult:
        """Analyze user intent from prompt and candidates.

        Args:
            prompt: User prompt
            candidates: Ranked candidates
            chat_history: Optional chat history

        Returns:
            Intent analysis result
        """
        if self.wikipedia_intent_service:
            return await self.wikipedia_intent_service.analyze(
                prompt=prompt,
                candidates=[
                    {
                        "pageid": r.pageid,
                        "title": r.title,
                        "snippet": r.snippet,
                        "language": getattr(r, "language", self.primary_language)
                    }
                    for r in candidates
                ],
                chat_history=chat_history
            )
        else:
            primary_candidate = candidates[0]
            return WikipediaIntentResult(
                primary=WikipediaIntentTopic(
                    pageid=primary_candidate.pageid,
                    title=primary_candidate.title,
                    role="PRIMARY",
                    reasoning="Defaulted to top-ranked result (intent service unavailable)."
                ),
                context=[],
                ignored=[],
                notes="Intent service unavailable; using top-ranked result."
            )

    def _match_topic(
        self,
        topic: Optional[WikipediaIntentTopic],
        candidates: List[RankedResult]
    ) -> Optional[RankedResult]:
        """Match a topic to a candidate from results.

        Args:
            topic: Topic to match
            candidates: List of candidates

        Returns:
            Matching candidate or None
        """
        if not topic:
            return None
        if topic.pageid is not None:
            for candidate in candidates:
                if candidate.pageid == topic.pageid:
                    return candidate
        title_lower = topic.title.strip().lower()
        if title_lower:
            for candidate in candidates:
                if candidate.title.strip().lower() == title_lower:
                    return candidate
        return None

    def _resolve_context_topics(
        self,
        intent_result: WikipediaIntentResult,
        ranked_results: List[RankedResult],
        primary_candidate: RankedResult,
        max_total: int
    ) -> List[Tuple[WikipediaIntentTopic, RankedResult]]:
        """Resolve context topics from intent analysis.

        Args:
            intent_result: Intent analysis result
            ranked_results: Ranked search results
            primary_candidate: Primary candidate
            max_total: Maximum total articles

        Returns:
            List of (topic, candidate) pairs
        """
        resolved_context_pairs: List[Tuple[WikipediaIntentTopic, RankedResult]] = []
        context_capacity = max_total - 1
        primary_key = (
            primary_candidate.pageid,
            getattr(primary_candidate, "language", self.primary_language)
        )
        seen_context_ids = {primary_key}

        if intent_result and intent_result.context:
            for topic in intent_result.context:
                if len(resolved_context_pairs) >= context_capacity:
                    break
                candidate = self._match_topic(topic, ranked_results)
                if not candidate:
                    continue
                candidate_key = (
                    candidate.pageid,
                    getattr(candidate, "language", self.primary_language)
                )
                if candidate_key in seen_context_ids:
                    continue
                if candidate.pageid is not None:
                    seen_context_ids.add(candidate_key)
                    topic.pageid = candidate.pageid
                resolved_context_pairs.append((topic, candidate))

        if context_capacity > len(resolved_context_pairs):
            for candidate in ranked_results:
                candidate_key = (
                    candidate.pageid,
                    getattr(candidate, "language", self.primary_language)
                )
                if candidate_key in seen_context_ids:
                    continue
                topic = WikipediaIntentTopic(
                    pageid=candidate.pageid,
                    title=candidate.title,
                    role="CONTEXT",
                    reasoning="Auto-selected from top-ranked results."
                )
                resolved_context_pairs.append((topic, candidate))
                if candidate.pageid is not None:
                    seen_context_ids.add(candidate_key)
                if len(resolved_context_pairs) >= context_capacity:
                    break

        return resolved_context_pairs

    def build_wikipedia_context(self, articles: List[Dict]) -> str:
        """Build Wikipedia context string from articles.

        Args:
            articles: List of articles

        Returns:
            Formatted context string
        """
        return self.article_fetcher.build_wikipedia_context(articles)

    def build_wiki_url(self, pageid: Optional[int], language: Optional[str] = None) -> str:
        """Build Wikipedia URL.

        Args:
            pageid: Page ID
            language: Language code

        Returns:
            Wikipedia URL
        """
        return self.article_fetcher.build_wiki_url(
            pageid,
            language,
            getattr(self.wikipedia_service, "language", None)
        )
