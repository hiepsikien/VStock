"""Intro and outro doors for prelude, allemande, and courante.

Pedal bars are checked with the study profile. Minor cadences stay minor.
"""

from __future__ import annotations

from app.sonify.chords import C, CM
from app.sonify.form import ChordSlot
from app.sonify.guitar_patterns import _Ctx, assert_playable
from app.sonify.guitar_scale_passages import (
    _BACH_GROUP2,
    _BAROQUE_PATTERNS,
    _HAT_PATTERNS,
    _base_window,
    _bass_onsets,
    _courante_intrinsic_eighths,
    _courante_window,
)
from app.sonify.keys import C_KEY
from app.sonify.model import NoteEvent, Phrase, Run, Score
from app.sonify.program import pattern_title

_METERS = {
    "4/4": {"epb": 8, "kind": "4/4", "strong": (0, 4), "bar_beats": 4.0, "beats": 4, "beat_type": 4},
    "3/4": {"epb": 6, "kind": "3/4", "strong": (0,), "bar_beats": 3.0, "beats": 3, "beat_type": 4},
    "6/8": {"epb": 6, "kind": "6/8", "strong": (0, 3), "bar_beats": 3.0, "beats": 6, "beat_type": 8},
}
_PATTERNS = ("bach_prelude", "bach_allemande", "bach_courante")


def _region(pattern: str, length: int, meter: str, *, mode: str = "major", closing: bool = False):
    from app.sonify.guitar_frame import render_intro, render_outro

    grid = _METERS[meter]
    chord = CM if mode == "minor" else C
    total = length + 1
    melody = [67] * (total * grid["epb"])
    ctx = _Ctx(
        melody=melody,
        raw=list(melody),
        chord_at={bar: chord for bar in range(total)},
        kind_at={bar: "outro" if closing else "intro" for bar in range(total)},
        band_at={bar: "mf" for bar in range(total)},
        phrases=(),
        bars=total,
        bpm=96,
        ensemble="bach",
        mode=mode,
        character="rally",
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
    lead, support, low = render(ctx, list(range(length)), pattern=pattern)
    return ctx, lead, support, low


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
        ensemble="bach",
        divisions=4,
        beats=grid["beats"],
        beat_type=grid["beat_type"],
        bar_beats=grid["bar_beats"],
        mode=mode,
    )


def _sounding(events, bar: int) -> list[NoteEvent]:
    return [note for note in events if note.bar == bar and note.midi is not None]


def _slot(note: NoteEvent) -> int:
    """Sixteenth index inside the bar. Eighth n starts at slot 2n."""
    return int(round(note.beat * 4))


def _eighth(note: NoteEvent) -> int | None:
    """Eighth index when the attack is on the eighth grid. Sixteenths return None."""
    doubled = note.beat * 2
    nearest = round(doubled)
    if abs(doubled - nearest) > 1e-6:
        return None
    return int(nearest)


def _onsets(events, bar: int) -> set[int]:
    return {eighth for note in _sounding(events, bar) if (eighth := _eighth(note)) is not None}


def test_doors_render_short_and_long_on_every_meter() -> None:
    for pattern in _PATTERNS:
        for meter in _METERS:
            for length in (2, 4):
                for closing in (False, True):
                    _ctx, lead, support, low = _region(pattern, length, meter, closing=closing)
                    assert lead or low, (pattern, meter, length, closing)
                    assert_playable(
                        _score(lead, support, low, meter, bars=length),
                        C_KEY,
                        "study",
                    )


def test_minor_doors_do_not_write_a_major_tonic() -> None:
    for pattern in _PATTERNS:
        for meter in _METERS:
            for length in (2, 4):
                for closing in (False, True):
                    _ctx, lead, support, low = _region(
                        pattern, length, meter, mode="minor", closing=closing
                    )
                    notes = [note for note in (*lead, *support, *low) if note.midi is not None]
                    assert notes
                    assert all(note.midi % 12 != 4 for note in notes), (pattern, meter, length, closing)
                    final = [note.midi % 12 for note in (*lead, *support, *low) if note.bar == length - 1 and note.midi is not None]
                    assert 4 not in final
                    if closing:
                        assert 3 in final, (pattern, meter, length)


