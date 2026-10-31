"""Per-pattern Torroba intro and outro doors.

A known pattern id uses its own script. A missing id still uses the shared frame.
"""

from __future__ import annotations

from app.sonify.chords import C, CM
from app.sonify.form import ChordSlot
from app.sonify.guitar_patterns import _Ctx, _under_lead, assert_playable
from app.sonify.keys import C_KEY
from app.sonify.model import NoteEvent, Score

_METERS = {
    "4/4": {"epb": 8, "kind": "4/4", "strong": (0, 4), "bar_beats": 4.0, "beats": 4, "beat_type": 4},
    "3/4": {"epb": 6, "kind": "3/4", "strong": (0,), "bar_beats": 3.0, "beats": 3, "beat_type": 4},
    "6/8": {"epb": 6, "kind": "6/8", "strong": (0, 3), "bar_beats": 3.0, "beats": 6, "beat_type": 8},
}
_PATTERNS = (
    "castillo",
    "sonatina",
    "fandanguillo",
    "danza",
    "torroba_tremolo",
    "alcaniz",
    "olite",
)
_NATIVE = {
    "castillo": ("4/4", "3/4", "6/8"),
    "sonatina": ("4/4", "3/4", "6/8"),
    "fandanguillo": ("4/4", "3/4", "6/8"),
    "danza": ("6/8", "4/4"),
    "torroba_tremolo": ("3/4", "4/4", "6/8"),
    "alcaniz": ("6/8", "4/4", "3/4"),
    "olite": ("4/4", "6/8", "3/4"),
}


def _region(pattern: str | None, length: int, meter: str, *, mode: str = "major", closing: bool = False):
    from app.sonify.guitar_frame import render_intro, render_outro

    grid = _METERS[meter]
    chord = CM if mode == "minor" else C
    total = length + 1
    melody = [72] * (total * grid["epb"])
    if closing:
        kinds = {0: "phrase"}
        kinds.update({bar: "outro" for bar in range(1, total)})
        frame = list(range(1, total))
    else:
        kinds = {bar: "intro" for bar in range(length)}
        kinds[length] = "phrase"
        frame = list(range(length))
    ctx = _Ctx(
        melody=melody,
        raw=list(melody),
        chord_at={bar: chord for bar in range(total)},
        kind_at=kinds,
        band_at={bar: "mf" for bar in range(total)},
        phrases=(),
        bars=total,
        bpm=96,
        ensemble="torroba",
        mode=mode,
        character="calm",
        character_at=None,
        sections=(),
        rel_span=1.0,
        semitones=0,
        bass_low=40,
        bass_high=53,
        mid_low=50,
        mid_high=65,
        treble_floor=59,
        treble_top=81,
        ceiling=83,
        epb=grid["epb"],
        kind=grid["kind"],
        strong=grid["strong"],
        bar_beats=grid["bar_beats"],
    )
    render = render_outro if closing else render_intro
    lead, support, low = render(ctx, frame, pattern=pattern)
    return lead, support, low, frame


def _score(lead, support, low, meter: str, *, mode: str = "major", bars: int) -> Score:
    grid = _METERS[meter]
    chord = CM if mode == "minor" else C
    slots = tuple(ChordSlot(bar, 1, chord, "sideway", "phrase") for bar in range(bars + 1))
    return Score(
        title="Guitar",
        bpm=96,
        bars=bars + 1,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=slots,
        high=(),
        lead=tuple(lead),
        support=tuple(support),
        comp=(),
        low=tuple(low),
        dynamics=(),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="torroba",
        divisions=4,
        beats=grid["beats"],
        beat_type=grid["beat_type"],
        bar_beats=grid["bar_beats"],
        mode=mode,
    )


def _sounding(events, bar: int) -> list[NoteEvent]:
    return [note for note in events if note.bar == bar and note.midi is not None]


