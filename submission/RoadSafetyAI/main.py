"""
Road Safety Simulation — FastAPI Server v2
AI layer unified through ai_bridge.py — same YOLOv8s model used by
simulation event generation AND the demo/upload detection endpoints.
"""
import asyncio
import base64
import io
import json
import time
import random
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import cv2

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from simulator import SimEngine

# ── Shared AI bridge (same detector instance as simulator) ────
from ai_bridge import bridge as _ai_bridge, DEMO_SCENES, SCENE_GENERATORS

AI_AVAILABLE = _ai_bridge.available

# ── Simulation engine ────────────────────────────────────────
engine = SimEngine()

# ── Authority work-item tracking ─────────────────────────────
# Maps event types to the authority responsible for handling them
_AUTHORITY_EVENTS: dict[str, set] = {
    "police":         {"accident", "roadblock", "heavy_traffic"},
    "ambulance":      {"accident"},
    "road_authority": {"pothole", "road_crack", "fallen_tree", "roadblock", "waterlogging"},
    "municipal":      {"waterlogging", "animal_crossing", "pothole", "road_crack"},
}
_AUTHORITY_META: dict[str, dict] = {
    "police":         {"label": "Delhi Police",            "icon": "🚔", "color": "#3b82f6"},
    "ambulance":      {"label": "Emergency Medical (EMS)", "icon": "🚑", "color": "#ef4444"},
    "road_authority": {"label": "PWD Road Authority",      "icon": "🚧", "color": "#f97316"},
    "municipal":      {"label": "Municipal Corporation",   "icon": "🏙️", "color": "#22c55e"},
}
# Persistent work item state: { (event_id, authority) : {status, ts_assigned, ts_updated, notes} }
_work_items: dict[tuple, dict] = {}

# Manual priority overrides: { event_id : "p1" | "p2" | "p3" | "p4" }
_event_priorities: dict[str, str] = {}

# Track which events have been auto-assigned (avoid re-processing)
_auto_assigned: set[str] = set()


def _default_priority(etype: str, severity: str) -> str:
    """Derive a sensible default priority from event type + AI severity."""
    if severity == "critical":                        return "p1"
    if severity == "high" and etype in ("accident","fallen_tree","roadblock"): return "p1"
    if severity == "high":                            return "p2"
    if severity == "medium" and etype == "accident":  return "p2"
    if severity == "medium":                          return "p3"
    return "p4"


async def _auto_assign_loop():
    """
    Background task: within 2 s of a new event being created,
    auto-assign it to every eligible authority and set a default priority.
    Runs forever alongside engine.run().
    """
    while True:
        await asyncio.sleep(2)
        now = time.time()
        for ev in list(engine.events.values()):
            if ev.event_id in _auto_assigned:
                continue
            # Assign to all eligible authorities for this event type
            assigned_labels = []
            for auth, types in _AUTHORITY_EVENTS.items():
                if ev.etype not in types:
                    continue
                key = (ev.event_id, auth)
                if key not in _work_items:
                    _work_items[key] = {
                        "status":      "new",
                        "ts_assigned": now,
                        "ts_updated":  now,
                        "notes":       "",
                    }
                    assigned_labels.append(_AUTHORITY_META[auth]["label"])

            if assigned_labels:
                _auto_assigned.add(ev.event_id)
                ev.timeline.append({
                    "ts":  now,
                    "msg": f"📋 Auto-assigned → {', '.join(assigned_labels)}",
                })
                # Set default priority if not already set
                if ev.event_id not in _event_priorities:
                    pri = _default_priority(ev.etype, ev.severity)
                    _event_priorities[ev.event_id] = pri
                    ev.timeline.append({
                        "ts":  now,
                        "msg": f"🎯 Default priority: {pri.upper()} ({ev.severity})",
                    })

        # Prune expired IDs so the set stays small
        _auto_assigned.intersection_update(engine.events.keys())


@asynccontextmanager
async def lifespan(app: FastAPI):
    task1 = asyncio.create_task(engine.run())
    task2 = asyncio.create_task(_auto_assign_loop())
    yield
    for t in (task1, task2):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Road Safety Simulation + Detection", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

