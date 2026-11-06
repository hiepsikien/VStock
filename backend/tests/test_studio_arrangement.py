"""Phase B arrangement builder: tags -> body roles -> a renderable StudioPiece."""

from __future__ import annotations

import pytest

from app.sonify.form import METER_24, FormSection, FormSpec
from app.sonify.pattern_figures import PatternFigure
from app.sonify.studio_arrangement import ArrangementResult, build_arrangement
from app.sonify.studio_piece import render_studio_arrangement
from app.studio.texture_spec import AuthoredEvent, PitchRef, TextureSpec
from tests.guitar_fixture import pattern_case


def _texture(cell_id: str, bars: int) -> TextureSpec:
    return TextureSpec(
        id=cell_id,
        composer="Test",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        authored=tuple(
            AuthoredEvent(
                bar=bar,
                beat=0.0,
                duration_beats=1.0,
                voice=1,
                pitch=PitchRef.literal_midi(60 + bar),
            )
            for bar in range(bars)
        ),
    )


def _figure(
    figure_id: str,
    cell_id: str,
    bars: int,
    tags: tuple[str, ...],
) -> PatternFigure:
    return PatternFigure(id=figure_id, cell_id=cell_id, bars=bars, tags=tags)


def _pool(
    *,
    contrast: bool = True,
    close: bool = True,
    key_bars: int = 4,
) -> list[PatternFigure]:
    figures = [
        _figure("fig_key", "cell_key", key_bars, ("key",)),
        _figure("fig_in2", "cell_in2", 2, ("intro.short",)),
        _figure("fig_in4", "cell_in4", 4, ("intro.long",)),
        _figure("fig_out2", "cell_out2", 2, ("outro.short",)),
        _figure("fig_out4", "cell_out4", 4, ("outro.long",)),
    ]
    if contrast:
        figures.append(_figure("fig_b", "cell_b", 4, ("contrast",)))
    if close:
        figures.append(_figure("fig_close", "cell_close", 2, ("close",)))
    return figures


def _form(
    parts: list[tuple[int, str]],
    *,
    bridge_index: int | None = None,
) -> FormSpec:
    """Build a contiguous form from ``(length, kind)`` parts."""
    sections: list[FormSection] = []
    start = 0
    for index, (length, kind) in enumerate(parts):
        sections.append(
            FormSection(
                start,
                start + length,
                kind,  # type: ignore[arg-type]
                0,
                bridge=index == bridge_index,
            )
        )
        start += length
    return FormSpec(
        bars=start,
        bpm=100,
        sections=tuple(sections),
        meter=METER_24,
    )


def _textures(figures: list[PatternFigure]) -> dict[str, TextureSpec]:
    return {
        figure.cell_id: _texture(figure.cell_id, figure.bars)
        for figure in figures
    }


def _build(
    form: FormSpec,
    *,
    policy: str = "auto_aaba",
    figures: list[PatternFigure] | None = None,
) -> ArrangementResult:
    pool = _pool() if figures is None else figures
    return build_arrangement(
        pattern="studio_test",
        meter="2/4",
        figures=pool,
        form=form,
        policy=policy,
        textures=_textures(pool),
    )


def _cells(result: ArrangementResult) -> list[str]:
    return [entry.source_id for entry in result.piece.arrangement]


def _bars(result: ArrangementResult) -> list[int]:
    return [entry.source_bar for entry in result.piece.arrangement]


# ---------------------------------------------------------------------------
# Body policy
# ---------------------------------------------------------------------------


def test_auto_aaba_four_sections_are_a_a_b_close() -> None:
    form = _form([(1, "phrase")] * 4)
    result = _build(form)

    assert result.roles == ("A", "A", "B", "close")
    assert _cells(result) == ["cell_key", "cell_key", "cell_b", "cell_close"]
    assert result.warnings == ()
    assert "contrast" in result.used_tags
    assert "close" in result.used_tags
    assert result.piece.validate() == ()


def test_b_falls_back_to_key_with_a_warning_when_contrast_is_absent() -> None:
    form = _form([(1, "phrase")] * 4)
    result = _build(form, figures=_pool(contrast=False))

    assert result.roles == ("A", "A", "B", "close")
    assert _cells(result)[2] == "cell_key"
    assert "B fallback: key" in result.warnings
    assert "close" in result.used_tags


def test_close_falls_back_to_key_with_a_warning_when_close_is_absent() -> None:
    form = _form([(1, "phrase")] * 4)
    result = _build(form, figures=_pool(close=False))

    assert result.roles == ("A", "A", "B", "close")
    assert _cells(result)[-1] == "cell_key"
    assert "close fallback: key" in result.warnings
    assert "contrast" in result.used_tags


