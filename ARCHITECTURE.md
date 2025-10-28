# Architecture Documentation

## Overview

The application has been refactored from a monolithic `simple_server.py` into a scalable, modular architecture following best practices for maintainability and extensibility.

## Directory Structure

```
app/
├── __init__.py              # Application factory
├── main.py                  # Entry point
├── router.py                # API routes
├── controllers/             # Request handlers
│   ├── chat_controller.py
│   └── config_controller.py
├── services/                # Business logic
│   ├── config_service.py
│   ├── session_service.py
│   ├── llm_service.py
│   └── classification_service.py
├── advisory_tools/          # Extensible analysis tools
│   ├── base_tool.py
│   ├── security_advisor.py
│   └── topic_classifier.py
└── models/                  # Data models
    └── schemas.py
```

## Architecture Layers

### 1. Controllers Layer
- **Purpose**: Handle HTTP requests and responses
- **Responsibilities**:
  - Request validation
  - Response formatting
  - Error handling
  - Streaming management

### 2. Services Layer
- **Purpose**: Contain business logic
- **Key Services**:
  - `ConfigService`: Manage application configuration
  - `SessionService`: Handle chat sessions and history
  - `LLMService`: Manage API calls to language models
  - `ClassificationService`: Orchestrate advisory tools

### 3. Advisory Tools Layer
- **Purpose**: Extensible prompt analysis
- **Key Feature**: LLM-based analysis instead of heuristics
- **Tools**:
  - `SecurityAdvisor`: Detect security risks (prompt injection, etc.)
  - `TopicClassifier`: Intelligent topic classification

### 4. Models Layer
- **Purpose**: Define data structures
- **Uses**: Pydantic for validation and serialization

## Key Improvements

### 1. LLM-Based Analysis (No More Heuristics!)

**Before** (simple_server.py:141-146):
```python
dangerous_keywords = [
    "ignore", "previous", "instructions", "system", "prompt",
    "api key", "password", "secret", "token", "credentials"
]
dangerous_match_count = sum(1 for keyword in dangerous_keywords if keyword in prompt_lower)
```

**After** (SecurityAdvisor):
```python
# Uses LLM to intelligently detect security risks
# No keyword lists - understands context and intent
result = await llm_service.generate_structured_completion(
    messages=analysis_messages,
    model_config=model_config
)
```

### 2. Extensible Advisory Tools

Adding a new advisory tool is simple:

```python
# 1. Create new tool class
class CustomAdvisor(BaseAdvisoryTool):
    async def analyze(self, prompt, chat_history, context):
        # Your analysis logic
        return AdvisoryResult(...)

# 2. Register in classification_service
classification_service.add_tool('custom', CustomAdvisor(llm_service, config_service))
```

### 3. Scalable Structure

- **Separation of Concerns**: Each component has a single responsibility
- **Dependency Injection**: Services are injected, not global
- **Testability**: Each component can be tested in isolation
- **Extensibility**: Easy to add new features without modifying existing code

## Running the Application

### Development
```bash
# Using the new structure
python -m uvicorn app.main:app --reload

# Or directly
python app/main.py
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Migration from simple_server.py

The old `simple_server.py` has been decomposed as follows:

| Old Function | New Location |
|--------------|--------------|
| `classify_prompt()` | `ClassificationService.classify_prompt()` |
| `generate_response()` | `LLMService.generate_chat_response()` |
| `get_openai_client()` | `LLMService._get_client()` |
| `load_config()` | `ConfigService.load_config()` |
| Keyword matching | `TopicClassifier` (LLM-based) |
| Security heuristics | `SecurityAdvisor` (LLM-based) |
| `/api/chat` endpoint | `ChatController.handle_chat()` |

## Benefits

1. **Maintainability**: Clear structure, easy to navigate
2. **Scalability**: Easy to add new advisory tools, endpoints, or models
3. **Testability**: Each component can be unit tested
4. **Intelligence**: LLM-based analysis is more accurate than keywords
5. **Separation of Concerns**: Business logic separated from HTTP handling
6. **Reusability**: Services can be used in different contexts
