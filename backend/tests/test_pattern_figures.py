"""Pure figure-pool rules: tags, completeness, and the derived body sentence."""

from __future__ import annotations

import pytest

from app.sonify.pattern_figures import (
    FIGURE_TAGS,
    KEY_BODY_MISSING,
    REQUIRED_FIGURE_TAGS,
    PatternFigure,
    body_sentence_errors,
    derive_body_sentence,
    figure_tag_errors,
    missing_figure_tags,
    validate_figure_tags,
    validate_figures,
)
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span


def _figure(
    figure_id: str,
    *,
    cell_id: str | None = None,
    bars: int,
    tags: tuple[str, ...],
) -> PatternFigure:
    return PatternFigure(
        id=figure_id,
        cell_id=cell_id or figure_id,
        bars=bars,
        tags=tags,
    )


def test_tag_vocabulary_is_the_five_roles() -> None:
    assert FIGURE_TAGS == {
        "key",
        "intro.short",
        "intro.long",
        "outro.short",
        "outro.long",
    }
    assert REQUIRED_FIGURE_TAGS == (
        "key",
        "intro.short",
        "intro.long",
        "outro.short",
        "outro.long",
    )


def test_multi_tag_is_valid_when_every_tag_matches_the_bar_count() -> None:
    validate_figure_tags(("intro.short", "outro.short"), 2)
    validate_figure_tags(("intro.long", "outro.long"), 4)
    validate_figure_tags(("key",), 1)
    validate_figure_tags(("key", "intro.short"), 2)
    assert figure_tag_errors(("intro.short", "outro.short"), 2) == ()


def test_multi_tag_is_invalid_when_one_tag_disagrees() -> None:
    errors = figure_tag_errors(("key", "intro.short"), 4)
    assert errors and "intro.short" in errors[0]
    errors = figure_tag_errors(("intro.short", "outro.long"), 2)
    assert errors and "outro.long" in errors[0]


def test_short_and_long_require_their_exact_bar_count() -> None:
    with pytest.raises(ValueError, match="needs 2 bars"):
        validate_figure_tags(("intro.short",), 4)
    with pytest.raises(ValueError, match="needs 4 bars"):
        validate_figure_tags(("outro.long",), 2)
    with pytest.raises(ValueError, match="bars must be an integer >= 1"):
        validate_figure_tags(("key",), 0)


def test_unknown_and_duplicate_tags_are_rejected() -> None:
    assert any("unknown" in error for error in figure_tag_errors(("bridge",), 4))
    assert any(
        "duplicate" in error
        for error in figure_tag_errors(("key", "key"), 4)
    )


def test_a_figure_may_carry_multiple_compatible_tags() -> None:
    shared = _figure("fig_2", bars=2, tags=("intro.short", "outro.short"))
    assert validate_figures((shared,)) == ()
    assert "intro.short" not in missing_figure_tags((shared,))
    assert "outro.short" not in missing_figure_tags((shared,))


def test_duplicate_tag_across_figures_is_rejected() -> None:
    first = _figure("fig_a", bars=4, tags=("key",))
    second = _figure("fig_b", bars=4, tags=("key",))
    errors = validate_figures((first, second))
    assert any("claimed by more than one figure" in error for error in errors)
    assert KEY_BODY_MISSING in missing_figure_tags((first, second))


def test_missing_tags_for_an_empty_old_draft() -> None:
    """An old `{sentences}` draft has no figures, so nothing is complete."""
    assert missing_figure_tags(()) == (
        KEY_BODY_MISSING,
        "intro.short",
        "intro.long",
        "outro.short",
        "outro.long",
    )


def test_complete_pool_has_no_missing_tags() -> None:
    figures = (
        _figure("fig_key", bars=4, tags=("key",)),
        _figure("fig_intro2", bars=2, tags=("intro.short",)),
        _figure("fig_intro4", bars=4, tags=("intro.long",)),
        _figure("fig_outro2", bars=2, tags=("outro.short",)),
        _figure("fig_outro4", bars=4, tags=("outro.long",)),
    )
    assert validate_figures(figures) == ()
    assert missing_figure_tags(figures) == ()


def test_key_with_the_wrong_bar_count_reports_key_body() -> None:
    # `key` allows any length >= 1, so a broken key means zero bars, which the
    # dataclass helper cannot express through a tag rule. A key figure tagged
    # with a short/long tag but the wrong bars is the realistic broken case.
    broken = _figure("fig_key", bars=2, tags=("key", "intro.long"))
    assert KEY_BODY_MISSING in missing_figure_tags((broken,))
    assert "intro.long" in missing_figure_tags((broken,))


def test_derive_body_sentence_tiles_the_key_cell() -> None:
    key = _figure("fig_key", cell_id="cell_key", bars=4, tags=("key",))
    spec = derive_body_sentence("suite_x", "2/4", key)
    assert spec.id == "suite_x_cell_key_body"
    assert spec.pattern == "suite_x"
    assert spec.meter == "2/4"
    assert spec.select.length_min == 4
    assert spec.span.tile == 4
    assert spec.span.remainder == "same_figure"
    assert spec.span.truncate_to_length is True
    assert spec.slots == (Slot(0, 4, cell="cell_key"),)


def test_derive_body_sentence_keeps_a_matching_existing_sentence() -> None:
    key = _figure("fig_key", cell_id="cell_key", bars=4, tags=("key",))
    existing = SentenceSpec(
        id="hand_authored",
        pattern="suite_x",
        meter="4/4",
        select=Select(length_min=4),
        span=Span(tile=8, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(0, 4, cell="cell_key"),),
    )
    assert derive_body_sentence(
        "suite_x", "4/4", key, existing=(existing,)
    ) is existing


def test_derive_body_sentence_rejects_a_too_short_tile() -> None:
    key = _figure("fig_key", cell_id="cell_key", bars=4, tags=("key",))
    existing = SentenceSpec(
        id="too_short",
        pattern="suite_x",
        meter="4/4",
        select=Select(length_min=2),
        span=Span(tile=2, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(0, 4, cell="cell_key"),),
    )
    with pytest.raises(ValueError, match="shorter than the key figure"):
        derive_body_sentence("suite_x", "4/4", key, existing=(existing,))
    assert body_sentence_errors(
        "suite_x", "4/4", key, existing=(existing,)
    )


def test_derive_body_sentence_rejects_a_slot_with_wrong_bars() -> None:
    key = _figure("fig_key", cell_id="cell_key", bars=4, tags=("key",))
    existing = SentenceSpec(
        id="wrong_slot",
        pattern="suite_x",
        meter="4/4",
        select=Select(length_min=4),
        span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(0, 2, cell="cell_key"),),
    )
    with pytest.raises(ValueError, match="key cell slot has 2 bars"):
        derive_body_sentence("suite_x", "4/4", key, existing=(existing,))


def test_a_figure_without_the_key_tag_cannot_derive_a_body() -> None:
    not_key = _figure("fig_intro", bars=2, tags=("intro.short",))
    with pytest.raises(ValueError, match="does not carry the 'key' tag"):
        derive_body_sentence("suite_x", "4/4", not_key)
