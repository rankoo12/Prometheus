"""GoalHandler — turn GOAL events into goal-effect instructions (spec §7.2).

Stage 2 of the pipeline: consumes events + the Profile, emits ASS_OVERLAY EditInstructions
for the goal celebration — a white **flash** (full-frame box) and a **"GOAL!" text pop**,
both styled and positioned from the Profile. Knows nothing about how goals were detected or
how the ASS is rendered.

`scope` selects which goals to celebrate: "your_goals" (default) = only goals the user scored
(side=="your_team" and scorer=="you"); "all" = every detected goal. (Slowmo is a later slice.)
"""
from __future__ import annotations

from backend.handlers.base import Handler
from backend.models.event import Event, EventType
from backend.models.instruction import EditInstruction, InstructionKind
from backend.models.profile import Profile


class GoalHandler(Handler):
    def handle(self, events: list[Event], profile: Profile) -> list[EditInstruction]:
        goal = profile.data["goal"]
        if not goal.get("enabled", True):
            return []
        scope = goal.get("scope", "your_goals")
        out_cfg = profile.data["output"]
        w, h = int(out_cfg["width"]), int(out_cfg["height"])

        out: list[EditInstruction] = []
        for e in events:
            if e.type is not EventType.GOAL or not self._in_scope(e, scope):
                continue
            flash = goal["flash"]
            if flash.get("enabled", True):
                dur = (flash["fade_in_ms"] + flash["hold_ms"] + flash["fade_out_ms"]) / 1000.0
                out.append(
                    EditInstruction(
                        kind=InstructionKind.ASS_OVERLAY,
                        t_start=e.t_start,
                        t_end=e.t_start + dur,
                        payload={
                            "type": "flash",
                            "color": flash["color"],
                            "max_opacity": flash["max_opacity"],
                            "fade_in_ms": flash["fade_in_ms"],
                            "hold_ms": flash["hold_ms"],
                            "fade_out_ms": flash["fade_out_ms"],
                        },
                    )
                )
            text = goal["text"]
            if text.get("enabled", True):
                anim = goal["animation"]
                dur = (anim["fade_in_ms"] + anim["hold_ms"] + anim["fade_out_ms"]) / 1000.0
                x, y = self._position(text["position"], w, h)
                out.append(
                    EditInstruction(
                        kind=InstructionKind.ASS_OVERLAY,
                        t_start=e.t_start,
                        t_end=e.t_start + dur,
                        payload={
                            "text": text["label"],
                            "x": x,
                            "y": y,
                            "size": text["size"],
                            "font_file": text["font_file"],
                            "color": text["color"],
                            "outline_color": text["outline_color"],
                            "outline_width": text["outline_width"],
                            "animation": anim,
                        },
                    )
                )
        return out

    @staticmethod
    def _in_scope(e: Event, scope: str) -> bool:
        if scope == "all":
            return True
        # "your_goals": the user's team scored AND the user is the scorer
        return e.metadata.get("side") == "your_team" and e.metadata.get("scorer") == "you"

    @staticmethod
    def _position(pos: dict, w: int, h: int) -> tuple[int, int]:
        # "center" is the only anchor for now; others fall back to centre.
        base_x, base_y = w // 2, h // 2
        return base_x + int(pos.get("x_offset", 0)), base_y + int(pos.get("y_offset", 0))
