"""Config controller for handling configuration-related operations."""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ConfigController:
    """Controller for configuration operations."""

    def __init__(self, config_service):
        """Initialize config controller.

        Args:
            config_service: Configuration service
        """
        self.config_service = config_service

    def get_health(self) -> Dict:
        """Get health status.

        Returns:
            Health status dict
        """
        return {
            "status": "healthy",
            "config_loaded": True,
            "default_model": self.config_service.get_default_model(),
            "available_models": self.config_service.get_available_models()
        }

    def get_config(self) -> Dict:
        """Get sanitized configuration.

        Returns:
            Safe configuration dict without sensitive data
        """
        return self.config_service.get_safe_config()