def _eighth(note: NoteEvent) -> int | None:
    doubled = note.beat * 2
    nearest = round(doubled)
    if abs(doubled - nearest) > 1e-6:
        return None
    return int(nearest)


def _onsets(events, bar: int) -> set[int]:
    return {eighth for note in _sounding(events, bar) if (eighth := _eighth(note)) is not None}


def _all_notes(lead, support, low, bar: int | None = None) -> list[NoteEvent]:
    notes = [note for note in (*lead, *support, *low) if note.midi is not None]
    if bar is None:
        return notes
    return [note for note in notes if note.bar == bar]


def _fingerprint(lead, support, low):
    return [
        (note.bar, round(note.beat * 4), note.midi, round(note.duration_beats * 4), note.voice, note.velocity, note.accent)
        for note in _all_notes(lead, support, low)
    ]


def _twelfths(lead, support, low) -> list[int]:
    return [round(note.beat * 12) for note in _all_notes(lead, support, low)]


def test_seven_keys_dispatch_to_their_own_doors() -> None:
    from app.sonify.guitar_frame import _RETAINED_DOORS, _extra_doors
    from app.sonify.guitar_torroba_doors import DOORS

    extra = _extra_doors()
    assert set(DOORS) == {("torroba", pattern) for pattern in _PATTERNS}
    assert len(set(DOORS.values())) == 7
    for key, door in DOORS.items():
        assert _RETAINED_DOORS[key] is door
        assert extra[key] is door
        assert door.__module__ == "app.sonify.guitar_torroba_doors"
    missing = _fingerprint(*_region(None, 2, "4/4")[:3])
    unknown = _fingerprint(*_region("not-a-door", 2, "4/4")[:3])
    castillo = _fingerprint(*_region("castillo", 2, "4/4")[:3])
    assert missing == unknown
    assert missing != castillo


def test_doors_stay_playable_on_native_and_forced_meters() -> None:
    for pattern, meters in _NATIVE.items():
        for meter in meters:
            for length in (1, 2, 4):
                for closing in (False, True):
                    for mode in ("major", "minor"):
                        lead, support, low, _frame = _region(
                            pattern, length, meter, mode=mode, closing=closing
                        )
                        notes = _all_notes(lead, support, low)
                        assert notes, (pattern, meter, length, closing, mode)
                        assert all(slot % 3 == 0 for slot in _twelfths(lead, support, low)), (
                            pattern,
                            meter,
                            length,
                            closing,
                        )
                        assert_playable(
                            _score(lead, support, low, meter, mode=mode, bars=length),
                            C_KEY,
                            "torroba",
                        )


def test_only_castillo_calls_the_bell(monkeypatch) -> None:
    from app.sonify import guitar_torroba_doors as doors

    called: list[bool] = []
    real = doors._bell_chord

    def spy(ctx, bar, velocity, *, picardy: bool):
        called.append(picardy)
        return real(ctx, bar, velocity, picardy=picardy)

    monkeypatch.setattr(doors, "_bell_chord", spy)
    for pattern in _PATTERNS:
        meter = _NATIVE[pattern][0]
        for length in (2, 4):
            for mode in ("major", "minor"):
                for closing in (False, True):
                    called.clear()
                    _region(pattern, length, meter, mode=mode, closing=closing)
                    if pattern == "castillo" and closing:
                        assert called == [mode == "minor"], (length, mode)
                    else:
                        assert called == [], (pattern, length, mode, closing)


def test_fandanguillo_short_intro_opens_mf_on_the_eighth() -> None:
    lead, support, low, frame = _region("fandanguillo", 2, "4/4")
    opening = [note for note in _sounding(lead, frame[0]) if note.beat == 0]
    assert opening
    assert opening[0].velocity == 64
    assert opening[0].accent
    assert all(slot % 3 == 0 for slot in _twelfths(lead, support, low))
    long_lead, _support, _low, long_frame = _region("fandanguillo", 4, "4/4")
    long_open = [note for note in _sounding(long_lead, long_frame[0]) if note.beat == 0]
    assert long_open
    assert long_open[0].velocity == 50


