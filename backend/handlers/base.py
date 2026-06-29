"""Handler interface — the second stage of the pipeline (spec §3.1).

A Handler consumes Events and emits EditInstructions. One handler per event type. It
reads the Profile for styling and knows NOTHING about how events were detected or how
instructions are rendered. Open/Closed boundary: new behaviour = new Handler subclass.

PROVISIONAL (Phase 0): the concrete handle() signature firms up in Phase 2 against the
first real implementation (BoostHandler). Stated now to lock the seam.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models.event import Event
from backend.models.instruction import EditInstruction
from backend.models.profile import Profile


class Handler(ABC):
    @abstractmethod
    def handle(self, events: list[Event], profile: Profile) -> list[EditInstruction]:
        """Turn events into edit instructions, styled per the profile."""
        raise NotImplementedError
