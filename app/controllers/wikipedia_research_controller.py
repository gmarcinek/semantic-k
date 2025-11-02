"""Wikipedia research controller for handling deep-dive research operations."""
import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Optional

from app.models import WikipediaResearchRequest, WikipediaMetadata, WikipediaSource
from app.services.translation_service import TranslationService

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
        context_builder_service,
        translation_service: TranslationService
    ):
        self.session_service = session_service
        self.config_service = config_service
        self.llm_service = llm_service
        self.wikipedia_service = wikipedia_service
        self.sse_formatter = sse_formatter_service
        self.wikipedia_search_service = wikipedia_search_service
        self.context_builder_service = context_builder_service
        self.translation_service = translation_service

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

            # Enrich base article
            article = await self._attach_image_to_article(article, article_service)
            article = await self._fetch_article_images(article, article_service)

            languages_to_fetch = self._resolve_research_languages(
                requested_language=requested_language,
                base_language=article_language
            )
            langlinks = await self._get_language_links_safe(article_service, article.get('pageid'))

            language_articles, language_sources = await self._gather_language_variants(
                base_article=article,
                base_service=article_service,
                languages=languages_to_fetch,
                langlinks=langlinks
            )

            related_sources = await self._fetch_related_sources(
                base_service=article_service,
                article_title=article.get('title', ''),
                existing_pageids={src.pageid for src in language_sources if src.pageid}
            )

            if self.translation_service:
                _, translated_related = await self.translation_service.translate_articles_and_sources(
                    [],
                    related_sources,
                    default_language=article_language
                )
                related_sources = translated_related
            else:
                _, related_sources = self._apply_language_prefix([], related_sources)

            wiki_context = self.wikipedia_search_service.build_wikipedia_context(language_articles)
            final_context = self.context_builder_service.build_detached_context_with_article(wiki_context)

            # Send wikipedia event for UI
            yield self._send_wikipedia_metadata_event(
                primary_article=language_articles[0] if language_articles else article,
                language_sources=language_sources,
                related_sources=related_sources
            )

            for source in [*language_sources, *related_sources]:
                self.session_service.add_wikipedia_article(session_id, source.model_dump())

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

    def _send_wikipedia_metadata_event(
        self,
        primary_article: Dict,
        language_sources: List[WikipediaSource],
        related_sources: List[WikipediaSource]
    ):
        try:
            all_sources = list(language_sources) + list(related_sources)
            query_text = primary_article.get('title', '')
            queries_map: Dict[str, List[str]] = {}

            for source in language_sources:
                lang = (source.language or '').lower()
                if not lang:
                    continue
                queries_map.setdefault(lang, [])
                if source.title not in queries_map[lang]:
                    queries_map[lang].append(source.title)

            metadata = WikipediaMetadata(
                query=query_text,
                sources=all_sources,
                total_results=len(all_sources),
                reranked=False,
                primary_topic=primary_article.get('title'),
                primary_pageid=primary_article.get('pageid'),
                primary_language=(primary_article.get('language') or '').lower() or None,
                languages_used=sorted({
                    (src.language or '').lower()
                    for src in all_sources
                    if src.language
                }),
                queries_by_language=queries_map,
                intent_notes="Wikipedia research: aggregated multilingual sources and related pages."
            )
            return self.sse_formatter.format_sse('wikipedia', metadata.model_dump())
        except Exception as err:
            logger.error("Failed to send Wikipedia metadata event: %s", err, exc_info=True)
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

    def _resolve_research_languages(
        self,
        requested_language: Optional[str],
        base_language: Optional[str]
    ) -> List[str]:
        languages: List[str] = []
        seen: set = set()

        def add_lang(lang: Optional[str]):
            code = self._normalize_language_code(lang)
            if code and code not in seen:
                seen.add(code)
                languages.append(code)

        add_lang(base_language)
        add_lang(requested_language)

        if hasattr(self.wikipedia_search_service, "primary_language"):
            add_lang(self.wikipedia_search_service.primary_language)
        fallback = getattr(self.wikipedia_search_service, "fallback_languages", []) or []
        for lang in fallback:
            add_lang(lang)

        if not languages:
            add_lang(base_language or requested_language or getattr(self.wikipedia_service, "language", None))

        return languages

    async def _get_language_links_safe(self, service, pageid: Optional[int]) -> Dict[str, str]:
        if not pageid:
            return {}
        try:
            return await service.get_language_links(pageid)
        except Exception as err:
            logger.debug("Failed to fetch language links for page %s: %s", pageid, err)
            return {}

    async def _gather_language_variants(
        self,
        base_article: Dict,
        base_service,
        languages: List[str],
        langlinks: Dict[str, str]
    ) -> tuple[List[Dict], List[WikipediaSource]]:
        articles: List[Dict] = []
        sources: List[WikipediaSource] = []
        seen_languages: set = set()

        async def enrich_article(article: Dict, service, language: Optional[str], score: float):
            lang_code = self._normalize_language_code(language) or getattr(service, "language", None)
            if not lang_code or lang_code in seen_languages:
                return

            seen_languages.add(lang_code)
            article = dict(article)
            article['language'] = lang_code
            article.setdefault('url', self.wikipedia_search_service.build_wiki_url(article.get('pageid'), lang_code))

            article = await self._attach_image_to_article(article, service)
            article = await self._fetch_article_images(article, service)

            articles.append(article)
            sources.append(self._build_source_from_article(article, score))

        base_language = self._normalize_language_code(base_article.get('language'))
        await enrich_article(base_article, base_service, base_language, 1.0)

        for language in languages:
            lang_code = self._normalize_language_code(language)
            if not lang_code or lang_code == base_language:
                continue

            service = self._get_wikipedia_service_for_language(lang_code)
            title_hint = langlinks.get(lang_code) if langlinks else None
            article_variant = await self._fetch_article_for_language(
                service=service,
                language=lang_code,
                title_hint=title_hint,
                fallback_title=base_article.get('title'),
                max_chars=50000
            )
            if article_variant:
                await enrich_article(article_variant, service, lang_code, 0.9)

        if self.translation_service:
            return await self.translation_service.translate_articles_and_sources(
                articles,
                sources,
                default_language=getattr(self.wikipedia_service, "language", None)
            )

        return self._apply_language_prefix(articles, sources)

    async def _fetch_article_for_language(
        self,
        service,
        language: str,
        title_hint: Optional[str],
        fallback_title: Optional[str],
        max_chars: int
    ) -> Optional[Dict]:
        titles_to_try = [
            title_hint,
            fallback_title
        ]

        summary = None
        for title in titles_to_try:
            if not summary and title:
                try:
                    summary = await service.get_summary_by_title(title)
                except Exception:
                    summary = None

            if summary:
                break

        pageid = summary.get('pageid') if summary else None
        article = None

        if pageid:
            try:
                article = await service.get_full_article_by_pageid(pageid=pageid, max_chars=max_chars)
            except Exception:
                article = None

        if not article:
            for title in titles_to_try:
                if not title:
                    continue
                try:
                    article = await service.get_article_content(title=title, extract_length=min(max_chars, 10000))
                    if article:
                        break
                except Exception:
                    continue

        if not article and summary:
            article = {
                "title": summary.get("title") or title_hint or fallback_title,
                "extract": summary.get("extract", ""),
                "url": summary.get("url", ""),
                "pageid": summary.get("pageid")
            }

        if not article:
            return None

        article.setdefault('title', title_hint or fallback_title or '')
        article.setdefault('extract', summary.get('extract') if summary else '')
        article.setdefault('url', summary.get('url') if summary else self.wikipedia_search_service.build_wiki_url(article.get('pageid'), language))
        article.setdefault('pageid', summary.get('pageid') if summary else article.get('pageid'))

        return article

    def _build_source_from_article(self, article: Dict, score: float) -> WikipediaSource:
        return WikipediaSource(
            title=article.get('title', ''),
            url=article.get('url', ''),
            pageid=article.get('pageid') or 0,
            extract=(article.get('extract') or '')[:6000],
            relevance_score=score,
            image_url=article.get('image_url'),
            images=article.get('images', []),
            language=article.get('language')
        )

    def _apply_language_prefix(
        self,
        articles: List[Dict],
        sources: List[WikipediaSource]
    ) -> tuple[List[Dict], List[WikipediaSource]]:
        formatted_articles: List[Dict] = []
        for article in articles:
            lang = self._normalize_language_code(article.get("language") or getattr(self.wikipedia_service, "language", None))
            formatted_articles.append({
                **article,
                "title": self._format_with_language_code(article.get("title", ""), lang),
                "language": lang
            })

        formatted_sources: List[WikipediaSource] = []
        for source in sources:
            lang = self._normalize_language_code(getattr(source, "language", None) or getattr(self.wikipedia_service, "language", None))
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
        code = (language or getattr(self.wikipedia_service, "language", None) or "unknown").upper()
        prefix = f"({code})"
        content = (text or "").strip()
        if content.upper().startswith(prefix):
            return content
        if content:
            return f"{prefix} {content}"
        return prefix

    async def _fetch_related_sources(
        self,
        base_service,
        article_title: str,
        existing_pageids: set
    ) -> List[WikipediaSource]:
        if not article_title:
            return []

        try:
            related = await base_service.get_related_pages(article_title)
        except Exception as err:
            logger.debug("Failed to fetch related pages for '%s': %s", article_title, err)
            return []

        sources: List[WikipediaSource] = []
        language = getattr(base_service, "language", None)
        for rel in related:
            pageid = rel.get("pageid")
            if pageid and pageid in existing_pageids:
                continue
            source = WikipediaSource(
                title=rel.get("title", ""),
                url=rel.get("url", ""),
                pageid=pageid or 0,
                extract=(rel.get("extract") or "")[:600],
                relevance_score=0.4,
                image_url=rel.get("thumbnail"),
                images=[],
                language=language
            )
            sources.append(source)
        return sources
