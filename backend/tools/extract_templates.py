"""Dump boost-gauge crops from a clip so digit templates can be picked by eye.

Usage:
    python -m backend.tools.extract_templates <clip> <out_dir> [--every N]

Saves the gauge-region crop every N frames as PNGs in <out_dir>. Eyeball them, then
save clean single-digit glyphs as backend/detection/templates/0.png..9.png.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from backend.detection.config import DetectionConfig
from backend.detection.gauge import crop_gauge


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out_dir")
    ap.add_argument("--every", type=int, default=15, help="save every Nth frame")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cfg = DetectionConfig()

    cap = cv2.VideoCapture(args.clip)
    if not cap.isOpened():
        raise SystemExit(f"Could not open clip: {args.clip}")

    idx = saved = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % args.every == 0:
                cv2.imwrite(str(out / f"gauge_{idx:05d}.png"), crop_gauge(frame, cfg))
                saved += 1
            idx += 1
    finally:
        cap.release()
    print(f"saved {saved} gauge crops to {out}  (region={cfg.gauge})")


if __name__ == "__main__":
    main()
