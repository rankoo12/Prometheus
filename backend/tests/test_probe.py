"""Tests for the ffprobe wrapper.

The end-to-end probe test generates a tiny clip with ffmpeg and is skipped if ffmpeg /
ffprobe are unavailable. The parsing + error-path tests are pure unit tests.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.probe import _parse_fraction, probe


def test_parse_fraction_simple():
    assert _parse_fraction("60/1") == 60.0


def test_parse_fraction_ntsc():
    assert _parse_fraction("60000/1001") == pytest.approx(59.94, abs=0.01)


def test_parse_fraction_degenerate():
    assert _parse_fraction("0/0") == 0.0
    assert _parse_fraction(None) == 0.0
    assert _parse_fraction("") == 0.0


def test_probe_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        probe("does_not_exist_12345.mp4")


def _have_ffprobe() -> bool:
    return bool(os.environ.get("PROMETHEUS_FFPROBE")) or shutil.which("ffprobe") is not None


@pytest.mark.skipif(
    not (shutil.which("ffmpeg") and _have_ffprobe()),
    reason="ffmpeg/ffprobe not available",
)
def test_probe_real_clip(tmp_path: Path):
    clip = tmp_path / "sample.mp4"
    # 1s, 1080x1920, 60fps test pattern — matches the project's target format.
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=60:duration=1",
            "-pix_fmt", "yuv420p",
            str(clip),
        ],
        check=True,
    )
    info = probe(str(clip))
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["fps"] == pytest.approx(60.0, abs=0.01)
    assert info["duration"] == pytest.approx(1.0, abs=0.2)
