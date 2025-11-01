"""Simplified FastAPI server using only config.yml for all settings."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import yaml
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


# Load configuration from config.yml
def load_config() -> Dict:
    """Load configuration from config.yml."""
    config_path = Path("config.yml")
    if not config_path.exists():
        # Try alternative path
        config_path = Path("config/config.yml")
    
    if not config_path.exists():
        raise FileNotFoundError("config.yml not found in current directory or config/ directory")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# Load config at startup
CONFIG = load_config()
logger.info(f"Configuration loaded. Default model: {CONFIG['default_model']}")


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


def get_openai_client():
    """Get or create OpenAI client using config."""
    global openai_client
    if openai_client is None:
        # Get API key from config
        model_config = CONFIG['models'][CONFIG['default_model']]
        api_key_env = model_config['api_key_env']
        api_key = os.getenv(api_key_env)

        # Fallback: if a model-specific env var is missing, try OPENAI_API_KEY
        if not api_key and api_key_env != "OPENAI_API_KEY":
            fallback_key = "OPENAI_API_KEY"
            fallback_api_key = os.getenv(fallback_key)
            if fallback_api_key:
                api_key = fallback_api_key
                logger.warning(
                    f"{api_key_env} not set; falling back to {fallback_key}"
                )
        
        if not api_key:
            raise ValueError(f"{api_key_env} not set in environment variables")
        
        openai_client = AsyncOpenAI(api_key=api_key)
        logger.info(f"OpenAI client initialized using {api_key_env}")
    
    return openai_client


def get_weather_keywords() -> List[str]:
    """Get weather keywords from config."""
    for rule in CONFIG['routing']['rules']:
        if rule['name'] == 'WEATHER':
            return [kw.lower() for kw in rule['keywords']]
    return []


def get_system_prompt(topic: str) -> str:
    """Get system prompt for a topic from config."""
    for rule in CONFIG['routing']['rules']:
        if rule['name'] == topic:
            return rule.get('system_prompt', '')
    return ''


def get_model_config(topic: str) -> Dict:
    """Get model configuration for a topic from config."""
    # Get preferred model name from routing rules
    preferred_model = CONFIG['default_model']
    for rule in CONFIG['routing']['rules']:
        if rule['name'] == topic:
            preferred_model = rule.get('preferred_model', CONFIG['default_model'])
            break
    
    # Get model config
    return CONFIG['models'][preferred_model]


def classify_prompt(prompt: str, chat_history: List[Dict] = None) -> Dict:
    """Classify a prompt and generate metadata using config."""
    prompt_lower = prompt.lower()
    
    # Get weather keywords from config
    weather_keywords = get_weather_keywords()

    # Determine topic based on keywords
    weather_match_count = sum(1 for keyword in weather_keywords if keyword in prompt_lower)
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


async def generate_response(prompt: str, chat_history: List[Dict], system_prompt: str, model_config: Dict) -> str:
    """Generate response using configured model."""
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
        
        # Build API parameters
        api_params = {
            "model": model_config['model_id'],
            "messages": messages,
        }
        
        # Add optional parameters if present in config
        if 'max_completion_tokens' in model_config:
            api_params['max_completion_tokens'] = model_config['max_completion_tokens']

        # Add temperature if present in config
        if 'temperature' in model_config:
            api_params['temperature'] = model_config['temperature']
        
        response = await client.chat.completions.create(**api_params)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return f"Error generating response: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page."""
    html_path = Path("frontend/index.html")
    if not html_path.exists():
        html_path = Path("frontend") / "index.html"
    
    if not html_path.exists():
        return HTMLResponse(content="<h1>Error: frontend/index.html not found</h1>", status_code=404)
    
    with open(html_path, "r", encoding="utf-8") as f:
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

    # Classify the prompt using config
    metadata = classify_prompt(prompt, chat_history)

    # Get system prompt and model config from config.yml
    system_prompt = get_system_prompt(metadata["topic"])
    model_config = get_model_config(metadata["topic"])
    model_name = model_config['model_id']

    logger.info(f"Processing prompt for session {session_id}: topic={metadata['topic']}, model={model_name}")

    async def generate():
        """Generate streaming response."""
        try:
            # First, send metadata
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"

            # Generate response using configured model
            response_text = await generate_response(prompt, chat_history, system_prompt, model_config)

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
async def reset_session(request: Optional[Dict] = None):
    """Reset chat session."""
    session_id = request.get('session_id') if request else None
    
    if session_id and session_id in chat_sessions:
        del chat_sessions[session_id]

    new_session_id = str(uuid4())
    chat_sessions[new_session_id] = []

    return {"session_id": new_session_id, "message": "Session reset successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "config_loaded": True,
        "default_model": CONFIG['default_model'],
        "available_models": list(CONFIG['models'].keys())
    }


@app.get("/api/config")
async def get_config():
    """Get current configuration (without sensitive data)."""
    safe_config = {
        "default_model": CONFIG['default_model'],
        "models": {
            name: {
                "provider": cfg['provider'],
                "model_id": cfg['model_id'],
                "max_tokens": cfg.get('max_tokens', 0),
                "temperature": cfg.get('temperature', 0.7)
            }
            for name, cfg in CONFIG['models'].items()
        },
        "routing_rules": [
            {
                "name": rule['name'],
                "keywords_count": len(rule['keywords']),
                "preferred_model": rule['preferred_model']
            }
            for rule in CONFIG['routing']['rules']
        ]
    }
    return safe_config


if __name__ == "__main__":
    import uvicorn
    
    # Check if config is loaded
    logger.info("=" * 50)
    logger.info("Starting Weather Chat Application")
    logger.info("=" * 50)
    logger.info(f"Default model: {CONFIG['default_model']}")
    logger.info(f"Available models: {list(CONFIG['models'].keys())}")
    logger.info(f"Routing rules: {[rule['name'] for rule in CONFIG['routing']['rules']]}")
    logger.info("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
