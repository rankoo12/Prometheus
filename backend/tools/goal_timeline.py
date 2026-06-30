"""Diagnostic: print the detected GOAL timeline for a clip (text).

Usage: python -m backend.tools.goal_timeline "<clip>" [goal_config.json]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.detection.goal_config import GoalConfig
from backend.detection.scoreboard import load_bank
from backend.detection.scorer import GoalScorer, load_templates
from backend.sources.goal_source import GoalSource

_DET = Path(__file__).resolve().parents[1] / "detection"
_BANK = _DET / "score_templates"
_NAME = _DET / "scorer_templates" / "name"
_POPUP = _DET / "scorer_templates" / "popup"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("config", nargs="?", default=None)
    args = ap.parse_args()

    cfg = GoalConfig.load(args.config)
    bank = load_bank(_BANK)
    scorer = GoalScorer(load_templates(_NAME), load_templates(_POPUP), cfg)
    events = GoalSource(args.clip, bank, cfg, scorer=scorer, verbose=True).detect()

    if not events:
        print("no goals detected.")
        return
    print(f"{len(events)} goal(s):")
    for e in events:
        side = e.metadata.get("side", "?")
        score = e.metadata.get("score", "?")
        who = e.metadata.get("scorer", "-")
        print(f"  {e.t_start:6.2f}s  {side:<9} -> {score}   scorer={who}")


if __name__ == "__main__":
    main()
