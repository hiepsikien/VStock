"""Phase A renderer seam: a StudioPiece writes authored cells through production.

The score is compared against ``render_texture_bar`` itself: a literal-MIDI cell
resolves identically in any context, so the only allowed difference after the
shared tail is the wave's velocity change. Notes, voices, bar placement and
durations must not move.
"""

from __future__ import annotations

import hashlib

import pytest

from app.sonify.form import METER_24, METER_44, FormSection, FormSpec
from app.sonify.model import Bar
from app.sonify.musicxml import score_to_musicxml
from app.sonify.params import compose_params
from app.sonify.render import render
from app.sonify.studio_piece import (
    ArrangementBar,
    StudioPiece,
    render_studio_arrangement,
)
from app.sonify.texture_figure import render_texture_bar
from app.studio.texture_spec import AuthoredEvent, PitchRef, TextureSpec
from tests.guitar_fixture import pattern_case

_UNSET = object()


def _bars(count: int) -> list[Bar]:
    return [Bar(100.0 + (index % 4) * 40, 250.0) for index in range(count * 4)]


def _form(bars: int, meter) -> FormSpec:
    return FormSpec(
        bars,
        120,
        (FormSection(0, bars, "phrase", 0),),
        meter=meter,
    )


def _texture(
    *,
    id: str,
    meter,
    pitches: tuple[tuple[int, tuple[int, ...]], ...],
) -> TextureSpec:
    """One cell bar per ``(bar, pitches)`` pair, each pitch a quarter note."""
    events: list[AuthoredEvent] = []
    epb = meter.eighths_per_bar
    for bar, voices in pitches:
        for beat in range(epb // 2):
            for voice, midi in enumerate(voices, start=1):
                events.append(
                    AuthoredEvent(
                        bar=bar,
                        beat=float(beat),
                        duration_beats=1.0,
                        voice=voice,
                        pitch=PitchRef.literal_midi(midi),
                    )
                )
    return TextureSpec(
        id=id,
        composer="Test",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        authored=tuple(events),
    )


def _ctx(meter, bars: int):
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


def _render_piece(
    piece,
    meter,
    bars: int,
    *,
    studio=_UNSET,
):
    kwargs = dict(
        variant="guitar",
        ensemble="villa",
        form=_form(bars, meter),
        framed=True,
    )
    with compose_params({}):
        if studio is _UNSET:
            return render(_bars(bars), **kwargs)
        return render(_bars(bars), studio_piece=studio, **kwargs)


def _note_key(event) -> tuple:
    return (
        event.bar,
        round(event.beat, 6),
        round(event.duration_beats, 6),
        event.voice,
        event.midi,
    )


def _notes(events) -> list[tuple]:
    return sorted(_note_key(event) for event in events if event.midi is not None)


def _expected(piece: StudioPiece, ctx, bars: int):
    lead, support, low = render_studio_arrangement(ctx, piece)
    return _notes(lead), _notes(support), _notes(low)


def _assert_matches_authored(score, piece: StudioPiece, ctx, bars: int) -> None:
    lead, support, low = _expected(piece, ctx, bars)
    assert _notes(score.lead) == lead
    assert _notes(score.support) == support
    assert _notes(score.low) == low


@pytest.mark.parametrize(
    ("meter", "voice_pitches"),
    [
        (METER_44, ((59, 55, 40), (62, 55, 45), (64, 57, 47), (60, 52, 43))),
        (METER_24, ((59, 55, 40), (62, 55, 45), (64, 57, 47), (60, 52, 43))),
    ],
)
def test_studio_piece_renders_authored_notes_without_drift(meter, voice_pitches) -> None:
    bars = 4
    cell = _texture(
        id="key",
        meter=meter,
        pitches=tuple((index, pitches) for index, pitches in enumerate(voice_pitches)),
    )
    piece = StudioPiece(
        pattern="studio_test",
        meter=f"{(meter.beats)}/{meter.beat_type}",
        cells={"key": cell},
        arrangement=tuple(
            ("cell", "key", index) for index in range(bars)
        ),
    )
    assert piece.validate() == ()

    score = _render_piece(piece, meter, bars, studio=piece)
    assert score.bars == bars
    _assert_matches_authored(score, piece, _ctx(meter, bars), bars)


def test_arrangement_uses_each_bars_own_cell_bar() -> None:
    bars = 4
    # A different pitch per cell bar, arranged out of order. Target bar 3 reads
    # cell bar 0, target bar 2 reads cell bar 2, and so on; target bar 0 reads
    # an interior cell bar without touching bar 0 of the cell.
    voice_pitches = ((60, 55, 40), (62, 57, 43), (64, 59, 45), (65, 60, 47))
    cell = _texture(
        id="key",
        meter=METER_44,
        pitches=tuple((index, pitches) for index, pitches in enumerate(voice_pitches)),
    )
    arrangement = (
        ArrangementBar.cell("key", 3),
        ("cell", "key", 1),
        ("cell", "key", 2),
        ("cell", "key", 0),
    )
    piece = StudioPiece(
        pattern="studio_test",
        meter="4/4",
        cells={"key": cell},
        arrangement=arrangement,
    )

    score = _render_piece(piece, METER_44, bars, studio=piece)
    _assert_matches_authored(score, piece, _ctx(METER_44, bars), bars)

    lead_by_bar = {note.bar: note.midi for note in score.lead}
    assert lead_by_bar == {0: 65, 1: 62, 2: 64, 3: 60}


def test_studio_piece_none_keeps_the_default_path_byte_identical() -> None:
    bars = 4
    without_flag = _render_piece(None, METER_44, bars)
    with_none = _render_piece(None, METER_44, bars, studio=None)

    def digest(score) -> str:
        xml = score_to_musicxml(score)
        notes = "\n".join(
            repr(
                (
                    event.voice,
                    event.bar,
                    event.beat,
                    event.duration_beats,
                    event.midi,
                    event.velocity,
                )
            )
            for voice in (score.lead, score.support, score.low)
            for event in voice
        )
        return hashlib.sha256((xml + notes).encode()).hexdigest()

    assert digest(without_flag) == digest(with_none)


def test_studio_piece_validate_reports_unknown_cells_and_bad_bars() -> None:
    cell = _texture(id="key", meter=METER_44, pitches=((0, (60, 55, 40)),))
    piece = StudioPiece(
        pattern="studio_test",
        meter="4/4",
        cells={"key": cell},
        arrangement=(("cell", "missing", -1),),
    )
    errors = piece.validate()
    assert any("unknown cell" in error for error in errors)
    assert any("source_bar" in error for error in errors)


def test_studio_piece_figure_entries_are_reserved_for_phase_b() -> None:
    cell = _texture(id="key", meter=METER_44, pitches=((0, (60, 55, 40)),))
    piece = StudioPiece(
        pattern="studio_test",
        meter="4/4",
        cells={"key": cell},
        arrangement=(("figure", "cadence", 0),),
    )
    assert piece.validate() == ()
    with pytest.raises(NotImplementedError, match="Phase B"):
        render_studio_arrangement(_ctx(METER_44, 1), piece)


def test_render_texture_bar_and_arrangement_agree() -> None:
    bars = 2
    cell = _texture(
        id="key",
        meter=METER_24,
        pitches=((0, (59, 55, 40)), (1, (62, 57, 43))),
    )
    piece = StudioPiece(
        pattern="studio_test",
        meter="2/4",
        cells={"key": cell},
        arrangement=(("cell", "key", 0), ("cell", "key", 1)),
    )
    ctx = _ctx(METER_24, bars)
    lead, support, low = render_studio_arrangement(ctx, piece)
    first = render_texture_bar(cell, ctx, 0, cell_bar=0)
    second = render_texture_bar(cell, ctx, 1, cell_bar=1)
    assert lead == [*first[0], *second[0]]
    assert support == [*first[1], *second[1]]
    assert low == [*first[2], *second[2]]


def test_compressed_frame_uses_both_cell_bars() -> None:
    texture = _texture(
        id="cell_frame",
        meter=METER_44,
        pitches=((0, (60,)), (1, (61,))),
    )
    piece = StudioPiece(
        pattern="studio_frame",
        meter="4/4",
        cells={"cell_frame": texture},
        arrangement=(("compressed", "cell_frame", 0),),
    )
    ctx = _ctx(METER_44, 1)
    lead, _support, _low = render_studio_arrangement(ctx, piece)
    midis = {event.midi for event in lead}
    assert 60 in midis and 61 in midis
    assert {round(event.beat, 3) for event in lead} == {0.0, 1.0, 2.0, 3.0}
