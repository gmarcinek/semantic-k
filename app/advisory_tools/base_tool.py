"""Base class for advisory tools."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.models import AdvisoryResult


class BaseAdvisoryTool(ABC):
    """Abstract base class for advisory tools.

    Advisory tools analyze prompts and provide insights such as:
    - Topic classification
    - Security risk assessment
    - Content moderation
    - Intent detection
    """

    def __init__(self, name: str, llm_service, config_service):
        """Initialize advisory tool.

        Args:
            name: Tool name identifier
            llm_service: LLM service for API calls
            config_service: Configuration service
        """
        self.name = name
        self.llm_service = llm_service
        self.config_service = config_service

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None
    ) -> AdvisoryResult:
        """Analyze a prompt and return advisory result.

        Args:
            prompt: User prompt to analyze
            chat_history: Optional conversation history
            context: Optional additional context

        Returns:
            AdvisoryResult with analysis
        """
        pass

    def _build_analysis_messages(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> List[Dict]:
        """Build messages for LLM analysis.

        Args:
            system_prompt: System instructions for the LLM
            user_prompt: User prompt to analyze

        Returns:
            List of message dictionaries
        """
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _get_model_config(self) -> Dict:
        """Get model configuration for advisory tool.

        Uses a lightweight model for quick analysis.

        Returns:
            Model configuration dictionary
        """
        # Use default model for advisory analysis
        return self.config_service.get_model_config()
