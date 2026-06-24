#!/usr/bin/env bash
# =====================================================================
#  Road Safety AI System — One-shot Setup & Launch
#  Tested on macOS and Ubuntu/Debian Linux
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
SIM="$ROOT/roadsafety_sim"
AI="$ROOT/roadsafety_ai"

echo ""
echo "============================================================"
echo "  Road Safety AI System — Setup"
echo "============================================================"
echo ""

# ── 1. Check Python version ──────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PY_VER found at $PYTHON"

# ── 2. Install dependencies ──────────────────────────────────────
echo ""
echo "Installing roadsafety_ai dependencies..."
cd "$AI"
$PYTHON -m pip install -r requirements.txt -q

echo "Installing roadsafety_sim dependencies..."
cd "$SIM"
$PYTHON -m pip install -r requirements.txt -q

# ── 3. Check YOLOv8 model ────────────────────────────────────────
MODEL="$AI/yolov8s.pt"
if [ ! -f "$MODEL" ]; then
    echo ""
    echo "⬇️  Downloading YOLOv8s model (~22 MB)..."
    $PYTHON -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"
    # ultralytics downloads to ~/.cache — copy it here
    CACHE_PT=$(find ~/.cache/ultralytics -name 'yolov8s.pt' 2>/dev/null | head -1)
    if [ -z "$CACHE_PT" ]; then
        CACHE_PT=$(find ~/.config -name 'yolov8s.pt' 2>/dev/null | head -1)
    fi
    if [ -n "$CACHE_PT" ]; then
        cp "$CACHE_PT" "$MODEL"
        echo "✅ Model saved to $MODEL"
    else
        echo "⚠️  Could not auto-locate downloaded model."
        echo "   Manually copy yolov8s.pt to: $MODEL"
    fi
else
    echo "✅ YOLOv8s model found"
fi

# ── 4. Launch both services ──────────────────────────────────────
echo ""
echo "============================================================"
echo "  Launching services..."
echo "  AI Service  → http://localhost:8001"
echo "  Simulation  → http://localhost:8000"
echo "  Press Ctrl+C to stop both"
echo "============================================================"
echo ""

# Start AI service in background
cd "$AI"
$PYTHON start.py &
AI_PID=$!

sleep 3   # Give AI service time to load YOLOv8

# Start simulation service in foreground
cd "$SIM"
$PYTHON start.py

# Cleanup on exit
kill $AI_PID 2>/dev/null
echo "Services stopped."
