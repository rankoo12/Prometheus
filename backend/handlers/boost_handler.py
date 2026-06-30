"""BoostHandler — turn BOOST_PICKUP events into ASS overlay instructions (spec §7.1).

Stage 2 of the pipeline: consumes events + the Profile, emits ASS_OVERLAY
EditInstructions (the +12/+100 text with a pop animation, placed relative to the
boost gauge). Knows nothing about how events were detected or how the ASS is rendered.
"""
from __future__ import annotations

from backend.detection.config import DetectionConfig, GaugeRegion
from backend.handlers.base import Handler
from backend.models.event import Event, EventType
from backend.models.instruction import EditInstruction, InstructionKind
from backend.models.profile import Profile

_DEFAULT_SIZE = 72  # px; the Profile has no boost.text.size yet (see note in handle())


class BoostHandler(Handler):
    """One overlay per boost pickup, styled + positioned entirely from the Profile.

    The Profile's `near_gauge` anchor is resolved against the known gauge region
    (a detection concern), so placement stays data-driven while still landing on the
    actual on-screen gauge.
    """

    def __init__(self, gauge: GaugeRegion | None = None) -> None:
        self.gauge = gauge or DetectionConfig().gauge

    def handle(self, events: list[Event], profile: Profile) -> list[EditInstruction]:
        boost = profile.data["boost"]
        if not boost.get("enabled", True):
            return []
        text = boost["text"]
        anim = boost["animation"]
        full = profile.data["output"]  # reserved for clamping/scaling later
        x, y = self._position(text["position"])
        duration = (anim["fade_in_ms"] + anim["hold_ms"] + anim["fade_out_ms"]) / 1000.0

        out: list[EditInstruction] = []
        for e in events:
            if e.type is not EventType.BOOST_PICKUP:
                continue
            amount = e.metadata.get("amount", 0)
            label = text["big_label"] if amount and amount >= 100 else text["small_label"]
            out.append(
                EditInstruction(
                    kind=InstructionKind.ASS_OVERLAY,
                    t_start=e.t_start,
                    t_end=e.t_start + duration,
                    payload={
                        "text": label,
                        "x": x,
                        "y": y,
                        "size": text.get("size", _DEFAULT_SIZE),
                        "font_file": text["font_file"],
                        "color": text["color"],
                        "outline_color": text["outline_color"],
                        "outline_width": text["outline_width"],
                        "animation": anim,
                    },
                )
            )
        return out

    def _position(self, pos: dict) -> tuple[int, int]:
        g = self.gauge
        if pos.get("anchor") == "near_gauge":
            base_x = g.x + g.w // 2     # centered on the gauge horizontally
            base_y = g.y                # gauge-number top; offsets nudge from here
        else:                            # other anchors added when needed
            base_x, base_y = 0, 0
        return base_x + int(pos.get("x_offset", 0)), base_y + int(pos.get("y_offset", 0))
