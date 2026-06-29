"""Command registry for the JSON-RPC server (spec §5.2).

Open/Closed: register a new command by adding it to REGISTRY, never by editing the
dispatcher. Phase 0 exposes only probe(); detect / render / fetch_music land in later
phases as new entries here.
"""
from __future__ import annotations

from typing import Any, Callable

from backend.probe import probe as _probe


def probe(clip_path: str) -> dict[str, Any]:
    """probe(clip_path) -> {duration, width, height, fps}  (spec §5.2)."""
    return _probe(clip_path)


REGISTRY: dict[str, Callable[..., Any]] = {
    "probe": probe,
}
