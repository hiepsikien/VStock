"""Phase 4 texture cells: binding, cell-bar selection, and Suite dispatch."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace

import pytest

from app.sonify.form import METER_24, METER_44
from app.sonify.guitar_suite_gate import SuiteGate, render_sentence
from app.sonify.guitar_villa_figures import VILLA_ARPEGGIO
from app.sonify.pattern_figures import PatternFigure, derive_body_sentence
from app.sonify.sentence_specs import SENTENCE_SPECS, Select, SentenceSpec, Slot, Span
from app.sonify.texture_figure import (
    TEXTURE_CELLS,
    bind_texture,
    register_texture_cell,
    render_texture_bar,
    render_texture_cell,
    unregister_texture_cell,
)
from app.studio.texture_spec import AuthoredEvent, PitchRef, TextureSpec
from tests.guitar_fixture import pattern_case


@pytest.fixture(autouse=True)
def _isolate_cells():
    saved = {key: dict(value) for key, value in TEXTURE_CELLS.items()}
    TEXTURE_CELLS.clear()
    try:
        yield
    finally:
        TEXTURE_CELLS.clear()
        TEXTURE_CELLS.update(saved)


def _event(
    *,
    bar: int,
    voice: int,
    beat: float = 0.0,
    duration: float = 1.0,
    pitch: PitchRef | None = None,
    tie: str = "none",
    slur: str = "none",
) -> AuthoredEvent:
    return AuthoredEvent(
        bar=bar,
        beat=beat,
        duration_beats=duration,
        voice=voice,
        pitch=PitchRef.literal_midi(60 + voice) if pitch is None else pitch,
        tie=tie,
        slur=slur,
    )


def _texture(
    events: tuple[AuthoredEvent, ...],
    *,
    id: str = "key_figure",
) -> TextureSpec:
    return TextureSpec(
        id=id,
        composer="Villa-Lobos",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        authored=events,
    )


def _case(*, meter=METER_44, bars: int = 8):
    ctx, _phrases = pattern_case(
        "study",
        meter,
        ensemble="villa",
        mood="calm",
        band="mf",
        bpm=96,
        bars=bars,
        movement_span="1W",
        movement_index=0,
    )
    return ctx


# ---------------------------------------------------------------------------
# bind_texture
# ---------------------------------------------------------------------------


def test_bind_texture_moves_only_melody_eighth_indexes() -> None:
    texture = _texture(
        (
            _event(bar=1, voice=1, pitch=PitchRef.melody_eighth(3)),
            _event(bar=1, voice=3, pitch=PitchRef.chord_root()),
        )
    )
    bound = bind_texture(texture, bar_offset=5, epb=4)

    melody, bass = bound.authored
    assert melody.pitch.eighth == 3 + 5 * 4
    assert melody.bar == 1  # bar is authored_to_events' job, not bind's
    assert bass.pitch.kind == "chord_root"
    assert bass.bar == 1
    assert bind_texture(texture, bar_offset=0, epb=4) is texture


def test_bind_texture_rejects_a_bad_offset() -> None:
    texture = _texture((_event(bar=0, voice=1),))
    with pytest.raises(ValueError):
        bind_texture(texture, bar_offset=-1, epb=4)
    with pytest.raises(ValueError):
        bind_texture(texture, bar_offset=1, epb=0)


# ---------------------------------------------------------------------------
# render_texture_bar
# ---------------------------------------------------------------------------


def test_render_texture_bar_selects_one_cell_bar_and_reindexes() -> None:
    ctx = _case(bars=8)
    texture = _texture(
        (
            _event(bar=0, voice=1, pitch=PitchRef.melody_eighth(0)),
            _event(bar=1, voice=1, pitch=PitchRef.melody_eighth(2)),
            _event(bar=1, voice=3, beat=0, duration=4, pitch=PitchRef.chord_root()),
            _event(bar=1, voice=2, beat=0, duration=2, pitch=PitchRef.chord_degree(2)),
        )
    )

    lead, support, low = render_texture_bar(texture, ctx, 5, cell_bar=1)

    assert [note.bar for note in lead] == [5]
    assert [note.bar for note in support] == [5]
    assert [note.bar for note in low] == [5]
    assert lead[0].midi == ctx.melody[5 * ctx.epb + 2]
    assert lead[0].voice == 1
    assert support[0].voice == 2
    assert low[0].voice == 3


def test_render_texture_bar_uses_bar_beats_for_the_target_meter() -> None:
    ctx = _case(meter=METER_24, bars=6)
    texture = _texture(
        (
            _event(bar=0, voice=1, duration=2, pitch=PitchRef.melody_eighth(0)),
            _event(bar=0, voice=3, duration=2, pitch=PitchRef.chord_root()),
        )
    )
    lead, _support, low = render_texture_bar(texture, ctx, 2)
    assert all(note.bar == 2 for note in (*lead, *low))
    assert all(note.beat + note.duration_beats <= 2 for note in (*lead, *low))


def test_render_texture_bar_clears_endpoints_at_the_cell_edges() -> None:
    ctx = _case(bars=4)
    one_bar = _texture(
        (
            _event(
                bar=0,
                voice=1,
                duration=4,
                pitch=PitchRef.melody_eighth(0),
                tie="start",
                slur="start",
            ),
        )
    )
    first, _support, _low = render_texture_bar(one_bar, ctx, 0, cell_bar=0)
    # First and last bar of the cell: a tie/slur with no partner is dropped.
    assert first[0].tie_start is False
    assert first[0].slur_start is False

    three_bars = _texture(
        (
            _event(bar=0, voice=1, duration=4, pitch=PitchRef.melody_eighth(0)),
            _event(
                bar=1,
                voice=1,
                duration=4,
                pitch=PitchRef.melody_eighth(2),
                tie="start",
                slur="start",
            ),
            _event(bar=2, voice=1, duration=4, pitch=PitchRef.melody_eighth(4)),
        )
    )
    middle, _support, _low = render_texture_bar(
        three_bars, ctx, 1, cell_bar=1
    )
    # An interior cell bar keeps the endpoint; the next cell bar will render
    # its partner at the next target bar.
    assert middle[0].tie_start is True
    assert middle[0].slur_start is True


def test_render_texture_bar_returns_empty_for_an_unwritten_cell_bar() -> None:
    ctx = _case()
    texture = _texture((_event(bar=0, voice=1),))
    assert render_texture_bar(texture, ctx, 0, cell_bar=3) == ([], [], [])


def test_render_texture_cell_returns_none_for_an_unknown_cell() -> None:
    ctx = _case()
    assert (
        render_texture_cell(ctx, 0, None, "missing", 0, "suite_x", "4/4")
        is None
    )


def test_render_texture_cell_resolves_the_registered_table() -> None:
    ctx = _case()
    texture = _four_bar_cell_texture()
    register_texture_cell("suite_x", "4/4", "key_a", texture)
    lead, _support, _low = render_texture_cell(
        ctx, 2, None, "key_a", 2, "suite_x", "4/4"
    )
    assert [note.bar for note in lead] == [2]
    assert lead[0].midi == ctx.melody[2 * ctx.epb + 4]


def test_texture_cells_register_is_idempotent_and_replaces() -> None:
    texture = _texture((_event(bar=0, voice=1),))
    assert register_texture_cell("suite_x", "4/4", "key_a", texture) is True
    assert register_texture_cell("suite_x", "4/4", "key_a", texture) is False
    other = replace(texture, id="other")
    with pytest.raises(ValueError, match="already registered"):
        register_texture_cell("suite_x", "4/4", "key_a", other)
    assert (
        register_texture_cell("suite_x", "4/4", "key_a", other, replace=True)
        is True
    )
    assert TEXTURE_CELLS[("suite_x", "4/4")]["key_a"] is other
    assert unregister_texture_cell("suite_x", "4/4", "key_a") is True
    assert ("suite_x", "4/4") not in TEXTURE_CELLS


# ---------------------------------------------------------------------------
# SuiteGate cell dispatch
# ---------------------------------------------------------------------------


def _cell_gate(*, render_cell=None, valid_cells=None) -> SuiteGate:
    @contextmanager
    def no_flag(_enabled: bool = True):
        yield

    spec = SentenceSpec(
        id="unit_cell_body",
        pattern="unit_cell_gate",
        meter="4/4",
        select=Select(length_min=4),
        span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(0, 4, cell="key_a"),),
    )
    return SuiteGate(
        pattern="unit_cell_gate",
        meter="4/4",
        title="Unit cell",
        name_source="dance",
        min_bars=4,
        sentence_id=spec.id,
        spec=spec,
        caveat="",
        enabled=lambda: True,
        use_flag=no_flag,
        render_cell=render_cell,
        valid_cells=valid_cells,
        movement_scopes=frozenset({("1W", 0)}),
    )


def _four_bar_cell_texture() -> TextureSpec:
    return _texture(
        (
            _event(bar=0, voice=1, duration=4, pitch=PitchRef.melody_eighth(0)),
            _event(bar=1, voice=1, duration=4, pitch=PitchRef.melody_eighth(2)),
            _event(bar=2, voice=1, duration=4, pitch=PitchRef.melody_eighth(4)),
            _event(bar=3, voice=1, duration=4, pitch=PitchRef.melody_eighth(6)),
        )
    )


def test_suite_gate_renders_a_cell_tile_through_render_cell() -> None:
    ctx = _case(bars=4)
    calls: list[tuple[int, str, int]] = []
    texture = _four_bar_cell_texture()

    def dispatch(ctx, bar, phrase, cell_id, cell_bar):
        calls.append((bar, cell_id, cell_bar))
        return render_texture_bar(texture, ctx, bar, cell_bar=cell_bar)

    gate = _cell_gate(render_cell=dispatch, valid_cells=frozenset({"key_a"}))
    sentence = render_sentence(
        gate,
        ctx,
        lambda *_args: (_ for _ in ()).throw(AssertionError("figure renderer called")),
    )
    assert sentence is not None
    assert calls == [
        (0, "key_a", 0),
        (1, "key_a", 1),
        (2, "key_a", 2),
        (3, "key_a", 3),
    ]
    assert [note.bar for note in sentence.lead] == [0, 1, 2, 3]
    SENTENCE_SPECS.pop(("unit_cell_gate", "4/4"), None)


def test_suite_gate_falls_back_without_a_cell_renderer() -> None:
    ctx = _case(bars=4)
    gate = _cell_gate(render_cell=None)
    assert render_sentence(gate, ctx, lambda *_args: ([], [], [])) is None
    SENTENCE_SPECS.pop(("unit_cell_gate", "4/4"), None)


def test_ensure_registered_rejects_an_unknown_cell() -> None:
    ctx = _case(bars=4)
    gate = _cell_gate(render_cell=lambda *_args: ([], [], []), valid_cells=frozenset())
    with pytest.raises(ValueError, match=r"cells \['key_a'\] are not registered"):
        render_sentence(gate, ctx, lambda *_args: ([], [], []))
    SENTENCE_SPECS.pop(("unit_cell_gate", "4/4"), None)


def test_cell_dispatch_keeps_the_figure_path_unchanged() -> None:
    """A figure-only gate never asks the cell renderer and stays compatible."""
    from app.sonify.guitar_suite_gate import _plan

    ctx = _case(bars=4)
    instruction = derive_body_sentence(
        "unit_figure_gate",
        "4/4",
        PatternFigure(id="fig", cell_id="key_a", bars=4, tags=("key",)),
    )
    gate = replace(
        _cell_gate(render_cell=lambda *_args: ([], [], [])),
        pattern="unit_figure_gate",
        sentence_id=instruction.id,
        spec=SentenceSpec(
            id=instruction.id,
            pattern="unit_figure_gate",
            meter="4/4",
            select=Select(length_min=4),
            span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
            slots=(Slot(0, 4, figure=VILLA_ARPEGGIO),),
        ),
    )
    plan = _plan(gate, ctx)
    assert plan is not None
    figures, cells, _contours, _covered = plan
    assert figures and not cells
    SENTENCE_SPECS.pop(("unit_figure_gate", "4/4"), None)
