"""Phase 5: full export — every effect (boost + goal + captions + slow-mo) in ONE render.

Usage:
    python -m backend.tools.render_all <clip> [out.mp4] [profile.json]
"""
from __future__ import annotations

import argparse

from backend.models.profile import Profile
from backend.pipeline import export


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out", nargs="?", default="export.mp4")
    ap.add_argument("profile", nargs="?", default=None)
    args = ap.parse_args()

    profile = Profile.load(args.profile)
    print("full export (boost + goal + captions + slow-mo)...", flush=True)
    export(args.clip, profile, args.out, verbose=True)
    print("done:", args.out)


if __name__ == "__main__":
    main()
