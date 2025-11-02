import logging
import re
from typing import Dict, List, Optional, Tuple, Union

from app.models import WikipediaMetadata, WikipediaSource, WikipediaIntentResult, WikipediaIntentTopic
from app.services.wikipedia_service import WikipediaService
from app.services.reranker_service import RankedResult

logger = logging.getLogger(__name__)

class WikipediaSearchService:

    def __init__(
        self,
        wikipedia_service,
        reranker_service,
        config_service,
        wikipedia_intent_service=None
    ):

        self.wikipedia_service = wikipedia_service
        self.reranker_service = reranker_service
        self.config_service = config_service
        self.wikipedia_intent_service = wikipedia_intent_service

        wiki_cfg = self.config_service.config.get('wikipedia', {})

        base_language = getattr(self.wikipedia_service, "language", None) or wiki_cfg.get('language', 'pl')
        self.primary_language = (base_language or 'pl').strip().lower() or 'pl'
        # Ensure base service uses normalized language code
        self.wikipedia_service.language = self.primary_language
        self.wikipedia_service.base_url = f"https://{self.primary_language}.wikipedia.org/w/api.php"

        fallback_cfg = wiki_cfg.get('fallback_languages', ['en', 'de', 'es', 'fr'])
        if isinstance(fallback_cfg, str):
            fallback_cfg = [fallback_cfg]
        self.fallback_languages = [
            str(lang).strip().lower()
            for lang in (fallback_cfg or [])
            if str(lang).strip() and str(lang).strip().lower() != self.primary_language
        ]

        self._language_services: Dict[str, WikipediaService] = {self.primary_language: self.wikipedia_service}

    def extract_wikipedia_queries(self, response: str) -> List[str]:

        pattern = r'\[WIKIPEDIA_SEARCH:\s*([^\]]+)\]'
        matches = re.findall(pattern, response or "")
        return [m.strip() for m in matches if m and m.strip()]

    def _get_service_for_language(self, language: Optional[str]) -> WikipediaService:

        lang = (language or self.primary_language or 'pl').strip().lower() or 'pl'
        service = self._language_services.get(lang)
        if service:
            return service

        service = WikipediaService(language=lang)
        self._language_services[lang] = service
        return service

    def _normalize_queries_by_language(
        self,
        queries: Union[List[str], Dict[str, List[str]]],
        languages: List[str],
        fallback_prompt: str
    ) -> Dict[str, List[str]]:

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

    @staticmethod
    def _is_low_quality(results: List[Dict]) -> bool:

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

        if not primary_results:
            return True

        fallback_threshold = max(1, (max_total + 1) // 2)  # ceil(max_total / 2)
        if len(primary_results) < fallback_threshold:
            return True

        return self._is_low_quality(primary_results)

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

        configured_languages = [self.primary_language, *self.fallback_languages]
        queries_map = self._normalize_queries_by_language(
            queries,
            configured_languages,
            original_prompt
        )
        fallback_sequence: List[str] = []
        for lang in self.fallback_languages:
            if lang != self.primary_language and lang not in fallback_sequence:
                fallback_sequence.append(lang)
        for lang in queries_map.keys():
            if lang != self.primary_language and lang not in fallback_sequence:
                fallback_sequence.append(lang)

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

        if self._needs_additional_results(primary_results, max_total):
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

        intent_result = await self._analyze_intent(
            original_prompt,
            ranked_results,
            chat_history
        )

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

        resolved_context_pairs = self._resolve_context_topics(
            intent_result,
            ranked_results,
            primary_candidate,
            max_total
        )

        sources, articles = await self._fetch_articles(
            primary_candidate,
            resolved_context_pairs,
            extract_length,
            max_total
        )

        wiki_context = self.build_wikipedia_context(articles)
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

    async def _fetch_articles(
        self,
        primary_candidate: RankedResult,
        resolved_context_pairs: List[Tuple[WikipediaIntentTopic, RankedResult]],
        extract_length: int,
        max_total: int
    ) -> Tuple[List[WikipediaSource], List[Dict]]:

        sources: List[WikipediaSource] = []
        articles: List[Dict] = []

        primary_article = await self._fetch_primary_article(primary_candidate, extract_length)
        articles.append(primary_article)
        sources.append(WikipediaSource(
            title=primary_article.get("title", ""),
            url=primary_article.get("url", ""),
            pageid=primary_article.get("pageid", 0) or 0,
            extract=(primary_article.get("extract", "") or "")[:6000],
            relevance_score=primary_candidate.relevance_score,
            image_url=primary_article.get("image_url"),
            images=primary_article.get("images", []),
            language=primary_article.get("language"),
        ))

        for topic, candidate in resolved_context_pairs:
            if len(articles) >= max_total:
                break
            service = self._get_service_for_language(candidate.language)
            summary = await service.get_summary_by_title(candidate.title)
            extract = (summary or {}).get("extract", candidate.snippet)
            url = (summary or {}).get("url") or self.build_wiki_url(candidate.pageid, candidate.language)
            context_article = {
                "title": candidate.title,
                "extract": extract,
                "url": url,
                "pageid": candidate.pageid,
                "image_url": None,
                "images": [],
                "language": (getattr(service, "language", self.primary_language) or self.primary_language).lower()
            }
            articles.append(context_article)
            sources.append(WikipediaSource(
                title=candidate.title,
                url=url,
                pageid=candidate.pageid or 0,
                extract=extract[:800],
                relevance_score=candidate.relevance_score,
                image_url=None,
                images=[],
                language=context_article.get("language")
            ))

        return sources, articles

    async def _fetch_primary_article(
        self,
        primary_candidate: RankedResult,
        extract_length: int
    ) -> Dict:

        primary_article = None
        service = self._get_service_for_language(primary_candidate.language)
        language = (getattr(service, "language", self.primary_language) or self.primary_language).lower()

        try:
            if primary_candidate.pageid:
                primary_article = await service.get_full_article_by_pageid(
                    pageid=primary_candidate.pageid,
                    max_chars=extract_length
                )
        except Exception as exc:
            logger.error("Failed to fetch full primary article: %s", exc)

        if not primary_article:
            summary = await service.get_summary_by_title(primary_candidate.title)
            primary_article = {
                "title": primary_candidate.title,
                "extract": (summary or {}).get("extract", primary_candidate.snippet),
                "url": (summary or {}).get("url") or self.build_wiki_url(primary_candidate.pageid, language),
                "pageid": primary_candidate.pageid,
                "image_url": (summary or {}).get("thumbnail_url"),
                "images": [],
                "language": language
            }
        else:
            if not primary_article.get("url"):
                primary_article["url"] = self.build_wiki_url(primary_candidate.pageid, language)
            try:
                summary_extra = await service.get_summary_by_title(primary_article.get("title", ""))
                if summary_extra:
                    if summary_extra.get("thumbnail_url"):
                        primary_article["image_url"] = summary_extra["thumbnail_url"]
                    if summary_extra.get("url"):
                        primary_article["url"] = summary_extra["url"]
                    if not primary_article.get("extract"):
                        primary_article["extract"] = summary_extra.get("extract", "")
            except Exception:
                pass
            if "images" not in primary_article:
                primary_article["images"] = []
            if not primary_article["images"]:
                try:
                    media = await service._fetch_media_by_title(primary_article.get("title", ""))
                    if media:
                        primary_article["images"] = media[:12]
                except Exception:
                    primary_article["images"] = []

            primary_article.setdefault("language", language)

        return primary_article

    def build_wikipedia_context(self, articles: List[Dict]) -> str:

        context_parts = []
        for i, article in enumerate(articles, 1):
            title = article.get("title", "Unknown")
            url = article.get("url", "")
            extract = article.get("extract", "")
            image = article.get("image_url") or article.get("thumbnail") or ""
            language = article.get("language", self.primary_language)

            block = (
                f"Article {i}: {title}\n"
                f"Language: {language}\n"
                f"URL: {url}\n"
                f"Content: {extract}\n"
            )
            if image:
                block += f"Image: {image}\n"
            context_parts.append(block)

        return "\n".join(context_parts)

    def build_wiki_url(self, pageid: Optional[int], language: Optional[str] = None) -> str:

        if not pageid:
            return ""
        lang = (language or self.primary_language or getattr(self.wikipedia_service, "language", "pl")).strip() or "pl"
        return f"https://{lang}.wikipedia.org/?curid={pageid}"