def test_juglar_intro_attacks_each_beat_and_leads_in_at_eighth_five() -> None:
    lead, support, low, frame = _region("torroba_tremolo", 2, "3/4")
    opening = _sounding(lead, frame[0])
    assert _onsets(lead, frame[0]) == {0, 2, 4}
    assert _onsets(low, frame[0]) == {0}
    assert len({note.midi for note in opening}) == 1
    by_eighth = {_eighth(note): note for note in opening}
    assert by_eighth[0].velocity == 46
    assert by_eighth[0].duration_beats == 1
    echo, _bass = _under_lead(46, "mf")
    assert echo < 46
    assert by_eighth[2].velocity == echo
    assert by_eighth[4].velocity == echo
    assert by_eighth[2].duration_beats == 1
    assert by_eighth[4].duration_beats == 1
    assert all(not note.accent for note in _all_notes(lead, support, low, frame[0]))
    arrival = _sounding(lead, frame[1])
    assert {0, 2, 4, 5} <= _onsets(lead, frame[1])
    arrived = {_eighth(note): note for note in arrival}
    assert arrived[0].duration_beats == 1
    assert arrived[4].duration_beats == 0.5
    assert arrived[0].midi == arrived[2].midi == arrived[4].midi
    later, _bass = _under_lead(arrived[0].velocity, "mf")
    assert later < arrived[0].velocity
    assert arrived[2].velocity == later
    assert arrived[4].velocity == later
    assert not arrived[2].accent and not arrived[4].accent
    at_five = [note for note in _all_notes(lead, support, low, frame[1]) if _eighth(note) == 5]
    assert len(at_five) == 1
    one_lead, _one_support, _one_low, one_frame = _region("torroba_tremolo", 1, "3/4")
    assert {0, 2, 4, 5} <= _onsets(one_lead, one_frame[0])


def test_alcaniz_holds_the_second_group_and_cuts_only_the_last_outro() -> None:
    lead, support, low, frame = _region("alcaniz", 4, "6/8")
    opening = _all_notes(lead, support, low, frame[0])
    assert len(opening) == 2
    assert len({note.beat for note in opening}) == 2
    assert _sounding(lead, frame[0])[0].velocity == 50
    last = frame[3]
    down = [note for note in _sounding(lead, last) if _eighth(note) == 0]
    later = [note for note in _sounding(lead, last) if _eighth(note) == 3]
    assert down and down[0].velocity == 56
    assert later and later[0].duration_beats == 1.5
    short_lead, short_support, short_low, short_frame = _region("alcaniz", 2, "6/8")
    touched = short_frame[1]
    second = [note for note in _sounding(short_lead, touched) if _eighth(note) == 3]
    assert second and second[0].duration_beats == 1.5
    assert 4 in _onsets(short_low, touched)
    assert 5 not in _onsets(short_lead, touched) | _onsets(short_support, touched) | _onsets(short_low, touched)
    outro_lead, outro_support, outro_low, outro_frame = _region("alcaniz", 2, "6/8", closing=True)
    early = _sounding(outro_lead, outro_frame[0])
    assert early and all(not note.staccato and note.duration_beats == 1.5 for note in early)
    closing = _sounding(outro_lead, outro_frame[1])
    assert {0, 3} <= _onsets(outro_lead, outro_frame[1])
    assert all(note.duration_beats == 0.5 for note in closing)
    marked = [note for note in closing if _eighth(note) == 3]
    assert marked and marked[0].accent and marked[0].velocity == 64
    one_lead, one_support, one_low, one_frame = _region("alcaniz", 1, "6/8")
    assert [note for note in _sounding(one_lead, one_frame[0]) if _eighth(note) == 3][0].duration_beats == 1.5
    assert 4 in _onsets(one_low, one_frame[0])


