"""Digit template matching for the boost gauge (spec §6.1) — not general OCR."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DigitMatch:
    digit: int          # 0-9, or -1 if nothing matched
    score: float        # normalized-correlation peak, in [-1.0, 1.0]


def match_digit(cell: np.ndarray, templates: dict[int, np.ndarray]) -> DigitMatch:
    """Best-matching digit for a single digit-cell image, via normalized
    cross-correlation against each 0-9 template."""
    best = DigitMatch(-1, -1.0)
    for digit, template in templates.items():
        score = _score(cell, template)
        if score > best.score:
            best = DigitMatch(digit, score)
    return best


def _score(cell: np.ndarray, template: np.ndarray) -> float:
    """TM_CCOEFF_NORMED with the template resized to the cell (scale-tolerant)."""
    ch, cw = cell.shape[:2]
    th, tw = template.shape[:2]
    if (th, tw) != (ch, cw):
        template = cv2.resize(template, (cw, ch), interpolation=cv2.INTER_AREA)
    result = cv2.matchTemplate(cell, template, cv2.TM_CCOEFF_NORMED)
    return float(result.max())
