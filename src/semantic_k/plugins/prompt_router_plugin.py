"""Prompt Router Plugin for Semantic Kernel.

This plugin analyzes incoming prompts and routes them to the most appropriate LLM model
based on configured rules and keywords.
"""

import logging
import re
from typing import Optional

from semantic_kernel.functions import kernel_function

from ..utils.config_loader import RoutingConfig

logger = logging.getLogger(__name__)


class PromptRouterPlugin:
    """Plugin that routes prompts to appropriate LLM models based on content analysis."""

    def __init__(self, routing_config: RoutingConfig) -> None:
        """Initialize the prompt router plugin.

        Args:
            routing_config: Routing configuration with rules and fallback model.
        """
        self.routing_config = routing_config
        self.rules = routing_config.rules
        self.fallback_model = routing_config.fallback_model

    @kernel_function(
        name="analyze_prompt",
        description="Analyzes a prompt and determines the best model to route it to",
    )
    def analyze_prompt(self, prompt: str) -> str:
        """Analyze a prompt and determine the best model to use.

        Args:
            prompt: The input prompt to analyze.

        Returns:
            Name of the recommended model for this prompt.
        """
        prompt_lower = prompt.lower()

        # Check each routing rule
        for rule in self.rules:
            # Count keyword matches
            matches = 0
            matched_keywords = []

            for keyword in rule.keywords:
                # Use word boundaries to avoid partial matches
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, prompt_lower):
                    matches += 1
                    matched_keywords.append(keyword)

            # If we have matches, use this rule's preferred model
            if matches > 0:
                logger.info(
                    f"Prompt matched rule '{rule.name}' with keywords: {matched_keywords}. "
                    f"Routing to model: {rule.preferred_model}"
                )
                return rule.preferred_model

        # No rules matched, use fallback
        logger.info(f"No routing rules matched. Using fallback model: {self.fallback_model}")
        return self.fallback_model

    @kernel_function(
        name="get_routing_info",
        description="Gets detailed routing information for a prompt",
    )
    def get_routing_info(self, prompt: str) -> str:
        """Get detailed routing information for a prompt.

        Args:
            prompt: The input prompt to analyze.

        Returns:
            Detailed information about routing decision as a formatted string.
        """
        prompt_lower = prompt.lower()
        info_lines = ["Prompt Routing Analysis:", f"Prompt: {prompt[:100]}...", ""]

        best_match = None
        best_match_count = 0
        best_match_keywords = []

        # Analyze all rules
        for rule in self.rules:
            matches = 0
            matched_keywords = []

            for keyword in rule.keywords:
                pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
                if re.search(pattern, prompt_lower):
                    matches += 1
                    matched_keywords.append(keyword)

            if matches > 0:
                info_lines.append(
                    f"  - Rule '{rule.name}': {matches} keyword(s) matched "
                    f"({', '.join(matched_keywords)}) -> {rule.preferred_model}"
                )

                if matches > best_match_count:
                    best_match = rule
                    best_match_count = matches
                    best_match_keywords = matched_keywords

        if best_match:
            info_lines.append("")
            info_lines.append(
                f"Selected Model: {best_match.preferred_model} "
                f"(matched {best_match_count} keyword(s): {', '.join(best_match_keywords)})"
            )
        else:
            info_lines.append("")
            info_lines.append(f"Selected Model: {self.fallback_model} (fallback - no rules matched)")

        return "\n".join(info_lines)

    @kernel_function(
        name="suggest_model",
        description="Suggests the best model for a given task type",
    )
    def suggest_model(self, task_type: str) -> str:
        """Suggest the best model for a specific task type.

        Args:
            task_type: Type of task (e.g., 'code_generation', 'analysis', 'creative').

        Returns:
            Name of the recommended model for this task type.
        """
        # Find rule matching the task type
        for rule in self.rules:
            if rule.name.lower() == task_type.lower():
                logger.info(f"Found matching rule for task '{task_type}': {rule.preferred_model}")
                return rule.preferred_model

        # Check if task type is in keywords
        task_lower = task_type.lower()
        for rule in self.rules:
            if task_lower in [k.lower() for k in rule.keywords]:
                logger.info(
                    f"Task '{task_type}' found in keywords of rule '{rule.name}': "
                    f"{rule.preferred_model}"
                )
                return rule.preferred_model

        # Return fallback
        logger.info(f"No rule found for task '{task_type}'. Using fallback: {self.fallback_model}")
        return self.fallback_model

    def add_custom_rule(
        self, rule_name: str, keywords: list[str], preferred_model: str
    ) -> None:
        """Add a custom routing rule at runtime.

        Args:
            rule_name: Name for the new rule.
            keywords: List of keywords to match.
            preferred_model: Model to use when rule matches.
        """
        from ..utils.config_loader import RoutingRule

        new_rule = RoutingRule(name=rule_name, keywords=keywords, preferred_model=preferred_model)
        self.rules.append(new_rule)
        logger.info(f"Added custom routing rule: {rule_name} -> {preferred_model}")

    def list_rules(self) -> str:
        """List all configured routing rules.

        Returns:
            Formatted string listing all rules.
        """
        lines = ["Configured Routing Rules:", ""]

        for i, rule in enumerate(self.rules, 1):
            lines.append(f"{i}. {rule.name}")
            lines.append(f"   Keywords: {', '.join(rule.keywords)}")
            lines.append(f"   Model: {rule.preferred_model}")
            lines.append("")

        lines.append(f"Fallback Model: {self.fallback_model}")

        return "\n".join(lines)