if Path("static").exists():
    # Serve built React assets (JS/CSS bundles, fonts etc.)
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


# ════════════════════════════════════════════════════════════
# Simulation routes
# ════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    p = Path("static/index.html")
    return p.read_text() if p.exists() else "<h1>Road Safety Sim</h1>"


# SPA catch-all: any unknown GET that isn't an API/WS route returns index.html
# so React Router (if used) or hard refresh on /authority-style paths still work.
@app.get("/app/{rest_of_path:path}", response_class=HTMLResponse)
async def spa_catchall(rest_of_path: str):
    p = Path("static/index.html")
    return p.read_text() if p.exists() else "<h1>Road Safety Sim</h1>"


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    engine._ws_clients.add(ws)
    try:
        await ws.send_text(json.dumps(engine.get_state(), default=str))
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=45.0)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        engine._ws_clients.discard(ws)


@app.get("/api/state")
async def api_state():
    return JSONResponse(engine.get_state(), media_type="application/json")


@app.get("/api/routes")
async def api_routes():
    return JSONResponse({"routes": engine.get_routes()})


@app.post("/api/scale/{mode}")
async def api_scale(mode: int):
    engine.set_scale(mode)
    return {"ok": True, "scale": mode}


@app.post("/api/speed/{mult}")
async def api_speed(mult: float):
    engine.set_speed(mult)
    return {"ok": True, "speed": engine.speed_mult}


@app.get("/api/health")
async def api_health():
    s = engine.get_state().get("stats", {})
    return {
        "status":       "running",
        "uptime_s":     s.get("uptime_s", 0),
        "buses":        s.get("total_buses", 0),
        "events":       s.get("total_events", 0),
        "ws_clients":   len(engine._ws_clients),
        "ai_available": AI_AVAILABLE,
    }


# ════════════════════════════════════════════════════════════
# AI Detection routes
# ════════════════════════════════════════════════════════════

@app.get("/authority", response_class=HTMLResponse)
async def authority_page():
    p = Path("static/authority.html")
    return p.read_text() if p.exists() else "<h1>Authority Dashboard</h1>"


@app.get("/presentation", response_class=HTMLResponse)
async def presentation_page():
    p = Path("static/presentation.html")
    return p.read_text() if p.exists() else "<h1>Presentation</h1>"


@app.get("/presentation/download")
async def presentation_download():
    from fastapi.responses import FileResponse
    p = Path("static/presentation.pdf")
    if not p.exists():
        raise HTTPException(404, "PDF not generated yet")
    return FileResponse(p, media_type="application/pdf",
                        filename="RoadSafety_AI_Presentation.pdf")


# ════════════════════════════════════════════════════════════
# Authority dashboard routes
# ════════════════════════════════════════════════════════════

@app.get("/api/authority/meta")
async def authority_meta():
    return JSONResponse(_AUTHORITY_META)


@app.get("/api/authority/{auth_type}/events")
async def authority_events(auth_type: str):
    """Return all current events assigned to this authority, with work status."""
    if auth_type not in _AUTHORITY_EVENTS:
        raise HTTPException(404, f"Unknown authority: {auth_type}")

    relevant_types = _AUTHORITY_EVENTS[auth_type]
    now = time.time()
    items = []

    for ev in engine.events.values():
        if ev.etype not in relevant_types:
            continue
        key = (ev.event_id, auth_type)
        wi  = _work_items.get(key)
        status = wi["status"] if wi else "new"
        items.append({
            "event_id":    ev.event_id,
            "type":        ev.etype,
            "icon":        ev.to_dict()["icon"],
            "lat":         ev.lat,
            "lng":         ev.lng,
            "severity":    ev.severity,
            "confidence":  round(ev.confidence, 2),
            "detected_by": ev.detected_by,
            "age_s":       round(now - ev.ts),
            "verification":ev.verification,
            "emergency":   ev.emergency,
            "timeline":    ev.timeline[-4:],
            "work_status": status,
            "ts_assigned": wi["ts_assigned"] if wi else ev.ts,
            "ts_updated":  wi["ts_updated"]  if wi else None,
            "notes":       wi.get("notes","") if wi else "",
        })

    # Sort: new first, then by severity
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    status_order = {"new": 0, "acknowledged": 1, "in_progress": 2, "completed": 3}
    items.sort(key=lambda x: (status_order[x["work_status"]], sev_order.get(x["severity"], 9)))

    counts = {"new": 0, "acknowledged": 0, "in_progress": 0, "completed": 0}
    for it in items:
        counts[it["work_status"]] = counts.get(it["work_status"], 0) + 1

    meta = _AUTHORITY_META[auth_type]
    return JSONResponse({
        "authority":  auth_type,
        "label":      meta["label"],
        "icon":       meta["icon"],
        "color":      meta["color"],
        "items":      items,
        "counts":     counts,
        "total":      len(items),
    })