def _covers(note: NoteEvent, slot: int) -> bool:
    start = int(round(note.beat * 4))
    span = max(1, int(round(note.duration_beats * 4)))
    return start <= slot < start + span


def test_v7_keeps_the_leading_tone_away_from_the_bass() -> None:
    """A V7 bar may use the leading tone, but not within two semitones of the bass."""
    leading = 11
    bars_for = {
        ("bach_prelude", False, 2): (1,),
        ("bach_prelude", False, 4): (2, 3),
        ("bach_prelude", True, 2): (0,),
        ("bach_prelude", True, 4): (1,),
        ("bach_allemande", False, 2): (1,),
        ("bach_allemande", False, 4): (2, 3),
        ("bach_allemande", True, 2): (0,),
        ("bach_allemande", True, 4): (1,),
        ("bach_courante", False, 2): (1,),
        ("bach_courante", False, 4): (2, 3),
        ("bach_courante", True, 2): (0,),
        ("bach_courante", True, 4): (1, 2),
    }
    for (pattern, closing, length), bars in bars_for.items():
        for meter, grid in _METERS.items():
            for mode in ("major", "minor"):
                _ctx, lead, support, low = _region(pattern, length, meter, mode=mode, closing=closing)
                for bar in bars:
                    basses = _sounding(low, bar)
                    uppers = [*_sounding(lead, bar), *_sounding(support, bar)]
                    for slot in range(grid["epb"] * 2):
                        bass_now = [note.midi for note in basses if note.midi is not None and _covers(note, slot)]
                        upper_now = [
                            note.midi
                            for note in uppers
                            if note.midi is not None and note.midi % 12 == leading and _covers(note, slot)
                        ]
                        for bass in bass_now:
                            for upper in upper_now:
                                assert abs(upper - bass) > 2, (pattern, meter, mode, length, bar, bass, upper)


def test_courante_4_4_outro_has_no_hemiola() -> None:
    for length in (2, 4):
        _ctx, lead, support, low = _region("bach_courante", length, "4/4", closing=True)
        accented = set()
        for note in (*lead, *support, *low):
            if note.accent:
                accented.add(_eighth(note))
        assert not {0, 3, 6} <= accented


def test_courante_6_8_hemiola_leaves_eighth_five() -> None:
    for length, bar in ((2, 0), (4, 2)):
        _ctx, lead, support, low = _region("bach_courante", length, "6/8", closing=True)
        notes = [*_sounding(lead, bar), *_sounding(support, bar), *_sounding(low, bar)]
        assert 5 in {_eighth(note) for note in notes}
        bass_at_four = [note for note in _sounding(low, bar) if _eighth(note) == 4]
        assert bass_at_four
        assert abs(bass_at_four[0].duration_beats - 0.5) < 1e-6


def test_prelude_half_opens_on_bass_and_outro_grid_matches_the_half() -> None:
    for meter, grid in _METERS.items():
        half = grid["epb"] // 2
        for length in (2, 4):
            _ctx, lead, support, low = _region("bach_prelude", length, meter)
            for bar in range(length):
                for boundary in (0, half):
                    voices = {
                        "lead": _sounding(lead, bar),
                        "support": _sounding(support, bar),
                        "low": _sounding(low, bar),
                    }
                    assert any(_eighth(note) == boundary for note in voices["low"])
                    assert not any(_eighth(note) == boundary for note in voices["lead"])
                    assert not any(_eighth(note) == boundary for note in voices["support"])
        for length, bar in ((2, 0), (4, 1)):
            _ctx, lead, support, low = _region("bach_prelude", length, meter, closing=True)
            second = []
            for note in (*_sounding(lead, bar), *_sounding(support, bar), *_sounding(low, bar)):
                eighth = _eighth(note)
                if eighth is not None and eighth >= half:
                    second.append((eighth, note))
            counts: dict[int, int] = {}
            for eighth, _note in second:
                counts[eighth] = counts.get(eighth, 0) + 1
            assert set(counts) == set(range(half, grid["epb"]))
            assert all(count == 1 for count in counts.values())


