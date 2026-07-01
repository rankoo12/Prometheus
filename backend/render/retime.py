"""Retiming math + FFmpeg filtergraph for slow-motion segments (spec §7.2, §8).

A RETIME_SEGMENT slows (or speeds) a span [a, b] of the INPUT clip by `speed` (0.5 = half
speed → the span plays for twice as long). This changes the clip's duration and therefore
shifts the OUTPUT timestamp of everything after `a`. `remap_time` is the pure mapping from an
input second to its output second given the segments; `remap_overlays` re-times overlay
instructions onto the output timeline (start moves, wall-clock duration is preserved). Segments
must be sorted and non-overlapping. This module is pure except `build_filter`, which emits an
FFmpeg `filter_complex` string (no ffmpeg call here).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.models.instruction import EditInstruction, InstructionKind


@dataclass(frozen=True)
class Segment:
    start: float   # input seconds
    end: float     # input seconds
    speed: float   # 0.5 = half speed (span lasts 1/speed as long in the output)


def segments_from(instructions: list[EditInstruction]) -> list[Segment]:
    """Extract sorted RETIME_SEGMENT instructions as Segments."""
    segs = [
        Segment(i.t_start, i.t_end if i.t_end is not None else i.t_start, float(i.payload.get("speed", 1.0)))
        for i in instructions
        if i.kind is InstructionKind.RETIME_SEGMENT
    ]
    return sorted(segs, key=lambda s: s.start)


def remap_time(t: float, segments: list[Segment]) -> float:
    """Map an input time (s) to its output time (s) after the segments are retimed."""
    out = t
    for s in segments:
        if t <= s.start:
            break                       # segments are sorted; none from here on affects t
        span = s.end - s.start
        if t >= s.end:
            out += span / s.speed - span            # fully past: add the whole stretch
        else:
            inside = t - s.start
            out += inside / s.speed - inside        # partway in: add the partial stretch
    return out


def remap_overlays(overlays: list[EditInstruction], segments: list[Segment]) -> list[EditInstruction]:
    """Re-time overlay instructions onto the output timeline: the start is remapped; the
    wall-clock duration is preserved (an overlay is a fixed-length pop, not stretched)."""
    if not segments:
        return overlays
    out: list[EditInstruction] = []
    for inst in overlays:
        dur = (inst.t_end - inst.t_start) if inst.t_end is not None else 0.0
        new_start = remap_time(inst.t_start, segments)
        out.append(
            EditInstruction(
                kind=inst.kind,
                t_start=new_start,
                t_end=new_start + dur if inst.t_end is not None else None,
                payload=inst.payload,
            )
        )
    return out


def _atempo_chain(speed: float) -> str:
    """atempo supports [0.5, 100]; chain factors for slower speeds (e.g. 0.25 = 0.5,0.5)."""
    factors: list[float] = []
    s = speed
    while s < 0.5:
        factors.append(0.5)
        s /= 0.5
    factors.append(s)
    return ",".join(f"atempo={f:g}" for f in factors)


def build_filter(segments: list[Segment], ass_name: str, has_audio: bool = True) -> str:
    """FFmpeg filter_complex: split the clip at each segment boundary, retime the slowed spans,
    concat, then burn the subtitles. Video labelled [vout]; audio [aout] when has_audio."""
    # boundaries -> pieces: [0,a1] normal, [a1,b1] slow, [b1,a2] normal, ... , [bN,end] normal
    pieces: list[tuple[float, float | None, float]] = []
    prev = 0.0
    for s in segments:
        if s.start > prev:
            pieces.append((prev, s.start, 1.0))
        pieces.append((s.start, s.end, s.speed))
        prev = s.end
    pieces.append((prev, None, 1.0))                 # tail to end of clip

    vlabels, alabels, chains = [], [], []
    for idx, (a, b, sp) in enumerate(pieces):
        trim = f"start={a:g}" + (f":end={b:g}" if b is not None else "")
        vpts = f"setpts=(PTS-STARTPTS)" if sp == 1.0 else f"setpts=(1/{sp:g})*(PTS-STARTPTS)"
        chains.append(f"[0:v]trim={trim},{vpts}[v{idx}]")
        vlabels.append(f"[v{idx}]")
        if has_audio:
            atrim = f"start={a:g}" + (f":end={b:g}" if b is not None else "")
            apts = "asetpts=PTS-STARTPTS" + ("" if sp == 1.0 else f",{_atempo_chain(sp)}")
            chains.append(f"[0:a]atrim={atrim},{apts}[a{idx}]")
            alabels.append(f"[a{idx}]")

    n = len(pieces)
    chains.append(f"{''.join(vlabels)}concat=n={n}:v=1:a=0[vcat]")
    chains.append(f"[vcat]subtitles={ass_name}[vout]")
    if has_audio:
        chains.append(f"{''.join(alabels)}concat=n={n}:v=0:a=1[aout]")
    return ";".join(chains)
