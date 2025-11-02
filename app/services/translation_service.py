"""Translation service for converting Wikipedia snippets to Polish."""
import logging
from typing import Dict, List, Optional, Sequence, Tuple

from app.services.llm_service import LLMService
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)


class TranslationService:
    """Service responsible for translating short texts to Polish."""

    def __init__(
        self,
        llm_service: LLMService,
        config_service: ConfigService,
        target_language: str = "pl"
    ):
        self.llm_service = llm_service
        self.config_service = config_service
        self.target_language = target_language.lower()

        translation_cfg = config_service.config.get("translation", {})
        self.model_name = translation_cfg.get("model", "gpt-4.1-mini")
        self.max_chars = int(translation_cfg.get("max_chars", 1600))
        self.temperature = float(translation_cfg.get("temperature", 0.1))

        try:
            self.model_config = self.config_service.get_model_config(self.model_name)
        except KeyError:
            logger.warning(
                "Translation model '%s' not found in config; falling back to default.",
                self.model_name
            )
            self.model_name = self.config_service.get_default_model()
            self.model_config = self.config_service.get_model_config(self.model_name)

    async def translate_articles_and_sources(
        self,
        articles: Sequence[Dict],
        sources: Sequence,
        default_language: Optional[str] = None
    ) -> Tuple[List[Dict], List]:
        """Translate article dictionaries and WikipediaSource objects to Polish.

        Args:
            articles: List of article dictionaries (mutated copy returned)
            sources: Iterable of WikipediaSource instances
            default_language: Fallback language code

        Returns:
            Tuple of (translated_articles, translated_sources)
        """
        translated_articles: List[Dict] = []
        translated_sources: List = []
        translation_cache: Dict[Tuple[str, str], Dict[str, str]] = {}

        for article in articles:
            lang_code = self._normalize_language(article.get("language") or default_language)
            translated_article = dict(article)

            translation_key = self._build_translation_key(lang_code, article)
            if lang_code != self.target_language and translation_key not in translation_cache:
                translation_cache[translation_key] = await self._translate_entry(
                    title=article.get("title", ""),
                    extract=article.get("extract", ""),
                    source_language=lang_code
                )

            translation = translation_cache.get(translation_key)
            display_title = translation.get("title") if translation else article.get("title", "")
            display_extract = translation.get("extract") if translation else article.get("extract", "")

            translated_article["title"] = self._format_with_language_code(display_title, lang_code)
            translated_article["extract"] = display_extract
            translated_article["language"] = lang_code
            translated_articles.append(translated_article)

        for source in sources:
            lang_code = self._normalize_language(getattr(source, "language", None) or default_language)
            translation_key = self._build_translation_key(lang_code, source)

            translation = translation_cache.get(translation_key)
            translated_title = translation.get("title") if translation else source.title
            translated_extract = translation.get("extract") if translation else source.extract

            translated_sources.append(
                source.model_copy(
                    update={
                        "title": self._format_with_language_code(translated_title, lang_code),
                        "extract": translated_extract,
                        "language": lang_code
                    }
                )
            )

        return translated_articles, translated_sources

    async def _translate_entry(
        self,
        title: str,
        extract: str,
        source_language: Optional[str]
    ) -> Dict[str, str]:
        """Translate a title and extract to Polish via LLM."""
        title = (title or "").strip()
        extract = (extract or "").strip()

        if not title and not extract:
            return {"title": title, "extract": extract}

        lang_label = source_language.upper() if source_language else "NIEZNANY"
        trimmed_extract = extract[: self.max_chars]

        system_prompt = (
            "Jesteś tłumaczem, który tłumaczy teksty Wikipedii na język polski. "
            "Zachowujesz precyzyjne znaczenie, unikając dodatkowych komentarzy. "
            "Zwracasz wyłącznie poprawne językowo tłumaczenie."
        )
        user_prompt = (
            f"Przetłumacz poniższe treści z języka {lang_label} na język polski. "
            "Zwróć wynik w formacie JSON z polami 'title' i 'extract'.\n\n"
            f"Tytuł: {title or '[BRAK]'}\n"
            f"Fragment: {trimmed_extract or '[BRAK]'}"
        )

        try:
            response = await self.llm_service.generate_structured_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model_config=self.model_config,
                temperature=self.temperature
            )
        except Exception as exc:
            logger.warning("Translation failed (%s): %s", lang_label, exc)
            return {"title": title, "extract": trimmed_extract or extract}

        translated_title = (response.get("title") or title).strip()
        translated_extract = (response.get("extract") or trimmed_extract or extract).strip()

        return {
            "title": translated_title,
            "extract": translated_extract
        }

    @staticmethod
    def _build_translation_key(language: Optional[str], entry) -> Tuple[str, str]:
        identifier = ""
        if isinstance(entry, dict):
            identifier = str(entry.get("pageid") or entry.get("title") or "").strip().lower()
        else:
            identifier = str(getattr(entry, "pageid", None) or getattr(entry, "title", "")).strip().lower()
        return (language or "unknown", identifier)

    @staticmethod
    def _normalize_language(language: Optional[str]) -> str:
        if not language:
            return "unknown"
        return str(language).strip().lower() or "unknown"

    @staticmethod
    def _format_with_language_code(text: str, language: Optional[str]) -> str:
        code = (language or "unknown").upper()
        content = (text or "").strip()
        prefix = f"({code})"
        if content.upper().startswith(prefix):
            return content
        if content:
            return f"{prefix} {content}"
        return prefix
