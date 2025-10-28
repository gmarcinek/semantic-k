"""Classifier service for prompt analysis and metadata generation."""

import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class PromptMetadata(BaseModel):
    """Metadata for a classified prompt."""

    topic: str = Field(description="Topic classification: WEATHER or OTHER")
    topic_relevance: float = Field(ge=0, le=1, description="Relevance to the topic (0-1)")
    is_dangerous: float = Field(ge=0, le=1, description="Likelihood of data leak or dangerous prompt (0-1)")
    is_continuation: float = Field(ge=0, le=1, description="Is this a continuation of previous conversation (0-1)")
    topic_change: float = Field(ge=0, le=1, description="Is this a topic change (0-1)")
    summary: str = Field(description="One sentence explanation of classification")


class ClassifierService:
    """Service for classifying prompts and generating metadata."""

    def __init__(self, routing_config: Dict[str, Any]):
        """Initialize the classifier service.

        Args:
            routing_config: Routing configuration from config.yml
        """
        self.routing_config = routing_config
        self.logger = logging.getLogger(__name__)

        # Extract weather keywords
        self.weather_keywords = []
        for rule in routing_config.get('rules', []):
            if rule.get('name') == 'WEATHER':
                self.weather_keywords = [kw.lower() for kw in rule.get('keywords', [])]
                break

    def classify_prompt(self, prompt: str, chat_history: List[Dict[str, str]] = None) -> PromptMetadata:
        """Classify a prompt and generate metadata.

        Args:
            prompt: The user prompt to classify
            chat_history: Previous chat messages for context

        Returns:
            PromptMetadata with classification results
        """
        prompt_lower = prompt.lower()

        # Determine topic based on keywords
        weather_match_count = sum(1 for keyword in self.weather_keywords if keyword in prompt_lower)
        is_weather = weather_match_count > 0

        topic = "WEATHER" if is_weather else "OTHER"

        # Calculate topic relevance
        if is_weather:
            topic_relevance = min(1.0, weather_match_count / 2)  # Max out at 2 keywords
        else:
            topic_relevance = 0.0

        # Detect dangerous prompts (simple heuristics)
        dangerous_keywords = [
            "ignore", "previous", "instructions", "system", "prompt",
            "api key", "password", "secret", "token", "credentials",
            "bypass", "override", "admin", "root", "sudo"
        ]
        dangerous_match_count = sum(1 for keyword in dangerous_keywords if keyword in prompt_lower)
        is_dangerous = min(1.0, dangerous_match_count / 3)

        # Check if continuation (based on chat history)
        is_continuation = 0.0
        topic_change = 0.0

        if chat_history and len(chat_history) > 0:
            is_continuation = 0.8  # High probability of continuation

            # Check if topic changed
            last_message = chat_history[-1].get('metadata', {})
            if last_message:
                last_topic = last_message.get('topic', '')
                if last_topic and last_topic != topic:
                    topic_change = 0.9
                else:
                    topic_change = 0.1
        else:
            is_continuation = 0.0
            topic_change = 0.0

        # Generate summary
        if is_weather:
            summary = f"Prompt classified as WEATHER with {weather_match_count} matching keyword(s)."
        else:
            summary = f"Prompt classified as OTHER - no weather-related keywords found."

        if is_dangerous > 0.5:
            summary += " Potential security concern detected."

        if topic_change > 0.5:
            summary += " Topic change detected from previous conversation."

        metadata = PromptMetadata(
            topic=topic,
            topic_relevance=round(topic_relevance, 2),
            is_dangerous=round(is_dangerous, 2),
            is_continuation=round(is_continuation, 2),
            topic_change=round(topic_change, 2),
            summary=summary
        )

        self.logger.info(f"Classified prompt: {metadata.topic} (relevance: {metadata.topic_relevance})")

        return metadata

    def get_system_prompt(self, topic: str) -> str:
        """Get the system prompt for a given topic.

        Args:
            topic: Topic classification (WEATHER or OTHER)

        Returns:
            System prompt string
        """
        for rule in self.routing_config.get('rules', []):
            if rule.get('name') == topic:
                return rule.get('system_prompt', '')

        return ''

    def get_preferred_model(self, topic: str) -> str:
        """Get the preferred model for a given topic.

        Args:
            topic: Topic classification (WEATHER or OTHER)

        Returns:
            Model name
        """
        for rule in self.routing_config.get('rules', []):
            if rule.get('name') == topic:
                return rule.get('preferred_model', '')

        return self.routing_config.get('fallback_model', 'gpt-5')
