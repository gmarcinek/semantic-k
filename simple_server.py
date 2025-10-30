"""Thin entrypoint that exposes the FastAPI app from server_core.api.

Refactored into server_core package:
- server_core/config.py – config loading and prompt/model resolution
- server_core/clients.py – external clients (OpenAI)
- server_core/classifier.py – topic classifier
- server_core/plugins – plugin system with WEATHER plugin scaffold
- server_core/api.py – FastAPI app and endpoints
"""

import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from server_core.api import app  # noqa: E402
from server_core.config import CONFIG  # noqa: E402


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 50)
    logger.info("Starting Weather Chat Application")
    logger.info("=" * 50)
    logger.info(f"Default model: {CONFIG['default_model']}")
    logger.info(f"Available models: {list(CONFIG['models'].keys())}")
    strategies = CONFIG.get('strategies', []) or []
    if strategies:
        logger.info(f"Strategies: {[s.get('name') for s in strategies]}")
    else:
        logger.info(f"Routing rules: {[rule['name'] for rule in CONFIG.get('routing', {}).get('rules', [])]}")
    logger.info("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000)
