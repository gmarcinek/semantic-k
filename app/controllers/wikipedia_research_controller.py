"""Wikipedia research controller for handling deep-dive research operations."""
import asyncio
import logging
from typing import AsyncGenerator, Optional

from app.models import WikipediaResearchRequest, WikipediaMetadata, WikipediaSource

logger = logging.getLogger(__name__)


class WikipediaResearchController:
    """Controller for Wikipedia research operations."""

    def __init__(
        self,
        session_service,
        config_service,
        llm_service,
        wikipedia_service,
        sse_formatter_service,
        wikipedia_search_service,
        context_builder_service
    ):
        self.session_service = session_service
        self.config_service = config_service
        self.llm_service = llm_service
        self.wikipedia_service = wikipedia_service
        self.sse_formatter = sse_formatter_service
        self.wikipedia_search_service = wikipedia_search_service
        self.context_builder_service = context_builder_service

    async def handle_wikipedia_research(
        self,
        request: WikipediaResearchRequest
    ) -> AsyncGenerator[str, None]:
        session_id = request.session_id
        pageid = request.pageid
        title = request.title
        requested_language = self._normalize_language_code(request.language)

        try:
            chat_history = self.session_service.get_session(session_id)

            # Determine topic from last metadata
            topic = self._extract_topic_from_history(chat_history)

            # Build system prompt and model config
            base_system_prompt = self.config_service.get_system_prompt(topic)
            base_system_prompt = self._enable_wikipedia_tool(base_system_prompt)
            system_prompt = (
                f"{base_system_prompt}\n\n"
                "Dla tej operacji badawczej ZUPEŁNIE ignoruj poprzednią rozmowę. "
                "Opracuj referat wyłącznie na podstawie artykułu z Wikipedii, który dodam poniżej w kontekście systemowym. "
                "Nie dodawaj treści spoza artykułu."
            )

            model_name = self.config_service.get_preferred_model_for_topic(topic)
            if model_name and "mini" in model_name:
                model_name = self.config_service.get_default_model()
            model_config = self.config_service.get_model_config(model_name)

            language = requested_language or self._infer_language_from_session(session_id, pageid)
            article_service = self._get_wikipedia_service_for_language(language)
            article_language = getattr(article_service, "language", None) or language or getattr(self.wikipedia_service, "language", None)

            # Fetch full article
            article = await article_service.get_full_article_by_pageid(
                pageid=pageid,
                max_chars=50000
            )
            if not article:
                yield self.sse_formatter.format_sse('error', f'Nie udało się pobrać artykułu (pageid={pageid}).')
                yield self.sse_formatter.format_sse('done', {})
                return

            article['language'] = article_language
            article.setdefault('url', self.wikipedia_search_service.build_wiki_url(pageid, article_language))

            # Attach image if available
            article = await self._attach_image_to_article(article, article_service)

            # Prepare Wikipedia context
            wiki_context = self.wikipedia_search_service.build_wikipedia_context([article])
            final_context = self.context_builder_service.build_detached_context_with_article(wiki_context)

            # Fetch gallery of images
            article = await self._fetch_article_images(article, article_service)

            # Send wikipedia event for UI
            yield self._send_wikipedia_metadata_event(article, title)

            # Generate referat
            prompt = self._build_research_prompt(title or article.get('title', ''))

            response_text = await self.llm_service.generate_chat_response(
                prompt=prompt,
                chat_history=final_context,
                system_prompt=system_prompt,
                model_config=model_config
            )

            # Stream response
            yield self.sse_formatter.status_event('compiling_answer')
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield self.sse_formatter.format_sse('chunk', chunk)
                await asyncio.sleep(0.02)

            yield self.sse_formatter.format_sse('done', {})

            # Save assistant message
            self.session_service.add_message(
                session_id=session_id,
                role='assistant',
                content=response_text,
                model=model_name
            )

        except Exception as e:
            logger.error(f"Error in wikipedia research handler: {e}", exc_info=True)
            yield self.sse_formatter.format_sse('error', f'Błąd: {str(e)}')

    def _extract_topic_from_history(self, chat_history):
        topic = 'GENERAL_KNOWLEDGE'
        if chat_history:
            for msg in reversed(chat_history):
                md = msg.get('metadata') or {}
                if md.get('topic'):
                    topic = md['topic']
                    break
        return topic

    async def _attach_image_to_article(self, article, service):
        try:
            summary_extra = await service.get_summary_by_title(
                article.get('title', '')
            )
            if summary_extra and summary_extra.get('thumbnail_url'):
                article['image_url'] = summary_extra['thumbnail_url']
        except Exception:
            pass
        return article

    async def _fetch_article_images(self, article, service):
        try:
            media = await service._fetch_media_by_title(
                article.get('title', '')
            )
            if media:
                article['images'] = media[:20]
        except Exception:
            article['images'] = article.get('images', [])
        return article

    def _send_wikipedia_metadata_event(self, article, title):
        try:
            query_text = title or article.get('title', '')
            lang_code = (article.get('language', getattr(self.wikipedia_service, "language", None)) or "").lower()
            queries_map = {lang_code: [query_text]} if lang_code else {}
            wm = WikipediaMetadata(
                query=query_text,
                sources=[WikipediaSource(
                    title=article.get('title', ''),
                    url=article.get('url', ''),
                    pageid=article.get('pageid', 0),
                    extract=article.get('extract', ''),
                    relevance_score=1.0,
                    image_url=article.get('image_url'),
                    images=article.get('images', []),
                    language=article.get('language', getattr(self.wikipedia_service, "language", None))
                )],
                total_results=1,
                reranked=False,
                primary_language=article.get('language', getattr(self.wikipedia_service, "language", None)),
                languages_used=[
                    lang for lang in [article.get('language', getattr(self.wikipedia_service, "language", None))]
                    if lang
                ],
                queries_by_language=queries_map
            )
            return self.sse_formatter.format_sse('wikipedia', wm.model_dump())
        except Exception:
            return ""

    def _build_research_prompt(self, title: str) -> str:
        return (
            "Na podstawie pełnego artykułu z Wikipedii w kontekście systemowym powyżej przygotuj zwięzły, dobrze ustrukturyzowany referat o tym HAŚLE. "
            "Nie odwołuj się do wcześniejszej rozmowy. Nie dodawaj nic spoza artykułu. "
            f"Cytuj źródło w formie: Według Wikipedii (artykuł: {title}). "
            "Sformatuj odpowiedź jako prosty HTML (użyj <h2>, <p>, <ul>, <li>, <a>, <blockquote>). "
            "Jeśli dostępny obraz (linia 'Image: <URL>'), możesz dodać <figure><img src=...><figcaption>."
        )

    def _enable_wikipedia_tool(self, system_prompt: str) -> str:
        return system_prompt

    def _normalize_language_code(self, language: Optional[str]) -> Optional[str]:
        if language is None:
            return None
        code = str(language).strip().lower()
        return code or None

    def _infer_language_from_session(self, session_id: str, pageid: int) -> Optional[str]:
        try:
            articles = self.session_service.get_wikipedia_articles(session_id)
        except Exception:
            return None

        for article in articles or []:
            stored_pageid = article.get('pageid')
            try:
                if stored_pageid is not None and int(stored_pageid) == int(pageid):
                    return self._normalize_language_code(article.get('language'))
            except Exception:
                continue
        return None

    def _get_wikipedia_service_for_language(self, language: Optional[str]):
        normalized = self._normalize_language_code(language)
        if normalized:
            try:
                if hasattr(self.wikipedia_search_service, "get_service_for_language"):
                    return self.wikipedia_search_service.get_service_for_language(normalized)
            except Exception as err:
                logger.debug("Falling back to default Wikipedia service for language %s: %s", normalized, err)
        return self.wikipedia_service
