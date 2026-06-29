"""Read the boost-gauge integer (0-100) from a frame (spec §6.1)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from backend.detection.config import DetectionConfig
from backend.detection.matching import match_digit


@dataclass(frozen=True)
class GaugeReading:
    value: int | None       # 0-100, or None when unreadable / below threshold
    confidence: float       # min per-digit score (0.0 when unreadable)


def load_templates(dir_path: str | Path) -> dict[int, np.ndarray]:
    """Load digit templates `0.png`..`9.png` (grayscale) from a directory."""
    out: dict[int, np.ndarray] = {}
    base = Path(dir_path)
    for digit in range(10):
        p = base / f"{digit}.png"
        if p.exists():
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                out[digit] = img
    return out


def crop_gauge(frame: np.ndarray, cfg: DetectionConfig) -> np.ndarray:
    g = cfg.gauge
    return frame[g.y : g.y + g.h, g.x : g.x + g.w]


def segment_digits(gray: np.ndarray) -> list[np.ndarray]:
    """Split the gauge crop into individual digit cells, left to right.

    PROVISIONAL heuristic (Otsu threshold + external contours, filtered by height):
    a sensible starting point. Real segmentation is tuned once the exact gauge
    layout and font are known from footage (spec §6.1).
    """
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_img = gray.shape[0]
    boxes = [cv2.boundingRect(c) for c in contours]
    boxes = [b for b in boxes if b[3] >= 0.3 * h_img]   # drop noise by height
    boxes.sort(key=lambda b: b[0])                       # left to right
    return [gray[y : y + h, x : x + w] for (x, y, w, h) in boxes]


def read_value(
    frame: np.ndarray, templates: dict[int, np.ndarray], cfg: DetectionConfig
) -> GaugeReading:
    crop = crop_gauge(frame, cfg)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    cells = segment_digits(gray)
    if not cells or not templates:
        return GaugeReading(None, 0.0)

    digits: list[int] = []
    scores: list[float] = []
    for cell in cells:
        m = match_digit(cell, templates)
        digits.append(m.digit)
        scores.append(m.score)

    confidence = min(scores) if scores else 0.0
    if confidence < cfg.match_threshold or any(d < 0 for d in digits):
        return GaugeReading(None, confidence)

    value = int("".join(str(d) for d in digits))
    value = max(0, min(cfg.full_value, value))
    return GaugeReading(value, confidence)
