"""Unit tests for the pure goal detector (integer score series, no footage)."""
from __future__ import annotations

from backend.detection.goal_config import GoalConfig
from backend.models.event import EventType
from backend.sources.goal_source import ScoreReading, detect_goals

CFG = GoalConfig()
CFG0 = GoalConfig(min_gap_s=0.0)   # disable the close-goal debounce for structural tests
FPS = 20.0


def _series(left, right=None):
    """Build ScoreReadings from per-frame left/right scores (right constant 0 if omitted).
    left box = your team, right box = opponent."""
    right = right if right is not None else [0] * len(left)
    return [ScoreReading(i / FPS, l, r) for i, (l, r) in enumerate(zip(left, right))]


def test_single_your_goal():
    events = detect_goals(_series([1] * 6 + [2] * 6, [0] * 12), CFG)
    assert len(events) == 1
    e = events[0]
    assert e.type is EventType.GOAL
    assert e.metadata["side"] == "your_team"
    assert e.metadata["score"] == 2
    # fires at the last frame the old score (1) still showed -> frame 5 -> 5/20 s
    assert abs(e.t_start - 5 / FPS) < 1e-6


def test_no_goal_when_score_constant():
    assert detect_goals(_series([2] * 30, [3] * 30), CFG) == []


def test_single_frame_misread_ignored():
    # a lone wrong read (5) never reaches stable_reads -> no goal
    assert detect_goals(_series([1] * 8 + [5] + [1] * 8), CFG) == []


def test_replay_gap_does_not_break_detection():
    # old score 2, scoreboard vanishes during the replay (None), reappears as 3
    left = [2] * 6 + [None] * 5 + [3] * 6
    events = detect_goals(_series(left), CFG)
    assert len(events) == 1
    assert events[0].metadata["score"] == 3
    # timed at the last frame '2' was visible (frame 5)
    assert abs(events[0].t_start - 5 / FPS) < 1e-6


def test_score_decrease_is_not_a_goal():
    # a correction / overtime reset rebaselines without emitting
    assert detect_goals(_series([3] * 6 + [2] * 6), CFG) == []


def test_two_your_goals_no_debounce():
    events = detect_goals(_series([1] * 6 + [2] * 6 + [3] * 6), CFG0)
    assert [e.metadata["score"] for e in events] == [2, 3]
    assert events[0].t_start < events[1].t_start


def test_close_double_read_collapsed_by_debounce():
    # two increments within min_gap_s collapse to the first (e.g. a transient misread bump)
    raw = detect_goals(_series([1] * 6 + [2] * 6 + [3] * 6), CFG0)
    near = detect_goals(_series([1] * 6 + [2] * 6 + [3] * 6), CFG)
    assert len(raw) == 2 and len(near) == 1
    assert near[0].t_start == raw[0].t_start


def test_opponent_goal_detected_and_tagged():
    events = detect_goals(_series([1] * 12, [0] * 6 + [1] * 6), CFG)
    assert len(events) == 1
    assert events[0].metadata["side"] == "opponent"


def test_both_sides_score_sorted_by_time():
    left = [0] * 6 + [1] * 18
    right = [0] * 14 + [1] * 10
    events = detect_goals(_series(left, right), CFG0)
    assert [e.metadata["side"] for e in events] == ["your_team", "opponent"]
    assert events[0].t_start < events[1].t_start
