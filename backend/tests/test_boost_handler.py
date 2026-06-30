"""BoostHandler: BOOST_PICKUP events -> ASS overlay instructions, styled from the Profile."""
from __future__ import annotations

from backend.detection.config import DetectionConfig
from backend.handlers.boost_handler import BoostHandler
from backend.models.event import Event, EventType
from backend.models.instruction import InstructionKind
from backend.models.profile import Profile


def _pickup(t: float, amount: int) -> Event:
    return Event(EventType.BOOST_PICKUP, t_start=t, metadata={"amount": amount, "confidence": 1.0})


def test_one_overlay_per_pickup_with_labels():
    insts = BoostHandler().handle([_pickup(1.0, 12), _pickup(2.0, 100)], Profile.load())
    assert [i.kind for i in insts] == [InstructionKind.ASS_OVERLAY, InstructionKind.ASS_OVERLAY]
    assert insts[0].payload["text"] == "+12"
    assert insts[1].payload["text"] == "+100"
    assert insts[0].t_start == 1.0 and insts[0].t_end > 1.0


def test_position_resolved_above_gauge():
    insts = BoostHandler().handle([_pickup(1.0, 12)], Profile.load())
    g = DetectionConfig().gauge  # default near_gauge anchor + y_offset -40
    assert insts[0].payload["x"] == g.x + g.w // 2
    assert insts[0].payload["y"] == g.y - 40


def test_disabled_boost_emits_nothing():
    profile = Profile.load()
    profile.data["boost"]["enabled"] = False
    assert BoostHandler().handle([_pickup(1.0, 12)], profile) == []


def test_ignores_non_boost_events():
    assert BoostHandler().handle([Event(EventType.GOAL, t_start=1.0)], Profile.load()) == []
