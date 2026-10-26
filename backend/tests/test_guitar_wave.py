"""Volume-wave rebase for the nylon guitar.

The locked checks are the seven criteria in
docs/sonify-guitar-dynamics-wave-plan.md, plus the intro examples: a Barrios
cadence with crest 0, the bell 44/50/46, the Villa 64→50 seam of 4, the
pre-join envelope for V_open 26 and 63, and the bass that would land on 18.
"""

from __future__ import annotations

import math

from app.sonify.chords import C
from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _Ctx
from app.sonify.guitar_wave import (
    PROFILES,
    alpha_price,
    alpha_volume,
    apply_guitar_wave,
    bar_edges,
    etude11_middle_velocity,
    morendo_peak,
    phrase_delta,
    prejoin_envelope,
    profile_for,
    range_lock,
    resolve_bar_volumes,
    shape_join_velocity,
    shape_prejoin_velocity,
    smooth_log,
    u_vol,
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


def test_profile_table_has_the_twenty_eight_locked_rows() -> None:
    assert set(PROFILES) == _EXPECTED
    assert ("barrios", "pedal") not in PROFILES
    assert ("villa", "pedal") not in PROFILES
    for key, profile in PROFILES.items():
        assert profile.floor_calm <= profile.floor_wide
        assert profile.ceil_calm <= profile.ceil_wide <= 63
        assert profile.floor_calm >= 20
        assert profile.sup_floor >= 18
        if profile.snap_wide is None:
            assert profile.snap_calm is None
            assert profile.max_units_per_phrase == 0
            assert profile.max_units_per_sec == 0
        else:
            assert profile.snap_calm is not None
            assert 66 <= profile.snap_calm <= profile.snap_wide <= 76
            assert profile.max_units_per_phrase == 1
    barrios = profile_for("barrios", "thumb_cantabile")
    villa = profile_for("villa", "thumb_cantabile")
    assert barrios is not None and villa is not None
    assert (barrios.floor_wide, barrios.ceil_wide, barrios.snap_wide) == (30, 62, 68)
    assert (villa.floor_wide, villa.ceil_wide, villa.snap_wide) == (32, 63, 70)
    assert barrios.bass_ceil == 44 and villa.bass_ceil == 46


def _phrase_over(bars: int, apex_bar: int, *, rise: bool = True) -> Phrase:
    runs: list[Run] = []
    for bar in range(bars):
        for eighth in range(_EPB):
            midi = 72 if rise and bar == apex_bar and eighth == 0 else 60
            runs.append(Run(bar * _EPB + eighth, 1, midi))
    return Phrase(0, bars * _EPB, tuple(runs))


def _ctx(
    *,
    ensemble: str,
    bars: int,
    volumes: list[float] | None,
    phrases: tuple[Phrase, ...],
    sections: tuple[FormSection, ...],
    rel_span: float = 0.02,
    spans: dict | None = None,
    bands: dict[int, str] | None = None,
    kinds: dict[int, str] | None = None,
    character: str = "rally",
) -> _Ctx:
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
    midi: int,
    voice: int,
    velocity: int = 40,
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


def _lead_line(bars: int) -> list[NoteEvent]:
    return [_note(bar, eighth / 2, 60, 1) for bar in range(bars) for eighth in range(_EPB)]


def _levels(volumes: list[float]) -> list[float]:
    return range_lock(smooth_log(volumes, 0, len(volumes)), ["mf"] * len(volumes))


def test_range_lock_is_flat_on_extrema_and_continuous_across_barlines() -> None:
    volumes = [1.0 + 30.0 * math.exp(-((bar - 6) ** 2) / 4.0) for bar in range(12)]
    levels = _levels(volumes)
    assert 0.0 in levels and 1.0 in levels
    edges = bar_edges(levels)
    for index, level in enumerate(levels):
        if level not in (0.0, 1.0):
            continue
        for step in range(_EPB):
            assert u_vol(edges[index][0], edges[index][1], _EPB, step) == level
    for index in range(len(levels) - 1):
        left, right = levels[index], levels[index + 1]
        if left in (0.0, 1.0) and right in (0.0, 1.0) and left != right:
            continue
        leaving = u_vol(edges[index][0], edges[index][1], _EPB, _EPB - 1)
        arriving = u_vol(edges[index + 1][0], edges[index + 1][1], _EPB, 0)
        assert abs(leaving - arriving) < 1e-9
    # Entering a peak: the last eighth of the previous ordinary bar is 1.
    peak = levels.index(1.0)
    if peak > 0 and levels[peak - 1] not in (0.0, 1.0):
        arriving = u_vol(edges[peak - 1][0], edges[peak - 1][1], _EPB, _EPB - 1)
        assert arriving == 1.0
        leaving = u_vol(edges[peak][0], edges[peak][1], _EPB, 0)
        assert leaving == 1.0


def test_peak_bars_touch_the_ceiling_and_a_quiet_phrase_cannot_pass_them() -> None:
    bars = 12
    volumes = [1.0 + 30.0 * math.exp(-((bar - 6) ** 2) / 4.0) for bar in range(bars)]
    levels = _levels(volumes)
    peak = levels.index(1.0)
    phrase = _phrase_over(bars, peak)
    section = FormSection(0, bars, "phrase", 0)
    ctx = _ctx(
        ensemble="classic",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.0,
        spans={0: 0.0},
    )
    lead, _support, _low = apply_guitar_wave(ctx, _lead_line(bars), [], [], ["cantabile"])
    smoothed = smooth_log(volumes, 0, bars)
    opened = warm_alpha(alpha_price(0.0), alpha_volume(smoothed, alpha_price(0.0)), inward=False)
    profile = profile_for("classic", "cantabile")
    assert profile is not None
    floor, ceiling = window_for(profile, opened)
    edges = bar_edges(levels)
    heard = {(note.bar, round(note.beat * 2)): note.velocity for note in lead}
    for step in range(_EPB):
        assert heard[(peak, step)] == ceiling
    troughs = [index for index, level in enumerate(levels) if level == 0.0]
    assert troughs
    for bar in troughs:
        for step in range(_EPB):
            assert heard[(bar, step)] == floor
    for bar in range(bars):
        for step in range(_EPB):
            level = u_vol(edges[bar][0], edges[bar][1], _EPB, step)
            assert level < 1.0 or heard[(bar, step)] == ceiling
            assert heard[(bar, step)] is not None and heard[(bar, step)] <= ceiling
            onset = bar * _EPB + step
            assert phrase_delta(phrase, onset, level) <= 0.0
    # A note on a lower volume eighth stays within 3 of a louder one, plus the
    # one unit round() can add when both envelopes sit on a .5 boundary.
    pairs = [
        (bar, step, u_vol(edges[bar][0], edges[bar][1], _EPB, step))
        for bar in range(bars)
        for step in range(_EPB)
    ]
    for left, right in zip(pairs, pairs[1:]):
        if left[2] <= right[2]:
            quieter, louder = left, right
        else:
            quieter, louder = right, left
        assert (heard[(quieter[0], quieter[1])] or 0) <= (heard[(louder[0], louder[1])] or 0) + 4


def test_a_calm_price_keeps_the_snap_gate_shut_except_one_slap() -> None:
    bars = 8
    volumes = [1.0 + (20.0 if bar == 4 else 0.0) for bar in range(bars)]
    levels = _levels(volumes)
    peak = levels.index(1.0)
    phrase = _phrase_over(bars, peak)
    section = FormSection(0, bars, "phrase", 0)

    def run(ensemble: str, pattern: str) -> list[NoteEvent]:
        ctx = _ctx(
            ensemble=ensemble,
            bars=bars,
            volumes=volumes,
            phrases=(phrase,),
            sections=(section,),
            rel_span=0.0,
            spans={0: 0.0},
            character="volatile",
        )
        lead = [_note(peak, 1.5, 76, 1, accent=True, staccato=True, duration=0.5)]
        lead += [_note(bar, 0.0, 64, 1) for bar in range(bars) if bar != peak]
        low = [_note(peak, 1.5, 48, 3, accent=True, staccato=True, duration=0.5)]
        support = [_note(peak, 1.5, 55, 2, accent=True, staccato=True, duration=0.5)]
        heard, _inner, _bass = apply_guitar_wave(ctx, lead, support, low, [pattern])
        return heard

    for ensemble, pattern in (
        ("classic", "cantabile"),
        ("barrios", "andante"),
        ("villa", "chord_melody"),
        ("brouwer", "noviembre"),
        ("bach", "bach_sarabande"),
        ("barrios", "choro"),
    ):
        heard = run(ensemble, pattern)
        assert all(note.velocity is not None and note.velocity <= 63 for note in heard), pattern
    slap = run("brouwer", "elogio_pizz")
    snapped = [note for note in slap if note.velocity is not None and note.velocity >= 66]
    assert len(snapped) == 1
    assert snapped[0].velocity == 72
    assert all(note.velocity is not None and note.velocity <= 72 for note in slap)


def _target_notes(pattern: str, peak: int) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    if pattern == "thumb_cantabile":
        low.append(_note(peak, 0.0, 48, 3, duration=1.0))
        lead.append(_note(peak, 0.0, 64, 1, duration=1.0))
        support.append(_note(peak, 0.0, 55, 2, duration=1.0))
    elif pattern == "tremolo":
        for quarter, offset in enumerate((-4, 0, 4, 1)):
            low.append(_note(peak, float(quarter), 45, 3, duration=1.0))
            for finger in range(4):
                lead.append(_note(peak, quarter + finger * 0.25, 64, 1, duration=0.25))
            if quarter == 0:
                support.append(_note(peak, 0.0, 50, 2, duration=1.0))
        del offset
    elif pattern == "etude1":
        lead.append(_note(peak, 1.75, 67, 1, duration=0.5))
        lead.append(_note(peak, 2.25, 72, 1, duration=1.75))
        for slot, _arc in (
            (1, -2),
            (2, -2),
            (3, -2),
            (4, 0),
            (5, 0),
            (6, 2),
            (8, 2),
            (10, 2),
            (11, 0),
            (12, 0),
            (13, -2),
            (14, -2),
            (15, -2),
        ):
            support.append(_note(peak, slot / 4, 55, 2, duration=0.25))
        low.append(_note(peak, 0.0, 40, 3, duration=4.0))
    elif pattern == "etude11":
        lead.append(_note(peak, 0.0, 64, 1, duration=0.5, accent=True))
        lead.append(_note(peak, 0.5, 64, 1, duration=0.5))
        low.append(_note(peak, 0.0, 45, 3, duration=1.0, accent=True))
        for slot in (1, 2, 4, 5):
            support.append(_note(peak, slot / 6, 57, 2, duration=1 / 6))
    elif pattern == "vals":
        lead.append(_note(peak, 2.0, 70, 1, duration=0.5, accent=True))
    elif pattern == "preludio":
        lead.append(_note(peak, 0.0, 72, 1, duration=1.5))
        lead.append(_note(peak, 1.5, 70, 1, duration=0.5))
    elif pattern == "elogio_pizz":
        lead.append(_note(peak, 1.5, 76, 1, duration=0.25, accent=True, staccato=True))
        low.append(_note(peak, 1.5, 52, 3, duration=0.25, accent=True, staccato=True))
        support.append(_note(peak, 1.5, 55, 2, duration=0.25, accent=True, staccato=True))
        lead.append(_note(peak, 0.0, 64, 1, duration=0.5))
    elif pattern == "villa_pattern":
        for eighth in (0, 3, 6):
            lead.append(_note(peak, eighth / 2, 64, 1, duration=0.5, accent=True))
    else:
        flags = {"accent": True}
        if pattern == "bach_gavotte":
            flags = {}
        lead.append(_note(peak, 0.0, 67, 1, duration=0.5, **flags))
        low.append(_note(peak, 0.0, 48, 3, duration=1.0))
        support.append(_note(peak, 0.0, 55, 2, duration=1.0))
    return lead, support, low


def _phrase_for(pattern: str, bars: int, peak: int) -> Phrase:
    if pattern == "bach_gavotte":
        runs = [Run(0, 1, 60)]
        runs.append(Run(1, bars * _EPB - 1, 72))
        return Phrase(peak * _EPB, (peak + bars) * _EPB, tuple(runs))
    return _phrase_over(bars, peak)


def test_a_wide_price_snaps_only_the_patterns_that_ask_for_a_nail() -> None:
    bars = 8
    volumes = [1.0 + 40.0 * math.exp(-((bar - 3) ** 2) / 3.0) for bar in range(bars)]
    levels = _levels(volumes)
    peak = levels.index(1.0)
    section = FormSection(0, bars, "phrase", 0)
    for (ensemble, pattern), profile in PROFILES.items():
        phrase = _phrase_for(pattern, bars, peak if pattern != "bach_gavotte" else 0)
        if pattern == "bach_gavotte":
            gavotte_volumes = [40.0] + [1.0] * (bars - 1)
            gavotte_peak = _levels(gavotte_volumes).index(1.0)
            volumes_for = gavotte_volumes
            phrase = _phrase_for(pattern, bars, gavotte_peak)
            target_bar = gavotte_peak
        else:
            volumes_for = volumes
            target_bar = peak
        ctx = _ctx(
            ensemble=ensemble,
            bars=bars,
            volumes=volumes_for,
            phrases=(phrase,),
            sections=(section,),
            rel_span=0.02,
            spans={0: 0.02},
            character="rally",
        )
        lead, support, low = _target_notes(pattern, target_bar)
        # Keep the singing voice populated so the section budget is at least 1.
        if pattern not in {"tremolo", "etude1", "etude11", "thumb_cantabile"}:
            lead += [_note(bar, 0.0, 64, 1) for bar in range(bars) if bar != target_bar]
        heard_lead, heard_support, heard_low = apply_guitar_wave(ctx, lead, support, low, [pattern])
        singing = heard_low if pattern in {"thumb_cantabile", "tremolo"} else heard_lead
        snapped = [note for note in singing if note.velocity is not None and note.velocity >= 66]
        if profile.snap_wide is None:
            assert not snapped, pattern
            assert all(note.velocity is not None and note.velocity <= 63 for note in (*heard_lead, *heard_support, *heard_low))
            continue
        units = {(note.bar, round(note.beat, 2)) for note in snapped}
        if pattern == "villa_pattern":
            units = {note.bar for note in snapped}
        if pattern == "tremolo":
            units = {note.bar for note in snapped if note.duration_beats >= 0.75}
        assert units, pattern
        assert len(units) <= profile.max_units_per_sec
        ceiling = profile.snap_wide
        assert all(66 <= (note.velocity or 0) <= ceiling for note in snapped), pattern


def test_tremolo_etude_and_preludio_keep_their_inner_steps_when_warm() -> None:
    assert [etude11_middle_velocity(60, slot, "mf") for slot in (1, 2, 4, 5)] == [49, 50, 51, 51]
    bars = 1
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    section = FormSection(0, 1, "phrase", 0)
    ctx = _ctx(
        ensemble="barrios",
        bars=bars,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.0,
        spans={0: 0.0},
    )
    lead, support, low = _target_notes("tremolo", 0)
    heard_lead, heard_support, heard_low = apply_guitar_wave(ctx, lead, support, low, ["tremolo"])
    thumbs = [note.velocity for note in sorted(heard_low, key=lambda note: note.beat)]
    assert thumbs[1] - thumbs[0] == 4
    assert thumbs[2] - thumbs[1] == 4
    assert thumbs[3] - thumbs[2] == -3
    first = [note.velocity for note in sorted(heard_lead, key=lambda note: note.beat)[:4]]
    assert [first[index] - thumbs[0] for index in range(4)] == [-6, -3, -4, -6]
    assert thumbs[0] == heard_support[0].velocity
    middle_finger = next(note.velocity for note in heard_lead if abs(note.beat - 1.25) < 1e-6)
    assert thumbs[1] - middle_finger == 3

    etude_ctx = _ctx(
        ensemble="villa",
        bars=1,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.0,
        spans={0: 0.0},
    )
    lead, support, low = _target_notes("etude1", 0)
    heard_lead, heard_support, heard_low = apply_guitar_wave(etude_ctx, lead, support, low, ["etude1"])
    sung = min(note.velocity or 0 for note in heard_lead)
    middles = sorted(heard_support, key=lambda note: note.beat)
    offsets = [note.velocity - middles[0].velocity for note in middles]
    assert offsets[0] == offsets[1] == offsets[2]
    assert offsets[3] - offsets[0] == 2
    assert max(note.velocity or 0 for note in middles) < (heard_low[0].velocity or 0) < sung

    eleven_lead, eleven_support, eleven_low = _target_notes("etude11", 0)
    heard_lead, heard_support, heard_low = apply_guitar_wave(etude_ctx, eleven_lead, eleven_support, eleven_low, ["etude11"])
    hairpin = next(note.velocity for note in heard_lead if abs(note.beat) < 1e-6)
    echo = next(note.velocity for note in heard_lead if abs(note.beat - 0.5) < 1e-6)
    assert echo == max(22 + 6, (hairpin or 0) - 8) or hairpin >= 66
    middles = [note.velocity for note in sorted(heard_support, key=lambda note: note.beat)]
    if hairpin is not None and hairpin <= 63:
        assert middles == [etude11_middle_velocity(hairpin, slot, "mf") for slot in (1, 2, 4, 5)]
        assert all(velocity <= 55 for velocity in middles)
        assert echo <= hairpin
        assert (heard_low[0].velocity or 0) > echo


def test_a_snapped_cluster_does_not_pull_the_warm_fill_over_63() -> None:
    bars = 8
    volumes = [1.0 + 40.0 * math.exp(-((bar - 4) ** 2) / 2.0) for bar in range(bars)]
    peak = _levels(volumes).index(1.0)
    phrase = _phrase_over(bars, peak)
    section = FormSection(0, bars, "phrase", 0)
    ctx = _ctx(
        ensemble="barrios",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.02,
        spans={0: 0.02},
    )
    lead, support, low = _target_notes("tremolo", peak)
    heard_lead, _support, heard_low = apply_guitar_wave(ctx, lead, support, low, ["tremolo"])
    thumb = next(note for note in heard_low if note.velocity is not None and note.velocity >= 66)
    quarter = int(thumb.beat)
    fills = [
        note
        for note in heard_lead
        if int(note.beat) == quarter and note.duration_beats <= 0.3
    ]
    fills.sort(key=lambda note: note.beat)
    assert fills[1].velocity is not None and fills[1].velocity <= 69
    assert all(note.velocity is not None and note.velocity <= 63 for note in (fills[0], fills[2], fills[3]))

    etude_ctx = _ctx(
        ensemble="villa",
        bars=bars,
        volumes=volumes,
        phrases=(phrase,),
        sections=(section,),
        rel_span=0.02,
        spans={0: 0.02},
    )
    lead, support, low = _target_notes("etude1", peak)
    heard_lead, heard_support, _low = apply_guitar_wave(etude_ctx, lead, support, low, ["etude1"])
    snapped = [note for note in heard_lead if note.velocity is not None and note.velocity >= 66]
    assert len(snapped) == 1
    assert abs(snapped[0].beat - 2.25) < 1e-6
    assert all(note.velocity is not None and note.velocity <= 52 for note in heard_support)

    lead, support, low = _target_notes("etude11", peak)
    heard_lead, heard_support, heard_low = apply_guitar_wave(etude_ctx, lead, support, low, ["etude11"])
    down = next(note for note in heard_lead if abs(note.beat) < 1e-6)
    assert down.velocity is not None and down.velocity >= 66 and down.accent
    echo = next(note for note in heard_lead if abs(note.beat - 0.5) < 1e-6)
    assert echo.velocity is not None and echo.velocity <= 60 and not echo.accent
    assert all(note.velocity is not None and note.velocity <= 55 for note in heard_support)
    assert heard_low[0].accent and (heard_low[0].velocity or 0) <= 62


def test_price_volume_and_trio_windows_stay_independent() -> None:
    bars = 8
    volumes = [1.0 + 30.0 * math.exp(-((bar - 3) ** 2) / 3.0) for bar in range(bars)]

    def peak_velocity(rel_span: float, *, trio: bool) -> int:
        phrase = _phrase_over(bars, _levels(volumes).index(1.0))
        section = FormSection(0, bars, "phrase", 0, trio=trio)
        ctx = _ctx(
            ensemble="classic",
            bars=bars,
            volumes=volumes,
            phrases=(phrase,),
            sections=(section,),
            rel_span=rel_span,
            spans={0: rel_span},
        )
        lead, _support, _low = apply_guitar_wave(ctx, _lead_line(bars), [], [], ["cantabile"])
        return max(note.velocity or 0 for note in lead)

    calm = peak_velocity(0.0, trio=False)
    wide = peak_velocity(0.03, trio=False)
    inward = peak_velocity(0.03, trio=True)
    # A flat price still opens the warm window from the volume wave. A wide
    # price reaches the pattern ceiling, and a trio uses half of that opening.
    assert 54 <= calm <= 63
    assert wide == 58
    assert inward == 56
    assert inward < wide
    assert alpha_price(0.0) == 0.0
    assert alpha_price(0.03) == 1.0
    assert warm_alpha(1.0, 0.0, inward=True) == 0.5

    flat = FormSection(0, bars, "phrase", 0)
    moving = FormSection(bars, bars * 2, "phrase", 1)
    both = volumes + volumes
    phrase_flat = _phrase_over(bars, _levels(volumes).index(1.0))
    phrase_moving = Phrase(
        bars * _EPB,
        bars * 2 * _EPB,
        tuple(Run(bars * _EPB + index, 1, 72 if index == 0 else 60) for index in range(bars * _EPB)),
    )
    ctx = _ctx(
        ensemble="barrios",
        bars=bars * 2,
        volumes=both,
        phrases=(phrase_flat, phrase_moving),
        sections=(flat, moving),
        spans={0: 0.0, bars: 0.03},
    )
    lead = _lead_line(bars * 2)
    for bar in range(bars, bars * 2):
        lead.append(_note(bar, 0.0, 70, 1, accent=True))
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["choro", "choro"])
    flat_notes = [note for note in heard if note.bar < bars]
    moving_notes = [note for note in heard if note.bar >= bars]
    assert all(note.velocity is not None and note.velocity <= 63 for note in flat_notes)
    assert any(note.velocity is not None and note.velocity >= 66 for note in moving_notes)


