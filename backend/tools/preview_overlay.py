"""Preview: render the clip with detected +12/+100 markers burned in, to eyeball
detection by watching. A test/preview tool (NOT the Phase 2 renderer).

Usage:
    python -m backend.tools.preview_overlay <clip> [out.mp4] [--scale 0.5]

Each detected pickup shows its amount (cyan +100, amber +12) for ~0.8s. Output is
downscaled by default for speed; play it and check the markers land on real grabs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from backend.detection.config import DetectionConfig
from backend.detection.gauge import load_templates
from backend.sources.boost_source import BoostSource

HOLD_S = 0.8  # how long each marker stays on screen
_DEFAULT_TEMPLATES = Path(__file__).resolve().parents[1] / "detection" / "templates"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out", nargs="?", default="preview.mp4")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--templates", default=str(_DEFAULT_TEMPLATES))
    args = ap.parse_args()

    cfg = DetectionConfig()
    templates = load_templates(args.templates)
    print("detecting pickups...", flush=True)
    events = BoostSource(args.clip, templates, cfg, verbose=True).detect()
    print(f"{len(events)} pickups; rendering preview...", flush=True)
    windows = [(e.t_start, e.t_start + HOLD_S, int(e.metadata["amount"])) for e in events]

    cap = cv2.VideoCapture(args.clip)
    if not cap.isOpened():
        raise SystemExit(f"Could not open clip: {args.clip}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * args.scale)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * args.scale)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    out = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    idx = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        fr = cv2.resize(fr, (w, h))
        t = idx / fps
        for t0, t1, amt in windows:
            if t0 <= t <= t1:
                color = (255, 255, 0) if amt >= 100 else (0, 220, 255)  # BGR: cyan / amber
                g = cfg.gauge  # place just above the boost gauge (preview of the Profile anchor)
                org = (int(g.x * args.scale), int((g.y - 55) * args.scale))
                fs = h / 760
                cv2.putText(fr, f"+{amt}", org, cv2.FONT_HERSHEY_DUPLEX, fs, (0, 0, 0), 6)
                cv2.putText(fr, f"+{amt}", org, cv2.FONT_HERSHEY_DUPLEX, fs, color, 2)
                break
        out.write(fr)
        if total and idx % 200 == 0:
            sys.stderr.write(f"\r  rendering {idx}/{total} ...")
            sys.stderr.flush()
        idx += 1
    cap.release()
    out.release()
    sys.stderr.write("\r  done.                         \n")
    print(f"wrote {args.out}  ({len(events)} markers)")


if __name__ == "__main__":
    main()
