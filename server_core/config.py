import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def load_config() -> Dict:
    """Load configuration from config.yml (root or config/).

    Returns:
        Dict: Parsed YAML configuration.
    """
    config_path = Path("config.yml")
    if not config_path.exists():
        config_path = Path("config/config.yml")
    if not config_path.exists():
        raise FileNotFoundError("config.yml not found in current directory or config/ directory")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG: Dict = load_config()


def _get_strategies() -> List[Dict]:
    return CONFIG.get("strategies", []) or []


def _find_strategy(topic: str) -> Optional[Dict]:
    for strat in _get_strategies():
        if strat.get("name") == topic:
            return strat
    return None


def _find_prompt_text(prompt_name: str) -> str:
    for p in CONFIG.get("prompts", []) or []:
        if p.get("name") == prompt_name:
            return p.get("value", "")
    return ""


def get_system_prompt(topic: str) -> str:
    """Resolve system prompt for a topic using strategies/prompts, with fallback."""
    strat = _find_strategy(topic)
    if strat and strat.get("prompt"):
        prompt_text = _find_prompt_text(strat["prompt"])
        if prompt_text:
            return prompt_text

    routing = CONFIG.get("routing", {})
    for rule in routing.get("rules", []) or []:
        if rule.get("name") == topic:
            return rule.get("system_prompt", "")
    return ""


def get_model_config(topic: str) -> Dict:
    """Get model configuration for a topic from strategies/routing."""
    preferred_model = CONFIG["default_model"]
    strat = _find_strategy(topic)
    if strat:
        preferred_model = strat.get("preferred_model", preferred_model)
    else:
        for rule in (CONFIG.get("routing", {}).get("rules", []) or []):
            if rule.get("name") == topic:
                preferred_model = rule.get("preferred_model", preferred_model)
                break
    return CONFIG["models"][preferred_model]


def get_history_window() -> int:
    """Get how many past messages to include in context.

    Returns a positive integer for a fixed window size. If set to 0 or a
    negative value, the entire conversation history is included.
    Defaults to 5 for backward compatibility if not configured.
    """
    chat_cfg = CONFIG.get("chat", {}) or {}
    window = chat_cfg.get("history_window", 5)
    try:
        return int(window)
    except Exception:
        return 5
