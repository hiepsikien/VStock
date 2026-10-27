"""Affine volume wave: the eight invariants in the dynamics plan, sections 2–8.

The tide adds one rounded center per bar. It does not replace the velocity
that was already written on the note.
"""

from __future__ import annotations

import math

from app.sonify.chords import C
from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _Ctx, _shape_dynamics
from app.sonify.guitar_wave import (
    BAND_LEVEL,
    PROFILES,
    affine_raw,
    alpha_price,
    alpha_volume,
    apply_guitar_wave,
    fit_intro,
    fit_outro,
    gain,
    profile_for,
    round_center,
    smooth_ell,
    tide_bounds,
    warm_alpha,
    window_for,
)
from app.sonify.humanize import humanize
from app.sonify.model import NoteEvent, Phrase, Run, Score

_EPB = 8
_EXPECTED = {
    ("bach", "bach_sarabande"),
    ("bach", "bach_gavotte"),
    ("bach", "bach_bourree"),
    ("bach", "bach_fuga"),
    ("bach", "bach_gigue"),
    ("bach", "bach_chaconne"),
    ("classic", "cantabile"),
    ("classic", "elegiaque"),
    ("classic", "study"),
    ("classic", "mozart_var"),
    ("classic", "galop"),
    ("barrios", "preludio"),
    ("barrios", "andante"),
    ("barrios", "thumb_cantabile"),
    ("barrios", "tremolo"),
    ("barrios", "choro"),
    ("barrios", "polca"),
    ("barrios", "hemiola"),
    ("barrios", "vals"),
    ("villa", "chord_melody"),
    ("villa", "thumb_cantabile"),
    ("villa", "villa_pattern"),
    ("villa", "etude1"),
    ("villa", "etude11"),
    ("brouwer", "noviembre"),
    ("brouwer", "sarabande"),
    ("brouwer", "brouwer_etude"),
    ("brouwer", "elogio_pizz"),
}


def _phrase_over(bars: int, apex_bar: int, *, start: int = 0, high: int = 72, low: int = 60) -> Phrase:
    runs: list[Run] = []
    for bar in range(bars):
        for eighth in range(_EPB):
            midi = high if bar == apex_bar and eighth == 0 else low
            runs.append(Run((start + bar) * _EPB + eighth, 1, midi))
    return Phrase(start * _EPB, (start + bars) * _EPB, tuple(runs))


def _ctx(
    *,
    ensemble: str,
    bars: int,
    volumes: list[float] | None,
    phrases: tuple[Phrase, ...],
    sections: tuple[FormSection, ...],
    rel_span: float = 0.0,
    spans: dict | None = None,
    bands: dict[int, str] | None = None,
    kinds: dict[int, str] | None = None,
    character: str = "rally",
    patterns_hint: str | None = None,
) -> _Ctx:
    del patterns_hint
    bands = bands or {bar: "mf" for bar in range(bars)}
    kinds = kinds or {bar: "phrase" for bar in range(bars)}
    return _Ctx(
        melody=[60] * (bars * _EPB),
        raw=[60] * (bars * _EPB),
        chord_at={bar: C for bar in range(bars)},
        kind_at=kinds,
        band_at=bands,
        phrases=phrases,
        bars=bars,
        bpm=96,
        ensemble=ensemble,
        mode="major",
        character=character,
        character_at=None,
        sections=sections,
        rel_span=rel_span,
        semitones=0,
        bass_low=40,
        bass_high=55,
        mid_low=48,
        mid_high=67,
        treble_floor=60,
        treble_top=84,
        ceiling=88,
        epb=_EPB,
        kind="4/4",
        strong=(0, 2, 4, 6),
        bar_beats=4.0,
        bar_volumes=volumes,
        section_rel_spans=spans if spans is not None else {section.start: rel_span for section in sections},
    )


def _note(
    bar: int,
    beat: float,
    velocity: int,
    midi: int = 64,
    voice: int = 1,
    *,
    duration: float = 0.5,
    **flags,
) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=voice,
        velocity=velocity,
        **flags,
    )


def _at(notes: list[NoteEvent], bar: int, beat: float) -> int:
    found = [note.velocity for note in notes if note.bar == bar and abs(note.beat - beat) < 1e-6]
    assert found and found[0] is not None
    return int(found[0])