def test_voice_order_follows_the_pattern_family() -> None:
    def ordered(ensemble: str, pattern: str) -> tuple[int, int, int]:
        phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
        ctx = _ctx(
            ensemble=ensemble,
            bars=1,
            volumes=[4.0],
            phrases=(phrase,),
            sections=(FormSection(0, 1, "phrase", 0),),
            rel_span=0.0,
            spans={0: 0.0},
        )
        lead = [_note(0, 0.0, 67, 1, duration=1.0, accent=pattern == "bach_fuga")]
        low = [_note(0, 0.0, 48, 3, duration=1.0, accent=pattern == "bach_fuga")]
        support = [_note(0, 0.0, 55, 2, duration=1.0, accent=pattern == "bach_fuga")]
        heard_lead, heard_support, heard_low = apply_guitar_wave(ctx, lead, support, low, [pattern])
        return (
            heard_lead[0].velocity or 0,
            heard_low[0].velocity or 0,
            heard_support[0].velocity or 0,
        )

    lead, bass, inner = ordered("classic", "study")
    assert lead > bass > inner
    assert bass <= lead - 3 and inner <= bass - 2
    lead, bass, inner = ordered("villa", "thumb_cantabile")
    assert bass >= lead + 4
    assert lead >= inner + 1
    assert inner >= 18
    lead, bass, inner = ordered("bach", "bach_fuga")
    assert lead >= bass
    assert min(lead, bass) >= inner + 2
    lead, support, low = _target_notes("tremolo", 0)
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    ctx = _ctx(
        ensemble="barrios",
        bars=1,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(FormSection(0, 1, "phrase", 0),),
        rel_span=0.0,
        spans={0: 0.0},
    )
    heard_lead, _support, heard_low = apply_guitar_wave(ctx, lead, support, low, ["tremolo"])
    thumb = heard_low[0].velocity or 0
    fill = min(note.velocity or 0 for note in heard_lead if note.beat < 1)
    assert thumb > fill


