"""Print the boost-pickup timeline for a clip (Phase 1 test harness, spec §10).

Usage:
    python -m backend.tools.boost_timeline <clip> [templates_dir]

templates_dir defaults to backend/detection/templates.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.detection.config import DetectionConfig
from backend.detection.gauge import load_templates
from backend.sources.boost_source import BoostSource

_DEFAULT_TEMPLATES = Path(__file__).resolve().parents[1] / "detection" / "templates"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("templates_dir", nargs="?", default=str(_DEFAULT_TEMPLATES))
    args = ap.parse_args()

    templates = load_templates(args.templates_dir)
    if not templates:
        print(f"WARNING: no templates in {args.templates_dir} — values will be unreadable")

    events = BoostSource(args.clip, templates, DetectionConfig()).detect()
    print(f"{len(events)} boost pickup(s):")
    for e in events:
        print(f"  t={e.t_start:7.3f}s  +{e.metadata['amount']:<3} conf={e.metadata['confidence']}")


if __name__ == "__main__":
    main()
