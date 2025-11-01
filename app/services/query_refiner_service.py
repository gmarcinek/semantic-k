"""LLM-powered query refiner for Wikipedia searches.

Takes a natural-language user prompt and produces concise Wikipedia-ready
search queries (e.g., article titles or key phrases). Falls back gracefully
if LLM fails.
"""

import logging
from typing import Dict, List, Optional, Tuple


class QueryRefinerService:
    """Uses LLM to refine user prompts into Wikipedia search queries."""

    def __init__(self, llm_service, config_service):
        self.llm_service = llm_service
        self.config_service = config_service
        self.logger = logging.getLogger(__name__)

    def _get_model_config(self) -> Dict:
        cfg = self.config_service.config
        wiki_cfg = cfg.get("wikipedia", {})
        ref_cfg = wiki_cfg.get("query_refiner", {})

        # Model selection: prefer wikipedia.query_refiner.model, else default_model
        model_name = ref_cfg.get("model") or cfg.get("default_model")
        return self.config_service.get_model_config(model_name)

    async def refine(self, prompt: str, max_queries: Optional[int] = None) -> Tuple[List[str], Optional[str]]:
        """Refine a user prompt into candidate Wikipedia search queries.

        Returns a tuple of (queries, language) where language can be 'pl', 'en', etc., or None.
        """
        cfg = self.config_service.config
        wiki_cfg = cfg.get("wikipedia", {})
        ref_cfg = wiki_cfg.get("query_refiner", {})
        enabled = ref_cfg.get("enabled", True)
        max_q = max_queries or ref_cfg.get("max_queries", 3)

        if not enabled:
            return [], None

        system = (
            "You are a search query planner for Wikipedia. "
            "Given a user's question, propose up to N short search queries suitable for Wikipedia search. "
            "Prefer likely article titles or concise noun phrases. If relevant, infer the language ('pl' or 'en'). "
            "Output strictly as JSON with keys: queries (list[str]), language (string|null)."
        )

        user = (
            f"User question: {prompt}\n\n"
            f"N: {max_q}\n\n"
            "Return JSON only."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        model_config = self._get_model_config()

        try:
            data = await self.llm_service.generate_structured_completion(
                messages=messages,
                model_config=model_config,
                temperature=0.0,
            )

            queries = data.get("queries") or []
            language = data.get("language")

            # Normalize
            if not isinstance(queries, list):
                queries = []
            queries = [q for q in queries if isinstance(q, str) and q.strip()]
            if max_q and len(queries) > max_q:
                queries = queries[:max_q]

            if language and isinstance(language, str):
                language = language.strip().lower() or None

            self.logger.info(f"QueryRefiner produced {len(queries)} queries; lang={language}")
            return queries, language

        except Exception as e:
            self.logger.warning(f"Query refinement failed, falling back to heuristics: {e}")
            return [], None

