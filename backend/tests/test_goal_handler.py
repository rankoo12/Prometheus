"""GoalHandler: GOAL events + Profile -> flash + "GOAL!" overlay instructions."""
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


def _payloads(instrs):
    return [i.payload for i in instrs]


def test_your_goal_emits_flash_and_text():
    instrs = GoalHandler().handle([_goal("your_team", "you")], Profile.load())
    assert all(i.kind is InstructionKind.ASS_OVERLAY for i in instrs)
    kinds = [p.get("type", "text") for p in _payloads(instrs)]
    assert kinds == ["flash", "text"]          # flash first (under), text second (on top)
    flash, text = instrs
    assert flash.t_start == 10.0 and flash.t_end > flash.t_start
    assert text.payload["text"] == "GOAL!"
    # centered on a 1080x1920 frame
    assert text.payload["x"] == 540 and text.payload["y"] == 960


def test_assist_is_not_celebrated_by_default():
    assert GoalHandler().handle([_goal("your_team", "teammate")], Profile.load()) == []


def test_opponent_goal_not_celebrated_by_default():
    assert GoalHandler().handle([_goal("opponent")], Profile.load()) == []


def test_scope_all_celebrates_every_goal():
    prof = Profile.load()
    prof.data["goal"]["scope"] = "all"
    instrs = GoalHandler().handle([_goal("opponent"), _goal("your_team", "teammate")], prof)
    # 2 goals x (flash + text)
    assert len(instrs) == 4


def test_flash_disabled_emits_text_only():
    prof = Profile.load()
    prof.data["goal"]["flash"]["enabled"] = False
    instrs = GoalHandler().handle([_goal("your_team", "you")], prof)
    assert [p.get("type", "text") for p in _payloads(instrs)] == ["text"]


def test_text_disabled_emits_flash_only():
    prof = Profile.load()
    prof.data["goal"]["text"]["enabled"] = False
    instrs = GoalHandler().handle([_goal("your_team", "you")], prof)
    assert [p.get("type", "text") for p in _payloads(instrs)] == ["flash"]


def test_disabled_goal_section_emits_nothing():
    prof = Profile.load()
    prof.data["goal"]["enabled"] = False
    assert GoalHandler().handle([_goal("your_team", "you")], prof) == []


def test_position_offsets_applied():
    prof = Profile.load()
    prof.data["goal"]["text"]["position"] = {"anchor": "center", "x_offset": -20, "y_offset": 100}
    instrs = GoalHandler().handle([_goal("your_team", "you")], prof)
    text = [i for i in instrs if i.payload.get("type", "text") == "text"][0]
    assert text.payload["x"] == 520 and text.payload["y"] == 1060
