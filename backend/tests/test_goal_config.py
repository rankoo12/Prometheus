"""Unit tests for GoalConfig (round-trip + overrides)."""
from __future__ import annotations

from backend.detection.goal_config import GoalConfig, ScoreRegion


def test_defaults_have_two_score_regions():
    cfg = GoalConfig()
    assert isinstance(cfg.left, ScoreRegion)
    assert isinstance(cfg.right, ScoreRegion)
    assert cfg.left.x != cfg.right.x


def test_from_dict_overrides_regions_and_params():
    cfg = GoalConfig.from_dict(
        {"left": {"x": 1, "y": 2, "w": 3, "h": 4}, "min_match": 0.7}
    )
    assert cfg.left == ScoreRegion(1, 2, 3, 4)
    assert cfg.min_match == 0.7
    # untouched fields keep defaults
    assert cfg.right == GoalConfig().right


def test_to_dict_round_trips():
    cfg = GoalConfig()
    assert GoalConfig.from_dict(cfg.to_dict()) == cfg
