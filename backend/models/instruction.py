"""EditInstruction — produced by Handlers, consumed by the Renderer (spec §4.2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InstructionKind(str, Enum):
    ASS_OVERLAY = "ASS_OVERLAY"
    SFX_CUE = "SFX_CUE"
    MUSIC_BED = "MUSIC_BED"
    STATIC_OVERLAY = "STATIC_OVERLAY"


@dataclass
class EditInstruction:
    """A single render directive.

    payload is kind-specific (e.g. an ASS fragment, an SFX file path + gain, an
    image path). The Renderer is the only stage that interprets it.
    """

    kind: InstructionKind
    t_start: float
    t_end: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "t_start": self.t_start,
            "t_end": self.t_end,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EditInstruction":
        return cls(
            kind=InstructionKind(d["kind"]),
            t_start=float(d["t_start"]),
            t_end=None if d.get("t_end") is None else float(d["t_end"]),
            payload=dict(d.get("payload", {})),
        )