def test_trio_three_sections_are_a_b_a() -> None:
    form = _form([(1, "phrase")] * 3)
    result = _build(form, policy="trio")

    assert result.roles == ("A", "B", "A")
    assert _cells(result) == ["cell_key", "cell_b", "cell_key"]
    assert result.warnings == ()
    assert "close" not in result.used_tags


def test_trio_honours_a_bridge_section_for_b() -> None:
    form = _form([(1, "phrase")] * 5, bridge_index=3)
    result = _build(form, policy="trio")

    assert result.roles[3] == "B"
    assert _cells(result)[3] == "cell_b"
    # Five phrases leave room for a closing unit after the A/B/A.
    assert result.roles[-1] == "close"
    assert _cells(result)[-1] == "cell_close"


def test_default_pool_without_optional_tags_still_builds() -> None:
    form = _form([(1, "phrase")] * 3)
    result = _build(form, figures=_pool(contrast=False, close=False))

    assert result.roles == ("A", "B", "close")
    assert result.warnings == ("B fallback: key", "close fallback: key")
    assert result.piece.validate() == ()


# ---------------------------------------------------------------------------
# Frame doors
# ---------------------------------------------------------------------------


def test_two_bar_intro_uses_intro_short_cell_bars() -> None:
    result = _build(_form([(2, "intro"), (1, "phrase")]))

    assert _cells(result)[:2] == ["cell_in2", "cell_in2"]
    assert _bars(result)[:2] == [0, 1]


def test_four_bar_intro_uses_intro_long_cell_bars() -> None:
    result = _build(_form([(4, "intro"), (1, "phrase")]))

    assert _cells(result)[:4] == ["cell_in4"] * 4
    assert _bars(result)[:4] == [0, 1, 2, 3]


def test_three_bar_frame_plays_roles_zero_two_three() -> None:
    result = _build(_form([(3, "intro"), (1, "phrase")]))

    assert _cells(result)[:3] == ["cell_in4"] * 3
    assert _bars(result)[:3] == [0, 2, 3]


def test_one_bar_frame_is_compressed_to_short_cell_bar_zero() -> None:
    result = _build(_form([(1, "intro"), (1, "phrase")]))

    assert _cells(result)[0] == "cell_in2"
    assert _bars(result)[0] == 0


def test_two_bar_outro_uses_outro_short_cell_bars() -> None:
    result = _build(_form([(1, "phrase"), (2, "outro")]))

    assert _cells(result)[-2:] == ["cell_out2", "cell_out2"]
    assert _bars(result)[-2:] == [0, 1]


def test_warmup_and_cooldown_are_frames_too() -> None:
    result = _build(_form([(2, "warmup"), (1, "phrase"), (2, "cooldown")]))

    assert _cells(result)[0] == "cell_in2"
    assert _cells(result)[-1] == "cell_out2"


# ---------------------------------------------------------------------------
# Tiling and resolution
# ---------------------------------------------------------------------------


def test_body_source_bars_tile_by_figure_length() -> None:
    # Two body phrases: a three-bar A then a one-bar close. A two-bar key cell
    # must wrap 0, 1, 0 inside the A phrase and never overflow.
    form = _form([(3, "phrase"), (1, "phrase")])
    pool = _pool(key_bars=2)
    result = _build(form, figures=pool)

    assert result.roles == ("A", "A", "A", "close")
    assert _bars(result) == [0, 1, 0, 0]
    assert result.piece.validate() == ()
    bars_by_cell = {figure.cell_id: figure.bars for figure in pool}
    for entry in result.piece.arrangement:
        assert entry.source_id in result.piece.cells
        assert 0 <= entry.source_bar < bars_by_cell[entry.source_id]


def test_arrangement_cells_render_without_overflow() -> None:
    form = _form([(2, "intro"), (4, "phrase"), (2, "outro")])
    result = _build(form)

    assert len(result.roles) == 4
    assert len(result.piece.arrangement) == form.bars

    ctx, _phrases = pattern_case(
        "study",
        METER_24,
        ensemble="villa",
        mood="calm",
        band="mf",
        bpm=96,
        bars=form.bars,
        movement_span="1W",
        movement_index=0,
    )
    lead, support, low = render_studio_arrangement(ctx, result.piece)
    assert lead or support or low


def test_missing_texture_is_a_hard_error() -> None:
    form = _form([(1, "phrase")])
    with pytest.raises(ValueError, match="no texture for cell"):
        build_arrangement(
            pattern="studio_test",
            meter="2/4",
            figures=_pool(),
            form=form,
            textures={},
        )


def test_unknown_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown arrangement policy"):
        _build(_form([(1, "phrase")]), policy="abab")
