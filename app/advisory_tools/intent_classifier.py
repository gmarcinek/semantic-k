"""Intent classifier tool to detect depth of response requested.

Determines whether the user wants a brief informational answer (INFO)
or a deeper, elaborated essay (DEEP_DIVE). Uses light heuristics and
conversation context to avoid unnecessary LLM calls.
"""

import logging
from typing import Dict, List, Optional

from app.advisory_tools.base_tool import BaseAdvisoryTool
from app.models import AdvisoryResult

logger = logging.getLogger(__name__)


class IntentClassifier(BaseAdvisoryTool):
    """Heuristic intent classifier for INFO vs DEEP_DIVE."""

    # Keywords indicating a desire for more depth or an essay (PL/EN)
    DEEP_KEYWORDS_PL = [
        "więcej", "rozwiń", "szczegół", "szczegol", "dogłęb", "dogleb",
        "szerzej", "obszern", "wyczerpująco", "wyczerpujaco", "elaborat",
        "referat", "esej", "omów szerzej", "omow szerzej", "omów dogłębnie",
        "omow doglebnie", "napisz dłużej", "napisz dluzej", "pogłęb", "pogleb"
    ]

    DEEP_KEYWORDS_EN = [
        "more", "more details", "detailed", "in depth", "in-depth",
        "expand", "elaborate", "comprehensive", "long form", "long-form",
        "write an essay", "essay", "report", "deep dive", "deep-dive",
        "explain further", "go deeper", "cover in detail"
    ]

    def __init__(self, llm_service, config_service):
        super().__init__("IntentClassifier", llm_service, config_service)

    async def analyze(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ) -> AdvisoryResult:
        """Classify the user's intent as INFO or DEEP_DIVE.

        Heuristics:
        - Explicit depth cues in current prompt → DEEP_DIVE (high confidence)
        - Single-word follow-ups like "więcej" / "more" after assistant reply → DEEP_DIVE
        - Phrases like "napisz referat/esej" → DEEP_DIVE (very high confidence)
        - Otherwise → INFO
        """
        text = (prompt or "").strip().lower()

        indicators: List[str] = []
        explicit_more_request = False

        # Check explicit deep cues in current prompt
        for kw in self.DEEP_KEYWORDS_PL + self.DEEP_KEYWORDS_EN:
            if kw in text:
                indicators.append(kw)

        # Detect terse follow-up asking for more after assistant message
        if chat_history:
            last_roles = [m.get("role") for m in chat_history[-2:]]
            if any(r == "assistant" for r in last_roles):
                if text in {"więcej", "prosze wiecej", "more", "more details", "rozwiń", "rozwin"}:
                    explicit_more_request = True
                    indicators.append("explicit_followup_more")

        # Determine intent and confidence
        if explicit_more_request:
            intent = "DEEP_DIVE"
            confidence = 0.95
            reasoning = "Explicit follow-up requesting more detail detected."
        elif any(indicators):
            intent = "DEEP_DIVE"
            # Weight confidence by number/strength of indicators
            base = 0.75
            bonus = min(0.2, 0.05 * len(indicators))
            confidence = base + bonus
            reasoning = f"Depth indicators found: {', '.join(indicators)}."
        else:
            intent = "INFO"
            confidence = 0.6
            reasoning = "No signals for deep elaboration; defaulting to brief information."

        summary = f"Intent: {intent} (confidence: {confidence:.2f}). {reasoning}"

        return AdvisoryResult(
            tool_name=self.name,
            score=confidence,
            reasoning=summary,
            metadata={
                "intent": intent,
                "indicators": indicators,
                "explicit_more_request": explicit_more_request,
            },
        )

