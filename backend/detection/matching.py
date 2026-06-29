"""Digit template matching for the boost gauge (spec §6.1) — not general OCR."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DigitMatch:
    digit: int          # 0-9, or -1 if nothing matched
    score: float        # normalized-correlation peak, in [-1.0, 1.0]


def match_digit(cell: np.ndarray, templates: dict[int, list[np.ndarray]]) -> DigitMatch:
    """1-NN over prepared exemplar fingerprints. `templates` values must already be
    prepared (load_templates does this); the cell is prepared once here."""
    cell_fp = prepare(cell)
    best = DigitMatch(-1, -1.0)
    for digit, exemplars in templates.items():
        for tpl_fp in exemplars:
            score = _score(cell_fp, tpl_fp)
            if score > best.score:
                best = DigitMatch(digit, score)
    return best


_CANON = (16, 24)  # canonical (w, h): glyphs shrink to a low-res fingerprint


def prepare(glyph: np.ndarray) -> np.ndarray:
    """Canonical-size float fingerprint of a binary glyph. Templates are prepared ONCE
    at load (load_templates); only the cell is prepared per match. Shrinking to a small
    fixed size (INTER_AREA) tolerates stroke thickness and slight misalignment."""
    return cv2.resize(glyph, _CANON, interpolation=cv2.INTER_AREA).astype(np.float32)


def _score(cell_fp: np.ndarray, tpl_fp: np.ndarray) -> float:
    """Normalized correlation of two prepared fingerprints. The variance guard returns
    0 for an empty cell/template, so a blank glyph can never match everything."""
    if cell_fp.std() < 1e-3 or tpl_fp.std() < 1e-3:
        return 0.0
    return float(cv2.matchTemplate(cell_fp, tpl_fp, cv2.TM_CCOEFF_NORMED)[0, 0])
