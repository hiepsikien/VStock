"""Door coverage and profile audit.

Every pattern in `PROFILES` renders a door today. A door region takes the body
pattern's playability profile, so there is no separate door profile table: the
old `_PEDAL_DOOR_PROFILE` duplicated `_PROFILE` entry for entry.
"""

from __future__ import annotations

from app.sonify.guitar_frame import _extra_doors
from app.sonify.guitar_patterns import _PROFILE, door_profile
from app.sonify.guitar_wave import PROFILES


def test_every_pattern_has_a_door() -> None:
    """38/38 PROFILES rows resolve to a door key."""
    doors = _extra_doors()
    missing = sorted(key for key in PROFILES if key not in doors)
    assert not missing, missing


def test_door_profiles_resolve_through_profile() -> None:
    """38/38 rows: door profile == body profile."""
    for _ensemble, pattern in PROFILES:
        assert door_profile(pattern) == _PROFILE.get(pattern, "study"), pattern


def test_unknown_door_falls_back_to_study() -> None:
    assert door_profile("not-a-pattern") == "study"


def test_profile_table_is_single_sourced() -> None:
    """No door-only table: every door name must exist in `_PROFILE`."""
    for _ensemble, pattern in PROFILES:
        assert pattern in _PROFILE, pattern
