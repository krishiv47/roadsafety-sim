"""
Road Safety AI System — One-command launcher
=============================================
    python run.py

Opens:
  City Live Map      →  http://localhost:8000
  Authority Center   →  http://localhost:8000/authority

Press Ctrl+C to stop.
"""

import os
import sys
import shutil
import signal
import urllib.request
from pathlib import Path

ROOT   = Path(__file__).parent.resolve()
AI_DIR = ROOT / "roadsafety_ai"
MODEL  = AI_DIR / "models" / "yolov8s.pt"

YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt"


def banner(msg, char="─"):
    print(f"\n{char * 58}\n  {msg}\n{char * 58}")


def ensure_model():
    """Ensure yolov8s.pt is present; auto-download if missing."""
    if MODEL.exists():
        print(f"✓ Model found: {MODEL.name}")
        return

    print("⬇  Downloading YOLOv8s model (~22 MB)…")
    MODEL.parent.mkdir(parents=True, exist_ok=True)

    # Try ultralytics auto-download first
    try:
        from ultralytics import YOLO
        YOLO("yolov8s.pt")   # places in cwd or ~/.cache/ultralytics
        for loc in [Path("yolov8s.pt")] + list(Path.home().rglob("yolov8s.pt")):
            if loc.exists() and loc != MODEL:
                shutil.copy(loc, MODEL)
                print(f"✓ Saved to {MODEL}")
                return
        print("✓ Model cached by ultralytics (auto-loaded at runtime)")
        return
    except Exception:
        pass

    # Fallback: direct download
    try:
        urllib.request.urlretrieve(
            YOLO_URL, MODEL,
            reporthook=lambda b, bs, t:
                print(f"\r  {min(100, int(b*bs/max(t,1)*100))}%", end="", flush=True)
        )
        print(f"\n✓ Downloaded to {MODEL}")
    except Exception as e:
        print(f"\n⚠  Could not download ({e}). Simulation will use CV fallback.")


def main():
    banner("Road Safety AI System", "═")

    vi = sys.version_info
    print(f"✓ Python {vi.major}.{vi.minor}.{vi.micro}")

    if not AI_DIR.exists():
        print(f"✗ roadsafety_ai/ not found at {AI_DIR}")
        sys.exit(1)
    print(f"✓ Project folder: {ROOT.name}/")

    ensure_model()

    # Keep ROOT first so uvicorn loads roadsafety_sim/main.py, not roadsafety_ai/main.py
    os.chdir(str(ROOT))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # ai_bridge.py handles adding roadsafety_ai/ to sys.path internally

    banner("✅  Starting — open your browser", "═")
    print("""
  City Live Map      →  http://localhost:8000
  Authority Center   →  http://localhost:8000/authority

  Press Ctrl+C to stop.
""")

    def _stop(sig, frame):
        print("\nStopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000,
                loop="asyncio", reload=False)


if __name__ == "__main__":
    main()
