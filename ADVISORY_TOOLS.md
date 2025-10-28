# Advisory Tools Guide

## Overview

Advisory Tools are modular, LLM-powered components that analyze prompts to provide insights such as:
- Security risk assessment
- Topic classification
- Content moderation
- Intent detection
- Custom analysis

## Built-in Tools

### 1. SecurityAdvisor

**Purpose**: Detect security risks in user prompts

**Detection Capabilities**:
- Prompt injection attempts
- Jailbreaking attempts
- Requests for sensitive information (API keys, passwords, etc.)
- System prompt extraction attempts
- Malicious instruction overrides
- Social engineering attempts

**Output**:
```json
{
  "tool_name": "SecurityAdvisor",
  "score": 0.85,
  "reasoning": "High risk: Detected prompt injection attempt...",
  "metadata": {
    "risk_level": "high",
    "detected_threats": ["prompt_injection", "credential_request"],
    "is_safe": false
  }
}
```

### 2. TopicClassifier

**Purpose**: Intelligently classify prompts into topics

**Features**:
- Semantic understanding (not keyword matching)
- Context-aware classification
- Conversation continuity detection
- Topic change detection

**Output**:
```json
{
  "tool_name": "TopicClassifier",
  "score": 0.92,
  "reasoning": "Topic: WEATHER (confidence: 0.92)...",
  "metadata": {
    "topic": "WEATHER",
    "confidence": 0.92,
    "relevance_score": 0.88,
    "is_continuation": false,
    "topic_changed": false
  }
}
```

## Creating Custom Advisory Tools

### Step 1: Create Tool Class

Create a new file in `app/advisory_tools/`:

```python
# app/advisory_tools/sentiment_analyzer.py
from typing import Dict, List, Optional
from app.advisory_tools.base_tool import BaseAdvisoryTool
from app.models import AdvisoryResult


class SentimentAnalyzer(BaseAdvisoryTool):
    """Analyze sentiment of user prompts."""

    SYSTEM_PROMPT = """You are a sentiment analysis expert.

Analyze the user's prompt and respond with JSON:
{
    "sentiment": "<positive|negative|neutral>",
    "score": <float 0.0-1.0>,
    "intensity": "<low|medium|high>",
    "reasoning": "<brief explanation>"
}

Score guide:
- 0.0-0.3: Negative
- 0.3-0.7: Neutral
- 0.7-1.0: Positive
"""

    def __init__(self, llm_service, config_service):
        super().__init__("SentimentAnalyzer", llm_service, config_service)

    async def analyze(
        self,
        prompt: str,
        chat_history: Optional[List[Dict]] = None,
        context: Optional[Dict] = None
    ) -> AdvisoryResult:
        """Analyze sentiment of prompt."""
        try:
            # Build analysis messages
            messages = self._build_analysis_messages(
                self.SYSTEM_PROMPT,
                f"Analyze sentiment: \"{prompt}\""
            )

            # Get model config
            model_config = self._get_model_config()

            # Call LLM
            result = await self.llm_service.generate_structured_completion(
                messages=messages,
                model_config=model_config,
                temperature=0.3
            )

            # Parse results
            sentiment = result.get('sentiment', 'neutral')
            score = float(result.get('score', 0.5))
            intensity = result.get('intensity', 'medium')
            reasoning = result.get('reasoning', 'Sentiment analyzed.')

            return AdvisoryResult(
                tool_name=self.name,
                score=score,
                reasoning=f"Sentiment: {sentiment} ({intensity}). {reasoning}",
                metadata={
                    'sentiment': sentiment,
                    'intensity': intensity
                }
            )

        except Exception as e:
            # Fallback
            return AdvisoryResult(
                tool_name=self.name,
                score=0.5,
                reasoning="Sentiment analysis unavailable.",
                metadata={'error': str(e)}
            )
```

### Step 2: Register Tool

Update `app/services/classification_service.py`:

```python
from app.advisory_tools import SecurityAdvisor, TopicClassifier
from app.advisory_tools.sentiment_analyzer import SentimentAnalyzer  # Add import

class ClassificationService:
    def __init__(self, llm_service, config_service):
        self.llm_service = llm_service
        self.config_service = config_service

        # Initialize advisory tools
        self.tools = {
            'security': SecurityAdvisor(llm_service, config_service),
            'topic': TopicClassifier(llm_service, config_service),
            'sentiment': SentimentAnalyzer(llm_service, config_service),  # Add tool
        }
```

### Step 3: Update Exports

Update `app/advisory_tools/__init__.py`:

```python
from .base_tool import BaseAdvisoryTool
from .security_advisor import SecurityAdvisor
from .topic_classifier import TopicClassifier
from .sentiment_analyzer import SentimentAnalyzer  # Add

__all__ = [
    "BaseAdvisoryTool",
    "SecurityAdvisor",
    "TopicClassifier",
    "SentimentAnalyzer",  # Add
]
```

That's it! Your new advisory tool will now run in parallel with others.

## Advanced Patterns

### 1. Context-Aware Analysis

Use conversation history for better analysis:

```python
async def analyze(self, prompt, chat_history, context):
    if chat_history:
        # Include recent messages for context
        recent = chat_history[-3:]
        context_str = "\n".join([f"{m['role']}: {m['content']}" for m in recent])
        analysis_prompt = f"Prompt: {prompt}\n\nContext:\n{context_str}"
    else:
        analysis_prompt = f"Prompt: {prompt}"

    # Continue analysis...
```

### 2. Conditional Execution

Skip expensive analysis when not needed:

```python
async def analyze(self, prompt, chat_history, context):
    # Quick heuristic check
    if len(prompt) < 10:
        return AdvisoryResult(
            tool_name=self.name,
            score=0.0,
            reasoning="Prompt too short for analysis.",
            metadata={}
        )

    # Expensive LLM analysis only if needed
    result = await self.llm_service.generate_structured_completion(...)
```

### 3. Multi-Model Analysis

Use different models for different purposes:

```python
def _get_model_config(self):
    # Use a faster model for quick analysis
    return self.config_service.get_model_config('gpt-3.5-turbo')
```

## Best Practices

1. **Always provide fallbacks**: If LLM call fails, return safe defaults
2. **Use structured output**: Request JSON for consistent parsing
3. **Keep prompts focused**: Clear instructions yield better results
4. **Consider performance**: Advisory tools run in parallel, but keep them fast
5. **Test thoroughly**: Validate with various input types
6. **Document behavior**: Explain what your tool detects and how

## Testing Advisory Tools

```python
# tests/test_advisory_tools.py
import pytest
from app.advisory_tools.sentiment_analyzer import SentimentAnalyzer

@pytest.mark.asyncio
async def test_sentiment_analyzer():
    # Setup
    llm_service = MockLLMService()
    config_service = MockConfigService()
    analyzer = SentimentAnalyzer(llm_service, config_service)

    # Test
    result = await analyzer.analyze("I love this!")

    # Assert
    assert result.metadata['sentiment'] == 'positive'
    assert result.score > 0.7
```

## Performance Considerations

Advisory tools run in **parallel** by default:

```python
# In ClassificationService
tasks = {
    name: tool.analyze(prompt, chat_history)
    for name, tool in self.tools.items()
}
results = await asyncio.gather(*tasks.values())
```

This means:
- Adding more tools doesn't significantly increase latency
- All tools run simultaneously
- Total time ≈ slowest tool's execution time

## Examples

See `app/advisory_tools/` for production examples:
- `security_advisor.py` - Complex security analysis
- `topic_classifier.py` - Dynamic topic classification
