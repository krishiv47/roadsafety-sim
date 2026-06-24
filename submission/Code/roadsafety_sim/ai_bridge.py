"""
AI Bridge — shared AI layer for roadsafety_sim
===============================================
• Loads RoadHazardDetector (YOLOv8s + OpenCV) from roadsafety_ai
• Pre-warms a per-event-type result pool in a background thread
• Exposes get_result(event_type) → (confidence, severity) for the simulator
• Exposes run_on_frame / annotate_frame for the API endpoints
• Provides all scene generators used by both simulation and demo endpoints
• Falls back gracefully when roadsafety_ai is unavailable
"""

import sys
import os
import random
import threading
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

# ─────────────────────────────────────────────────────────────
# Detector bootstrap
# ─────────────────────────────────────────────────────────────

# Check both layouts:
#   dev layout:        roadsafety_sim/roadsafety_ai/   (roadsafety_ai nested inside)
#   submission layout: roadsafety_ai/  alongside  roadsafety_sim/  (siblings)
_AI_DIR = Path(__file__).parent / "roadsafety_ai"
if not _AI_DIR.exists():
    _AI_DIR = Path(__file__).parent.parent / "roadsafety_ai"


def _load_detector():
    """Load RoadHazardDetector from the roadsafety_ai project (any layout)."""
    if not _AI_DIR.exists():
        print(f"[AI Bridge] roadsafety_ai not found (checked {Path(__file__).parent / 'roadsafety_ai'} "
              f"and {Path(__file__).parent.parent / 'roadsafety_ai'})")
        return None, False
    if str(_AI_DIR) not in sys.path:
        sys.path.insert(0, str(_AI_DIR))
    try:
        from detector import RoadHazardDetector  # type: ignore
        model_path = _AI_DIR / "models" / "pothole.pt"
        det = RoadHazardDetector(
            pothole_model_path=str(model_path) if model_path.exists() else None,
            model_size="s",   # always use yolov8s — same as roadsafety_ai
        )
        print(f"[AI Bridge] ✅ YOLOv8s loaded — pothole model: {det.has_pothole_model}"
              + (f" | classes: {list(det._pothole_names.values())}" if det.has_pothole_model else ""))
        return det, True
    except Exception as exc:
        print(f"[AI Bridge] ⚠  Could not load detector: {exc}")
        return None, False


# ─────────────────────────────────────────────────────────────
# Fallback confidence/severity ranges (when AI is unavailable)
# ─────────────────────────────────────────────────────────────

_FALLBACK: dict[str, Tuple[Tuple[float, float], list]] = {
    "pothole":         ((0.68, 0.84), ["low", "medium", "high"]),
    "road_crack":      ((0.62, 0.80), ["low", "medium"]),
    "accident":        ((0.70, 0.92), ["high", "critical"]),
    "waterlogging":    ((0.75, 0.91), ["medium", "high"]),
    "heavy_traffic":   ((0.60, 0.78), ["low", "medium", "high"]),
    "fallen_tree":     ((0.65, 0.85), ["high", "critical"]),
    "roadblock":       ((0.68, 0.88), ["medium", "high"]),
    "animal_crossing": ((0.60, 0.76), ["low", "medium"]),
}

# Map sim event type → AI detection category to match against.
# Base mapping covers both the CV fallback and the base YOLOv8s.
# When a fine-tuned pothole model is loaded, _update_type_map() refines these
# using the model's actual class names (road_crack, flooding, debris …).
_TYPE_TO_CAT: dict[str, Optional[str]] = {
    "pothole":         "pothole",
    "road_crack":      "pothole",     # fine-tuned model also sets category="pothole" for cracks
    "accident":        "accident",
    "waterlogging":    "obstacle",    # fine-tuned "flooding" class uses category="obstacle"
    "heavy_traffic":   None,          # derive from traffic density score
    "fallen_tree":     "obstacle",
    "roadblock":       "obstacle",
    "animal_crossing": "pedestrian",
}

# Fine-tuned model class name → sim event type it helps detect
_POTHOLE_CLASS_TO_EVENT: dict[str, str] = {
    "pothole":      "pothole",
    "road_crack":   "road_crack",
    "crack":        "road_crack",
    "debris":       "roadblock",
    "flooding":     "waterlogging",
    "waterlogging": "waterlogging",
}


def _update_type_map(det) -> None:
    """
    After loading the fine-tuned pothole model, check which classes it knows about
    and print a summary — _TYPE_TO_CAT already handles them correctly via categories.
    """
    names = getattr(det, "_pothole_names", {})
    if not names:
        return
    mapped = {v: _POTHOLE_CLASS_TO_EVENT.get(v, v) for v in names.values()}
    print(f"[AI Bridge] 🎯 Fine-tuned model covers: "
          + ", ".join(f"{k}→{v}" for k, v in mapped.items()))


