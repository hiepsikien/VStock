"""Door coverage and profile audit.

Every pattern in `PROFILES` renders a door today, and a door region takes the
body pattern's playability profile rather than falling back to "study".
"""

from __future__ import annotations

from app.sonify.guitar_frame import _extra_doors
from app.sonify.guitar_patterns import _PEDAL_DOOR_PROFILE, _PROFILE, door_profile
from app.sonify.guitar_wave import PROFILES


def test_every_pattern_has_a_door() -> None:
    doors = _extra_doors()
    missing = sorted(key for key in PROFILES if key not in doors)
    assert not missing, missing


def test_door_profiles_follow_the_body_profile() -> None:
    for _ensemble, pattern in PROFILES:
        assert door_profile(pattern) == _PROFILE.get(pattern, "study"), pattern


def test_explicit_door_profiles_agree_with_profile() -> None:
    for pattern, profile in _PEDAL_DOOR_PROFILE.items():
        assert _PROFILE[pattern] == profile, pattern


def test_unknown_door_falls_back_to_study() -> None:
    assert door_profile("not-a-pattern") == "study"


def test_fallback_count_is_deliberate() -> None:
    """A new pattern must either get a door profile entry or accept `_PROFILE`.

    The count is a tripwire: add the entry (or update this number with a reason)
    instead of letting a new pattern fall through unnoticed.
    """
    fallback = {pattern for _ensemble, pattern in PROFILES if pattern not in _PEDAL_DOOR_PROFILE}
    assert len(fallback) == 27
    for pattern in fallback:
        assert door_profile(pattern) == _PROFILE.get(pattern, "study")
