import asyncio
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .clients import get_openai_client
from .classifier import classify_prompt
from .config import CONFIG, get_model_config, get_system_prompt, get_history_window
from .plugins import get_plugin


logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None


chat_sessions: Dict[str, List[Dict]] = {}


app = FastAPI(title="Weather Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def generate_response(prompt: str, chat_history: List[Dict], system_prompt: str, model_config: Dict,
                            plugin_context: Optional[str]) -> str:
    messages: List[Dict] = []

    combined_system = system_prompt
    if plugin_context:
        combined_system = (combined_system + "\n\n" if combined_system else "") + f"[Plugin Context]: {plugin_context}"

    if combined_system:
        messages.append({"role": "system", "content": combined_system})

    # Include configured amount of history (<=0 means full history)
    history_window = get_history_window()
    history_slice = chat_history if history_window <= 0 else chat_history[-history_window:]
    for msg in history_slice:
        if msg.get("role") == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg.get("role") == "assistant":
            messages.append({"role": "assistant", "content": msg["content"]})

    messages.append({"role": "user", "content": prompt})

    try:
        client = get_openai_client()
        api_params = {
            "model": model_config["model_id"],
            "messages": messages,
        }
        if "max_completion_tokens" in model_config:
            api_params["max_completion_tokens"] = model_config["max_completion_tokens"]
        if "temperature" in model_config and model_config.get("model_id") != "gpt-5":
            api_params["temperature"] = model_config["temperature"]
        # Logging of outgoing LLM request (sizes and brief preview)
        logger.info(
            "LLM request -> model=%s, system=%s, history=%d, user_len=%d, plugin_ctx=%s",
            model_config["model_id"],
            "yes" if bool(system_prompt or plugin_context) else "no",
            len([m for m in history_slice if m.get("role") in ("user", "assistant")]),
            len(prompt or ""),
            "yes" if bool(plugin_context) else "no",
        )
        logger.debug(
            "LLM request preview -> system=%.120s | user=%.120s",
            (combined_system or "")[:120],
            (prompt or "")[:120],
        )
        response = await client.chat.completions.create(**api_params)
        content = response.choices[0].message.content
        logger.info("LLM response <- %d chars", len(content or ""))
        logger.debug("LLM response preview <- %.200s", (content or "")[:200])
        return content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return f"Error generating response: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_path = Path("frontend/index.html")
    if not html_path.exists():
        html_path = Path("frontend") / "index.html"
    if not html_path.exists():
        return HTMLResponse(content="<h1>Error: frontend/index.html not found</h1>", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/chat")
async def chat(request: ChatRequest):
    prompt = request.prompt
    session_id = request.session_id or str(uuid4())

    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    chat_history = chat_sessions[session_id]

    metadata = await classify_prompt(prompt, chat_history)

    system_prompt = get_system_prompt(metadata["topic"])
    model_config = get_model_config(metadata["topic"])
    model_name = model_config["model_id"]

    plugin_context: Optional[str] = None
    plugin = get_plugin(metadata["topic"]) if metadata["topic"] else None
    if plugin and plugin.can_handle(prompt):
        try:
            plugin_context = plugin.prepare_context(prompt)
        except Exception as e:
            logger.warning(f"Plugin error for topic {metadata['topic']}: {e}")

    logger.info(
        f"Processing prompt for session {session_id}: topic={metadata['topic']}, model={model_name}, plugin={'yes' if plugin_context else 'no'}"
    )

    async def generate():
        try:
            logger.info("SSE stream open for session %s", session_id)
            yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"
            logger.info("SSE -> sent metadata for session %s", session_id)

            response_text = await generate_response(prompt, chat_history, system_prompt, model_config, plugin_context)

            chunk_size = 10
            total_len = len(response_text or "")
            total_chunks = math.ceil(total_len / chunk_size) if chunk_size else 0
            logger.info(
                "SSE streaming started for session %s: %d chars in %d chunks",
                session_id, total_len, total_chunks
            )
            sent_chunks = 0
            for i in range(0, total_len, chunk_size):
                chunk = response_text[i : i + chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
                sent_chunks += 1
                logger.debug(
                    "SSE -> sent chunk %d/%d (len=%d) for session %s",
                    sent_chunks, total_chunks, len(chunk or ""), session_id
                )
                await asyncio.sleep(0.02)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            logger.info(
                "SSE streaming completed for session %s: sent %d/%d chunks",
                session_id, sent_chunks, total_chunks
            )

            chat_sessions[session_id].append({
                "role": "user",
                "content": prompt,
                "metadata": metadata,
            })
            chat_sessions[session_id].append({
                "role": "assistant",
                "content": response_text,
                "model": model_name,
            })
        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            error_msg = f"Error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"
        finally:
            logger.info("SSE stream closed for session %s", session_id)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/reset")
async def reset_session(request: Optional[Dict] = None):
    session_id = request.get("session_id") if request else None
    if session_id and session_id in chat_sessions:
        del chat_sessions[session_id]
    new_session_id = str(uuid4())
    chat_sessions[new_session_id] = []
    return {"session_id": new_session_id, "message": "Session reset successfully"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "config_loaded": True,
        "default_model": CONFIG["default_model"],
        "available_models": list(CONFIG["models"].keys()),
    }


@app.get("/api/config")
async def get_config():
    safe_config: Dict = {
        "default_model": CONFIG["default_model"],
        "models": {
            name: {
                "provider": cfg["provider"],
                "model_id": cfg["model_id"],
                "max_tokens": cfg.get("max_tokens", 0),
                "temperature": cfg.get("temperature", 0.7),
            }
            for name, cfg in CONFIG["models"].items()
        },
    }

    strategies = CONFIG.get("strategies", []) or []
    if strategies:
        safe_config["strategies"] = [
            {
                "name": s.get("name"),
                "keywords_count": len(s.get("keywords", []) or []),
                "preferred_model": s.get("preferred_model", CONFIG["default_model"]),
                "prompt_ref": s.get("prompt"),
            }
            for s in strategies
        ]
        safe_config["router_topics"] = CONFIG.get("router", {}).get("topics", [])
    else:
        safe_config["routing_rules"] = [
            {
                "name": rule["name"],
                "keywords_count": len(rule.get("keywords", []) or []),
                "preferred_model": rule.get("preferred_model", CONFIG["default_model"]),
            }
            for rule in (CONFIG.get("routing", {}).get("rules", []) or [])
        ]
    return safe_config
