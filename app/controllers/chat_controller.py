"""Chat controller for handling chat-related operations."""
import asyncio
import json
import logging
from typing import Dict, Optional, List, Tuple
from uuid import uuid4

from app.models import (
    ChatRequest,
    WikipediaSource,
    WikipediaMetadata,
    WikipediaResearchRequest,
    WikipediaIntentResult,
    WikipediaIntentTopic,
)
from app.services.reranker_service import RankedResult

logger = logging.getLogger(__name__)


class ChatController:
    """Controller for chat operations."""

    def __init__(
        self,
        session_service,
        classification_service,
        llm_service,
        config_service,
        wikipedia_service,
        reranker_service,
        query_refiner_service=None,
        wikipedia_intent_service=None
    ):
        """Initialize chat controller.

        Args:
            session_service: Session management service
            classification_service: Prompt classification service
            llm_service: LLM API service
            config_service: Configuration service
            wikipedia_service: Wikipedia API service
            reranker_service: Wikipedia reranker service
        """
        self.session_service = session_service
        self.classification_service = classification_service
        self.llm_service = llm_service
        self.config_service = config_service
        self.wikipedia_service = wikipedia_service
        self.reranker_service = reranker_service
        self.query_refiner_service = query_refiner_service
        self.wikipedia_intent_service = wikipedia_intent_service

    async def handle_chat(self, request: ChatRequest):
        """Handle chat request with streaming response.

        Args:
            request: ChatRequest with prompt and session_id

        Yields:
            Server-Sent Events (SSE) formatted data
        """
        prompt = request.prompt
        session_id = request.session_id or str(uuid4())

        logger.info(f"Processing chat for session {session_id}")

        # Get chat history
        chat_history = self.session_service.get_session(session_id)

        try:
            # Classify the prompt using advisory tools
            metadata = await self.classification_service.classify_prompt(
                prompt, chat_history
            )

            # Send metadata to client
            yield self._format_sse('metadata', metadata.model_dump())

            # Check if prompt is dangerous
            if metadata.is_dangerous > 0.8:
                error_msg = "Request rejected due to security concerns."
                yield self._format_sse('error', error_msg)
                logger.warning(f"Rejected dangerous prompt: {metadata.summary}")
                return

            # Get system prompt and model config based on topic
            system_prompt = self.config_service.get_system_prompt(metadata.topic)
            model_name = self.config_service.get_preferred_model_for_topic(metadata.topic)
            # Enforce: if a mini variant is selected for final summary, use default instead
            if model_name and "mini" in model_name:
                model_name = self.config_service.get_default_model()
            model_config = self.config_service.get_model_config(model_name)

            logger.info(
                f"Generating response: topic={metadata.topic}, model={model_name}"
            )

            # Prepare conversation context
            context = self.session_service.get_conversation_context(session_id, limit=6)

            # If classifier says Wikipedia is needed, search first and present results
            if getattr(metadata, 'needs_wikipedia', False):
                system_prompt = self._enable_wikipedia_tool(system_prompt)

                # Optionally refine queries via LLM
                wiki_cfg = self.config_service.config.get('wikipedia', {})
                qr_cfg = wiki_cfg.get('query_refiner', {})
                queries = [prompt]
                if qr_cfg.get('enabled', False) and self.query_refiner_service:
                    refined = await self.query_refiner_service.refine_queries(
                        prompt=prompt,
                        chat_history=chat_history,
                        language=wiki_cfg.get('language', 'pl'),
                        max_queries=int(qr_cfg.get('max_queries', 3)),
                        model_name=qr_cfg.get('model', 'gpt-4.1-mini')
                    )
                    if refined:
                        queries = refined

                wiki_context, wikipedia_metadata = await self._search_wikipedia_multi_query(
                    queries=queries,
                    original_prompt=prompt,
                    chat_history=chat_history
                )

                if wikipedia_metadata and getattr(wikipedia_metadata, 'sources', None):
                    # Show sources first so buttons are visible
                    yield self._format_sse('wikipedia', wikipedia_metadata.model_dump())

                # Decide behavior based on relevance thresholds (lowered via config)
                sources = wikipedia_metadata.sources if wikipedia_metadata else []
                thr_cfg = self.config_service.config.get('wikipedia', {}).get('thresholds', {})
                answer_thr = float(thr_cfg.get('answer', 0.8))    # previously 0.9
                perfect_thr = float(thr_cfg.get('perfect', 0.98)) # previously ~1.0
                top_answer = [s for s in sources if (s.relevance_score or 0) >= answer_thr]
                perfect = [s for s in sources if (s.relevance_score or 0) >= perfect_thr]

                # Build context with Wikipedia results when we plan to cite
                final_context = list(context)
                if sources:
                    final_context.append({'role': 'system', 'content': f'Wikipedia results:\n{wiki_context}'})

                if perfect:
                    # Fetch full article and generate a source-centric answer
                    best = perfect[0]
                    full_article = await self.wikipedia_service.get_full_article_by_pageid(pageid=best.pageid, max_chars=50000)
                    if full_article:
                        # Try to attach an image via summary
                        summary_extra = await self.wikipedia_service.get_summary_by_title(full_article.get('title', ''))
                        if summary_extra and summary_extra.get('thumbnail_url'):
                            full_article['image_url'] = summary_extra['thumbnail_url']

                        wiki_full_ctx = self._build_wikipedia_context([full_article])
                        final_context.append({'role': 'system', 'content': f'Wikipedia full article (perfect match):\n{wiki_full_ctx}'})

                        # Craft prompt to explicitly state perfect match on Wikipedia
                        title_or = (best.title or full_article.get('title') or '').strip()
                        prompt_text = (
                            f"{prompt}\n\n"
                            "Na Wikipedii jest artykuł, który opisuje to dokładnie. "
                            f"Napisz wprost: Na Wikipedii jest artykuł '{title_or}', który opisuje to dokładnie. "
                            "Przygotuj odpowiedź bazując na treści artykułu (z kontekstu systemowego), dodaj 1–2 krótkie cytaty w bloku cytatu i podaj link. "
                            "Jeśli jest obraz/miniatura, wspomnij o nim i podaj URL obrazu. "
                            "Zachowaj zwięzłość i nie wymyślaj faktów. "
                            "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>). "
                            "Jeśli w kontekście jest linia 'Image: <URL>', możesz dodać <figure><img src=...><figcaption> z podpisem."
                        )

                        response_text = await self.llm_service.generate_chat_response(
                            prompt=prompt_text,
                            chat_history=final_context,
                            system_prompt=system_prompt,
                            model_config=model_config
                        )
                    else:
                        # Fallback to high relevance behavior if full fetch failed
                        perfect = []

                if not perfect:
                    # If we have high-relevance sources (>=0.9), generate a summary based on them
                    if top_answer:
                        cite_lines = "\n".join([
                            f"- {s.title} ({s.url}) [~{int(round((s.relevance_score or 0)*100))}%]"
                            for s in top_answer[:3]
                        ])
                        prompt_text = (
                            "Podsumuj odpowiedź bazując na wynikach z Wikipedii (patrz kontekst systemowy). "
                            "W treści wpleć odniesienia do źródeł, a na końcu wypisz je w formie listy. "
                            "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>).\n"
                            f"{cite_lines}"
                        )

                        response_text = await self.llm_service.generate_chat_response(
                            prompt=prompt_text,
                            chat_history=final_context,
                            system_prompt=system_prompt,
                            model_config=model_config
                        )
                    else:
                        # No Wikipedia sources found despite needs_wikipedia → inform and propose next steps
                        nores_prompt = (
                            "Sformatuj odpowiedź jako prosty HTML. "
                            "<p>Nie znaleziono wiarygodnych wyników w Wikipedii dla tego zapytania.</p> "
                            "<p>Zaproponuj alternatywne zapytania:</p><ul><li>…</li><li>…</li><li>…</li></ul>"
                        )
                        response_text = await self.llm_service.generate_chat_response(
                            prompt=nores_prompt,
                            chat_history=context,
                            system_prompt=system_prompt,
                            model_config=model_config
                        )

                # Stream assistant answer
                chunk_size = 10
                for i in range(0, len(response_text), chunk_size):
                    chunk = response_text[i:i + chunk_size]
                    yield self._format_sse('chunk', chunk)
                    await asyncio.sleep(0.02)

                yield self._format_sse('done', {})

                # Save user message and assistant reply
                user_metadata = metadata.model_dump()
                if wikipedia_metadata:
                    user_metadata['wikipedia'] = wikipedia_metadata.model_dump()

                self.session_service.add_message(
                    session_id=session_id,
                    role='user',
                    content=prompt,
                    metadata=user_metadata
                )
                self.session_service.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=response_text,
                    model=model_name
                )

                logger.info(f"Wikipedia pre-search + initial answer complete for session {session_id}")
                return

            # Otherwise: normal conversational flow (LLM may optionally request Wikipedia)
            final_context = list(context)

            initial_response = await self.llm_service.generate_chat_response(
                prompt=prompt,
                chat_history=final_context,
                system_prompt=system_prompt,
                model_config=model_config
            )

            # Extract potential Wikipedia search requests from the model output
            wiki_queries = self._extract_wikipedia_queries(initial_response)

            if wiki_queries:
                wiki_context, wikipedia_metadata = await self._search_wikipedia_multi_query(
                    queries=wiki_queries,
                    original_prompt=prompt,
                    chat_history=chat_history
                )

                if wiki_context and wikipedia_metadata and getattr(wikipedia_metadata, 'sources', None):
                    final_context.append({'role': 'system', 'content': f'Wikipedia results:\n{wiki_context}'})
                    yield self._format_sse('wikipedia', wikipedia_metadata.model_dump())

                    sources = wikipedia_metadata.sources
                    thr_cfg = self.config_service.config.get('wikipedia', {}).get('thresholds', {})
                    answer_thr = float(thr_cfg.get('answer', 0.8))
                    perfect_thr = float(thr_cfg.get('perfect', 0.98))
                    top_answer = [s for s in sources if (s.relevance_score or 0) >= answer_thr]
                    perfect = [s for s in sources if (s.relevance_score or 0) >= perfect_thr]

                    if perfect:
                        best = perfect[0]
                        full_article = await self.wikipedia_service.get_full_article_by_pageid(pageid=best.pageid, max_chars=50000)
                        if full_article:
                            # Attach image if possible
                            summary_extra = await self.wikipedia_service.get_summary_by_title(full_article.get('title', ''))
                            if summary_extra and summary_extra.get('thumbnail_url'):
                                full_article['image_url'] = summary_extra['thumbnail_url']

                            wiki_full_ctx = self._build_wikipedia_context([full_article])
                            final_context.append({'role': 'system', 'content': f'Wikipedia full article (perfect match):\n{wiki_full_ctx}'})

                            title_or = (best.title or full_article.get('title') or '').strip()
                            prompt_text = (
                                "Na Wikipedii jest artykuł, który opisuje to dokładnie. "
                                f"Napisz wprost: Na Wikipedii jest artykuł '{title_or}', który opisuje to dokładnie. "
                                "Przygotuj kompletną odpowiedź bazując na artykule (z kontekstu), dodaj 1–2 krótkie cytaty i link. "
                                "Wspomnij o obrazie, jeśli dostępny, i podaj URL obrazu. "
                                "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>). "
                                "Jeśli w kontekście jest linia 'Image: <URL>', możesz dodać <figure><img src=...><figcaption>."
                            )

                            response_text = await self.llm_service.generate_chat_response(
                                prompt=prompt_text,
                                chat_history=final_context,
                                system_prompt=system_prompt,
                                model_config=model_config
                            )
                        else:
                            perfect = []

                    if not perfect:
                        if top_answer:
                            cite_lines = "\n".join([
                                f"- {s.title} ({s.url}) [~{int(round((s.relevance_score or 0)*100))}%]"
                                for s in top_answer[:3]
                            ])
                            prompt_text = (
                                "Based on the Wikipedia results above, provide a complete answer to the user's question. "
                                "UWZGLĘDNIJ w treści odwołania do tych wysokotrafnych źródeł. "
                                "Sformatuj odpowiedź jako prosty HTML (użyj <p>, <ul>, <li>, <a>, <blockquote>).\n"
                                f"{cite_lines}\n"
                            )
                            response_text = await self.llm_service.generate_chat_response(
                                prompt=prompt_text,
                                chat_history=final_context,
                                system_prompt=system_prompt,
                                model_config=model_config
                            )
                        else:
                            response_text = await self.llm_service.generate_chat_response(
                                prompt=("Based on the Wikipedia results above, provide a complete answer to the user's question."),
                                chat_history=final_context,
                                system_prompt=system_prompt,
                                model_config=model_config
                            )
                else:
                    response_text = initial_response
            else:
                response_text = initial_response

            # Stream response in chunks
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield self._format_sse('chunk', chunk)
                await asyncio.sleep(0.02)

            # Send done signal
            yield self._format_sse('done', {})

            # Save to chat history
            user_metadata = metadata.model_dump()
            if wikipedia_metadata:
                user_metadata['wikipedia'] = wikipedia_metadata.model_dump()

            self.session_service.add_message(
                session_id=session_id,
                role='user',
                content=prompt,
                metadata=user_metadata
            )
            self.session_service.add_message(
                session_id=session_id,
                role='assistant',
                content=response_text,
                model=model_name
            )

            logger.info(f"Chat completed for session {session_id}")

        except Exception as e:
            logger.error(f"Error in chat handler: {e}", exc_info=True)
            error_msg = f"Error: {str(e)}"
            yield self._format_sse('error', error_msg)

    def _build_wikipedia_context(self, articles: list) -> str:
        """Build Wikipedia context from articles.

        Args:
            articles: List of Wikipedia articles

        Returns:
            Formatted Wikipedia context string
        """
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

    def _format_sse(self, event_type: str, data) -> str:
        """Format data as Server-Sent Event.

        Args:
            event_type: Event type (metadata, chunk, done, error)
            data: Event data

        Returns:
            Formatted SSE string
        """
        event_data = {
            'type': event_type,
            'data': data
        }
        return f"data: {json.dumps(event_data)}\n\n"

    def _extract_wikipedia_queries(self, response: str) -> List[str]:
        """Wyciągnij zapytania [WIKIPEDIA_SEARCH: query] z odpowiedzi LLM."""
        import re
        pattern = r'\[WIKIPEDIA_SEARCH:\s*([^\]]+)\]'
        matches = re.findall(pattern, response or "")
        return [m.strip() for m in matches if m and m.strip()]

    async def _search_wikipedia_multi_query(
        self,
        queries: List[str],
        original_prompt: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> Tuple[Optional[str], Optional[WikipediaMetadata]]:
        """Execute Wikipedia search with intent-aware post-processing."""

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

        intent_result: WikipediaIntentResult
        if self.wikipedia_intent_service:
            intent_result = await self.wikipedia_intent_service.analyze(
                prompt=original_prompt,
                candidates=[
                    {"pageid": r.pageid, "title": r.title, "snippet": r.snippet}
                    for r in ranked_results
                ],
                chat_history=chat_history
            )
        else:
            primary_candidate = ranked_results[0]
            intent_result = WikipediaIntentResult(
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

        def match_topic(topic: Optional[WikipediaIntentTopic]) -> Optional[RankedResult]:
            if not topic:
                return None
            if topic.pageid is not None:
                for candidate in ranked_results:
                    if candidate.pageid == topic.pageid:
                        return candidate
            title_lower = topic.title.strip().lower()
            if title_lower:
                for candidate in ranked_results:
                    if candidate.title.strip().lower() == title_lower:
                        return candidate
            return None

        primary_candidate = match_topic(intent_result.primary) if intent_result else None
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

        resolved_context_pairs: List[Tuple[WikipediaIntentTopic, RankedResult]] = []
        context_capacity = max_total - 1
        seen_context_pageids = {primary_candidate.pageid}

        if intent_result and intent_result.context:
            for topic in intent_result.context:
                if len(resolved_context_pairs) >= context_capacity:
                    break
                candidate = match_topic(topic)
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

        sources: List[WikipediaSource] = []
        articles: List[Dict] = []

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
                "url": (summary or {}).get("url") or self._build_wiki_url(primary_candidate.pageid),
                "pageid": primary_candidate.pageid,
                "image_url": (summary or {}).get("thumbnail_url"),
                "images": []
            }
        else:
            if not primary_article.get("url"):
                primary_article["url"] = self._build_wiki_url(primary_candidate.pageid)
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

        resolved_context_topics: List[WikipediaIntentTopic] = []
        for topic, candidate in resolved_context_pairs:
            if len(articles) >= max_total:
                break
            summary = await self.wikipedia_service.get_summary_by_title(candidate.title)
            extract = (summary or {}).get("extract", candidate.snippet)
            url = (summary or {}).get("url") or self._build_wiki_url(candidate.pageid)
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
            resolved_context_topics.append(topic)

        wiki_context = self._build_wikipedia_context(articles)

        metadata = WikipediaMetadata(
            query=", ".join(queries[:3]),
            sources=sources,
            total_results=len(combined_results),
            reranked=bool(rerank_cfg.get('enabled', True)),
            reranking_model=rerank_cfg.get('model') if rerank_cfg.get('enabled', True) else None,
            primary_topic=intent_result.primary.title if intent_result and intent_result.primary else primary_article.get("title"),
            primary_pageid=primary_article.get("pageid"),
            context_topics=resolved_context_topics,
            intent_notes=intent_result.notes if intent_result else None
        )

        return wiki_context, metadata

    def _build_wiki_url(self, pageid: Optional[int]) -> str:
        """Construct a canonical Wikipedia URL for a page ID."""
        if not pageid:
            return ""
        language = getattr(self.wikipedia_service, "language", "en")
        return f"https://{language}.wikipedia.org/?curid={pageid}"

    def _enable_wikipedia_tool(self, system_prompt: str) -> str:
        """Dodaj informację o dostępności Wikipedia jako tool (już w promptcie)."""
        return system_prompt

    async def handle_wikipedia_research(self, request: WikipediaResearchRequest):
        """Stream a deep-dive summary (referat) based on a full Wikipedia article."""
        session_id = request.session_id
        pageid = request.pageid
        title = request.title

        try:
            chat_history = self.session_service.get_session(session_id)

            # Determine topic from last metadata, fallback (used only to pick model/prompt)
            topic = 'GENERAL_KNOWLEDGE'
            if chat_history:
                for msg in reversed(chat_history):
                    md = msg.get('metadata') or {}
                    if md.get('topic'):
                        topic = md['topic']
                        break

            # Build a detached, clean system prompt: ignore prior conversation
            base_system_prompt = self.config_service.get_system_prompt(topic)
            base_system_prompt = self._enable_wikipedia_tool(base_system_prompt)
            system_prompt = (
                f"{base_system_prompt}\n\n" \
                "Dla tej operacji badawczej ZUPEŁNIE ignoruj poprzednią rozmowę. "
                "Opracuj referat wyłącznie na podstawie artykułu z Wikipedii, który dodam poniżej w kontekście systemowym. "
                "Nie dodawaj treści spoza artykułu."
            )
            model_name = self.config_service.get_preferred_model_for_topic(topic)
            if model_name and "mini" in model_name:
                model_name = self.config_service.get_default_model()
            model_config = self.config_service.get_model_config(model_name)

            # Fetch full article
            article = await self.wikipedia_service.get_full_article_by_pageid(pageid=pageid, max_chars=50000)
            if not article:
                yield self._format_sse('error', f'Nie udało się pobrać artykułu (pageid={pageid}).')
                yield self._format_sse('done', {})
                return

            # Attach image if summary provides a thumbnail
            try:
                summary_extra = await self.wikipedia_service.get_summary_by_title(article.get('title', ''))
                if summary_extra and summary_extra.get('thumbnail_url'):
                    article['image_url'] = summary_extra['thumbnail_url']
            except Exception:
                pass

            # Prepare Wikipedia context
            wiki_context = self._build_wikipedia_context([article])
            # Use a clean, detached context limited to the article only
            final_context = [{'role': 'system', 'content': f'Wikipedia results (detached):\n{wiki_context}'}]

            # Also fetch gallery of images for this article
            try:
                media = await self.wikipedia_service._fetch_media_by_title(article.get('title', ''))
                if media:
                    article['images'] = media[:20]
            except Exception:
                article['images'] = article.get('images', [])

            # Send wikipedia event so UI can render image thumbnails gallery
            try:
                wm = WikipediaMetadata(
                    query=title or article.get('title', ''),
                    sources=[WikipediaSource(
                        title=article.get('title', ''),
                        url=article.get('url', ''),
                        pageid=article.get('pageid', 0),
                        extract=article.get('extract', ''),
                        relevance_score=1.0,
                        image_url=article.get('image_url'),
                        images=article.get('images', [])
                    )],
                    total_results=1,
                    reranked=False
                )
                yield self._format_sse('wikipedia', wm.model_dump())
            except Exception:
                pass

            # Generate referat based on full article
            prompt = (
                "Na podstawie pełnego artykułu z Wikipedii w kontekście systemowym powyżej przygotuj zwięzły, dobrze ustrukturyzowany referat o tym HAŚLE. "
                "Nie odwołuj się do wcześniejszej rozmowy. Nie dodawaj nic spoza artykułu. "
                "Cytuj źródło w formie: Według Wikipedii (artykuł: {title_or}). "
                "Sformatuj odpowiedź jako prosty HTML (użyj <h2>, <p>, <ul>, <li>, <a>, <blockquote>). Jeśli dostępny obraz (linia 'Image: <URL>'), możesz dodać <figure><img src=...><figcaption>."
            )
            title_or = (title or article.get('title') or '').strip()
            prompt = prompt.replace('{title_or}', title_or)

            response_text = await self.llm_service.generate_chat_response(
                prompt=prompt,
                chat_history=final_context,
                system_prompt=system_prompt,
                model_config=model_config
            )

            # Stream response
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield self._format_sse('chunk', chunk)
                await asyncio.sleep(0.02)

            yield self._format_sse('done', {})

            # Save assistant message
            self.session_service.add_message(
                session_id=session_id,
                role='assistant',
                content=response_text,
                model=model_name
            )

        except Exception as e:
            logger.error(f"Error in wikipedia research handler: {e}", exc_info=True)
            yield self._format_sse('error', f'Błąd: {str(e)}')

    async def handle_reset(self, session_id: Optional[str] = None) -> Dict:
        """Handle session reset request.

        Args:
            session_id: Optional session ID to reset

        Returns:
            Response dict with new session_id
        """
        new_session_id = self.session_service.reset_session(session_id)
        logger.info(f"Session reset: old={session_id}, new={new_session_id}")

        return {
            "session_id": new_session_id,
            "message": "Session reset successfully"
        }

