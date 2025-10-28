"""Main entry point for the application."""
import logging

from app import create_app

logger = logging.getLogger(__name__)


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 50)
    logger.info("Starting Semantic-K Chat Application")
    logger.info("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000)
