"""Render-context tests for ``app.studio.texture_resolve``.

The fixture is the deterministic ``pattern_case`` context used by the render
matrix: a fixed contour, C major/minor chords, fixed registers, no clock or
random source. These tests exercise resolution, the authored → ``NoteEvent``
bridge, and the render-context playability checks. They never mutate
``SENTENCE_SPECS`` and the import test runs in a fresh interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.sonify import sentence_specs
from app.sonify.chords import G7
from app.sonify.form import METER_44
from app.sonify.model import NoteEvent
from app.studio.texture_spec import AuthoredEvent, PitchRef, TextureError, TextureSpec
from app.studio.texture_resolve import (
    HAND_SPAN_LIMIT,
    TextureResolveError,
    authored_to_events,
    check_authored_playable,
    resolve_pitch,
)
from tests.guitar_fixture import pattern_case


def _case(*, mode: str = "major", bars: int = 2):
    ensemble = "classic" if mode == "major" else "villa"
    ctx, _phrases = pattern_case(
        "study",
        METER_44,
        ensemble=ensemble,
        mood="calm",
        band="mf",
        bpm=96,
        bars=bars,
    )
    return ctx


def _event(
    *,
    voice: int = 1,
    beat: float = 0.0,
    duration: float = 4.0,
    pitch: PitchRef | None = None,
    bar: int = 0,
    **overrides,
) -> AuthoredEvent:
    data = {
        "bar": bar,
        "beat": beat,
        "duration_beats": duration,
        "voice": voice,
        "pitch": PitchRef.literal_midi(60) if pitch is None else pitch,
    }
    data.update(overrides)
    return AuthoredEvent(**data)


# ---------------------------------------------------------------------------
# resolve_pitch
# ---------------------------------------------------------------------------


def test_melody_eighth_reads_the_render_melody_and_offset() -> None:
    ctx = _case()
    # fixture contour for bar 0: 67, 65, 64, 62, 60, 62, 64, 65
    assert resolve_pitch(PitchRef.melody_eighth(0), ctx) == 67
    assert resolve_pitch(PitchRef.melody_eighth(2), ctx) == 64
    assert resolve_pitch(PitchRef.melody_eighth(0, offset=2), ctx) == 64
    assert resolve_pitch(PitchRef.melody_eighth(8), ctx) == 67
    assert resolve_pitch(PitchRef.melody_eighth(15, offset=0), ctx) == 65


def test_melody_eighth_out_of_range_is_rejected_not_clamped() -> None:
    ctx = _case()
    with pytest.raises(TextureResolveError) as eighth:
        resolve_pitch(PitchRef.melody_eighth(16), ctx)
    assert eighth.value.path == "pitch.eighth"
    assert "outside melody length" in eighth.value.message

    with pytest.raises(TextureResolveError) as offset:
        resolve_pitch(PitchRef.melody_eighth(15, offset=1), ctx)
    assert offset.value.path == "pitch.offset"
    assert "outside melody length" in offset.value.message

    with pytest.raises(TextureResolveError) as shorter:
        resolve_pitch(PitchRef.melody_eighth(8), ctx, melody_length=8)
    assert shorter.value.path == "pitch.eighth"


def test_chord_degree_and_root_read_the_actual_chord_object() -> None:
    ctx = replace(_case(), chord_at={0: G7, 1: G7})
    # G7 = G B D F = 67, 71, 74, 77. Degree 5 wraps the root by an octave.
    assert resolve_pitch(PitchRef.chord_root(), ctx, bar=0) == 67
    assert resolve_pitch(PitchRef.chord_degree(1), ctx, bar=0) == 67
    assert resolve_pitch(PitchRef.chord_degree(2), ctx, bar=0) == 71
    assert resolve_pitch(PitchRef.chord_degree(3), ctx, bar=0) == 74
    assert resolve_pitch(PitchRef.chord_degree(4), ctx, bar=0) == 77
    assert resolve_pitch(PitchRef.chord_degree(5), ctx, bar=0) == 79
    assert resolve_pitch(PitchRef.chord_root(), ctx, bar=1) == 67


def test_scale_step_walks_the_mode_scale_in_the_lead_register() -> None:
    major = _case()
    # C major inside 59..81, anchored at the scale tone nearest 70 (A, 69).
    assert resolve_pitch(PitchRef.scale_step(0), major) == 69
    assert resolve_pitch(PitchRef.scale_step(-1), major) == 67
    assert resolve_pitch(PitchRef.scale_step(1), major) == 71
    assert resolve_pitch(PitchRef.scale_step(2), major) == 72

    minor = _case(mode="minor")
    # C natural minor, anchored at the scale tone nearest 70 (B♭, 70).
    assert resolve_pitch(PitchRef.scale_step(0), minor) == 70
    assert resolve_pitch(PitchRef.scale_step(-1), minor) == 68
    assert resolve_pitch(PitchRef.scale_step(1), minor) == 72

    # A leap past the register clamps to the edge scale tone.
    assert resolve_pitch(PitchRef.scale_step(99), major) == 81
    assert resolve_pitch(PitchRef.scale_step(-99), major) == 59


def test_literal_midi_is_absolute_and_bounded() -> None:
    ctx = _case()
    assert resolve_pitch(PitchRef.literal_midi(57), ctx) == 57
    assert resolve_pitch(PitchRef.literal_midi(0), ctx) == 0
    assert resolve_pitch(PitchRef.literal_midi(127), ctx) == 127
    with pytest.raises(TextureResolveError) as excinfo:
        resolve_pitch(PitchRef.literal_midi(128), ctx)
    assert excinfo.value.path == "pitch.value"


# ---------------------------------------------------------------------------
# authored_to_events
# ---------------------------------------------------------------------------


def _round_trip_events() -> tuple[AuthoredEvent, ...]:
    return (
        _event(
            voice=1,
            beat=0.0,
            duration=1.5,
            pitch=PitchRef.melody_eighth(0),
            staff=1,
            tie="start",
            slur="start",
            accent=True,
            tenuto=True,
            staccato=True,
        ),
        _event(
            voice=1,
            beat=1.5,
            duration=0.5,
            pitch=PitchRef.melody_eighth(3),
            tie="continue",
            slur="continue",
        ),
        _event(
            voice=1,
            beat=2.0,
            duration=2.0,
            pitch=PitchRef.melody_eighth(4),
            tie="stop",
            slur="stop",
        ),
        _event(
            voice=3,
            beat=0.0,
            duration=4.0,
            pitch=PitchRef.chord_root(),
            staff=2,
            tie="next_bar",
        ),
    )


def test_authored_to_events_preserves_placement_voice_and_notation() -> None:
    ctx = _case()
    notes = authored_to_events(_round_trip_events(), ctx, METER_44)

    assert all(isinstance(note, NoteEvent) for note in notes)
    assert [(note.bar, note.beat, note.duration_beats, note.voice, note.staff) for note in notes] == [
        (0, 0.0, 1.5, 1, 1),
        (0, 1.5, 0.5, 1, 1),
        (0, 2.0, 2.0, 1, 1),
        (0, 0.0, 4.0, 3, 2),
    ]

    first, second, third, bass = notes
    assert (first.midi, first.tie_start, first.tie_stop) == (67, True, False)
    assert (first.slur_start, first.slur_stop) == (True, False)
    assert (first.accent, first.tenuto, first.staccato) == (True, True, True)
    assert (second.tie_start, second.tie_stop) == (True, True)
    assert (second.slur_start, second.slur_stop) == (True, True)
    assert (third.tie_start, third.tie_stop) == (False, True)
    assert (third.slur_start, third.slur_stop) == (False, True)
    assert (bass.midi, bass.tie_start, bass.tie_stop) == (60, True, False)
    assert first.velocity is None
    assert first.hairpin is False and first.pinned is False


def test_authored_to_events_accepts_a_spec_and_shifts_bars() -> None:
    ctx = _case()
    events = _round_trip_events()
    notes = authored_to_events(events, ctx, METER_44, bar_offset=2)
    assert [note.bar for note in notes] == [2, 2, 2, 2]

    spec = TextureSpec(
        id="bridge",
        composer="classic",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        authored=events,
    )
    assert authored_to_events(spec, ctx, METER_44, bar_offset=2) == notes


def test_authored_to_events_is_deterministic() -> None:
    ctx = _case()
    first = authored_to_events(_round_trip_events(), ctx, METER_44)
    second = authored_to_events(_round_trip_events(), ctx, METER_44)
    assert first == second


def test_authored_to_events_rejects_a_pitch_outside_the_melody() -> None:
    ctx = _case()
    event = _event(pitch=PitchRef.melody_eighth(99))
    with pytest.raises(TextureResolveError) as excinfo:
        authored_to_events([event], ctx, METER_44)
    assert excinfo.value.path == "authored.events[0].pitch.eighth"


# ---------------------------------------------------------------------------
# check_authored_playable
# ---------------------------------------------------------------------------


def _valid_playable_events() -> tuple[AuthoredEvent, ...]:
    return (
        _event(
            voice=3,
            pitch=PitchRef.literal_midi(45),
            string=6,
            fret=1,
            written_pitch="A2",
            sounding_pitch="A1",
        ),
        _event(
            voice=2,
            pitch=PitchRef.literal_midi(60),
            string=4,
            fret=5,
            written_pitch="C4",
            sounding_pitch="C3",
        ),
        _event(
            voice=1,
            pitch=PitchRef.literal_midi(69),
            string=1,
            fret=5,
            written_pitch="A4",
            sounding_pitch="A3",
        ),
    )


def test_a_valid_authored_voicing_has_no_playability_problems() -> None:
    report = check_authored_playable(_valid_playable_events(), _case(), METER_44)
    assert report == []
    assert report.skipped == ("profile",)
    assert report.partial is True


def test_resolved_midi_outside_the_guitar_is_reported() -> None:
    event = _event(voice=1, pitch=PitchRef.literal_midi(90))
    report = check_authored_playable([event], _case(), METER_44)
    assert [problem.path for problem in report] == ["authored.events[0].pitch"]
    assert "outside guitar range" in report[0].message


def test_voice_order_bass_below_mid_below_lead() -> None:
    events = (
        _event(voice=3, pitch=PitchRef.literal_midi(72)),
        _event(voice=1, pitch=PitchRef.literal_midi(60)),
    )
    report = check_authored_playable(events, _case(), METER_44)
    assert any("is not below" in problem.message for problem in report)
    assert any(problem.path == "authored.events[0].voice" for problem in report)


def test_non_overlapping_voices_are_not_compared() -> None:
    events = (
        _event(voice=3, beat=0.0, duration=2.0, pitch=PitchRef.literal_midi(72)),
        _event(voice=1, beat=2.0, duration=2.0, pitch=PitchRef.literal_midi(60)),
    )
    report = check_authored_playable(events, _case(), METER_44)
    assert not any("is not below" in problem.message for problem in report)


@pytest.mark.parametrize(
    ("string", "fret", "path"),
    [
        (7, 1, "authored.events[0].string"),
        (6, 13, "authored.events[0].fret"),
        (None, 5, "authored.events[0].fret"),
        (1, -1, "authored.events[0].fret"),
    ],
)
def test_bad_string_or_fret_is_reported(string, fret, path) -> None:
    event = _event(pitch=PitchRef.literal_midi(60), string=string, fret=fret)
    report = check_authored_playable([event], _case(), METER_44)
    assert [problem.path for problem in report] == [path]


def test_written_and_sounding_must_differ_by_an_octave() -> None:
    event = _event(
        pitch=PitchRef.literal_midi(69),
        written_pitch="A4",
        sounding_pitch="G3",
    )
    report = check_authored_playable([event], _case(), METER_44)
    assert [problem.path for problem in report] == ["authored.events[0].sounding_pitch"]
    assert "12" in report[0].message


def test_hand_span_over_five_frets_is_reported() -> None:
    events = (
        _event(voice=3, pitch=PitchRef.literal_midi(41), string=6, fret=1),
        _event(voice=1, pitch=PitchRef.literal_midi(72), string=5, fret=7),
    )
    report = check_authored_playable(events, _case(), METER_44)
    assert any(
        "hand span" in problem.message and problem.path == "authored.events[0].fret"
        for problem in report
    )
    assert HAND_SPAN_LIMIT == 5


def test_missing_tab_and_octave_metadata_is_reported_as_skipped() -> None:
    event = _event(pitch=PitchRef.literal_midi(60))
    report = check_authored_playable([event], _case(), METER_44)
    assert report == []
    assert report.skipped == (
        "string/fret",
        "written/sounding",
        "hand span",
        "profile",
    )


def test_check_reports_a_pitch_that_cannot_resolve() -> None:
    event = _event(pitch=PitchRef.melody_eighth(99))
    report = check_authored_playable([event], _case(), METER_44)
    assert report == [
        TextureError(
            "authored.events[0].pitch.eighth",
            "eighth 99 is outside melody length 16",
        )
    ]


# ---------------------------------------------------------------------------
# Inert import / no runtime mutation
# ---------------------------------------------------------------------------


def test_runtime_registry_is_unchanged_by_resolving() -> None:
    before = dict(sentence_specs.SENTENCE_SPECS)
    ctx = _case()
    authored_to_events(_round_trip_events(), ctx, METER_44)
    check_authored_playable(_valid_playable_events(), ctx, METER_44)
    assert dict(sentence_specs.SENTENCE_SPECS) == before


def test_import_does_not_render_register_or_load_the_pattern_module() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import sys\n"
        "from app.sonify.sentence_specs import SENTENCE_SPECS\n"
        "before = len(SENTENCE_SPECS)\n"
        "import app.studio.texture_resolve\n"
        "print(before, len(SENTENCE_SPECS), "
        "'app.sonify.guitar_patterns' in sys.modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    before, after, loaded = completed.stdout.split()
    assert before == after
    assert loaded == "False"
