"""Chat orchestration service for managing chat flow."""
import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional

from app.models import ChatRequest, WikipediaMetadata
from app.services.response_strategy_service import ResponseStrategy

logger = logging.getLogger(__name__)


class ChatOrchestrationService:
    """Service for orchestrating chat flow."""

    def __init__(
        self,
        session_service,
        classification_service,
        llm_service,
        config_service,
        wikipedia_search_service,
        response_strategy_service,
        context_builder_service,
        sse_formatter_service,
        query_refiner_service=None,
    ):
        """Initialize chat orchestration service.

        Args:
            session_service: Session management service
            classification_service: Prompt classification service
            llm_service: LLM API service
            config_service: Configuration service
            wikipedia_search_service: Wikipedia search service
            response_strategy_service: Response strategy service
            context_builder_service: Context builder service
            sse_formatter_service: SSE formatter service
            query_refiner_service: Optional query refiner service
        """
        self.session_service = session_service
        self.classification_service = classification_service
        self.llm_service = llm_service
        self.config_service = config_service
        self.wikipedia_search_service = wikipedia_search_service
        self.response_strategy_service = response_strategy_service
        self.context_builder_service = context_builder_service
        self.sse_formatter = sse_formatter_service
        self.query_refiner_service = query_refiner_service

    async def process_chat(
        self,
        prompt: str,
        session_id: str,
        chat_history: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """Process a chat request and yield SSE events.

        Args:
            prompt: User prompt
            session_id: Session ID
            chat_history: Chat history

        Yields:
            SSE formatted events
        """
        try:
            # Classify prompt
            metadata = await self.classification_service.classify_prompt(prompt, chat_history)

            yield self.sse_formatter.format_sse('metadata', metadata.model_dump())
            yield self.sse_formatter.status_event('analyzing_query')

            # Check if dangerous
            if metadata.is_dangerous > 0.8:
                error_msg = "Request rejected due to security concerns."
                yield self.sse_formatter.format_sse('error', error_msg)
                logger.warning(f"Rejected dangerous prompt: {metadata.summary}")
                return

            # Get model configuration
            system_prompt, model_name, model_config = self._get_model_config(metadata.topic)

            logger.info(f"Generating response: topic={metadata.topic}, model={model_name}")

            # Check if Wikipedia is needed upfront
            if getattr(metadata, 'needs_wikipedia', False):
                async for event in self._handle_wikipedia_upfront(
                    prompt,
                    chat_history,
                    session_id,
                    metadata,
                    system_prompt,
                    model_config,
                    model_name
                ):
                    yield event
                return

            # Normal conversational flow
            async for event in self._handle_conversational_flow(
                prompt,
                chat_history,
                session_id,
                metadata,
                system_prompt,
                model_config,
                model_name
            ):
                yield event

        except Exception as e:
            logger.error(f"Error in chat orchestration: {e}", exc_info=True)
            yield self.sse_formatter.format_sse('error', f"Error: {str(e)}")

    def _get_model_config(self, topic: str):
        """Get system prompt and model configuration for a topic.

        Args:
            topic: Topic string

        Returns:
            Tuple of (system_prompt, model_name, model_config)
        """
        system_prompt = self.config_service.get_system_prompt(topic)
        model_name = self.config_service.get_preferred_model_for_topic(topic)

        # Enforce: if a mini variant is selected for final summary, use default instead
        if model_name and "mini" in model_name:
            model_name = self.config_service.get_default_model()

        model_config = self.config_service.get_model_config(model_name)
        return system_prompt, model_name, model_config

    async def _handle_wikipedia_upfront(
        self,
        prompt: str,
        chat_history: List[Dict],
        session_id: str,
        metadata,
        system_prompt: str,
        model_config: Dict,
        model_name: str
    ) -> AsyncGenerator[str, None]:
        """Handle Wikipedia search upfront (classifier determined Wikipedia is needed).

        Args:
            prompt: User prompt
            chat_history: Chat history
            session_id: Session ID
            metadata: Classification metadata
            system_prompt: System prompt
            model_config: Model configuration
            model_name: Model name

        Yields:
            SSE events
        """
        system_prompt = self._enable_wikipedia_tool(system_prompt)

        # Refine queries if enabled
        queries = await self._refine_queries_if_enabled(prompt, chat_history)

        # Search Wikipedia
        yield self.sse_formatter.status_event('connecting_wikipedia')
        yield self.sse_formatter.status_event('searching_articles')

        wiki_context, wikipedia_metadata = await self.wikipedia_search_service.search_wikipedia_multi_query(
            queries=queries,
            original_prompt=prompt,
            chat_history=chat_history
        )

        if wikipedia_metadata and getattr(wikipedia_metadata, 'sources', None):
            yield self.sse_formatter.status_event('comparing_results')
            yield self.sse_formatter.format_sse('wikipedia', wikipedia_metadata.model_dump())

        # Determine response strategy
        strategy, top_answer, perfect = self.response_strategy_service.determine_strategy(wikipedia_metadata)

        # Build context
        context = self.context_builder_service.get_conversation_context(session_id, limit=6)
        final_context = list(context)
        if wiki_context:
            final_context.append({'role': 'system', 'content': f'Wikipedia results:\n{wiki_context}'})

        # Generate response based on strategy
        response_text = await self._generate_response_by_strategy(
            strategy=strategy,
            perfect=perfect,
            top_answer=top_answer,
            prompt=prompt,
            final_context=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

        # Stream response
        async for event in self._stream_response(response_text):
            yield event

        yield self.sse_formatter.format_sse('done', {})

        # Save to history
        self._save_to_history(
            session_id=session_id,
            prompt=prompt,
            response_text=response_text,
            metadata=metadata,
            wikipedia_metadata=wikipedia_metadata,
            model_name=model_name
        )

        logger.info(f"Wikipedia pre-search + initial answer complete for session {session_id}")

    async def _handle_conversational_flow(
        self,
        prompt: str,
        chat_history: List[Dict],
        session_id: str,
        metadata,
        system_prompt: str,
        model_config: Dict,
        model_name: str
    ) -> AsyncGenerator[str, None]:
        """Handle normal conversational flow (LLM may request Wikipedia).

        Args:
            prompt: User prompt
            chat_history: Chat history
            session_id: Session ID
            metadata: Classification metadata
            system_prompt: System prompt
            model_config: Model configuration
            model_name: Model name

        Yields:
            SSE events
        """
        context = self.context_builder_service.get_conversation_context(session_id, limit=6)
        final_context = list(context)

        yield self.sse_formatter.status_event('thinking')
        initial_response = await self.llm_service.generate_chat_response(
            prompt=prompt,
            chat_history=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

        # Check if LLM requested Wikipedia
        wiki_queries = self.wikipedia_search_service.extract_wikipedia_queries(initial_response)
        wikipedia_metadata = None

        if wiki_queries:
            yield self.sse_formatter.status_event('connecting_wikipedia')
            yield self.sse_formatter.status_event('gathering_data')

            wiki_context, wikipedia_metadata = await self.wikipedia_search_service.search_wikipedia_multi_query(
                queries=wiki_queries,
                original_prompt=prompt,
                chat_history=chat_history
            )

            if wiki_context and wikipedia_metadata and getattr(wikipedia_metadata, 'sources', None):
                yield self.sse_formatter.status_event('reranking_results')
                final_context.append({'role': 'system', 'content': f'Wikipedia results:\n{wiki_context}'})
                yield self.sse_formatter.format_sse('wikipedia', wikipedia_metadata.model_dump())

                # Determine strategy and generate response
                strategy, top_answer, perfect = self.response_strategy_service.determine_strategy(wikipedia_metadata)

                response_text = await self._generate_response_by_strategy(
                    strategy=strategy,
                    perfect=perfect,
                    top_answer=top_answer,
                    prompt=prompt,
                    final_context=final_context,
                    system_prompt=system_prompt,
                    model_config=model_config
                )
            else:
                response_text = initial_response
        else:
            response_text = initial_response

        # Stream response
        async for event in self._stream_response(response_text):
            yield event

        yield self.sse_formatter.format_sse('done', {})

        # Save to history
        self._save_to_history(
            session_id=session_id,
            prompt=prompt,
            response_text=response_text,
            metadata=metadata,
            wikipedia_metadata=wikipedia_metadata,
            model_name=model_name
        )

        logger.info(f"Chat completed for session {session_id}")

    async def _refine_queries_if_enabled(
        self,
        prompt: str,
        chat_history: List[Dict]
    ) -> List[str]:
        """Refine queries using query refiner service if enabled.

        Args:
            prompt: User prompt
            chat_history: Chat history

        Returns:
            List of queries (refined or original)
        """
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

        return queries

    async def _generate_response_by_strategy(
        self,
        strategy: str,
        perfect: List,
        top_answer: List,
        prompt: str,
        final_context: List[Dict],
        system_prompt: str,
        model_config: Dict
    ) -> str:
        """Generate response based on strategy.

        Args:
            strategy: Response strategy
            perfect: List of perfect match sources
            top_answer: List of high-relevance sources
            prompt: User prompt
            final_context: Conversation context
            system_prompt: System prompt
            model_config: Model configuration

        Returns:
            Response text
        """
        if strategy == ResponseStrategy.PERFECT_MATCH:
            return await self._generate_perfect_match_response(
                perfect[0],
                prompt,
                final_context,
                system_prompt,
                model_config
            )
        elif strategy == ResponseStrategy.HIGH_RELEVANCE:
            return await self._generate_high_relevance_response(
                top_answer,
                final_context,
                system_prompt,
                model_config
            )
        elif strategy == ResponseStrategy.NO_RESULTS:
            return await self._generate_no_results_response(
                final_context,
                system_prompt,
                model_config
            )
        else:  # LOW_RELEVANCE
            return await self._generate_low_relevance_response(
                final_context,
                system_prompt,
                model_config
            )

    async def _generate_perfect_match_response(
        self,
        best_source,
        prompt: str,
        final_context: List[Dict],
        system_prompt: str,
        model_config: Dict
    ) -> str:
        """Generate response for perfect match.

        Args:
            best_source: Best matching source
            prompt: User prompt
            final_context: Conversation context
            system_prompt: System prompt
            model_config: Model configuration

        Returns:
            Response text
        """
        # Fetch full article
        full_article = await self.wikipedia_search_service.wikipedia_service.get_full_article_by_pageid(
            pageid=best_source.pageid,
            max_chars=50000
        )

        if not full_article:
            return await self._generate_high_relevance_response(
                [best_source],
                final_context,
                system_prompt,
                model_config
            )

        # Try to attach image
        try:
            summary_extra = await self.wikipedia_search_service.wikipedia_service.get_summary_by_title(
                full_article.get('title', '')
            )
            if summary_extra and summary_extra.get('thumbnail_url'):
                full_article['image_url'] = summary_extra['thumbnail_url']
        except Exception:
            pass

        # Add full article to context
        wiki_full_ctx = self.wikipedia_search_service.build_wikipedia_context([full_article])
        final_context.append({
            'role': 'system',
            'content': f'Wikipedia full article (perfect match):\n{wiki_full_ctx}'
        })

        # Build prompt
        title = (best_source.title or full_article.get('title') or '').strip()
        prompt_text = self.response_strategy_service.build_perfect_match_prompt_with_user_query(
            prompt,
            title
        )

        return await self.llm_service.generate_chat_response(
            prompt=prompt_text,
            chat_history=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

    async def _generate_high_relevance_response(
        self,
        top_answer: List,
        final_context: List[Dict],
        system_prompt: str,
        model_config: Dict
    ) -> str:
        """Generate response for high relevance sources.

        Args:
            top_answer: List of high-relevance sources
            final_context: Conversation context
            system_prompt: System prompt
            model_config: Model configuration

        Returns:
            Response text
        """
        # Check if Wikipedia context is already in final_context
        has_wiki_context = any(
            msg.get('role') == 'system' and 'Wikipedia results:' in msg.get('content', '')
            for msg in final_context
        )

        if has_wiki_context:
            prompt_text = self.response_strategy_service.build_high_relevance_prompt_with_context(top_answer)
        else:
            prompt_text = self.response_strategy_service.build_high_relevance_prompt(top_answer)

        return await self.llm_service.generate_chat_response(
            prompt=prompt_text,
            chat_history=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

    async def _generate_no_results_response(
        self,
        final_context: List[Dict],
        system_prompt: str,
        model_config: Dict
    ) -> str:
        """Generate response when no results found.

        Args:
            final_context: Conversation context
            system_prompt: System prompt
            model_config: Model configuration

        Returns:
            Response text
        """
        prompt_text = self.response_strategy_service.build_no_results_prompt()
        return await self.llm_service.generate_chat_response(
            prompt=prompt_text,
            chat_history=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

    async def _generate_low_relevance_response(
        self,
        final_context: List[Dict],
        system_prompt: str,
        model_config: Dict
    ) -> str:
        """Generate response for low relevance sources.

        Args:
            final_context: Conversation context
            system_prompt: System prompt
            model_config: Model configuration

        Returns:
            Response text
        """
        prompt_text = self.response_strategy_service.build_low_relevance_prompt()
        return await self.llm_service.generate_chat_response(
            prompt=prompt_text,
            chat_history=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

    async def _stream_response(self, response_text: str) -> AsyncGenerator[str, None]:
        """Stream response text in chunks.

        Args:
            response_text: Response text to stream

        Yields:
            SSE events
        """
        yield self.sse_formatter.status_event('compiling_answer')
        chunk_size = 10
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            yield self.sse_formatter.format_sse('chunk', chunk)
            await asyncio.sleep(0.02)

    def _save_to_history(
        self,
        session_id: str,
        prompt: str,
        response_text: str,
        metadata,
        wikipedia_metadata: Optional[WikipediaMetadata],
        model_name: str
    ):
        """Save conversation to history.

        Args:
            session_id: Session ID
            prompt: User prompt
            response_text: Assistant response
            metadata: Classification metadata
            wikipedia_metadata: Optional Wikipedia metadata
            model_name: Model name used
        """
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

    def _enable_wikipedia_tool(self, system_prompt: str) -> str:
        """Enable Wikipedia tool in system prompt.

        Args:
            system_prompt: Current system prompt

        Returns:
            Modified system prompt
        """
        return system_prompt
