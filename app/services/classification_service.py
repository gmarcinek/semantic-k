"""Classification service for orchestrating advisory tools."""
import asyncio
import logging
from typing import Dict, List, Optional

from app.advisory_tools import SecurityAdvisor, TopicClassifier
from app.advisory_tools.intent_classifier import IntentClassifier
from app.models import ClassificationMetadata
from app.utils.colored_logger import get_plugin_logger

logger = logging.getLogger(__name__)
plugin_logger = get_plugin_logger(__name__, 'classification')


class ClassificationService:
    """Service for orchestrating prompt classification using advisory tools."""

    def __init__(self, llm_service, config_service):
        """Initialize classification service.

        Args:
            llm_service: LLM service for API calls
            config_service: Configuration service
        """
        self.llm_service = llm_service
        self.config_service = config_service

        # Initialize advisory tools
        self.tools = {
            'security': SecurityAdvisor(llm_service, config_service),
            'topic': TopicClassifier(llm_service, config_service),
            'intent': IntentClassifier(llm_service, config_service),
        }

        logger.info(f"Initialized classification service with {len(self.tools)} advisory tools")

    def add_tool(self, name: str, tool):
        """Add a new advisory tool.

        Args:
            name: Tool identifier
            tool: Advisory tool instance
        """
        self.tools[name] = tool
        logger.info(f"Added advisory tool: {name}")

    async def classify_prompt(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None
    ) -> ClassificationMetadata:
        """Classify a prompt using all advisory tools.

        Runs all advisory tools in parallel for efficiency.

        Args:
            prompt: User prompt to classify
            chat_history: Optional conversation history

        Returns:
            ClassificationMetadata with aggregated results
        """
        logger.debug(f"Classifying prompt: {prompt[:50]}...")

        # Run all advisory tools in parallel
        tasks = {
            name: tool.analyze(prompt, chat_history)
            for name, tool in self.tools.items()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Map results back to tool names
        advisory_results = []
        tool_outputs = {}

        for (name, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                logger.error(f"Advisory tool {name} failed: {result}")
                continue

            advisory_results.append(result)
            tool_outputs[name] = result

        # Extract key metrics from tool outputs
        topic_result = tool_outputs.get('topic')
        security_result = tool_outputs.get('security')
        intent_result = tool_outputs.get('intent')

        # Build classification metadata
        metadata = self._build_metadata(
            topic_result,
            security_result,
            intent_result,
            chat_history,
            advisory_results
        )

        logger.info(
            f"Classification complete: topic={metadata.topic}, "
            f"security_risk={metadata.is_dangerous:.2f}"
        )

        # Log classification results with plugin logger
        plugin_logger.info(f"🏷️  Prompt Classification Results:")
        plugin_logger.info(f"   📂 Topic: {metadata.topic} (relevance: {metadata.topic_relevance:.2f})")
        if metadata.is_dangerous > 0.5:
            plugin_logger.warning(f"   ⚠️  Security Risk: {metadata.is_dangerous:.2f} - HIGH")
        elif metadata.is_dangerous > 0.2:
            plugin_logger.info(f"   ⚠️  Security Risk: {metadata.is_dangerous:.2f} - MODERATE")
        else:
            plugin_logger.info(f"   ✅ Security Risk: {metadata.is_dangerous:.2f} - LOW")

        return metadata

    def _build_metadata(
        self,
        topic_result,
        security_result,
        intent_result,
        chat_history: Optional[List[Dict]],
        advisory_results: List
    ) -> ClassificationMetadata:
        """Build classification metadata from tool results.

        Args:
            topic_result: Result from topic classifier
            security_result: Result from security advisor
            chat_history: Conversation history
            advisory_results: All advisory tool results

        Returns:
            ClassificationMetadata
        """
        # Extract topic information
        if topic_result:
            topic = topic_result.metadata.get('topic', 'OTHER')
            topic_relevance = topic_result.metadata.get('relevance_score', 0.5)
            is_continuation = 0.8 if topic_result.metadata.get('is_continuation', False) else 0.0
            topic_change = 0.9 if topic_result.metadata.get('topic_changed', False) else 0.1
            needs_wikipedia = bool(topic_result.metadata.get('needs_wikipedia', False))
        else:
            topic = 'OTHER'
            topic_relevance = 0.0
            is_continuation = 0.0
            topic_change = 0.0
            needs_wikipedia = False

        # Extract security information
        if security_result:
            is_dangerous = security_result.score
            security_reasoning = security_result.reasoning
        else:
            is_dangerous = 0.0
            security_reasoning = "Security analysis unavailable."

        # Extract intent information
        if intent_result:
            intent = intent_result.metadata.get('intent', 'INFO')
            intent_confidence = float(intent_result.score or 0.0)
        else:
            intent = 'INFO'
            intent_confidence = 0.0

        # Build summary
        summary = self._build_summary(
            topic, topic_relevance, is_dangerous, topic_change, security_reasoning
        )

        return ClassificationMetadata(
            topic=topic,
            topic_relevance=round(topic_relevance, 2),
            is_dangerous=round(is_dangerous, 2),
            is_continuation=round(is_continuation, 2),
            topic_change=round(topic_change, 2),
            summary=summary,
            intent=intent,
            intent_confidence=round(intent_confidence, 2),
            needs_wikipedia=needs_wikipedia,
            advisory_results=advisory_results
        )

    def _build_summary(
        self,
        topic: str,
        topic_relevance: float,
        is_dangerous: float,
        topic_change: float,
        security_reasoning: str
    ) -> str:
        """Build human-readable summary.

        Args:
            topic: Classified topic
            topic_relevance: Topic relevance score
            is_dangerous: Security risk score
            topic_change: Topic change score
            security_reasoning: Security analysis reasoning

        Returns:
            Summary string
        """
        summary = f"Classified as {topic} (relevance: {topic_relevance:.2f})."

        # Add security warning if needed
        if is_dangerous > 0.5:
            summary += f" SECURITY WARNING: {security_reasoning}"
        elif is_dangerous > 0.2:
            summary += " Minor security concerns detected."

        # Add topic change notice
        if topic_change > 0.5:
            summary += " Topic change detected from previous conversation."

        return summary
