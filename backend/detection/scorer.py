"""Personal-scorer detection (spec §6.2) — did the USER score a team goal, or a teammate?

Layered on top of the team-level GoalSource. For each of the user's TEAM goals we decide
"you" vs "teammate" by scanning a window around the goal for two shape-matched signals:

  PRIMARY — the "<NAME> SCORED!" banner matching the user's name. It appears right at the
            goal, so it survives clips that end seconds after scoring. The name templates are
            user-specific (one image = one name), NOT full-alphabet OCR. The directory they
            load from is the single swap point for a future "register your name" feature.
  BACKUP  — the "GOAL +100" points popup (only awarded when you personally score). It appears
            ~2-3s after the goal, so it can miss short clips on its own; it covers cases where
            the banner is unclear and is name-independent (works for any user).

Both are binary template correlations, robust to the HUD's semi-transparent background bleed.
The score-time can lag the real goal, so the window reaches further BEFORE the goal than after.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.detection.goal_config import GoalConfig


def load_templates(path: str | Path) -> list[np.ndarray]:
    """Load binary glyph templates (grayscale PNGs) from a directory."""
    import cv2

    out: list[np.ndarray] = []
    for p in sorted(Path(path).glob("*.png")):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            out.append(img)
    return out


def _binw(crop, threshold: int) -> np.ndarray:
    import cv2

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, b = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return b


def _best_match(region_bin: np.ndarray, templates: list[np.ndarray]) -> float:
    """Highest normalized correlation of any template within the (larger) region, or -1."""
    import cv2

    best = -1.0
    for tpl in templates:
        if region_bin.shape[0] >= tpl.shape[0] and region_bin.shape[1] >= tpl.shape[1]:
            best = max(best, float(cv2.matchTemplate(region_bin, tpl, cv2.TM_CCOEFF_NORMED).max()))
    return best


def decide(best_name: float, best_popup: float, cfg: GoalConfig) -> tuple[str, float]:
    """Pure classification from the two best correlations -> ("you" | "teammate", confidence)."""
    you = best_name >= cfg.name_match or best_popup >= cfg.popup_match
    return ("you" if you else "teammate"), round(max(best_name, best_popup), 3)


class GoalScorer:
    """Classifies one TEAM goal as scored by the user ("you") or a teammate."""

    def __init__(self, name_templates: list[np.ndarray], popup_templates: list[np.ndarray],
                 cfg: GoalConfig | None = None) -> None:
        self.name_templates = name_templates
        self.popup_templates = popup_templates
        self.cfg = cfg or GoalConfig()

    def classify(self, clip_path: str, goal_time: float) -> tuple[str, float]:
        """Scan a window around `goal_time` for the name banner (primary) and +100 popup
        (backup); return ("you" | "teammate", confidence)."""
        import cv2

        cfg = self.cfg
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open clip: {clip_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        fr0 = max(0, int((goal_time - cfg.scorer_before_s) * fps))
        fr1 = int((goal_time + cfg.scorer_after_s) * fps)
        if total:
            fr1 = min(fr1, total)
        best_name = best_popup = -1.0
        b, p = cfg.banner, cfg.popup
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr0)
        idx = fr0
        try:
            while idx < fr1:
                if (idx - fr0) % cfg.scorer_stride == 0:
                    ok, f = cap.read()
                    if not ok:
                        break
                    breg = _binw(f[b.y:b.y + b.h, b.x:b.x + b.w], cfg.banner_bin)
                    best_name = max(best_name, _best_match(breg, self.name_templates))
                    preg = _binw(f[p.y:p.y + p.h, p.x:p.x + p.w], cfg.popup_bin)
                    best_popup = max(best_popup, _best_match(preg, self.popup_templates))
                elif not cap.grab():
                    break
                idx += 1
        finally:
            cap.release()
        return decide(best_name, best_popup, cfg)
