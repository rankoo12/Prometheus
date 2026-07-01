"""ass_builder: ASS_OVERLAY instructions -> a valid .ass document."""
from __future__ import annotations

from backend.handlers.boost_handler import BoostHandler
from backend.handlers.caption_handler import CaptionHandler
from backend.handlers.goal_handler import GoalHandler
from backend.models.event import Event, EventType
from backend.models.instruction import EditInstruction, InstructionKind
from backend.models.profile import Profile
from backend.render.ass_builder import _ass_alpha, _ass_color, build_ass


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


def test_per_event_inline_style():
    # each overlay carries its own size/colour inline, not a single global style
    ass = build_ass(_overlays(), 1080, 1920)
    assert "\\fs" in ass and "\\1c" in ass and "\\3c" in ass


def test_ass_alpha_maps_opacity():
    assert _ass_alpha(1.0) == "&H00&"      # opaque
    assert _ass_alpha(0.0) == "&HFF&"      # transparent


def test_goal_flash_draws_full_frame_box():
    goal = Event(EventType.GOAL, t_start=5.0, metadata={"side": "your_team", "scorer": "you"})
    ass = build_ass(GoalHandler().handle([goal], Profile.load()), 1080, 1920)
    assert "GOAL!" in ass                            # the text pop
    assert "\\p1}" in ass and "l 1080 0 1080 1920" in ass   # the flash box drawing spans the frame
    assert "Dialogue: 0," in ass and "Dialogue: 1," in ass  # flash under (L0), text over (L1)


def test_caption_karaoke_line():
    prof = Profile.load()
    prof.data["captions"]["words_per_chunk"] = 4
    words = [
        Event(EventType.CAPTION_WORD, t_start=25.0, t_end=25.3, metadata={"word": "Nice"}),
        Event(EventType.CAPTION_WORD, t_start=25.3, t_end=25.8, metadata={"word": "shot"}),
    ]
    ass = build_ass(CaptionHandler().handle(words, prof), 1080, 1920)
    assert "\\k30}Nice" in ass and "\\k50}shot" in ass       # per-word karaoke timings
    assert "\\2c" in ass                                      # secondary (base) colour set for \k
