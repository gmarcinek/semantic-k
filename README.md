# Semantic-K

Semantic Kernel project with intelligent LLM routing capabilities for Python.

## Overview

This project implements a Python application using Microsoft's Semantic Kernel framework with an intelligent prompt routing system. It allows you to:

- Connect to multiple LLM providers (OpenAI, Azure OpenAI, Anthropic)
- Automatically route prompts to the most appropriate model based on content
- Configure models and routing rules via YAML configuration
- Add custom routing rules at runtime
- Use Semantic Kernel's powerful plugin system

## Features

- **Multi-Provider Support**: Connect to OpenAI, Azure OpenAI, and other LLM providers
- **Intelligent Routing**: Automatically route prompts based on keywords and content analysis
- **Prompt Router Plugin**: First tool implementation that analyzes prompts and suggests optimal models
- **Flexible Configuration**: YAML-based configuration for models and routing rules
- **Easy Integration**: Simple API for chat completions and prompt execution
- **Extensible**: Add custom routing rules and plugins at runtime

## Project Structure

```
semantic-k/
├── src/
│   └── semantic_k/
│       ├── __init__.py
│       ├── semantic_k_app.py       # Main application
│       ├── plugins/
│       │   ├── __init__.py
│       │   └── prompt_router_plugin.py  # Router tool plugin
│       ├── services/
│       │   ├── __init__.py
│       │   └── llm_service.py      # LLM service management
│       └── utils/
│           ├── __init__.py
│           └── config_loader.py    # Configuration loader
├── config/
│   └── config.yml                  # Model and routing configuration
├── examples/
│   ├── basic_usage.py              # Basic usage examples
│   └── custom_routing.py           # Custom routing examples
├── tests/                          # Test directory
├── .env.example                    # Environment variables template
├── pyproject.toml                  # Project dependencies
└── README.md                       # This file
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd semantic-k
```

2. Create a virtual environment (Python 3.11+ required):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

### Environment Variables

Create a `.env` file with your API keys:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/

# Anthropic Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### Model Configuration

Edit `config/config.yml` to configure available models and routing rules:

```yaml
default_model: "gpt-4"

models:
  gpt-4:
    provider: "openai"
    model_id: "gpt-4"
    api_key_env: "OPENAI_API_KEY"
    max_tokens: 4096
    temperature: 0.7
  # ... more models

routing:
  rules:
    - name: "code_generation"
      keywords: ["code", "implement", "function", "class"]
      preferred_model: "gpt-4"
    # ... more rules
```

## Usage

### Basic Usage

```python
import asyncio
from semantic_k import SemanticKernelApp

async def main():
    # Initialize the app
    app = SemanticKernelApp()
    app.initialize()

    # Auto-route a prompt
    response = await app.route_and_execute(
        "Write a Python function to sort a list",
        auto_route=True
    )
    print(response)

    # Use a specific model
    response = await app.chat_completion(
        "What is the capital of France?",
        model_name="gpt-3.5-turbo"
    )
    print(response)

asyncio.run(main())
```

### Routing Information

```python
# Get routing analysis without executing
routing_info = app.get_routing_info(
    "Analyze the performance of this algorithm"
)
print(routing_info)
```

### Custom Routing Rules

```python
# Add a custom routing rule
app.router_plugin.add_custom_rule(
    rule_name="data_science",
    keywords=["data", "statistics", "machine learning"],
    preferred_model="gpt-4-turbo"
)

# List all rules
print(app.list_routing_rules())
```

## Prompt Router Plugin

The Prompt Router is the first tool implemented in this project. It provides several kernel functions:

- `analyze_prompt`: Analyzes a prompt and returns the recommended model
- `get_routing_info`: Returns detailed routing analysis
- `suggest_model`: Suggests a model based on task type
- `list_rules`: Lists all configured routing rules

### Plugin Functions

```python
from semantic_k import PromptRouterPlugin

# Use the router directly
router = app.router_plugin

# Analyze a prompt
model = router.analyze_prompt("Write a function to parse JSON")
print(f"Recommended model: {model}")

# Get detailed info
info = router.get_routing_info("Analyze this code for bugs")
print(info)

# Suggest by task type
model = router.suggest_model("code_generation")
print(f"Best model for code generation: {model}")
```

## Examples

Run the provided examples:

```bash
# Basic usage example
python examples/basic_usage.py

# Custom routing example
python examples/custom_routing.py
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Requirements

- Python 3.11+
- semantic-kernel >= 1.2.0
- pyyaml >= 6.0.1
- pydantic >= 2.0.0
- python-dotenv >= 1.0.0

## Architecture

### Components

1. **SemanticKernelApp**: Main application class that orchestrates the system
2. **LLMService**: Manages connections to different LLM providers
3. **PromptRouterPlugin**: Semantic Kernel plugin for intelligent routing
4. **ConfigLoader**: Loads and validates YAML configuration

### Flow

1. User submits a prompt
2. Router plugin analyzes the prompt content
3. Best model is selected based on routing rules
4. Kernel switches to the selected model (if needed)
5. Prompt is executed on the chosen model
6. Response is returned to the user

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license here]

## Acknowledgments

- Built with [Microsoft Semantic Kernel](https://github.com/microsoft/semantic-kernel)
- Supports OpenAI, Azure OpenAI, and Anthropic models