# ═════════════════════════════════════════════════════════════
# Scene generators  (single source of truth — used by both
# the simulation event pipeline and the demo API endpoints)
# ═════════════════════════════════════════════════════════════

def _noise_road(h: int = 480, w: int = 640, base: int = 105) -> np.ndarray:
    """Generate a noisy road-texture frame."""
    lo, hi = max(0, base - 10), min(255, base + 12)
    img = np.random.randint(lo, hi, (h, w, 3), dtype=np.uint8)
    for _ in range(250):
        x = np.random.randint(0, w)
        y = np.random.randint(h // 2, h)
        cv2.circle(img, (x, y), np.random.randint(1, 3),
                   (base - 25, base - 25, base - 25), -1)
    for x in range(0, w, 70):
        cv2.rectangle(img, (x, h // 2 + 10), (x + 50, h // 2 + 25),
                      (210, 210, 210), -1)
    return img


def scene_pothole() -> np.ndarray:
    img = _noise_road()
    pts = np.array([[310, 340], [378, 328], [408, 358], [400, 405],
                    [358, 428], [295, 418], [266, 392], [272, 358]], np.int32)
    cv2.fillPoly(img, [pts], (18, 16, 14))
    cv2.polylines(img, [pts], True, (48, 46, 43), 3)
    cv2.ellipse(img, (335, 378), (45, 28), 10, 0, 360, (12, 10, 8), -1)
    cv2.ellipse(img, (148, 422), (32, 20), 25, 0, 360, (20, 18, 16), -1)
    cv2.ellipse(img, (500, 390), (22, 14), 40, 0, 360, (22, 20, 18), -1)
    cv2.line(img, (200, 350), (260, 410), (60, 58, 55), 2)
    cv2.line(img, (420, 320), (460, 380), (60, 58, 55), 2)
    return img


def scene_road_crack() -> np.ndarray:
    img = _noise_road()
    for _ in range(random.randint(4, 7)):
        x1 = random.randint(50, 500)
        y1 = random.randint(220, 420)
        dx = random.randint(50, 130)
        dy = random.randint(-20, 20)
        cv2.line(img, (x1, y1), (x1 + dx, y1 + dy), (32, 30, 28),
                 random.randint(2, 4))
        mid = ((x1 * 2 + dx) // 2, (y1 * 2 + dy) // 2)
        cv2.line(img, mid,
                 (mid[0] + random.randint(-25, 25), mid[1] + random.randint(15, 40)),
                 (32, 30, 28), 2)
    return img


def scene_traffic_light() -> np.ndarray:
    """RED traffic light — used by demo scene 2."""
    img = _noise_road(base=115)
    img[:180] = np.array([185, 155, 110], dtype=np.uint8)   # sky
    # Main pole + housing
    cv2.rectangle(img, (305, 30), (328, 210), (28, 28, 28), -1)
    cv2.rectangle(img, (292, 32), (342, 168), (18, 18, 18), -1)
    cv2.rectangle(img, (294, 34), (340, 166), (25, 25, 25), 1)
    # RED lit
    cv2.circle(img, (317, 58), 18, (0, 0, 200), -1)
    cv2.circle(img, (317, 58), 14, (0, 0, 255), -1)
    cv2.circle(img, (317, 58),  6, (80, 80, 255), -1)
    # Yellow / Green off
    cv2.circle(img, (317, 103), 16, (35, 35, 35), -1)
    cv2.circle(img, (317, 148), 16, (35, 35, 35), -1)
    # Second (distant) traffic light
    cv2.rectangle(img, (490, 50), (506, 160), (28, 28, 28), -1)
    cv2.rectangle(img, (482, 52), (514, 148), (18, 18, 18), -1)
    cv2.circle(img, (498,  72), 12, (0, 0, 200), -1)
    cv2.circle(img, (498, 103), 11, (35, 35, 35), -1)
    cv2.circle(img, (498, 133), 11, (35, 35, 35), -1)
    return img


def scene_accident() -> np.ndarray:
    img = _noise_road()
    # Car 1 (blue, hit from behind)
    cv2.rectangle(img, (55, 258), (210, 358), (170, 85, 28), -1)
    cv2.rectangle(img, (75, 237), (192, 263), (170, 85, 28), -1)
    cv2.rectangle(img, (82, 243), (185, 260), (220, 200, 150), -1)
    # Car 2 (orange, overlapping — collision)
    cv2.rectangle(img, (162, 268), (328, 372), (28, 118, 205), -1)
    cv2.rectangle(img, (182, 248), (308, 275), (28, 118, 205), -1)
    cv2.rectangle(img, (190, 253), (300, 272), (220, 200, 150), -1)
    # Damage marks at collision point
    for _ in range(12):
        px = np.random.randint(155, 215)
        py = np.random.randint(255, 375)
        cv2.circle(img, (px, py), np.random.randint(2, 6), (30, 30, 30), -1)
    # Car 3 (green, stopped behind)
    cv2.rectangle(img, (368, 262), (510, 362), (28, 155, 58), -1)
    cv2.rectangle(img, (388, 241), (490, 268), (28, 155, 58), -1)
    # Pedestrian on road
    cv2.ellipse(img, (562, 298), (17, 22), 0, 0, 360, (72, 52, 38), -1)
    cv2.rectangle(img, (549, 320), (575, 392), (58, 78, 118), -1)
    cv2.rectangle(img, (544, 392), (560, 445), (58, 78, 118), -1)
    cv2.rectangle(img, (563, 392), (578, 445), (58, 78, 118), -1)
    # Debris
    for _ in range(15):
        px = np.random.randint(100, 380)
        py = np.random.randint(340, 430)
        cv2.circle(img, (px, py), np.random.randint(2, 5), (55, 53, 50), -1)
    return img


def scene_waterlogging() -> np.ndarray:
    img = _noise_road(base=100)
    # Main pool
    cv2.ellipse(img, (320, 390), (270, 85), 0, 0, 360, (130, 95, 55), -1)
    # Reflections
    for _ in range(30):
        x = np.random.randint(70, 570)
        y = np.random.randint(315, 465)
        cv2.ellipse(img, (x, y),
                    (np.random.randint(6, 28), np.random.randint(2, 9)),
                    np.random.randint(0, 180), 0, 360, (170, 135, 75), -1)
    for r in [20, 40, 60]:
        cv2.ellipse(img, (320, 390), (r, r // 3), 0, 0, 360, (155, 120, 68), 1)
    for x in range(0, 640, 70):
        cv2.rectangle(img, (x, 378), (x + 50, 390), (165, 128, 72), -1)
    # Stranded car
    cv2.rectangle(img, (480, 330), (600, 410), (140, 70, 22), -1)
    cv2.rectangle(img, (495, 312), (585, 336), (140, 70, 22), -1)
    return img


def scene_heavy_traffic() -> np.ndarray:
    img = _noise_road(base=108)
    colors = [(170, 85, 28), (28, 118, 205), (28, 155, 58), (195, 195, 195),
              (85, 28, 170), (205, 170, 28), (28, 205, 170), (170, 28, 85)]
    for row, row_y in enumerate([245, 308, 370]):
        for col, col_x in enumerate([15, 135, 255, 375, 495]):
            c = colors[(row * 5 + col) % len(colors)]
            cv2.rectangle(img, (col_x, row_y), (col_x + 108, row_y + 58), c, -1)
            cv2.rectangle(img, (col_x + 10, row_y - 22), (col_x + 98, row_y + 5), c, -1)
            cv2.rectangle(img, (col_x + 16, row_y - 18), (col_x + 92, row_y + 2),
                          (220, 200, 145), -1)
            cv2.rectangle(img, (col_x, row_y + 40), (col_x + 18, row_y + 58),
                          (0, 0, 200), -1)
            cv2.rectangle(img, (col_x + 90, row_y + 40), (col_x + 108, row_y + 58),
                          (0, 0, 200), -1)
    # Red traffic light
    cv2.rectangle(img, (612, 28), (632, 128), (25, 25, 25), -1)
    cv2.rectangle(img, (605, 30), (640, 118), (18, 18, 18), -1)
    cv2.circle(img, (622,  50), 14, (0, 0, 210), -1)
    cv2.circle(img, (622,  85), 12, (35, 35, 35), -1)
    cv2.circle(img, (622, 116), 12, (35, 35, 35), -1)
    return img


def scene_fallen_tree() -> np.ndarray:
    img = _noise_road()
    # Trunk across road (dark brown in BGR)
    pts = np.array([[50, 310], [580, 270], [582, 312], [52, 352]], np.int32)
    cv2.fillPoly(img, [pts], (52, 80, 120))
    cv2.polylines(img, [pts], True, (40, 60, 90), 2)
    for i in range(15):
        x = 60 + i * 35
        cv2.line(img, (x, 315), (x + 20, 330), (38, 58, 85), 2)
    # Green foliage clumps
    for _ in range(8):
        cx = random.randint(100, 520)
        cy = random.randint(245, 385)
        cv2.ellipse(img, (cx, cy),
                    (random.randint(25, 55), random.randint(20, 40)),
                    random.randint(0, 180), 0, 360, (28, 130, 38), -1)
    return img


def scene_roadblock() -> np.ndarray:
    img = _noise_road()
    for i in range(5):
        x = 60 + i * 110
        cv2.rectangle(img, (x, 270), (x + 90, 390), (0, 120, 220), -1)      # orange (BGR)
        cv2.rectangle(img, (x, 270), (x + 90, 310), (210, 210, 210), -1)    # white stripe
        cv2.rectangle(img, (x, 350), (x + 90, 390), (210, 210, 210), -1)
    # Warning sign
    cv2.rectangle(img, (280, 200), (360, 270), (0, 90, 200), -1)
    cv2.putText(img, "STOP", (285, 248), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (255, 255, 255), 2)
    return img


def scene_animal_crossing() -> np.ndarray:
    img = _noise_road()
    cx, cy = 320, 340
    cv2.ellipse(img, (cx, cy), (70, 40), 0, 0, 360, (210, 210, 215), -1)         # body
    cv2.ellipse(img, (cx + 55, cy - 25), (28, 24), -15, 0, 360, (210, 210, 215), -1)  # head
    for leg_x in [cx - 40, cx - 15, cx + 20, cx + 45]:
        cv2.rectangle(img, (leg_x, cy + 35), (leg_x + 12, cy + 72), (200, 200, 205), -1)
    for _ in range(3):
        cv2.ellipse(img,
                    (cx + random.randint(-40, 30), cy + random.randint(-20, 15)),
                    (random.randint(8, 18), random.randint(6, 12)),
                    random.randint(0, 180), 0, 360, (55, 55, 60), -1)
    return img


# Scene generators keyed by simulator event type
SCENE_GENERATORS: dict[str, callable] = {
    "pothole":         scene_pothole,
    "road_crack":      scene_road_crack,
    "accident":        scene_accident,
    "waterlogging":    scene_waterlogging,
    "heavy_traffic":   scene_heavy_traffic,
    "fallen_tree":     scene_fallen_tree,
    "roadblock":       scene_roadblock,
    "animal_crossing": scene_animal_crossing,
}

# Ordered demo scenes list for /api/detect/sample/{n}
DEMO_SCENES = [
    ("Pothole Road",        scene_pothole),
    ("Traffic Light (RED)", scene_traffic_light),
    ("Traffic Accident",    scene_accident),
    ("Waterlogging",        scene_waterlogging),
    ("Heavy Traffic",       scene_heavy_traffic),
]


# ═════════════════════════════════════════════════════════════
# AIBridge — singleton, non-blocking, thread-safe
# ═════════════════════════════════════════════════════════════

class AIBridge:
    """
    Non-blocking AI inference bridge for the simulation.

    Maintains a pre-warmed pool of (confidence, severity) tuples per event
    type so that _gen_event() never blocks on YOLO inference.  Pool refills
    happen asynchronously in daemon threads.
    """

    POOL_SIZE = 8   # max cached results per event type

    def __init__(self):
        self._detector = None
        self.available = False
        self._pools: dict[str, list] = {k: [] for k in SCENE_GENERATORS}
        self._lock = threading.Lock()          # guards pool dict
        self._infer_lock = threading.Lock()    # serialises YOLO inference (not thread-safe)
        self._det_count = 0
        self._status = "loading"

        det, ok = _load_detector()
        self._detector = det
        self.available = ok
        self._status = "ready" if ok else "fallback (CV only)"

        if ok:
            _update_type_map(det)   # log fine-tuned class coverage
            t = threading.Thread(target=self._warmup, daemon=True, name="ai-warmup")
            t.start()

    # ──── Internal ────────────────────────────────────────────

    def _warmup(self):
        """Pre-fill pool with 3 AI results per event type at startup."""
        for etype in SCENE_GENERATORS:
            self._fill_pool(etype, n=3)
        print(f"[AI Bridge] ✅ Warmup complete — {self._det_count} inferences run")

    def _fill_pool(self, event_type: str, n: int = 2):
        gen = SCENE_GENERATORS.get(event_type)
        if not gen or not self._detector:
            return
        for _ in range(n):
            try:
                frame = gen()
                with self._infer_lock:          # serialise YOLO calls
                    result = self._detector.detect_full(frame)
                self._det_count += 1
                conf, sev = self._extract(event_type, result)
                with self._lock:
                    pool = self._pools.setdefault(event_type, [])
                    pool.append((conf, sev))
                    if len(pool) > self.POOL_SIZE:
                        pool.pop(0)
            except Exception as exc:
                print(f"[AI Bridge] Pool fill error ({event_type}): {exc}")

    def _extract(self, event_type: str, result) -> Tuple[float, str]:
        """Pull (confidence, severity) from a FrameResult."""
        expected_cat = _TYPE_TO_CAT.get(event_type)

        # Match a detection with the expected category
        if expected_cat and result.detections:
            matches = [d for d in result.detections if d.category == expected_cat]
            if matches:
                best = max(matches, key=lambda d: d.confidence)
                return best.confidence, best.severity

        # For heavy_traffic derive from traffic density
        if event_type == "heavy_traffic" and result.traffic:
            t   = result.traffic
            vc  = t.get("vehicle_count", 0) if isinstance(t, dict) else t.vehicle_count
            den = t.get("density", "low")   if isinstance(t, dict) else t.density
            conf = round(min(0.98, 0.55 + vc * 0.04), 2)
            sev  = {"low": "low", "moderate": "medium",
                    "heavy": "high", "gridlock": "critical"}.get(den, "medium")
            return conf, sev

        return self._fallback_values(event_type)

    def _fallback_values(self, event_type: str) -> Tuple[float, str]:
        conf_range, sevs = _FALLBACK.get(event_type, ((0.60, 0.85), ["medium"]))
        return round(random.uniform(*conf_range), 2), random.choice(sevs)

    # ──── Public API ──────────────────────────────────────────

    def get_result(self, event_type: str) -> Tuple[float, str]:
        """
        Return (confidence, severity) for an event type.
        Uses the pre-warmed pool when possible; never blocks the caller.
        """
        with self._lock:
            pool = self._pools.get(event_type, [])
            if pool:
                result = pool.pop(0)
                # Async refill when pool runs low
                if len(pool) < 3 and self.available:
                    threading.Thread(
                        target=self._fill_pool,
                        args=(event_type, 3),
                        daemon=True,
                        name=f"ai-refill-{event_type}",
                    ).start()
                return result

        # Pool empty — run synchronously (rare; only during heavy startup load)
        if self.available:
            try:
                frame = SCENE_GENERATORS[event_type]()
                with self._infer_lock:          # serialise YOLO call
                    result = self._detector.detect_full(frame)
                self._det_count += 1
                return self._extract(event_type, result)
            except Exception as exc:
                print(f"[AI Bridge] On-demand detection error: {exc}")

        return self._fallback_values(event_type)

    def run_on_frame(self, frame: np.ndarray):
        """
        Run full AI detection on a real camera/upload frame.
        Returns FrameResult (from detector.py) or None.
        """
        if not self.available or self._detector is None:
            return None
        with self._infer_lock:
            return self._detector.detect_full(frame)

    def annotate_frame(self, frame: np.ndarray, result) -> np.ndarray:
        """Draw bounding boxes and stats overlay on frame."""
        if not self.available or self._detector is None:
            return frame
        return self._detector.annotate(frame, result)

    def cv_pothole_only(self, frame: np.ndarray) -> list:
        """
        Run only the CV pothole detector (no YOLO).
        Used as a fallback when the full model is unavailable.
        """
        h, w = frame.shape[:2]
        if self._detector:
            return self._detector._detect_potholes_cv(frame, w, h)
        # Minimal inline CV if detector import failed entirely
        return []

    @property
    def model_name(self) -> str:
        if not self.available:
            return "CV fallback"
        det = self._detector
        if det and det.has_pothole_model:
            classes = list(det._pothole_names.values()) if det._pothole_names else []
            cls_str = "+".join(classes) if classes else "pothole.pt"
            return f"YOLOv8s + fine-tuned [{cls_str}]"
        return "YOLOv8s + CV"

    @property
    def status(self) -> dict:
        with self._lock:
            pool_sizes = {k: len(v) for k, v in self._pools.items()}
        det = self._detector
        pothole_info = {}
        if det and det.has_pothole_model:
            pothole_info = {
                "classes":    det._pothole_names,
                "conf":       getattr(det, "_pothole_conf", 0.35),
                "val_metrics": getattr(det, "_pothole_val_metrics", None),
            }
        return {
            "available":     self.available,
            "status":        self._status,
            "model":         self.model_name,
            "inferences":    self._det_count,
            "pool":          pool_sizes,
            "ai_dir":        str(_AI_DIR),
            "ai_dir_exists": _AI_DIR.exists(),
            "pothole_model": pothole_info if pothole_info else None,
        }


# ── Global singleton ─────────────────────────────────────────
bridge = AIBridge()
