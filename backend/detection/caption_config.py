"""Caption transcription tuning (spec §6.3).

Whisper model/runtime choices, kept OUT of the styling Profile (SRP). Defaults are CPU int8
`base.en` — fast and accurate enough for short clips; CUDA is an optional speed-up later.
Language lives in the Profile (`captions.language`) and is passed to the source separately.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionConfig:
    # small.en is the sweet spot on this footage: it transcribes MORE COMPLETELY than medium.en,
    # which (being more "confident") drops some quick/quiet words. Bigger != better for word
    # coverage. base.en is a lighter fallback; the occasional wrong word is fixed in Phase 6 review.
    model_size: str = "small.en"    # Whisper model; *.en = English-only
    device: str = "cpu"             # "cuda" to use the GPU (needs CUDA libs)
    compute_type: str = "int8"      # int8 on CPU; "float16" on CUDA
    beam_size: int = 5
