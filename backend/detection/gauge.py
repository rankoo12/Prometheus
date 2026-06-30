"""Read the boost-gauge integer (0-100) from a frame (spec §6.1).

The displayed number is matched on an Otsu-binarized crop so reading is invariant to
the orange->white colour shift and the busy background. Non-digit contours (the radial
dial arc) are dropped two ways: a size filter, and a final per-cell match-score filter
(an arc fragment matches no digit template well).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from backend.detection.config import DetectionConfig
from backend.detection.matching import match_digit, prepare


@dataclass(frozen=True)
class GaugeReading:
    value: int | None       # 0-100, or None when unreadable
    confidence: float       # min kept-digit score (0.0 when unreadable)


def load_templates(dir_path: str | Path) -> dict[int, list[np.ndarray]]:
    """Load digit exemplars from a directory and prepare their fingerprints once.
    Filenames start with the digit: `<digit>.png` or `<digit>_<id>.png`.
    Returns {digit: [prepared fingerprints]} for fast 1-NN matching."""
    out: dict[int, list[np.ndarray]] = {}
    for p in Path(dir_path).glob("*.png"):
        head = p.stem.split("_")[0]
        if not head.isdigit() or not 0 <= int(head) <= 9:
            continue
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            out.setdefault(int(head), []).append(prepare(img))
    return out


def crop_gauge(frame: np.ndarray, cfg: DetectionConfig) -> np.ndarray:
    g = cfg.gauge
    return frame[g.y : g.y + g.h, g.x : g.x + g.w]


def binarize(gray: np.ndarray) -> np.ndarray:
    """Otsu threshold — bright glyphs (orange or white) to 255, background to 0."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def digit_boxes(binary: np.ndarray, cfg: DetectionConfig) -> list[tuple[int, int, int, int]]:
    """Candidate digit bounding boxes, left to right (size-filtered for dial ticks)."""
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows, cols = binary.shape[:2]
    boxes = []
    for x, y, w, h in (cv2.boundingRect(c) for c in contours):
        if h < cfg.min_digit_height_frac * rows or w < cfg.min_digit_width:
            continue
        if x < cfg.edge_margin or (x + w) > cols - cfg.edge_margin:
            continue  # touches a crop edge -> dial arc, not a digit
        boxes.append((x, y, w, h))
    boxes.sort(key=lambda b: b[0])
    return boxes


def read_value(
    frame: np.ndarray, templates: dict[int, list[np.ndarray]], cfg: DetectionConfig
) -> GaugeReading:
    if not templates:
        return GaugeReading(None, 0.0)
    crop = crop_gauge(frame, cfg)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    binary = binarize(gray)

    boxes = digit_boxes(binary, cfg)
    if any(w > cfg.max_digit_width for _, _, w, _ in boxes):
        return GaugeReading(None, 0.0)   # merged digits (motion blur) -> unreliable frame

    digits: list[int] = []
    scores: list[float] = []
    for x, y, w, h in boxes:
        m = match_digit(binary[y : y + h, x : x + w], templates)
        if m.score >= cfg.match_threshold:   # keep digits, drop arc fragments
            digits.append(m.digit)
            scores.append(m.score)

    if not digits:
        return GaugeReading(None, 0.0)
    value = int("".join(str(d) for d in digits))
    if value > cfg.full_value:        # boost can't exceed 100 -> misread, discard
        return GaugeReading(None, 0.0)
    return GaugeReading(value, min(scores))