def test_prelude_roll_keeps_a_third_and_the_final_block() -> None:
    """Section 2.4: the door's inner voices are a third, and the last bar stays a chord."""
    from app.sonify.guitar_frame_bach_sor import _roll_voices
    from app.sonify import guitar_frame as frame

    for meter, grid in _METERS.items():
        half = grid["epb"] // 2
        _ctx, _lead, support, low = _region("bach_prelude", 2, meter)
        for bar in range(2):
            for boundary in (0, 1):
                inners = [
                    note
                    for note in _sounding(support, bar)
                    if note.midi is not None and (0 if note.beat < half * 0.5 - 1e-9 else 1) == boundary
                ]
                pitches = {note.midi for note in inners}
                assert len(pitches) >= 2, (meter, bar, boundary, pitches)
                low_pitch, high_pitch = min(pitches), max(pitches)
                assert high_pitch - low_pitch >= 3
                low_vel = {note.velocity for note in inners if note.midi == low_pitch}
                high_vel = {note.velocity for note in inners if note.midi == high_pitch}
                assert next(iter(high_vel)) - next(iter(low_vel)) == 8
            basses = sorted(_sounding(low, bar), key=lambda note: note.beat)
            assert len(basses) >= 2
            left, right = basses[0], basses[1]
            if right.midi == left.midi:
                assert right.velocity == left.velocity
            elif right.midi > left.midi:
                assert right.velocity - left.velocity == 8
            else:
                assert left.velocity - right.velocity == 8
        _ctx, lead, support, low = _region("bach_prelude", 4, meter, closing=True)
        final = [note for note in (*lead, *support, *low) if note.bar == 3 and note.midi is not None]
        assert final
        assert all(note.duration_beats >= 1.0 - 1e-6 for note in final)
        assert not any(abs(note.duration_beats - 0.25) < 1e-6 for note in final)

    ctx, _lead, _support, _low = _region("bach_prelude", 2, "4/4")
    bass, low_mid, upper_mid, lead_pitch = _roll_voices(frame, ctx, [0])
    assert bass < low_mid < upper_mid < lead_pitch
    assert upper_mid - low_mid >= 3
    assert upper_mid != low_mid


def test_prelude_and_courante_long_intro_writes_velocity_58() -> None:
    for pattern in ("bach_prelude", "bach_courante"):
        for meter in _METERS:
            _ctx, lead, support, low = _region(pattern, 4, meter)
            last = [note for note in (*lead, *support, *low) if note.bar == 3 and note.velocity == 58]
            assert last, (pattern, meter)


def test_allemande_pickup_is_four_sixteenths_and_never_staccato() -> None:
    for meter, grid in _METERS.items():
        tail = grid["epb"] - 2
        for length in (2, 4):
            _ctx, lead, support, low = _region("bach_allemande", length, meter)
            notes = [*lead, *support, *low]
            assert all(not note.staccato for note in notes)
            pickup = [
                note
                for note in _sounding(lead, length - 1)
                if note.duration_beats <= 0.3 and _slot(note) >= tail * 2
            ]
            assert len(pickup) == 4, (meter, length, [(note.beat, note.midi) for note in pickup])
            bass_tail = [note for note in _sounding(low, length - 1) if _slot(note) >= tail * 2]
            support_tail = [note for note in _sounding(support, length - 1) if _slot(note) >= tail * 2]
            assert bass_tail == []
            assert support_tail == []
        _ctx, lead, _support, _low = _region("bach_allemande", 4, meter)
        sixteenths = [
            note for note in _sounding(lead, 2) if note.duration_beats <= 0.3
        ]
        half = grid["epb"] // 2
        assert sixteenths
        assert all(_slot(note) >= half * 2 for note in sixteenths)