def _window(ensemble: str, pattern: str, volumes: list[float], rel_span: float, *, inward: bool = False) -> tuple[int, int, float, float]:
    profile = profile_for(ensemble, pattern)
    assert profile is not None
    smoothed = smooth_ell(volumes, 0, len(volumes))
    price = alpha_price(rel_span)
    opened = warm_alpha(price, alpha_volume(smoothed, price), inward=inward)
    floor, ceiling = window_for(profile, opened)
    _gain, c_lo, c_hi = tide_bounds(floor, ceiling, profile)
    return floor, ceiling, c_lo, c_hi


def _guitar_score(lead: list[NoteEvent], *, ensemble: str = "classic", bars: int = 1) -> Score:
    return Score(
        title="wave",
        bpm=96,
        bars=bars,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(),
        high=(),
        lead=tuple(lead),
        support=(),
        comp=(),
        low=(),
        dynamics=(),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble=ensemble,  # type: ignore[arg-type]
        bar_beats=4.0,
    )


def test_same_bar_differences_follow_one_rounded_center() -> None:
    """Invariant 1. round(C) once, then the written offset. M is 1 on all 28 rows."""
    assert set(PROFILES) == _EXPECTED
    for profile in PROFILES.values():
        assert profile.floor_calm <= profile.floor_wide
        assert profile.ceil_calm <= profile.ceil_wide <= 63
        assert profile.d_lo == -16 and profile.d_hi == 8
        for opened in (0.0, 0.5, 1.0):
            floor, ceiling = window_for(profile, opened)
            assert ceiling - floor >= 30
            assert gain(floor, ceiling) == 1.0
        if profile.snap_wide is None:
            assert profile.snap_calm is None
            assert profile.max_units_per_phrase == 0
        else:
            assert profile.snap_calm is not None
            assert 66 <= profile.snap_calm <= profile.snap_wide <= 76

    # C = 40.5. Python rounds 40.5 to 40 and 41.5 to 42, so round(C + d) would
    # turn a written step of 1 into a step of 2. Rounding C first keeps the step.
    assert round_center(40.5) == 40
    assert affine_raw(40.5, 64) == 40
    assert affine_raw(40.5, 65) == 41
    assert affine_raw(41.5, 64) == 42

    bars = 7
    # Tiny copy of (0, 0, 5, 4, 4, 4, 4). Bar 0 lands on U = 1/12, so C = 40.5
    # while the calm cantabile window stays shut (volume ratio under 1.01).
    volumes = [math.exp(1.6 + 0.001 * value) - 1 for value in (0, 0, 5, 4, 4, 4, 4)]
    phrase = _phrase_over(bars, 4, high=60, low=60)
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        rel_span=0.0,
        spans={0: 0.0},
    )
    lead = [
        _note(0, 0.0, 64, midi=64),
        _note(0, 1.0, 65, midi=65),
        _note(0, 2.0, 72, midi=72),
        _note(0, 3.0, 48, midi=48),
        _note(4, 0.0, 64, midi=64),
        _note(4, 1.0, 70, midi=70),
    ]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["cantabile"])
    assert _at(heard, 0, 0.0) == 40
    assert _at(heard, 0, 1.0) == 41
    assert _at(heard, 0, 2.0) - _at(heard, 0, 0.0) == 8
    assert _at(heard, 0, 0.0) - _at(heard, 0, 3.0) == 16
    center_gap = _at(heard, 4, 0.0) - _at(heard, 0, 0.0)
    assert _at(heard, 4, 1.0) - _at(heard, 0, 0.0) == center_gap + 6

    # Tremolo, etude, preludio, and a plain pattern keep written steps when
    # the bar is flat, so nothing is pushed into the snap layer.
    flat = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    section = FormSection(0, 1, "phrase", 0)
    tremolo = _ctx(
        ensemble="barrios",
        bars=1,
        volumes=[4.0],
        phrases=(flat,),
        sections=(section,),
        spans={0: 0.0},
    )
    thumbs = [_note(0, float(quarter), 64 + offset, midi=45, voice=3, duration=1.0) for quarter, offset in enumerate((-4, 0, 4, 1))]
    fills = [
        _note(0, quarter + finger * 0.25, 64 + offset + fill, midi=70, duration=0.25)
        for quarter, offset in enumerate((-4, 0, 4, 1))
        for finger, fill in enumerate((-6, -3, -4, -6))
    ]
    heard_lead, _support, heard_low = apply_guitar_wave(tremolo, fills, [], thumbs, ["tremolo"])
    ordered = sorted(heard_low, key=lambda note: note.beat)
    assert [ordered[index].velocity - ordered[0].velocity for index in range(4)] == [0, 4, 8, 5]
    first = sorted((note for note in heard_lead if note.beat < 1), key=lambda note: note.beat)
    assert [note.velocity - ordered[0].velocity for note in first] == [-6, -3, -4, -6]

    etude = _ctx(ensemble="villa", bars=1, volumes=[4.0], phrases=(flat,), sections=(section,), spans={0: 0.0})
    sung = [_note(0, 1.75, 60, midi=67, duration=0.5), _note(0, 2.25, 60, midi=72, duration=1.0)]
    inner = [_note(0, slot / 4, 52 + arc, midi=55, voice=2, duration=0.25) for slot, arc in ((1, -2), (6, 2), (8, 2))]
    bass = [_note(0, 0.0, 56, midi=40, voice=3, duration=4.0)]
    heard_lead, heard_support, heard_low = apply_guitar_wave(etude, sung, inner, bass, ["etude1"])
    assert _at(heard_lead, 0, 2.25) - _at(heard_lead, 0, 1.75) == 0
    assert _at(heard_support, 0, 1.5) - _at(heard_support, 0, 0.25) == 4
    assert _at(heard_low, 0, 0.0) - _at(heard_lead, 0, 1.75) == -4

    preludio = _ctx(ensemble="barrios", bars=1, volumes=[4.0], phrases=(flat,), sections=(section,), spans={0: 0.0})
    wave = [_note(0, beat, 64 if int(beat * 2) % 2 == 0 else 60, midi=72, duration=0.5) for beat in (i * 0.5 for i in range(4))]
    heard_lead, _support, _low = apply_guitar_wave(preludio, wave, [], [], ["preludio"])
    assert _at(heard_lead, 0, 0.0) - _at(heard_lead, 0, 0.5) == 4

    plain = _ctx(ensemble="classic", bars=1, volumes=[4.0], phrases=(flat,), sections=(section,), spans={0: 0.0})
    chord = [
        _note(0, 0.0, 64, midi=72),
        _note(0, 0.0, 56, midi=48, voice=3),
        _note(0, 0.0, 50, midi=55, voice=2),
    ]
    heard_lead, heard_support, heard_low = apply_guitar_wave(plain, chord[:1], chord[2:], chord[1:2], ["study"])
    assert heard_lead[0].velocity - heard_low[0].velocity == 8
    assert heard_low[0].velocity - heard_support[0].velocity == 6


