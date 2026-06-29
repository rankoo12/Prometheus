"""Pure-logic tests for boost pickup detection (no footage / OpenCV needed)."""
from __future__ import annotations

from backend.detection.config import DetectionConfig
from backend.models.event import EventType
from backend.sources.boost_source import (
    Reading,
    detect_pickups,
    drop_despike,
    smooth_values,
)

CFG = DetectionConfig()


def _series(values):
    """One reading per frame at 60fps; None passes through as unreadable."""
    return [Reading(t=i / 60.0, value=v) for i, v in enumerate(values)]


def _amounts(events):
    return [e.metadata["amount"] for e in events]


def test_drain_only_no_events():
    assert detect_pickups(_series([100, 98, 95, 90, 80, 60]), CFG) == []


def test_small_pad_from_empty():
    events = detect_pickups(_series([0, 0, 12, 12, 12]), CFG)
    assert _amounts(events) == [12]
    assert events[0].type == EventType.BOOST_PICKUP


def test_big_pad_from_empty():
    assert _amounts(detect_pickups(_series([0, 0, 100, 100, 100]), CFG)) == [100]


def test_big_pad_near_full_classified_by_result():
    # 88 -> 100 is only a +12-sized jump but fills to full => big pad
    assert _amounts(detect_pickups(_series([88, 88, 100, 100]), CFG)) == [100]


def test_small_pad_midrange():
    assert _amounts(detect_pickups(_series([50, 62, 62, 62]), CFG)) == [12]


def test_transient_intermediate_frame():
    # settle reads 0 -> 6 -> 12; still one +12, not two
    assert _amounts(detect_pickups(_series([0, 6, 12, 12]), CFG)) == [12]


def test_two_distinct_pickups():
    # two grabs separated by a sustained hold (not one animated ramp)
    assert _amounts(detect_pickups(_series([0] + [12] * 6 + [24] * 6), CFG)) == [12, 12]


def test_animated_ramp_is_one_pickup():
    # the overlay ramps the number up over several frames -> one pickup at the peak
    assert _amounts(detect_pickups(_series([0, 0, 26, 63, 74, 89, 97, 100] + [100] * 6), CFG)) == [100]


def test_read_noise_no_false_positive():
    assert detect_pickups(_series([50, 51, 49, 50, 51, 50]), CFG) == []


def test_single_frame_spike_rejected():
    # a lone bad read (12) that doesn't hold is not a pickup
    assert detect_pickups(_series([0, 12, 0, 0, 0]), CFG) == []


def test_unreadable_frames_ignored():
    assert _amounts(detect_pickups(_series([0, None, 12, None, 12, 12]), CFG)) == [12]


def test_timestamp_is_rise_start():
    events = detect_pickups(_series([0, 0, 100, 100, 100]), CFG)
    assert abs(events[0].t_start - 2 / 60.0) < 1e-9  # rise first seen at index 2


def test_smooth_values_removes_isolated_spike():
    rs = smooth_values(_series([50, 50, 100, 50, 50, 50, 50]), 5)
    assert all(r.value == 50 for r in rs)


def test_despike_dropout_recovery_is_not_a_pickup():
    # 66 momentarily misread as 6, then recovers — must not become a pickup
    rs = drop_despike(_series([66] * 6 + [6] * 4 + [66] * 6), CFG.max_drain_per_second)
    assert detect_pickups(rs, CFG) == []


def test_despike_keeps_real_drain_then_pickup():
    rs = drop_despike(_series([60, 59, 58, 57, 56, 55, 55, 67, 67, 67]), CFG.max_drain_per_second)
    assert _amounts(detect_pickups(rs, CFG)) == [12]
