"""SSE (Server-Sent Events) formatting service."""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SSEFormatterService:
    """Service for formatting Server-Sent Events."""

    def __init__(self, config_service=None):
        """Initialize SSE formatter service.

        Args:
            config_service: Optional configuration service for status messages
        """
        self.config_service = config_service

    def format_sse(self, event_type: str, data: Any) -> str:
        """Format data as Server-Sent Event.

        Args:
            event_type: Event type (metadata, chunk, done, error, status, wikipedia)
            data: Event data

        Returns:
            Formatted SSE string
        """
        event_data = {
            'type': event_type,
            'data': data
        }
        return f"data: {json.dumps(event_data)}\n\n"

    def status_event(self, status_key: str) -> str:
        """Helper to format status updates.

        Args:
            status_key: Status message key from config

        Returns:
            Formatted SSE status event
        """
        if self.config_service:
            message = self.config_service.get_status_message(status_key)
        else:
            logger.warning("config_service not provided, using status_key as message")
            message = status_key

        return self.format_sse('status', {'message': message})
