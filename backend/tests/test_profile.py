"""The Profile contract loads and validates against its JSON Schema."""
from __future__ import annotations

import pytest

from backend.models.profile import Profile


def test_default_profile_loads_and_validates():
    profile = Profile.load()  # contracts/profile.default.json, validate=True
    assert profile.data["version"] == 1
    assert profile.data["output"]["width"] == 1080
    assert profile.data["output"]["height"] == 1920


def test_invalid_profile_rejected():
    jsonschema = pytest.importorskip("jsonschema")
    bad = {"version": 1}  # missing every required section
    with pytest.raises(jsonschema.ValidationError):
        Profile.validate(bad)
