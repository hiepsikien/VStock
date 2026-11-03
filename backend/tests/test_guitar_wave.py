"""Affine volume wave: the eight invariants in the dynamics plan, sections 2–8.

The tide adds one rounded center per bar. It does not replace the velocity
that was already written on the note.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from app.sonify.chords import C
from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _Ctx, _shape_dynamics
from app.sonify.guitar_wave import (
    BAND_LEVEL,
    PROFILES,
    SPEECH,
    affine_raw,
    alpha_price,
    alpha_volume,
    _is_target,
    _joined_floor,
    _apply_tremolo_bass_trim,
    _limit_steps,
    _make_wave,
    _place_centers,
    _phrase_breath,
    _section_anchor,
    _wave_profile,
    _written_deviations,
    WrittenDeviation,
    apply_guitar_wave,
    fit_intro,
    fit_outro,
    gain,
    intro_centers,
    lipschitz,
    outro_centers,
    profile_for,
    resolve_bar_volumes,
    round_center,
    smooth_ell,
    soft_ceiling,
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
    ("bach", "bach_prelude"),
    ("bach", "bach_allemande"),
    ("bach", "bach_courante"),
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
    ("torroba", "castillo"),
    ("torroba", "sonatina"),
    ("torroba", "fandanguillo"),
    ("torroba", "danza"),
    ("torroba", "torroba_tremolo"),
    ("torroba", "alcaniz"),
    ("torroba", "olite"),
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
    # P5: the wave shrinks W to the section, keeping it odd.
    width = min(profile.smooth, max(1, 2 * ((len(volumes) - 1) // 2) + 1))
    smoothed = smooth_ell(volumes, 0, len(volumes), width)
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
    """Invariant 1. round(C) once, then the written offset. M is 1 on all 38 rows."""
    assert set(PROFILES) == _EXPECTED
    sung_rows = {"castillo", "sonatina", "torroba_tremolo"}
    for key, profile in PROFILES.items():
        assert profile.floor_calm <= profile.floor_wide
        assert profile.ceil_calm <= profile.ceil_wide <= 63
        assert profile.smooth % 2 == 1 and profile.smooth in {3, 5, 9}
        if key[0] == "torroba":
            assert profile.d_lo == -8 and profile.d_hi == 8
            assert profile.floor_calm == profile.floor_wide
            assert profile.ceil_calm == profile.ceil_wide
            floor, ceiling = window_for(profile, 1.0)
            if key[1] in sung_rows:
                assert (floor, ceiling, profile.smooth) == (34, 58, 5)
                assert gain(floor, ceiling) == 1.0
                assert profile.snap_wide is None and profile.max_units_per_phrase == 0
            else:
                assert (floor, ceiling, profile.smooth) == (39, 63, 3)
                assert abs(gain(floor, ceiling) - 1.0) < 1e-12
                assert (profile.snap_calm, profile.snap_wide) == (70, 73)
            continue
        assert profile.d_lo == -16 and profile.d_hi == 8
        for opened in (0.0, 0.25, 0.5, 0.75, 1.0):
            floor, ceiling = window_for(profile, opened)
            assert ceiling - floor >= 27
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

    windows = {
        ("bach", "bach_sarabande"): (28, 56, 34, 62, 9),
        ("bach", "bach_gavotte"): (30, 58, 34, 62, 5),
        ("bach", "bach_bourree"): (30, 58, 36, 63, 5),
        ("bach", "bach_fuga"): (30, 58, 36, 63, 9),
        ("bach", "bach_gigue"): (30, 58, 36, 63, 3),
        ("bach", "bach_chaconne"): (28, 58, 34, 63, 9),
        ("bach", "bach_prelude"): (28, 56, 34, 62, 5),
        ("bach", "bach_allemande"): (28, 56, 34, 62, 9),
        ("bach", "bach_courante"): (30, 58, 36, 63, 3),
        ("classic", "cantabile"): (26, 54, 30, 58, 9),
        ("classic", "elegiaque"): (26, 56, 32, 62, 9),
        ("classic", "study"): (28, 56, 34, 63, 5),
        ("classic", "mozart_var"): (28, 56, 34, 62, 5),
        ("classic", "galop"): (30, 58, 36, 63, 3),
        ("barrios", "preludio"): (28, 56, 34, 62, 5),
        ("barrios", "andante"): (26, 54, 32, 60, 9),
        ("barrios", "thumb_cantabile"): (28, 56, 34, 62, 9),
        ("barrios", "tremolo"): (30, 58, 36, 63, 9),
        ("barrios", "choro"): (30, 58, 36, 63, 3),
        ("barrios", "polca"): (30, 58, 36, 63, 3),
        ("barrios", "hemiola"): (30, 58, 36, 63, 3),
        ("barrios", "vals"): (28, 58, 34, 62, 3),
        ("villa", "chord_melody"): (26, 54, 32, 60, 9),
        ("villa", "thumb_cantabile"): (30, 58, 36, 63, 9),
        ("villa", "villa_pattern"): (28, 58, 34, 63, 3),
        ("villa", "etude1"): (30, 58, 36, 63, 5),
        ("villa", "etude11"): (30, 58, 36, 63, 5),
        ("brouwer", "noviembre"): (24, 52, 30, 58, 9),
        ("brouwer", "sarabande"): (26, 56, 32, 62, 9),
        ("brouwer", "brouwer_etude"): (26, 58, 32, 63, 3),
        ("brouwer", "elogio_pizz"): (26, 56, 32, 62, 3),
        ("torroba", "castillo"): (34, 58, 34, 58, 5),
        ("torroba", "sonatina"): (34, 58, 34, 58, 5),
        ("torroba", "fandanguillo"): (40, 63, 40, 63, 3),
        ("torroba", "danza"): (40, 63, 40, 63, 3),
        ("torroba", "torroba_tremolo"): (34, 58, 34, 58, 5),
        ("torroba", "alcaniz"): (40, 63, 40, 63, 3),
        ("torroba", "olite"): (40, 63, 40, 63, 3),
    }
    assert set(windows) == set(PROFILES)
    for key, expected in windows.items():
        profile = PROFILES[key]
        assert (
            profile.floor_calm,
            profile.ceil_calm,
            profile.floor_wide,
            profile.ceil_wide,
            profile.smooth,
        ) == expected
    assert min(profile.floor_calm for profile in PROFILES.values()) == 24
    assert max(profile.ceil_calm for key, profile in PROFILES.items() if key[0] != "torroba") == 58
    assert max(profile.ceil_calm for profile in PROFILES.values()) == 63
    assert max(profile.ceil_wide for profile in PROFILES.values()) == 63
    # P0: every body row gets at least MIN_TIDE steps when the speech floor
    # leaves room. Noviembre calm is the one row that tops out at 6.
    for key, profile in PROFILES.items():
        floor, ceiling = window_for(profile, 1.0)
        assert ceiling - floor >= 6, key
        if ceiling - profile.d_hi < 6:
            continue
        if floor != SPEECH:
            assert ceiling - floor >= 8, key

    bars = 7
    # Tiny copy of (0, 0, 5, 4, 4, 4, 4). Noviembre calm stays shut (ratio under
    # 1.01), C_lo is 40, and bar 0 rounds to 40. Written 64 and 65 stay one apart.
    volumes = [math.exp(1.6 + 0.001 * value) - 1 for value in (0, 0, 5, 4, 4, 4, 4)]
    phrase = _phrase_over(bars, 4, high=60, low=60)
    ctx = _ctx(
        ensemble="brouwer",
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
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["noviembre"])
    assert _at(heard, 0, 0.0) == 38
    assert _at(heard, 0, 1.0) == 39
    assert _at(heard, 0, 2.0) - _at(heard, 0, 0.0) == 8
    assert _at(heard, 0, 0.0) - _at(heard, 0, 3.0) == 16
    center_gap = _at(heard, 4, 0.0) - _at(heard, 0, 0.0)
    # The breath clamp keeps bar 4 six steps above bar 0; 70 is six above 64 and
    # stays under the knee at this center, so the heard gap is the full 6.
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
    # The tremolo body sits `TREMOLO_BASS_TRIM` under the lead; the fill keeps
    # its written offsets, so the lead-to-thumb gap narrows by two steps.
    assert [note.velocity - ordered[0].velocity for note in first] == [-4, -1, -2, -4]

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
    # Tremolo smooths with W=9. The raw 5 sits on bar 2; smoothed ell peaks on bar 6
    # and bottoms on bar 3. 72 on that peak is the ceiling. 48 on the valley is the floor.
    lead = [
        _note(6, 0.0, 72, midi=72),
        _note(6, 1.0, 80, midi=80),
        _note(6, 2.0, 80, midi=81),
        _note(6, 3.0, 64, midi=64),
        _note(3, 0.0, 48, midi=48),
        _note(4, 0.0, 48, midi=49),
        _note(2, 0.0, 64, midi=60),
    ]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["tremolo"])
    # P2: written 72 at the peak compresses one step under the ceiling; 80
    # reaches it. The valley is the lowest heard center, not necessarily the
    # window floor (the tide and breath share the bar).
    assert [_at(heard, 6, beat) for beat in (0.0, 1.0, 2.0, 3.0)] == [62, 63, 63, 55]
    assert _at(heard, 3, 0.0) == 35
    assert _at(heard, 4, 0.0) == 38
    assert _at(heard, 2, 0.0) == 48
    # Lipschitz may lift neighbors. It does not move the center's peak onto the raw 5.
    assert _at(heard, 6, 3.0) > _at(heard, 2, 0.0)

    lifted = humanize(_guitar_score([note for note in heard if note.bar == 6 and note.velocity == 63], bars=bars), offset_at=lambda *_args: 2)
    assert lifted.lead
    assert all(note.velocity is not None and note.velocity <= 64 for note in lifted.lead)

    short_volumes = [1.0, 80.0]
    short_floor, short_ceiling, c_lo, c_hi = _window("classic", "elegiaque", short_volumes, 0.0)
    width = profile_for("classic", "elegiaque")
    assert width is not None
    short_width = min(width.smooth, max(1, 2 * ((len(short_volumes) - 1) // 2) + 1))
    smoothed = smooth_ell(short_volumes, 0, 2, short_width)
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
    heard, _support, _low = apply_guitar_wave(short, lead, [], [], ["elegiaque"])
    assert all(_at(heard, bar, 0.0) > short_floor for bar in range(2))
    assert _at(heard, 1, 1.0) == 59


def test_the_smoothed_series_holds_the_peak_and_the_barline_step() -> None:
    """Invariant 3. The shoulder, not the raw spike, is the center's peak."""
    bars = 7
    ell = (0, 0, 5, 4, 4, 4, 4)
    volumes = [math.exp(value) - 1 for value in ell]
    for bad in (0, 4, -3):
        try:
            smooth_ell(volumes, 0, bars, bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    smoothed = smooth_ell(volumes, 0, bars, 5)
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
    # Study uses W=5, so the center peaks on the shoulder (4.2), not the raw 5.
    # P4 breath is clamped to the tide bounds, so compare the tide's own centers
    # for the exact peak; the heard values still prove the step limit.
    lead = [_note(bar, beat, 64) for bar in range(bars) for beat in (0.0, 3.0)]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["study"])
    centers = [_at(heard, bar, 0.0) for bar in range(bars)]
    placed, _waves, _leading, _trailing = _place_centers(
        ctx, ["study"] * bars, resolve_bar_volumes(ctx)
    )
    wave = placed[0].wave
    assert wave is not None
    tide = [round(wave.centers[index]) for index in range(bars)]
    assert tide.index(max(tide)) == 4
    assert tide.index(max(tide)) != 2
    assert centers.index(max(centers)) != 2
    assert centers[4] >= centers[2]
    assert all(_at(heard, bar, 3.0) == centers[bar] for bar in range(bars))
    assert all(abs(centers[bar] - centers[bar - 1]) <= 4 for bar in range(1, bars))

    def peaked(ensemble: str, pattern: str) -> int:
        profile = profile_for(ensemble, pattern)
        assert profile is not None
        # P5: the wave uses min(profile.smooth, section length, odd).
        width = min(profile.smooth, max(1, 2 * ((bars - 1) // 2) + 1))
        series = smooth_ell(volumes, 0, bars, width)
        local = _ctx(
            ensemble=ensemble,
            bars=bars,
            volumes=volumes,
            phrases=(phrase,),
            sections=(FormSection(0, bars, "phrase", 0),),
            spans={0: 0.0},
        )
        heard_lead, _support_voice, _low_voice = apply_guitar_wave(
            local, [_note(bar, 0.0, 64) for bar in range(bars)], [], [], [pattern]
        )
        heard_centers = [_at(heard_lead, bar, 0.0) for bar in range(bars)]
        # P4 adds the phrase breath to the final velocity. Compare the tide's
        # own centers so this test still measures only the smoothed volume.
        placed, _waves, _leading, _trailing = _place_centers(
            local, [pattern] * bars, resolve_bar_volumes(local)
        )
        wave = placed[0].wave
        assert wave is not None
        tide_centers = [
            round(wave.centers[bar - wave.start]) for bar in range(bars)
        ]
        assert tide_centers.index(max(tide_centers)) == series.index(max(series))
        assert tide_centers.index(max(tide_centers)) != 2
        assert all(abs(tide_centers[bar] - tide_centers[bar - 1]) <= 4 for bar in range(1, bars))
        assert all(abs(heard_centers[bar] - heard_centers[bar - 1]) <= 4 for bar in range(1, bars))
        return tide_centers.index(max(tide_centers))

    # Same ell, different W: the dance looks at 3 bars and the song at 5
    # (P5 shrinks the nine-point window to the seven-bar section).
    assert peaked("bach", "bach_gigue") == 3
    assert peaked("classic", "cantabile") == 5
    assert peaked("bach", "bach_gigue") != peaked("classic", "cantabile")


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
        # P4: a flat phrase now breathes 0..+4 across its bars, so the four
        # melody attacks are no longer one number. At a high band the breath is
        # clamped to the tide ceiling, so the spread can shrink to one step.
        assert 1 <= max(melody) - min(melody) <= 4
        assert melody.index(max(melody)) in {1, 2, 3}
        # P2 compresses the last steps: 72 over 64 is 8 on the lower bands and
        # 7 when the bar's ceiling is already at the knee.
        assert _at(heard, 0, 1.0) - melody[0] in {7, 8}
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
    assert all(note.velocity is not None and note.velocity <= 79 for note in warmed.lead)

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
    # Elegiaque's calm and wide spans are both 30, so the tide stays 6. The trio
    # alpha is half, which pulls that same tide down toward the calm window.
    profile = profile_for("classic", "elegiaque")
    assert profile is not None
    calm_floor, calm_ceiling = window_for(profile, 0.0)
    trio_floor, trio_ceiling = window_for(profile, 0.5)
    wide_floor, wide_ceiling = window_for(profile, 1.0)
    assert calm_floor < trio_floor < wide_floor
    assert calm_ceiling < trio_ceiling < wide_ceiling
    assert trio_ceiling - trio_floor >= 27 and wide_ceiling - wide_floor >= 27
    assert gain(trio_floor, trio_ceiling) == 1.0
    assert trio_low < wide_low
    assert trio_high < wide_high
    # P2: the written 72 is above the knee, so its headroom over the 64 line
    # compresses; it still sits above it and never exceeds the written 8.
    assert 0 < wide_apex - wide_high <= 8
    assert 0 < trio_apex - trio_high <= 8


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
    # Andante calm: the pre-P0 body floor keeps the whole intro at the body
    # center. Written 44/50/46 land at 23/29/25 on every intro bar.
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
    assert [_at(heard, 0, beat) for beat in (0.0, 0.5, 1.0)] == [23, 29, 25]
    soft = [_at(heard, bar, 0.0) for bar in range(intro)]
    assert soft == [23] * intro
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
    assert _at(heard, intro - 1, 0.0) == _at(heard, intro, 0.0)
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
    assert two == [55, 55, 51]
    nine = outro(9)
    assert nine == [55, 55, 53, 50, 48, 46, 43, 41, 38, 36]
    assert nine[-1] != 23

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
    # The bell's L sits under the body center, so the outro can fall. The
    # written 20-step gap survives except at the very top, where P2 compresses
    # the 64 note by one; the fall never exceeds the 4-step limit.
    assert all(-20 <= quiet[index] - melody[index] <= -19 for index in range(len(melody)))
    assert all(melody[index] >= melody[index + 1] for index in range(len(melody) - 1))
    assert all(melody[index] - melody[index + 1] <= 4 for index in range(len(melody) - 1))

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


def test_the_line_fitter_still_returns_the_centers_it_was_given() -> None:
    """The whisper ramp and the decay to 23 stay when every bar already clears L."""
    whisper = intro_centers(8, 42.6)
    assert whisper[0] == 27
    assert fit_intro(whisper, [24.0] * 8) == whisper
    decay = outro_centers(9, 55)
    assert decay[-1] == 23
    assert fit_outro(decay, [22.0] * 9) == decay
    # C == L is a flat line at the body center, not the ramp from 27.
    assert fit_intro(intro_centers(6, 50.0), [50.0] * 6) == [50.0] * 6


def test_pedal_speech_uses_the_body_floor() -> None:
    """L = max(F, 22) - min(V - 64). The fitter then draws, or parks, one line."""
    # Gigue wide, six bars, written 50. F = 36, L = 50. Body center is above L.
    for body in (52.0, 53.0, 54.0, 55.0):
        line = fit_intro(intro_centers(6, body), [50.0] * 6)
        assert line[0] == 50
        assert line[-1] == body
        assert line[0] < line[-1]
        assert affine_raw(line[0], 50) == 36
        assert affine_raw(36, 50) == 22
    # Choro wide, four bars, bell 44/50/46. F = 36, L = 56. Body 52 is under L.
    parked = fit_intro(intro_centers(4, 52.0), [56.0] * 4)
    assert parked == [52.0] * 4
    assert [affine_raw(52.0, written) for written in (44, 50, 46)] == [32, 38, 34]
    assert [affine_raw(42.0, written) for written in (44, 50, 46)] == [22, 28, 24]
    # Andante calm, eight bars, body 44.6 under L = 46.
    held = fit_intro(intro_centers(8, 44.6), [46.0] * 8)
    assert held == [44.6] * 8
    assert round_center(44.6) == 45
    assert affine_raw(44.6, 44) == 25
    # Galop wide, softest note 46. F = 36, L = 54. Both centers stay under floor 36.
    assert fit_intro(intro_centers(4, 52.0), [54.0] * 4) == [52.0] * 4
    assert fit_intro(intro_centers(4, 53.0), [54.0] * 4) == [53.0] * 4
    assert affine_raw(52.0, 46) == 34
    assert affine_raw(53.0, 46) == 35
    assert 34 < 36 and 35 < 36
    # A bar of only 50s is the other galop case: L = 50, opening center 50, heard 36.
    galop_fifties = fit_intro(intro_centers(6, 53.0), [50.0] * 6)
    assert galop_fifties[0] == 50
    assert affine_raw(galop_fifties[0], 50) == 36
    # Outro uses the same L. Nine bars from 55 end at 36, not 23. Two bars end at 51.
    nine = fit_outro(outro_centers(9, 55.0), [36.0] * 9)
    assert nine[0] == 55 and nine[-1] == 36 and nine[-1] != 23
    two = fit_outro(outro_centers(2, 55.0), [36.0] * 2)
    assert two == [55.0, 51.0]

    def pedal_score(ensemble: str, pattern: str, intro: int, written: list[tuple[float, int]], *, band: str, rel: float):
        total = intro + 1
        kinds = {bar: ("intro" if bar < intro else "phrase") for bar in range(total)}
        phrase = Phrase(intro * _EPB, total * _EPB, (Run(intro * _EPB, _EPB, 64),))
        ctx = _ctx(
            ensemble=ensemble,
            bars=total,
            volumes=[4.0] * total,
            phrases=(phrase,),
            sections=(FormSection(0, intro, "intro", 0), FormSection(intro, total, "phrase", 0)),
            rel_span=rel,
            spans={intro: rel},
            kinds=kinds,
            bands={bar: band for bar in range(total)},
        )
        notes = [
            _note(bar, beat, velocity, midi=60 + index)
            for bar in range(intro)
            for index, (beat, velocity) in enumerate(written)
        ]
        notes.append(_note(intro, 0.0, written[0][1], midi=64))
        heard, _support, _low = apply_guitar_wave(ctx, notes, [], [], ["pedal"] * intro + [pattern])
        return heard

    gigue = pedal_score("bach", "bach_gigue", 6, [(0.0, 50)], band="mf", rel=0.03)
    assert [_at(gigue, bar, 0.0) for bar in range(7)] == [36, 36, 37, 37, 38, 38, 38]
    seam = [_at(gigue, bar, 0.0) for bar in range(7)]
    assert seam[5] == seam[6]
    assert all(abs(seam[bar] - seam[bar - 1]) <= 4 for bar in range(1, 7))

    choro = pedal_score("barrios", "choro", 4, [(0.0, 44), (0.5, 50), (1.0, 46)], band="p", rel=0.03)
    assert [_at(choro, 0, beat) for beat in (0.0, 0.5, 1.0)] == [28, 34, 30]
    assert [_at(choro, bar, 0.0) for bar in range(4)] == [28, 28, 28, 28]
    assert _at(choro, 3, 0.0) == _at(choro, 4, 0.0)

    galop_soft = pedal_score("classic", "galop", 4, [(0.0, 46), (1.0, 64)], band="p", rel=0.03)
    assert [_at(galop_soft, bar, 0.0) for bar in range(4)] == [30, 30, 30, 30]
    galop_mid = pedal_score("classic", "galop", 4, [(0.0, 46), (1.0, 64)], band="mp", rel=0.03)
    assert [_at(galop_mid, bar, 0.0) for bar in range(4)] == [32, 32, 32, 32]
    galop_even = pedal_score("classic", "galop", 6, [(0.0, 50)], band="mf", rel=0.03)
    assert [_at(galop_even, bar, 0.0) for bar in range(7)] == [36, 36, 37, 37, 38, 38, 38]

    # Noviembre calm, written 64: L = 24, and 27 still clears it, so the ramp stays.
    whisper = pedal_score("brouwer", "noviembre", 8, [(0.0, 64)], band="mf", rel=0.0)
    assert [_at(whisper, bar, 0.0) for bar in range(9)] == [27, 29, 31, 33, 36, 38, 40, 42, 42]
    assert _at(whisper, 7, 0.0) == _at(whisper, 8, 0.0)


def test_a_middle_pedal_takes_the_nearest_body_floor() -> None:
    """A pedal bar between phrases uses L from the nearest wave, not the bare 22."""
    kinds = {0: "phrase", 1: "cooldown", 2: "phrase"}
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    ctx = _ctx(
        ensemble="classic",
        bars=3,
        volumes=[4.0, 4.0, 4.0],
        phrases=(phrase, Phrase(2 * _EPB, 3 * _EPB, (Run(2 * _EPB, _EPB, 64),))),
        sections=(FormSection(0, 1, "phrase", 0), FormSection(2, 3, "phrase", 1)),
        rel_span=0.03,
        spans={0: 0.03, 2: 0.03},
        kinds=kinds,
    )
    heard, _support, _low = apply_guitar_wave(
        ctx,
        [_note(0, 0.0, 64), _note(1, 0.0, 64), _note(2, 0.0, 64)],
        [],
        [],
        ["galop", "pedal", "galop"],
    )
    assert _at(heard, 1, 0.0) == 36
    assert _at(heard, 1, 0.0) != 22


def test_the_raised_floor_still_prints_the_bell_at_the_trough() -> None:
    """Both calm rows now put the written 44 bell at 18 and the 48 at 22."""
    bars = 16
    volumes = [4.0] * 8 + [4.8] * 8
    phrase = _phrase_over(bars, 12, high=60, low=60)

    def trough(ensemble: str, pattern: str) -> tuple[int, int]:
        ctx = _ctx(
            ensemble=ensemble,
            bars=bars,
            volumes=volumes,
            phrases=(phrase,),
            sections=(FormSection(0, bars, "phrase", 0),),
            rel_span=0.0,
            spans={0: 0.0},
        )
        heard, _support, _low = apply_guitar_wave(
            ctx,
            [_note(0, 0.0, 44, midi=76), _note(0, 1.0, 48, midi=48), _note(0, 2.0, 64, midi=64)],
            [],
            [],
            [pattern],
        )
        return _at(heard, 0, 0.0), _at(heard, 0, 1.0)

    assert trough("brouwer", "noviembre") == (18, 22)
    assert trough("barrios", "andante") == (18, 22)
    noviembre = profile_for("brouwer", "noviembre")
    andante = profile_for("barrios", "andante")
    assert noviembre is not None and andante is not None
    floor, ceiling = window_for(noviembre, 0.0)
    gain_m, c_lo, c_hi = tide_bounds(floor, ceiling, noviembre)
    assert (floor, ceiling, gain_m, c_hi - c_lo) == (22, 52, 1.0, 6)
    assert affine_raw(c_lo, 44) == 18
    floor, ceiling = window_for(andante, 0.0)
    _gain, c_lo, c_hi = tide_bounds(floor, ceiling, andante)
    assert (floor, ceiling) == (22, 54)
    assert affine_raw(c_lo, 44) == 18

    wide = [1.0] * 8 + [80.0] * 8
    floor, ceiling, c_lo, c_hi = _window("barrios", "andante", wide, 0.03)
    assert (floor, ceiling, c_lo, c_hi) == (28, 60, 44, 52)
    ctx = _ctx(
        ensemble="barrios",
        bars=bars,
        volumes=wide,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        rel_span=0.03,
        spans={0: 0.03},
    )
    heard, _support, _low = apply_guitar_wave(
        ctx,
        [
            _note(0, 0.0, 64),
            _note(0, 1.0, 72, midi=72),
            _note(0, 2.0, 48, midi=48),
            _note(0, 3.0, 80, midi=80),
            _note(12, 0.0, 64, midi=65),
            _note(12, 1.0, 72, midi=73),
            _note(12, 2.0, 48, midi=49),
            _note(12, 3.0, 80, midi=81),
        ],
        [],
        [],
        ["andante"],
    )
    assert (_at(heard, 0, 0.0), _at(heard, 0, 1.0), _at(heard, 0, 2.0), _at(heard, 0, 3.0)) == (44, 52, 28, 59)
    assert (_at(heard, 12, 0.0), _at(heard, 12, 1.0), _at(heard, 12, 2.0), _at(heard, 12, 3.0)) == (52, 59, 36, 60)


def test_suite_snaps_follow_the_written_attack() -> None:
    """Prelude snaps the even sixteenth of each price pair. Courante snaps the staccato third."""
    from dataclasses import replace

    phrase = Phrase(0, 8, (Run(0, 4, 60), Run(4, 4, 72)))
    assert phrase.rise >= 3
    ctx = _ctx(
        ensemble="bach",
        bars=1,
        volumes=None,
        phrases=(phrase,),
        sections=(FormSection(0, 1, "phrase", 0),),
    )
    onset = phrase.apex.start

    def hit(
        pattern: str,
        beat: float,
        voice: str,
        *,
        accent: bool = False,
        staccato: bool = False,
        meter: str = "4/4",
    ) -> bool:
        local = ctx
        if meter != "4/4":
            local = replace(ctx, kind=meter, epb=6, bar_beats=3.0)
        event = _note(0, beat, 64, voice=1 if voice == "lead" else 3, accent=accent, staccato=staccato)
        return _is_target(local, pattern, event, voice, phrase, onset, 0.0)

    assert hit("bach_prelude", 0.0, "lead")
    assert hit("bach_prelude", 0.5, "lead")
    assert not hit("bach_prelude", 0.25, "lead")
    assert not hit("bach_prelude", 0.75, "lead")
    assert not hit("bach_prelude", 2.75, "lead")
    assert not hit("bach_prelude", 0.0, "low")
    assert hit("bach_prelude", 0.0, "lead", meter="3/4")
    assert hit("bach_prelude", 1.5, "lead", meter="3/4")
    assert not hit("bach_prelude", 0.75, "lead", meter="3/4")
    assert hit("bach_prelude", 1.0, "lead", meter="6/8")
    assert not hit("bach_prelude", 2.25, "lead", meter="6/8")
    assert not hit("bach_prelude", 2.75, "lead", meter="3/4")
    assert hit("bach_allemande", 1.0, "lead")
    assert not hit("bach_allemande", 1.0, "low")
    flat = Phrase(0, 8, (Run(0, 8, 64),))
    assert not _is_target(ctx, "bach_allemande", _note(0, 1.0, 64), "lead", flat, flat.apex.start, 0.0)
    assert not _is_target(ctx, "bach_prelude", _note(0, 0.0, 64), "lead", flat, flat.apex.start, 0.0)
    assert hit("bach_courante", 0.5, "lead", staccato=True)
    assert not hit("bach_courante", 0.0, "low", accent=True)
    assert _is_target(ctx, "bach_courante", _note(0, 0.5, 64, staccato=True), "lead", flat, 0.0, 0.0)
    assert not _is_target(ctx, "bach_courante", _note(0, 0.0, 64, accent=True), "lead", flat, 0.0, 0.0)
    assert not _is_target(ctx, "bach_courante", _note(0, 0.5, 64, accent=True), "lead", phrase, 0.0, 0.0)
    assert not hit("galop", 0.0, "lead")
    assert not hit("galop", 3.0, "lead")


def test_torroba_sung_and_dance_tides_keep_an_eight_degree_lead() -> None:
    """Sung tide is 42..50; the flat breath is clamped at c_hi. Dance rounds 47..55."""
    bars = 9
    ell = (0, 0, 0, 0, 6, 0, 0, 0, 0)
    volumes = [math.exp(value) - 1 for value in ell]
    phrase = Phrase(0, bars * _EPB, tuple(Run(index, 1, 64) for index in range(bars * _EPB)))
    ctx = _ctx(
        ensemble="torroba",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        rel_span=0.0,
        spans={0: 0.0},
    )
    sung = profile_for("torroba", "sonatina")
    assert sung is not None
    _gain, c_lo, c_hi = tide_bounds(*window_for(sung, 0.0), sung)
    assert (c_lo, c_hi) == (42.0, 50.0)
    lead = [_note(bar, 0.0, 64) for bar in range(bars)]
    bass = [_note(bar, 0.0, 64, midi=48, voice=3) for bar in range(bars)]
    heard_lead, _support, heard_low = apply_guitar_wave(ctx, lead, [], bass, ["sonatina"])
    assert _at(heard_lead, 0, 0.0) == 42 and _at(heard_lead, 4, 0.0) == 50
    assert _at(heard_low, 0, 0.0) == 42 and _at(heard_low, 4, 0.0) == 50

    dance = profile_for("torroba", "fandanguillo")
    assert dance is not None
    _gain, c_lo, c_hi = tide_bounds(*window_for(dance, 1.0), dance)
    assert round_center(c_lo) == 47 and round_center(c_hi) == 55
    high = [_note(bar, 0.0, 72, midi=72) for bar in range(bars)]
    heard_high, _support, _low = apply_guitar_wave(ctx, high, [], [], ["danza"])
    assert _at(heard_high, 0, 0.0) == 55 and _at(heard_high, 4, 0.0) == 62


def test_movement_zero_raises_the_sung_ceiling_to_63() -> None:
    """The first movement sings up to 63. The profile table itself stays at 58.

    Written 72 plus d_hi 8 meets that ceiling on the peak bar. floor_calm stays
    34, so the calm center still opens at 42. The tide is 13 wide, and the
    step of 4 cannot fall from the plateau to that floor in two bars, so the
    opening bar of this ell sits at 55. A later movement, and a missing index,
    keep the peak at 58 and that opening bar at 50.
    """
    for name in ("castillo", "sonatina", "torroba_tremolo"):
        profile = PROFILES[("torroba", name)]
        assert (profile.floor_calm, profile.floor_wide) == (34, 34)
        assert (profile.ceil_calm, profile.ceil_wide) == (58, 58)
        assert profile.d_lo == -8 and profile.d_hi == 8
    for name in ("fandanguillo", "danza", "alcaniz", "olite"):
        profile = PROFILES[("torroba", name)]
        assert profile.floor_calm == 40 and profile.ceil_calm == 63
        assert profile.d_lo == -8 and profile.d_hi == 8

    bars = 9
    ell = (0, 0, 0, 0, 6, 0, 0, 0, 0)
    volumes = [math.exp(value) - 1 for value in ell]
    phrase = Phrase(0, bars * _EPB, tuple(Run(index, 1, 64) for index in range(bars * _EPB)))
    ctx = _ctx(
        ensemble="torroba",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        rel_span=0.0,
        spans={0: 0.0},
    )
    classic = _wave_profile(replace(ctx, ensemble="classic", movement_index=0), "cantabile")
    assert classic is PROFILES[("classic", "cantabile")]
    for pattern in ("castillo", "sonatina", "torroba_tremolo"):
        lifted = _wave_profile(replace(ctx, movement_index=0), pattern)
        assert lifted is not None and lifted is not PROFILES[("torroba", pattern)]
        assert lifted.ceil_calm == 63 and lifted.ceil_wide == 63
        assert lifted.floor_calm == 34 and lifted.d_hi == 8
        assert PROFILES[("torroba", pattern)].ceil_calm == 58
        assert _wave_profile(ctx, pattern) is PROFILES[("torroba", pattern)]
        assert _wave_profile(replace(ctx, movement_index=1), pattern) is PROFILES[("torroba", pattern)]
        high = [_note(bar, 0.0, 72) for bar in range(bars)]
        plain, _support, _low = apply_guitar_wave(ctx, high, [], [], [pattern])
        first, _support, _low = apply_guitar_wave(replace(ctx, movement_index=0), high, [], [], [pattern])
        later, _support, _low = apply_guitar_wave(replace(ctx, movement_index=1), high, [], [], [pattern])
        assert _at(plain, 4, 0.0) == 57
        assert _at(later, 4, 0.0) == 57
        assert _at(first, 4, 0.0) == 62
        assert _at(plain, 0, 0.0) == 50
        assert _at(later, 0, 0.0) == 50
        assert _at(first, 0, 0.0) == 55
    dance = [_note(bar, 0.0, 72) for bar in range(bars)]
    plain_dance, _support, _low = apply_guitar_wave(ctx, dance, [], [], ["danza"])
    first_dance, _support, _low = apply_guitar_wave(replace(ctx, movement_index=0), dance, [], [], ["danza"])
    assert _at(plain_dance, 4, 0.0) == _at(first_dance, 4, 0.0) == 62


def test_dance_snap_reads_the_written_bell_not_the_affine_value() -> None:
    """Velocity 48 is gone after the tide. The nail still has to see the written number."""
    bars = 8
    volumes = [1.0 + 40.0 * math.exp(-((bar - 3) ** 2) / 3.0) for bar in range(bars)]
    phrase = _phrase_over(bars, 3)
    ctx = _ctx(
        ensemble="torroba",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        rel_span=0.02,
        spans={0: 0.02},
    )
    lead = [_note(bar, 1.0, 64) for bar in range(bars)]
    lead.append(_note(3, 0.0, 48, midi=67, accent=True))
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["danza"])
    bell = next(note for note in heard if note.bar == 3 and abs(note.beat) < 1e-6)
    assert bell.velocity is not None and bell.velocity <= 63


def test_soft_ceiling_is_monotone_and_keeps_three_top_steps() -> None:
    """P2: the last six written steps still produce at least three heard values."""
    values = [soft_ceiling(raw, 63) for raw in range(55, 81)]
    assert values == sorted(values)
    assert all(value <= 63 for value in values)
    assert soft_ceiling(60, 63) == 60
    assert soft_ceiling(80, 63) == 63
    assert len({soft_ceiling(raw, 63) for raw in range(61, 67)}) >= 3


def test_flat_phrase_breath_is_one_number_per_bar() -> None:
    """P4: a flat phrase opens, peaks in the middle, and eases at the close."""
    bars = 4
    phrase = Phrase(0, bars * _EPB, tuple(Run(index, 1, 64) for index in range(bars * _EPB)))
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=[4.0] * bars,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        spans={0: 0.0},
    )
    assert [
        _phrase_breath(ctx, bar, ["cantabile"] * bars, _EPB, set())
        for bar in range(bars)
    ] == [0, 2, 4, 3]


def test_phrase_breath_skips_own_contour_and_harmonic_bars() -> None:
    bars = 4
    phrase = _phrase_over(bars, 2)
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=[4.0] * bars,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        spans={0: 0.0},
    )
    assert max(
        _phrase_breath(ctx, bar, ["cantabile"] * bars, _EPB, set())
        for bar in range(bars)
    ) == 4
    assert all(
        _phrase_breath(ctx, bar, ["etude1"] * bars, _EPB, set()) == 0
        for bar in range(bars)
    )
    assert all(
        _phrase_breath(ctx, bar, ["cantabile"] * bars, _EPB, {bar}) == 0
        for bar in range(bars)
    )


