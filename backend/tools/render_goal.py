"""Phase 3 end-to-end: render a clip with the goal effect (flash + "GOAL!" pop) burned in.

Usage:
    python -m backend.tools.render_goal <clip> [out.mp4] [profile.json]

Pipeline: GoalSource (+ GoalScorer) -> GoalHandler (flash + text instructions, Profile-styled)
-> ass_builder (.ass) -> Renderer (FFmpeg burn). Celebrates your_goals by default (Profile scope).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.detection.goal_config import GoalConfig
from backend.detection.scoreboard import load_bank
from backend.detection.scorer import GoalScorer, load_templates
from backend.handlers.goal_handler import GoalHandler
from backend.models.profile import Profile
from backend.render.renderer import render
from backend.sources.goal_source import GoalSource

_DET = Path(__file__).resolve().parents[1] / "detection"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out", nargs="?", default="goal_render.mp4")
    ap.add_argument("profile", nargs="?", default=None)
    args = ap.parse_args()

    cfg = GoalConfig()
    bank = load_bank(_DET / "score_templates")
    scorer = GoalScorer(load_templates(_DET / "scorer_templates" / "name"),
                        load_templates(_DET / "scorer_templates" / "popup"), cfg)
    profile = Profile.load(args.profile)

    print("detecting goals...", flush=True)
    events = GoalSource(args.clip, bank, cfg, scorer=scorer, verbose=True).detect()
    instructions = GoalHandler().handle(events, profile)
    out_cfg = profile.data["output"]

    celebrated = sum(1 for e in events if e.metadata.get("scorer") == "you")
    print(f"{len(events)} goal(s), {celebrated} celebrated; rendering -> {args.out} ...", flush=True)
    render(args.clip, instructions, out_cfg["width"], out_cfg["height"], args.out,
           crf=int(out_cfg.get("crf", 19)), font="Arial", fps=int(out_cfg.get("fps", 60)))
    print("done:", args.out)


if __name__ == "__main__":
    main()
