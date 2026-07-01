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
    """Re-time overlay instructions onto the output timeline.

    A pop/flash overlay is a fixed-length animation, so its start is remapped and its wall-clock
    duration is preserved. A CAPTION tracks the (also-slowed) speech, so it must STRETCH with the
    audio: start, end, AND each per-word start are all remapped through the segments — otherwise
    a caption inside a slow-mo would run ahead of the slowed voice."""
    if not segments:
        return overlays
    out: list[EditInstruction] = []
    for inst in overlays:
        if inst.payload.get("type") == "caption":
            words = [{**w, "start": remap_time(w["start"], segments)} for w in inst.payload.get("words", [])]
            out.append(
                EditInstruction(
                    kind=inst.kind,
                    t_start=remap_time(inst.t_start, segments),
                    t_end=remap_time(inst.t_end, segments) if inst.t_end is not None else None,
                    payload={**inst.payload, "words": words},
                )
            )
        else:
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


def _pieces(segments: list[Segment]) -> list[tuple[float, float | None, float]]:
    """Split [0, end] at each segment: [0,a1] normal, [a1,b1] slow, [b1,a2] normal, ... , tail."""
    pieces: list[tuple[float, float | None, float]] = []
    prev = 0.0
    for s in segments:
        if s.start > prev:
            pieces.append((prev, s.start, 1.0))
        pieces.append((s.start, s.end, s.speed))
        prev = s.end
    pieces.append((prev, None, 1.0))
    return pieces


def build_filter(segments: list[Segment], ass_name: str, has_audio: bool = True, *,
                 music: bool = False, music_gain_db: float = 0.0, duck: bool = False,
                 norm_lufs: float | None = None, true_peak: float = -1.0) -> str:
    """FFmpeg filter_complex for the render. VIDEO: (retime split+concat if any segments) then
    burn subtitles -> [vout]. AUDIO (when has_audio): the clip's voice (retimed to match) ->
    optionally mixed under looped music input [1:a] (gain, and sidechain-ducked by the voice) ->
    optionally loudnorm -> [aout]. Handles the no-segment case (plain subtitles + passthrough)."""
    chains: list[str] = []

    # ---- VIDEO ----
    if segments:
        pieces = _pieces(segments)
        vlabels = []
        for idx, (a, b, sp) in enumerate(pieces):
            trim = f"start={a:g}" + (f":end={b:g}" if b is not None else "")
            vpts = "setpts=(PTS-STARTPTS)" if sp == 1.0 else f"setpts=(1/{sp:g})*(PTS-STARTPTS)"
            chains.append(f"[0:v]trim={trim},{vpts}[v{idx}]")
            vlabels.append(f"[v{idx}]")
        chains.append(f"{''.join(vlabels)}concat=n={len(pieces)}:v=1:a=0[vcat]")
        vsrc = "[vcat]"
    else:
        vsrc = "[0:v]"
    chains.append(f"{vsrc}subtitles={ass_name}[vout]")
    if not has_audio:
        return ";".join(chains)

    # ---- AUDIO: voice (retimed to match the video), then loudness-NORMALIZE THE VOICE ----
    if segments:
        pieces = _pieces(segments)
        alabels = []
        for idx, (a, b, sp) in enumerate(pieces):
            atrim = f"start={a:g}" + (f":end={b:g}" if b is not None else "")
            apts = "asetpts=PTS-STARTPTS" + ("" if sp == 1.0 else f",{_atempo_chain(sp)}")
            chains.append(f"[0:a]atrim={atrim},{apts}[a{idx}]")
            alabels.append(f"[a{idx}]")
        chains.append(f"{''.join(alabels)}concat=n={len(pieces)}:v=0:a=1[voiceraw]")
    else:
        chains.append("[0:a]asetpts=PTS-STARTPTS[voiceraw]")
    # Normalize the VOICE (not the final mix). Normalizing a music-heavy mix would re-boost the
    # music and drown the voice — the reason a low music gain seemed to have no effect.
    if norm_lufs is not None:
        chains.append(f"[voiceraw]loudnorm=I={norm_lufs:g}:TP={true_peak:g}[voice]")
    else:
        chains.append("[voiceraw]anull[voice]")

    # ---- MUSIC a controlled amount UNDER the normalized voice (input [1:a], looped by caller) ----
    final = "[voice]"
    if music:
        chains.append(f"[1:a]volume={music_gain_db:g}dB[music]")
        if duck:                                          # music ducks further when the voice is present
            chains.append("[voice]asplit=2[vA][vB]")
            chains.append("[music][vB]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[mduck]")
            chains.append("[vA][mduck]amix=inputs=2:duration=first:normalize=0[amix]")
        else:
            chains.append("[voice][music]amix=inputs=2:duration=first:normalize=0[amix]")
        final = "[amix]"

    chains.append(f"{final}alimiter=limit=0.97[aout]")     # catch summed peaks; no re-normalize
    return ";".join(chains)
