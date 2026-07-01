"""Goal-detection tuning (spec §6.2).

Separate from boost's DetectionConfig (SRP): goal detection watches the scoreboard, not
the boost gauge. Kept OUT of the styling Profile -- detection tuning is not style. Defaults
are tuned to the user's vertical stream layout (scoreboard in the middle game view); override
via GoalConfig.load(<json>).

Detection backbone: read the digit inside each fixed colour score-box (shape-matched against a
small exemplar bank -- robust to the box's semi-transparent background bleed), then emit a GOAL
whenever a team's confirmed score increments.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScoreRegion:
    """Crop of one team's score digit, in source pixels (top-left origin)."""

    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class GoalConfig:
    # The two score-digit boxes (1080x1920 stream layout). Labelled by OWNERSHIP, not colour:
    # the user's team is always shown on the LEFT (its colour varies -- blue/orange/gray club),
    # the opponent on the RIGHT. So `left` increment = your team scored, `right` = opponent.
    left: ScoreRegion = field(default_factory=lambda: ScoreRegion(355, 640, 86, 76))
    right: ScoreRegion = field(default_factory=lambda: ScoreRegion(622, 640, 86, 76))

    sample_every_n_frames: int = 3       # process every Nth frame (3 = 20fps; ample for a scoreline)
    bin_threshold: int = 190             # grayscale threshold isolating the bright white digit
    min_match: float = 0.55              # min 1-NN correlation to accept a digit (else: no reading)
    stable_reads: int = 4                # consecutive equal reads to confirm a score (rejects misreads)
    min_gap_s: float = 4.0               # goals nearer than this collapse to one (digit morph + RL
                                         # celebration/kickoff mean real goals can't be this close)

    # --- personal scorer: did the USER score this team goal, or a teammate? (scorer.py) ---
    # PRIMARY signal: the '<NAME> SCORED!' banner matching the user's name; BACKUP: the
    # 'GOAL +100' points popup. Both shape-matched over a window around the goal.
    banner: ScoreRegion = field(default_factory=lambda: ScoreRegion(150, 948, 610, 112))
    popup: ScoreRegion = field(default_factory=lambda: ScoreRegion(395, 795, 310, 130))
    banner_bin: int = 180                # threshold isolating the bright banner text
    popup_bin: int = 200                 # threshold isolating the bright '+100' text
    name_match: float = 0.55             # banner-name correlation -> the user scored
    popup_match: float = 0.70            # +100 correlation -> the user scored (backup)
    scorer_before_s: float = 4.0         # window starts this far BEFORE the goal (scoreboard lags)
    scorer_after_s: float = 6.0          # ...and ends this far after
    scorer_stride: int = 9               # frames between samples while scanning the window

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GoalConfig":
        kw: dict[str, Any] = dict(d)
        for region in ("left", "right", "banner", "popup"):
            if kw.get(region) is not None:
                kw[region] = ScoreRegion(**kw[region])
        return cls(**kw)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "GoalConfig":
        if path is None:
            return cls()
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
