"""Article fetcher service for retrieving and enriching Wikipedia articles."""
import logging
from typing import Dict, List, Optional, Tuple
from app.models import WikipediaSource, WikipediaIntentTopic
from app.services.reranker_service import RankedResult

logger = logging.getLogger(__name__)


class ArticleFetcherService:
    """Service for fetching and enriching Wikipedia articles with images and metadata."""

    def __init__(self, primary_language: str):
        """Initialize article fetcher.

        Args:
            primary_language: Primary Wikipedia language code
        """
        self.primary_language = primary_language

    async def fetch_articles(
        self,
        primary_candidate: RankedResult,
        resolved_context_pairs: List[Tuple[WikipediaIntentTopic, RankedResult]],
        extract_length: int,
        max_total: int,
        get_service_for_language_func,
        build_wiki_url_func
    ) -> Tuple[List[WikipediaSource], List[Dict]]:
        """Fetch primary and context articles.

        Args:
            primary_candidate: Primary article to fetch
            resolved_context_pairs: List of (topic, candidate) pairs for context
            extract_length: Maximum extract length for full articles
            max_total: Maximum total articles
            get_service_for_language_func: Function to get WikipediaService for language
            build_wiki_url_func: Function to build Wikipedia URL

        Returns:
            Tuple of (sources list, articles list)
        """
        sources: List[WikipediaSource] = []
        articles: List[Dict] = []

        # Fetch primary article
        primary_article = await self._fetch_primary_article(
            primary_candidate,
            extract_length,
            get_service_for_language_func,
            build_wiki_url_func
        )
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

        # Fetch context articles
        for topic, candidate in resolved_context_pairs:
            if len(articles) >= max_total:
                break

            service = get_service_for_language_func(candidate.language)
            summary = await service.get_summary_by_title(candidate.title)
            extract = (summary or {}).get("extract", candidate.snippet)
            url = (summary or {}).get("url") or build_wiki_url_func(candidate.pageid, candidate.language)

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
        extract_length: int,
        get_service_for_language_func,
        build_wiki_url_func
    ) -> Dict:
        """Fetch primary article with full content and enrichment.

        Args:
            primary_candidate: Primary article candidate
            extract_length: Maximum extract length
            get_service_for_language_func: Function to get WikipediaService for language
            build_wiki_url_func: Function to build Wikipedia URL

        Returns:
            Enriched article dictionary
        """
        primary_article = None
        service = get_service_for_language_func(primary_candidate.language)
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
                "url": (summary or {}).get("url") or build_wiki_url_func(primary_candidate.pageid, language),
                "pageid": primary_candidate.pageid,
                "image_url": (summary or {}).get("thumbnail_url"),
                "images": [],
                "language": language
            }
        else:
            # Enrich with URL if missing
            if not primary_article.get("url"):
                primary_article["url"] = build_wiki_url_func(primary_candidate.pageid, language)

            # Attach image to article
            await self._attach_image_to_article(primary_article, service)

            primary_article.setdefault("language", language)

        return primary_article

    async def _attach_image_to_article(self, article: Dict, service) -> None:
        """Attach thumbnail and media images to article.

        Args:
            article: Article dictionary to enrich
            service: WikipediaService instance
        """
        try:
            summary_extra = await service.get_summary_by_title(article.get("title", ""))
            if summary_extra:
                if summary_extra.get("thumbnail_url"):
                    article["image_url"] = summary_extra["thumbnail_url"]
                if summary_extra.get("url"):
                    article["url"] = summary_extra["url"]
                if not article.get("extract"):
                    article["extract"] = summary_extra.get("extract", "")
        except Exception:
            pass

        if "images" not in article:
            article["images"] = []
        if not article["images"]:
            try:
                media = await service._fetch_media_by_title(article.get("title", ""))
                if media:
                    article["images"] = media[:12]
            except Exception:
                article["images"] = []

    def build_wikipedia_context(self, articles: List[Dict]) -> str:
        """Build context string from articles for LLM.

        Args:
            articles: List of article dictionaries

        Returns:
            Formatted context string
        """
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

    def build_wiki_url(
        self,
        pageid: Optional[int],
        language: Optional[str] = None,
        default_service_language: Optional[str] = None
    ) -> str:
        """Build Wikipedia URL from page ID and language.

        Args:
            pageid: Wikipedia page ID
            language: Language code
            default_service_language: Default service language

        Returns:
            Wikipedia URL
        """
        if not pageid:
            return ""
        lang = (language or self.primary_language or default_service_language or "pl").strip() or "pl"
        return f"https://{lang}.wikipedia.org/?curid={pageid}"