@app.post("/api/authority/{auth_type}/work/{event_id}/{action}")
async def authority_work_action(auth_type: str, event_id: str, action: str,
                                 payload: dict = None):
    """
    Update work status for an event.
    action: acknowledge | start | complete | note
    """
    if auth_type not in _AUTHORITY_EVENTS:
        raise HTTPException(404, "Unknown authority")
    if action not in ("acknowledge", "start", "complete", "note"):
        raise HTTPException(400, "Unknown action")

    ev = engine.events.get(event_id)
    if not ev:
        raise HTTPException(404, "Event not found (may have expired)")

    if ev.etype not in _AUTHORITY_EVENTS[auth_type]:
        raise HTTPException(403, "This event type is not assigned to your authority")

    key = (event_id, auth_type)
    now = time.time()

    status_map = {
        "acknowledge": "acknowledged",
        "start":       "in_progress",
        "complete":    "completed",
    }

    if action == "note":
        notes = (payload or {}).get("notes", "")
        if key not in _work_items:
            _work_items[key] = {"status": "acknowledged", "ts_assigned": ev.ts,
                                 "ts_updated": now, "notes": notes}
        else:
            _work_items[key]["notes"] = notes
            _work_items[key]["ts_updated"] = now
    else:
        new_status = status_map[action]
        if key not in _work_items:
            _work_items[key] = {"status": new_status, "ts_assigned": ev.ts,
                                 "ts_updated": now, "notes": ""}
        else:
            _work_items[key]["status"] = new_status
            _work_items[key]["ts_updated"] = now

        # Append to event timeline
        action_msgs = {
            "acknowledge": f"👀 {_AUTHORITY_META[auth_type]['label']} acknowledged",
            "start":       f"🔧 {_AUTHORITY_META[auth_type]['label']} started work on-site",
            "complete":    f"✅ {_AUTHORITY_META[auth_type]['label']} marked resolved",
        }
        ev.timeline.append({"ts": now, "msg": action_msgs[action]})

    return {"ok": True, "event_id": event_id, "status": _work_items[key]["status"]}


@app.get("/api/authority/{auth_type}/stats")
async def authority_stats(auth_type: str):
    """Completion stats for the authority's work today."""
    if auth_type not in _AUTHORITY_EVENTS:
        raise HTTPException(404, "Unknown authority")

    relevant = _AUTHORITY_EVENTS[auth_type]
    total_events = sum(1 for e in engine.events.values() if e.etype in relevant)

    wi_for_auth = {k: v for k, v in _work_items.items() if k[1] == auth_type}
    completed = sum(1 for v in wi_for_auth.values() if v["status"] == "completed")
    in_prog   = sum(1 for v in wi_for_auth.values() if v["status"] == "in_progress")
    acked     = sum(1 for v in wi_for_auth.values() if v["status"] == "acknowledged")

    return JSONResponse({
        "total_events": total_events,
        "completed":    completed,
        "in_progress":  in_prog,
        "acknowledged": acked,
        "new":          max(0, total_events - completed - in_prog - acked),
        "rate":         round(completed / max(total_events, 1) * 100, 1),
    })


# ════════════════════════════════════════════════════════════
# All-events & priority/assignment endpoints
# ════════════════════════════════════════════════════════════

