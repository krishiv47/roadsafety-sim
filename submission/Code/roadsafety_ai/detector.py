"""
Road Hazard Detector v2
- YOLOv8s (small, ~22 MB) for vehicle/accident/traffic detection
- Traffic density analysis + traffic light state estimation
- Multi-signal accident detection (overlap, person-vehicle proximity, cluster density)
- Improved pothole CV (adaptive threshold + edge mask + local contrast)
- Optional: drop models/pothole.pt for ML pothole detection
"""
import cv2
import json
import numpy as np
from ultralytics import YOLO
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

# Fine-tuned pothole model: class name → detection category
# "pothole" and "road_crack" both map to the "pothole" category so the
# existing _TYPE_TO_CAT mapping in ai_bridge.py continues to work.
_POTHOLE_CLASS_CAT: dict[str, str] = {
    "pothole":      "pothole",
    "road_crack":   "pothole",   # surface damage group
    "crack":        "pothole",
    "debris":       "obstacle",
    "flooding":     "obstacle",  # flooding = waterlogging
    "waterlogging": "obstacle",
}

# BGR draw colors
CATEGORY_COLORS = {
    "pothole":       (0,   0,   255),   # red
    "accident":      (0,   80,  255),   # deep orange
    "traffic_light": (0,   255, 200),   # cyan-green
    "traffic":       (255, 180,   0),   # blue
    "pedestrian":    (200,   0, 255),   # purple
    "vehicle":       (0,   200,  50),   # green
    "obstacle":      (30,  200, 255),   # amber — waterlogging / road obstacle
}

DENSITY_COLOR = {
    "low":      (0, 200, 50),
    "moderate": (0, 200, 220),
    "heavy":    (0, 140, 255),
    "gridlock": (0,   0, 255),
}

LIGHT_COLOR = {
    "red":     (0,   0,   255),
    "yellow":  (0,   220, 255),
    "green":   (0,   200,  50),
    "unknown": (128, 128, 128),
}

# COCO class IDs
_VEHICLE_IDS   = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
_BICYCLE_ID    = 1
_PERSON_ID     = 0
_TLIGHT_ID     = 9
_STOPSIGN_ID   = 11


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: list          # [x1, y1, x2, y2] normalized 0–1
    severity: str       # low | medium | high | critical
    category: str       # pothole | accident | traffic_light | vehicle | pedestrian

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrafficInfo:
    vehicle_count: int
    pedestrian_count: int
    bicycle_count: int
    density: str                    # low | moderate | heavy | gridlock
    density_score: float            # 0.0 – 1.0
    traffic_lights: list            # [{state, confidence, bbox}]
    congestion_advice: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FrameResult:
    frame_number: int
    timestamp: float
    detections: list
    traffic: Optional[dict]
    motion_score: float             # 0 = still, 1 = high motion (video only)
    annotated_frame: Optional[np.ndarray] = field(default=None, repr=False)


