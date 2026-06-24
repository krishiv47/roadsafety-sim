"""
Road Safety AI System — One-command launcher
=============================================
Starts BOTH services with a single command:
    python run.py

  AI Detection  → http://localhost:8001
  City Map      → http://localhost:8000          ← open this
  Authority     → http://localhost:8000/authority

Press Ctrl+C to stop everything.
"""

import os
import sys
import time
import shutil
import signal
import subprocess
import urllib.request
from pathlib import Path

ROOT   = Path(__file__).parent.resolve()
AI_DIR = ROOT / "roadsafety_ai"
MODEL  = AI_DIR / "models" / "yolov8s.pt"
SIM_MODEL = ROOT / "yolov8s.pt"  # ultralytics also searches cwd

YOLO_DOWNLOAD = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt"

# ── Helpers ────────────────────────────────────────────────────

def banner(msg, char="─"):
    print(f"\n{char * 58}")
    print(f"  {msg}")
    print(f"{char * 58}")


def check_python():
    vi = sys.version_info
    if vi < (3, 10):
        print(f"✗ Python 3.10+ required (you have {vi.major}.{vi.minor})")
        sys.exit(1)
    print(f"✓ Python {vi.major}.{vi.minor}.{vi.micro}")


def ensure_model():
    """Download yolov8s.pt if not already present."""
    if MODEL.exists():
        print(f"✓ Model: {MODEL}")
        return
    # Try ultralytics auto-download (places in current dir or cache)
    print("⬇  yolov8s.pt not found — downloading (~22 MB)…")
    try:
        from ultralytics import YOLO
        m = YOLO("yolov8s.pt")   # downloads to cwd or ~/.cache/ultralytics
        # Find the file ultralytics downloaded
        downloaded = Path("yolov8s.pt")
        if not downloaded.exists():
            import glob
            hits = (glob.glob(str(Path.home() / ".cache/ultralytics/**/yolov8s.pt"), recursive=True)
                    + glob.glob(str(Path.home() / ".config/**/yolov8s.pt"),         recursive=True))
            if hits:
                downloaded = Path(hits[0])
        if downloaded.exists():
            shutil.copy(downloaded, MODEL)
            print(f"✓ Model saved to {MODEL}")
        else:
            print(f"✓ Model in ultralytics cache — will load automatically")
        return
    except Exception as e:
        print(f"  Ultralytics auto-download failed ({e}), trying direct URL…")

    # Fallback: direct HTTP download
    try:
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(YOLO_DOWNLOAD, MODEL,
            reporthook=lambda b, bs, t: print(
                f"\r  {min(100, int(b*bs/max(t,1)*100))}%", end="", flush=True))
        print(f"\n✓ Downloaded to {MODEL}")
    except Exception as e:
        print(f"\n✗ Could not download model: {e}")
        print(f"  Manually place yolov8s.pt at: {MODEL}")
        sys.exit(1)


def wait_for_port(port: int, timeout: int = 30) -> bool:
    """Poll until the port accepts connections."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


# ── Main ───────────────────────────────────────────────────────

def main():
    banner("Road Safety AI System — Starting up", "═")

    check_python()

    # Verify layout
    if not AI_DIR.exists():
        print(f"✗ roadsafety_ai/ folder not found at {AI_DIR}")
        sys.exit(1)
    print(f"✓ Layout: single-folder ({ROOT.name}/)")

    ensure_model()

    # ── Start AI service (subprocess, port 8001) ───────────────
    banner("Starting AI Detection Service on port 8001")
    ai_env = os.environ.copy()
    ai_env["PYTHONPATH"] = str(AI_DIR)
    ai_proc = subprocess.Popen(
        [sys.executable, str(AI_DIR / "start.py")],
        cwd=str(AI_DIR),
        env=ai_env,
    )

    print("  Waiting for AI service to be ready…", end="", flush=True)
    if wait_for_port(8001, timeout=40):
        print(" ✓")
    else:
        print(" timeout — continuing anyway")

    # ── Start simulation service (this process, port 8000) ─────
    banner("Starting Simulation Service on port 8000")

    # Add AI dir to path so ai_bridge.py can import detector
    if str(AI_DIR) not in sys.path:
        sys.path.insert(0, str(AI_DIR))
    os.chdir(str(ROOT))

    banner("✅  Both services running", "═")
    print(f"""
  City Live Map      →  http://localhost:8000
  Authority Center   →  http://localhost:8000/authority
  AI Detection API   →  http://localhost:8001
  AI Web UI          →  http://localhost:8001

  Press Ctrl+C to stop.
""")

    # Graceful shutdown
    def _stop(sig, frame):
        print("\n\nStopping services…")
        ai_proc.terminate()
        try:
            ai_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ai_proc.kill()
        print("Stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, loop="asyncio", reload=False)


if __name__ == "__main__":
    main()
