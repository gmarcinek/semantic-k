"""Main application package."""
import logging
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers import ChatController, ConfigController
from app.router import create_router
from app.services import (
    ClassificationService,
    ConfigService,
    LLMService,
    SessionService,
)
from app.services.wikipedia_service import WikipediaService
from app.services.reranker_service import RerankerService
from app.services.query_refiner_service import QueryRefinerService
from app.utils.colored_logger import setup_colored_logging

# Load environment variables
load_dotenv()

# Configure colored logging
setup_colored_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_path: Optional[str] = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        config_path: Optional path to config file

    Returns:
        Configured FastAPI application
    """
    # Initialize services
    logger.info("Initializing services...")

    config_service = ConfigService(config_path)
    session_service = SessionService()
    llm_service = LLMService()
    classification_service = ClassificationService(llm_service, config_service)
    query_refiner_service = QueryRefinerService(llm_service, config_service)

    # Initialize Wikipedia services
    wiki_config = config_service.config.get("wikipedia", {})
    wikipedia_service = WikipediaService(language=wiki_config.get("language", "en"))
    reranker_service = RerankerService(llm_service)

    # Initialize controllers
    logger.info("Initializing controllers...")

    chat_controller = ChatController(
        session_service=session_service,
        classification_service=classification_service,
        llm_service=llm_service,
        config_service=config_service,
        wikipedia_service=wikipedia_service,
        reranker_service=reranker_service,
        query_refiner_service=query_refiner_service
    )

    config_controller = ConfigController(config_service=config_service)

    # Create FastAPI app
    app = FastAPI(
        title="Wikipedia Q&A API",
        description="Wikipedia-based Q&A system with LLM reranking and intelligent search",
        version="2.0.0"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create and include router
    router = create_router(chat_controller, config_controller)
    app.include_router(router)

    logger.info("Application initialized successfully")
    logger.info(f"Default model: {config_service.get_default_model()}")
    logger.info(f"Available models: {config_service.get_available_models()}")

    return app
