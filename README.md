---
title: Road Safety Simulation AI
emoji: 🚦
colorFrom: orange
colorTo: red
sdk: docker
app_port: 8000
pinned: false
---

# 🚦 Road Safety Simulation + AI Detection

A real-time, city-scale **road safety monitoring platform**. It simulates a live
fleet of buses moving across real Delhi corridors, uses **YOLOv8** computer
vision to detect road hazards, runs every detection through a **multi-authority
emergency-response pipeline**, and streams everything to a **React + Leaflet
command dashboard** over WebSockets.

The entire system — backend, AI, and the built UI — ships as a **single Docker
container**.

<p>
  <img alt="Python"     src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI"    src="https://img.shields.io/badge/FastAPI-WebSockets-009688?logo=fastapi&logoColor=white">
  <img alt="YOLOv8"     src="https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?logo=opencv&logoColor=black">
  <img alt="React"      src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white">
  <img alt="Leaflet"    src="https://img.shields.io/badge/Leaflet-Maps-199900?logo=leaflet&logoColor=white">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [The Dashboard](#the-dashboard)
- [API Reference](#api-reference)
- [Deployment](#deployment)

---

## Overview

Most road-safety systems are reactive — a citizen reports a pothole, an accident
is called in. This project demonstrates a **proactive, sensor-driven** model: a
fleet of connected vehicles continuously scans the road, an AI layer classifies
hazards in real time, and incidents are automatically triaged and dispatched to
the right civic authority — all visualised on a live operations map.

It is built to **scale conceptually from one city to a whole country**: a single
toggle extrapolates the simulation from 100 buses in Delhi → 1,000 across the
NCR → 10,000 nationwide, projecting the throughput and infrastructure load at
each tier.

## Key Features

- 🚌 **Live fleet simulation** — 100 buses moving on 10 real Delhi corridors with
  GPS interpolation, variable speed, and heading.
- 🧠 **Real AI hazard detection** — YOLOv8s + OpenCV classify 8 hazard types
  (pothole, road crack, accident, waterlogging, heavy traffic, fallen tree,
  roadblock, animal crossing) and assign a confidence + severity to each event.
- 🖼️ **Image & demo detection** — upload any road photo or generate a synthetic
  scene and run the same model on it, returning an annotated image + JSON.
- ✅ **Multi-bus verification** — an unverified event is upgraded to
  *partially* then *fully verified* as other buses pass within 65 m, reducing
  false positives.
- 📶 **Network simulation** — each bus has a good / weak / none link driven by a
  Markov chain; offline buses queue events locally and **auto-sync** on
  reconnect.
- 🚨 **Emergency response pipeline** — critical incidents escalate automatically:
  `pending → police → ambulance → road authority → resolved`, each on a timer.
- 🏛️ **Authority operations board** — events are auto-assigned to the relevant
  agency (Police, EMS, PWD Road Authority, Municipal Corp) and flow through a
  `new → acknowledged → in progress → completed` kanban.
- 📊 **Analytics & scalability** — throughput, average confidence, event mix, and
  projected load at 100 / 1,000 / 10,000-bus scale.
- 🤖 **AI Operator Copilot** — a chat assistant (Groq `llama-3.3-70b-versatile`)
  that reads live simulation context and suggests dispatch strategies. The API
  key is held **server-side** via a proxy and never reaches the browser.

## Architecture

```
┌──────────────────────────── Single Docker container ────────────────────────────┐
│                                                                                  │
│   React + Vite + Leaflet UI  ──build──►  static/                                 │
│            │  WebSocket /ws  +  REST /api/*                                       │
│            ▼                                                                      │
│   FastAPI (main.py)                                                              │
│     • Simulation routes        • Authority / work-item routes                    │
│     • Detection routes         • AI Copilot proxy (/api/copilot)                 │
│            │                                                                      │
│     ┌──────┴───────┐                                                              │
│     ▼              ▼                                                              │
│  SimEngine     ai_bridge.py  ──►  roadsafety_ai/  (YOLOv8s + OpenCV detector)     │
│  (simulator.py)   • pre-warmed confidence/severity pool                          │
│   • 100 buses     • run_on_frame / annotate for uploads                          │
│   • events        • synthetic scene generators                                   │
│   • verification                                                                 │
│   • network                  External: Groq API (Copilot, key stays server-side) │
│   • emergency                                                                    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

The frontend is served as a static build by FastAPI, so there is **one origin**
for the UI, the REST API, and the WebSocket — no CORS or separate hosting needed.

## Tech Stack

| Layer        | Technologies |
|--------------|--------------|
| **Backend**  | Python 3.11, FastAPI, Uvicorn, WebSockets |
| **AI / CV**  | Ultralytics YOLOv8s, OpenCV, NumPy |
| **Frontend** | React 19, TypeScript, Vite 6, Tailwind CSS 4 |
| **Mapping**  | Leaflet |
| **Charts**   | Recharts |
| **Copilot**  | Groq API (`llama-3.3-70b-versatile`) via a server-side proxy |
| **Packaging**| Docker (single container), `run.py` one-command launcher |

## Project Structure

```
roadsafety_sim/
├── main.py              # FastAPI app: simulation, detection, authority & copilot routes
├── simulator.py         # SimEngine — buses, events, verification, network, emergencies
├── ai_bridge.py         # Shared AI layer (YOLOv8s + OpenCV) + synthetic scene generators
├── run.py               # One-command launcher (ensures model, serves on :8000)
├── requirements.txt
├── Dockerfile           # Single-container build
├── DEPLOY.md            # Google Cloud Run deploy guide
├── render.yaml          # Render Blueprint (one-click deploy)
├── yolov8s.pt           # YOLOv8s weights
├── roadsafety_ai/       # RoadHazardDetector module (detector.py, models/)
├── frontend/            # React + Vite source
│   ├── src/
│   │   ├── App.tsx          # WebSocket wiring, state, toasts, view routing
│   │   ├── components/      # Header, MapView, KanbanBoard, DetailPanel,
│   │   │                    #   SidebarLive, AnalyticsPanel, CopilotPanel
│   │   ├── data.ts          # REST API client
│   │   └── types.ts
│   └── package.json
├── static/              # Built UI served by FastAPI (+ authority & presentation pages)
└── .env                 # Server-side secrets (GROQ_API_KEY) — gitignored, never committed
```

## Getting Started

### Prerequisites

- Python **3.11+**
- Node.js **18+** (only needed to rebuild the frontend)
- ~2 GB RAM available (YOLOv8s inference)

### Run the whole app (backend serves the prebuilt UI)

```bash
pip install -r requirements.txt
python run.py
```

Then open **http://localhost:8000**. `run.py` verifies the YOLOv8s weights are
present (auto-downloads if missing) and starts the server on port 8000.

> First start loads the model and may take ~20 s. If the model can't load, the
> app automatically falls back to a CV-only / heuristic path so the simulation
> still runs.

### Frontend development (hot reload)

```bash
cd frontend
npm install
npm run dev        # Vite dev server on :3000
```

Rebuild the production UI (output goes to `../static/`, which the backend serves):

```bash
cd frontend
npm run build
```

## Configuration

### AI Copilot (Groq)

The Copilot calls a **server-side proxy** (`/api/copilot`) so the API key is
never shipped to the browser or baked into the bundle. Provide the key in either
of these ways:

```bash
# Option A — environment variable
export GROQ_API_KEY="gsk_your_key_here"

# Option B — gitignored .env in the project root
echo 'GROQ_API_KEY="gsk_your_key_here"' > .env
```

Get a free key at <https://console.groq.com/keys>. Check status at
`GET /api/copilot/status` → `{ "configured": true }`. Without a key, the rest of
the app works fully; only the Copilot tab is disabled.

### Simulation scale

Switch scale at runtime from the sidebar or via `POST /api/scale/{100|1000|10000}`,
and adjust the clock with `POST /api/speed/{0.25–8.0}`.

## How It Works

### Simulation engine (`simulator.py`)

- **Buses** move by linear interpolation between route waypoints; speed and
  heading update every tick (2 s wall-clock, adjustable).
- **Events** are generated on a timer. The event type is weighted (potholes are
  common, accidents rare), and its **confidence + severity come from the AI
  layer** — not random numbers (see below).
- **Verification** — when a *different* bus passes within `65 m` of an open
  event it becomes a verifier; 1 verifier ⇒ *partially verified*, 2+ ⇒ *fully
  verified*.
- **Network** — every bus holds a `good / weak / none` state that transitions via
  a Markov matrix. Events detected while offline queue on the bus and sync when
  the link returns.
- **Emergencies** — events of type `accident`, `fallen_tree`, or `roadblock` at
  high/critical severity trigger the escalation timeline and a live alert.

### AI layer (`ai_bridge.py` + `roadsafety_ai/`)

- Loads `RoadHazardDetector` (YOLOv8s + OpenCV). To keep event generation
  non-blocking, a **background thread pre-warms a pool** of
  `(confidence, severity)` results per hazard type by running the model on
  synthetic road scenes; the simulator pulls from this pool instantly.
- The **same model** powers the upload/demo endpoints (`/api/detect/*`),
  returning real bounding boxes and an annotated image.
- If Ultralytics/YOLO is unavailable, it degrades gracefully to a CV-only
  pothole detector or calibrated fallback ranges.

### Authority pipeline (`main.py`)

Each event type maps to the authorities that can handle it. A background loop
auto-assigns new events, sets a default priority (P1–P4) from type + severity,
and advances work items through `new → acknowledged → in_progress → completed`
on staggered, severity-scaled timers — so the operations board shows realistic
movement. Operators can also act manually (acknowledge, start, complete, assign,
re-prioritise) via the API/UI.

## The Dashboard

| View | What it shows |
|------|---------------|
| **Live Map** | Buses, routes, and events on a Leaflet map; click any event for full detail, timeline, and dispatch controls. |
| **Operations** | Kanban board of incidents per authority, filterable by severity/agency, with acknowledge/complete actions. |
| **Analytics** | Throughput, average AI confidence, event-type mix, and projected load at 1×/10×/100× scale. |
| **Copilot** | Chat assistant grounded in live simulation context, suggesting dispatch and routing strategies. |

## API Reference

> Base URL is the same origin that serves the UI (e.g. `http://localhost:8000`).

### Simulation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/state` | Current world snapshot (buses, events, alerts, stats) |
| `GET`  | `/api/routes` | Route polylines for the active scale |
| `GET`  | `/api/health` | Liveness + counts + `ai_available` |
| `POST` | `/api/scale/{mode}` | Set scale: `100` / `1000` / `10000` |
| `POST` | `/api/speed/{mult}` | Set sim speed (0.25–8.0) |
| `WS`   | `/ws` | Live state stream (broadcast every tick) |

### Events & authorities

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`    | `/api/events/all` | Every live event with assignments + priority |
| `GET`    | `/api/events/{id}` | Full detail for one event |
| `POST`   | `/api/events/{id}/priority/{p1..p4\|none}` | Set manual priority |
| `POST`   | `/api/events/{id}/assign/{authority}` | Assign to an authority |
| `DELETE` | `/api/events/{id}/assign/{authority}` | Remove an assignment |
| `GET`    | `/api/authority/{type}/events` | Work queue for an authority |
| `POST`   | `/api/authority/{type}/work/{id}/{action}` | `acknowledge` / `start` / `complete` / `note` |
| `GET`    | `/api/authority/{type}/stats` | Completion stats |

### Detection & Copilot

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/detect/image` | Upload a road image → detections + annotated JPEG (base64) |
| `GET`  | `/api/detect/sample/{n}` | Run the model on a synthetic scene (1–5) |
| `POST` | `/api/detect/inject` | Inject a detection as a live map event |
| `GET`  | `/api/ai/status` | Model + inference-pool status |
| `GET`  | `/api/copilot/status` | Whether the Copilot key is configured |
| `POST` | `/api/copilot` | Server-side Groq chat proxy (key stays on the server) |

## Deployment

The app is one Docker container that listens on port **8000** and serves the UI,
REST API, and WebSocket together. It needs **~2 GB RAM** for YOLOv8s and a host
that supports **WebSockets** (so serverless/edge platforms like Vercel are not
suitable).

### Hugging Face Spaces (free tier)

This repo includes Space metadata (the front matter above) and a `Dockerfile`.
Create a **Docker Space**, push the repo, and set `GROQ_API_KEY` as a Space
secret. The free CPU hardware (16 GB RAM) comfortably runs the model.

### Google Cloud Run

```bash
gcloud run deploy roadsafety-ai --source . --region asia-south1 \
  --port 8000 --memory 2Gi --cpu 2 --allow-unauthenticated
```

Cloud Run builds the Dockerfile and returns a public HTTPS URL with WebSocket
support. See [DEPLOY.md](DEPLOY.md) for details.

### Render

A `render.yaml` Blueprint is included — create a Blueprint deploy from this repo
and set `GROQ_API_KEY`. Note the model needs the 2 GB (Standard) instance.

### Docker (any host)

```bash
docker build -t roadsafety-sim .
docker run -p 8000:8000 -e GROQ_API_KEY="gsk_..." roadsafety-sim
# → http://localhost:8000
```
