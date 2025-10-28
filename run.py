#!/usr/bin/env python3
"""Simple script to run the application."""
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Semantic-K Chat Application (New Architecture)")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ LLM-based security detection (no keywords!)")
    print("  ✓ Intelligent topic classification")
    print("  ✓ Extensible advisory tools")
    print("  ✓ Scalable architecture")
    print("\nServer will start at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")
    print("=" * 60)
    print()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
