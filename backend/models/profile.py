"""Profile — the UI<->backend styling contract (spec §4.3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # validation is best-effort if the optional dep is absent
    jsonschema = None

# backend/models/profile.py -> parents[2] is the repo root
_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SCHEMA_PATH = _CONTRACTS / "profile.schema.json"
DEFAULT_PATH = _CONTRACTS / "profile.default.json"


class Profile:
    """A styling profile.

    A Profile is a JSON *document* validated against contracts/profile.schema.json,
    not a code structure. Principle #2: style is data, not code. Adding a styling
    field means editing the schema + default JSON, never this class.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    @classmethod
    def load(cls, path: str | Path | None = None, *, validate: bool = True) -> "Profile":
        path = Path(path) if path is not None else DEFAULT_PATH
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if validate:
            cls.validate(data)
        return cls(data)

    @staticmethod
    def validate(data: dict[str, Any]) -> None:
        """Raise jsonschema.ValidationError if the document violates the contract.

        No-ops if jsonschema is not installed, so the backend never hard-crashes on an
        optional dependency. Install it (requirements.txt) to enforce the contract.
        """
        if jsonschema is None:
            return
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=data, schema=schema)

    def __repr__(self) -> str:
        return f"Profile(version={self.data.get('version')!r})"
