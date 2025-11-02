"""LLM-based query refiner for Wikipedia searches.

Generates high-quality search queries for multiple Wikipedia languages based on
the user's prompt and recent conversation context. Output is LLM-only and must
be valid JSON.
"""

import logging
from typing import Dict, List, Optional, Set

from app.services.llm_service import LLMService
from app.utils.colored_logger import get_plugin_logger

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'wikipedia')


class QueryRefinerService:
    """Service that asks the LLM to produce refined Wikipedia queries."""

    def __init__(self, llm_service: LLMService, config_service):
        self.llm_service = llm_service
        self.config_service = config_service

    def _build_system_prompt(self, language: str, max_queries: int) -> str:
        return (
            "You are an expert at crafting concise, effective search queries for Wikipedia. "
            "Given a user prompt and brief conversation context, propose up to "
            f"{max_queries} distinct, high-quality queries in {language}. "
            "Focus on disambiguation (place/person/event), synonyms, and typical article titles. "
            "Return ONLY JSON with the key 'queries': a list of strings."
        )

    def _build_user_prompt(self, prompt: str, chat_history: Optional[List[Dict]]) -> str:
        content = [f"User prompt:\n\"{prompt}\""]
        if chat_history:
            recent = chat_history[-3:]
            hist = "\n".join(
                f"{m.get('role')}: {str(m.get('content', ''))[:120]}" for m in recent
            )
            content.append("\nRecent conversation context:\n" + hist)
        content.append(
            "\nRespond ONLY with JSON of the form: {\n  \"queries\": [\"...\"]\n}"
        )
        return "\n".join(content)

    def _build_multi_language_system_prompt(self, languages: List[str], max_queries: int) -> str:
        lang_list = ", ".join(languages)
        return (
            "You are an expert at crafting concise, effective Wikipedia search queries across multiple languages. "
            f"For each language code in the set [{lang_list}], propose up to {max_queries} distinct, high-quality queries "
            "phrased naturally for that language, focusing on likely Wikipedia article titles and disambiguation. "
            "Return ONLY JSON with the key 'queries_by_language', mapping each language code to a list of strings."
        )

    def _build_multi_language_user_prompt(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]],
        languages: List[str],
        base_queries: Optional[List[str]] = None
    ) -> str:
        content = [f"User prompt:\n\"{prompt}\""]
        if chat_history:
            recent = chat_history[-3:]
            hist = "\n".join(
                f"{m.get('role')}: {str(m.get('content', ''))[:120]}" for m in recent
            )
            content.append("\nRecent conversation context:\n" + hist)
        content.append(f"\nTarget languages (use these codes exactly): {', '.join(languages)}")
        if base_queries:
            base = "\n".join(f"- {str(q)[:120]}" for q in base_queries[:6])
            content.append(
                "\nExisting queries requested by the assistant (use them as hints, adapt per language as needed):\n"
                f"{base}"
            )
        content.append(
            "\nRespond ONLY with JSON of the form:\n"
            "{\n"
            '  "queries_by_language": {\n'
            '    "pl": ["..."],\n'
            '    "en": ["..."]\n'
            "  }\n"
            "}\n"
            "Include every language code even if you must reuse or lightly adapt the original phrasing."
        )
        return "\n".join(content)

    async def refine_queries(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        language: str = "pl",
        max_queries: int = 3,
        model_name: Optional[str] = None,
    ) -> List[str]:
        """Return a list of refined queries for Wikipedia search."""
        result = await self.refine_queries_multi_language(
            prompt=prompt,
            chat_history=chat_history,
            languages=[language],
            max_queries=max_queries,
            model_name=model_name
        )
        return result.get(language, [])

    async def refine_queries_multi_language(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        languages: Optional[List[str]] = None,
        max_queries: int = 3,
        model_name: Optional[str] = None,
        base_queries: Optional[List[str]] = None,
    ) -> Dict[str, List[str]]:
        """Return a mapping of language code -> refined queries for Wikipedia search."""
        try:
            lang_list: List[str] = []
            seen_codes: Set[str] = set()
            if languages:
                for lang in languages:
                    code = str(lang or "").strip().lower()
                    if not code or code in seen_codes:
                        continue
                    seen_codes.add(code)
                    lang_list.append(code)
            if not lang_list:
                lang_list = ["pl"]

            system = self._build_multi_language_system_prompt(lang_list, max_queries=max(1, max_queries))
            user = self._build_multi_language_user_prompt(prompt, chat_history, lang_list, base_queries)

            if not model_name:
                model_name = (
                    self.config_service.config
                    .get('wikipedia', {})
                    .get('query_refiner', {})
                    .get('model', 'gpt-4.1-mini')
                )
            model_config = self.config_service.get_model_config(model_name)

            result = await self.llm_service.generate_structured_completion(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                model_config=model_config,
                temperature=0.2,
            )

            raw_map = result.get('queries_by_language') or {}
            if not isinstance(raw_map, dict):
                raw_map = {}

            base_cleaned: List[str] = []
            if base_queries:
                for q in base_queries:
                    q2 = str(q or "").strip()
                    if q2:
                        base_cleaned.append(q2)

            normalized: Dict[str, List[str]] = {}
            for code in lang_list:
                candidate_list = raw_map.get(code) or []
                cleaned: List[str] = []
                seen_local: Set[str] = set()
                for q in candidate_list[:max_queries]:
                    q2 = str(q or "").strip()
                    if not q2:
                        continue
                    key = q2.lower()
                    if key in seen_local:
                        continue
                    cleaned.append(q2)
                    seen_local.add(key)
                if not cleaned and base_cleaned:
                    cleaned = base_cleaned[:max_queries]
                if not cleaned:
                    cleaned = [prompt]
                normalized[code] = cleaned

            plugin_logger.info(
                "Ы\" Query refiner produced queries for languages: %s",
                ", ".join(f"{code}({len(normalized.get(code, []))})" for code in lang_list)
            )
            return normalized
        except Exception as exc:
            logger.error("Query refinement failed: %s", exc, exc_info=True)
            if languages:
                return {str(lang or '').strip().lower() or 'pl': [prompt] for lang in languages}
            return {"pl": [prompt]}
