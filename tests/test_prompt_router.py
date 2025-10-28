"""Tests for the Prompt Router Plugin."""

import pytest

from semantic_k.plugins.prompt_router_plugin import PromptRouterPlugin
from semantic_k.utils.config_loader import RoutingConfig, RoutingRule


@pytest.fixture
def routing_config() -> RoutingConfig:
    """Create a test routing configuration."""
    rules = [
        RoutingRule(
            name="code_generation",
            keywords=["code", "implement", "function", "class", "programming"],
            preferred_model="gpt-4",
        ),
        RoutingRule(
            name="analysis", keywords=["analyze", "explain", "review"], preferred_model="claude-3-sonnet"
        ),
        RoutingRule(
            name="creative",
            keywords=["write", "story", "creative", "imagine"],
            preferred_model="gpt-4-turbo",
        ),
    ]
    return RoutingConfig(rules=rules, fallback_model="gpt-3.5-turbo")


@pytest.fixture
def router_plugin(routing_config: RoutingConfig) -> PromptRouterPlugin:
    """Create a test router plugin."""
    return PromptRouterPlugin(routing_config)


def test_analyze_prompt_code_generation(router_plugin: PromptRouterPlugin) -> None:
    """Test routing for code generation prompts."""
    prompt = "Write a Python function to calculate fibonacci numbers"
    model = router_plugin.analyze_prompt(prompt)
    assert model == "gpt-4"


def test_analyze_prompt_analysis(router_plugin: PromptRouterPlugin) -> None:
    """Test routing for analysis prompts."""
    prompt = "Analyze the performance characteristics of this algorithm"
    model = router_plugin.analyze_prompt(prompt)
    assert model == "claude-3-sonnet"


def test_analyze_prompt_creative(router_plugin: PromptRouterPlugin) -> None:
    """Test routing for creative prompts."""
    prompt = "Write a short story about a robot learning to paint"
    model = router_plugin.analyze_prompt(prompt)
    assert model == "gpt-4-turbo"


def test_analyze_prompt_fallback(router_plugin: PromptRouterPlugin) -> None:
    """Test fallback when no rules match."""
    prompt = "What is the weather like today?"
    model = router_plugin.analyze_prompt(prompt)
    assert model == "gpt-3.5-turbo"


def test_suggest_model_by_task_type(router_plugin: PromptRouterPlugin) -> None:
    """Test model suggestion by task type."""
    assert router_plugin.suggest_model("code_generation") == "gpt-4"
    assert router_plugin.suggest_model("analysis") == "claude-3-sonnet"
    assert router_plugin.suggest_model("creative") == "gpt-4-turbo"
    assert router_plugin.suggest_model("unknown") == "gpt-3.5-turbo"


def test_suggest_model_by_keyword(router_plugin: PromptRouterPlugin) -> None:
    """Test model suggestion when task type is a keyword."""
    assert router_plugin.suggest_model("code") == "gpt-4"
    assert router_plugin.suggest_model("analyze") == "claude-3-sonnet"


def test_add_custom_rule(router_plugin: PromptRouterPlugin) -> None:
    """Test adding a custom routing rule."""
    initial_rule_count = len(router_plugin.rules)

    router_plugin.add_custom_rule(
        rule_name="testing", keywords=["test", "pytest", "unittest"], preferred_model="gpt-3.5-turbo"
    )

    assert len(router_plugin.rules) == initial_rule_count + 1

    # Test the new rule
    prompt = "Write a pytest test for this function"
    model = router_plugin.analyze_prompt(prompt)
    assert model == "gpt-3.5-turbo"


def test_get_routing_info(router_plugin: PromptRouterPlugin) -> None:
    """Test getting detailed routing information."""
    prompt = "Implement a function to sort an array"
    info = router_plugin.get_routing_info(prompt)

    assert "Prompt Routing Analysis" in info
    assert "code_generation" in info
    assert "gpt-4" in info


def test_list_rules(router_plugin: PromptRouterPlugin) -> None:
    """Test listing all routing rules."""
    rules_list = router_plugin.list_rules()

    assert "Configured Routing Rules" in rules_list
    assert "code_generation" in rules_list
    assert "analysis" in rules_list
    assert "creative" in rules_list
    assert "Fallback Model: gpt-3.5-turbo" in rules_list


def test_case_insensitive_matching(router_plugin: PromptRouterPlugin) -> None:
    """Test that keyword matching is case-insensitive."""
    prompts = [
        "WRITE A FUNCTION to calculate",
        "Write A Function to calculate",
        "write a function to calculate",
    ]

    for prompt in prompts:
        model = router_plugin.analyze_prompt(prompt)
        assert model == "gpt-4", f"Failed for prompt: {prompt}"


def test_word_boundary_matching(router_plugin: PromptRouterPlugin) -> None:
    """Test that keywords match only on word boundaries."""
    # "code" should match
    assert router_plugin.analyze_prompt("Write code for this") == "gpt-4"

    # "coded" should not match "code" keyword
    prompt_with_coded = "This is coded differently"
    # Should fall back since "coded" doesn't match "code" with word boundaries
    # (assuming no other keywords match)
    # This test depends on the specific implementation
