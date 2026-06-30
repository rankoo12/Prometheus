"""Unit tests for the personal-scorer classification (no footage)."""
from __future__ import annotations

from backend.detection.goal_config import GoalConfig
from backend.detection.scorer import decide
from backend.models.event import Event, EventType
from backend.sources.goal_source import enrich_with_scorer

CFG = GoalConfig()  # name_match=0.55, popup_match=0.70


def test_decide_name_banner_wins():
    who, conf = decide(0.92, 0.30, CFG)
    assert who == "you"
    assert conf == 0.92


def test_decide_popup_backup_wins():
    # banner unclear, but the +100 popup is over threshold
    who, _ = decide(0.20, 0.80, CFG)
    assert who == "you"


def test_decide_neither_is_teammate():
    who, conf = decide(0.19, 0.41, CFG)
    assert who == "teammate"
    assert conf == 0.41


def test_decide_thresholds_are_inclusive():
    assert decide(0.55, 0.0, CFG)[0] == "you"
    assert decide(0.0, 0.70, CFG)[0] == "you"


class _FakeScorer:
    """Records calls, returns a fixed verdict — no clip access."""

    def __init__(self, verdict=("you", 0.9)):
        self.verdict = verdict
        self.calls: list[float] = []

    def classify(self, clip_path, goal_time):
        self.calls.append(goal_time)
        return self.verdict


def _goal(side, t):
    return Event(type=EventType.GOAL, t_start=t, metadata={"side": side, "score": 1})


def test_enrich_only_tags_your_team_goals():
    events = [_goal("your_team", 5.0), _goal("opponent", 9.0)]
    scorer = _FakeScorer(("you", 0.88))
    enrich_with_scorer(events, "clip.mp4", scorer)
    assert events[0].metadata["scorer"] == "you"
    assert events[0].metadata["scorer_conf"] == 0.88
    assert "scorer" not in events[1].metadata        # opponent goal untouched
    assert scorer.calls == [5.0]                       # scorer only consulted for the team goal


def test_enrich_marks_teammate():
    events = [_goal("your_team", 3.0)]
    enrich_with_scorer(events, "clip.mp4", _FakeScorer(("teammate", 0.2)))
    assert events[0].metadata["scorer"] == "teammate"
