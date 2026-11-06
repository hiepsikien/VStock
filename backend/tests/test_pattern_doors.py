"""Phase 4 doors: frame role mapping, compiled cells, seam, and registry."""

from __future__ import annotations

import pytest

from app.sonify.form import METER_24, METER_44
from app.sonify.guitar_frame import _RETAINED_DOORS, _extra_doors, frame_roles
from app.sonify.pattern_doors import (
    STUDIO_DOOR_METERS,
    STUDIO_DOORS,
    compile_figure_doors,
    frame_role_bar,
    register_studio_door,
    unregister_studio_door,
)
from app.sonify.pattern_figures import PatternFigure
from app.sonify.texture_figure import TEXTURE_CELLS, register_texture_cell
from app.studio.texture_spec import AuthoredEvent, PitchRef, TextureSpec
from tests.guitar_fixture import pattern_case

PATTERN = "suite_door_unit"
METER = "4/4"


@pytest.fixture(autouse=True)
def _isolate_registries():
    saved_cells = {key: dict(value) for key, value in TEXTURE_CELLS.items()}
    saved_doors = dict(STUDIO_DOORS)
    saved_meters = dict(STUDIO_DOOR_METERS)
    TEXTURE_CELLS.clear()
    STUDIO_DOORS.clear()
    STUDIO_DOOR_METERS.clear()
    try:
        yield
    finally:
        TEXTURE_CELLS.clear()
        TEXTURE_CELLS.update(saved_cells)
        STUDIO_DOORS.clear()
        STUDIO_DOOR_METERS.clear()
        STUDIO_DOORS.update(saved_doors)
        STUDIO_DOOR_METERS.update(saved_meters)


def _event(
    *,
    bar: int,
    voice: int,
    beat: float = 0.0,
    duration: float = 2.0,
    midi: int,
    tie: str = "none",
    slur: str = "none",
) -> AuthoredEvent:
    return AuthoredEvent(
        bar=bar,
        beat=beat,
        duration_beats=duration,
        voice=voice,
        pitch=PitchRef.literal_midi(midi),
        tie=tie,
        slur=slur,
    )


def _texture(
    bars: int,
    *,
    id: str,
    bar_beats: float = 4.0,
    first_tie: str = "none",
    first_slur: str = "none",
    last_tie: str = "none",
    last_slur: str = "none",
    last_full: bool = False,
) -> TextureSpec:
    """One lead/support/low note in each authored bar, with stable MIDI."""
    half = bar_beats / 2
    events: list[AuthoredEvent] = []
    for bar in range(bars):
        lead_length = bar_beats if last_full and bar == bars - 1 else half
        events.append(
            _event(
                bar=bar,
                voice=1,
                beat=0,
                duration=lead_length,
                midi=72 + bar,
                tie=last_tie if bar == bars - 1 else "none",
                slur=last_slur if bar == bars - 1 else "none",
            )
        )
        events.append(
            _event(bar=bar, voice=2, beat=half, duration=half, midi=60 + bar)
        )
        events.append(
            _event(
                bar=bar,
                voice=3,
                beat=0,
                duration=bar_beats,
                midi=48 + bar,
                tie=first_tie if bar == 0 else "none",
                slur=first_slur if bar == 0 else "none",
            )
        )
    return TextureSpec(
        id=id,
        composer="Villa-Lobos",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        authored=tuple(events),
    )


def _figure(figure_id: str, cell_id: str, bars: int, tags: tuple[str, ...]) -> PatternFigure:
    return PatternFigure(id=figure_id, cell_id=cell_id, bars=bars, tags=tags)


def _ctx(*, meter=METER_44, bars: int = 8):
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


def _pool() -> tuple[PatternFigure, ...]:
    return (
        _figure("fig_in2", "cell_in2", 2, ("intro.short",)),
        _figure("fig_in4", "cell_in4", 4, ("intro.long",)),
        _figure("fig_out2", "cell_out2", 2, ("outro.short",)),
        _figure("fig_out4", "cell_out4", 4, ("outro.long",)),
    )


def _register_doors() -> None:
    register_texture_cell(PATTERN, METER, "cell_in2", _texture(2, id="cell_in2"))
    register_texture_cell(PATTERN, METER, "cell_in4", _texture(4, id="cell_in4"))
    register_texture_cell(
        PATTERN,
        METER,
        "cell_out2",
        _texture(2, id="cell_out2"),
    )
    register_texture_cell(
        PATTERN,
        METER,
        "cell_out4",
        _texture(4, id="cell_out4"),
    )


def _door():
    intro_short, intro_long, outro_short, outro_long = _pool()
    return compile_figure_doors(
        PATTERN,
        METER,
        intro_short,
        intro_long,
        outro_short,
        outro_long,
    )


# ---------------------------------------------------------------------------
# frame_role_bar
# ---------------------------------------------------------------------------


