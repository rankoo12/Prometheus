"""Pipeline orchestration: build_instructions merges every handler's output (no footage)."""
from __future__ import annotations

from backend.models.event import Event, EventType
from backend.models.instruction import InstructionKind
from backend.models.profile import Profile
from backend.pipeline import build_instructions


def test_build_instructions_merges_all_handlers():
    events = [
        Event(EventType.BOOST_PICKUP, t_start=2.0, metadata={"amount": 100}),
        Event(EventType.GOAL, t_start=25.0, metadata={"side": "your_team", "scorer": "you"}),
        Event(EventType.CAPTION_WORD, t_start=25.0, t_end=25.3, metadata={"word": "Nice"}),
        Event(EventType.CAPTION_WORD, t_start=25.3, t_end=25.8, metadata={"word": "shot"}),
    ]
    instrs = build_instructions(events, Profile.load())
    kinds = [i.kind for i in instrs]
    overlays = [i for i in instrs if i.kind is InstructionKind.ASS_OVERLAY]
    types = [i.payload.get("type", "text") for i in overlays]

    assert InstructionKind.RETIME_SEGMENT in kinds                       # goal slow-mo
    assert "flash" in types and "caption" in types                      # goal flash + captions
    assert any(o.payload.get("text") == "+100" for o in overlays)       # boost pop


def test_disabled_stages_drop_out():
    prof = Profile.load()
    prof.data["boost"]["enabled"] = False
    prof.data["goal"]["enabled"] = False
    events = [
        Event(EventType.BOOST_PICKUP, t_start=2.0, metadata={"amount": 100}),
        Event(EventType.GOAL, t_start=25.0, metadata={"side": "your_team", "scorer": "you"}),
        Event(EventType.CAPTION_WORD, t_start=25.0, t_end=25.3, metadata={"word": "Nice"}),
    ]
    instrs = build_instructions(events, prof)
    # only captions remain
    assert all(i.payload.get("type") == "caption" for i in instrs)
    assert instrs
