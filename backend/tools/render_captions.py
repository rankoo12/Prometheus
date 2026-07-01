"""Phase 4 end-to-end: render a clip with karaoke captions burned in.

Usage:
    python -m backend.tools.render_captions <clip> [out.mp4] [profile.json]

Pipeline: CaptionSource (Whisper word-timing) -> CaptionHandler (karaoke overlays, Profile-styled)
-> ass_builder (.ass) -> Renderer (FFmpeg burn).
"""
from __future__ import annotations

import argparse

from backend.detection.caption_config import CaptionConfig
from backend.handlers.caption_handler import CaptionHandler
from backend.models.profile import Profile
from backend.render.ass_builder import build_ass
from backend.render.renderer import burn_overlay
from backend.sources.caption_source import CaptionSource


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out", nargs="?", default="caption_render.mp4")
    ap.add_argument("profile", nargs="?", default=None)
    args = ap.parse_args()

    profile = Profile.load(args.profile)
    lang = profile.data["captions"].get("language", "en")

    print("transcribing...", flush=True)
    events = CaptionSource(args.clip, CaptionConfig(), language=lang, verbose=True).detect()
    instructions = CaptionHandler().handle(events, profile)
    out_cfg = profile.data["output"]
    ass = build_ass(instructions, out_cfg["width"], out_cfg["height"], font="Arial")

    print(f"{len(events)} words, {len(instructions)} caption lines; burning -> {args.out} ...", flush=True)
    burn_overlay(args.clip, ass, args.out, crf=int(out_cfg.get("crf", 19)))
    print("done:", args.out)


if __name__ == "__main__":
    main()
