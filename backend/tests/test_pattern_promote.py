"""Phase 4 promote: five-tag gate, cell id mapping, and reversible apply."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.sonify.form import METER_44
from app.sonify.pattern_doors import STUDIO_DOOR_METERS, STUDIO_DOORS
from app.sonify.pattern_figures import PatternFigure
from app.sonify.pattern_promote import (
    PromotionPlan,
    apply_promotion,
    promote_figures,
    reset_promotions,
    register_body_sentence,
    unapply_promotion,
)
from app.sonify.sentence_specs import SENTENCE_SPECS, Select, SentenceSpec, Slot, Span
from app.sonify.texture_figure import TEXTURE_CELLS, register_texture_cell
from app.studio.texture_spec import AuthoredEvent, PitchRef, TextureSpec
from tests.guitar_fixture import pattern_case

PATTERN = "suite_promote_unit"
METER = "4/4"


@pytest.fixture(autouse=True)
def _isolate_registries():
    reset_promotions()
    saved_cells = {key: dict(value) for key, value in TEXTURE_CELLS.items()}
    saved_doors = dict(STUDIO_DOORS)
    saved_meters = dict(STUDIO_DOOR_METERS)
    saved_specs = dict(SENTENCE_SPECS)
    TEXTURE_CELLS.clear()
    STUDIO_DOORS.clear()
    STUDIO_DOOR_METERS.clear()
    SENTENCE_SPECS.clear()
    try:
        yield
    finally:
        TEXTURE_CELLS.clear()
        TEXTURE_CELLS.update(saved_cells)
        STUDIO_DOORS.clear()
        STUDIO_DOOR_METERS.clear()
        STUDIO_DOORS.update(saved_doors)
        STUDIO_DOOR_METERS.update(saved_meters)
        SENTENCE_SPECS.clear()
        SENTENCE_SPECS.update(saved_specs)
        reset_promotions()


def _event(*, bar: int, midi: int) -> AuthoredEvent:
    return AuthoredEvent(
        bar=bar,
        beat=0.0,
        duration_beats=2.0,
        voice=1,
        # Production promotion rejects absolute MIDI; the unit fixture uses a
        # relative chord tone so it exercises the real promote contract.
        pitch=PitchRef.chord_root(),
    )


def _texture(bars: int, *, id: str, base: int = 72) -> TextureSpec:
    return TextureSpec(
        id=id,
        composer="Villa-Lobos",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        authored=tuple(_event(bar=bar, midi=base + bar) for bar in range(bars)),
    )


def _figure(
    figure_id: str,
    cell_id: str,
    bars: int,
    tags: tuple[str, ...],
) -> PatternFigure:
    return PatternFigure(id=figure_id, cell_id=cell_id, bars=bars, tags=tags)


def _key() -> PatternFigure:
    return _figure("fig_key", "cell_key", 4, ("key",))


def _pool(*, shared_short: bool = False) -> list[tuple[PatternFigure, TextureSpec]]:
    """Five compatible tags; ``shared_short`` reuses one 2-bar figure."""
    key = _key()
    intro_long = _figure("fig_in4", "cell_in4", 4, ("intro.long",))
    outro_long = _figure("fig_out4", "cell_out4", 4, ("outro.long",))
    if shared_short:
        short = _figure(
            "fig_short", "cell_short", 2, ("intro.short", "outro.short")
        )
        return [
            (key, _texture(4, id="cell_key")),
            (short, _texture(2, id="cell_short")),
            (intro_long, _texture(4, id="cell_in4")),
            (outro_long, _texture(4, id="cell_out4")),
        ]
    intro_short = _figure("fig_in2", "cell_in2", 2, ("intro.short",))
    outro_short = _figure("fig_out2", "cell_out2", 2, ("outro.short",))
    return [
        (key, _texture(4, id="cell_key")),
        (intro_short, _texture(2, id="cell_in2")),
        (intro_long, _texture(4, id="cell_in4")),
        (outro_short, _texture(2, id="cell_out2")),
        (outro_long, _texture(4, id="cell_out4")),
    ]


def _ctx():
    ctx, _phrases = pattern_case(
        "study",
        METER_44,
        ensemble="villa",
        mood="calm",
        band="mf",
        bpm=96,
        bars=8,
        movement_span="1W",
        movement_index=0,
    )
    return ctx


# ---------------------------------------------------------------------------
# Pure plan + five-tag gate
# ---------------------------------------------------------------------------


def test_promote_requires_all_five_tags() -> None:
    pool = [item for item in _pool() if item[0].id != "fig_out4"]
    with pytest.raises(ValueError, match="missing figure tags: outro.long"):
        promote_figures(PATTERN, METER, pool)


def test_promote_rejects_a_tag_with_two_owners() -> None:
    first = _key()
    second = _figure("fig_key_2", "cell_key_2", 4, ("key",))
    pool = [
        (first, _texture(4, id="cell_key")),
        (second, _texture(4, id="cell_key_2")),
    ] + [item for item in _pool() if item[0].id != "fig_key"]
    with pytest.raises(ValueError, match="claimed by more than one figure"):
        promote_figures(PATTERN, METER, pool)


def test_promote_rejects_a_figure_without_a_cell_id() -> None:
    pool = list(_pool())
    key, texture = pool[0]
    pool[0] = (replace(key, cell_id=""), texture)
    with pytest.raises(ValueError, match="cell_id must be non-empty"):
        promote_figures(PATTERN, METER, pool)


def test_promote_is_pure_and_returns_the_expected_plan_shape() -> None:
    plan = promote_figures(PATTERN, METER, _pool())

    assert isinstance(plan, PromotionPlan)
    assert plan.pattern == PATTERN
    assert plan.meter == METER
    assert plan.ensemble == "villa"
    assert plan.body.id == f"{PATTERN}_cell_key_body"
    assert plan.body.slots == (Slot(0, 4, cell="cell_key"),)
    assert plan.tags["key"] is plan.key
    assert set(plan.tags) == {
        "key",
        "intro.short",
        "intro.long",
        "outro.short",
        "outro.long",
    }
    assert set(plan.cells) == {
        "cell_key",
        "cell_in2",
        "cell_in4",
        "cell_out2",
        "cell_out4",
    }
    # Nothing registered by the pure plan.
    assert TEXTURE_CELLS == {}
    assert STUDIO_DOORS == {}
    assert SENTENCE_SPECS == {}


def test_shared_short_figure_covers_both_short_tags() -> None:
    plan = promote_figures(PATTERN, METER, _pool(shared_short=True))
    assert plan.tags["intro.short"] is plan.tags["outro.short"]
    assert plan.tags["intro.short"].cell_id == "cell_short"


def test_promote_reads_existing_texture_cells_for_plain_figures() -> None:
    pool = _pool()
    for figure, texture in pool:
        register_texture_cell(PATTERN, METER, figure.cell_id, texture)
    plan = promote_figures(
        PATTERN, METER, [figure for figure, _texture in pool]
    )
    assert set(plan.cells) == {figure.cell_id for figure, _texture in pool}


# ---------------------------------------------------------------------------
# id vs cellId
# ---------------------------------------------------------------------------


def test_body_slot_uses_cell_id_not_the_figure_id() -> None:
    plan = promote_figures(PATTERN, METER, _pool())

    assert plan.tags["key"].id == "fig_key"
    assert plan.tags["key"].cell_id == "cell_key"
    assert plan.body.slots[0].cell == "cell_key"
    assert "fig_key" not in plan.cells
    assert plan.cell_ids["key"] == "cell_key"


def test_a_sentence_using_the_figure_id_is_rejected() -> None:
    wrong = SentenceSpec(
        id="uses_figure_id",
        pattern=PATTERN,
        meter=METER,
        select=Select(length_min=4),
        span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(0, 4, cell="fig_key"),),
    )
    with pytest.raises(ValueError, match="is a figure id"):
        promote_figures(PATTERN, METER, _pool(), existing_sentences=(wrong,))


# ---------------------------------------------------------------------------
# apply / unapply
# ---------------------------------------------------------------------------


def test_apply_then_unapply_is_idempotent_and_leaves_no_global_leak() -> None:
    plan = promote_figures(PATTERN, METER, _pool())

    body = apply_promotion(plan)
    assert body is plan.body
    assert set(TEXTURE_CELLS[(PATTERN, METER)]) == set(plan.cells)
    assert STUDIO_DOORS[("villa", PATTERN)] is plan.door

    # Applying the same plan again is a no-op, not an error.
    assert apply_promotion(plan) is plan.body

    unapply_promotion(plan)
    assert (PATTERN, METER) not in TEXTURE_CELLS
    assert ("villa", PATTERN) not in STUDIO_DOORS

    # Unapplying twice is also safe.
    unapply_promotion(plan)
    assert TEXTURE_CELLS == {}
    assert STUDIO_DOORS == {}


def test_unapply_leaves_a_replaced_door_alone() -> None:
    plan = promote_figures(PATTERN, METER, _pool())
    apply_promotion(plan)

    replacement = lambda ctx, bar, role, **kwargs: []  # noqa: E731
    from app.sonify.pattern_doors import register_studio_door

    register_studio_door("villa", PATTERN, replacement, replace=True)

    unapply_promotion(plan)
    assert STUDIO_DOORS[("villa", PATTERN)] is replacement


# ---------------------------------------------------------------------------
# Door wiring
# ---------------------------------------------------------------------------


def test_promoted_door_renders_the_requested_cell_bar_at_a_later_bar() -> None:
    plan = promote_figures(PATTERN, METER, _pool())
    apply_promotion(plan)
    ctx = _ctx()

    specs = plan.door(ctx, 3, 2, steps=4, closing=False, index=2)

    assert specs
    assert all(0 <= offset < ctx.epb for offset, *_rest in specs)
    assert all(offset + length <= ctx.epb for offset, length, *_rest in specs)
    assert any(voice == 1 for _o, _l, _m, voice, _v, _f in specs)


def test_register_body_sentence_is_explicit_and_reversible() -> None:
    plan = promote_figures(PATTERN, METER, _pool())
    apply_promotion(plan)
    assert (PATTERN, METER) not in SENTENCE_SPECS

    body = register_body_sentence(plan)
    assert body is plan.body
    assert SENTENCE_SPECS[(PATTERN, METER)] == (plan.body,)
    # Identical re-registration is a no-op, like the shared registry contract.
    register_body_sentence(plan.body)
    assert SENTENCE_SPECS[(PATTERN, METER)] == (plan.body,)


def test_promote_rejects_absolute_literal_midi() -> None:
    pool = list(_pool())
    figure, texture = pool[0]
    literal = replace(
        texture,
        authored=(
            replace(texture.authored[0], pitch=PitchRef.literal_midi(60)),
            *texture.authored[1:],
        ),
    )
    pool[0] = (figure, literal)
    with pytest.raises(ValueError, match="literal_midi is preview-only"):
        promote_figures(PATTERN, METER, pool)


def test_promote_rejects_a_plain_figure_without_a_texture() -> None:
    pool = _pool()
    with pytest.raises(ValueError, match="no texture for cell"):
        promote_figures(PATTERN, METER, [figure for figure, _texture in pool])


def test_second_apply_upserts_and_unapply_restores_the_previous_promotion() -> None:
    first = promote_figures(PATTERN, METER, _pool())
    apply_promotion(first)
    first_door = STUDIO_DOORS[("villa", PATTERN)]

    second = promote_figures(PATTERN, METER, _pool())
    apply_promotion(second)
    assert STUDIO_DOORS[("villa", PATTERN)] is second.door

    unapply_promotion(second)
    assert STUDIO_DOORS[("villa", PATTERN)] is first_door
    assert set(TEXTURE_CELLS[(PATTERN, METER)]) == set(first.cells)

    unapply_promotion(first)
    assert (PATTERN, METER) not in TEXTURE_CELLS
    assert ("villa", PATTERN) not in STUDIO_DOORS
