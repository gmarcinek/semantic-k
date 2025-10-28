"""Advanced example with custom routing rules.

This example demonstrates how to add custom routing rules at runtime.
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
    print("Semantic Kernel - Custom Routing Rules Example")
    print("=" * 80)
    print()

    # Initialize the application
    app = SemanticKernelApp()
    app.initialize()

    print("Initial routing rules:")
    print(app.list_routing_rules())
    print()

    # Add a custom routing rule
    print("-" * 80)
    print("Adding custom routing rule for data science tasks")
    print("-" * 80)
    app.router_plugin.add_custom_rule(
        rule_name="data_science",
        keywords=["data", "statistics", "machine learning", "dataset", "model training"],
        preferred_model="gpt-4-turbo",
    )

    print("Updated routing rules:")
    print(app.list_routing_rules())
    print()

    # Test the custom rule
    print("-" * 80)
    print("Testing custom rule with data science prompt")
    print("-" * 80)
    prompt = "Explain how to prepare a dataset for machine learning model training"

    routing_info = app.get_routing_info(prompt)
    print(routing_info)
    print()

    print("Executing prompt...")
    try:
        response = await app.route_and_execute(prompt, auto_route=True)
        print(f"Response: {response[:300]}...")
    except Exception as e:
        print(f"Error: {e}")
    print()

    # Test model suggestion by task type
    print("-" * 80)
    print("Testing model suggestions by task type")
    print("-" * 80)

    task_types = ["code_generation", "analysis", "creative", "data_science", "unknown_task"]

    for task_type in task_types:
        suggested_model = app.router_plugin.suggest_model(task_type)
        print(f"Task: {task_type:20s} -> Model: {suggested_model}")

    print()
    print("=" * 80)
    print("Custom routing example completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
