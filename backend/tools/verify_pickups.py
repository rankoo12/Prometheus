"""Visual verifier for boost detection.

Usage:
    python -m backend.tools.verify_pickups <clip> [out.png] [templates_dir]

Runs BoostSource on the clip and writes a montage: one row per detected pickup,
showing the gauge crop across ~+/-0.25s around the event (so you can see the number
rise), with the per-frame read value overlaid (green) and the event time + amount
labeled. Open the PNG to confirm every detection without scrubbing the video.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from backend.detection.config import DetectionConfig
from backend.detection.gauge import crop_gauge, load_templates, read_value
from backend.sources.boost_source import BoostSource

OFFSETS = [-0.25, -0.12, 0.0, 0.12, 0.25]  # seconds, relative to each event
_DEFAULT_TEMPLATES = Path(__file__).resolve().parents[1] / "detection" / "templates"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("out", nargs="?", default="pickups.png")
    ap.add_argument("templates_dir", nargs="?", default=str(_DEFAULT_TEMPLATES))
    args = ap.parse_args()

    cfg = DetectionConfig()
    templates = load_templates(args.templates_dir)
    events = BoostSource(args.clip, templates, cfg).detect()
    if not events:
        print("no pickups detected")
        return

    cap = cv2.VideoCapture(args.clip)
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0

    # Map each needed frame index -> the (event, column) slots it fills.
    targets: dict[int, list[tuple[int, int]]] = {}
    for ei, e in enumerate(events):
        for oi, off in enumerate(OFFSETS):
            fidx = max(0, int(round((e.t_start + off) * fps)))
            targets.setdefault(fidx, []).append((ei, oi))

    g = cfg.gauge
    cells: dict[tuple[int, int], np.ndarray] = {}
    fi, last = 0, max(targets)
    while fi <= last:
        ok, fr = cap.read()
        if not ok:
            break
        if fi in targets:
            crop = crop_gauge(fr, cfg).copy()
            val = read_value(fr, templates, cfg).value
            cv2.putText(crop, str(val), (2, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            for slot in targets[fi]:
                cells[slot] = crop
        fi += 1
    cap.release()

    label_w = 150
    rows = []
    for ei, e in enumerate(events):
        strip = np.hstack(
            [cells.get((ei, oi), np.zeros((g.h, g.w, 3), np.uint8)) for oi in range(len(OFFSETS))]
        )
        label = np.zeros((g.h, label_w, 3), np.uint8)
        cv2.putText(label, f"{e.t_start:.2f}s", (4, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(label, f"+{e.metadata['amount']}", (4, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
        rows.append(np.hstack([label, strip]))
    cv2.imwrite(args.out, np.vstack(rows))
    print(f"{len(events)} pickups -> {args.out}  (columns span t{OFFSETS}s; green = read value)")


if __name__ == "__main__":
    main()