def test_frame_role_bar_short_and_long_steps() -> None:
    assert [frame_role_bar(role, steps=2) for role in range(2)] == [0, 1]
    assert [frame_role_bar(role, steps=4) for role in range(4)] == [0, 1, 2, 3]


def test_frame_role_bar_three_and_one_bar_frame_roles() -> None:
    # A three-bar frame uses the long script's 0/2/3 steps.
    assert frame_roles(3) == [0, 2, 3]
    assert [frame_role_bar(role, steps=4) for role in frame_roles(3)] == [0, 2, 3]
    # A one-bar frame compresses the short script's two roles.
    assert frame_roles(1) == [0]
    assert [frame_role_bar(role, steps=2) for role in (0, 1)] == [0, 1]


def test_frame_role_bar_rejects_bad_steps_and_roles() -> None:
    with pytest.raises(ValueError, match="steps must be 2 or 4"):
        frame_role_bar(0, steps=3)
    with pytest.raises(ValueError, match="role must be an integer"):
        frame_role_bar(-1, steps=4)
    with pytest.raises(ValueError, match="role must be an integer"):
        frame_role_bar(4, steps=4)
    with pytest.raises(ValueError, match="role must be an integer"):
        frame_role_bar(2, steps=2)
    with pytest.raises(ValueError, match="role must be an integer"):
        frame_role_bar(True, steps=2)  # bool is not a role


# ---------------------------------------------------------------------------
# compile_figure_doors
# ---------------------------------------------------------------------------


def test_short_door_uses_role_as_cell_bar_and_returns_frame_specs() -> None:
    _register_doors()
    door = _door()
    ctx = _ctx()

    specs = door(ctx, 5, 1, steps=2, closing=False, index=1)

    assert specs
    for offset, length, midi, voice, velocity, flags in specs:
        assert 0 <= offset < ctx.epb
        assert length >= 1
        assert offset + length <= ctx.epb
        assert voice in (1, 2, 3)
        assert isinstance(velocity, int)
        assert isinstance(flags, dict)
    # Cell bar 1: the authored lead is 72 + 1, support 60 + 1, low 48 + 1.
    assert {midi for _o, _l, midi, voice, _v, _f in specs if voice == 1} == {73}
    assert {midi for _o, _l, midi, voice, _v, _f in specs if voice == 2} == {61}
    assert {midi for _o, _l, midi, voice, _v, _f in specs if voice == 3} == {49}


def test_long_door_uses_the_long_cell_for_the_requested_role() -> None:
    _register_doors()
    door = _door()
    ctx = _ctx()

    specs = door(ctx, 4, 2, steps=4, closing=False, index=2)

    assert {midi for _o, _l, midi, voice, _v, _f in specs if voice == 1} == {74}
    assert all(offset + length <= ctx.epb for offset, length, *_rest in specs)


def test_closing_door_selects_outro_and_missing_cell_is_silent() -> None:
    _register_doors()
    door = _door()
    ctx = _ctx()

    closing = door(ctx, 0, 0, steps=2, closing=True, index=0)
    assert {midi for _o, _l, midi, voice, _v, _f in closing if voice == 1} == {72}

    TEXTURE_CELLS[(PATTERN, METER)].pop("cell_out2")
    assert door(ctx, 0, 0, steps=2, closing=True, index=0) == []


def test_two_four_door_keeps_offsets_inside_the_bar() -> None:
    register_texture_cell(
        PATTERN,
        "2/4",
        "cell_in2",
        _texture(
            2,
            id="cell_in2",
            bar_beats=2.0,
            first_tie="stop",
            first_slur="stop",
        ),
    )
    register_texture_cell(
        PATTERN, "2/4", "cell_in4", _texture(4, id="cell_in4", bar_beats=2.0)
    )
    register_texture_cell(
        PATTERN, "2/4", "cell_out2", _texture(2, id="cell_out2", bar_beats=2.0)
    )
    register_texture_cell(
        PATTERN, "2/4", "cell_out4", _texture(4, id="cell_out4", bar_beats=2.0)
    )
    intro_short, intro_long, outro_short, outro_long = _pool()
    door = compile_figure_doors(
        PATTERN,
        "2/4",
        intro_short,
        intro_long,
        outro_short,
        outro_long,
    )
    ctx = _ctx(meter=METER_24, bars=4)

    specs = door(ctx, 1, 0, steps=2, closing=True, index=0)
    assert all(offset + length <= ctx.epb for offset, length, *_rest in specs)
    assert all(offset < ctx.epb for offset, *_rest in specs)


