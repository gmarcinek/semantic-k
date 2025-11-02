"""Wikipedia search coordinator service for orchestrating the search process."""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple, Union
from app.models import WikipediaMetadata, WikipediaSource, WikipediaIntentResult, WikipediaIntentTopic
from app.services.wikipedia_service import WikipediaService
from app.services.reranker_service import RankedResult
from app.services.wikipedia.query_normalizer_service import QueryNormalizerService
from app.services.wikipedia.article_fetcher_service import ArticleFetcherService
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


class WikipediaSearchCoordinatorService:
    """Service for coordinating Wikipedia search across multiple queries and languages."""

    def __init__(
        self,
        wikipedia_service,
        reranker_service,
        config_service,
        wikipedia_intent_service=None,
        translation_service: Optional[TranslationService] = None
    ):
        self.wikipedia_service = wikipedia_service
        self.reranker_service = reranker_service
        self.config_service = config_service
        self.wikipedia_intent_service = wikipedia_intent_service
        self.translation_service = translation_service

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
        pattern = r'\[WIKIPEDIA_SEARCH:\s*([^\]]+)\]'
        matches = re.findall(pattern, response or "")
        return [m.strip() for m in matches if m and m.strip()]

    def _get_service_for_language(self, language: Optional[str]) -> WikipediaService:
        return self.query_normalizer._get_service_for_language(language)

    async def search_wikipedia_multi_query(
        self,
        queries: Union[List[str], Dict[str, List[str]]],
        original_prompt: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> Tuple[Optional[str], Optional[WikipediaMetadata]]:
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

        # Determine search order (primary first, then configured fallbacks, then dynamic languages)
        languages_to_search: List[str] = []
        seen_languages: set = set()
        for lang in [self.primary_language, *self.fallback_languages, *queries_map.keys()]:
            normalized = (lang or "").strip().lower()
            if not normalized or normalized in seen_languages:
                continue
            seen_languages.add(normalized)
            languages_to_search.append(normalized)

        # Launch per-language searches concurrently
        search_tasks: Dict[str, asyncio.Task] = {}
        for lang in languages_to_search:
            lang_queries = queries_map.get(lang)
            if lang == self.primary_language:
                lang_queries = lang_queries or [original_prompt]
            if not lang_queries:
                continue
            search_tasks[lang] = asyncio.create_task(
                self._collect_results_for_language(
                    language=lang,
                    queries=lang_queries,
                    per_query_limit=per_query_limit,
                    per_language_cap=max_total
                )
            )

        language_results: Dict[str, List[Dict]] = {}
        if search_tasks:
            task_results = await asyncio.gather(*search_tasks.values(), return_exceptions=True)
            for lang, result in zip(search_tasks.keys(), task_results):
                if isinstance(result, Exception):
                    logger.error(
                        "Wikipedia language '%s' search failed: %s",
                        lang,
                        result
                    )
                    continue
                language_results[lang] = result

        primary_results = language_results.get(self.primary_language, [])

        combined_results: List[Dict] = []
        seen_pageids: set = set()
        seen_titles: set = set()
        fallback_contributions: Dict[str, int] = {}

        def append_results(results: List[Dict], lang: str, collector: Optional[List[Dict]] = None) -> int:
            added = 0
            for result in results:
                if len(combined_results) >= max_total:
                    break
                pid = result.get('pageid')
                title_key = (result.get('title') or '').strip().lower()

                composite_pid = f"{lang}:{pid}" if pid is not None else None
                composite_title = f"{lang}:{title_key}" if title_key else None

                if composite_pid and composite_pid in seen_pageids:
                    continue
                if composite_title and composite_title in seen_titles:
                    continue

                combined_results.append(result)
                added += 1

                if collector is not None:
                    collector.append(result)

                if composite_pid:
                    seen_pageids.add(composite_pid)
                if composite_title:
                    seen_titles.add(composite_title)
            return added

        append_results(primary_results, self.primary_language)

        for lang in languages_to_search:
            if lang == self.primary_language or len(combined_results) >= max_total:
                continue
            lang_results = language_results.get(lang)
            if not lang_results:
                continue
            added = append_results(lang_results, lang)
            if added:
                fallback_contributions[lang] = added

        for lang, contributed in fallback_contributions.items():
            logger.info(
                "Wikipedia language '%s' contributed %d results",
                lang,
                contributed
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

        if self.translation_service:
            articles, sources = await self.translation_service.translate_articles_and_sources(
                articles,
                sources,
                default_language=self.primary_language
            )
        else:
            articles, sources = self._apply_language_prefix(articles, sources)

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
        per_language_cap: int
    ) -> List[Dict]:
        service = self._get_service_for_language(language)
        language_results: List[Dict] = []
        seen_pageids: set = set()
        seen_titles: set = set()

        for query in queries[:3]:
            if len(language_results) >= per_language_cap:
                break
            search_results = await service.search(query=query, limit=per_query_limit)
            if not search_results:
                continue

            for result in search_results:
                if len(language_results) >= per_language_cap:
                    break

                pid = result.get('pageid')
                title_key = (result.get('title') or '').strip().lower()

                if pid is not None and pid in seen_pageids:
                    continue
                if title_key and title_key in seen_titles:
                    continue

                result_with_lang = dict(result)
                result_with_lang['language'] = language

                language_results.append(result_with_lang)

                if pid is not None:
                    seen_pageids.add(pid)
                if title_key:
                    seen_titles.add(title_key)

        return language_results

    async def _analyze_intent(
        self,
        prompt: str,
        candidates: List[RankedResult],
        chat_history: Optional[List[Dict]] = None
    ) -> WikipediaIntentResult:
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
        return self.article_fetcher.build_wikipedia_context(articles)

    def build_wiki_url(self, pageid: Optional[int], language: Optional[str] = None) -> str:
        return self.article_fetcher.build_wiki_url(
            pageid,
            language,
            getattr(self.wikipedia_service, "language", None)
        )

    def _apply_language_prefix(
        self,
        articles: List[Dict],
        sources: List[WikipediaSource]
    ) -> Tuple[List[Dict], List[WikipediaSource]]:
        formatted_articles: List[Dict] = []
        for article in articles:
            lang = (article.get("language") or self.primary_language).lower()
            formatted_articles.append({
                **article,
                "title": self._format_with_language_code(article.get("title", ""), lang),
                "language": lang
            })

        formatted_sources: List[WikipediaSource] = []
        for source in sources:
            lang = (source.language or self.primary_language).lower()
            formatted_sources.append(
                source.model_copy(
                    update={
                        "title": self._format_with_language_code(source.title, lang),
                        "language": lang
                    }
                )
            )
        return formatted_articles, formatted_sources

    def _format_with_language_code(self, text: str, language: Optional[str]) -> str:
        code = (language or self.primary_language or "unknown").upper()
        prefix = f"({code})"
        content = (text or "").strip()
        if content.upper().startswith(prefix):
            return content
        if content:
            return f"{prefix} {content}"
        return prefix
