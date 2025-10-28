"""Configuration service for managing application config."""
import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for managing application configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration service.

        Args:
            config_path: Path to config file. If None, will search default locations.
        """
        self._config: Optional[Dict] = None
        self._config_path = config_path
        self.load_config()

    def load_config(self) -> Dict:
        """Load configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
        """
        if self._config_path:
            config_path = Path(self._config_path)
        else:
            # Try default locations
            config_path = Path("config.yml")
            if not config_path.exists():
                config_path = Path("config/config.yml")

        if not config_path.exists():
            raise FileNotFoundError(
                "config.yml not found in current directory or config/ directory"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        logger.info(f"Configuration loaded from {config_path}")
        logger.info(f"Default model: {self._config['default_model']}")

        return self._config

    @property
    def config(self) -> Dict:
        """Get current configuration."""
        if self._config is None:
            raise RuntimeError("Configuration not loaded")
        return self._config

    def get_default_model(self) -> str:
        """Get default model name."""
        return self.config['default_model']

    def get_model_config(self, model_name: Optional[str] = None) -> Dict:
        """Get configuration for a specific model.

        Args:
            model_name: Name of the model. If None, returns default model config.

        Returns:
            Model configuration dictionary
        """
        if model_name is None:
            model_name = self.get_default_model()

        return self.config['models'][model_name]

    def get_routing_rules(self) -> List[Dict]:
        """Get routing rules from configuration."""
        return self.config['routing']['rules']

    def get_rule_by_name(self, rule_name: str) -> Optional[Dict]:
        """Get a specific routing rule by name.

        Args:
            rule_name: Name of the rule

        Returns:
            Rule configuration or None if not found
        """
        for rule in self.get_routing_rules():
            if rule['name'] == rule_name:
                return rule
        return None

    def get_system_prompt(self, topic: str) -> str:
        """Get system prompt for a specific topic.

        Args:
            topic: Topic name

        Returns:
            System prompt string
        """
        rule = self.get_rule_by_name(topic)
        return rule.get('system_prompt', '') if rule else ''

    def get_preferred_model_for_topic(self, topic: str) -> str:
        """Get preferred model for a topic.

        Args:
            topic: Topic name

        Returns:
            Model name
        """
        rule = self.get_rule_by_name(topic)
        if rule and 'preferred_model' in rule:
            return rule['preferred_model']
        return self.get_default_model()

    def get_available_models(self) -> List[str]:
        """Get list of available model names."""
        return list(self.config['models'].keys())

    def get_safe_config(self) -> Dict:
        """Get sanitized configuration without sensitive data.

        Returns:
            Safe configuration dictionary
        """
        return {
            "default_model": self.get_default_model(),
            "models": {
                name: {
                    "provider": cfg['provider'],
                    "model_id": cfg['model_id'],
                    "max_tokens": cfg.get('max_tokens', 0),
                    "temperature": cfg.get('temperature', 0.7)
                }
                for name, cfg in self.config['models'].items()
            },
            "routing_rules": [
                {
                    "name": rule['name'],
                    "preferred_model": rule.get('preferred_model', self.get_default_model())
                }
                for rule in self.get_routing_rules()
            ]
        }