def test_intro_examples_and_the_bass_floor() -> None:
    cadence = [54, 56, 54, 50, 48, 52, 56, 60]
    assert [shape_join_velocity(written, 60, 60, 32) for written in cadence] == [
        26,
        28,
        26,
        22,
        20,
        24,
        28,
        32,
    ]
    assert shape_join_velocity(46, 60, 60, 32) == 20
    assert [shape_join_velocity(written, 60, 60, 63) for written in (54, 60)] == [57, 63]
    assert [shape_join_velocity(written, 50, 46, 63) for written in (44, 50, 46)] == [57, 63, 59]
    assert shape_join_velocity(64, 64, 50, 63) == 63
    assert shape_join_velocity(50, 64, 50, 63) == 59
    assert prejoin_envelope(2, 26) == [27, 26]
    assert prejoin_envelope(2, 63) == [27, 56]
    assert prejoin_envelope(1, 26) == [26]
    assert prejoin_envelope(1, 63) == [56]
    assert shape_prejoin_velocity(46, 60, 27) == 20
    assert all(20 <= morendo_peak(63, index, 4) <= 63 for index in range(4))
    assert 20 <= morendo_peak(63, 3, 4) <= 26
    assert morendo_peak(63, 0, 4) == 63

    # The same cadence, bell, and Villa seam through the frame shaper.
    def shaped(notes: list[int], v_join: int) -> list[int]:
        lead = [_note(0, index / 2, 60, 1, velocity=level, duration=0.5) for index, level in enumerate(notes)]
        heard, _support, _low = apply_guitar_wave(
            _ctx(
                ensemble="barrios",
                bars=2,
                volumes=[4.0, 4.0],
                phrases=(Phrase(_EPB, _EPB * 2, (Run(_EPB, _EPB, 64),)),),
                sections=(FormSection(0, 1, "intro", 0), FormSection(1, 2, "phrase", 0)),
                kinds={0: "intro", 1: "phrase"},
                rel_span=0.0,
                spans={1: 0.0},
            ),
            lead + [_note(1, 0.0, 64, 1, velocity=48)],
            [],
            [],
            ["pedal", "andante"],
        )
        del v_join
        return [note.velocity or 0 for note in heard if note.bar == 0]

    # Body is one mf bar, so V_join is the andante ceiling at the band step,
    # not the illustrative 32/63. The crest of a flat ending stays 0, and the
    # bell's crest of 4 is preserved whenever the shifted contour fits.
    cadence_out = shaped(cadence, 32)
    assert max(cadence_out) - cadence_out[-1] == 0
    bell_out = shaped([44, 50, 46], 63)
    assert bell_out[1] - bell_out[2] == 4
    assert bell_out[1] - bell_out[0] == 6
    villa_out = shaped([64, 50], 63)
    assert villa_out[0] - villa_out[-1] == 4


