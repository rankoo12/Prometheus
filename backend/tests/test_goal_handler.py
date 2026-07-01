"""GoalHandler: GOAL events + Profile -> slowmo retime + flash + "GOAL!" overlay instructions."""
from __future__ import annotations

from backend.handlers.goal_handler import GoalHandler
from backend.models.event import Event, EventType
from backend.models.instruction import InstructionKind
from backend.models.profile import Profile


def _goal(side, scorer=None, t=10.0):
    md = {"side": side, "score": 1}
    if scorer is not None:
        md["scorer"] = scorer
    return Event(EventType.GOAL, t_start=t, metadata=md)


def _split(instrs):
    retimes = [i for i in instrs if i.kind is InstructionKind.RETIME_SEGMENT]
    overlays = [i for i in instrs if i.kind is InstructionKind.ASS_OVERLAY]
    return retimes, overlays


def _types(overlays):
    return [o.payload.get("type", "text") for o in overlays]


def test_your_goal_emits_slowmo_flash_and_text():
    retimes, overlays = _split(GoalHandler().handle([_goal("your_team", "you")], Profile.load()))
    assert len(retimes) == 1
    assert _types(overlays) == ["flash", "text"]        # flash under, text over
    text = overlays[1]
    assert text.payload["text"] == "GOAL!"
    assert text.payload["x"] == 540 and text.payload["y"] == 960   # centered on 1080x1920


def test_retime_span_and_speed_from_profile():
    prof = Profile.load()
    sm = prof.data["goal"]["slowmo"]
    retimes, _ = _split(GoalHandler().handle([_goal("your_team", "you", t=10.0)], prof))
    seg = retimes[0]
    assert round(seg.t_start, 2) == round(10.0 - sm["pre_s"], 2)
    assert round(seg.t_end, 2) == round(10.0 + sm["post_s"], 2)
    assert seg.payload["speed"] == sm["speed"]


def test_retime_start_clamped_at_zero():
    retimes, _ = _split(GoalHandler().handle([_goal("your_team", "you", t=0.2)], Profile.load()))
    assert retimes[0].t_start == 0.0


def test_assist_is_not_celebrated_by_default():
    assert GoalHandler().handle([_goal("your_team", "teammate")], Profile.load()) == []


def test_opponent_goal_not_celebrated_by_default():
    assert GoalHandler().handle([_goal("opponent")], Profile.load()) == []


def test_scope_all_celebrates_every_goal():
    prof = Profile.load()
    prof.data["goal"]["scope"] = "all"
    instrs = GoalHandler().handle([_goal("opponent"), _goal("your_team", "teammate")], prof)
    retimes, overlays = _split(instrs)
    assert len(retimes) == 2 and len(overlays) == 4     # 2 goals x (retime + flash + text)


def test_slowmo_disabled_emits_no_retime():
    prof = Profile.load()
    prof.data["goal"]["slowmo"]["enabled"] = False
    retimes, overlays = _split(GoalHandler().handle([_goal("your_team", "you")], prof))
    assert retimes == [] and _types(overlays) == ["flash", "text"]


def test_flash_disabled_emits_text_only():
    prof = Profile.load()
    prof.data["goal"]["flash"]["enabled"] = False
    _, overlays = _split(GoalHandler().handle([_goal("your_team", "you")], prof))
    assert _types(overlays) == ["text"]


def test_text_disabled_emits_flash_only():
    prof = Profile.load()
    prof.data["goal"]["text"]["enabled"] = False
    _, overlays = _split(GoalHandler().handle([_goal("your_team", "you")], prof))
    assert _types(overlays) == ["flash"]


def test_disabled_goal_section_emits_nothing():
    prof = Profile.load()
    prof.data["goal"]["enabled"] = False
    assert GoalHandler().handle([_goal("your_team", "you")], prof) == []


def test_position_offsets_applied():
    prof = Profile.load()
    prof.data["goal"]["text"]["position"] = {"anchor": "center", "x_offset": -20, "y_offset": 100}
    _, overlays = _split(GoalHandler().handle([_goal("your_team", "you")], prof))
    text = [o for o in overlays if o.payload.get("type", "text") == "text"][0]
    assert text.payload["x"] == 520 and text.payload["y"] == 1060
