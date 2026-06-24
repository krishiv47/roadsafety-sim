"""
Road Hazard AI v2 — FastAPI server
Endpoints:
  POST /detect/image            → JSON: detections + traffic analysis
  POST /detect/image/annotated  → annotated JPEG
  POST /detect/video            → JSON: per-frame detections + traffic + motion
  GET  /health                  → model status
  GET  /                        → web UI
"""
import io
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from detector import RoadHazardDetector
from video_processor import VideoProcessor

# ---------------------------------------------------------------------------
app = FastAPI(title="Road Hazard AI", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

POTHOLE_MODEL = Path("models/pothole.pt")
detector  = RoadHazardDetector(
    pothole_model_path=str(POTHOLE_MODEL) if POTHOLE_MODEL.exists() else None
)
video_proc = VideoProcessor(detector)

if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    ui = Path("static/index.html")
    return ui.read_text() if ui.exists() else "<h1>Road Hazard AI v2</h1>"


@app.get("/health")
async def health():
    return {
        "status":        "ok",
        "version":       "2.0",
        "model":         f"YOLOv8s ({'+ pothole.pt' if detector.has_pothole_model else 'CV fallback'})",
        "capabilities":  ["pothole", "accident", "traffic_density",
                          "traffic_light_state", "pedestrian", "optical_flow"],
    }


@app.post("/detect/image")
async def detect_image(file: UploadFile = File(...)):
    _require_image(file)
    frame  = _decode_upload(await file.read())
    result = detector.detect_full(frame)

    return JSONResponse({
        "filename":   file.filename,
        "image_size": {"width": frame.shape[1], "height": frame.shape[0]},
        "detections": [d.to_dict() for d in result.detections],
        "traffic":    result.traffic,
        "summary":    _summary(result),
    })


@app.post("/detect/image/annotated")
async def detect_image_annotated(
    file: UploadFile = File(...),
    quality: int = Query(default=90, ge=10, le=100),
):
    _require_image(file)
    frame  = _decode_upload(await file.read())
    result = detector.detect_full(frame)
    img    = detector.annotate(frame, result)

    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return StreamingResponse(io.BytesIO(buf.tobytes()), media_type="image/jpeg")


@app.post("/detect/video")
async def detect_video(
    file: UploadFile = File(...),
    sample_rate: int = Query(default=5, ge=1, le=30),
):
    if not (file.content_type or "").startswith("video/"):
        raise HTTPException(400, "File must be a video (mp4, avi, mov, …)")

    data   = await file.read()
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        frames_out = []
        for res in video_proc.process_video(tmp_path, sample_rate=sample_rate):
            frames_out.append({
                "frame":        res.frame_number,
                "timestamp_s":  res.timestamp,
                "motion_score": res.motion_score,
                "detections":   [d.to_dict() for d in res.detections],
                "traffic":      res.traffic,
                "summary":      _summary(res),
            })

        hazard_frames = [f for f in frames_out if f["detections"]]
        all_dets = [d for f in hazard_frames for d in f["detections"]]

        return JSONResponse({
            "filename":           file.filename,
            "sample_rate":        sample_rate,
            "total_frames_scanned": len(frames_out),
            "frames_with_hazards": len(hazard_frames),
            "overall_summary":    _summary_dicts(all_dets),
            "peak_traffic":       _peak_traffic(frames_out),
            "results":            hazard_frames,
        })
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_image(file: UploadFile):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "File must be an image (jpg, png, …)")


def _decode_upload(data: bytes) -> np.ndarray:
    arr   = np.frombuffer(data, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Could not decode image")
    return frame


def _summary(result) -> dict:
    dets = result.detections
    return {
        "total":      len(dets),
        "potholes":   sum(1 for d in dets if d.category == "pothole"),
        "accidents":  sum(1 for d in dets if d.category == "accident"),
        "pedestrians":sum(1 for d in dets if d.category == "pedestrian"),
        "critical":   sum(1 for d in dets if d.severity == "critical"),
        "high":       sum(1 for d in dets if d.severity == "high"),
    }


def _summary_dicts(dets: list) -> dict:
    return {
        "total":      len(dets),
        "potholes":   sum(1 for d in dets if d["category"] == "pothole"),
        "accidents":  sum(1 for d in dets if d["category"] == "accident"),
        "pedestrians":sum(1 for d in dets if d["category"] == "pedestrian"),
        "critical":   sum(1 for d in dets if d["severity"] == "critical"),
        "high":       sum(1 for d in dets if d["severity"] == "high"),
    }


def _peak_traffic(frames: list) -> dict:
    if not frames:
        return {}
    peak = max(frames, key=lambda f: (f["traffic"] or {}).get("vehicle_count", 0))
    return {
        "frame":         peak["frame"],
        "timestamp_s":   peak["timestamp_s"],
        "vehicle_count": (peak["traffic"] or {}).get("vehicle_count", 0),
        "density":       (peak["traffic"] or {}).get("density", "low"),
    }
