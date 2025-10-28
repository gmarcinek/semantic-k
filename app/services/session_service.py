"""Session service for managing chat sessions."""
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from app.models import ChatMessage

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing chat sessions."""

    def __init__(self):
        """Initialize session service."""
        self._sessions: Dict[str, List[Dict]] = {}

    def create_session(self) -> str:
        """Create a new session.

        Returns:
            New session ID
        """
        session_id = str(uuid4())
        self._sessions[session_id] = []
        logger.info(f"Created new session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> List[Dict]:
        """Get chat history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of chat messages
        """
        if session_id not in self._sessions:
            logger.info(f"Session {session_id} not found, creating new one")
            self._sessions[session_id] = []

        return self._sessions[session_id]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        model: Optional[str] = None
    ) -> None:
        """Add a message to session history.

        Args:
            session_id: Session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Optional metadata
            model: Model used for generation (for assistant messages)
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        message = {
            'role': role,
            'content': content
        }

        if metadata:
            message['metadata'] = metadata

        if model:
            message['model'] = model

        self._sessions[session_id].append(message)
        logger.debug(f"Added {role} message to session {session_id}")

    def reset_session(self, session_id: Optional[str] = None) -> str:
        """Reset a session or create a new one.

        Args:
            session_id: Session to reset. If None, creates new session.

        Returns:
            New session ID
        """
        if session_id and session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Reset session {session_id}")

        return self.create_session()

    def session_exists(self, session_id: str) -> bool:
        """Check if session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        return session_id in self._sessions

    def get_recent_messages(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get recent messages from session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of recent messages
        """
        history = self.get_session(session_id)
        return history[-limit:] if history else []

    def get_conversation_context(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get conversation context formatted for LLM.

        Args:
            session_id: Session identifier
            limit: Maximum number of message pairs to include

        Returns:
            List of messages formatted for LLM
        """
        history = self.get_recent_messages(session_id, limit)
        context = []

        for msg in history:
            if msg.get('role') in ['user', 'assistant']:
                context.append({
                    'role': msg['role'],
                    'content': msg['content']
                })

        return context
