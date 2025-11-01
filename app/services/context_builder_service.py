"""Context builder service for constructing conversation contexts."""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextBuilderService:
    """Service for building conversation contexts."""

    def __init__(self, session_service):
        """Initialize context builder service.

        Args:
            session_service: Session management service
        """
        self.session_service = session_service

    def build_context_with_wikipedia(
        self,
        session_id: str,
        wiki_context: str,
        limit: int = 6
    ) -> List[Dict]:
        """Build conversation context with Wikipedia results.

        Args:
            session_id: Session ID
            wiki_context: Wikipedia context string
            limit: Maximum number of conversation messages to include

        Returns:
            List of context messages
        """
        context = self.session_service.get_conversation_context(session_id, limit=limit)
        final_context = list(context)
        final_context.append({
            'role': 'system',
            'content': f'Wikipedia results:\n{wiki_context}'
        })
        return final_context

    def build_context_with_full_article(
        self,
        session_id: str,
        wiki_context: str,
        full_article_context: str,
        limit: int = 6
    ) -> List[Dict]:
        """Build conversation context with Wikipedia results and full article.

        Args:
            session_id: Session ID
            wiki_context: Wikipedia search results context
            full_article_context: Full article context
            limit: Maximum number of conversation messages to include

        Returns:
            List of context messages
        """
        context = self.session_service.get_conversation_context(session_id, limit=limit)
        final_context = list(context)
        final_context.append({
            'role': 'system',
            'content': f'Wikipedia results:\n{wiki_context}'
        })
        final_context.append({
            'role': 'system',
            'content': f'Wikipedia full article (perfect match):\n{full_article_context}'
        })
        return final_context

    def build_detached_context_with_article(
        self,
        article_context: str
    ) -> List[Dict]:
        """Build a detached context with only a Wikipedia article (no conversation history).

        Args:
            article_context: Wikipedia article context

        Returns:
            List of context messages (system-only)
        """
        return [{
            'role': 'system',
            'content': f'Wikipedia results (detached):\n{article_context}'
        }]

    def get_conversation_context(
        self,
        session_id: str,
        limit: int = 6
    ) -> List[Dict]:
        """Get conversation context from session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to include

        Returns:
            List of context messages
        """
        return self.session_service.get_conversation_context(session_id, limit=limit)
