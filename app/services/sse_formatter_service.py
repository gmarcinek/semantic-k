"""SSE (Server-Sent Events) formatting service."""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SSEFormatterService:
    """Service for formatting Server-Sent Events."""

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

    def status_event(self, message: str) -> str:
        """Helper to format status updates.

        Args:
            message: Status message to send

        Returns:
            Formatted SSE status event
        """
        return self.format_sse('status', {'message': message})
