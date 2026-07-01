"""CaptionHandler — turn CAPTION_WORD events into karaoke caption overlays (spec §7.3).

Stage 2: groups words into chunks of `words_per_chunk`, and for each chunk emits one ASS_OVERLAY
(payload type "caption") carrying per-word karaoke durations. The renderer highlights each word
from `base_color` to `active_color` as it's spoken (ASS \\k), with an optional pop-in. Pure — no
Whisper, no rendering.
"""
from __future__ import annotations

from backend.handlers.base import Handler
from backend.models.event import Event, EventType
from backend.models.instruction import EditInstruction, InstructionKind
from backend.models.profile import Profile

_HOLD_S = 0.3    # keep a chunk on screen this long after its last word ends
_MAX_GAP_S = 1.0  # a pause longer than this starts a new chunk (don't span silences)


def _chunks(words: list[Event], n: int, max_gap: float = _MAX_GAP_S) -> list[list[Event]]:
    """Group words into lines of <= n words, breaking early on a pause > max_gap so a caption
    never spans a silence (which would leave it lingering on screen for seconds)."""
    chunks: list[list[Event]] = []
    cur: list[Event] = []
    for w in words:
        if cur and (len(cur) >= n or (w.t_start - cur[-1].t_end) > max_gap):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


class CaptionHandler(Handler):
    def handle(self, events: list[Event], profile: Profile) -> list[EditInstruction]:
        cap = profile.data["captions"]
        if not cap.get("enabled", True):
            return []
        words = [e for e in events if e.type is EventType.CAPTION_WORD]
        if not words:
            return []
        out_cfg = profile.data["output"]
        x, y = self._position(cap["position"], int(out_cfg["width"]), int(out_cfg["height"]))
        anim = cap["animation"]

        out: list[EditInstruction] = []
        for chunk in _chunks(words, int(cap["words_per_chunk"])):
            out.append(
                EditInstruction(
                    kind=InstructionKind.ASS_OVERLAY,
                    t_start=chunk[0].t_start,
                    t_end=chunk[-1].t_end + _HOLD_S,
                    payload={
                        "type": "caption",
                        "words": self._karaoke(chunk),
                        "x": x,
                        "y": y,
                        "size": cap["size"],
                        "font_file": cap["font_file"],
                        "base_color": cap["base_color"],
                        "active_color": cap["active_color"],
                        "outline_color": cap["outline_color"],
                        "outline_width": cap["outline_width"],
                        "pop_in": bool(anim.get("pop_in", False)),
                        "pop_duration_ms": anim.get("pop_duration_ms", 120),
                    },
                )
            )
        return out

    @staticmethod
    def _karaoke(chunk: list[Event]) -> list[dict]:
        """Per-word {text, kdur} where kdur (centiseconds) is the time until the next word starts
        (the last word holds for its own duration). ASS \\k highlights word-by-word from these."""
        words = []
        for i, w in enumerate(chunk):
            nxt = chunk[i + 1].t_start if i + 1 < len(chunk) else w.t_end
            kdur = max(1, round((nxt - w.t_start) * 100))
            words.append({"text": w.metadata.get("word", ""), "kdur": kdur})
        return words

    @staticmethod
    def _position(pos: dict, w: int, h: int) -> tuple[int, int]:
        # "lower_third" (default) sits captions in the lower area, bottom-centre anchored.
        base_y = round(h * 0.82)
        return w // 2, base_y + int(pos.get("y_offset", 0))
