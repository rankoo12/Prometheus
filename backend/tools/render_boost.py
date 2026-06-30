"""Phase 2 end-to-end: render a clip with the boost +12/+100 pop overlays burned in.

Usage:
    python -m backend.tools.render_boost <clip> [out.mp4] [profile.json]

Pipeline: BoostSource (detect) -> BoostHandler (ASS overlay instructions, Profile-styled)
-> ass_builder (.ass) -> Renderer (FFmpeg burn). Output preserves source resolution.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.detection.config import DetectionConfig
from backend.detection.gauge import load_templates
from backend.handlers.boost_handler import BoostHandler
from backend.models.profile import Profile
from backend.render.ass_builder import build_ass
from backend.render.renderer import burn_overlay
from backend.sources.boost_source import BoostSource

_TEMPLATES = Path(__file__).resolve().parents[1] / "detection" / "templates"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out", nargs="?", default="boost_render.mp4")
    ap.add_argument("profile", nargs="?", default=None)
    args = ap.parse_args()

    cfg = DetectionConfig()
    templates = load_templates(str(_TEMPLATES))
    profile = Profile.load(args.profile)

    print("detecting pickups...", flush=True)
    events = BoostSource(args.clip, templates, cfg, verbose=True).detect()
    instructions = BoostHandler(cfg.gauge).handle(events, profile)
    out_cfg = profile.data["output"]
    ass = build_ass(instructions, out_cfg["width"], out_cfg["height"], font="Arial")

    print(f"{len(events)} pickups; burning overlay -> {args.out} ...", flush=True)
    burn_overlay(args.clip, ass, args.out, crf=int(out_cfg.get("crf", 19)))
    print("done:", args.out)


if __name__ == "__main__":
    main()
