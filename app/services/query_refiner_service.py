"""LLM-based query refiner for Wikipedia searches.

Generates a small set of high-quality search queries based on the user's
prompt and recent conversation context. Output is LLM-only, structured JSON.
"""

import logging
from typing import Dict, List, Optional

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
                f"{m.get('role')}: {str(m.get('content',''))[:120]}" for m in recent
            )
            content.append("\nRecent conversation context:\n" + hist)
        content.append(
            "\nRespond ONLY with JSON of the form: {\n  \"queries\": [\"...\"]\n}"
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
        try:
            system = self._build_system_prompt(language=language, max_queries=max_queries)
            user = self._build_user_prompt(prompt, chat_history)

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

            queries = result.get('queries') or []
            if not isinstance(queries, list):
                return []

            # Cleanup and dedup
            cleaned = []
            seen = set()
            for q in queries[:max_queries]:
                q2 = (str(q).strip())
                if not q2 or q2.lower() in seen:
                    continue
                cleaned.append(q2)
                seen.add(q2.lower())

            plugin_logger.info(
                f"🔎 Query refiner produced {len(cleaned)} queries: " + ", ".join(cleaned)
            )
            return cleaned
        except Exception as e:
            logger.error(f"Query refinement failed: {e}", exc_info=True)
            return []

