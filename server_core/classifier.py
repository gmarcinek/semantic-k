from typing import Dict, List, Optional

from .config import CONFIG, get_history_window
from .clients import get_openai_client


async def classify_prompt(prompt: str, chat_history: Optional[List[Dict]] = None) -> Dict:
    """Classify a prompt into a topic using LLM Router (no keyword heuristics)."""
    topics = (CONFIG.get("router", {}).get("topics", []) or ["WEATHER", "ADVISORY", "OTHER"])  # fallback list
    router_prompt = CONFIG.get("router", {}).get("prompt", "")

    # Call LLM deterministically
    model_name = CONFIG["default_model"]
    model_cfg = CONFIG["models"][model_name]
    client = get_openai_client()
    messages: List[Dict] = []
    if router_prompt:
        messages.append({"role": "system", "content": router_prompt})

    # Include recent conversation as context so the router can
    # correctly treat short follow-ups like "i co?" as continuation.
    if chat_history:
        window = get_history_window()
        history_slice = chat_history if window <= 0 else chat_history[-window:]
        for msg in history_slice:
            role = msg.get("role")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # Current user prompt to classify
    messages.append({"role": "user", "content": prompt})

    topic = "OTHER"
    try:
        params = {
            "model": model_cfg["model_id"],
            "messages": messages,
            "temperature": 0.0,
            "max_completion_tokens": 16,
        }
        resp = await client.chat.completions.create(**params)
        content = (resp.choices[0].message.content or "").strip().upper()
        # Normalize and validate
        valid = {t.upper(): t for t in topics}
        topic = valid.get(content, "OTHER")
    except Exception as e:
        # Fallback to OTHER; no heuristics
        topic = "OTHER"

    # Minimal metadata; keep simple heuristics for continuation only
    is_continuation = 0.0
    topic_change = 0.0
    if chat_history and len(chat_history) > 0:
        is_continuation = 0.8
        last_message = chat_history[-1].get("metadata", {})
        if last_message:
            last_topic = last_message.get("topic", "")
            topic_change = 0.9 if last_topic and last_topic != topic else 0.1

    summary = f"Prompt classified by LLM router as {topic}."

    return {
        "topic": topic,
        "topic_relevance": 1.0,  # Router is authoritative
        "is_dangerous": 0.0,     # Not evaluated here
        "is_continuation": round(is_continuation, 2),
        "topic_change": round(topic_change, 2),
        "summary": summary,
    }
