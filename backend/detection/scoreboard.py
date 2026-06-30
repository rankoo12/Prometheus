"""Scoreboard CV helpers (spec §6.2) -- read a score digit by SHAPE, robust to the
semi-transparent score box (background bleed defeats naive pixel counting).

`read_score` binarizes the box, crops to the digit, and 1-NN matches it against a small
multi-exemplar bank (same technique as the boost reader). The stable-run / increment logic
that consumes the per-frame values lives in `sources/goal_source.py` and is pure.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.detection.goal_config import GoalConfig, ScoreRegion

_CANON = (20, 28)  # canonical (w, h) every digit crop is resized to before matching


def canon_digit(crop, bin_threshold: int) -> np.ndarray | None:
    """Binarize a score-box crop and return the digit as a canonical float mask, or None
    if no plausible single digit is present (absent scoreboard / replay / garbage)."""
    import cv2

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, b = cv2.threshold(gray, bin_threshold, 255, cv2.THRESH_BINARY)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.where(b > 0)
    if len(xs) < 25:
        return None
    sub = b[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = sub.shape
    if h < 20 or w < 6 or w > h:           # a digit is clearly taller than wide; reject merges/specks
        return None
    return cv2.resize(sub, _CANON, interpolation=cv2.INTER_AREA).astype(np.float32)


def load_bank(path: str | Path) -> dict[int, list[np.ndarray]]:
    """Load the scoreboard digit bank: <digit>_*.png canonical glyphs grouped by value."""
    import cv2

    bank: dict[int, list[np.ndarray]] = {}
    for p in sorted(Path(path).glob("*.png")):
        digit = int(p.name[0])
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        bank.setdefault(digit, []).append(img.astype(np.float32))
    return bank


def _match(canon: np.ndarray, bank: dict[int, list[np.ndarray]]) -> tuple[int | None, float]:
    import cv2

    best, best_score = None, -2.0
    for digit, exemplars in bank.items():
        for tpl in exemplars:
            s = float(cv2.matchTemplate(canon, tpl, cv2.TM_CCOEFF_NORMED)[0, 0])
            if s > best_score:
                best_score, best = s, digit
    return best, best_score


def read_score(frame, region: ScoreRegion, bank: dict[int, list[np.ndarray]],
               cfg: GoalConfig) -> tuple[int | None, float]:
    """Read one score box -> (value, match_score). Returns (None, score) when no digit is
    found or the best match is below cfg.min_match (so callers can treat it as 'no reading')."""
    crop = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    canon = canon_digit(crop, cfg.bin_threshold)
    if canon is None:
        return None, 0.0
    digit, score = _match(canon, bank)
    if score < cfg.min_match:
        return None, score
    return digit, score
