"""Server core package for the simplified FastAPI app.

Modules:
- config: load config and resolve prompts/models
- clients: external API clients (OpenAI, etc.)
- classifier: topic classification helpers
- plugins: plugin system with WEATHER scaffold
- api: FastAPI app and routes
"""

__all__ = [
    "config",
    "clients",
    "classifier",
    "plugins",
]