def test_missing_bar_volumes_fall_back_to_the_printed_band() -> None:
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    section = FormSection(0, 1, "phrase", 0)

    def level(band: str) -> int:
        ctx = _ctx(
            ensemble="classic",
            bars=1,
            volumes=None,
            phrases=(phrase,),
            sections=(section,),
            bands={0: band},
            rel_span=0.0,
            spans={0: 0.0},
        )
        assert resolve_bar_volumes(ctx) == [{"p": 1.0, "mp": 2.0, "mf": 4.0, "f": 8.0}[band]]
        lead, _support, _low = apply_guitar_wave(ctx, [_note(0, 0.0, 64, 1)], [], [], ["cantabile"])
        return lead[0].velocity or 0

    assert level("p") < level("f")


def test_humanize_keeps_warm_notes_under_64_and_snaps_inside_the_nail() -> None:
    def offset(sign: int):
        def choose(*_args) -> int:
            return sign

        return choose

    def plateau(velocity: int, ensemble: str, sign: int) -> list[int]:
        notes = tuple(_note(0, beat, 60 + int(beat), 1, velocity=velocity) for beat in (0.0, 1.0))
        score = Score(
            title="wave",
            bpm=96,
            bars=1,
            regimes=("sideway", "sideway", "sideway"),
            regime_samples=None,
            slots=(),
            high=(),
            lead=notes,
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
        heard = humanize(score, offset_at=offset(sign))
        return [note.velocity or 0 for note in heard.lead]

    assert all(velocity <= 64 for velocity in plateau(63, "villa", 2))
    assert all(66 <= velocity <= 76 for velocity in plateau(74, "brouwer", 2))
    assert all(velocity == 66 for velocity in plateau(66, "villa", -2))
    assert all(velocity <= 70 for velocity in plateau(70, "bach", 2))
    assert all(velocity <= 70 for velocity in plateau(68, "classic", 2))


def test_ties_copy_the_attack_after_the_wave() -> None:
    phrase = Phrase(0, _EPB, (Run(0, _EPB, 64),))
    ctx = _ctx(
        ensemble="classic",
        bars=1,
        volumes=[4.0],
        phrases=(phrase,),
        sections=(FormSection(0, 1, "phrase", 0),),
        rel_span=0.0,
        spans={0: 0.0},
    )
    lead = [
        _note(0, 0.0, 64, 1, velocity=40, duration=1.0, tie_start=True),
        _note(0, 1.0, 64, 1, velocity=12, duration=1.0, tie_stop=True),
    ]
    heard, _support, _low = apply_guitar_wave(ctx, lead, [], [], ["cantabile"])
    assert heard[0].velocity == heard[1].velocity
    assert heard[0].velocity != 12