def test_door_seam_has_no_hanging_tie_on_the_frame_edges() -> None:
    """Intro's last bar and outro's first bar close their endpoints."""
    register_texture_cell(
        PATTERN,
        METER,
        "cell_in2",
        _texture(
            2,
            id="cell_in2",
            last_tie="start",
            last_slur="start",
            last_full=True,
        ),
    )
    register_texture_cell(PATTERN, METER, "cell_in4", _texture(4, id="cell_in4"))
    register_texture_cell(
        PATTERN,
        METER,
        "cell_out2",
        _texture(2, id="cell_out2", first_tie="stop", first_slur="stop"),
    )
    register_texture_cell(PATTERN, METER, "cell_out4", _texture(4, id="cell_out4"))
    register_texture_cell(
        PATTERN, METER, "cell_key", _texture(1, id="cell_key")
    )
    door = _door()
    ctx = _ctx()

    # A two-bar intro's last bar, the key bar, then the outro's first bar.
    intro = door(ctx, 1, 1, steps=2, closing=False, index=1)
    outro = door(ctx, 3, 0, steps=2, closing=True, index=0)
    key = TEXTURE_CELLS[(PATTERN, METER)]["cell_key"]
    from app.sonify.texture_figure import render_texture_bar

    key_lead, key_support, key_low = render_texture_bar(key, ctx, 2, cell_bar=0)

    assert all(not flags.get("tie_start") for *_rest, flags in intro)
    assert all(not flags.get("slur_start") for *_rest, flags in intro)
    assert all(not flags.get("tie_stop") for *_rest, flags in outro)
    assert all(not flags.get("slur_stop") for *_rest, flags in outro)

    # Structural seam: every rendered note stays inside its own bar and no
    # voice overlaps across the three bars.
    spans: dict[int, list[tuple[int, int]]] = {1: [], 2: [], 3: []}
    for bar, specs in ((1, intro), (2, None), (3, outro)):
        if specs is None:
            specs = [
                (
                    int(round(event.beat * 2)),
                    max(1, int(round(event.duration_beats * 2))),
                    event.midi,
                    event.voice,
                    int(event.velocity or 0),
                    {},
                )
                for event in (*key_lead, *key_support, *key_low)
            ]
        for offset, length, _midi, voice, _velocity, _flags in specs:
            absolute = bar * ctx.epb + offset
            assert offset + length <= ctx.epb
            assert not any(
                absolute < end and start < absolute + length
                for start, end in spans[voice]
            )
            spans[voice].append((absolute, absolute + length))


# ---------------------------------------------------------------------------
# registry hook
# ---------------------------------------------------------------------------


def test_studio_door_registration_merges_without_touching_retained_doors() -> None:
    door = lambda ctx, bar, role, **kwargs: []  # noqa: E731
    key = ("villa", PATTERN)
    assert key not in _RETAINED_DOORS

    assert register_studio_door(*key, door) is True
    assert register_studio_door(*key, door) is False
    assert _extra_doors()[key] is door
    assert key not in _RETAINED_DOORS

    with pytest.raises(ValueError, match="already registered"):
        register_studio_door(*key, lambda *args, **kwargs: [])

    assert unregister_studio_door(*key) is True
    assert unregister_studio_door(*key) is False
    assert key not in _extra_doors()
    assert key not in _RETAINED_DOORS


def test_registered_studio_door_reaches_render_intro() -> None:
    from app.sonify.guitar_frame import render_intro

    _register_doors()
    door = _door()
    register_studio_door("villa", PATTERN, door)
    ctx = _ctx()

    lead, support, low = render_intro(ctx, [4, 5], pattern=PATTERN)

    assert lead or support or low
    for note in (*lead, *support, *low):
        assert note.bar in (4, 5)
    # Cell bar 0 and 1 for the short script.
    assert {note.midi for note in lead if note.bar == 4} == {72}
    assert {note.midi for note in lead if note.bar == 5} == {73}


def test_studio_door_cannot_shadow_a_production_door() -> None:
    def door(ctx, bar, role, **kwargs):
        return []

    with pytest.raises(ValueError, match="production pattern/door"):
        register_studio_door("villa", "suite_schottish", door)


def test_one_studio_door_pattern_cannot_switch_meter_silently() -> None:
    def door(ctx, bar, role, **kwargs):
        return []

    assert register_studio_door("villa", "studio_meter_unit", door, meter="4/4")
    with pytest.raises(ValueError, match="already registered for 4/4"):
        register_studio_door("villa", "studio_meter_unit", door, meter="2/4", replace=True)


def test_dispatch_ignores_a_meter_mismatched_studio_door() -> None:
    from app.sonify.guitar_frame import _dispatch

    pattern = "studio_meter_dispatch"
    def door(ctx, bar, role, **kwargs):
        return [(0, 1, 127, 1, 56, {})]

    register_studio_door("villa", pattern, door, meter="4/4")
    four = _ctx(meter=METER_44)
    two = _ctx(meter=METER_24)
    assert _dispatch(four, 0, 0, steps=2, closing=False, index=0, pattern=pattern)
    fallback = _dispatch(two, 0, 0, steps=2, closing=False, index=0, pattern=pattern)
    assert all(midi != 127 for _o, _l, midi, *_rest in fallback)