def test_body_edges_use_the_genre_window() -> None:
    """Invariant 2. 72 on U=1 is the ceiling. 48 hits the floor only on a real valley."""
    bars = 7
    volumes = [math.exp(value) - 1 for value in (0, 0, 5, 4, 4, 4, 4)]
    floor, ceiling, _c_lo, c_hi = _window("barrios", "tremolo", volumes, 0.03)
    assert ceiling <= 63
    assert c_hi - (ceiling - 8) == 0
    phrase = _phrase_over(bars, 4)
    ctx = _ctx(
        ensemble="barrios",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        rel_span=0.03,
        spans={0: 0.03},
    )
    lead = [
        _note(4, 0.0, 72, midi=72),
        _note(4, 1.0, 80, midi=80),
        _note(4, 2.0, 80, midi=81),
        _note(4, 3.0, 64, midi=64),
        _note(1, 0.0, 48, midi=48),
        _note(2, 0.0, 48, midi=48),
    ]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["tremolo"])
    assert _at(heard, 4, 0.0) == ceiling
    assert _at(heard, 4, 1.0) == 63
    assert _at(heard, 4, 2.0) == 63
    assert _at(heard, 1, 0.0) == floor
    # Bar 2 is the raw spike. The smoothed peak is bar 4, so this valley was lifted.
    assert _at(heard, 2, 0.0) > floor

    lifted = humanize(_guitar_score([note for note in heard if note.bar == 4 and note.velocity == 63], bars=bars), offset_at=lambda *_args: 2)
    assert lifted.lead
    assert all(note.velocity is not None and note.velocity <= 64 for note in lifted.lead)

    short_volumes = [1.0, 80.0]
    short_floor, short_ceiling, c_lo, c_hi = _window("classic", "cantabile", short_volumes, 0.0)
    smoothed = smooth_ell(short_volumes, 0, 2)
    distance = abs(smoothed.index(max(smoothed)) - smoothed.index(min(smoothed)))
    assert distance < math.ceil((c_hi - c_lo) / 4)
    short = _ctx(
        ensemble="classic",
        bars=2,
        volumes=short_volumes,
        phrases=(_phrase_over(2, 1),),
        sections=(FormSection(0, 2, "phrase", 0),),
        spans={0: 0.0},
    )
    lead = [_note(bar, 0.0, 48, midi=48) for bar in range(2)]
    lead.append(_note(1, 1.0, 72, midi=72))
    heard, _support, _low = apply_guitar_wave(short, lead, [], [], ["cantabile"])
    assert all(_at(heard, bar, 0.0) > short_floor for bar in range(2))
    assert _at(heard, 1, 1.0) == short_ceiling


