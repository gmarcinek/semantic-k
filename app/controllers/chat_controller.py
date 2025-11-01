"""Chat controller for handling chat-related operations."""
import logging
from typing import AsyncGenerator, Dict, Optional
from uuid import uuid4

from app.models import ChatRequest, WikipediaResearchRequest

logger = logging.getLogger(__name__)


class ChatController:
    """Thin controller for chat operations - delegates to orchestration services."""

    def __init__(
        self,
        session_service,
        chat_orchestration_service,
        wikipedia_research_controller,
        session_controller
    ):
        """Initialize chat controller.

        Args:
            session_service: Session management service
            chat_orchestration_service: Chat orchestration service
            wikipedia_research_controller: Wikipedia research controller
            session_controller: Session controller
        """
        self.session_service = session_service
        self.chat_orchestration_service = chat_orchestration_service
        self.wikipedia_research_controller = wikipedia_research_controller
        self.session_controller = session_controller

    async def handle_chat(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Handle chat request with streaming response.

        Args:
            request: ChatRequest with prompt and session_id

        Yields:
            Server-Sent Events (SSE) formatted data
        """
        prompt = request.prompt
        session_id = request.session_id or str(uuid4())

        logger.info(f"Processing chat for session {session_id}")

        # Get chat history
        chat_history = self.session_service.get_session(session_id)

        # Delegate to orchestration service
        async for event in self.chat_orchestration_service.process_chat(
            prompt=prompt,
            session_id=session_id,
            chat_history=chat_history
        ):
            yield event

    async def handle_wikipedia_research(
        self,
        request: WikipediaResearchRequest
    ) -> AsyncGenerator[str, None]:
        """Handle Wikipedia research request.

        Args:
            request: WikipediaResearchRequest with session_id, pageid, and title

        Yields:
            Server-Sent Events (SSE) formatted data
        """
        async for event in self.wikipedia_research_controller.handle_wikipedia_research(request):
            yield event

    async def handle_reset(self, session_id: Optional[str] = None) -> Dict:
        """Handle session reset request.

        Args:
            session_id: Optional session ID to reset

        Returns:
            Response dict with new session_id
        """
        return await self.session_controller.handle_reset(session_id)
