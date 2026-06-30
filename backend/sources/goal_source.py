"""GoalSource — detect goals from a clip via the scoreboard (spec §6.2).

Stage 1 of the pipeline: emits GOAL events and knows nothing about effects or rendering.
The series -> events logic (`detect_goals`) is pure and unit-tested with synthetic score
series; reading each score box (shape-matching the digit) is delegated to the detection
layer (`scoreboard`).

Backbone signal: read each team's score digit per frame; a GOAL is a confirmed increment of
that team's score. Reading by shape is robust to the box's semi-transparent background bleed,
and confirming via several consecutive equal reads rejects transient misreads. A None read
(absent scoreboard during a replay, or a low-confidence frame) is simply skipped, so a goal's
own replay gap doesn't break detection.

Scope: this source detects ALL goals, tagging `metadata["side"]` as "your_team" (the user's
team, always the LEFT score box) or "opponent" (the RIGHT box). The box colour varies by team
(blue/orange/gray club) and is irrelevant -- ownership is by position. This is TEAM level: a
teammate's goal you assisted still reads "your_team". Finer "*you* personally vs a teammate"
classification (via the 'GOAL +100' popup / the '… SCORED!' banner name) is a separate detector
layered on later -- NOT built yet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

from backend.detection.goal_config import GoalConfig
from backend.models.event import Event, EventType
from backend.sources.base import Source


@dataclass(frozen=True)
class ScoreReading:
    """Both score boxes at time `t` (seconds). left = your team, right = opponent; None when
    unreadable."""

    t: float
    left: int | None
    right: int | None


def _side_events(series: Sequence[tuple[float, int | None]], side: str, cfg: GoalConfig) -> list[Event]:
    """Emit a GOAL each time this team's confirmed score increments. The goal time is the
    last moment the *old* score was still showing (≈ ball-cross), so a replay gap before the
    new score confirms doesn't push the timestamp late."""
    events: list[Event] = []
    established: int | None = None
    last_est_t: float | None = None
    cand: int | None = None
    cand_t0 = 0.0
    cand_count = 0

    for t, v in series:
        if v is None:
            continue
        if established is not None and v == established:
            last_est_t = t
        if v == cand:
            cand_count += 1
        else:
            cand, cand_t0, cand_count = v, t, 1
        if cand_count == cfg.stable_reads:           # candidate just became confirmed
            if established is None:
                established, last_est_t = cand, cand_t0
            elif cand > established:
                events.append(
                    Event(
                        type=EventType.GOAL,
                        t_start=last_est_t if last_est_t is not None else cand_t0,
                        metadata={"side": side, "score": cand, "confidence": 1.0},
                    )
                )
                established = cand
            elif cand < established:                 # correction / overtime reset: rebaseline, no goal
                established = cand
    return events


def _debounce(events: list[Event], min_gap_s: float) -> list[Event]:
    """Collapse goals closer than min_gap_s, keeping the earliest. RL's celebration + kickoff
    forbid genuinely close goals, so anything nearer is a double-read of one goal."""
    kept: list[Event] = []
    for e in events:
        if kept and e.t_start - kept[-1].t_start < min_gap_s:
            continue
        kept.append(e)
    return kept


def detect_goals(readings: Sequence[ScoreReading], cfg: GoalConfig) -> list[Event]:
    """Turn the two per-frame score series into GOAL events (both sides), sorted by time."""
    left = [(r.t, r.left) for r in readings]
    right = [(r.t, r.right) for r in readings]
    events = _side_events(left, "your_team", cfg) + _side_events(right, "opponent", cfg)
    events.sort(key=lambda e: e.t_start)
    return _debounce(events, cfg.min_gap_s)


def enrich_with_scorer(events: list[Event], clip_path: str, scorer) -> list[Event]:
    """Tag each of the user's TEAM goals with metadata["scorer"] = "you" | "teammate" (and a
    confidence) via the scorer. Opponent goals are left untouched. Mutates and returns events."""
    for e in events:
        if e.metadata.get("side") == "your_team":
            who, conf = scorer.classify(clip_path, e.t_start)
            e.metadata["scorer"] = who
            e.metadata["scorer_conf"] = conf
    return events


class GoalSource(Source):
    """Configured at construction; `detect()` reads the clip and emits GOAL events.

    An optional `scorer` (GoalScorer) enriches each of the user's team goals with
    metadata["scorer"] = "you" | "teammate" (did the user score it, vs a teammate)."""

    def __init__(self, clip_path: str, bank: dict[int, list], cfg: GoalConfig | None = None,
                 scorer: "object | None" = None, verbose: bool = False) -> None:
        self.clip_path = clip_path
        self.bank = bank
        self.cfg = cfg or GoalConfig()
        self.scorer = scorer
        self.verbose = verbose

    def detect(self) -> list[Event]:
        events = detect_goals(list(self._read_series()), self.cfg)
        if self.scorer is not None:
            enrich_with_scorer(events, self.clip_path, self.scorer)
        return events

    def _read_series(self) -> Iterator[ScoreReading]:
        import sys

        import cv2

        from backend.detection.scoreboard import read_score

        cap = cv2.VideoCapture(self.clip_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open clip: {self.clip_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        step = max(1, self.cfg.sample_every_n_frames)
        idx = 0
        try:
            while True:
                if idx % step == 0:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    left, _ = read_score(frame, self.cfg.left, self.bank, self.cfg)
                    right, _ = read_score(frame, self.cfg.right, self.bank, self.cfg)
                    yield ScoreReading(idx / fps, left, right)
                elif not cap.grab():
                    break
                if self.verbose and total and idx % 300 == 0:
                    sys.stderr.write(f"\r  reading frame {idx}/{total} ...")
                    sys.stderr.flush()
                idx += 1
        finally:
            cap.release()
            if self.verbose:
                sys.stderr.write("\r  done reading frames.            \n")