def test_section_anchor_lifts_a_louder_section() -> None:
    """P3: a 4x louder section gets a positive anchor; the quiet one is lower."""
    volumes = [1.0, 1.0, 4.0, 4.0]
    quiet = _section_anchor(volumes, 0, 2)
    loud = _section_anchor(volumes, 2, 4)
    assert quiet < loud
    assert loud > 0


def test_limit_steps_caps_both_sides_of_a_seam() -> None:
    """P3 uses the largest minorant: peaks are lowered, valleys are not raised."""
    assert _limit_steps([40.0, 50.0, 40.0]) == [40.0, 44.0, 40.0]
    assert _limit_steps([40.0, 40.0, 60.0]) == [40.0, 40.0, 44.0]


def test_lipschitz_matches_the_direct_cone_envelope() -> None:
    """A band-derived input must keep the exact direct max, not a two-pass lift."""
    delta = 4.0 / 40.0
    # The second case is where a two-pass lift diverges by 1 ULP.
    for values in ((20, 24, 20, 36, 28, 24, 20), (40, 36, 20)):
        levels = [(value - 20.0) / 40.0 for value in values]
        shaped = lipschitz(levels, delta)
        expected = [
            min(
                1.0,
                max(
                    0.0,
                    max(
                        level - delta * abs(index - other)
                        for other, level in enumerate(levels)
                    ),
                ),
            )
            for index in range(len(levels))
        ]
        assert shaped == expected
        assert all(right - left <= delta + 1e-12 for left, right in zip(shaped, shaped[1:]))
        assert all(right - left >= -delta - 1e-12 for left, right in zip(shaped, shaped[1:]))


