"""Event — produced by Sources, consumed by Handlers (spec §4.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """str-backed so the enum serializes straight to JSON over the RPC boundary."""

    BOOST_PICKUP = "BOOST_PICKUP"
    GOAL = "GOAL"
    CAPTION_WORD = "CAPTION_WORD"


@dataclass
class Event:
    """A detected gameplay event.

    metadata is event-specific (spec §4.1):
      BOOST_PICKUP -> {"amount": 12 | 100, "confidence": float}
      GOAL         -> {"confidence": float}
      CAPTION_WORD -> {"word": str}
    """

    type: EventType
    t_start: float                       # seconds, relative to the trimmed clip
    t_end: float | None = None           # spans (captions); None for instants
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "t_start": self.t_start,
            "t_end": self.t_end,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Event":
        return cls(
            type=EventType(d["type"]),
            t_start=float(d["t_start"]),
            t_end=None if d.get("t_end") is None else float(d["t_end"]),
            metadata=dict(d.get("metadata", {})),
        )
