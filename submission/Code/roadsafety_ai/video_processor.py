"""
Video processor v2 — optical flow between frames for motion-based accident detection.
"""
import cv2
import numpy as np
from typing import Generator, Optional
from detector import RoadHazardDetector, FrameResult


class VideoProcessor:
    def __init__(self, detector: RoadHazardDetector):
        self.detector = detector

    def process_video(
        self,
        path: str,
        sample_rate: int = 5,
        annotate: bool = False,
    ) -> Generator[FrameResult, None, None]:
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        idx = 0
        prev_gray: Optional[np.ndarray] = None
        prev_motion: float = 0.0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if idx % sample_rate == 0:
                    # Optical flow against previous sampled frame
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (7, 7), 0)
                    motion_score = self._motion_score(prev_gray, gray, prev_motion)

                    result = self.detector.detect_full(frame, motion_score=motion_score)
                    result.frame_number = idx
                    result.timestamp    = round(idx / fps, 2)

                    if annotate:
                        result.annotated_frame = self.detector.annotate(frame, result)

                    prev_gray   = gray
                    prev_motion = motion_score
                    yield result

                idx += 1
        finally:
            cap.release()

    def process_image(self, path: str) -> FrameResult:
        frame = cv2.imread(path)
        if frame is None:
            raise ValueError(f"Could not read image: {path}")
        result = self.detector.detect_full(frame)
        result.annotated_frame = self.detector.annotate(frame, result)
        return result

    # ------------------------------------------------------------------ #

    @staticmethod
    def _motion_score(prev: Optional[np.ndarray], curr: np.ndarray,
                      prev_score: float) -> float:
        """
        Farneback dense optical flow → mean magnitude → normalized score 0–1.
        A sudden spike followed by a drop (prev_score high, curr low) strongly
        suggests a collision event.
        """
        if prev is None or prev.shape != curr.shape:
            return 0.0

        flow = cv2.calcOpticalFlowFarneback(
            prev, curr, None,
            pyr_scale=0.5, levels=3, winsize=13,
            iterations=3, poly_n=5, poly_sigma=1.1, flags=0,
        )
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        mean_mag = float(mag.mean())

        # Normalize: typical road values 0–20 px/frame
        score = min(mean_mag / 18.0, 1.0)

        # Sudden drop after high motion = crash indicator — boost score
        if prev_score > 0.5 and score < 0.15:
            score = min(1.0, score + 0.55)

        return round(score, 3)
