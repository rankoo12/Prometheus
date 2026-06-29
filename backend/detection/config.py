"""Boost-detection tuning (spec §6.1).

Kept OUT of the styling Profile: detection tuning and output styling are separate
concerns (SRP). Defaults are provisional (the spec's gauge estimate) and meant to be
tuned against real footage; override via DetectionConfig.load(<json>).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GaugeRegion:
    """Crop of the on-screen boost number, in source pixels (top-left origin)."""

    x: int = 20
    y: int = 1330
    w: int = 240
    h: int = 240


@dataclass(frozen=True)
class DetectionConfig:
    gauge: GaugeRegion = field(default_factory=GaugeRegion)
    sample_every_n_frames: int = 1       # 1 = every frame
    match_threshold: float = 0.70        # min normalized-correlation to accept a digit
    jump_threshold: int = 8              # min rise (boost units) to treat as a pickup
    stable_frames: int = 2               # readings the peak must hold to confirm a settle
    stable_tolerance: int = 2            # +/- units still counted as "the same" value
    full_value: int = 100                # a big pad fills to this
    full_read_tolerance: int = 1         # treat >= full_value - this as "full" (read noise)
    small_amount: int = 12               # a small pad adds this

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DetectionConfig":
        d = dict(d)
        gauge = d.pop("gauge", None)
        if gauge is None:
            return cls(**d)
        return cls(gauge=GaugeRegion(**gauge), **d)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "DetectionConfig":
        if path is None:
            return cls()
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
