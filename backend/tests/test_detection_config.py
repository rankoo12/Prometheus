"""DetectionConfig defaults, overrides, and round-trip."""
from __future__ import annotations

from backend.detection.config import DetectionConfig, GaugeRegion


def test_defaults():
    cfg = DetectionConfig()
    assert cfg.full_value == 100
    assert cfg.small_amount == 12
    assert isinstance(cfg.gauge, GaugeRegion)


def test_from_dict_overrides_and_nested_gauge():
    cfg = DetectionConfig.from_dict({"jump_threshold": 15, "gauge": {"x": 30, "y": 1300}})
    assert cfg.jump_threshold == 15
    assert cfg.gauge.x == 30 and cfg.gauge.y == 1300
    assert cfg.gauge.w == 240  # untouched default preserved


def test_to_dict_roundtrip():
    cfg = DetectionConfig()
    assert DetectionConfig.from_dict(cfg.to_dict()) == cfg
