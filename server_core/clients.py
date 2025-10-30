import os
import logging
from typing import Optional

from openai import AsyncOpenAI

from .config import CONFIG

logger = logging.getLogger(__name__)


_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create OpenAI client using config models."""
    global _openai_client
    if _openai_client is None:
        model_config = CONFIG["models"][CONFIG["default_model"]]
        api_key_env = model_config["api_key_env"]
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(f"{api_key_env} not set in environment variables")
        _openai_client = AsyncOpenAI(api_key=api_key)
        logger.info(f"OpenAI client initialized using {api_key_env}")
    return _openai_client

