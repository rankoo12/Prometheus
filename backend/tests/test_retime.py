"""Unit tests for the pure slow-motion retiming math (no ffmpeg)."""
from __future__ import annotations

from backend.models.instruction import EditInstruction, InstructionKind
from backend.render.retime import (
    Segment,
    _atempo_chain,
    build_filter,
    remap_overlays,
    remap_time,
    segments_from,
)

# one segment: slow [10,12] to half speed -> the 2s span lasts 4s in the output (stretch = +2s)
SEG = [Segment(10.0, 12.0, 0.5)]


def test_remap_before_segment_unchanged():
    assert remap_time(5.0, SEG) == 5.0
    assert remap_time(10.0, SEG) == 10.0


def test_remap_inside_segment_stretches():
    # 1s into a 2x-slow span -> 2s of output
    assert remap_time(11.0, SEG) == 12.0


def test_remap_after_segment_shifted_by_full_stretch():
    assert remap_time(12.0, SEG) == 14.0     # end of span
    assert remap_time(20.0, SEG) == 22.0     # +2s stretch


def test_remap_identity_without_segments():
    assert remap_time(7.5, []) == 7.5


def test_two_segments_accumulate():
    segs = [Segment(2.0, 4.0, 0.5), Segment(10.0, 11.0, 0.5)]
    # after both: +2s (first span) +1s (second span) = +3s
    assert remap_time(20.0, segs) == 23.0
    # between them: only the first applies (+2s)
    assert remap_time(6.0, segs) == 8.0


def test_remap_overlays_moves_start_keeps_duration():
    ov = [EditInstruction(InstructionKind.ASS_OVERLAY, t_start=11.0, t_end=11.8, payload={"text": "GOAL!"})]
    out = remap_overlays(ov, SEG)
    assert out[0].t_start == 12.0
    assert round(out[0].t_end - out[0].t_start, 6) == 0.8    # wall-clock duration preserved
    assert out[0].payload == {"text": "GOAL!"}


def test_remap_overlays_stretches_caption_words():
    # a caption tracks the (slowed) speech, so start/end AND each word start remap through the span
    cap = EditInstruction(
        InstructionKind.ASS_OVERLAY, t_start=11.0, t_end=11.6,
        payload={"type": "caption", "words": [{"text": "a", "start": 11.0}, {"text": "b", "start": 11.3}]},
    )
    out = remap_overlays([cap], SEG)[0]      # SEG slows [10,12] to 0.5x
    assert out.t_start == 12.0 and round(out.t_end, 2) == 13.2
    assert out.payload["words"][0]["start"] == 12.0
    assert round(out.payload["words"][1]["start"], 2) == 12.6


def test_atempo_chain():
    assert _atempo_chain(0.5) == "atempo=0.5"
    assert _atempo_chain(0.25) == "atempo=0.5,atempo=0.5"


def test_segments_from_extracts_and_sorts():
    instrs = [
        EditInstruction(InstructionKind.RETIME_SEGMENT, 10.0, 11.0, {"speed": 0.5}),
        EditInstruction(InstructionKind.ASS_OVERLAY, 1.0, 2.0, {"text": "x"}),
        EditInstruction(InstructionKind.RETIME_SEGMENT, 3.0, 4.0, {"speed": 0.4}),
    ]
    segs = segments_from(instrs)
    assert [s.start for s in segs] == [3.0, 10.0]     # sorted, overlays ignored


def test_build_filter_shape():
    filt = build_filter(SEG, "overlay.ass", has_audio=True)
    assert "concat=n=3:v=1:a=0[vcat]" in filt          # before-slow-tail = 3 video pieces
    assert "setpts=(1/0.5)*(PTS-STARTPTS)" in filt      # the slowed piece
    assert "[vcat]subtitles=overlay.ass[vout]" in filt
    assert "atempo=0.5" in filt and "concat=n=3:v=0:a=1[voice]" in filt and "[aout]" in filt


def test_build_filter_no_audio_omits_audio_chain():
    filt = build_filter(SEG, "overlay.ass", has_audio=False)
    assert "[aout]" not in filt and "atempo" not in filt


def test_build_filter_no_segments_is_plain_subtitles():
    filt = build_filter([], "overlay.ass", has_audio=True)
    assert "[0:v]subtitles=overlay.ass[vout]" in filt   # no concat when nothing is retimed
    assert "concat" not in filt and "[voice]" in filt


def test_build_filter_music_duck_and_loudnorm():
    filt = build_filter([], "overlay.ass", has_audio=True, music=True,
                        music_gain_db=-8, duck=True, norm_lufs=-14, true_peak=-1.0)
    assert "[1:a]volume=-8dB[music]" in filt
    assert "sidechaincompress" in filt                  # ducking
    assert "amix=inputs=2" in filt
    assert "loudnorm=I=-14:TP=-1[aout]" in filt
