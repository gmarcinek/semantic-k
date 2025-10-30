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

        Uses new routing_strategies structure if available,
        falls back to legacy routing rules.

        Args:
            topic: Topic name

        Returns:
            System prompt string
        """
        # Try new routing strategies first
        if 'routing_strategies' in self.config and self.config['routing_strategies']:
            for strategy in self.config['routing_strategies']:
                if strategy['name'] == topic:
                    # Get prompt value from system_prompts
                    prompt_name = strategy['system_prompt']
                    return self._get_prompt_value(prompt_name)

        # Fall back to legacy routing rules
        rule = self.get_rule_by_name(topic)
        return rule.get('system_prompt', '') if rule else ''

    def get_preferred_model_for_topic(self, topic: str) -> str:
        """Get preferred model for a topic.

        Uses new routing_strategies structure if available,
        falls back to legacy routing rules.

        Args:
            topic: Topic name

        Returns:
            Model name
        """
        # Try new routing strategies first
        if 'routing_strategies' in self.config and self.config['routing_strategies']:
            for strategy in self.config['routing_strategies']:
                if strategy['name'] == topic:
                    return strategy.get('preferred_model', self.get_default_model())

        # Fall back to legacy routing rules
        rule = self.get_rule_by_name(topic)
        if rule and 'preferred_model' in rule:
            return rule['preferred_model']
        return self.get_default_model()

    def _get_prompt_value(self, prompt_name: str) -> str:
        """Get prompt value by name from system_prompts.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Prompt value string
        """
        if 'system_prompts' not in self.config or not self.config['system_prompts']:
            return ''

        for prompt in self.config['system_prompts']:
            if prompt['name'] == prompt_name:
                return prompt['value']

        return ''

    def get_classifier_prompt(self) -> str:
        """Get topic classifier prompt.

        Returns:
            Classifier prompt string
        """
        if 'router' not in self.config or not self.config['router']:
            return ''

        prompt_name = self.config['router'].get('classifier_prompt', '')
        return self._get_prompt_value(prompt_name)

    def get_security_advisor_prompt(self) -> str:
        """Get security advisor prompt.

        Returns:
            Security advisor prompt string
        """
        if 'router' not in self.config or not self.config['router']:
            return ''

        prompt_name = self.config['router'].get('security_advisor_prompt', '')
        return self._get_prompt_value(prompt_name)

    def get_available_topics(self) -> List[str]:
        """Get list of available topics.

        Returns:
            List of topic names
        """
        # Try new router config first
        if 'router' in self.config and self.config['router']:
            return self.config['router'].get('topics', [])

        # Fall back to legacy routing rules
        return [rule['name'] for rule in self.get_routing_rules()]

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
