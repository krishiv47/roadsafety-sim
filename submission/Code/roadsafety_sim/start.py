"""
Road Safety Simulation Service — startup script.

Usage:
    python start.py

Starts the simulation server on http://localhost:8000
    /           → City Map (live bus tracking)
    /authority  → Authority Command Center
    /api/health → Service health check
"""
import sys
import os

# Ensure this directory is on sys.path regardless of where Python was invoked from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Validate that roadsafety_ai is adjacent (needed by ai_bridge.py)
_ai_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "roadsafety_ai")
if not os.path.isdir(_ai_dir):
    print("⚠️  WARNING: ../roadsafety_ai not found.")
    print("   ai_bridge.py will fall back to heuristic confidence values.")
    print("   For full AI integration, place roadsafety_ai/ alongside roadsafety_sim/")
    print()

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  Road Safety AI — Simulation Service")
    print("  http://localhost:8000")
    print("=" * 60)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, loop="asyncio", reload=False)