def test_the_smoothed_series_holds_the_peak_and_the_barline_step() -> None:
    """Invariant 3. The shoulder, not the raw spike, is the center's peak."""
    bars = 7
    volumes = [math.exp(value) - 1 for value in (0, 0, 5, 4, 4, 4, 4)]
    smoothed = smooth_ell(volumes, 0, bars)
    assert abs(smoothed[2] - 2.6) < 1e-9
    assert abs(smoothed[4] - 4.2) < 1e-9
    assert smoothed.index(max(smoothed)) == 4
    phrase = _phrase_over(bars, 4, high=60, low=60)
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        spans={0: 0.0},
    )
    lead = [_note(bar, beat, 64) for bar in range(bars) for beat in (0.0, 3.0)]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["cantabile"])
    centers = [_at(heard, bar, 0.0) for bar in range(bars)]
    assert centers.index(max(centers)) == 4
    assert centers[4] > centers[2]
    assert all(_at(heard, bar, 3.0) == centers[bar] for bar in range(bars))
    assert all(abs(centers[bar] - centers[bar - 1]) <= 4 for bar in range(1, bars))


def test_a_flat_section_takes_one_center_from_the_band() -> None:
    """Invariant 4. One printed band and one volume: one center, written steps kept."""
    bars = 4
    phrase = Phrase(0, bars * _EPB, tuple(Run(index, 1, 64) for index in range(bars * _EPB)))
    section = FormSection(0, bars, "phrase", 0)
    for band, level in BAND_LEVEL.items():
        ctx = _ctx(
            ensemble="classic",
            bars=bars,
            volumes=[4.0] * bars,
            phrases=(phrase,),
            sections=(section,),
            bands={bar: band for bar in range(bars)},
            spans={0: 0.0},
        )
        lead = [_note(bar, 0.0, 64) for bar in range(bars)]
        lead.append(_note(0, 1.0, 72, midi=72))
        lead.append(_note(0, 2.0, 48, midi=48))
        heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["cantabile"])
        melody = [_at(heard, bar, 0.0) for bar in range(bars)]
        assert len(set(melody)) == 1
        assert _at(heard, 0, 1.0) - melody[0] == 8
        assert melody[0] - _at(heard, 0, 2.0) == 16
        assert level == BAND_LEVEL[band]


def test_a_printed_band_does_not_move_the_center_a_second_time() -> None:
    """Invariant 5. Same U, written 64: p and f leave the filter together."""
    bars = 7
    volumes = [math.exp(1.6 + 0.001 * value) - 1 for value in (0, 0, 5, 4, 4, 4, 4)]
    phrase = _phrase_over(bars, 4, high=60, low=60)
    heard_by_band: dict[str, list[int]] = {}
    for band in ("p", "f"):
        ctx = _ctx(
            ensemble="classic",
            bars=bars,
            volumes=volumes,
            phrases=(phrase,),
            sections=(FormSection(0, bars, "phrase", 0),),
            bands={bar: band for bar in range(bars)},
            spans={0: 0.0},
        )
        heard, _support, _low = apply_guitar_wave(ctx, [_note(bar, 0.0, 64) for bar in range(bars)], [], [], ["cantabile"])
        heard_by_band[band] = [note.velocity or 0 for note in heard]
    assert heard_by_band["p"] == heard_by_band["f"]

    rising = Phrase(0, _EPB, (Run(0, 4, 60), Run(4, 4, 72)))
    for band in ("p", "f"):
        ctx = _ctx(
            ensemble="classic",
            bars=1,
            volumes=[4.0],
            phrases=(rising,),
            sections=(FormSection(0, 1, "phrase", 0),),
            bands={0: band},
            spans={0: 0.0},
        )
        shaped, _support, _low = _shape_dynamics(ctx, [_note(0, 0.0, 64), _note(0, 2.0, 30), _note(0, 3.0, 90)], [], [], set(), ["cantabile"])
        if band == "p":
            first = [note.velocity for note in shaped]
        else:
            assert [note.velocity for note in shaped] == first
    # Phrase extra is 0..+4. The old path also clamped into [44, 78] and added the band.
    written = (64, 30, 90)
    assert all(written[index] <= first[index] <= written[index] + 4 for index in range(3))
    assert first[1] < 44
    assert first[2] > 78


