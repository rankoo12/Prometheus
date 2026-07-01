"""Diagnostic: burn a visible GOAL marker onto clips at each detected goal, for review.

Pure validation aid (not the render pipeline): for every clip it detects goals and burns a
green "GOAL blue->N" banner (over the facecam, so it never hides the action) around each
detected time, so you can scrub straight to them and confirm. Clips with no detected goal are
listed but not re-encoded (watch the original to check for a missed, replay-only goal).

Usage:
    python -m backend.tools.goal_preview                     # all of samples/ -> goal_previews/
    python -m backend.tools.goal_preview "<clip>" [out_dir]  # one clip
"""
from __future__ import annotations

import argparse
import glob
from pathlib import Path

from backend.detection.goal_config import GoalConfig
from backend.detection.scoreboard import load_bank
from backend.detection.scorer import GoalScorer, load_templates
from backend.models.instruction import EditInstruction, InstructionKind
from backend.render.ass_builder import build_ass
from backend.render.renderer import burn_overlay
from backend.sources.goal_source import GoalSource

_DET = Path(__file__).resolve().parents[1] / "detection"
_BANK = _DET / "score_templates"
_NAME = _DET / "scorer_templates" / "name"
_POPUP = _DET / "scorer_templates" / "popup"
_MARKER = {"color": "#2BFF66", "outline_color": "#000000", "outline_width": 4, "size": 76}


def _label(e) -> str:
    """Marker text: YOU (you scored), ASSIST (teammate scored), or OPP (opponent goal)."""
    if e.metadata.get("side") != "your_team":
        return "OPP"
    return "YOU" if e.metadata.get("scorer") == "you" else "ASSIST"


def _instructions(events, width):
    out = []
    for e in events:
        score = e.metadata.get("score", "?")
        out.append(
            EditInstruction(
                kind=InstructionKind.ASS_OVERLAY,
                t_start=max(0.0, e.t_start - 0.3),
                t_end=e.t_start + 3.0,
                payload={
                    "text": f"GOAL  {_label(e)}->{score}",
                    "x": width // 2,
                    "y": 300,          # over the facecam (top); keeps gameplay clear
                    "animation": {},
                    **_MARKER,
                },
            )
        )
    return out


def _preview_one(clip: str, out_dir: Path, bank, scorer, cfg: GoalConfig) -> None:
    import cv2

    cap = cv2.VideoCapture(clip)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    cap.release()

    events = GoalSource(clip, bank, cfg, scorer=scorer).detect()
    name = Path(clip).stem
    if not events:
        print(f"  {name}: no goals (not rendered)")
        return
    summary = ", ".join(f"{_label(e)}->{e.metadata['score']}@{e.t_start:.1f}s" for e in events)
    out_path = out_dir / f"{name}__goals.mp4"
    ass = build_ass(_instructions(events, w), w, h, font="Arial")
    burn_overlay(clip, ass, str(out_path))
    print(f"  {name}: {summary}  ->  {out_path.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", nargs="?", default=None)
    ap.add_argument("out_dir", nargs="?", default="goal_previews")
    args = ap.parse_args()

    cfg = GoalConfig()
    bank = load_bank(_BANK)
    scorer = GoalScorer(load_templates(_NAME), load_templates(_POPUP), cfg)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    clips = [args.clip] if args.clip else sorted(glob.glob("samples/*.mp4"))
    print(f"writing previews to {out_dir}/ ...")
    for clip in clips:
        _preview_one(clip, out_dir, bank, scorer, cfg)
    print("done.")


if __name__ == "__main__":
    main()
