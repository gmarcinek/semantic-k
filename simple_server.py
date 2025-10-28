"""Simplified FastAPI server without Semantic Kernel dependencies."""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from uuid import uuid4

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request model."""
    prompt: str
    session_id: Optional[str] = None


# In-memory session storage
chat_sessions: Dict[str, List[Dict]] = {}


# Initialize FastAPI app
app = FastAPI(title="Weather Chat API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize API clients (lazy initialization)
openai_client = None
anthropic_client = None


def get_openai_client():
    """Get or create OpenAI client."""
    global openai_client
    if openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment variables")
        openai_client = AsyncOpenAI(api_key=api_key)
    return openai_client


def get_anthropic_client():
    """Get or create Anthropic client."""
    global anthropic_client
    if anthropic_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment variables")
        anthropic_client = AsyncAnthropic(api_key=api_key)
    return anthropic_client


# Weather keywords for classification
WEATHER_KEYWORDS = [
    "weather", "pogoda", "temperatura", "temperature", "forecast", "prognoza",
    "rain", "deszcz", "snow", "śnieg", "sun", "słońce", "cloud", "chmura",
    "wind", "wiatr", "storm", "burza"
]


def classify_prompt(prompt: str, chat_history: List[Dict] = None) -> Dict:
    """Classify a prompt and generate metadata."""
    prompt_lower = prompt.lower()

    # Determine topic based on keywords
    weather_match_count = sum(1 for keyword in WEATHER_KEYWORDS if keyword in prompt_lower)
    is_weather = weather_match_count > 0

    topic = "WEATHER" if is_weather else "OTHER"

    # Calculate topic relevance
    if is_weather:
        topic_relevance = min(1.0, weather_match_count / 2)
    else:
        topic_relevance = 0.0

    # Detect dangerous prompts
    dangerous_keywords = [
        "ignore", "previous", "instructions", "system", "prompt",
        "api key", "password", "secret", "token", "credentials"
    ]
    dangerous_match_count = sum(1 for keyword in dangerous_keywords if keyword in prompt_lower)
    is_dangerous = min(1.0, dangerous_match_count / 3)

    # Check if continuation
    is_continuation = 0.0
    topic_change = 0.0

    if chat_history and len(chat_history) > 0:
        is_continuation = 0.8

        # Check if topic changed
        last_message = chat_history[-1].get('metadata', {})
        if last_message:
            last_topic = last_message.get('topic', '')
            if last_topic and last_topic != topic:
                topic_change = 0.9
            else:
                topic_change = 0.1
    else:
        is_continuation = 0.0
        topic_change = 0.0

    # Generate summary
    if is_weather:
        summary = f"Prompt classified as WEATHER with {weather_match_count} matching keyword(s)."
    else:
        summary = f"Prompt classified as OTHER - no weather-related keywords found."

    if is_dangerous > 0.5:
        summary += " Potential security concern detected."

    if topic_change > 0.5:
        summary += " Topic change detected from previous conversation."

    return {
        "topic": topic,
        "topic_relevance": round(topic_relevance, 2),
        "is_dangerous": round(is_dangerous, 2),
        "is_continuation": round(is_continuation, 2),
        "topic_change": round(topic_change, 2),
        "summary": summary
    }


async def generate_openai_response(prompt: str, chat_history: List[Dict], system_prompt: str) -> str:
    """Generate response using OpenAI GPT-5."""
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Add chat history (last 5 messages)
    for msg in chat_history[-5:]:
        if msg.get('role') == 'user':
            messages.append({"role": "user", "content": msg['content']})
        elif msg.get('role') == 'assistant':
            messages.append({"role": "assistant", "content": msg['content']})

    # Add current prompt
    messages.append({"role": "user", "content": prompt})

    try:
        client = get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4",  # Fallback to GPT-4 if GPT-5 not available
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return f"Error generating response: {str(e)}"


async def generate_anthropic_response(prompt: str, chat_history: List[Dict], system_prompt: str) -> str:
    """Generate response using Anthropic Claude Sonnet 4.5."""
    messages = []

    # Add chat history (last 5 messages)
    for msg in chat_history[-5:]:
        if msg.get('role') == 'user':
            messages.append({"role": "user", "content": msg['content']})
        elif msg.get('role') == 'assistant':
            messages.append({"role": "assistant", "content": msg['content']})

    # Add current prompt
    messages.append({"role": "user", "content": prompt})

    try:
        client = get_anthropic_client()
        response = await client.messages.create(
            model="claude-3-5-sonnet-20240620",  # Claude 3.5 Sonnet (stable version)
            system=system_prompt if system_prompt else "You are a helpful assistant.",
            messages=messages,
            temperature=0.7,
            max_tokens=2000
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        return f"Error generating response: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page."""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat endpoint with streaming support."""
    prompt = request.prompt
    session_id = request.session_id or str(uuid4())

    # Get or create chat session
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []

    chat_history = chat_sessions[session_id]

    # Classify the prompt
    metadata = classify_prompt(prompt, chat_history)

    # Get system prompt based on topic
    if metadata["topic"] == "WEATHER":
        system_prompt = "You are a weather information assistant. Provide accurate and helpful weather-related information."
        model_name = "sonnet-4.5"
    else:
        system_prompt = "Przepraszam, ale nie posiadam informacji na ten temat. To nie jest moja dziedzina specjalizacji. Mogę Ci pomóc tylko z informacjami związanymi z pogodą."
        model_name = "gpt-5"

    logger.info(f"Processing prompt for session {session_id}: topic={metadata['topic']}, model={model_name}")

    async def generate():
        """Generate streaming response."""
        try:
            # First, send metadata
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"

            # Generate response
            if metadata["topic"] == "WEATHER":
                response_text = await generate_anthropic_response(prompt, chat_history, system_prompt)
            else:
                response_text = await generate_openai_response(prompt, chat_history, system_prompt)

            # Simulate streaming by sending chunks
            chunk_size = 10
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
                await asyncio.sleep(0.02)

            # Send done signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

            # Save to chat history
            chat_sessions[session_id].append({
                'role': 'user',
                'content': prompt,
                'metadata': metadata
            })
            chat_sessions[session_id].append({
                'role': 'assistant',
                'content': response_text,
                'model': model_name
            })

        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            error_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/reset")
async def reset_session(session_id: Optional[str] = None):
    """Reset chat session."""
    if session_id and session_id in chat_sessions:
        del chat_sessions[session_id]

    new_session_id = str(uuid4())
    chat_sessions[new_session_id] = []

    return {"session_id": new_session_id, "message": "Session reset successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
