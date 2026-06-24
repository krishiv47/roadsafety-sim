╔══════════════════════════════════════════════════════════╗
║         Road Safety AI System — Quick Start             ║
║         Smart India Hackathon 2025                      ║
╚══════════════════════════════════════════════════════════╝

REQUIREMENTS
  Python 3.10 or higher  (3.11 recommended)

──────────────────────────────────────────────────────────
STEP 1 — Install dependencies  (run once)
──────────────────────────────────────────────────────────

  pip install -r requirements.txt

──────────────────────────────────────────────────────────
STEP 2 — Launch everything
──────────────────────────────────────────────────────────

  python run.py

  The script will:
    • Auto-download the YOLOv8s model on first run (~22 MB)
    • Start AI Detection service  → http://localhost:8001
    • Start Simulation service    → http://localhost:8000

──────────────────────────────────────────────────────────
STEP 3 — Open your browser
──────────────────────────────────────────────────────────

  City Live Map      →  http://localhost:8000
  Authority Center   →  http://localhost:8000/authority
  AI Detection UI    →  http://localhost:8001

  Press Ctrl+C in the terminal to stop.

──────────────────────────────────────────────────────────
TRAIN YOUR OWN POTHOLE MODEL (optional)
──────────────────────────────────────────────────────────

  python roadsafety_ai/train.py --data /path/to/data.yaml --epochs 100

  After training, the model is saved to roadsafety_ai/models/pothole.pt
  Restart run.py — it picks up the fine-tuned model automatically.

  Classes supported: pothole | road_crack | debris | flooding

──────────────────────────────────────────────────────────
FOLDER STRUCTURE
──────────────────────────────────────────────────────────

  RoadSafetyAI/
  ├── run.py               ← start here
  ├── requirements.txt
  ├── main.py              ← simulation + dashboards (port 8000)
  ├── simulator.py         ← 100-bus Delhi simulation engine
  ├── ai_bridge.py         ← shared AI layer
  ├── static/
  │   ├── index.html       ← city live map
  │   ├── authority.html   ← authority command center
  │   └── presentation.html
  └── roadsafety_ai/       ← AI detection service (port 8001)
      ├── detector.py      ← YOLOv8s + OpenCV pipeline
      ├── train.py         ← fine-tune on your own dataset
      └── models/          ← place pothole.pt here after training

──────────────────────────────────────────────────────────
