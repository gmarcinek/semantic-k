"""LLM-powered intent resolution for Wikipedia retrieval."""
from typing import Dict, List, Optional
import logging

from app.models.schemas import WikipediaIntentResult, WikipediaIntentTopic
from app.utils.colored_logger import get_plugin_logger

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'wikipedia_intent')


class WikipediaIntentService:
    """Determine primary vs contextual topics for Wikipedia usage."""

    def __init__(self, llm_service, config_service):
        self.llm_service = llm_service
        self.config_service = config_service

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert analyst that interprets user intent for Wikipedia retrieval. "
            "Given the user prompt and candidate Wikipedia articles, decide which article "
            "represents the PRIMARY focus of the question and which articles are merely "
            "CONTEXT (supporting background) versus irrelevant matches. "
            "Always return strict JSON with keys: primary, context, ignored, notes. "
            "Each primary/context/ignored entry must contain pageid, title, reasoning, and role."
        )

    def _format_candidates(self, candidates: List[Dict]) -> str:
        lines = []
        for idx, cand in enumerate(candidates, 1):
            lines.append(
                f"{idx}. Title: {cand.get('title', 'N/A')}\n"
                f"   PageID: {cand.get('pageid')}\n"
                f"   Snippet: {cand.get('snippet', '').strip()}\n"
            )
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        prompt: str,
        candidates: List[Dict],
        chat_history: Optional[List[Dict]] = None
    ) -> str:
        history_block = ""
        if chat_history:
            trimmed = chat_history[-3:]
            history_lines = [
                f"{msg.get('role', 'unknown')}: {str(msg.get('content', ''))[:160]}"
                for msg in trimmed
            ]
            history_block = "\nRecent conversation:\n" + "\n".join(history_lines)

        candidates_block = self._format_candidates(candidates)

        return (
            f"User prompt:\n\"{prompt}\"\n"
            f"{history_block}\n\n"
            "Candidate Wikipedia articles:\n"
            f"{candidates_block}\n\n"
            "Decide which candidate (if any) is the user's primary target. "
            "If the prompt explicitly asks about X in the context of Y, "
            "treat X as PRIMARY and Y as CONTEXT. Do not choose more than one PRIMARY. "
            "Context entries are those that provide background but are not the main answer. "
            "Return strict JSON:\n"
            "{\n"
            '  "primary": {"pageid": <int|null>, "title": "<str>", "reasoning": "<str>", "role": "PRIMARY"} or null,\n'
            '  "context": [{"pageid": <int|null>, "title": "<str>", "reasoning": "<str>", "role": "CONTEXT"}],\n'
            '  "ignored": [{"pageid": <int|null>, "title": "<str>", "reasoning": "<str>", "role": "IRRELEVANT"}],\n'
            '  "notes": "<overall reasoning>"\n'
            "}\n"
            "Use null pageid when you cannot map the topic. Keep arrays even if empty."
        )

    async def analyze(
        self,
        prompt: str,
        candidates: List[Dict],
        chat_history: Optional[List[Dict]] = None
    ) -> WikipediaIntentResult:
        """Return resolved intent for Wikipedia retrieval."""
        if not candidates:
            return WikipediaIntentResult(
                primary=None,
                context=[],
                ignored=[],
                notes="No candidates provided."
            )

        wiki_cfg = self.config_service.config.get('wikipedia', {})
        intent_cfg = wiki_cfg.get('intent_resolution', {})
        model_name = intent_cfg.get('model', 'gpt-4.1-mini')
        temperature = intent_cfg.get('temperature', 0.0)
        model_config = self.config_service.get_model_config(model_name)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(prompt, candidates, chat_history)

        try:
            result = await self.llm_service.generate_structured_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model_config=model_config,
                temperature=temperature
            )
        except Exception as exc:
            logger.error("Intent resolution failed: %s", exc, exc_info=True)
            return WikipediaIntentResult(
                primary=None,
                context=[],
                ignored=[],
                notes="Intent resolution failed."
            )

        def _coerce_topic(data: Optional[Dict], role: str) -> Optional[WikipediaIntentTopic]:
            if not isinstance(data, dict):
                return None
            try:
                pageid = data.get("pageid")
                if isinstance(pageid, str) and pageid.isdigit():
                    pageid = int(pageid)
                elif isinstance(pageid, (float, int)):
                    pageid = int(pageid)
                else:
                    pageid = None

                title = str(data.get("title") or "").strip()
                if not title:
                    return None

                reasoning = str(data.get("reasoning") or "").strip() or None
                return WikipediaIntentTopic(
                    pageid=pageid,
                    title=title,
                    role=role,
                    reasoning=reasoning
                )
            except Exception as err:
                logger.warning("Failed to coerce topic data %s: %s", data, err)
                return None

        primary_topic = _coerce_topic(result.get("primary"), "PRIMARY")
        context_topics = [
            topic for topic in (
                _coerce_topic(item, "CONTEXT") for item in result.get("context", [])
            ) if topic is not None
        ]
        ignored_topics = [
            topic for topic in (
                _coerce_topic(item, "IRRELEVANT") for item in result.get("ignored", [])
            ) if topic is not None
        ]
        notes = result.get("notes")
        if isinstance(notes, str):
            notes = notes.strip()
        else:
            notes = None

        plugin_logger.info(
            "Resolved Wikipedia intent. Primary=%s, context=%d, ignored=%d",
            primary_topic.title if primary_topic else None,
            len(context_topics),
            len(ignored_topics)
        )

        return WikipediaIntentResult(
            primary=primary_topic,
            context=context_topics,
            ignored=ignored_topics,
            notes=notes
        )
