import logging
import re
from typing import Dict, List, Optional, Tuple

from app.models import WikipediaMetadata, WikipediaSource, WikipediaIntentResult, WikipediaIntentTopic
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

    def extract_wikipedia_queries(self, response: str) -> List[str]:

        pattern = r'\[WIKIPEDIA_SEARCH:\s*([^\]]+)\]'
        matches = re.findall(pattern, response or "")
        return [m.strip() for m in matches if m and m.strip()]

    async def search_wikipedia_multi_query(
        self,
        queries: List[str],
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

        combined_results: List[Dict] = []
        seen_pageids = set()
        seen_titles = set()

        for query in queries[:3]:
            search_results = await self.wikipedia_service.search(query=query, limit=per_query_limit)
            if not search_results:
                continue

            for result in search_results:
                pid = result.get('pageid')
                title_key = (result.get('title') or '').strip().lower()

                if pid in seen_pageids or (title_key and title_key in seen_titles):
                    continue

                combined_results.append(result)
                if pid is not None:
                    seen_pageids.add(pid)
                if title_key:
                    seen_titles.add(title_key)

                if len(combined_results) >= max_total:
                    break

            if len(combined_results) >= max_total:
                break

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
                    reasoning="Reranking disabled"
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

        metadata = WikipediaMetadata(
            query=", ".join(queries[:3]),
            sources=sources,
            total_results=len(combined_results),
            reranked=bool(rerank_cfg.get('enabled', True)),
            reranking_model=rerank_cfg.get('model') if rerank_cfg.get('enabled', True) else None,
            primary_topic=intent_result.primary.title if intent_result and intent_result.primary else articles[0].get("title"),
            primary_pageid=articles[0].get("pageid"),
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
                    {"pageid": r.pageid, "title": r.title, "snippet": r.snippet}
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
        seen_context_pageids = {primary_candidate.pageid}

        if intent_result and intent_result.context:
            for topic in intent_result.context:
                if len(resolved_context_pairs) >= context_capacity:
                    break
                candidate = self._match_topic(topic, ranked_results)
                if not candidate:
                    continue
                if candidate.pageid in seen_context_pageids:
                    continue
                if candidate.pageid is not None:
                    seen_context_pageids.add(candidate.pageid)
                    topic.pageid = candidate.pageid
                resolved_context_pairs.append((topic, candidate))

        if context_capacity > len(resolved_context_pairs):
            for candidate in ranked_results:
                if candidate.pageid in seen_context_pageids:
                    continue
                topic = WikipediaIntentTopic(
                    pageid=candidate.pageid,
                    title=candidate.title,
                    role="CONTEXT",
                    reasoning="Auto-selected from top-ranked results."
                )
                resolved_context_pairs.append((topic, candidate))
                if candidate.pageid is not None:
                    seen_context_pageids.add(candidate.pageid)
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
        ))

        for topic, candidate in resolved_context_pairs:
            if len(articles) >= max_total:
                break
            summary = await self.wikipedia_service.get_summary_by_title(candidate.title)
            extract = (summary or {}).get("extract", candidate.snippet)
            url = (summary or {}).get("url") or self.build_wiki_url(candidate.pageid)
            context_article = {
                "title": candidate.title,
                "extract": extract,
                "url": url,
                "pageid": candidate.pageid,
                "image_url": None,
                "images": []
            }
            articles.append(context_article)
            sources.append(WikipediaSource(
                title=candidate.title,
                url=url,
                pageid=candidate.pageid or 0,
                extract=extract[:800],
                relevance_score=candidate.relevance_score,
                image_url=None,
                images=[]
            ))

        return sources, articles

    async def _fetch_primary_article(
        self,
        primary_candidate: RankedResult,
        extract_length: int
    ) -> Dict:

        primary_article = None
        try:
            if primary_candidate.pageid:
                primary_article = await self.wikipedia_service.get_full_article_by_pageid(
                    pageid=primary_candidate.pageid,
                    max_chars=extract_length
                )
        except Exception as exc:
            logger.error("Failed to fetch full primary article: %s", exc)

        if not primary_article:
            summary = await self.wikipedia_service.get_summary_by_title(primary_candidate.title)
            primary_article = {
                "title": primary_candidate.title,
                "extract": (summary or {}).get("extract", primary_candidate.snippet),
                "url": (summary or {}).get("url") or self.build_wiki_url(primary_candidate.pageid),
                "pageid": primary_candidate.pageid,
                "image_url": (summary or {}).get("thumbnail_url"),
                "images": []
            }
        else:
            if not primary_article.get("url"):
                primary_article["url"] = self.build_wiki_url(primary_candidate.pageid)
            try:
                summary_extra = await self.wikipedia_service.get_summary_by_title(primary_article.get("title", ""))
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
                    media = await self.wikipedia_service._fetch_media_by_title(primary_article.get("title", ""))
                    if media:
                        primary_article["images"] = media[:12]
                except Exception:
                    primary_article["images"] = []

        return primary_article

    def build_wikipedia_context(self, articles: List[Dict]) -> str:

        context_parts = []
        for i, article in enumerate(articles, 1):
            title = article.get("title", "Unknown")
            url = article.get("url", "")
            extract = article.get("extract", "")
            image = article.get("image_url") or article.get("thumbnail") or ""

            block = (
                f"Article {i}: {title}\n"
                f"URL: {url}\n"
                f"Content: {extract}\n"
            )
            if image:
                block += f"Image: {image}\n"
            context_parts.append(block)

        return "\n".join(context_parts)

    def build_wiki_url(self, pageid: Optional[int]) -> str:

        if not pageid:
            return ""
        language = getattr(self.wikipedia_service, "language", "pl")
        return f"https://{language}.wikipedia.org/?curid={pageid}"
