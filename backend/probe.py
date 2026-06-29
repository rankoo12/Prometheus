"""ffprobe wrapper: read a clip's duration/width/height/fps (spec §5.2).

ffprobe discovery: PROMETHEUS_FFPROBE env override -> PATH lookup -> clear error.
Never hardcoded.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _ffprobe_path() -> str:
    override = os.environ.get("PROMETHEUS_FFPROBE")
    if override:
        if Path(override).is_file():
            return override
        raise FileNotFoundError(f"PROMETHEUS_FFPROBE points at a missing file: {override}")
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FileNotFoundError(
        "ffprobe not found. Install ffmpeg and put it on PATH, or set PROMETHEUS_FFPROBE."
    )


def _parse_fraction(value: str | None) -> float:
    """ffprobe frame rates are fractions like '60/1' or '60000/1001'."""
    if not value:
        return 0.0
    try:
        num, _, den = value.partition("/")
        numerator = float(num)
        denominator = float(den) if den else 1.0
        return numerator / denominator if denominator else 0.0
    except ValueError:
        return 0.0


def probe(clip_path: str) -> dict[str, Any]:
    """Return {duration, width, height, fps} for a video clip."""
    path = Path(clip_path)
    if not path.is_file():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    cmd = [
        _ffprobe_path(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {completed.stderr.strip()}")

    data = json.loads(completed.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("No video stream found in clip")

    duration_raw = data.get("format", {}).get("duration") or video.get("duration")
    fps = _parse_fraction(video.get("r_frame_rate") or video.get("avg_frame_rate"))

    return {
        "duration": float(duration_raw) if duration_raw else 0.0,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
    }