def test_olite_keeps_both_chords_and_the_breath_has_no_second_chord() -> None:
    lead, support, low, frame = _region("olite", 2, "4/4")
    opening = _sounding(lead, frame[0])
    assert _onsets(lead, frame[0]) == {0, 4}
    assert all(note.staccato and note.accent and note.velocity == 50 for note in opening)
    assert 0 in _onsets(low, frame[0]) and 4 in _onsets(low, frame[0])
    touched = _sounding(lead, frame[1])
    assert 4 in _onsets(lead, frame[1])
    assert {6, 7} <= _onsets(lead, frame[1])
    scale = [note for note in touched if _eighth(note) in {6, 7}]
    assert {note.beat for note in scale} == {3.0, 3.5}
    one_lead, _one_support, _one_low, one_frame = _region("olite", 1, "4/4")
    assert 4 in _onsets(one_lead, one_frame[0])
    assert {6, 7} <= _onsets(one_lead, one_frame[0])
    long_lead, long_support, long_low, long_frame = _region("olite", 4, "4/4", closing=True)
    breath = long_frame[2]
    assert all(_eighth(note) != 4 for note in _all_notes(long_lead, long_support, long_low, breath))
    sung = _sounding(long_lead, breath)
    assert len(sung) == 1
    assert _eighth(sung[0]) == 0
    assert sung[0].duration_beats == 1
    assert sung[0].velocity == 50


def test_castillo_doors_and_juglar_hold_shorten_the_bass() -> None:
    _lead, _support, low, frame = _region("castillo", 4, "4/4")
    # Role 0 is still a whole-bar pedal. Roles 1 and 2 were `bass_length=ctx.epb`.
    assert _sounding(low, frame[0])
    assert all(note.duration_beats == 4.0 for note in _sounding(low, frame[0]))
    for bar in frame[1:3]:
        basses = _sounding(low, bar)
        assert basses
        assert {_eighth(note) for note in basses} == {0}
        assert all(note.duration_beats == 1.0 for note in basses)
    outro_lead, _outro_support, outro_low, outro_frame = _region("castillo", 4, "4/4", closing=True)
    for bar in outro_frame[:3]:
        basses = _sounding(outro_low, bar)
        assert basses
        assert {_eighth(note) for note in basses} == {0}
        assert all(note.duration_beats == 1.0 for note in basses)
    assert any(note.duration_beats > 1.0 for note in _sounding(outro_lead, outro_frame[0]))

    hold_lead, _hold_support, hold_low, hold_frame = _region("torroba_tremolo", 4, "3/4", closing=True)
    for bar in hold_frame[2:]:
        basses = _sounding(hold_low, bar)
        assert basses
        assert {_eighth(note) for note in basses} == {0}
        assert all(note.duration_beats == 1.0 for note in basses)
        assert any(note.duration_beats == 3.0 for note in _sounding(hold_lead, bar))
    short_lead, _short_support, short_low, short_frame = _region("torroba_tremolo", 2, "3/4", closing=True)
    held = _sounding(short_low, short_frame[1])
    assert held and all(note.duration_beats == 1.0 for note in held)
    motor = _sounding(short_low, short_frame[0])
    assert motor and all(note.duration_beats == 0.5 for note in motor)
    assert any(note.duration_beats == 1.0 for note in _sounding(short_lead, short_frame[0]))


def test_danza_four_four_fallback_is_not_empty() -> None:
    lead, support, low, frame = _region("danza", 2, "4/4")
    assert _all_notes(lead, support, low)
    assert 0 in _onsets(lead, frame[0])
    assert 0 in _onsets(low, frame[0])
    assert {1, 2} <= _onsets(lead, frame[0])
    one_lead, one_support, one_low, _one_frame = _region("danza", 1, "4/4")
    assert _all_notes(one_lead, one_support, one_low)