def _budget(profile, attacks: int, price: float, pattern: str) -> int:
    if profile.snap_wide is None:
        return 0
    if price < 0.25:
        return 1 if pattern == "elogio_pizz" else 0
    return min(profile.max_units_per_sec, max(1, int(math.floor(0.045 * attacks))))


def test_snap_is_rare_and_leaves_the_rest_of_the_bar_warm() -> None:
    """Invariant 6. Only the chosen attack leaves 63. Companions stay on the affine clamp."""
    bars = 7
    volumes = [math.exp(value) - 1 for value in (0, 0, 5, 4, 4, 4, 4)]
    phrase = _phrase_over(bars, 4)
    for ensemble, pattern in (
        ("classic", "cantabile"),
        ("barrios", "andante"),
        ("villa", "chord_melody"),
        ("brouwer", "noviembre"),
        ("bach", "bach_sarabande"),
    ):
        ctx = _ctx(
            ensemble=ensemble,
            bars=bars,
            volumes=volumes,
            phrases=(phrase,),
            sections=(FormSection(0, bars, "phrase", 0),),
            rel_span=0.03,
            spans={0: 0.03},
        )
        lead = [_note(4, 0.0, 80, midi=80), _note(4, 1.0, 72, midi=72), _note(4, 2.0, 90, midi=81)]
        heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], [pattern])
        assert all(note.velocity is not None and note.velocity <= 63 for note in heard), pattern
        warmed = humanize(_guitar_score(heard, ensemble=ensemble, bars=bars), offset_at=lambda *_args: 2)
        assert all(note.velocity is not None and note.velocity <= 64 for note in warmed.lead)

    volumes = [1.0 + 40.0 * math.exp(-((bar - 3) ** 2) / 3.0) for bar in range(8)]
    phrase = _phrase_over(8, 3)
    section = FormSection(0, 8, "phrase", 0)
    profile = profile_for("barrios", "choro")
    assert profile is not None and profile.snap_wide is not None
    ctx = _ctx(
        ensemble="barrios",
        bars=8,
        volumes=volumes,
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.02,
        spans={0: 0.02},
    )
    lead = [_note(bar, 0.0, 64) for bar in range(8)]
    lead.append(_note(3, 0.0, 70, midi=76, accent=True))
    support = [_note(3, 0.0, 80, midi=55, voice=2)]
    heard_lead, heard_support, _low = apply_guitar_wave(ctx, lead, support, [], ["choro"])
    snapped = [note for note in heard_lead if note.velocity is not None and note.velocity >= 66]
    assert snapped
    assert all(66 <= (note.velocity or 0) <= profile.snap_wide for note in snapped)
    assert len({(note.bar, round(note.beat, 2)) for note in snapped}) <= _budget(profile, len(heard_lead), alpha_price(0.02), "choro")
    assert heard_support[0].velocity is not None and heard_support[0].velocity <= 63
    warmed = humanize(_guitar_score(heard_lead, ensemble="barrios", bars=8), offset_at=lambda *_args: 2)
    assert all(note.velocity is not None and note.velocity <= 76 for note in warmed.lead)

    ctx = _ctx(
        ensemble="brouwer",
        bars=8,
        volumes=volumes,
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.0,
        spans={0: 0.0},
        character="volatile",
    )
    lead = [_note(3, 1.5, 76, midi=76, duration=0.25, accent=True, staccato=True)]
    low = [_note(3, 1.5, 52, midi=48, voice=3, duration=0.25, accent=True, staccato=True)]
    support = [_note(3, 1.5, 55, midi=55, voice=2, duration=0.25, accent=True, staccato=True)]
    heard_lead, heard_support, heard_low = apply_guitar_wave(ctx, lead, support, low, ["elogio_pizz"])
    nails = [note for note in (*heard_lead, *heard_support, *heard_low) if note.velocity is not None and note.velocity >= 66]
    assert len(nails) == 1 and nails[0].velocity == 72
    assert all(note.velocity is not None and note.velocity <= 63 for note in (*heard_support, *heard_low))

    ctx = _ctx(
        ensemble="villa",
        bars=8,
        volumes=volumes,
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.02,
        spans={0: 0.02},
    )
    tresillo = [_note(3, eighth / 2, 64, accent=True) for eighth in (0, 3, 6)]
    tresillo.append(_note(3, 1.0, 60, midi=60))
    heard, _support, _low = apply_guitar_wave(ctx, tresillo, [], [], ["villa_pattern"])
    snapped = [note for note in heard if note.velocity is not None and note.velocity >= 66]
    assert {round(note.beat, 2) for note in snapped} == {0.0, 1.5, 3.0}
    assert len({note.bar for note in snapped}) == 1
    assert _at(heard, 3, 1.0) <= 63

    sung = [_note(3, 1.75, 67, midi=67, duration=0.5), _note(3, 2.25, 72, midi=74, duration=1.0)]
    heard, heard_support, _low = apply_guitar_wave(
        ctx,
        sung,
        [_note(3, 0.5, 55, midi=55, voice=2)],
        [],
        ["etude1"],
    )
    nails = [note for note in heard if note.velocity is not None and note.velocity >= 66]
    assert len(nails) == 1 and abs(nails[0].beat - 2.25) < 1e-6
    assert _at(heard, 3, 1.75) <= 63
    assert heard_support[0].velocity is not None and heard_support[0].velocity <= 63


