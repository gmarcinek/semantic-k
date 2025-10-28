"""Semantic Kernel Application with LLM Routing.

A Python project that implements Semantic Kernel with intelligent prompt routing
to multiple LLM providers.
"""

from .plugins.prompt_router_plugin import PromptRouterPlugin
from .semantic_k_app import SemanticKernelApp
from .services.llm_service import LLMService
from .utils.config_loader import Config, ConfigLoader, ModelConfig

__version__ = "0.1.0"

__all__ = [
    "SemanticKernelApp",
    "LLMService",
    "PromptRouterPlugin",
    "ConfigLoader",
    "Config",
    "ModelConfig",
]
