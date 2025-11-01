"""Chat controller for handling chat-related operations."""
import asyncio
import json
import logging
from typing import Dict, Optional
from uuid import uuid4

from app.models import ChatRequest, WikipediaSource, WikipediaMetadata
from app.utils.search_query_builder import SearchQueryBuilder

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
        query_refiner_service
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

            # Get full conversation context for LLM (use entire history)
            history_len = len(chat_history) if chat_history else 0
            context = self.session_service.get_conversation_context(session_id, limit=history_len)

            # Wikipedia search and reranking
            wikipedia_metadata = None
            enhanced_prompt = prompt

            if metadata.topic == "GENERAL_KNOWLEDGE":
                # Inspect chat history for previous Wikipedia metadata and topic
                last_wiki = None
                last_topic = None
                if chat_history:
                    for msg in reversed(chat_history):
                        md = msg.get('metadata') or {}
                        if not last_wiki and isinstance(md.get('wikipedia'), dict) and md['wikipedia'].get('sources'):
                            last_wiki = md['wikipedia']
                        if not last_topic and md.get('topic'):
                            last_topic = md['topic']
                        if last_wiki and last_topic:
                            break

                # Decide on continuation and topic change more robustly
                is_continuation = metadata.is_continuation >= 0.5
                classifier_topic_changed = metadata.topic_change > 0.5
                history_topic_changed = (last_topic is not None and last_topic != metadata.topic)
                topic_changed = classifier_topic_changed or history_topic_changed

                if last_wiki and is_continuation and not topic_changed:
                    # Reuse previous Wikipedia sources without re-searching
                    logger.info("Reusing previous Wikipedia sources for context (continuation detected)")
                    articles = last_wiki.get('sources', [])

                    # Build context and enhanced prompt
                    wiki_context = self._build_wikipedia_context(articles)
                    enhanced_prompt = f"""User Question: {prompt}

Wikipedia Information:
{wiki_context}

Please answer the user's question based ONLY on the Wikipedia information provided above. Include citations to the article titles."""

                    # Prepare and emit previous metadata for client visibility
                    wikipedia_metadata = WikipediaMetadata.model_validate(last_wiki)
                    yield self._format_sse('wikipedia', wikipedia_metadata.model_dump())
                else:
                    # LLM-powered refinement first
                    llm_queries, llm_lang = await self.query_refiner_service.refine(prompt)

                    # Heuristic candidates from the user's prompt
                    heuristic_candidates = SearchQueryBuilder.build_candidates(prompt)

                    # Merge, prioritizing LLM queries
                    seen = set()
                    candidates = []
                    for q in (llm_queries or []):
                        qn = (q or '').strip()
                        if qn and qn.lower() not in seen:
                            candidates.append(qn)
                            seen.add(qn.lower())
                    for q in heuristic_candidates:
                        qn = (q or '').strip()
                        if qn and qn.lower() not in seen:
                            candidates.append(qn)
                            seen.add(qn.lower())

                    # Only seed with previous queries/titles if topic didn't change
                    if last_wiki and not topic_changed:
                        prior_titles = [s.get('title') for s in last_wiki.get('sources', []) if s.get('title')]
                        prior_query = last_wiki.get('query')
                        seed = []
                        if prior_query:
                            seed.append(prior_query)
                        seed.extend(prior_titles[:3])
                        # Deduplicate preserving order, with seed first
                        seen = set()
                        merged = []
                        for q in seed + candidates:
                            if q and q not in seen:
                                merged.append(q)
                                seen.add(q)
                        candidates = merged

                    logger.info(f"Searching Wikipedia for candidates: {candidates}")

                    # Get Wikipedia configuration
                    wiki_config = self.config_service.config.get("wikipedia", {})
                    search_config = wiki_config.get("search", {})
                    reranking_config = wiki_config.get("reranking", {})

                    # Search Wikipedia with candidates in current language
                    search_results = []
                    used_query = None
                    for q in candidates:
                        results_try = await self.wikipedia_service.search(
                            query=q,
                            limit=search_config.get("max_results", 10)
                        )
                        if results_try:
                            search_results = results_try
                            used_query = q
                            break

                    # If no results and likely a different language, try alternate language
                    if not search_results:
                        # Prefer LLM-indicated language; else heuristic detection
                        likely_lang = llm_lang or SearchQueryBuilder.detect_language(prompt, default=wiki_config.get("language", "en"))
                        current_lang = wiki_config.get("language", "en")
                        if likely_lang and likely_lang != current_lang:
                            from app.services.wikipedia_service import WikipediaService
                            alt_service = WikipediaService(language=likely_lang)
                            for q in candidates:
                                results_try = await alt_service.search(
                                    query=q,
                                    limit=search_config.get("max_results", 10)
                                )
                                if results_try:
                                    search_results = results_try
                                    used_query = q
                                    # Replace service so subsequent calls use the right language
                                    self.wikipedia_service = alt_service
                                    break

                    if search_results:
                        # Rerank results if enabled
                        if reranking_config.get("enabled", True):
                            logger.info("Reranking Wikipedia results")
                            ranked_results = await self.reranker_service.rerank_results(
                                query=used_query or prompt,
                                search_results=search_results,
                                top_n=reranking_config.get("top_n", 5),
                                model=reranking_config.get("model", "gpt-4o-mini")
                            )
                        else:
                            # Use original ranking
                            from app.services.reranker_service import RankedResult
                            ranked_results = [
                                RankedResult(
                                    pageid=r.get("pageid", 0),
                                    title=r.get("title", ""),
                                    snippet=r.get("snippet", ""),
                                    relevance_score=1.0 - (i * 0.1),
                                    reasoning="Original ranking"
                                )
                                for i, r in enumerate(search_results[:reranking_config.get("top_n", 5)])
                            ]

                        # Get full article content ONLY for results with relevance >= 0.9
                        high_conf_results = [r for r in ranked_results if (r.relevance_score or 0) >= 0.9]
                        articles = []
                        if high_conf_results:
                            pageids = [r.pageid for r in high_conf_results]
                            articles = await self.wikipedia_service.get_multiple_articles(
                                pageids=pageids,
                                extract_length=search_config.get("extract_length", 500)
                            )

                        # Sort articles by reranked relevance (desc)
                        score_lookup = {r.pageid: r.relevance_score for r in ranked_results}
                        articles.sort(key=lambda a: score_lookup.get(a.get("pageid"), 0), reverse=True)

                        # Build Wikipedia context (may be empty if no >=0.9 results)
                        wiki_context = self._build_wikipedia_context(articles)

                        # Enhance prompt with Wikipedia content or note low relevance
                        if articles:
                            enhanced_prompt = f"""User Question: {prompt}

Wikipedia Information:
{wiki_context}

Please answer the user's question based ONLY on the Wikipedia information provided above. Include citations to the article titles."""
                        else:
                            enhanced_prompt = (
                                f"{prompt}\n\nNote: No high-relevance (>=0.9) Wikipedia articles were found among candidates."
                            )

                        # Build Wikipedia metadata
                        sources = []
                        for article in articles:
                            pid = article.get("pageid")
                            rel = score_lookup.get(pid)
                            sources.append(
                                WikipediaSource(
                                    title=article.get("title", ""),
                                    url=article.get("url", ""),
                                    pageid=pid or 0,
                                    extract=article.get("extract", ""),
                                    relevance_score=rel
                                )
                            )

                        wikipedia_metadata = WikipediaMetadata(
                            query=used_query or prompt,
                            sources=sources,
                            total_results=len(search_results),
                            reranked=reranking_config.get("enabled", True),
                            reranking_model=reranking_config.get("model", "gpt-4o-mini") if reranking_config.get("enabled", True) else None
                        )

                        # Send Wikipedia metadata to client
                        yield self._format_sse('wikipedia', wikipedia_metadata.model_dump())

                        logger.info(f"Wikipedia search complete: {len(articles)} articles retrieved")
                    else:
                        logger.info("No Wikipedia results found for any candidate")
                        enhanced_prompt = (
                            f"{prompt}\n\nNote: No relevant Wikipedia articles were found for related queries: "
                            f"{', '.join(candidates)}."
                        )

            # Generate response
            response_text = await self.llm_service.generate_chat_response(
                prompt=enhanced_prompt,
                chat_history=context,
                system_prompt=system_prompt,
                model_config=model_config
            )

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

            context_parts.append(
                f"Article {i}: {title}\n"
                f"URL: {url}\n"
                f"Content: {extract}\n"
            )

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