class RoadHazardDetector:
    def __init__(self, pothole_model_path: Optional[str] = None, model_size: str = "s"):
        # yolov8s.pt (~22 MB) — much better detection than yolov8n
        self.general_model = YOLO(f"yolov8{model_size}.pt")

        self.pothole_model: Optional[YOLO] = None
        self._pothole_conf: float = 0.35       # inference confidence threshold
        self._pothole_names: dict[int, str] = {}  # {cls_id: class_name}
        self._pothole_val_metrics: Optional[dict] = None

        if pothole_model_path and Path(pothole_model_path).exists():
            self.pothole_model = YOLO(pothole_model_path)
            # Class names from model weights (always available)
            raw_names = self.pothole_model.names or {}
            self._pothole_names = {int(k): v for k, v in raw_names.items()}

            # Prefer the richer pothole_config.json written by train.py —
            # it carries the trained conf threshold and val metrics.
            config_path = Path(pothole_model_path).parent / "pothole_config.json"
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        cfg = json.load(f)
                    self._pothole_conf = float(cfg.get("conf", self._pothole_conf))
                    # Config classes override model names (more explicit)
                    if "classes" in cfg:
                        self._pothole_names = {int(k): v
                                               for k, v in cfg["classes"].items()}
                    self._pothole_val_metrics = cfg.get("val_metrics")
                except Exception:
                    pass  # fall back to model defaults

        self.has_pothole_model = self.pothole_model is not None

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def detect_full(self, frame: np.ndarray, motion_score: float = 0.0) -> FrameResult:
        """Full analysis: hazards + traffic + light states. Returns FrameResult."""
        h, w = frame.shape[:2]
        raw = self._run_yolo(frame)

        # Traffic analysis
        traffic = self._analyze_traffic(raw, frame)

        # Hazard detections
        hazards: list[Detection] = []

        # Accident signals
        acc = self._analyze_accident(raw["vehicles"], raw["people"], w, h, motion_score)
        if acc:
            hazards.append(acc)

        # Traffic lights as detections (for annotation)
        for tl in raw["traffic_lights"]:
            hazards.append(Detection(
                class_name=f"traffic_light_{tl['state']}",
                confidence=round(tl["conf"], 3),
                bbox=tl["bbox"],
                severity="low",
                category="traffic_light",
            ))

        # Pedestrians on road
        for p in raw["people"]:
            if self._person_on_road(p["bbox"], h):
                hazards.append(Detection(
                    class_name="pedestrian_on_road",
                    confidence=round(p["conf"], 3),
                    bbox=p["bbox"],
                    severity="high",
                    category="pedestrian",
                ))

        # Pothole detection
        if self.pothole_model:
            hazards.extend(self._detect_potholes_model(frame, w, h))
        else:
            hazards.extend(self._detect_potholes_cv(frame, w, h))

        # CV scene hazard analysis: waterlogging + multi-vehicle incidents
        hazards.extend(self._detect_scene_hazards_cv(frame, w, h, hazards))

        # Normalize all bboxes to [0,1]
        for d in hazards:
            d.bbox = [
                round(d.bbox[0] / w, 4), round(d.bbox[1] / h, 4),
                round(d.bbox[2] / w, 4), round(d.bbox[3] / h, 4),
            ]

        return FrameResult(
            frame_number=0,
            timestamp=0.0,
            detections=hazards,
            traffic=traffic.to_dict(),
            motion_score=round(motion_score, 3),
        )

    def annotate(self, frame: np.ndarray, result: FrameResult) -> np.ndarray:
        h, w = frame.shape[:2]
        img = frame.copy()

        # Draw each detection
        for det in result.detections:
            x1, y1 = int(det.bbox[0] * w), int(det.bbox[1] * h)
            x2, y2 = int(det.bbox[2] * w), int(det.bbox[3] * h)
            color = CATEGORY_COLORS.get(det.category, (0, 255, 0))

            thickness = 3 if det.severity in ("critical", "high") else 2
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

            label = f"{det.class_name}  {det.severity}  {det.confidence:.0%}"
            (lw, lh), base = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
            cv2.rectangle(img, (x1, y1 - lh - base - 6), (x1 + lw + 4, y1), color, -1)
            cv2.putText(img, label, (x1 + 2, y1 - base - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

        # Traffic overlay bar at top
        t = result.traffic or {}
        density = t.get("density", "low")
        d_color = DENSITY_COLOR.get(density, (200, 200, 200))
        bar = f"  Vehicles: {t.get('vehicle_count',0)}  |  Traffic: {density.upper()}  |  Pedestrians: {t.get('pedestrian_count',0)}  |  Hazards: {len(result.detections)}"
        if result.motion_score > 0:
            bar += f"  |  Motion: {result.motion_score:.2f}"

        cv2.rectangle(img, (0, 0), (w, 38), (20, 20, 20), -1)
        cv2.putText(img, bar, (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.62, d_color, 2, cv2.LINE_AA)

        # Traffic light mini icons
        lights = t.get("traffic_lights", [])
        for i, tl in enumerate(lights[:4]):
            state = tl.get("state", "unknown")
            lc = LIGHT_COLOR.get(state, (128, 128, 128))
            cx = w - 30 - i * 36
            cv2.circle(img, (cx, 54), 12, lc, -1)
            cv2.circle(img, (cx, 54), 12, (255, 255, 255), 1)
            cv2.putText(img, state[0].upper(), (cx - 5, 59),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        return img

    # ------------------------------------------------------------------ #
    #  YOLO inference                                                      #
    # ------------------------------------------------------------------ #

    def _run_yolo(self, frame: np.ndarray) -> dict:
        results = self.general_model(frame, verbose=False, conf=0.30)[0]
        vehicles, people, traffic_lights, bicycles = [], [], [], []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf   = float(box.conf[0])
            bbox   = [float(c) for c in box.xyxy[0]]

            if cls_id in _VEHICLE_IDS:
                vehicles.append({"bbox": bbox, "cls": _VEHICLE_IDS[cls_id], "conf": conf})
            elif cls_id == _PERSON_ID:
                people.append({"bbox": bbox, "conf": conf})
            elif cls_id == _TLIGHT_ID:
                state = self._estimate_light_state(frame, bbox)
                traffic_lights.append({"bbox": bbox, "conf": conf, "state": state})
            elif cls_id == _BICYCLE_ID:
                bicycles.append({"bbox": bbox, "conf": conf})

        return {"vehicles": vehicles, "people": people,
                "traffic_lights": traffic_lights, "bicycles": bicycles}

    # ------------------------------------------------------------------ #
    #  Traffic analysis                                                    #
    # ------------------------------------------------------------------ #

    def _analyze_traffic(self, raw: dict, frame: np.ndarray) -> TrafficInfo:
        vc = len(raw["vehicles"])
        pc = len(raw["people"])
        bc = len(raw["bicycles"])

        if vc <= 2:   density, score = "low",      min(vc / 3, 1.0)
        elif vc <= 5: density, score = "moderate",  vc / 6
        elif vc <= 10:density, score = "heavy",     vc / 11
        else:         density, score = "gridlock",  1.0

        advice = {
            "low":      "Road is clear.",
            "moderate": "Moderate traffic — drive carefully.",
            "heavy":    "Heavy traffic — expect delays.",
            "gridlock": "Gridlock detected — consider alternate route.",
        }[density]

        return TrafficInfo(
            vehicle_count=vc,
            pedestrian_count=pc,
            bicycle_count=bc,
            density=density,
            density_score=round(score, 3),
            traffic_lights=raw["traffic_lights"],
            congestion_advice=advice,
        )

    # ------------------------------------------------------------------ #
    #  Traffic light state estimation                                      #
    # ------------------------------------------------------------------ #

    def _estimate_light_state(self, frame: np.ndarray, bbox: list) -> str:
        x1, y1, x2, y2 = (int(c) for c in bbox)
        crop = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
        if crop.size == 0:
            return "unknown"

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # HSV masks for each light color
        red_lo  = cv2.inRange(hsv, (0,   120, 100), (10,  255, 255))
        red_hi  = cv2.inRange(hsv, (160, 120, 100), (180, 255, 255))
        red_m   = cv2.bitwise_or(red_lo, red_hi)
        yellow_m= cv2.inRange(hsv, (18,  120, 100), (35,  255, 255))
        green_m = cv2.inRange(hsv, (40,  80,  80),  (90,  255, 255))

        counts = {
            "red":    int(red_m.sum()),
            "yellow": int(yellow_m.sum()),
            "green":  int(green_m.sum()),
        }
        best = max(counts, key=counts.get)
        return best if counts[best] > 200 else "unknown"

    # ------------------------------------------------------------------ #
    #  Accident detection (multi-signal)                                   #
    # ------------------------------------------------------------------ #

    def _analyze_accident(self, vehicles: list, people: list,
                          w: int, h: int, motion_score: float = 0.0) -> Optional[Detection]:
        score = 0.0
        evidence = []
        best_bbox = None

        # Signal 1: vehicle overlap (IoU)
        if len(vehicles) >= 2:
            max_iou, best_pair = 0.0, None
            for i in range(len(vehicles)):
                for j in range(i + 1, len(vehicles)):
                    iou = self._iou(vehicles[i]["bbox"], vehicles[j]["bbox"])
                    if iou > max_iou:
                        max_iou, best_pair = iou, (vehicles[i], vehicles[j])

            if max_iou >= 0.08:
                score += max_iou * 0.6
                evidence.append(f"overlap:{max_iou:.2f}")
                b1, b2 = best_pair[0]["bbox"], best_pair[1]["bbox"]
                best_bbox = [min(b1[0], b2[0]), min(b1[1], b2[1]),
                             max(b1[2], b2[2]), max(b1[3], b2[3])]

        # Signal 2: person within 50 px of a vehicle (potential victim)
        for p in people:
            for v in vehicles:
                dist = self._center_dist(p["bbox"], v["bbox"])
                px_threshold = 0.12 * w        # 12% of frame width
                if dist < px_threshold:
                    score += 0.35
                    evidence.append("person_near_vehicle")
                    if best_bbox is None:
                        best_bbox = v["bbox"][:]
                    break

        # Signal 3: sudden motion drop in video (optical flow)
        if motion_score > 0.5:
            score += 0.20
            evidence.append(f"high_motion:{motion_score:.2f}")

        # Signal 4: large vehicle cluster
        if len(vehicles) >= 4:
            img_area = w * h
            cluster_area = sum(
                (v["bbox"][2] - v["bbox"][0]) * (v["bbox"][3] - v["bbox"][1])
                for v in vehicles
            )
            if cluster_area / img_area > 0.45:
                score += 0.25
                evidence.append("dense_cluster")

        if score < 0.20 or best_bbox is None:
            return None

        severity = "critical" if score > 0.75 else ("high" if score > 0.45 else "medium")
        conf = round(min(0.97, 0.45 + score * 0.55), 3)

        return Detection(
            class_name="traffic_accident",
            confidence=conf,
            bbox=best_bbox,
            severity=severity,
            category="accident",
        )

    # ------------------------------------------------------------------ #
    #  Pothole detection                                                   #
    # ------------------------------------------------------------------ #

    def _detect_potholes_model(self, frame: np.ndarray, w: int, h: int) -> list[Detection]:
        """
        Run the fine-tuned pothole model.
        Uses the trained confidence threshold from pothole_config.json and
        the model's actual class names (pothole / road_crack / debris / flooding …).
        """
        results = self.pothole_model(frame, verbose=False, conf=self._pothole_conf)[0]
        out = []
        for box in results.boxes:
            conf   = float(box.conf[0])
            cls_id = int(box.cls[0])
            # Resolve class name: model names dict, then generic fallback
            cls_name = self._pothole_names.get(cls_id, f"damage_{cls_id}")
            category = _POTHOLE_CLASS_CAT.get(cls_name, "pothole")

            x1, y1, x2, y2 = (float(c) for c in box.xyxy[0])
            area_ratio = (x2 - x1) * (y2 - y1) / max(w * h, 1)
            severity   = self._area_severity(area_ratio)

            # Flooding / debris can't be "low" — always at least medium
            if cls_name in ("flooding", "waterlogging", "debris") and severity == "low":
                severity = "medium"

            out.append(Detection(
                class_name=cls_name,
                confidence=round(conf, 3),
                bbox=[x1, y1, x2, y2],
                severity=severity,
                category=category,
            ))
        return out

    def _detect_potholes_cv(self, frame: np.ndarray, w: int, h: int) -> list[Detection]:
        """
        Improved pothole CV:
        1. Focus on lower 55% (road area)
        2. Adaptive threshold instead of fixed cutoff
        3. Edge-mask to confirm irregular boundaries
        4. Local contrast check (pothole darker than surroundings)
        5. Aspect ratio + circularity filtering
        """
        roi_y = int(h * 0.45)
        roi = frame[roi_y:, :]
        rh, rw = roi.shape[:2]

        gray     = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred  = cv2.GaussianBlur(gray, (13, 13), 0)

        # Adaptive threshold — handles varied lighting
        adapt    = cv2.adaptiveThreshold(blurred, 255,
                                         cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY_INV, 51, 8)

        # Fixed threshold catches very dark pixels (deep potholes)
        _, fixed = cv2.threshold(blurred, 70, 255, cv2.THRESH_BINARY_INV)
        # OR: either adaptive pattern OR very dark pixel qualifies
        combined = cv2.bitwise_or(adapt, fixed)

        # Morphological cleanup
        kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        cleaned  = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        cleaned  = cv2.morphologyEx(cleaned,  cv2.MORPH_OPEN,  kernel)

        cnts, _  = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out      = []

        for cnt in cnts:
            area = cv2.contourArea(cnt)
            ratio = area / (w * h)
            if not (0.0015 < ratio < 0.18):
                continue

            perim = cv2.arcLength(cnt, True)
            if perim == 0:
                continue
            circularity = 4 * np.pi * area / (perim ** 2)
            if circularity < 0.18:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / max(bh, 1)
            if not (0.25 < aspect < 4.0):
                continue

            # Local contrast: pothole region mean vs surrounding ring
            pad = max(10, int(min(bw, bh) * 0.4))
            sx1, sy1 = max(0, x - pad), max(0, y - pad)
            sx2, sy2 = min(rw, x + bw + pad), min(rh, y + bh + pad)
            surround = blurred[sy1:sy2, sx1:sx2]
            inner    = blurred[y:y+bh, x:x+bw]
            if inner.size == 0 or surround.size == 0:
                continue
            contrast = float(surround.mean()) - float(inner.mean())
            if contrast < 8:          # pothole must be darker than surroundings
                continue

            conf     = round(min(0.82, 0.38 + circularity * 0.4 + min(contrast, 40) / 100), 3)
            severity = self._area_severity(ratio)
            y_abs    = float(y + roi_y)

            out.append(Detection(
                class_name="pothole",
                confidence=conf,
                bbox=[float(x), y_abs, float(x + bw), y_abs + float(bh)],
                severity=severity,
                category="pothole",
            ))

        return out

    # ------------------------------------------------------------------ #
    #  Scene hazard CV: waterlogging + multi-vehicle incident             #
    # ------------------------------------------------------------------ #

    def _detect_scene_hazards_cv(self, frame: np.ndarray, w: int, h: int,
                                  existing: list) -> list[Detection]:
        """
        Two complementary CV signals for cases YOLO misses (synthetic / low-res):
        1. Waterlogging — large blue/brown pool covering >15 % of road area
        2. Multi-vehicle incident — 3+ distinct-hue blobs clustered tightly
        """
        out: list[Detection] = []
        roi_y = int(h * 0.40)
        roi   = frame[roi_y:, :]
        rh, rw = roi.shape[:2]
        if rh < 10 or rw < 10:
            return out
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hue_ch = hsv[:, :, 0].astype(np.int32)
        sat_ch = hsv[:, :, 1]
        val_ch = hsv[:, :, 2]

        # ── 1. Waterlogging ──────────────────────────────────────────────
        water_mask = cv2.bitwise_or(
            cv2.inRange(hsv, (90,  40, 60), (130, 255, 210)),   # blue-ish
            cv2.inRange(hsv, (15,  30, 55), (35,  130, 190)),   # muddy brown
        )
        water_ratio = float(np.sum(water_mask > 0)) / max(rh * rw, 1)
        if water_ratio > 0.15:
            ks = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            wc = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, ks)
            cnts, _ = cv2.findContours(wc, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts:
                c   = max(cnts, key=cv2.contourArea)
                x, y, bw, bh = cv2.boundingRect(c)
                conf = round(min(0.91, 0.55 + water_ratio * 1.5), 3)
                out.append(Detection(
                    class_name="waterlogging",
                    confidence=conf,
                    bbox=[float(x), float(y + roi_y),
                          float(x + bw), float(y + roi_y + bh)],
                    severity="high" if water_ratio > 0.25 else "medium",
                    category="obstacle",
                ))

        # ── 2. Multi-vehicle incident ────────────────────────────────────
        # Skip if YOLO already raised an accident
        if any(d.category == "accident" for d in existing):
            return out

        sat_mask = (sat_ch > 60) & (val_ch > 50)
        blob_threshold = 0.015 * rh * rw      # blob must cover > 1.5 % of road area
        colored_blobs: list[dict] = []
        seen_bands: set[int] = set()

        for hue_start in range(0, 180, 30):
            band_img = (
                (hue_ch >= hue_start) & (hue_ch < hue_start + 30) & sat_mask
            ).astype(np.uint8) * 255
            ks2 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            band_img = cv2.morphologyEx(band_img, cv2.MORPH_CLOSE, ks2)
            cnts, _ = cv2.findContours(band_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                area = cv2.contourArea(c)
                if area < blob_threshold:
                    continue
                x, y, bw2, bh2 = cv2.boundingRect(c)
                colored_blobs.append({
                    "hue_band": hue_start,
                    "cx":       x + bw2 / 2,
                    "cy":       y + bh2 / 2,
                    "area":     area,
                    "bbox":     [float(x), float(y + roi_y),
                                 float(x + bw2), float(y + roi_y + bh2)],
                })
                seen_bands.add(hue_start)

        # Need ≥3 distinct hue bands + at least one OVERLAPPING pair from
        # different bands (different-coloured vehicles touching = collision)
        if len(seen_bands) >= 3 and len(colored_blobs) >= 3:
            accident_box: Optional[list] = None
            for i, b1 in enumerate(colored_blobs):
                for b2 in colored_blobs[i + 1:]:
                    if b1["hue_band"] == b2["hue_band"]:
                        continue
                    # Convert stored abs-coords back to ROI coords for overlap test
                    x1a, y1a = b1["bbox"][0], b1["bbox"][1] - roi_y
                    x2a, y2a = b1["bbox"][2], b1["bbox"][3] - roi_y
                    x1b, y1b = b2["bbox"][0], b2["bbox"][1] - roi_y
                    x2b, y2b = b2["bbox"][2], b2["bbox"][3] - roi_y
                    if x1a < x2b and x2a > x1b and y1a < y2b and y2a > y1b:
                        # Ensure blobs are side-by-side, not bumper-to-bumper in
                        # the same column (same-column pairs have x-center diff ≈ 0)
                        cx_diff = abs((x1a + x2a) / 2 - (x1b + x2b) / 2)
                        if cx_diff < 35:   # same-column → lane traffic, not collision
                            continue
                        # Bounding-boxes of two differently-coloured vehicles overlap
                        accident_box = [
                            min(b1["bbox"][0], b2["bbox"][0]),
                            min(b1["bbox"][1], b2["bbox"][1]),
                            max(b1["bbox"][2], b2["bbox"][2]),
                            max(b1["bbox"][3], b2["bbox"][3]),
                        ]
                        break
                if accident_box:
                    break

            if accident_box:
                n = len(colored_blobs)
                conf = round(min(0.86, 0.55 + n * 0.04), 3)
                out.append(Detection(
                    class_name="multi_vehicle_incident",
                    confidence=conf,
                    bbox=accident_box,
                    severity="critical" if n >= 5 else "high",
                    category="accident",
                ))

        return out

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _area_severity(ratio: float) -> str:
        if ratio > 0.05:   return "critical"
        if ratio > 0.02:   return "high"
        if ratio > 0.005:  return "medium"
        return "low"

    @staticmethod
    def _iou(b1: list, b2: list) -> float:
        xi1, yi1 = max(b1[0], b2[0]), max(b1[1], b2[1])
        xi2, yi2 = min(b1[2], b2[2]), min(b1[3], b2[3])
        inter = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
        a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
        return inter / (a1 + a2 - inter + 1e-8)

    @staticmethod
    def _center_dist(b1: list, b2: list) -> float:
        cx1, cy1 = (b1[0] + b1[2]) / 2, (b1[1] + b1[3]) / 2
        cx2, cy2 = (b2[0] + b2[2]) / 2, (b2[1] + b2[3]) / 2
        return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5

    @staticmethod
    def _person_on_road(bbox: list, img_h: int) -> bool:
        # Person is in lower 60% of frame → likely on road, not sidewalk/background
        bottom_y = bbox[3]
        return bottom_y > img_h * 0.40
