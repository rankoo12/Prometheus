"""Caption transcription tuning (spec §6.3).

Whisper model/runtime choices, kept OUT of the styling Profile (SRP). Defaults are CPU int8
`base.en` — fast and accurate enough for short clips; CUDA is an optional speed-up later.
Language lives in the Profile (`captions.language`) and is passed to the source separately.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionConfig:
    model_size: str = "base.en"     # Whisper model; base.en = English-only, small + fast
    device: str = "cpu"             # "cuda" to use the GPU (needs CUDA libs)
    compute_type: str = "int8"      # int8 on CPU; "float16" on CUDA
    beam_size: int = 5
