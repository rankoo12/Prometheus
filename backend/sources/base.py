"""Source interface — the first stage of the pipeline (spec §3.1).

A Source detects events from input and knows NOTHING about overlays, SFX, or rendering.
This is the Open/Closed boundary: new event types are new Source subclasses, never edits
here.

PROVISIONAL (Phase 0): the concrete detect() signature firms up in Phase 1 against the
first real implementation (BoostSource). Stated now to lock the seam.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models.event import Event


class Source(ABC):
    @abstractmethod
    def detect(self) -> list[Event]:
        """Produce the events this source is responsible for."""
        raise NotImplementedError
