"""The pattern registry: `level` and `name_source` cover `_FAMILY` exactly.

Metadata only. These tests pin the split the model doc section 12 decided: five
texture ids, thirty-three topics, and a printed title for every topic.
"""

from __future__ import annotations

import pytest

from app.sonify.guitar_patterns import _FAMILY
from app.sonify.pattern_registry import (
    LEVELS,
    NAME_SOURCES,
    PATTERN_META,
    PatternMeta,
    meta,
    validate,
)
from app.sonify.program import _PATTERN_TITLE, pattern_title

# The five texture ids. `thumb_cantabile` is one id for two ensembles.
_TEXTURE = {
    "villa_pattern",
    "chord_melody",
    "tremolo",
    "thumb_cantabile",
    "pedal",
}
_TOPIC = set(_FAMILY) - _TEXTURE


def test_registry_covers_family() -> None:
    assert set(PATTERN_META) == set(_FAMILY)
    assert len(PATTERN_META) == 38


def test_registry_key_matches_id() -> None:
    for pattern, found in PATTERN_META.items():
        assert isinstance(found, PatternMeta)
        assert found.id == pattern


def test_level_sets_are_exact() -> None:
    topic = {
        pattern for pattern, found in PATTERN_META.items() if found.level == "topic"
    }
    texture = {
        pattern for pattern, found in PATTERN_META.items() if found.level == "texture"
    }
    assert topic == _TOPIC
    assert texture == _TEXTURE
    assert len(topic) == 33
    assert len(texture) == 5


def test_every_topic_prints_a_title() -> None:
    for pattern in _TOPIC:
        assert pattern_title(pattern, "classic"), pattern


def test_name_source_rules() -> None:
    for pattern, found in PATTERN_META.items():
        assert found.level in LEVELS
        if found.level == "texture":
            assert found.name_source is None, pattern
        else:
            assert found.name_source in NAME_SOURCES, pattern


@pytest.mark.parametrize("pattern", sorted(_TEXTURE))
def test_texture_needs_no_title(monkeypatch: pytest.MonkeyPatch, pattern: str) -> None:
    """A texture owns no name, so validate() must pass with every texture title gone."""
    monkeypatch.delitem(_PATTERN_TITLE, pattern)
    assert validate() is None


def test_validate_rejects_a_topic_without_a_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(_PATTERN_TITLE, "study")
    with pytest.raises(ValueError, match="no printed title"):
        validate()


def test_unknown_pattern_raises() -> None:
    with pytest.raises(KeyError):
        meta("not-a-pattern")


def test_validate_passes_on_the_real_module() -> None:
    assert validate() is None