def test_written_deviations_keeps_the_profile_under_24_attacks() -> None:
    """P1's sample guard: a short fixture must not invent a narrow window."""
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    ctx = _ctx(
        ensemble="classic",
        bars=1,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(FormSection(0, 1, "phrase", 0),),
        spans={0: 0.0},
    )
    short = [_note(0, index * 0.125, 64) for index in range(23)]
    voices = {"lead": short, "support": [], "low": []}
    assert _written_deviations(ctx, voices, ["cantabile"], set()) == {}
    full = [_note(0, index * 0.125, 64) for index in range(24)]
    voices = {"lead": full, "support": [], "low": []}
    assert _written_deviations(ctx, voices, ["cantabile"], set()) == {
        "cantabile": WrittenDeviation(0, 0)
    }


def test_p1_keeps_the_profiles_upper_headroom_on_every_row() -> None:
    """The upper tail is a profile guard, not a per-piece measurement.

    A low measured 99th percentile must not lower `d_hi`. The profile's value
    is the room the loudest written note needs under the timbre ceiling; if the
    wave trims it, every common note rises and one voice can saturate before
    the others.
    """
    bars = 4
    phrase = _phrase_over(bars, bars // 2)
    for (ensemble, pattern), profile in PROFILES.items():
        ctx = _ctx(
            ensemble=ensemble,
            bars=bars,
            volumes=[4.0] * bars,
            phrases=(phrase,),
            sections=(FormSection(0, bars, "phrase", 0),),
            rel_span=0.03,
            spans={0: 0.03},
        )
        measured = WrittenDeviation(profile.d_lo, profile.d_hi - 4)
        wave = _make_wave(
            ctx,
            [4.0] * bars,
            ctx.sections[0],
            0,
            bars,
            pattern,
            profile,
            (0, 0),
            measured,
        )
        assert wave.c_hi == pytest.approx(wave.v_ceil - profile.d_hi), (ensemble, pattern)

        # The lower half of P1 must still work end-to-end. Compare the wave
        # built from a profile trimmed at `d_lo` with the one built from the
        # measured lower tail. `MAX_TIDE` and rounding affect both equally.
        trimmed = profile.d_lo + 6
        reference = _make_wave(
            ctx,
            [4.0] * bars,
            ctx.sections[0],
            0,
            bars,
            pattern,
            replace(profile, d_lo=trimmed),
            (0, 0),
            None,
        )
        got = _make_wave(
            ctx,
            [4.0] * bars,
            ctx.sections[0],
            0,
            bars,
            pattern,
            profile,
            (0, 0),
            WrittenDeviation(trimmed, profile.d_hi - 4),
        )
        assert (got.c_lo, got.c_hi) == pytest.approx((reference.c_lo, reference.c_hi))


def test_p1_clamps_a_high_lower_trim_at_the_profile_top() -> None:
    """A measured 1% above `d_hi` must not raise `c_hi` or invert the window."""
    profile = profile_for("classic", "cantabile")
    assert profile is not None
    bars = 1
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        spans={0: 0.0},
    )
    wave = _make_wave(
        ctx,
        [4.0],
        ctx.sections[0],
        0,
        bars,
        "cantabile",
        profile,
        (0, 0),
        WrittenDeviation(profile.d_hi + 2, 0),
    )
    reference = _make_wave(
        ctx,
        [4.0],
        ctx.sections[0],
        0,
        bars,
        "cantabile",
        replace(profile, d_lo=profile.d_hi),
        (0, 0),
        None,
    )
    assert (wave.c_lo, wave.c_hi) == pytest.approx((reference.c_lo, reference.c_hi))
    assert wave.c_hi <= wave.v_ceil - profile.d_hi + 1e-9


