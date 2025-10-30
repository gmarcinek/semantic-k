"""Configuration loader for Semantic Kernel project."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for a single LLM model."""

    provider: str
    model_id: str
    api_key_env: str
    endpoint: Optional[str] = None
    endpoint_env: Optional[str] = None
    deployment_name: Optional[str] = None
    api_version: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7


class RoutingRule(BaseModel):
    """Routing rule configuration (legacy keyword-based)."""

    name: str
    keywords: list[str]
    preferred_model: str


class RoutingConfig(BaseModel):
    """Routing configuration (legacy keyword-based)."""

    rules: list[RoutingRule]
    fallback_model: str


class RouterConfig(BaseModel):
    """Router configuration for topic classification and security."""

    classifier_prompt: str
    security_advisor_prompt: str
    topics: list[str]


class RoutingStrategy(BaseModel):
    """Routing strategy - maps topic to system prompt."""

    name: str
    system_prompt: str
    preferred_model: str


class SystemPrompt(BaseModel):
    """System prompt definition."""

    name: str
    value: str


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "logs/semantic-k.log"


class Config(BaseModel):
    """Main configuration class."""

    default_model: str
    models: Dict[str, ModelConfig]
    router: Optional[RouterConfig] = None
    routing_strategies: Optional[list[RoutingStrategy]] = None
    system_prompts: Optional[list[SystemPrompt]] = None
    routing: RoutingConfig  # Legacy keyword-based routing
    logging: LoggingConfig


class ConfigLoader:
    """Loads and manages configuration from YAML files."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize the config loader.

        Args:
            config_path: Path to the configuration file. If None, uses default location.
        """
        if config_path is None:
            # Default to config/config.yml in project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "config" / "config.yml"

        self.config_path = config_path
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """Load configuration from YAML file.

        Returns:
            Parsed configuration object.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If config file is invalid.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            self._config = Config(**config_data)
            return self._config

        except Exception as e:
            raise ValueError(f"Failed to load config: {e}") from e

    def get_model_config(self, model_name: str) -> ModelConfig:
        """Get configuration for a specific model.

        Args:
            model_name: Name of the model to get config for.

        Returns:
            Model configuration.

        Raises:
            ValueError: If model not found or config not loaded.
        """
        if self._config is None:
            self.load()

        if model_name not in self._config.models:
            raise ValueError(f"Model '{model_name}' not found in configuration")

        return self._config.models[model_name]

    def get_api_key(self, model_config: ModelConfig) -> str:
        """Get API key for a model from environment variables.

        Args:
            model_config: Model configuration.

        Returns:
            API key from environment.

        Raises:
            ValueError: If API key not found in environment.
        """
        api_key = os.getenv(model_config.api_key_env)
        if not api_key:
            raise ValueError(
                f"API key not found in environment variable: {model_config.api_key_env}"
            )
        return api_key

    def get_endpoint(self, model_config: ModelConfig) -> Optional[str]:
        """Get endpoint for a model, from config or environment.

        Args:
            model_config: Model configuration.

        Returns:
            Endpoint URL or None.
        """
        if model_config.endpoint:
            return model_config.endpoint

        if model_config.endpoint_env:
            return os.getenv(model_config.endpoint_env)

        return None

    @property
    def config(self) -> Config:
        """Get the loaded configuration.

        Returns:
            Configuration object.

        Raises:
            ValueError: If config not loaded yet.
        """
        if self._config is None:
            self.load()
        return self._config

    def get_system_prompt(self, prompt_name: str) -> Optional[str]:
        """Get system prompt by name.

        Args:
            prompt_name: Name of the prompt to retrieve.

        Returns:
            Prompt value or None if not found.
        """
        if self._config is None:
            self.load()

        if not self._config.system_prompts:
            return None

        for prompt in self._config.system_prompts:
            if prompt.name == prompt_name:
                return prompt.value

        return None

    def get_routing_strategy(self, topic: str) -> Optional[RoutingStrategy]:
        """Get routing strategy for a topic.

        Args:
            topic: Topic name.

        Returns:
            Routing strategy or None if not found.
        """
        if self._config is None:
            self.load()

        if not self._config.routing_strategies:
            return None

        for strategy in self._config.routing_strategies:
            if strategy.name == topic:
                return strategy

        return None

    def get_classifier_prompt(self) -> Optional[str]:
        """Get topic classifier prompt.

        Returns:
            Classifier prompt name or None.
        """
        if self._config is None:
            self.load()

        if self._config.router:
            return self._config.router.classifier_prompt

        return None

    def get_security_advisor_prompt(self) -> Optional[str]:
        """Get security advisor prompt.

        Returns:
            Security advisor prompt name or None.
        """
        if self._config is None:
            self.load()

        if self._config.router:
            return self._config.router.security_advisor_prompt

        return None

    def get_available_topics(self) -> List[str]:
        """Get list of available topics from router config.

        Returns:
            List of topic names.
        """
        if self._config is None:
            self.load()

        if self._config.router:
            return self._config.router.topics

        # Fallback to legacy routing rules
        if self._config.routing:
            return [rule.name for rule in self._config.routing.rules]

        return []
