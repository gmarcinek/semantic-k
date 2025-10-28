"""LLM service for managing connections to different AI providers."""

import logging
from typing import Optional

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

from ..utils.config_loader import ConfigLoader, ModelConfig

logger = logging.getLogger(__name__)


class LLMService:
    """Service for managing LLM connections and Semantic Kernel."""

    def __init__(self, config_loader: ConfigLoader) -> None:
        """Initialize the LLM service.

        Args:
            config_loader: Configuration loader instance.
        """
        self.config_loader = config_loader
        self.config = config_loader.config
        self.kernel: Optional[Kernel] = None

    def create_kernel(self, model_name: Optional[str] = None) -> Kernel:
        """Create a Semantic Kernel instance with specified model.

        Args:
            model_name: Name of the model to use. If None, uses default from config.

        Returns:
            Configured Kernel instance.

        Raises:
            ValueError: If model configuration is invalid.
        """
        if model_name is None:
            model_name = self.config.default_model

        model_config = self.config_loader.get_model_config(model_name)
        kernel = Kernel()

        # Add the appropriate AI service based on provider
        self._add_ai_service(kernel, model_name, model_config)

        self.kernel = kernel
        logger.info(f"Created kernel with model: {model_name}")
        return kernel

    def _add_ai_service(
        self, kernel: Kernel, service_id: str, model_config: ModelConfig
    ) -> None:
        """Add AI service to the kernel based on provider.

        Args:
            kernel: Kernel instance to add service to.
            service_id: Service identifier.
            model_config: Model configuration.

        Raises:
            ValueError: If provider is not supported.
        """
        api_key = self.config_loader.get_api_key(model_config)

        if model_config.provider == "openai":
            kernel.add_service(
                OpenAIChatCompletion(
                    service_id=service_id,
                    ai_model_id=model_config.model_id,
                    api_key=api_key,
                )
            )
            logger.info(f"Added OpenAI service: {service_id}")
        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}. Only OpenAI is supported.")

    def get_kernel(self) -> Kernel:
        """Get the current kernel instance.

        Returns:
            Current Kernel instance.

        Raises:
            RuntimeError: If kernel has not been created yet.
        """
        if self.kernel is None:
            raise RuntimeError("Kernel not created. Call create_kernel() first.")
        return self.kernel

    def switch_model(self, model_name: str) -> Kernel:
        """Switch to a different model by creating a new kernel.

        Args:
            model_name: Name of the model to switch to.

        Returns:
            New Kernel instance with the specified model.
        """
        logger.info(f"Switching to model: {model_name}")
        return self.create_kernel(model_name)
