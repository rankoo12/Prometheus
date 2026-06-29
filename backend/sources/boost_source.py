"""BoostSource — detect boost pickups from a clip (spec §6.1).

Stage 1 of the pipeline: emits BOOST_PICKUP events and knows nothing about overlays
or rendering. The value-series -> events logic (`detect_pickups`) is pure and
unit-tested without footage; frame reading is delegated to the detection layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from backend.detection.config import DetectionConfig
from backend.models.event import Event, EventType
from backend.sources.base import Source


@dataclass(frozen=True)
class Reading:
    """One gauge reading at time `t` (seconds). value is None when unreadable."""

    t: float
    value: int | None
    confidence: float = 1.0


def _classify(peak: int, cfg: DetectionConfig) -> int:
    """+12 vs +100 by *result*, not jump size (spec §6.1): a big pad fills to 100,
    so a near-full grab (e.g. 88 -> 100) is still a big pad."""
    if peak >= cfg.full_value - cfg.full_read_tolerance:
        return cfg.full_value
    return cfg.small_amount


def detect_pickups(readings: Iterable[Reading], cfg: DetectionConfig) -> list[Event]:
    """Turn a (t, value) series into BOOST_PICKUP events.

    Robust to the three §6.1 hazards: continuous drain (the baseline tracks
    downward), the multi-frame settle (a pickup is confirmed only once the peak
    holds for `stable_frames`, collapsing the transient into a single event), and
    read noise (the jump + stability thresholds reject jitter and lone spikes).
    """
    valid = [r for r in readings if r.value is not None]
    if len(valid) < 2:
        return []

    events: list[Event] = []
    baseline = valid[0].value
    i = 1
    n = len(valid)
    while i < n:
        r = valid[i]
        if r.value >= baseline + cfg.jump_threshold:
            peak = r.value
            conf = r.confidence
            hold = 1
            j = i
            while j + 1 < n:
                nxt = valid[j + 1]
                if nxt.value >= peak + 1:                            # still climbing
                    j += 1
                    peak = nxt.value
                    conf = min(conf, nxt.confidence)
                    hold = 1
                elif abs(nxt.value - peak) <= cfg.stable_tolerance:  # holding at peak
                    j += 1
                    conf = min(conf, nxt.confidence)
                    hold += 1
                    if hold >= cfg.stable_frames:
                        break
                else:                                                # dropped -> settled
                    break
            if hold >= cfg.stable_frames and (peak - baseline) >= cfg.jump_threshold:
                events.append(
                    Event(
                        type=EventType.BOOST_PICKUP,
                        t_start=r.t,
                        metadata={"amount": _classify(peak, cfg), "confidence": round(conf, 3)},
                    )
                )
                baseline = peak
            i = j + 1
        else:
            if r.value < baseline:
                baseline = r.value
            i += 1
    return events


class BoostSource(Source):
    """Configured at construction; `detect()` reads the clip and emits events."""

    def __init__(
        self,
        clip_path: str,
        templates: dict[int, "object"],
        cfg: DetectionConfig | None = None,
    ) -> None:
        self.clip_path = clip_path
        self.templates = templates
        self.cfg = cfg or DetectionConfig()

    def detect(self) -> list[Event]:
        return detect_pickups(self._read_series(), self.cfg)

    def _read_series(self) -> Iterator[Reading]:
        # Lazy cv2 import so the pure detect_pickups path needs no OpenCV.
        import cv2

        from backend.detection.gauge import read_value

        cap = cv2.VideoCapture(self.clip_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open clip: {self.clip_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if idx % self.cfg.sample_every_n_frames == 0:
                    gr = read_value(frame, self.templates, self.cfg)
                    yield Reading(idx / fps, gr.value, gr.confidence)
                idx += 1
        finally:
            cap.release()
