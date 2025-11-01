"""API router with all endpoints."""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from app.models import ChatRequest, SessionResetRequest, WikipediaResearchRequest

logger = logging.getLogger(__name__)


def create_router(chat_controller, config_controller) -> APIRouter:
    """Create API router with all endpoints.

    Args:
        chat_controller: Chat controller instance
        config_controller: Config controller instance

    Returns:
        Configured APIRouter
    """
    router = APIRouter()
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"

    @router.get("/", response_class=HTMLResponse)
    async def read_root():
        """Serve the main HTML page."""
        html_path = frontend_dir / "index.html"

        if not html_path.exists():
            return HTMLResponse(
                content="<h1>Error: frontend/index.html not found</h1>",
                status_code=404
            )

        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    @router.post("/api/chat")
    async def chat(request: ChatRequest):
        """Chat endpoint with streaming support.

        Args:
            request: ChatRequest with prompt and optional session_id

        Returns:
            StreamingResponse with Server-Sent Events
        """
        return StreamingResponse(
            chat_controller.handle_chat(request),
            media_type="text/event-stream"
        )

    @router.post("/api/wiki/research")
    async def wiki_research(request: WikipediaResearchRequest):
        """Research a full Wikipedia article and generate a summary (referat).

        Streams the assistant summary as SSE chunks.
        """
        return StreamingResponse(
            chat_controller.handle_wikipedia_research(request),
            media_type="text/event-stream"
        )

    @router.post("/api/reset")
    async def reset_session(request: Optional[SessionResetRequest] = None):
        """Reset chat session.

        Args:
            request: Optional SessionResetRequest with session_id

        Returns:
            Response with new session_id
        """
        session_id = request.session_id if request else None
        return await chat_controller.handle_reset(session_id)

    @router.get("/health")
    async def health_check():
        """Health check endpoint.

        Returns:
            Health status information
        """
        return config_controller.get_health()

    @router.get("/api/config")
    async def get_config():
        """Get current configuration (without sensitive data).

        Returns:
            Sanitized configuration
        """
        return config_controller.get_config()

    return router