def test_barrios_tremolo_body_drops_two_after_the_wave() -> None:
    """The thumb and its colour sit two under the lead; other patterns do not."""
    bars = 1
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    ctx = _ctx(
        ensemble="barrios",
        bars=bars,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        spans={0: 0.0},
    )
    lead = [_note(0, 0.0, 60, midi=72)]
    support = [_note(0, 0.0, 60, midi=55, voice=2)]
    low = [_note(0, 0.0, 60, midi=45, voice=3), _note(0, 1.0, 60, midi=45, voice=3)]
    _apply_tremolo_bass_trim(ctx, low, support, ["tremolo"])
    assert [note.velocity for note in low] == [58, 58]
    assert support[0].velocity == 58
    assert lead[0].velocity == 60

    other = [_note(0, 0.0, 60, midi=45, voice=3)]
    _apply_tremolo_bass_trim(ctx, other, [], ["study"])
    assert other[0].velocity == 60


def test_max_tide_caps_a_trimmed_deviation() -> None:
    """P1 can free the whole window; MAX_TIDE stops it becoming a 20-step leap."""
    profile = profile_for("classic", "cantabile")
    assert profile is not None
    flat = replace(profile, d_lo=0, d_hi=0)
    _gain, c_lo, c_hi = tide_bounds(22, 63, flat)
    assert c_hi - c_lo == 16


