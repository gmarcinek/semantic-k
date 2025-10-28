"""Main Semantic Kernel Application.

This module provides the main application interface for using Semantic Kernel
with LLM routing capabilities.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from semantic_kernel import Kernel
from semantic_kernel.functions import KernelArguments

from .plugins.prompt_router_plugin import PromptRouterPlugin
from .services.llm_service import LLMService
from .utils.config_loader import ConfigLoader

# Load environment variables
load_dotenv()


class SemanticKernelApp:
    """Main application class for Semantic Kernel with routing."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize the Semantic Kernel application.

        Args:
            config_path: Path to configuration file. If None, uses default.
        """
        # Setup logging
        self._setup_logging()

        # Load configuration
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.config

        # Initialize services
        self.llm_service = LLMService(self.config_loader)

        # Initialize prompt router plugin
        self.router_plugin = PromptRouterPlugin(self.config.routing)

        # Kernel will be created on demand
        self.kernel: Optional[Kernel] = None

        self.logger.info("SemanticKernelApp initialized")

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

    def initialize(self, model_name: Optional[str] = None) -> None:
        """Initialize the kernel with a specific model.

        Args:
            model_name: Name of the model to use. If None, uses default from config.
        """
        self.kernel = self.llm_service.create_kernel(model_name)

        # Add the router plugin to the kernel
        self.kernel.add_plugin(self.router_plugin, plugin_name="PromptRouter")

        self.logger.info(f"Kernel initialized with model: {model_name or self.config.default_model}")

    def get_kernel(self) -> Kernel:
        """Get the kernel instance, initializing if necessary.

        Returns:
            Kernel instance.
        """
        if self.kernel is None:
            self.initialize()
        return self.kernel

    async def route_and_execute(
        self, prompt: str, auto_route: bool = True, model_name: Optional[str] = None
    ) -> str:
        """Route a prompt to the best model and execute it.

        Args:
            prompt: The prompt to execute.
            auto_route: If True, automatically routes to best model based on content.
            model_name: Specific model to use (overrides auto_route).

        Returns:
            Response from the LLM.
        """
        kernel = self.get_kernel()

        # Determine which model to use
        if model_name:
            target_model = model_name
            self.logger.info(f"Using explicitly specified model: {target_model}")
        elif auto_route:
            # Use the router plugin to determine best model
            target_model = self.router_plugin.analyze_prompt(prompt)
            self.logger.info(f"Auto-routed to model: {target_model}")
        else:
            target_model = self.config.default_model
            self.logger.info(f"Using default model: {target_model}")

        # Switch kernel to the target model if different from current
        current_services = list(kernel.services.keys())
        if not current_services or current_services[0] != target_model:
            self.logger.info(f"Switching kernel to model: {target_model}")
            kernel = self.llm_service.create_kernel(target_model)
            kernel.add_plugin(self.router_plugin, plugin_name="PromptRouter")
            self.kernel = kernel

        # Execute the prompt
        try:
            # Get the chat completion service
            chat_service = kernel.get_service()

            # Execute the prompt
            response = await chat_service.get_chat_message_content(
                chat_history=None, settings=None, prompt=prompt
            )

            return str(response)

        except Exception as e:
            self.logger.error(f"Error executing prompt: {e}")
            raise

    def get_routing_info(self, prompt: str) -> str:
        """Get detailed routing information for a prompt without executing it.

        Args:
            prompt: The prompt to analyze.

        Returns:
            Detailed routing information.
        """
        return self.router_plugin.get_routing_info(prompt)

    def list_available_models(self) -> list[str]:
        """List all available models from configuration.

        Returns:
            List of model names.
        """
        return list(self.config.models.keys())

    def list_routing_rules(self) -> str:
        """List all configured routing rules.

        Returns:
            Formatted string of routing rules.
        """
        return self.router_plugin.list_rules()

    async def chat_completion(
        self, prompt: str, model_name: Optional[str] = None, temperature: Optional[float] = None
    ) -> str:
        """Simple chat completion without routing.

        Args:
            prompt: The prompt to send.
            model_name: Model to use. If None, uses default.
            temperature: Temperature setting. If None, uses config default.

        Returns:
            Response from the LLM.
        """
        kernel = self.get_kernel()

        # Create or switch to specified model
        if model_name:
            kernel = self.llm_service.create_kernel(model_name)
            self.kernel = kernel

        # Get chat service and execute
        chat_service = kernel.get_service()

        # Create settings if temperature is specified
        settings = None
        if temperature is not None:
            # Note: Settings creation depends on the service type
            # This is a simplified version
            pass

        response = await chat_service.get_chat_message_content(
            chat_history=None, settings=settings, prompt=prompt
        )

        return str(response)
