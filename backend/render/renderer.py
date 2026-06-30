"""Renderer — burn ASS overlays onto a clip with FFmpeg (spec §8; Phase 2 subset).

Phase 2 renders the overlay burn only (no audio mix, no concat — those are later phases).
ffmpeg discovery: PROMETHEUS_FFMPEG env override -> PATH -> clear error. Preserves the
source resolution/fps (never downscale, spec §8).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _ffmpeg_path() -> str:
    override = os.environ.get("PROMETHEUS_FFMPEG")
    if override:
        if Path(override).is_file():
            return override
        raise FileNotFoundError(f"PROMETHEUS_FFMPEG points at a missing file: {override}")
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError("ffmpeg not found. Install ffmpeg and put it on PATH, or set PROMETHEUS_FFMPEG.")


def burn_overlay(clip_path: str, ass_text: str, out_path: str, crf: int = 19) -> str:
    """Burn an ASS document onto the clip. Returns out_path.

    The .ass is written into a temp dir and FFmpeg runs with cwd = that dir, so the
    subtitles filter takes a bare filename — sidestepping Windows filtergraph path
    escaping (drive colons, backslashes) entirely.
    """
    ff = _ffmpeg_path()
    clip_abs = os.path.abspath(clip_path)
    out_abs = os.path.abspath(out_path)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "overlay.ass").write_text(ass_text, encoding="utf-8")
        cmd = [
            ff, "-y", "-i", clip_abs,
            "-vf", "subtitles=overlay.ass",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast",
            "-c:a", "copy", "-movflags", "+faststart",
            out_abs,
        ]
        proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (code {proc.returncode}):\n{proc.stderr[-2000:]}")
    return out_abs