def test_each_section_keeps_its_own_window() -> None:
    """Invariant 7. A calm section does not snap. A trio runs a narrower tide. M stays 1."""
    left = [1.0 + 30.0 * math.exp(-((bar - 2) ** 2) / 2.0) for bar in range(4)]
    right = [1.0 + 30.0 * math.exp(-((bar - 2) ** 2) / 2.0) for bar in range(4)]
    phrases = (_phrase_over(4, 2, start=0), _phrase_over(4, 2, start=4))
    sections = (FormSection(0, 4, "phrase", 0), FormSection(4, 8, "phrase", 1))
    ctx = _ctx(
        ensemble="barrios",
        bars=8,
        volumes=left + right,
        phrases=phrases,
        sections=sections,
        spans={0: 0.0, 4: 0.03},
    )
    lead = [_note(bar, 0.0, 70, midi=70, accent=True) for bar in range(8)]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["choro", "choro"])
    assert not any(note.bar < 4 and note.velocity is not None and note.velocity >= 66 for note in heard)
    assert any(note.bar >= 4 and note.velocity is not None and note.velocity >= 66 for note in heard)

    ctx = _ctx(
        ensemble="brouwer",
        bars=4,
        volumes=left,
        phrases=(_phrase_over(4, 2),),
        sections=(FormSection(0, 4, "phrase", 0),),
        spans={0: 0.0},
        character="volatile",
    )
    # The raw spike is bar 2; reflection puts the smoothed peak on bar 3, where S clears 0.70.
    slap = [_note(3, 1.5, 76, midi=76, duration=0.25, accent=True, staccato=True)]
    heard, support, low = apply_guitar_wave(
        ctx,
        slap,
        [_note(3, 1.5, 55, midi=55, voice=2, duration=0.25, accent=True, staccato=True)],
        [_note(3, 1.5, 52, midi=48, voice=3, duration=0.25, accent=True, staccato=True)],
        ["elogio_pizz"],
    )
    nails = [note for note in (*heard, *support, *low) if note.velocity is not None and note.velocity >= 66]
    assert len(nails) == 1

    def tide(trio: bool) -> tuple[int, int, int]:
        bars = 12
        volumes = [1.0 + 50.0 * math.exp(-((bar - 6) ** 2) / 4.0) for bar in range(bars)]
        ctx = _ctx(
            ensemble="classic",
            bars=bars,
            volumes=volumes,
            phrases=(_phrase_over(bars, 6),),
            sections=(FormSection(0, bars, "phrase", 0, trio=trio),),
            rel_span=0.03,
            spans={0: 0.03},
        )
        lead = [_note(bar, 0.0, 64) for bar in range(bars)]
        lead.append(_note(6, 1.0, 72, midi=72))
        heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["elegiaque"])
        levels = [_at(heard, bar, 0.0) for bar in range(bars)]
        return min(levels), max(levels), _at(heard, 6, 1.0)

    wide_low, wide_high, wide_apex = tide(False)
    trio_low, trio_high, trio_apex = tide(True)
    assert trio_high - trio_low < wide_high - wide_low
    assert trio_high < wide_high
    assert wide_apex - wide_high == 8
    assert trio_apex - trio_high == 8


