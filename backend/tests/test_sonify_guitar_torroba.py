"""Torroba: Andalucian harmony, Ab on G, Picardy, and the four guitar patterns."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.sonify.chords import (
    AF,
    AM,
    AM7,
    BF,
    BF7,
    BM7B5,
    C,
    CM,
    CMAJ7,
    DM,
    DM7,
    EF,
    EM,
    EM7,
    F,
    FM,
    FMAJ7,
    FM7,
    G,
    G7,
    GM,
)
from app.sonify.form import (
    METER_34,
    METER_44,
    METER_68,
    ChordSlot,
    FormSection,
    FormSpec,
    _breaks_held_note_across_barline,
    compose_meter,
    plan_markov_chords,
)
from app.sonify.guitar import _place_melody, render_guitar_score
from app.sonify.guitar_patterns import (
    Unplayable,
    _Ctx,
    _fallback_body_pattern,
    _owning_pattern,
    _select_body,
    _shape_dynamics,
    assert_playable,
    headline_id,
)
from app.sonify.guitar_torroba import (
    _render_torroba_bar,
    _torroba_bass,
    _torroba_contrast,
    _torroba_primary,
    torroba_scale_step,
)
from app.sonify.guitar_wave import _is_target, profile_for
from app.sonify.harmony import BACH, TORROBA, TorrobaDialect, dialect_for
from app.sonify.humanize import _clamp_guitar
from app.sonify.model import HarmonyEvent, NoteEvent, Phrase, Run, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.phrasing import quantize_strong_beats
from app.sonify.quantize import bar_quantization_loss, c_natural_minor_scale


def _joined(start: int, pitches: list[int], held: bool = False) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs), held)


def _ctx(
    *,
    melody: list[int],
    phrase: Phrase,
    kind: str = "4/4",
    epb: int = 8,
    strong: tuple[int, ...] = (0, 4),
    bpm: int = 96,
    character: str = "rally",
    bars: int | None = None,
    chord=C,
    regime: str | None = "sideway",
    mode: str = "major",
    sections: tuple = (),
    bar_beats: float = 4.0,
) -> _Ctx:
    count = bars if bars is not None else max(1, len(melody) // epb)
    return _Ctx(
        melody=list(melody),
        raw=list(melody),
        chord_at={bar: chord for bar in range(count)},
        kind_at={bar: "phrase" for bar in range(count)},
        band_at={bar: "mf" for bar in range(count)},
        phrases=(phrase,),
        bars=count,
        bpm=bpm,
        ensemble="torroba",
        mode=mode,
        character=character,
        character_at=None,
        sections=sections,
        rel_span=0.02,
        semitones=0,
        bass_low=40,
        bass_high=55,
        mid_low=50,
        mid_high=65,
        treble_floor=59,
        treble_top=81,
        ceiling=83,
        epb=epb,
        kind=kind,
        strong=strong,
        bar_beats=bar_beats,
        regime_at={bar: regime for bar in range(count)} if regime is not None else {},
    )


def _scale():
    return c_natural_minor_scale()


def test_dialect_catalog_bans_and_named_edges() -> None:
    assert isinstance(dialect_for("torroba"), TorrobaDialect)
    assert dialect_for("torroba").name == "torroba"
    assert TORROBA.extra("minor") == (BF,)
    assert {chord.name for chord in TORROBA.extra("major")} == {"Bb", "Fm"}
    assert C not in TORROBA.extra("minor")
    from app.sonify.chords import AFMAJ7, CM7, DM7B5, EFMAJ7, FDIM7

    for chord in (CM, BF, AF, G, G7, FM, EF):
        assert TORROBA.allowed(chord, pedal=False, phrase_downbeat=True, character=None, mode="minor")
    for chord in (CM7, FM7, EFMAJ7, AFMAJ7, DM7B5, FDIM7):
        assert not TORROBA.allowed(chord, pedal=False, phrase_downbeat=False, character=None, mode="minor")
    for chord in (C, F, G, G7, BF, FM, AM, DM, EM):
        assert TORROBA.allowed(chord, pedal=False, phrase_downbeat=True, character=None, mode="major")
    for chord in (CMAJ7, FMAJ7, AM7, DM7, EM7, AF, EF, BF7, GM, BM7B5):
        assert not TORROBA.allowed(chord, pedal=False, phrase_downbeat=False, character=None, mode="major")
    assert TORROBA.transition(CM, BF, "minor") == 0.56
    assert TORROBA.transition(BF, AF, "minor") == 0.62
    assert TORROBA.transition(AF, G, "minor") == 0.66
    assert TORROBA.transition(G, CM, "minor") > TORROBA.transition(G7, CM, "minor") > 0
    assert TORROBA.transition(G7, FM, "minor") == 0.0
    assert TORROBA.transition(G7, EF, "minor") == 0.0
    assert TORROBA.transition(G7, AF, "minor") == 0.0
    assert TORROBA.transition(G7, G, "minor") == 0.0
    assert TORROBA.transition(AF, G7, "minor") > 0
    assert TORROBA.transition(BF, FM, "minor") == 0.0
    assert TORROBA.transition(EF, BF, "minor") == 0.0
    assert TORROBA.transition(BF, G, "minor") == 0.0
    assert TORROBA.transition(C, BF, "major") == 0.48
    assert TORROBA.transition(BF, F, "major") == 0.52
    assert TORROBA.transition(F, C, "major") == 0.56
    assert TORROBA.transition(C, FM, "major") > 0
    assert TORROBA.transition(BF, G, "major") == 0.0
    assert TORROBA.transition(G, FM, "major") > 0
    assert TORROBA.transition(FM, C, "major") > 0
    assert TORROBA.allowed(CM, pedal=True, phrase_downbeat=False, character=None, mode="minor")
    assert not TORROBA.allowed(BF, pedal=True, phrase_downbeat=False, character=None, mode="minor")
    assert not TORROBA.allowed(C, pedal=True, phrase_downbeat=False, character=None, mode="minor")
    assert TORROBA.allowed(C, pedal=True, phrase_downbeat=False, character=None, mode="major")


def test_minor_path_can_walk_the_andalucian_loop_on_ab() -> None:
    scale = _scale()

    def bar(downbeat: int, middle: int) -> list[int]:
        row = [downbeat] * 8
        row[4] = middle
        for eighth in range(8):
            if eighth >= 4:
                row[eighth] = middle
        return row

    bars = [
        bar(60, 63),
        bar(70, 62),
        bar(68, 60),
        bar(67, 68),
        bar(60, 63),
    ]
    spec = FormSpec(
        bars=5,
        bpm=96,
        sections=(FormSection(0, 5, "phrase", 0),),
        borrowed=False,
    )
    path = plan_markov_chords(
        ("sideway",),
        [note for row in bars for note in row],
        scale,
        spec,
        character="rally",
        mode="minor",
        dialect=TORROBA,
    )
    assert [chord.name for chord in path] == ["Cm", "Bb", "Ab", "G", "Cm"]
    assert bars[2][0] % 12 == 8
    assert bars[3][4] % 12 == 8


def test_ab_is_heard_on_g_only_for_torroba() -> None:
    scale = _scale()
    ab = [68] * 8
    assert bar_quantization_loss(ab, G.pitch_classes, scale, mode="minor", chord_name="G", ensemble="torroba") == 0
    assert bar_quantization_loss(ab, G7.pitch_classes, scale, mode="minor", chord_name="G7", ensemble="torroba") == 0
    assert bar_quantization_loss(ab, CM.pitch_classes, scale, mode="minor", chord_name="Cm", ensemble="torroba") > 0
    assert bar_quantization_loss(ab, G.pitch_classes, scale, mode="minor", chord_name="G", ensemble="bach") > 0
    assert bar_quantization_loss(ab, G.pitch_classes, scale, mode="minor", chord_name="G") > 0
    other = [65] * 8
    assert bar_quantization_loss(other, G.pitch_classes, scale, mode="minor", chord_name="G", ensemble="torroba") > 0


def test_common_tone_keeps_a_held_ab_across_cm_and_g() -> None:
    scale = _scale()
    held = [68] * 16
    kept = quantize_strong_beats(held, {0: CM, 1: G}, scale, "minor", "torroba")
    assert all(note % 12 == 8 for note in kept[8:])
    assert any(note % 12 != 8 for note in kept[:8])
    snapped = quantize_strong_beats(held, {0: CM, 1: G}, scale, "minor", "bach")
    assert any(note % 12 != 8 for note in snapped[8:])
    untouched = quantize_strong_beats([68] * 8, {0: G}, scale, "minor")
    assert all(note % 12 != 8 for note in untouched)
    solo = quantize_strong_beats([68] * 8, {0: G}, scale, "minor", "torroba")
    assert solo == [68] * 8


def test_place_melody_does_not_restore_ab_after_compression() -> None:
    phrase = Phrase(0, 8, (Run(0, 8, 68),))
    kept = _place_melody([68] * 8, (phrase,), 59, 81, {0: G}, "minor", ensemble="torroba")
    assert all(note % 12 == 8 for note in kept)
    moved = _place_melody([67] * 8, (Phrase(0, 8, (Run(0, 8, 67),)),), 59, 81, {0: G}, "minor", raw_pitches=[68] * 8, ensemble="torroba")
    assert all(note % 12 != 8 for note in moved)
    other = _place_melody([68] * 8, (phrase,), 59, 81, {0: G}, "minor", ensemble="villa")
    assert all(note % 12 != 8 for note in other)


def test_held_ab_into_g_is_not_a_break() -> None:
    scale = _scale()
    index = {note: cursor for cursor, note in enumerate(scale)}
    assert _breaks_held_note_across_barline(68, CM, G, scale, index, "minor", TORROBA) is False
    assert _breaks_held_note_across_barline(68, AF, G7, scale, index, "minor", TORROBA) is False
    assert _breaks_held_note_across_barline(68, AF, G7, scale, index, "minor", BACH) is True
    assert _breaks_held_note_across_barline(68, AF, G, scale, index, "minor", None) is True


def _render(pitches, phrases, *, chords, kinds, mode="minor", character="calm", bpm=96, meter=METER_44, sections=None):
    epb = meter.eighths_per_bar
    bars = len(pitches) // epb
    slots = tuple(ChordSlot(bar, 1, chords[bar], "sideway", kinds[bar]) for bar in range(bars))
    with compose_meter(meter):
        return render_guitar_score(
            title="Torroba",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=list(pitches),
            phrases=phrases,
            dynamics=(),
            bands=["mf"] * bars,
            band_at={bar: "mf" for bar in range(bars)},
            musical_bars=bars,
            total_eighths=len(pitches),
            bpm=bpm,
            ensemble="torroba",
            harmonies=tuple(HarmonyEvent(bar, chords[bar]) for bar in range(bars)),
            mode=mode,
            character=character,
            sections=sections,
            rel_span=0.0,
        )


def test_picardy_swaps_only_the_closing_bar_and_does_not_requantize(monkeypatch) -> None:
    pitches = [67] * 16
    phrase = _joined(0, pitches)
    with compose_meter(METER_44):
        under_cm = _place_melody(list(pitches), (phrase,), 59, 81, {0: CM, 1: CM}, "minor", ensemble="torroba")
    assert all(note % 12 != 3 for note in under_cm[8:])
    calls = {"n": 0}
    real = quantize_strong_beats

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr("app.sonify.guitar.quantize_strong_beats", counted)
    score = _render(
        pitches,
        (phrase,),
        chords={0: CM, 1: CM},
        kinds={0: "phrase", 1: "phrase"},
        character="calm",
        bpm=96,
    )
    assert calls["n"] == 1
    assert score.slots[0].chord.name == "Cm"
    assert score.slots[1].chord.name == "C"
    lead = [note.midi for note in score.lead if note.bar == 1 and note.midi is not None]
    assert lead
    assert lead[0] == under_cm[8]
    assert score.harmonies[-1].chord.name == "C"


def test_picardy_leaves_a_bar_that_already_sings_eb_and_pedal_bars() -> None:
    sung = [63] * 8
    score = _render(sung, (_joined(0, sung),), chords={0: CM}, kinds={0: "phrase"}, character="calm")
    assert score.slots[0].chord.name == "Cm"
    body = [65] * 8
    outro = [65] * 8
    pitches = body + outro
    phrase = _joined(0, pitches)
    held = _render(
        pitches,
        (phrase,),
        chords={0: CM, 1: CM},
        kinds={0: "phrase", 1: "outro"},
        character="calm",
        sections=(FormSection(0, 1, "phrase", 0), FormSection(1, 2, "outro", 0)),
    )
    assert held.slots[0].chord.name == "Cm"
    assert held.slots[1].chord.name == "Cm"


def test_picardy_splits_a_multibar_slot() -> None:
    pitches = [67] * 16
    phrase = _joined(0, pitches)
    slot = ChordSlot(0, 2, CM, "sideway", "phrase")
    with compose_meter(METER_44):
        score = render_guitar_score(
            title="Torroba",
            chosen=(),
            sample_indexes=None,
            slots=(slot,),
            pitches=pitches,
            phrases=(phrase,),
            dynamics=(),
            bands=["mf", "mf"],
            band_at={0: "mf", 1: "mf"},
            musical_bars=2,
            total_eighths=16,
            bpm=96,
            ensemble="torroba",
            harmonies=(HarmonyEvent(0, CM),),
            mode="minor",
            character="calm",
            rel_span=0.0,
        )
    assert [item.chord.name for item in score.slots] == ["Cm", "C"]
    assert score.slots[0].start == 0 and score.slots[0].length == 1
    assert score.slots[1].start == 1 and score.slots[1].length == 1


def test_four_fallbacks_and_the_mood_map() -> None:
    empty = _ctx(melody=[64] * 8, phrase=Phrase(0, 0, ()), character="rally")
    empty = _Ctx(
        melody=[],
        raw=[],
        chord_at={},
        kind_at={},
        band_at={},
        phrases=(),
        bars=0,
        bpm=96,
        ensemble="torroba",
        mode="major",
        character=None,
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
        epb=8,
        kind="4/4",
        strong=(0, 4),
        bar_beats=4.0,
    )
    assert headline_id(empty, []) == "sonatina"
    assert _owning_pattern(empty, 0, []) == "sonatina"
    assert _fallback_body_pattern(empty, 0, []) == "sonatina"
    phrase = _joined(0, [64] * 8)
    rally = _ctx(melody=[64] * 8, phrase=phrase, character="rally")
    assert _select_body(rally, phrase, first_body=True, previous=[], section=None) == "sonatina"
    calm = _ctx(melody=[64] * 8, phrase=phrase, character="calm")
    assert _select_body(calm, phrase, first_body=True, previous=[], section=None) == "castillo"
    volatile = _ctx(melody=[64] * 8, phrase=phrase, character="volatile")
    assert _select_body(volatile, phrase, first_body=True, previous=[], section=None) == "fandanguillo"
    slow = _ctx(melody=[64] * 8, phrase=phrase, character="selloff", bpm=72)
    assert _select_body(slow, phrase, first_body=True, previous=[], section=None) == "castillo"
    selloff = _ctx(melody=[64] * 8, phrase=phrase, character="selloff", bpm=96)
    assert _select_body(selloff, phrase, first_body=True, previous=[], section=None) == "sonatina"
    scherzo = _ctx(melody=[64] * 6, phrase=_joined(0, [64] * 6), kind="6/8", epb=6, strong=(0, 3), character="calm", bar_beats=3)
    assert _torroba_primary(scherzo, "calm", framed_macro=True) == "danza"
    assert _torroba_primary(scherzo, "calm", framed_macro=False) == "castillo"
    four = _ctx(melody=[64] * 8, phrase=phrase, kind="4/4", character="volatile", bpm=108)
    assert _torroba_primary(four, "volatile", framed_macro=True) == "fandanguillo"
    assert "danza" != _torroba_primary(four, "calm", framed_macro=True)
    assert _torroba_contrast(scherzo, "danza") == "castillo"
    assert _torroba_contrast(four, "castillo") == "sonatina"
    assert _torroba_contrast(slow, "castillo") == "sonatina"


def test_dance_writes_a_four_step_gap_and_one_extra_per_bar() -> None:
    phrase = _joined(0, [72] * 8)
    ctx = _ctx(melody=[72] * 8, phrase=phrase, character="volatile")
    with compose_meter(METER_44):
        lead, _support, _low = _render_torroba_bar(ctx, 0, phrase, "fandanguillo")
    by_beat = {round(note.beat, 2): note for note in lead if note.duration_beats >= 0.5}
    assert by_beat[0.0].velocity == 68 and by_beat[0.0].accent
    assert by_beat[1.0].velocity == 64 and not by_beat[1.0].accent
    assert by_beat[2.0].velocity == 68 and by_beat[2.0].accent
    assert by_beat[0.0].velocity - by_beat[1.0].velocity == 4
    rising = Phrase(0, 16, (Run(0, 8, 74), Run(8, 8, 60)))
    shape_ctx = _ctx(melody=[74] * 8 + [60] * 8, phrase=rising, bars=2)
    events = [
        NoteEvent(bar=0, beat=0.0, midi=74, duration_beats=0.5, voice=1, velocity=68, accent=True),
        NoteEvent(bar=0, beat=3.0, midi=72, duration_beats=0.5, voice=1, velocity=64),
        NoteEvent(bar=0, beat=0.0, midi=50, duration_beats=0.5, voice=3, velocity=60),
    ]
    shaped, _support, low = _shape_dynamics(shape_ctx, events[:2], [], events[2:], set(), ["fandanguillo"])
    assert shaped[0].velocity - shaped[1].velocity == 4
    assert shaped[0].velocity - 68 == low[0].velocity - 60
    assert shaped[0].velocity != 68


def test_snap_targets_are_accented_leads_and_castillo_has_none() -> None:
    castillo = profile_for("torroba", "castillo")
    sonatina = profile_for("torroba", "sonatina")
    dance = profile_for("torroba", "danza")
    assert castillo is not None and castillo.snap_wide is None and castillo.max_units_per_phrase == 0
    assert sonatina is not None and (sonatina.snap_calm, sonatina.snap_wide) == (66, 68)
    assert sonatina.max_units_per_phrase == 1 and sonatina.max_units_per_sec == 2
    assert dance is not None and (dance.snap_calm, dance.snap_wide) == (68, 70)
    assert dance.max_units_per_phrase == 1 and dance.max_units_per_sec == 3
    assert profile_for("torroba", "fandanguillo").max_units_per_sec == 3
    ctx = _ctx(melody=[72] * 8, phrase=_joined(0, [72] * 8))
    accented = NoteEvent(bar=0, beat=0.0, midi=72, duration_beats=0.5, voice=1, velocity=68, accent=True)
    plain = NoteEvent(bar=0, beat=1.0, midi=72, duration_beats=0.5, voice=1, velocity=72, accent=False)
    inner = NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=0.5, voice=2, velocity=68, accent=True)
    assert _is_target(ctx, "castillo", accented, "lead", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "sonatina", accented, "lead", ctx.phrases[0], 0.0, 1.0) is True
    assert _is_target(ctx, "sonatina", plain, "lead", ctx.phrases[0], 1.0, 1.0) is False
    assert _is_target(ctx, "fandanguillo", inner, "support", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "danza", accented, "lead", ctx.phrases[0], 0.0, 1.0) is True


def test_inner_above_65_is_playable_only_under_the_lead() -> None:
    def score(inner: int, lead: int) -> Score:
        return Score(
            title="Torroba",
            bpm=96,
            bars=1,
            regimes=("sideway", "sideway", "sideway"),
            regime_samples=None,
            slots=(ChordSlot(0, 1, C, "sideway", "phrase"),),
            high=(),
            lead=(NoteEvent(bar=0, beat=0.0, midi=lead, duration_beats=1.0, voice=1, velocity=64),),
            support=(NoteEvent(bar=0, beat=0.0, midi=inner, duration_beats=1.0, voice=2, velocity=56),),
            comp=(),
            low=(NoteEvent(bar=0, beat=0.0, midi=50, duration_beats=1.0, voice=3, velocity=54),),
            dynamics=(),
            harmonies=(),
            liquidity=("mf",),
            phrases=(),
            lead_wedges=(),
            support_wedges=(),
            lead_dynamics=(),
            support_dynamics=(),
            variant="guitar",
            ensemble="torroba",
        )

    assert_playable(score(68, 76), profiles="torroba")
    with pytest.raises(Unplayable, match="above the middle register"):
        assert_playable(score(68, 76), profiles="study")
    with pytest.raises(Unplayable, match="not below the melody"):
        assert_playable(score(76, 76), profiles="torroba")


def test_open_g3_is_never_the_bass() -> None:
    bare = SimpleNamespace(bass_low=40, bass_high=55, semitones=0, regime_at={})
    side = SimpleNamespace(bass_low=40, bass_high=55, semitones=0, regime_at={0: "sideway"})
    down = SimpleNamespace(bass_low=40, bass_high=55, semitones=0, regime_at={0: "downtrend"})
    up = SimpleNamespace(bass_low=40, bass_high=55, semitones=0, regime_at={0: "uptrend"})
    assert _torroba_bass(side, G, 0, 72) == 50
    assert _torroba_bass(bare, G, 0, 72) == 50
    assert _torroba_bass(down, G, 0, 72) == 43
    assert _torroba_bass(up, CM, 0, 72) % 12 == 0
    for ctx, chord in ((side, G), (down, G), (up, CM), (bare, G), (side, CM)):
        bass = _torroba_bass(ctx, chord, 0, 72)
        assert bass is not None
        assert bass + ctx.semitones != 55
        assert 40 <= bass + ctx.semitones <= 53


def test_sonatina_slur_leap_and_run_stay_out_of_scale_eighths() -> None:
    step = [72] * 4 + [74] * 4
    step_phrase = _joined(0, step)
    ctx = _ctx(melody=step, phrase=step_phrase, character="rally", chord=G)
    with compose_meter(METER_44):
        lead, _support, _low = _render_torroba_bar(ctx, 0, step_phrase, "sonatina")
    strong = [note for note in lead if note.duration_beats >= 0.5]
    assert [note.midi for note in strong] == [72, 74]
    assert any(note.slur_start for note in strong) and any(note.slur_stop for note in strong)
    assert not any(note.duration_beats == 0.25 for note in lead)

    leap = [74] * 4 + [67] * 4
    leap_phrase = _joined(0, leap)
    leap_ctx = _ctx(melody=leap, phrase=leap_phrase, character="rally", chord=G)
    with compose_meter(METER_44):
        leaped, _support, _low = _render_torroba_bar(leap_ctx, 0, leap_phrase, "sonatina")
    arrivals = [note for note in leaped if abs(note.beat - 2.0) < 1e-6]
    assert len(arrivals) == 1 and arrivals[0].duration_beats == 0.5 and arrivals[0].midi == 67
    approaches = [note for note in leaped if note.duration_beats == 0.25]
    assert len(approaches) == 1
    assert approaches[0].beat == 1.75 and approaches[0].velocity == 56 and approaches[0].slur_start
    assert arrivals[0].slur_stop

    rising = [67] * 4 + [74] * 4
    rise_phrase = _joined(0, rising)
    score = _render(
        rising,
        (rise_phrase,),
        chords={0: G},
        kinds={0: "phrase"},
        mode="major",
        character="rally",
        bpm=96,
    )
    run = [note for note in score.lead if note.duration_beats == 0.25]
    assert 2 <= len(run) <= 4
    assert all((note.velocity or 0) <= 64 for note in run)
    arrival = [note for note in score.lead if abs(note.beat - 2.0) < 1e-6 and note.duration_beats >= 0.5]
    assert len(arrival) == 1 and arrival[0].midi == 74
    assert run[0].slur_start and arrival[0].slur_stop
    assert score.scale_eighths == ()
    xml = score_to_musicxml(score)
    assert "<grace" not in xml
    assert "<harmonic" not in xml


def test_danza_grids_and_humanize_ceiling() -> None:
    phrase = _joined(0, [72] * 6)
    six = _ctx(
        melody=[72] * 6,
        phrase=phrase,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        character="calm",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_68):
        lead, support, low = _render_torroba_bar(six, 0, phrase, "danza")
    chords = {round(note.beat, 2) for note in lead if note.staccato}
    assert chords == {0.0, 1.5}
    answers = [note for note in lead if not note.staccato]
    assert {round(note.beat, 2) for note in answers} == {0.5, 1.0, 2.0, 2.5}
    assert all(note.velocity == 64 and not note.accent for note in answers)
    assert all(note.staccato for note in support + low)

    three = _ctx(
        melody=[72] * 6,
        phrase=phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        character="calm",
        bar_beats=3,
    )
    with compose_meter(METER_34):
        waltzed, _support, _low = _render_torroba_bar(three, 0, phrase, "danza")
    assert sum(1 for note in waltzed if note.staccato) == 1
    weak = next(note for note in waltzed if abs(note.beat - 2.0) < 1e-6)
    assert weak.velocity == 64 and not weak.accent and not weak.staccato

    original = (NoteEvent(bar=0, beat=0.0, midi=72, duration_beats=0.5, voice=1, velocity=70),)
    heard = [NoteEvent(bar=0, beat=0.0, midi=72, duration_beats=0.5, voice=1, velocity=80)]
    assert _clamp_guitar(original, heard, "torroba")[0].velocity == 73
    assert _clamp_guitar(original, heard, "bach")[0].velocity == 73
    assert _clamp_guitar(original, heard, "villa")[0].velocity == 79


def test_scale_step_may_be_ab_and_does_not_raise_bb() -> None:
    ctx = SimpleNamespace(mode="minor")
    assert torroba_scale_step(ctx, 69, 67, low=59, high=81) % 12 == 8
    stepped = torroba_scale_step(ctx, 70, 74, low=59, high=81)
    assert stepped % 12 != 11
    assert torroba_scale_step(ctx, 70, 67, low=59, high=81) % 12 == 8


def test_frames_and_body_patterns_stay_playable() -> None:
    pitches = [72] * 32
    phrase = _joined(8, [72] * 16)
    intro = _joined(0, [72] * 8, held=True)
    sections = (
        FormSection(0, 2, "intro", 0),
        FormSection(2, 6, "phrase", 0),
        FormSection(6, 8, "outro", 0),
    )
    kinds = {0: "intro", 1: "intro", 2: "phrase", 3: "phrase", 4: "phrase", 5: "phrase", 6: "outro", 7: "outro"}
    chords = {bar: CM for bar in range(8)}
    calm = _render(
        pitches,
        (intro, phrase, _joined(24, [60] * 8)),
        chords=chords,
        kinds=kinds,
        mode="minor",
        character="calm",
        bpm=96,
        sections=sections,
    )
    assert_playable(calm, profiles="torroba")
    volatile = _render(
        pitches,
        (intro, phrase, _joined(24, [60] * 8)),
        chords=chords,
        kinds=kinds,
        mode="minor",
        character="volatile",
        bpm=96,
        sections=sections,
    )
    assert_playable(volatile, profiles="torroba")
    long_kinds = {bar: ("intro" if bar < 4 else "phrase" if bar < 8 else "outro") for bar in range(12)}
    long_sections = (
        FormSection(0, 4, "intro", 0),
        FormSection(4, 8, "phrase", 0),
        FormSection(8, 12, "outro", 0),
    )
    long_score = _render(
        [67] * 96,
        (_joined(0, [67] * 32, held=True), _joined(32, [67] * 32), _joined(64, [60] * 32)),
        chords={bar: CM for bar in range(12)},
        kinds=long_kinds,
        mode="minor",
        character="rally",
        bpm=96,
        sections=long_sections,
    )
    assert_playable(long_score, profiles="torroba")
    outro_notes = [note.midi for note in (*long_score.lead, *long_score.support, *long_score.low) if note.bar == 11 and note.midi is not None]
    assert any(note % 12 == 4 for note in outro_notes)
    assert long_score.slots[-1].chord.name == "Cm"
    for pattern, meter, character in (
        ("castillo", METER_44, "calm"),
        ("sonatina", METER_44, "rally"),
        ("fandanguillo", METER_44, "volatile"),
        ("danza", METER_68, "calm"),
    ):
        epb = meter.eighths_per_bar
        row = [72] * (epb * 4)
        rendered = _render(
            row,
            (_joined(0, row),),
            chords={bar: C for bar in range(4)},
            kinds={bar: "phrase" for bar in range(4)},
            mode="major",
            character=character,
            bpm=96 if pattern != "danza" else 96,
            meter=meter,
        )
        if pattern == "danza":
            rendered = _render(
                [72] * 24,
                (_joined(0, [72] * 24),),
                chords={bar: C for bar in range(4)},
                kinds={bar: "phrase" for bar in range(4)},
                mode="major",
                character="calm",
                meter=METER_68,
            )
        assert_playable(rendered, profiles="torroba")


def test_breath_harmonics_and_fandanguillo_grids() -> None:
    row = [72] * 32
    phrase = _joined(0, row)
    ctx = _ctx(melody=row, phrase=phrase, character="volatile", bars=4, chord=C)
    with compose_meter(METER_44):
        support_counts = []
        lead_counts = []
        for bar in range(4):
            lead, support, _low = _render_torroba_bar(ctx, bar, phrase, "fandanguillo")
            support_counts.append(len(support))
            lead_counts.append(len([note for note in lead if note.midi is not None]))
    assert support_counts[0] >= 2
    assert support_counts[3] < support_counts[0]
    assert support_counts[3] <= support_counts[0] // 2 + 1
    assert lead_counts[3] == lead_counts[0]

    node = [67] * 8
    node_phrase = _joined(0, node)
    node_ctx = _ctx(melody=node, phrase=node_phrase, character="calm", chord=G, mode="minor")
    with compose_meter(METER_44):
        sung, emptied, _low = _render_torroba_bar(node_ctx, 0, node_phrase, "castillo")
    assert sung[0].midi == 67 and sung[0].velocity == 48 and sung[0].duration_beats >= 2
    assert emptied == []

    ordinary = [72] * 8
    ordinary_phrase = _joined(0, ordinary)
    ordinary_ctx = _ctx(melody=ordinary, phrase=ordinary_phrase, character="calm", chord=C)
    with compose_meter(METER_44):
        held, support, _low = _render_torroba_bar(ordinary_ctx, 0, ordinary_phrase, "castillo")
    assert held[0].midi == 72 and held[0].velocity != 48
    assert support

    short = [67] * 8
    short_phrase = _joined(0, short)
    short_ctx = _ctx(melody=short, phrase=short_phrase, character="rally", chord=G, mode="minor")
    with compose_meter(METER_44):
        sonatina, _support, _low = _render_torroba_bar(short_ctx, 0, short_phrase, "sonatina")
    assert all(note.midi == 67 and note.velocity != 48 for note in sonatina if note.duration_beats >= 0.5)

    six = _ctx(
        melody=[72] * 6,
        phrase=_joined(0, [72] * 6),
        kind="6/8",
        epb=6,
        strong=(0, 3),
        character="volatile",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_68):
        lead, support, low = _render_torroba_bar(six, 0, six.phrases[0], "fandanguillo")
    by_beat = {round(note.beat, 2): note for note in lead}
    assert set(by_beat) == {0.0, 1.0, 1.5}
    assert by_beat[0.0].velocity >= 68 and by_beat[0.0].accent and by_beat[0.0].midi == 72
    assert by_beat[1.0].velocity == 64 and not by_beat[1.0].accent
    assert by_beat[1.5].velocity >= 68 and by_beat[1.5].accent
    sounding = [note for note in (*lead, *support, *low) if abs(note.beat) < 1e-6]
    assert len(sounding) <= 3
    assert max(note.midi for note in sounding if note.midi is not None) == 72

    three = _ctx(
        melody=[72] * 6,
        phrase=_joined(0, [72] * 6),
        kind="3/4",
        epb=6,
        strong=(0,),
        character="volatile",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_34):
        waltzed, _support, _low = _render_torroba_bar(three, 0, three.phrases[0], "fandanguillo")
    beats = {round(note.beat, 2): note for note in waltzed}
    assert set(beats) == {0.0, 1.0, 2.0}
    assert beats[0.0].velocity >= 68 and beats[0.0].accent
    assert beats[1.0].velocity == 64 and not beats[1.0].accent
    assert beats[2.0].velocity == 64 and not beats[2.0].accent


def _covers_beat(note: NoteEvent, bar: int, beat: float, length: float) -> bool:
    if note.bar != bar or note.midi is None:
        return False
    start = note.beat
    end = note.beat + note.duration_beats
    return start < beat + length - 1e-9 and end > beat + 1e-9


def _two_bars(pitches, phrases, chords, *, character="rally", character_at=None):
    bars = len(pitches) // 8
    slots = tuple(ChordSlot(bar, 1, chords[bar], "sideway", "phrase") for bar in range(bars))
    with compose_meter(METER_44):
        return render_guitar_score(
            title="Torroba",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=list(pitches),
            phrases=phrases,
            dynamics=(),
            bands=["mf"] * bars,
            band_at={bar: "mf" for bar in range(bars)},
            musical_bars=bars,
            total_eighths=len(pitches),
            bpm=96,
            ensemble="torroba",
            harmonies=tuple(HarmonyEvent(bar, chords[bar]) for bar in range(bars)),
            mode="major",
            character=character,
            character_at=character_at,
            rel_span=0.0,
        )


def test_sonatina_downbeat_leap_step_run_and_castillo_hold() -> None:
    leap = _two_bars([74] * 8 + [67] * 8, (_joined(0, [74] * 8 + [67] * 8),), {0: G, 1: G})
    pickup = [note for note in leap.lead if note.midi is not None and note.duration_beats == 0.25]
    assert [(note.bar, round(note.beat, 2)) for note in pickup] == [(0, 3.75)]
    assert pickup[0].slur_start and pickup[0].voice == 1 and (pickup[0].velocity or 0) <= 64
    arrival = [note for note in leap.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(arrival) == 1 and arrival[0].midi == 67 and arrival[0].slur_stop
    assert not any(_covers_beat(note, 0, 3.75, 0.25) for note in leap.support)
    assert all(note.bar >= 0 for note in leap.lead)
    assert_playable(leap, profiles="torroba")

    step = _two_bars([71] * 8 + [72] * 8, (_joined(0, [71] * 8 + [72] * 8),), {0: G, 1: C})
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in step.lead)
    previous = [note for note in step.lead if note.bar == 0 and abs(note.beat - 2.0) < 1e-6 and note.duration_beats >= 0.5]
    arrived = [note for note in step.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(previous) == 1 and previous[0].midi == 71 and previous[0].slur_start
    assert len(arrived) == 1 and arrived[0].midi == 72 and arrived[0].slur_stop

    running = _two_bars([67] * 8 + [74] * 8, (_joined(0, [67] * 8 + [74] * 8),), {0: G, 1: G})
    run = sorted(
        (note for note in running.lead if note.midi is not None and note.bar == 0 and note.duration_beats == 0.25),
        key=lambda note: note.beat,
    )
    assert [round(note.beat, 2) for note in run] == [3.25, 3.5, 3.75]
    assert all((note.velocity or 0) <= 64 for note in run)
    assert run[0].slur_start and not any(note.slur_start for note in run[1:])
    apex = [note for note in running.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(apex) == 1 and apex[0].midi == 74 and apex[0].slur_stop
    assert running.scale_eighths == ()
    for beat in (3.25, 3.5, 3.75):
        assert not any(_covers_beat(note, 0, beat, 0.25) for note in running.support)
    assert_playable(running, profiles="torroba")

    held = _two_bars(
        [72] * 8 + [64] * 8,
        (_joined(0, [72] * 8), _joined(8, [64] * 8)),
        {0: C, 1: C},
        character="calm",
        character_at=("calm", "rally"),
    )
    grace = [note for note in held.lead if note.midi is not None and note.duration_beats == 0.25]
    assert [(note.bar, round(note.beat, 2)) for note in grace] == [(0, 3.75)]
    assert grace[0].slur_start
    sung = [note for note in held.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(sung) == 1 and sung[0].midi == 64 and sung[0].slur_stop
    for note in held.lead:
        if note.bar != 0 or note.duration_beats == 0.25 or note.midi is None:
            continue
        assert note.beat + note.duration_beats <= 3.75 + 1e-6
    assert_playable(held, profiles="torroba")

    dance = _two_bars([72] * 16, (_joined(0, [72] * 16),), {0: C, 1: C}, character="volatile")
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in dance.lead)

    # Castillo holds the downbeat. The unsung close at eighth 4 must not decide the ornament.
    step_line = [72] * 4 + [60] * 4 + [71] * 8
    held_step = _two_bars(
        step_line,
        (_joined(0, step_line[:8]), _joined(8, step_line[8:])),
        {0: C, 1: G},
        character="calm",
        character_at=("calm", "rally"),
    )
    held_price = [note for note in held_step.lead if note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None]
    assert len(held_price) == 1 and held_price[0].midi == step_line[0] == 72
    assert held_price[0].slur_start
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in held_step.lead)
    step_arrival = [note for note in held_step.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(step_arrival) == 1 and step_arrival[0].midi == 71 and step_arrival[0].slur_stop

    leap_line = [60] * 4 + [71] * 4 + [72] * 8
    held_leap = _two_bars(
        leap_line,
        (_joined(0, leap_line[:8]), _joined(8, leap_line[8:])),
        {0: CMAJ7, 1: C},
        character="calm",
        character_at=("calm", "rally"),
    )
    sounded = [note for note in held_leap.lead if note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None]
    assert len(sounded) == 1 and sounded[0].midi == leap_line[0] == 60
    leap_pickup = [note for note in held_leap.lead if note.midi is not None and note.duration_beats == 0.25]
    assert [(note.bar, round(note.beat, 2)) for note in leap_pickup] == [(0, 3.75)]
    assert leap_pickup[0].slur_start
    leap_arrival = [note for note in held_leap.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(leap_arrival) == 1 and leap_arrival[0].midi == 72 and leap_arrival[0].slur_stop
