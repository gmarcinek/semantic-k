"""LLM-only intent classifier to detect requested response depth.

Determines whether the user wants a brief informational answer (INFO)
or a deeper, elaborated essay (DEEP_DIVE). This version relies solely on
the LLM for classification and does not use hardcoded keyword lists or
heuristics. Conversation context may be provided to the LLM.
"""

import logging
from typing import Dict, List, Optional

from app.advisory_tools.base_tool import BaseAdvisoryTool
from app.models import AdvisoryResult

logger = logging.getLogger(__name__)


class IntentClassifier(BaseAdvisoryTool):
    """LLM-only intent classifier for INFO vs DEEP_DIVE."""

    def __init__(self, llm_service, config_service):
        super().__init__("IntentClassifier", llm_service, config_service)

    def _build_system_prompt(self) -> str:
        """Build system prompt for intent detection.

        The LLM must return strict JSON with fields: intent, confidence, reasoning.
        """
        return (
            "You are an expert intent classifier. "
            "Determine whether the user wants a brief informational answer (INFO) "
            "or a deeper, elaborated essay/report (DEEP_DIVE). "
            "Base the decision solely on semantic understanding of the current prompt "
            "and the provided recent conversation context, without relying on any keyword lists. "
            "Return a JSON object with fields: intent ('INFO' or 'DEEP_DIVE'), "
            "confidence (0.0-1.0), and reasoning (brief)."
        )

    def _build_analysis_prompt(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        """Build user message with prompt and minimal recent context for the LLM."""
        analysis = f"Classify intent for this user prompt:\n\n\"{prompt}\""

        if chat_history:
            recent = chat_history[-3:]
            context_lines = [
                f"{m.get('role')}: {str(m.get('content',''))[:240]}" for m in recent
            ]
            analysis += "\n\nRecent conversation context:\n" + "\n".join(context_lines)

        analysis += (
            "\n\nRespond ONLY with JSON in the form:\n"
            "{\n  \"intent\": \"INFO|DEEP_DIVE\",\n  \"confidence\": <float 0..1>,\n  \"reasoning\": \"<brief>\"\n}"
        )
        return analysis

    async def analyze(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ) -> AdvisoryResult:
        """Classify the user's intent as INFO or DEEP_DIVE using only the LLM."""
        try:
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_analysis_prompt(prompt, chat_history)
            model_config = self._get_model_config()

            result = await self.llm_service.generate_structured_completion(
                messages=self._build_analysis_messages(system_prompt, user_prompt),
                model_config=model_config,
                temperature=0.2,
            )

            intent = str(result.get("intent", "INFO")).strip().upper()
            if intent not in {"INFO", "DEEP_DIVE"}:
                intent = "INFO"
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "Intent classified.")

            summary = f"Intent: {intent} (confidence: {confidence:.2f}). {reasoning}"

            return AdvisoryResult(
                tool_name=self.name,
                score=confidence,
                reasoning=summary,
                metadata={
                    "intent": intent,
                },
            )
        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            return AdvisoryResult(
                tool_name=self.name,
                score=0.0,
                reasoning="Intent classification unavailable - defaulting to INFO.",
                metadata={
                    "intent": "INFO",
                    "error": str(e),
                },
            )
