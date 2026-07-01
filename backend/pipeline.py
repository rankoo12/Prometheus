"""Full pipeline (spec §3, §8) — run every Source, then every Handler, then one combined render.

The composition root: wires the boost / goal / caption detectors + handlers, loads their template
banks, and hands the MERGED instruction list to the Renderer for a single pass (all overlays +
slow-motion retiming; captions are re-timed through any slow-mo). Music/trim layer onto the
Renderer (later in Phase 5). Each stage is gated by its Profile `enabled` flag, so the pipeline
stays Open/Closed — a new event type is a new Source+Handler added here, not an edit to the render.
"""
from __future__ import annotations

from pathlib import Path

from backend.detection.caption_config import CaptionConfig
from backend.detection.config import DetectionConfig
from backend.detection.gauge import load_templates as _load_boost_templates
from backend.detection.goal_config import GoalConfig
from backend.detection.scoreboard import load_bank
from backend.detection.scorer import GoalScorer, load_templates as _load_scorer_templates
from backend.handlers.boost_handler import BoostHandler
from backend.handlers.caption_handler import CaptionHandler
from backend.handlers.goal_handler import GoalHandler
from backend.models.event import Event
from backend.models.instruction import EditInstruction
from backend.models.profile import Profile
from backend.render.renderer import render
from backend.sources.boost_source import BoostSource
from backend.sources.caption_source import CaptionSource
from backend.sources.goal_source import GoalSource

_DET = Path(__file__).resolve().parent / "detection"


def detect_events(clip_path: str, profile: Profile, *, verbose: bool = False) -> list[Event]:
    """Run every enabled Source over the clip and return the merged event stream."""
    events: list[Event] = []
    if profile.data["boost"].get("enabled", True):
        templates = _load_boost_templates(str(_DET / "templates"))
        events += BoostSource(clip_path, templates, DetectionConfig(), verbose=verbose).detect()
    if profile.data["goal"].get("enabled", True):
        gcfg = GoalConfig()
        scorer = GoalScorer(
            _load_scorer_templates(_DET / "scorer_templates" / "name"),
            _load_scorer_templates(_DET / "scorer_templates" / "popup"),
            gcfg,
        )
        events += GoalSource(clip_path, load_bank(_DET / "score_templates"), gcfg,
                             scorer=scorer, verbose=verbose).detect()
    if profile.data["captions"].get("enabled", True):
        lang = profile.data["captions"].get("language", "en")
        events += CaptionSource(clip_path, CaptionConfig(), language=lang, verbose=verbose).detect()
    return events


def build_instructions(events: list[Event], profile: Profile) -> list[EditInstruction]:
    """Run every Handler over the events and return the merged instruction list."""
    return (
        BoostHandler(DetectionConfig().gauge).handle(events, profile)
        + GoalHandler().handle(events, profile)
        + CaptionHandler().handle(events, profile)
    )


def resolve_music(profile: Profile) -> str | None:
    """The music track path if music is enabled and the file exists, else None."""
    m = profile.data["music"]
    f = m.get("file")
    return f if (m.get("enabled") and f and Path(f).is_file()) else None


def export(clip_path: str, profile: Profile, out_path: str, *, verbose: bool = False) -> str:
    """Detect -> decide -> render the whole clip in one pass: overlays + slow-mo retiming, plus
    music (mixed under the voice, ducked, loudness-normalized) per the Profile."""
    events = detect_events(clip_path, profile, verbose=verbose)
    instructions = build_instructions(events, profile)
    o, m, a = profile.data["output"], profile.data["music"], profile.data["audio"]
    return render(
        clip_path, instructions, int(o["width"]), int(o["height"]), out_path,
        crf=int(o.get("crf", 19)), fps=int(o.get("fps", 60)),
        music_path=resolve_music(profile), music_gain_db=float(m.get("gain_db", 0.0)),
        duck=bool(m.get("duck_under_voice", False)),
        norm_lufs=float(a["normalize_lufs"]), true_peak=float(a["true_peak_db"]),
    )
