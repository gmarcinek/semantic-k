"""Session controller for handling session-related operations."""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SessionController:
    """Controller for session operations."""

    def __init__(self, session_service):
        """Initialize session controller.

        Args:
            session_service: Session management service
        """
        self.session_service = session_service

    async def handle_reset(self, session_id: Optional[str] = None) -> Dict:
        """Handle session reset request.

        Args:
            session_id: Optional session ID to reset

        Returns:
            Response dict with new session_id
        """
        new_session_id = self.session_service.reset_session(session_id)
        logger.info(f"Session reset: old={session_id}, new={new_session_id}")

        return {
            "session_id": new_session_id,
            "message": "Session reset successfully"
        }
