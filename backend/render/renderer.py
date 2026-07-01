"""Renderer — burn ASS overlays (and apply slow-motion retiming) with FFmpeg (spec §8).

`burn_overlay` is the overlay-only path (no timeline change). `render` is the general entry:
it takes the full instruction list, and when RETIME_SEGMENTs are present it splits/retimes the
clip (setpts/atempo + concat), re-times the overlays onto the output timeline, and burns them.
ffmpeg discovery: PROMETHEUS_FFMPEG env override -> PATH -> clear error. Preserves the source
resolution/fps (never downscale, spec §8).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.models.instruction import EditInstruction, InstructionKind
from backend.render.ass_builder import build_ass
from backend.render.retime import build_filter, remap_overlays, segments_from


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


def _has_audio(clip_abs: str) -> bool:
    """True if the clip has at least one audio stream (probed via ffprobe; assume yes if the
    probe is unavailable — the retime path just maps [aout] which the clips carry)."""
    probe = os.environ.get("PROMETHEUS_FFPROBE") or shutil.which("ffprobe")
    if not probe:
        return True
    proc = subprocess.run(
        [probe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", clip_abs],
        capture_output=True, text=True,
    )
    return bool(proc.stdout.strip())


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


def render(clip_path: str, instructions: list[EditInstruction], width: int, height: int,
           out_path: str, crf: int = 19, font: str = "Arial", fps: int | None = None,
           music_path: str | None = None, music_gain_db: float = 0.0, duck: bool = False,
           norm_lufs: float | None = None, true_peak: float = -1.0) -> str:
    """Render a clip with overlays, optional slow-motion retiming, and optional music.

    With no RETIME_SEGMENTs and no music this is the plain overlay burn. Otherwise it runs a
    filtergraph: the clip is split/retimed (overlays re-timed onto the output timeline first),
    and a looped `music_path` is mixed under the voice (gain, sidechain-ducked when `duck`) then
    loudness-normalized to `norm_lufs`/`true_peak`. `fps` forces CFR (the slowed span is VFR)."""
    segments = segments_from(instructions)
    overlays = [i for i in instructions if i.kind is InstructionKind.ASS_OVERLAY]
    ff = _ffmpeg_path()
    clip_abs, out_abs = os.path.abspath(clip_path), os.path.abspath(out_path)
    has_audio = _has_audio(clip_abs)
    use_music = bool(music_path) and has_audio          # music mix needs the voice track
    # the audio needs the filtergraph whenever we mix music OR loudness-normalize
    need_audio_filter = has_audio and (use_music or norm_lufs is not None)

    if not segments and not need_audio_filter:          # fast path: just burn overlays, copy audio
        return burn_overlay(clip_path, build_ass(overlays, width, height, font), out_path, crf)

    ass = build_ass(remap_overlays(overlays, segments), width, height, font)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "overlay.ass").write_text(ass, encoding="utf-8")
        filt = build_filter(segments, "overlay.ass", has_audio, music=use_music,
                            music_gain_db=music_gain_db, duck=duck,
                            norm_lufs=norm_lufs, true_peak=true_peak)
        cmd = [ff, "-y", "-i", clip_abs]
        if use_music:
            cmd += ["-stream_loop", "-1", "-i", os.path.abspath(music_path)]
        cmd += ["-filter_complex", filt, "-map", "[vout]"]
        if has_audio:
            cmd += ["-map", "[aout]"]
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast"]
        if fps:
            cmd += ["-r", str(fps)]                     # force CFR (slowed span is VFR otherwise)
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]   # loudnorm can emit odd rates
        cmd += ["-movflags", "+faststart", out_abs]
        proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (code {proc.returncode}):\n{proc.stderr[-2000:]}")
    return out_abs