@app.get("/api/events/all")
async def all_events():
    """
    Return every live simulation event with:
    - manual priority (p1-p4)
    - work status per authority that has been assigned
    - which authority types it CAN be assigned to (based on event type)
    """
    now   = time.time()
    items = []

    for ev in sorted(engine.events.values(), key=lambda e: e.ts, reverse=True):
        ev_dict = ev.to_dict()

        # Which authorities can handle this event type
        eligible = [
            auth for auth, types in _AUTHORITY_EVENTS.items()
            if ev.etype in types
        ]

        # Work items for this event across all authorities
        assignments = {}
        for auth in eligible:
            key = (ev.event_id, auth)
            wi  = _work_items.get(key)
            assignments[auth] = {
                "assigned": wi is not None,
                "status":   wi["status"] if wi else None,
                "ts_updated": wi["ts_updated"] if wi else None,
                "notes":    wi.get("notes", "") if wi else "",
                "meta":     _AUTHORITY_META[auth],
            }

        # Overall status: worst-case across assignments
        statuses = [v["status"] for v in assignments.values() if v["assigned"]]
        if not statuses:
            overall = "unassigned"
        elif "in_progress" in statuses:
            overall = "in_progress"
        elif all(s == "completed" for s in statuses):
            overall = "completed"
        elif "acknowledged" in statuses:
            overall = "acknowledged"
        else:
            overall = "new"

        items.append({
            **ev_dict,
            "eligible_authorities": eligible,
            "assignments":          assignments,
            "overall_status":       overall,
            "priority":             _event_priorities.get(ev.event_id, None),
            "age_s":                round(now - ev.ts),
        })

    # Count summary
    from collections import Counter
    status_counts = Counter(i["overall_status"] for i in items)
    sev_counts    = Counter(i["severity"]        for i in items)
    pri_counts    = Counter(i["priority"] or "none" for i in items)

    return JSONResponse({
        "events": items,
        "total":  len(items),
        "status_counts": dict(status_counts),
        "sev_counts":    dict(sev_counts),
        "pri_counts":    dict(pri_counts),
    })


@app.get("/api/events/{event_id}")
async def get_single_event(event_id: str):
    """Full detail for one event — assignments, priority, complete timeline."""
    ev = engine.events.get(event_id)
    if not ev:
        raise HTTPException(404, "Event not found (may have expired)")

    now = time.time()
    eligible = [a for a, types in _AUTHORITY_EVENTS.items() if ev.etype in types]
    assignments = {}
    for auth in eligible:
        key = (ev.event_id, auth)
        wi  = _work_items.get(key)
        assignments[auth] = {
            "assigned":   wi is not None,
            "status":     wi["status"]      if wi else None,
            "ts_updated": wi["ts_updated"]  if wi else None,
            "notes":      wi.get("notes","") if wi else "",
            "meta":       _AUTHORITY_META[auth],
        }

    statuses = [v["status"] for v in assignments.values() if v["assigned"]]
    if not statuses:
        overall = "unassigned"
    elif "in_progress" in statuses:
        overall = "in_progress"
    elif all(s == "completed" for s in statuses):
        overall = "completed"
    elif "acknowledged" in statuses:
        overall = "acknowledged"
    else:
        overall = "new"

    return JSONResponse({
        **ev.to_dict(),
        "eligible_authorities": eligible,
        "assignments":          assignments,
        "overall_status":       overall,
        "priority":             _event_priorities.get(event_id),
        "age_s":                round(now - ev.ts),
        "full_timeline":        ev.timeline,        # all entries, not just last 6
    })


@app.post("/api/events/{event_id}/priority/{level}")
async def set_priority(event_id: str, level: str):
    """Set manual priority for an event. level = p1 | p2 | p3 | p4 | none"""
    if level not in ("p1", "p2", "p3", "p4", "none"):
        raise HTTPException(400, "level must be p1/p2/p3/p4/none")
    if event_id not in engine.events:
        raise HTTPException(404, "Event not found")
    if level == "none":
        _event_priorities.pop(event_id, None)
    else:
        _event_priorities[event_id] = level
    ev = engine.events[event_id]
    label = {"p1":"P1 CRITICAL","p2":"P2 HIGH","p3":"P3 MEDIUM","p4":"P4 LOW"}.get(level, level)
    ev.timeline.append({"ts": time.time(), "msg": f"🎯 Priority set to {label}"})
    return {"ok": True, "event_id": event_id, "priority": level}


