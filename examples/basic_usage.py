"""Basic usage example of Semantic Kernel with routing.

This example demonstrates how to use the SemanticKernelApp with automatic prompt routing.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from semantic_k import SemanticKernelApp


async def main() -> None:
    """Main example function."""
    print("=" * 80)
    print("Semantic Kernel with Prompt Routing - Basic Example")
    print("=" * 80)
    print()

    # Initialize the application
    app = SemanticKernelApp()

    # Initialize the kernel with default model
    app.initialize()

    print("Available models:")
    for model in app.list_available_models():
        print(f"  - {model}")
    print()

    print("Routing rules:")
    print(app.list_routing_rules())
    print()

    # Example 1: Auto-routed prompt for code generation
    print("-" * 80)
    print("Example 1: Code generation (should route to gpt-4)")
    print("-" * 80)
    prompt1 = "Write a Python function to calculate the fibonacci sequence"

    routing_info = app.get_routing_info(prompt1)
    print(routing_info)
    print()

    print("Executing prompt...")
    try:
        response1 = await app.route_and_execute(prompt1, auto_route=True)
        print(f"Response: {response1[:200]}...")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # Example 2: Auto-routed prompt for analysis
    print("-" * 80)
    print("Example 2: Analysis task (should route to claude-3-sonnet)")
    print("-" * 80)
    prompt2 = "Analyze the benefits and drawbacks of microservices architecture"

    routing_info2 = app.get_routing_info(prompt2)
    print(routing_info2)
    print()

    print("Executing prompt...")
    try:
        response2 = await app.route_and_execute(prompt2, auto_route=True)
        print(f"Response: {response2[:200]}...")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # Example 3: Explicit model selection
    print("-" * 80)
    print("Example 3: Using explicit model selection (gpt-3.5-turbo)")
    print("-" * 80)
    prompt3 = "Summarize the key features of Python in three sentences"

    print(f"Prompt: {prompt3}")
    print()

    print("Executing with gpt-3.5-turbo...")
    try:
        response3 = await app.route_and_execute(prompt3, auto_route=False, model_name="gpt-3.5-turbo")
        print(f"Response: {response3}")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # Example 4: Simple chat completion
    print("-" * 80)
    print("Example 4: Simple chat completion")
    print("-" * 80)
    prompt4 = "What is the capital of France?"

    print(f"Prompt: {prompt4}")
    print()

    try:
        response4 = await app.chat_completion(prompt4)
        print(f"Response: {response4}")
    except Exception as e:
        print(f"Error: {e}")
    print()

    print("=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
