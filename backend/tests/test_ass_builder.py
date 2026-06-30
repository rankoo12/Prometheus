"""ass_builder: ASS_OVERLAY instructions -> a valid .ass document."""
from __future__ import annotations

from backend.handlers.boost_handler import BoostHandler
from backend.models.event import Event, EventType
from backend.models.profile import Profile
from backend.render.ass_builder import _ass_color, build_ass


def _overlays():
    events = [
        Event(EventType.BOOST_PICKUP, t_start=1.0, metadata={"amount": 12}),
        Event(EventType.BOOST_PICKUP, t_start=2.0, metadata={"amount": 100}),
    ]
    return BoostHandler().handle(events, Profile.load())


def test_ass_color_rgb_to_bgr():
    assert _ass_color("#33CCFF") == "&H00FFCC33"


def test_dialogue_per_overlay_with_tags():
    ass = build_ass(_overlays(), 1080, 1920)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert ass.count("Dialogue:") == 2
    assert "+12" in ass and "+100" in ass
    assert "\\pos(" in ass and "\\fad(" in ass and "\\t(" in ass  # position + fade + pop transform


def test_empty_has_header_no_dialogue():
    ass = build_ass([], 1080, 1920)
    assert "[Events]" in ass and ass.count("Dialogue:") == 0
