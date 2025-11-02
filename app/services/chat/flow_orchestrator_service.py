"""Chat flow orchestrator service for managing conversation flow."""
import logging
from typing import AsyncGenerator, Dict, List, Optional
from app.models import WikipediaMetadata

logger = logging.getLogger(__name__)


class ChatFlowOrchestratorService:
    """Service for orchestrating chat flow and conversation management."""

    def __init__(
        self,
        session_service,
        classification_service,
        llm_service,
        config_service,
        wikipedia_search_service,
        response_generator_service,
        context_builder_service,
        sse_formatter_service,
        query_refiner_service=None,
    ):
        """Initialize chat flow orchestrator service.

        Args:
            session_service: Session management service
            classification_service: Prompt classification service
            llm_service: LLM API service
            config_service: Configuration service
            wikipedia_search_service: Wikipedia search service
            response_generator_service: Response generator service
            context_builder_service: Context builder service
            sse_formatter_service: SSE formatter service
            query_refiner_service: Optional query refiner service
        """
        self.session_service = session_service
        self.classification_service = classification_service
        self.llm_service = llm_service
        self.config_service = config_service
        self.wikipedia_search_service = wikipedia_search_service
        self.response_generator_service = response_generator_service
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
        queries_by_language = await self._refine_queries_if_enabled(
            prompt,
            chat_history,
            base_queries=None
        )

        # Search Wikipedia
        yield self.sse_formatter.status_event('connecting_wikipedia')
        yield self.sse_formatter.status_event('searching_articles')

        wiki_context, wikipedia_metadata = await self.wikipedia_search_service.search_wikipedia_multi_query(
            queries=queries_by_language,
            original_prompt=prompt,
            chat_history=chat_history
        )

        if wikipedia_metadata and getattr(wikipedia_metadata, 'sources', None):
            yield self.sse_formatter.status_event('comparing_results')
            yield self.sse_formatter.format_sse('wikipedia', wikipedia_metadata.model_dump())

        # Determine response strategy
        from app.services.response_strategy_service import ResponseStrategyService
        response_strategy_service = ResponseStrategyService()
        strategy, top_answer, perfect = response_strategy_service.determine_strategy(wikipedia_metadata)

        # Build context
        context = self.context_builder_service.get_conversation_context(session_id, limit=6)
        final_context = list(context)
        if wiki_context:
            final_context.append({'role': 'system', 'content': f'Wikipedia results:\n{wiki_context}'})

        # Generate response based on strategy
        response_text = await self.response_generator_service.generate_response_by_strategy(
            strategy=strategy,
            perfect=perfect,
            top_answer=top_answer,
            prompt=prompt,
            final_context=final_context,
            system_prompt=system_prompt,
            model_config=model_config
        )

        # Stream response
        async for event in self.response_generator_service.stream_response(response_text):
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

            queries_by_language = await self._refine_queries_if_enabled(
                prompt,
                chat_history,
                base_queries=wiki_queries
            )

            wiki_context, wikipedia_metadata = await self.wikipedia_search_service.search_wikipedia_multi_query(
                queries=queries_by_language,
                original_prompt=prompt,
                chat_history=chat_history
            )

            if wiki_context and wikipedia_metadata and getattr(wikipedia_metadata, 'sources', None):
                yield self.sse_formatter.status_event('reranking_results')
                final_context.append({'role': 'system', 'content': f'Wikipedia results:\n{wiki_context}'})
                yield self.sse_formatter.format_sse('wikipedia', wikipedia_metadata.model_dump())

                # Determine strategy and generate response
                from app.services.response_strategy_service import ResponseStrategyService
                response_strategy_service = ResponseStrategyService()
                strategy, top_answer, perfect = response_strategy_service.determine_strategy(wikipedia_metadata)

                response_text = await self.response_generator_service.generate_response_by_strategy(
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
        async for event in self.response_generator_service.stream_response(response_text):
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
        chat_history: List[Dict],
        base_queries: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """Refine queries using query refiner service if enabled.

        Args:
            prompt: User prompt
            chat_history: Chat history
            base_queries: Optional queries already supplied by the model

        Returns:
            Mapping of language -> queries (refined or original)
        """
        wiki_cfg = self.config_service.config.get('wikipedia', {})
        qr_cfg = wiki_cfg.get('query_refiner', {})

        primary_language = str(wiki_cfg.get('language', 'pl') or 'pl').strip().lower() or 'pl'
        fallback_cfg = wiki_cfg.get('fallback_languages', [])
        if isinstance(fallback_cfg, str):
            fallback_list = [fallback_cfg]
        else:
            fallback_list = list(fallback_cfg or [])
        languages: List[str] = []
        seen_langs: set = set()
        for lang in [primary_language, *fallback_list]:
            code = str(lang or '').strip().lower()
            if not code or code in seen_langs:
                continue
            seen_langs.add(code)
            languages.append(code)
        if not languages:
            languages = [primary_language]

        default_queries = base_queries if base_queries else [prompt]
        default_cleaned = [str(q).strip() for q in default_queries if str(q).strip()]
        if not default_cleaned:
            default_cleaned = [prompt]

        queries_by_language: Dict[str, List[str]] = {
            lang: list(default_cleaned) for lang in languages
        }

        if qr_cfg.get('enabled', False) and self.query_refiner_service:
            refined = await self.query_refiner_service.refine_queries_multi_language(
                prompt=prompt,
                chat_history=chat_history,
                languages=languages,
                max_queries=int(qr_cfg.get('max_queries', 3)),
                model_name=qr_cfg.get('model', 'gpt-4.1-mini'),
                base_queries=default_cleaned
            )
            if refined:
                queries_by_language = refined

        return queries_by_language

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

            # Add Wikipedia articles to session
            if hasattr(wikipedia_metadata, 'sources') and wikipedia_metadata.sources:
                for source in wikipedia_metadata.sources:
                    article_data = source.model_dump()
                    self.session_service.add_wikipedia_article(session_id, article_data)

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