@app.post("/api/events/{event_id}/assign/{auth_type}")
async def assign_event(event_id: str, auth_type: str):
    """
    Manually assign an event to an authority.
    Creates a 'new' work item if one doesn't exist.
    """
    if auth_type not in _AUTHORITY_EVENTS:
        raise HTTPException(404, "Unknown authority")
    ev = engine.events.get(event_id)
    if not ev:
        raise HTTPException(404, "Event not found")

    key = (event_id, auth_type)
    now = time.time()
    if key not in _work_items:
        _work_items[key] = {
            "status":      "new",
            "ts_assigned": now,
            "ts_updated":  now,
            "notes":       "",
        }
        meta = _AUTHORITY_META[auth_type]
        ev.timeline.append({
            "ts":  now,
            "msg": f"📋 Manually assigned to {meta['label']}",
        })
    return {"ok": True, "event_id": event_id, "auth": auth_type,
            "status": _work_items[key]["status"]}


@app.delete("/api/events/{event_id}/assign/{auth_type}")
async def unassign_event(event_id: str, auth_type: str):
    """Remove an assignment (work item) for an event+authority pair."""
    key = (event_id, auth_type)
    _work_items.pop(key, None)
    ev = engine.events.get(event_id)
    if ev:
        meta = _AUTHORITY_META.get(auth_type, {})
        ev.timeline.append({
            "ts":  time.time(),
            "msg": f"🗑️ Unassigned from {meta.get('label', auth_type)}",
        })
    return {"ok": True}


@app.post("/api/detect/image")
async def detect_image(file: UploadFile = File(...)):
    """Upload any road image → YOLOv8s + CV detection → JSON + annotated JPEG (base64)."""
    data  = await file.read()
    frame = _decode_img(data)
    return JSONResponse(_run_detection(frame))


@app.get("/api/detect/sample/{n}")
async def detect_sample(n: int):
    """
    Generate a synthetic road scene (1-5) and run real AI detection on it.
    Scene map:
      1 = pothole-heavy road
      2 = traffic light (RED) — YOLOv8 detects this reliably
      3 = accident (overlapping vehicles + pedestrian)
      4 = waterlogging
      5 = heavy traffic jam
    """
    idx   = (n - 1) % len(DEMO_SCENES)
    name, gen_fn = DEMO_SCENES[idx]
    frame  = gen_fn()
    result = _run_detection(frame)
    result["scene"]      = n
    result["scene_name"] = name
    return JSONResponse(result)


@app.get("/api/ai/status")
async def ai_status():
    """Return AI bridge status — model loaded, pool sizes, inference count."""
    return JSONResponse(_ai_bridge.status)


@app.post("/api/detect/inject")
async def detect_inject(payload: dict):
    """
    Inject a detection result as a real simulation event at the nearest bus location.
    Body: { event_type, severity, confidence, lat (optional), lng (optional) }
    """
    import time as _t
    buses = list(engine.buses.values())
    if not buses:
        raise HTTPException(503, "No buses in simulation")

    bus  = random.choice(buses)
    lat  = float(payload.get("lat", bus.lat)) + random.gauss(0, 0.0003)
    lng  = float(payload.get("lng", bus.lng)) + random.gauss(0, 0.0003)
    eid  = f"DET-{engine._evt_ctr:05d}"
    engine._evt_ctr += 1

    from simulator import Event, CRITICAL
    etype = payload.get("event_type", "pothole")
    sev   = payload.get("severity", "medium")
    conf  = float(payload.get("confidence", 0.80))

    ev = Event(
        event_id   = eid,
        etype      = etype,
        lat        = round(lat, 6),
        lng        = round(lng, 6),
        confidence = conf,
        severity   = sev,
        detected_by= f"{bus.bus_id} [AI-CAM]",
        ts         = _t.time(),
    )
    ev.timeline.append({
        "ts":  ev.ts,
        "msg": f"🤖 AI-detected {etype} from dashcam (conf {conf:.0%}) — injected by {bus.bus_id}"
    })

    if etype in CRITICAL and sev in ("high", "critical"):
        ev.emergency = "pending"
        ev.emg_ts    = ev.ts
        ev.timeline.append({"ts": ev.ts, "msg": "🚨 CRITICAL — Emergency protocol activated"})
        from collections import deque
        engine.alerts.appendleft({
            "ts": ev.ts, "level": "critical", "type": etype,
            "event_id": eid, "bus": bus.bus_id, "lat": lat, "lng": lng,
            "severity": sev,
            "msg": f"🚨 AI-CAM: {etype.replace('_',' ').upper()} detected & injected → map"
        })

    engine.events[eid] = ev
    return {"ok": True, "event_id": eid, "bus": bus.bus_id, "lat": lat, "lng": lng}


