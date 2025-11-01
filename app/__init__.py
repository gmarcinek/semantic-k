"""Main application package."""
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.controllers import (
    ChatController,
    ConfigController,
    SessionController,
    WikipediaResearchController,
)
from app.router import create_router
from app.services import (
    ClassificationService,
    ConfigService,
    LLMService,
    SessionService,
    SSEFormatterService,
    WikipediaSearchService,
    ResponseStrategyService,
    ContextBuilderService,
    ChatOrchestrationService,
)
from app.services.wikipedia_service import WikipediaService
from app.services.reranker_service import RerankerService
from app.services.query_refiner_service import QueryRefinerService
from app.services.wiki_intent_service import WikipediaIntentService
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

    # Initialize Wikipedia services
    wiki_config = config_service.config.get("wikipedia", {})
    wikipedia_service = WikipediaService(language=wiki_config.get("language", "pl"))
    reranker_service = RerankerService(llm_service)
    query_refiner_service = QueryRefinerService(llm_service, config_service)
    wikipedia_intent_service = WikipediaIntentService(llm_service, config_service)

    # Initialize new specialized services
    logger.info("Initializing specialized services...")

    sse_formatter_service = SSEFormatterService(config_service)
    response_strategy_service = ResponseStrategyService(config_service)
    context_builder_service = ContextBuilderService(session_service)

    wikipedia_search_service = WikipediaSearchService(
        wikipedia_service=wikipedia_service,
        reranker_service=reranker_service,
        config_service=config_service,
        wikipedia_intent_service=wikipedia_intent_service
    )

    chat_orchestration_service = ChatOrchestrationService(
        session_service=session_service,
        classification_service=classification_service,
        llm_service=llm_service,
        config_service=config_service,
        wikipedia_search_service=wikipedia_search_service,
        response_strategy_service=response_strategy_service,
        context_builder_service=context_builder_service,
        sse_formatter_service=sse_formatter_service,
        query_refiner_service=query_refiner_service
    )

    # Initialize controllers
    logger.info("Initializing controllers...")

    session_controller = SessionController(session_service=session_service)

    wikipedia_research_controller = WikipediaResearchController(
        session_service=session_service,
        config_service=config_service,
        llm_service=llm_service,
        wikipedia_service=wikipedia_service,
        sse_formatter_service=sse_formatter_service,
        wikipedia_search_service=wikipedia_search_service,
        context_builder_service=context_builder_service
    )

    chat_controller = ChatController(
        session_service=session_service,
        chat_orchestration_service=chat_orchestration_service,
        wikipedia_research_controller=wikipedia_research_controller,
        session_controller=session_controller
    )

    config_controller = ConfigController(config_service=config_service)

    # Create FastAPI app
    app = FastAPI(
        title="Wikipedia Q&A API",
        description="Wikipedia-based Q&A system with LLM reranking and intelligent search",
        version="2.0.0"
    )

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    else:
        logger.warning("Frontend directory not found for static assets: %s", frontend_dir)

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
