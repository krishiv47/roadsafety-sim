"""Entry point that sets sys.path and runs uvicorn — works from any cwd."""
import sys
import os

# Ensure this directory is on sys.path regardless of where Python was invoked from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, loop="asyncio", reload=False)
