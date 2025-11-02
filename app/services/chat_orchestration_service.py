"""Chat orchestration service - Compatibility wrapper for refactored services."""
import logging
from typing import AsyncGenerator, Dict, List
from app.services.chat.response_generator_service import ResponseGeneratorService
from app.services.chat.flow_orchestrator_service import ChatFlowOrchestratorService

logger = logging.getLogger(__name__)


class ChatOrchestrationService:
    """Compatibility wrapper for chat flow orchestrator and response generator.

    This class maintains backward compatibility while internally using
    the refactored service architecture.
    """

    def __init__(
        self,
        session_service,
        classification_service,
        llm_service,
        config_service,
        wikipedia_search_service,
        response_strategy_service,
        context_builder_service,
        sse_formatter_service,
        query_refiner_service=None,
    ):
        """Initialize chat orchestration service.

        Args:
            session_service: Session management service
            classification_service: Prompt classification service
            llm_service: LLM API service
            config_service: Configuration service
            wikipedia_search_service: Wikipedia search service
            response_strategy_service: Response strategy service
            context_builder_service: Context builder service
            sse_formatter_service: SSE formatter service
            query_refiner_service: Optional query refiner service
        """
        # Initialize response generator
        self.response_generator = ResponseGeneratorService(
            llm_service=llm_service,
            response_strategy_service=response_strategy_service,
            wikipedia_search_service=wikipedia_search_service,
            sse_formatter_service=sse_formatter_service
        )

        # Initialize flow orchestrator
        self.flow_orchestrator = ChatFlowOrchestratorService(
            session_service=session_service,
            classification_service=classification_service,
            llm_service=llm_service,
            config_service=config_service,
            wikipedia_search_service=wikipedia_search_service,
            response_generator_service=self.response_generator,
            context_builder_service=context_builder_service,
            sse_formatter_service=sse_formatter_service,
            query_refiner_service=query_refiner_service
        )

        # Expose services for compatibility
        self.session_service = session_service
        self.classification_service = classification_service
        self.llm_service = llm_service
        self.config_service = config_service
        self.wikipedia_search_service = wikipedia_search_service
        self.response_strategy_service = response_strategy_service
        self.context_builder_service = context_builder_service
        self.sse_formatter = sse_formatter_service
        self.query_refiner_service = query_refiner_service

    async def process_chat(
        self,
        prompt: str,
        session_id: str,
        chat_history: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """Process a chat request and yield SSE events.

        Args:
            prompt: User prompt
            session_id: Session ID
            chat_history: Chat history

        Yields:
            SSE formatted events
        """
        async for event in self.flow_orchestrator.process_chat(prompt, session_id, chat_history):
            yield event