@app.post("/api/detect/image/annotated")
async def detect_image_raw(file: UploadFile = File(...)):
    """Returns the annotated JPEG directly (for display)."""
    data  = await file.read()
    frame = _decode_img(data)
    ann   = _annotate_frame(frame)
    _, buf = cv2.imencode(".jpg", ann, [cv2.IMWRITE_JPEG_QUALITY, 90])
    import io
    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/jpeg")


# ════════════════════════════════════════════════════════════
# Internal helpers
# ════════════════════════════════════════════════════════════

_ICON_MAP = {
    "pothole":       "🕳️",
    "accident":      "🚗",
    "traffic_light": "🚦",
    "pedestrian":    "🚶",
    "damage":        "〰️",
    "obstacle":      "🚧",
    "vehicle":       "🚙",
}


def _decode_img(data: bytes) -> np.ndarray:
    arr   = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Could not decode image")
    return frame


def _run_detection(frame: np.ndarray) -> dict:
    """
    Run AI detection via ai_bridge (YOLOv8s + CV) and return a JSON-safe dict.
    Falls back to CV-only pothole detection when YOLO is unavailable.
    """
    result = _ai_bridge.run_on_frame(frame)

    if result is not None:
        # Full AI path
        annotated = _ai_bridge.annotate_frame(frame, result)
        dets      = [d.to_dict() for d in result.detections]
        traffic   = result.traffic if isinstance(result.traffic, dict) else (
                        result.traffic.to_dict() if result.traffic else None)
        model_used = _ai_bridge.model_name
    else:
        # CV-only fallback: run pothole detector without YOLO
        pots = _ai_bridge.cv_pothole_only(frame)
        h, w = frame.shape[:2]
        for d in pots:
            d.bbox = [round(d.bbox[0] / w, 4), round(d.bbox[1] / h, 4),
                      round(d.bbox[2] / w, 4), round(d.bbox[3] / h, 4)]
        annotated  = frame.copy()
        dets       = [d.to_dict() for d in pots]
        traffic    = None
        model_used = "CV fallback"

    for d in dets:
        d["icon"] = _ICON_MAP.get(d.get("category", ""), "📍")

    _, buf      = cv2.imencode(".jpg", annotated,  [cv2.IMWRITE_JPEG_QUALITY, 88])
    _, orig_buf = cv2.imencode(".jpg", frame,      [cv2.IMWRITE_JPEG_QUALITY, 85])

    return {
        "detections":    dets,
        "traffic":       traffic,
        "annotated_b64": base64.b64encode(buf.tobytes()).decode(),
        "original_b64":  base64.b64encode(orig_buf.tobytes()).decode(),
        "model":         model_used,
        "ai_available":  AI_AVAILABLE,
        "det_count":     len(dets),
        "summary": {
            "potholes":  sum(1 for d in dets if d["category"] == "pothole"),
            "accidents": sum(1 for d in dets if d["category"] == "accident"),
            "lights":    sum(1 for d in dets if d["category"] == "traffic_light"),
            "peds":      sum(1 for d in dets if d["category"] == "pedestrian"),
            "critical":  sum(1 for d in dets if d["severity"] == "critical"),
        },
    }


def _annotate_frame(frame: np.ndarray) -> np.ndarray:
    result = _ai_bridge.run_on_frame(frame)
    if result is None:
        return frame
    return _ai_bridge.annotate_frame(frame, result)
