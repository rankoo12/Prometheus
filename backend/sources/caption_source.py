"""CaptionSource — transcribe speech to word-timed CAPTION_WORD events (spec §6.3).

Stage 1 of the pipeline: runs Whisper (faster-whisper) with word-level timestamps and emits one
CAPTION_WORD event per spoken word (metadata {"word": text}, t_start/t_end the word's span).
Knows nothing about styling or rendering. The model is loaded lazily so importing this module
(and the pure CaptionHandler) never pulls in Whisper.
"""
from __future__ import annotations

from typing import Iterator

from backend.detection.caption_config import CaptionConfig
from backend.models.event import Event, EventType
from backend.sources.base import Source


class CaptionSource(Source):
    """Configured at construction; `detect()` transcribes the clip and emits CAPTION_WORD events."""

    def __init__(self, clip_path: str, cfg: CaptionConfig | None = None, language: str = "en",
                 verbose: bool = False) -> None:
        self.clip_path = clip_path
        self.cfg = cfg or CaptionConfig()
        self.language = language
        self.verbose = verbose

    def detect(self) -> list[Event]:
        return list(self._words())

    def _words(self) -> Iterator[Event]:
        import sys

        from faster_whisper import WhisperModel

        if self.verbose:
            sys.stderr.write(f"loading whisper {self.cfg.model_size} ({self.cfg.device})...\n")
        model = WhisperModel(self.cfg.model_size, device=self.cfg.device, compute_type=self.cfg.compute_type)
        segments, _ = model.transcribe(
            self.clip_path, language=self.language, word_timestamps=True, beam_size=self.cfg.beam_size
        )
        for seg in segments:
            for w in (seg.words or []):
                text = w.word.strip()
                if not text:
                    continue
                if self.verbose:
                    sys.stderr.write(f"  {w.start:6.2f}-{w.end:5.2f}  {text}\n")
                yield Event(
                    type=EventType.CAPTION_WORD,
                    t_start=float(w.start),
                    t_end=float(w.end),
                    metadata={"word": text},
                )
