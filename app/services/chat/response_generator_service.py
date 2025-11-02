"""Response generator service for creating chat responses based on strategies."""
import asyncio
import logging
from typing import AsyncGenerator, Dict, List
from app.services.response_strategy_service import ResponseStrategy

logger = logging.getLogger(__name__)


class ResponseGeneratorService:
    """Service for generating responses according to different strategies."""

    def __init__(
        self,
        llm_service,
        response_strategy_service,
        wikipedia_search_service,
        sse_formatter_service
    ):
        """Initialize response generator service.

        Args:
            llm_service: LLM API service
            response_strategy_service: Response strategy service
            wikipedia_search_service: Wikipedia search service
            sse_formatter_service: SSE formatter service
        """
        self.llm_service = llm_service
        self.response_strategy_service = response_strategy_service
        self.wikipedia_search_service = wikipedia_search_service
        self.sse_formatter = sse_formatter_service

    async def generate_response_by_strategy(
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

    async def stream_response(self, response_text: str) -> AsyncGenerator[str, None]:
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
