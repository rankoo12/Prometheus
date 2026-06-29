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


_CANON = (16, 24)  # canonical (w, h): both glyphs shrink to a low-res fingerprint


def _score(cell: np.ndarray, template: np.ndarray) -> float:
    """Normalized correlation of canonical-size grayscale fingerprints.

    Resizing both to a small fixed size (INTER_AREA) makes the score tolerant of
    stroke thickness and slight misalignment. The variance guard returns 0 for an
    empty cell or template, so a blank glyph can never match everything.
    """
    c = cv2.resize(cell, _CANON, interpolation=cv2.INTER_AREA).astype(np.float32)
    t = cv2.resize(template, _CANON, interpolation=cv2.INTER_AREA).astype(np.float32)
    if c.std() < 1e-3 or t.std() < 1e-3:
        return 0.0
    return float(cv2.matchTemplate(c, t, cv2.TM_CCOEFF_NORMED)[0, 0])
