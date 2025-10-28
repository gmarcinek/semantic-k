"""Topic classifier tool for intelligent topic detection."""
import json
import logging
from typing import Dict, List, Optional

from app.advisory_tools.base_tool import BaseAdvisoryTool
from app.models import AdvisoryResult

logger = logging.getLogger(__name__)


class TopicClassifier(BaseAdvisoryTool):
    """LLM-based topic classifier for intelligent topic detection.

    This tool uses an LLM to classify prompts into topics based on
    semantic understanding rather than keyword matching.
    """

    def __init__(self, llm_service, config_service):
        """Initialize topic classifier.

        Args:
            llm_service: LLM service for API calls
            config_service: Configuration service
        """
        super().__init__("TopicClassifier", llm_service, config_service)

    def _build_system_prompt(self, available_topics: List[str]) -> str:
        """Build system prompt with available topics.

        Args:
            available_topics: List of available topic names

        Returns:
            System prompt string
        """
        topics_str = ", ".join(available_topics)

        return f"""You are a topic classification expert. Analyze user prompts and classify them into predefined topics.

Available topics: {topics_str}

Analyze the user's prompt and respond with a JSON object:
{{
    "topic": "<the most appropriate topic from the list above>",
    "confidence": <float between 0.0 and 1.0>,
    "relevance_score": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation of your classification>",
    "is_continuation": <boolean - true if this continues a previous topic>,
    "topic_changed": <boolean - true if this is a topic change from conversation>
}}

Classification guidelines:
- Use semantic understanding, not just keyword matching
- Consider context from conversation history if provided
- Confidence should reflect how certain you are about the classification
- Relevance score should reflect how strongly the prompt relates to the topic
- If no topic fits well, use "OTHER" with lower confidence

Be precise and context-aware in your classification.
"""

    async def analyze(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None
    ) -> AdvisoryResult:
        """Classify prompt topic using LLM.

        Args:
            prompt: User prompt to analyze
            chat_history: Optional conversation history
            context: Optional additional context (e.g., available topics)

        Returns:
            AdvisoryResult with topic classification
        """
        try:
            # Get available topics from config
            available_topics = self._get_available_topics()

            # Build analysis prompt
            analysis_prompt = self._build_analysis_prompt(
                prompt, chat_history, available_topics
            )

            # Build system prompt
            system_prompt = self._build_system_prompt(available_topics)

            # Get model config
            model_config = self._get_model_config()

            # Call LLM for structured analysis
            result = await self.llm_service.generate_structured_completion(
                messages=self._build_analysis_messages(system_prompt, analysis_prompt),
                model_config=model_config,
                temperature=0.3
            )

            # Parse result
            topic = result.get('topic', 'OTHER')
            confidence = float(result.get('confidence', 0.5))
            relevance_score = float(result.get('relevance_score', 0.5))
            reasoning = result.get('reasoning', 'Topic classified.')
            is_continuation = result.get('is_continuation', False)
            topic_changed = result.get('topic_changed', False)

            # Build summary
            summary = f"Topic: {topic} (confidence: {confidence:.2f}). {reasoning}"

            return AdvisoryResult(
                tool_name=self.name,
                score=confidence,
                reasoning=summary,
                metadata={
                    'topic': topic,
                    'confidence': confidence,
                    'relevance_score': relevance_score,
                    'is_continuation': is_continuation,
                    'topic_changed': topic_changed
                }
            )

        except Exception as e:
            logger.error(f"Topic classification failed: {e}", exc_info=True)
            # Fallback to default
            return AdvisoryResult(
                tool_name=self.name,
                score=0.0,
                reasoning="Topic classification unavailable - defaulting to OTHER.",
                metadata={
                    'topic': 'OTHER',
                    'confidence': 0.0,
                    'error': str(e)
                }
            )

    def _get_available_topics(self) -> List[str]:
        """Get available topics from routing rules.

        Returns:
            List of topic names
        """
        rules = self.config_service.get_routing_rules()
        topics = [rule['name'] for rule in rules]

        # Always include OTHER as fallback
        if 'OTHER' not in topics:
            topics.append('OTHER')

        return topics

    def _build_analysis_prompt(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        available_topics: Optional[List[str]] = None
    ) -> str:
        """Build analysis prompt with context.

        Args:
            prompt: User prompt to analyze
            chat_history: Optional conversation history
            available_topics: Optional list of available topics

        Returns:
            Formatted analysis prompt
        """
        analysis = f"Classify this user prompt:\n\n\"{prompt}\""

        if chat_history and len(chat_history) > 0:
            # Include recent context
            recent = chat_history[-3:]

            # Get last topic if available
            last_topic = None
            for msg in reversed(chat_history):
                if msg.get('metadata', {}).get('topic'):
                    last_topic = msg['metadata']['topic']
                    break

            context_str = "\n".join([
                f"{msg['role']}: {msg['content'][:100]}"
                for msg in recent
            ])
            analysis += f"\n\nRecent conversation context:\n{context_str}"

            if last_topic:
                analysis += f"\n\nPrevious topic was: {last_topic}"

        return analysis
