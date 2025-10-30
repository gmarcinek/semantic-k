#!/usr/bin/env python3
"""
Test script for colored logging functionality.
Demonstrates different colored output for different plugin types.
"""

import sys
import logging
import importlib.util

# Load colored_logger module directly without triggering app.__init__
spec = importlib.util.spec_from_file_location("colored_logger", "app/utils/colored_logger.py")
colored_logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colored_logger)

setup_colored_logging = colored_logger.setup_colored_logging
get_plugin_logger = colored_logger.get_plugin_logger

# Setup colored logging
setup_colored_logging(level=logging.INFO)

# Create regular logger
regular_logger = logging.getLogger("test_app")

# Create plugin loggers
wikipedia_logger = get_plugin_logger("test_wikipedia", "wikipedia")
reranker_logger = get_plugin_logger("test_reranker", "reranker")
classification_logger = get_plugin_logger("test_classification", "classification")
llm_logger = get_plugin_logger("test_llm", "llm")

print("\n" + "=" * 80)
print("TESTING COLORED LOGGING - All plugin communications")
print("=" * 80 + "\n")

# Test regular logging (white/colored by level)
regular_logger.info("🚀 Application started")
regular_logger.warning("⚠️  This is a warning message")
regular_logger.error("❌ This is an error message")

print("\n" + "-" * 80)
print("Plugin Communications:")
print("-" * 80 + "\n")

# Test Wikipedia plugin (BRIGHT BLUE)
wikipedia_logger.info("📚 Wikipedia search returned 5 results for query: 'Python programming'")
wikipedia_logger.info("  [1] Python (programming language) (pageid: 23862)")
wikipedia_logger.info("  [2] History of Python (pageid: 23863)")
wikipedia_logger.info("  [3] Python syntax and semantics (pageid: 23864)")

wikipedia_logger.info("📖 Wikipedia fetched 3 full articles:")
wikipedia_logger.info("  📄 Python (programming language)")
wikipedia_logger.info("     Python is a high-level, general-purpose programming language...")
wikipedia_logger.info("     🔗 https://en.wikipedia.org/wiki/Python_(programming_language)")

# Test Reranker plugin (CYAN)
print()
reranker_logger.info("🔄 Reranked 10 results, returning top 3:")
reranker_logger.info("  [1] Python (programming language) (score: 0.95)")
reranker_logger.info("      💡 Highly relevant - directly matches the query intent")
reranker_logger.info("  [2] History of Python (score: 0.82)")
reranker_logger.info("      💡 Very relevant - provides historical context")

# Test Classification plugin (YELLOW)
print()
classification_logger.info("🏷️  Prompt Classification Results:")
classification_logger.info("   📂 Topic: GENERAL_KNOWLEDGE (relevance: 0.89)")
classification_logger.info("   ✅ Security Risk: 0.05 - LOW")

# Test LLM plugin (GREEN)
print()
llm_logger.info("🤖 LLM Response (gpt-4o-mini): 523 chars")
llm_logger.info("   Python is a high-level, interpreted programming language created by Guido van Rossum. It was first released in 1991 and emphasizes code readability...")

print("\n" + "=" * 80)
print("TESTING COMPLETE - Check colors in terminal!")
print("=" * 80)
print("\nColor mapping:")
print("  - Wikipedia: BRIGHT BLUE")
print("  - Reranker: CYAN")
print("  - Classification: YELLOW")
print("  - LLM: GREEN")
print("  - Regular logs: WHITE/Colored by level")
print()