def test_relaxed_bar_skips_the_shared_breath() -> None:
    """A boundary bar that was already thinned must not get the breath twice."""
    bars = 4
    phrase = Phrase(0, bars * _EPB, tuple(Run(index, 1, 64) for index in range(bars * _EPB)))
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=[4.0] * bars,
        phrases=(phrase,),
        sections=(FormSection(0, bars, "phrase", 0),),
        spans={0: 0.0},
    )
    lead = [_note(bar, 0.0, 64) for bar in range(bars)]
    normal, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["cantabile"])
    relaxed, _support, _low = apply_guitar_wave(
        ctx, lead, [], [], ["cantabile"], relaxed={2 * _EPB}
    )
    assert _at(relaxed, 2, 0.0) < _at(normal, 2, 0.0)


def test_soft_ceiling_keeps_exact_steps_below_the_knee() -> None:
    """The core contract: below the knee, written steps are unchanged."""
    assert soft_ceiling(55, 63) == 55
    assert soft_ceiling(58, 63) == 58
    assert soft_ceiling(60, 63) == 60
    assert soft_ceiling(58, 63) - soft_ceiling(55, 63) == 3


def test_section_anchor_uses_the_body_median() -> None:
    """P3: a long quiet frame must not make every body section look loud."""
    volumes = [1.0, 1.0, 1.0, 1.0, 4.0, 4.0, 4.0, 4.0]
    # Body-only median is 4, so the body section is exactly at the reference.
    assert _section_anchor(volumes, 4, 8, 4.0) == 0.0
    # The all-bar median is 2.5, which would invent a positive anchor.
    assert _section_anchor(volumes, 4, 8) > 0.0


def test_breath_never_lowers_an_anchored_center(monkeypatch) -> None:
    """MAX_TIDE can put c_hi below the post-anchor center; breath must only add."""
    import app.sonify.guitar_wave as gw

    wave = gw._Wave(
        start=0,
        end=1,
        pattern="cantabile",
        levels=[1.0],
        smoothed=[0.0],
        alpha_price=0.0,
        alpha_vol=0.0,
        alpha_warm=0.0,
        v_floor=30,
        v_ceil=58,
        pedal_floor=30,
        gain=1.0,
        c_lo=36.0,
        c_hi=52.0,
        centers=[54.0],
    )
    assert wave.c_hi < wave.v_ceil
    monkeypatch.setattr(gw, "_build_waves", lambda *args, **kwargs: {0: wave})
    phrase = Phrase(0, _EPB, (Run(0, 1, 72), Run(1, 7, 60)))
    ctx = _ctx(
        ensemble="classic",
        bars=1,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(FormSection(0, 1, "phrase", 0),),
        spans={0: 0.0},
    )
    placed, _waves, _leading, _trailing = _place_centers(
        ctx, ["cantabile"], [4.0], {"cantabile": (0, 0)}, set()
    )
    assert placed[0].center == 54.0
