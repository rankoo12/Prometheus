"""CaptionHandler: CAPTION_WORD events + Profile -> karaoke caption overlays."""
from __future__ import annotations

from backend.handlers.caption_handler import CaptionHandler
from backend.models.event import Event, EventType
from backend.models.instruction import InstructionKind
from backend.models.profile import Profile


def _word(text, t0, t1):
    return Event(EventType.CAPTION_WORD, t_start=t0, t_end=t1, metadata={"word": text})


def _words(spec):
    return [_word(t, a, b) for (t, a, b) in spec]


NICE_SHOT = _words([("Nice", 25.0, 25.3), ("shot", 25.3, 25.8)])


def test_groups_into_chunks_of_words_per_chunk():
    prof = Profile.load()
    prof.data["captions"]["words_per_chunk"] = 2
    words = _words([("a", 0, 1), ("b", 1, 2), ("c", 2, 3), ("d", 3, 4), ("e", 4, 5)])
    instrs = CaptionHandler().handle(words, prof)
    assert len(instrs) == 3                                   # 2+2+1
    assert all(i.kind is InstructionKind.ASS_OVERLAY for i in instrs)
    assert all(i.payload["type"] == "caption" for i in instrs)


def test_line_timing_spans_chunk_plus_hold():
    instrs = CaptionHandler().handle(NICE_SHOT, Profile.load())
    line = instrs[0]
    assert line.t_start == 25.0                              # first word start
    assert round(line.t_end, 2) == 26.1                       # last word end (25.8) + 0.3 hold


def test_words_carry_text_and_absolute_start():
    instrs = CaptionHandler().handle(NICE_SHOT, Profile.load())
    words = instrs[0].payload["words"]
    assert [w["text"] for w in words] == ["Nice", "shot"]
    assert [w["start"] for w in words] == [25.0, 25.3]     # absolute -> renderer highlights per word


def test_consecutive_lines_do_not_overlap():
    prof = Profile.load()
    prof.data["captions"]["words_per_chunk"] = 1              # each word its own line
    words = _words([("a", 1.0, 1.2), ("b", 1.3, 1.6)])        # closer than the 0.3s hold
    instrs = CaptionHandler().handle(words, prof)
    assert len(instrs) == 2
    assert instrs[0].t_end <= instrs[1].t_start              # first line capped at the next's start


def test_style_and_position_from_profile():
    instrs = CaptionHandler().handle(NICE_SHOT, Profile.load())
    p = instrs[0].payload
    cap = Profile.load().data["captions"]
    assert p["base_color"] == cap["base_color"] and p["active_color"] == cap["active_color"]
    assert p["size"] == cap["size"]
    assert p["x"] == 540 and p["y"] == round(1920 * 0.82)     # centered, lower third


def test_disabled_or_empty_yields_nothing():
    prof = Profile.load()
    prof.data["captions"]["enabled"] = False
    assert CaptionHandler().handle(NICE_SHOT, prof) == []
    assert CaptionHandler().handle([], Profile.load()) == []


def test_non_caption_events_ignored():
    goal = Event(EventType.GOAL, t_start=5.0, metadata={"side": "your_team"})
    assert CaptionHandler().handle([goal], Profile.load()) == []