def test_courante_leap_and_tirata_follow_the_meter() -> None:
    windows = {"4/4": (8, 11), "3/4": (4, 7), "6/8": (6, 9)}
    for meter, grid in _METERS.items():
        _ctx, lead, support, low = _region("bach_courante", 2, meter)
        bar0 = [*_sounding(lead, 0), *_sounding(low, 0)]
        assert any(note.accent and _eighth(note) == 0 for note in _sounding(low, 0))
        assert any(note.accent and _eighth(note) == 0 for note in _sounding(lead, 0))
        assert any(note.staccato and _eighth(note) == 1 for note in _sounding(lead, 0))
        assert not any(note.duration_beats <= 0.3 for note in [*_sounding(lead, 0), *_sounding(support, 0)])
        if meter == "6/8":
            opening = [note for note in _sounding(low, 0) if _eighth(note) == 0]
            assert opening and opening[0].duration_beats >= 1.5 - 1e-6
            assert 2 not in _onsets(low, 0)
        lo, hi = windows[meter]
        tirata = [
            note
            for note in _sounding(lead, 1)
            if note.duration_beats <= 0.3 and lo <= _slot(note) <= hi
        ]
        assert len(tirata) == 4, (meter, [(note.beat, note.duration_beats) for note in _sounding(lead, 1)])
        del bar0


def test_pattern_titles() -> None:
    assert pattern_title("bach_prelude", "bach") == "Prelude"
    assert pattern_title("bach_allemande", "bach") == "Allemande"
    assert pattern_title("bach_courante", "bach") == "Courante"


def _scale_ctx(meter: str, phrases: tuple[Phrase, ...], bars: int) -> _Ctx:
    grid = _METERS[meter]
    melody = [67] * (bars * grid["epb"])
    return _Ctx(
        melody=melody,
        raw=list(melody),
        chord_at={bar: C for bar in range(bars)},
        kind_at={bar: "phrase" for bar in range(bars)},
        band_at={bar: "mf" for bar in range(bars)},
        phrases=phrases,
        bars=bars,
        bpm=96,
        ensemble="bach",
        mode="major",
        character="rally",
        character_at=None,
        sections=(),
        rel_span=0.0,
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


def test_courante_scale_window_follows_kind_and_a_6_8_close_is_empty() -> None:
    assert "bach_courante" in _BACH_GROUP2
    assert "bach_allemande" not in _BACH_GROUP2
    assert "bach_prelude" not in _BACH_GROUP2
    assert "bach_allemande" in _HAT_PATTERNS
    assert "bach_prelude" in _BAROQUE_PATTERNS
    assert _base_window("bach_allemande") == (52, 82)
    assert _base_window("bach_prelude") == (54, 84)

    expected = {"3/4": (2, 3), "6/8": (3, 4), "4/4": (4, 5)}
    for meter, pair in expected.items():
        epb = _METERS[meter]["epb"]
        phrase = Phrase(0, epb * 2, (Run(0, epb * 2 - 4, 60), Run(epb * 2 - 4, 4, 72)))
        ctx = _scale_ctx(meter, (phrase,), 2)
        window = _courante_window(ctx, 0)
        assert window == (pair[0], pair[1])
        assert 0 not in range(window[0], window[1] + 1)
        assert 1 not in range(window[0], window[1] + 1)
        assert _courante_intrinsic_eighths(ctx, 0) == set(range(pair[0], pair[1] + 1))
        if meter == "6/8":
            assert phrase.closes
            assert _courante_intrinsic_eighths(ctx, 1) == set()
            assert [onset - epb for onset in _bass_onsets(ctx, "bach_courante", 1, epb, epb * 2)] == [0, 2, 4, 5]
        elif meter == "3/4":
            assert [onset - epb for onset in _bass_onsets(ctx, "bach_courante", 1, epb, epb * 2)] == [0, 3, 5]
        else:
            assert _bass_onsets(ctx, "bach_courante", 0, 0, epb) == [0, 2, 4, 7]