def test_a_body_below_the_speech_line_holds_the_pedal_at_the_seam() -> None:
    """A bell needs center 42. Body 40 cannot host that line, so the pedal stays at 40."""
    intro = [27 + (40 - 27) * index / 7 for index in range(8)]
    assert fit_intro(intro, [42.0] * 8) == [40.0] * 8
    assert [round(40) + (written - 64) for written in (44, 50, 46)] == [20, 26, 22]

    outro = [max(23.0, 40 - 4 * index) for index in range(6)]
    assert fit_outro(outro, [42.0] * 6) == [40.0] * 6
    assert round(40) + (44 - 64) == 20

    loud = [27 + (44 - 27) * index / 7 for index in range(8)]
    spread = fit_intro(loud, [42.0] * 8)
    assert spread[0] == 42 and spread[-1] == 44 and spread[0] < spread[-1]

    decay = [max(23.0, 55 - 4 * index) for index in range(9)]
    assert fit_outro(decay, [22.0] * 9) == decay


def test_intro_and_outro_shift_the_written_gesture() -> None:
    """Invariant 8. Pedal bars keep the written shape, join the body, and stab after the clamp."""
    # The bell needs center 42 to be stored at 22. A per-bar lift would pin the
    # first six bars to one chord. The ramp spreads instead, and the seam stays.
    intro = 8
    total = intro + 1
    kinds = {bar: ("intro" if bar < intro else "phrase") for bar in range(total)}
    sections = (FormSection(0, intro, "intro", 0), FormSection(intro, total, "phrase", 0))
    phrase = Phrase(intro * _EPB, total * _EPB, (Run(intro * _EPB, _EPB, 64),))
    ctx = _ctx(
        ensemble="barrios",
        bars=total,
        volumes=[4.0] * total,
        phrases=(phrase,),
        sections=sections,
        spans={intro: 0.0},
        kinds=kinds,
    )
    bell = [
        _note(bar, index * 0.5, velocity, midi=76 + index)
        for bar in range(intro)
        for index, velocity in enumerate((44, 50, 46))
    ]
    seam = [_note(intro - 1, 3.0, 64, midi=64), _note(intro, 0.0, 64)]
    heard, _support, _low = apply_guitar_wave(ctx, bell + seam, [], [], ["pedal"] * intro + ["andante"])
    assert [_at(heard, 0, beat) for beat in (0.0, 0.5, 1.0)] == [22, 28, 24]
    soft = [_at(heard, bar, 0.0) for bar in range(intro)]
    assert len(set(soft)) > 1
    assert soft[-1] > soft[0]
    assert all(level >= 22 for level in soft)
    assert all(abs(soft[bar] - soft[bar - 1]) <= 4 for bar in range(1, intro))
    assert _at(heard, intro - 1, 0.5) - soft[-1] == 6
    assert _at(heard, intro - 1, 1.0) - soft[-1] == 2
    assert _at(heard, intro - 1, 3.0) == _at(heard, intro, 0.0)
    assert _at(heard, intro, 0.0) != 27

    kinds = {0: "intro", 1: "phrase"}
    ctx = _ctx(
        ensemble="classic",
        bars=2,
        volumes=[4.0, 4.0],
        phrases=(Phrase(_EPB, 2 * _EPB, (Run(_EPB, _EPB, 64),)),),
        sections=(FormSection(0, 1, "intro", 0), FormSection(1, 2, "phrase", 0)),
        spans={1: 0.0},
        kinds=kinds,
    )
    heard, _support, _low = apply_guitar_wave(ctx, [_note(0, 0.0, 64), _note(1, 0.0, 64)], [], [], ["pedal", "cantabile"])
    assert _at(heard, 0, 0.0) == _at(heard, 1, 0.0)
    assert _at(heard, 0, 0.0) != 27

    body_bars = 7
    intro = 2
    total = intro + body_bars
    ell = (6, 4, 2, 1, 0, 0, 0)
    volumes = [1.0] * intro + [math.exp(value) - 1 for value in ell]
    kinds = {bar: ("intro" if bar < intro else "phrase") for bar in range(total)}
    phrase = Phrase(
        intro * _EPB,
        total * _EPB,
        tuple(Run(intro * _EPB + index, 1, 72 if index == 0 else 60) for index in range(body_bars * _EPB)),
    )
    ctx = _ctx(
        ensemble="barrios",
        bars=total,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, intro, "intro", 0), FormSection(intro, total, "phrase", 0)),
        rel_span=0.03,
        spans={intro: 0.03},
        kinds=kinds,
    )
    heard, _support, _low = apply_guitar_wave(
        ctx,
        [_note(bar, 0.0, 64) for bar in range(total)],
        [],
        [],
        ["pedal"] * intro + ["tremolo"] * body_bars,
    )
    assert _at(heard, intro - 1, 0.0) == _at(heard, intro, 0.0) == 55
    assert abs(_at(heard, 0, 0.0) - _at(heard, 1, 0.0)) <= 4

    def outro(count: int) -> list[int]:
        total = body_bars + count
        volumes = [math.exp(value) - 1 for value in (0, 0, 0, 1, 2, 4, 6)] + [1.0] * count
        kinds = {bar: ("phrase" if bar < body_bars else "outro") for bar in range(total)}
        phrase = Phrase(
            0,
            body_bars * _EPB,
            tuple(Run(index, 1, 72 if index == (body_bars - 1) * _EPB else 60) for index in range(body_bars * _EPB)),
        )
        ctx = _ctx(
            ensemble="barrios",
            bars=total,
            volumes=volumes,
            phrases=(phrase,),
            sections=(FormSection(0, body_bars, "phrase", 0), FormSection(body_bars, total, "outro", 0)),
            rel_span=0.03,
            spans={0: 0.03},
            kinds=kinds,
        )
        heard, _support, _low = apply_guitar_wave(
            ctx,
            [_note(bar, 0.0, 64) for bar in range(total)],
            [],
            [],
            ["tremolo"] * body_bars + ["pedal"] * count,
        )
        return [_at(heard, bar, 0.0) for bar in range(body_bars - 1, total)]

    two = outro(2)
    assert two[0] == 55
    assert two[-1] == 51
    nine = outro(9)
    assert nine[0] == 55
    assert nine[-1] == 23

    total = body_bars + 9
    volumes = [math.exp(value) - 1 for value in (0, 0, 0, 1, 2, 4, 6)] + [1.0] * 9
    kinds = {bar: ("phrase" if bar < body_bars else "outro") for bar in range(total)}
    phrase = Phrase(
        0,
        body_bars * _EPB,
        tuple(Run(index, 1, 72 if index == (body_bars - 1) * _EPB else 60) for index in range(body_bars * _EPB)),
    )
    ctx = _ctx(
        ensemble="barrios",
        bars=total,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, body_bars, "phrase", 0), FormSection(body_bars, total, "outro", 0)),
        rel_span=0.03,
        spans={0: 0.03},
        kinds=kinds,
    )
    notes = [_note(bar, 0.0, 64) for bar in range(body_bars)]
    for bar in range(body_bars, total):
        notes.append(_note(bar, 0.0, 64, midi=64))
        notes.append(_note(bar, 1.0, 44, midi=57))
    heard, _support, _low = apply_guitar_wave(ctx, notes, [], [], ["tremolo"] * body_bars + ["pedal"] * 9)
    melody = [_at(heard, bar, 0.0) for bar in range(body_bars, total)]
    quiet = [_at(heard, bar, 1.0) for bar in range(body_bars, total)]
    assert melody[0] == 55
    assert melody[-1] > 23
    assert quiet[-1] >= 22
    assert melody[-1] < melody[0]
    assert len(set(melody)) > 1
    assert all(abs(melody[index] - melody[index + 1]) <= 4 for index in range(len(melody) - 1))
    assert all(quiet[index] - melody[index] == -20 for index in range(len(melody)))

    ctx = _ctx(
        ensemble="brouwer",
        bars=1,
        volumes=[4.0],
        phrases=(Phrase(0, _EPB, (Run(0, _EPB, 60),)),),
        sections=(FormSection(0, 1, "outro", 0),),
        kinds={0: "outro"},
        character="volatile",
    )
    heard_lead, heard_support, heard_low = apply_guitar_wave(
        ctx,
        [_note(0, 0.0, 50, accent=True, staccato=True)],
        [_note(0, 0.0, 50, midi=55, voice=2, accent=True, staccato=True)],
        [_note(0, 0.0, 50, midi=40, voice=3, accent=True, staccato=True)],
        ["pedal"],
    )
    assert (heard_lead[0].velocity, heard_low[0].velocity, heard_support[0].velocity) == (70, 66, 62)

    ctx = _ctx(
        ensemble="classic",
        bars=1,
        volumes=[4.0],
        phrases=(Phrase(0, _EPB, (Run(0, _EPB, 64),)),),
        sections=(FormSection(0, 1, "phrase", 0),),
        spans={0: 0.0},
    )
    heard, _support, _low = apply_guitar_wave(
        ctx,
        [
            _note(0, 0.0, 64, duration=1.0, tie_start=True),
            _note(0, 1.0, 12, duration=1.0, tie_stop=True),
        ],
        [],
        [],
        ["cantabile"],
    )
    assert heard[0].velocity == heard[1].velocity
    assert heard[0].velocity != 12
