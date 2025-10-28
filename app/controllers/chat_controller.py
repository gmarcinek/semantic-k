"""Chat controller for handling chat-related operations."""
import asyncio
import json
import logging
from typing import Dict, Optional
from uuid import uuid4

from app.models import ChatRequest

logger = logging.getLogger(__name__)


class ChatController:
    """Controller for chat operations."""

    def __init__(
        self,
        session_service,
        classification_service,
        llm_service,
        config_service
    ):
        """Initialize chat controller.

        Args:
            session_service: Session management service
            classification_service: Prompt classification service
            llm_service: LLM API service
            config_service: Configuration service
        """
        self.session_service = session_service
        self.classification_service = classification_service
        self.llm_service = llm_service
        self.config_service = config_service

    async def handle_chat(self, request: ChatRequest):
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

        try:
            # Classify the prompt using advisory tools
            metadata = await self.classification_service.classify_prompt(
                prompt, chat_history
            )

            # Send metadata to client
            yield self._format_sse('metadata', metadata.model_dump())

            # Check if prompt is dangerous
            if metadata.is_dangerous > 0.8:
                error_msg = "Request rejected due to security concerns."
                yield self._format_sse('error', error_msg)
                logger.warning(f"Rejected dangerous prompt: {metadata.summary}")
                return

            # Get system prompt and model config based on topic
            system_prompt = self.config_service.get_system_prompt(metadata.topic)
            model_name = self.config_service.get_preferred_model_for_topic(metadata.topic)
            model_config = self.config_service.get_model_config(model_name)

            logger.info(
                f"Generating response: topic={metadata.topic}, model={model_name}"
            )

            # Get conversation context
            context = self.session_service.get_conversation_context(session_id)

            # Generate response
            response_text = await self.llm_service.generate_chat_response(
                prompt=prompt,
                chat_history=context,
                system_prompt=system_prompt,
                model_config=model_config
            )

            # Stream response in chunks
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield self._format_sse('chunk', chunk)
                await asyncio.sleep(0.02)

            # Send done signal
            yield self._format_sse('done', {})

            # Save to chat history
            self.session_service.add_message(
                session_id=session_id,
                role='user',
                content=prompt,
                metadata=metadata.model_dump()
            )
            self.session_service.add_message(
                session_id=session_id,
                role='assistant',
                content=response_text,
                model=model_name
            )

            logger.info(f"Chat completed for session {session_id}")

        except Exception as e:
            logger.error(f"Error in chat handler: {e}", exc_info=True)
            error_msg = f"Error: {str(e)}"
            yield self._format_sse('error', error_msg)

    def _format_sse(self, event_type: str, data) -> str:
        """Format data as Server-Sent Event.

        Args:
            event_type: Event type (metadata, chunk, done, error)
            data: Event data

        Returns:
            Formatted SSE string
        """
        event_data = {
            'type': event_type,
            'data': data
        }
        return f"data: {json.dumps(event_data)}\n\n"

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
