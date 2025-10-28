"""FastAPI server for Semantic Kernel chat application."""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .semantic_k_app import SemanticKernelApp
from .services.classifier_service import ClassifierService


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request model."""
    prompt: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    metadata: Dict
    session_id: str


# In-memory session storage (for demo purposes)
chat_sessions: Dict[str, List[Dict]] = {}


# Initialize FastAPI app
app = FastAPI(title="Semantic Kernel Chat API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Semantic Kernel app
sk_app = SemanticKernelApp()
sk_app.initialize()

# Initialize classifier service
classifier = ClassifierService(sk_app.config.routing)


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting Semantic Kernel Chat API...")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page."""
    with open("/home/user/semantic-k/frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat endpoint with streaming support.

    Args:
        request: Chat request with prompt and optional session_id

    Returns:
        Streaming response with chat completion
    """
    prompt = request.prompt
    session_id = request.session_id or str(uuid4())

    # Get or create chat session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    chat_history = chat_sessions[session_id]

    # Classify the prompt
    metadata = classifier.classify_prompt(prompt, chat_history)

    # Get preferred model and system prompt
    preferred_model = classifier.get_preferred_model(metadata.topic)
    system_prompt = classifier.get_system_prompt(metadata.topic)

    logger.info(f"Processing prompt for session {session_id}: topic={metadata.topic}, model={preferred_model}")

    async def generate():
        """Generate streaming response."""
        try:
            # First, send metadata
            metadata_dict = metadata.dict()
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata_dict})}\n\n"

            # Get the kernel and chat service
            kernel = sk_app.llm_service.create_kernel(preferred_model)
            chat_service = kernel.get_service()

            # Build conversation history for context
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Add chat history (last 5 messages for context)
            for msg in chat_history[-5:]:
                if msg.get('role') == 'user':
                    messages.append({"role": "user", "content": msg['content']})
                elif msg.get('role') == 'assistant':
                    messages.append({"role": "assistant", "content": msg['content']})

            # Add current prompt
            messages.append({"role": "user", "content": prompt})

            # For simplicity, we'll get the full response
            # In production, you'd want true streaming from the LLM
            response = await chat_service.get_chat_message_content(
                chat_history=None,
                settings=None,
                prompt=prompt
            )

            response_text = str(response)

            # Simulate streaming by sending chunks
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
                await asyncio.sleep(0.02)  # Small delay for streaming effect

            # Send done signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

            # Save to chat history
            chat_sessions[session_id].append({
                'role': 'user',
                'content': prompt,
                'metadata': metadata_dict
            })
            chat_sessions[session_id].append({
                'role': 'assistant',
                'content': response_text,
                'model': preferred_model
            })

        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            error_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/reset")
async def reset_session(session_id: Optional[str] = None):
    """Reset chat session.

    Args:
        session_id: Session ID to reset. If None, creates a new session.

    Returns:
        New session ID
    """
    if session_id and session_id in chat_sessions:
        del chat_sessions[session_id]

    new_session_id = str(uuid4())
    chat_sessions[new_session_id] = []

    return {"session_id": new_session_id, "message": "Session reset successfully"}


@app.get("/api/models")
async def list_models():
    """List available models."""
    models = sk_app.list_available_models()
    return {"models": models}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
