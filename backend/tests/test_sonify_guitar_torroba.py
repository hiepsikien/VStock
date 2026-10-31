"""Torroba: Andalucian harmony, Ab on G, Picardy, and the four guitar patterns."""

from __future__ import annotations

from dataclasses import replace
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
    _MICRO,
    _apex_eighths,
    _fallback_body_pattern,
    _note_velocity,
    _owning_pattern,
    _select_body,
    _shape_dynamics,
    assert_playable,
    headline_id,
)
from app.sonify.guitar_torroba import (
    _HARMONICS,
    _render_torroba_bar,
    _torroba_bass,
    _torroba_contrast,
    _torroba_primary,
    render_torroba_figure,
    select_torroba_figure,
    skips_bar_extra,
    torroba_figure_plan,
    torroba_scale_step,
)
from app.sonify.guitar_wave import _is_target, profile_for
from app.sonify.harmony import BACH, TORROBA, TorrobaDialect, dialect_for
from app.sonify.humanize import _clamp_guitar
from app.sonify.model import HarmonyEvent, NoteEvent, Phrase, Run, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.phrasing import MIN_RISE, quantize_strong_beats, swell
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
    assert TORROBA.transition(BF, CM, "minor") == 0.40
    assert TORROBA.transition(AF, BF, "minor") == 0.36
    assert TORROBA.transition(FM, BF, "minor") == 0.34
    assert TORROBA.transition(BF, AF, "minor") > TORROBA.transition(BF, CM, "minor")
    assert TORROBA.transition(FM, BF, "minor") > TORROBA.transition(FM, G, "minor")
    assert TORROBA.transition(G7, FM, "minor") == 0.0
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


def test_minor_path_can_turn_back_to_the_tonic_on_bb() -> None:
    scale = _scale()

    def bar(downbeat: int, middle: int) -> list[int]:
        return [downbeat] * 4 + [middle] * 4

    # Strong beats of the outer bars are C and G, the tonic. The middle bar is Bb and F.
    bars = [
        bar(60, 67),
        bar(70, 65),
        bar(60, 67),
    ]
    spec = FormSpec(
        bars=3,
        bpm=96,
        sections=(FormSection(0, 3, "phrase", 0),),
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
    assert [chord.name for chord in path] == ["Cm", "Bb", "Cm"]


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
    assert _torroba_contrast(scherzo, "sonatina") == "castillo"
    assert _torroba_contrast(scherzo, "castillo") == "sonatina"
    bridge = FormSection(0, 1, "phrase", 0, bridge=True)
    unframed = _ctx(
        melody=[64] * 6,
        phrase=_joined(0, [64] * 6),
        kind="6/8",
        epb=6,
        strong=(0, 3),
        character="rally",
        bar_beats=3,
    )
    assert _select_body(unframed, unframed.phrases[0], first_body=True, previous=[], section=None) == "sonatina"
    assert _select_body(unframed, unframed.phrases[0], first_body=True, previous=[], section=bridge) == "castillo"
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


def test_castillo_and_sonatina_share_one_extra_per_bar() -> None:
    rising = Phrase(0, 40, (Run(0, 32, 72), Run(32, 8, 79)))
    assert rising.rise > MIN_RISE
    castillo_ctx = _ctx(melody=[72] * 32 + [79] * 8, phrase=rising, bars=5, character="calm", chord=C)
    assert castillo_ctx.band(2) == "mf"
    with compose_meter(METER_44):
        lead, support, low = _render_torroba_bar(castillo_ctx, 2, rising, "castillo")
    assert any(note.duration_beats >= 2 and note.midi == 72 for note in lead)
    later = [note for note in support if abs(note.beat - 3.0) < 1e-6]
    assert later
    shaped_lead, shaped_support, _shaped_low = _shape_dynamics(
        castillo_ctx, list(lead), list(support), list(low), set(), ["castillo"]
    )
    lead_extra = shaped_lead[0].velocity - lead[0].velocity
    assert lead_extra == round(4 * swell(rising, 2 * castillo_ctx.epb))
    assert lead_extra != round(4 * swell(rising, 2 * castillo_ctx.epb + 6))
    for before, after in zip(support, shaped_support):
        assert after.velocity - before.velocity == lead_extra

    line = [60] * 12 + [72] * 4
    run_phrase = Phrase(0, 16, (Run(0, 12, 60), Run(12, 4, 72)))
    assert run_phrase.rise > MIN_RISE
    sonatina_ctx = _ctx(melody=line, phrase=run_phrase, bars=2, character="rally", chord=C)
    assert sonatina_ctx.band(1) == "mf"
    with compose_meter(METER_44):
        run_lead, run_support, run_low = _render_torroba_bar(sonatina_ctx, 1, run_phrase, "sonatina")
    written_run = sorted(
        (note for note in run_lead if note.duration_beats == 0.25 and note.midi is not None),
        key=lambda note: note.beat,
    )
    assert [note.velocity for note in written_run] == [56, 60, 64]
    shaped_run_lead, _shaped_support, _shaped_low = _shape_dynamics(
        sonatina_ctx, list(run_lead), list(run_support), list(run_low), set(), ["sonatina"]
    )
    heard = sorted(
        (note for note in shaped_run_lead if note.duration_beats == 0.25 and note.midi is not None),
        key=lambda note: note.beat,
    )
    extra = heard[0].velocity - 56
    assert extra == round(4 * swell(run_phrase, sonatina_ctx.epb))
    assert [note.velocity for note in heard] == [56 + extra, 60 + extra, 64 + extra]
    assert heard[1].velocity - heard[0].velocity == 4
    assert heard[2].velocity - heard[1].velocity == 4


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
    # Held so the one-bar line stays on the base grid. A close of this length is type 3.
    rise_phrase = _joined(0, rising, held=True)
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


def _with_phrases(ctx, phrases, kind_at=None):
    ctx.phrases = tuple(phrases)
    if kind_at:
        ctx.kind_at.update(kind_at)
    return ctx


def _gap_beats(support) -> set[float]:
    return {round(note.beat, 2) for note in support if note.midi is not None and round(note.beat, 2) != 0.0}


def _at(notes, beat: float):
    found = [note for note in notes if note.midi is not None and abs(note.beat - beat) < 1e-6]
    assert len(found) == 1
    return found[0]


def test_breath_harmonics_and_fandanguillo_grids() -> None:
    full_gaps = {0.5, 1.5, 2.5, 3.5}
    thin_gaps = {0.5, 2.5}

    # A close on bar 1 (1 % 4 == 1) thins that bar. Bar 0, still inside the phrase, stays full.
    closing = _joined(0, [72] * 16)
    closing_ctx = _with_phrases(
        _ctx(melody=[72] * 16, phrase=closing, character="volatile", bars=2, chord=C),
        (closing,),
    )
    with compose_meter(METER_44):
        _lead0, open_support, _low0 = _render_torroba_bar(closing_ctx, 0, closing, "fandanguillo")
        lead1, closed_support, _low1 = _render_torroba_bar(closing_ctx, 1, closing, "fandanguillo")
    assert _gap_beats(open_support) == full_gaps
    assert _gap_beats(closed_support) == thin_gaps
    assert len([note for note in lead1 if note.midi is not None]) == len(
        [note for note in _lead0 if note.midi is not None]
    )
    assert all(note.velocity == 50 for note in closed_support if note.midi is not None)

    # Bar 3 is the old modulo breath. Mid-phrase it stays as full as bar 0.
    longer = _joined(0, [72] * 40)
    longer_ctx = _with_phrases(
        _ctx(melody=[72] * 40, phrase=longer, character="volatile", bars=5, chord=C),
        (longer,),
    )
    with compose_meter(METER_44):
        _lead, early, _low = _render_torroba_bar(longer_ctx, 0, longer, "fandanguillo")
        _lead, middle, _low = _render_torroba_bar(longer_ctx, 3, longer, "fandanguillo")
    assert 3 % 4 == 3
    assert _gap_beats(middle) == _gap_beats(early) == full_gaps

    # A phrase that ends at eighth 6 thins only its own gaps. Offset 7 belongs to the next phrase.
    head = _joined(0, [72] * 6)
    tail = _joined(6, [72] * 10)
    split_ctx = _with_phrases(
        _ctx(melody=[72] * 16, phrase=head, character="volatile", bars=2, chord=C),
        (head, tail),
    )
    with compose_meter(METER_44):
        _lead, split_support, _low = _render_torroba_bar(split_ctx, 0, head, "fandanguillo")
    assert _gap_beats(split_support) == {0.5, 2.5, 3.5}
    assert _at(split_support, 0.5).velocity == 50
    assert _at(split_support, 2.5).velocity == 50
    assert _at(split_support, 3.5).velocity == 56

    # Castillo 4/4 inners sit at 2 and 6. A close through the bar keeps every other one, on `p`.
    # The held price is one note from the downbeat; its bass is `p` only because the close
    # covers the last eighth.
    covered = _joined(0, [72] * 8)
    covered_ctx = _with_phrases(
        _ctx(melody=[72] * 8, phrase=covered, character="calm", chord=C),
        (covered,),
    )
    with compose_meter(METER_44):
        covered_lead, covered_support, covered_low = _render_torroba_bar(covered_ctx, 0, covered, "castillo")
    assert {round(note.beat, 2) for note in covered_support} == {1.0}
    assert covered_support[0].velocity == 50
    assert covered_low[0].velocity == 54
    assert covered_lead[0].duration_beats >= 2

    # Ending at eighth 4 leaves only offset 2. That one-offset tail is dropped; offset 6 stays,
    # and the bar bed stays the printed band because the close does not reach the last eighth.
    ended = _joined(0, [72] * 4)
    follows = _joined(4, [72] * 12)
    partial_ctx = _with_phrases(
        _ctx(melody=[72] * 16, phrase=ended, character="calm", bars=2, chord=C),
        (ended, follows),
    )
    with compose_meter(METER_44):
        partial_lead, partial_support, partial_low = _render_torroba_bar(partial_ctx, 0, ended, "castillo")
    assert {round(note.beat, 2) for note in partial_support} == {3.0}
    assert partial_support[0].velocity == 56
    assert partial_low[0].velocity == 60
    assert partial_lead[0].velocity == covered_lead[0].velocity

    # The downbeat owner does not close. The phrase that starts at eighth 4 does, and it
    # holds only offset 6, so that one inner note is dropped.
    owner = Phrase(0, 4, (Run(0, 2, 72), Run(2, 2, 74)))
    later = _joined(4, [72] * 4)
    assert not owner.closes and later.closes
    scanned_ctx = _with_phrases(
        _ctx(melody=[72, 72, 74, 74, 72, 72, 72, 72], phrase=owner, character="calm", chord=C),
        (owner, later),
    )
    with compose_meter(METER_44):
        _lead, scanned, _low = _render_torroba_bar(scanned_ctx, 0, owner, "castillo")
    assert {round(note.beat, 2) for note in scanned} == {1.0}

    tied = _joined(0, [72] * 32, held=True)
    tied_ctx = _with_phrases(
        _ctx(melody=[72] * 32, phrase=tied, character="volatile", bars=4, chord=C),
        (tied,),
    )
    released = _joined(0, [72] * 32)
    released_ctx = _with_phrases(
        _ctx(melody=[72] * 32, phrase=released, character="volatile", bars=4, chord=C),
        (released,),
    )
    with compose_meter(METER_44):
        _lead, tied_support, _low = _render_torroba_bar(tied_ctx, 3, tied, "fandanguillo")
        _lead, released_support, _low = _render_torroba_bar(released_ctx, 3, released, "fandanguillo")
    assert tied.held_over and not tied.closes
    assert _gap_beats(tied_support) == full_gaps
    assert _gap_beats(released_support) == thin_gaps

    pedal = _joined(0, [72] * 8)
    for kind in ("intro", "warmup"):
        pedal_ctx = _with_phrases(
            _ctx(melody=[72] * 8, phrase=pedal, character="volatile", chord=C),
            (pedal,),
            {0: kind},
        )
        with compose_meter(METER_44):
            _lead, pedal_support, _low = _render_torroba_bar(pedal_ctx, 0, pedal, "fandanguillo")
        assert _gap_beats(pedal_support) == full_gaps

    # Two sonatina phrases. The earlier one closes, so the next strong beat is not slurred
    # and grows no pickup. One phrase that closes only at its own end still slurs.
    step_left = _joined(0, [72] * 4)
    step_right = _joined(4, [74] * 4)
    step_ctx = _with_phrases(
        _ctx(melody=[72] * 4 + [74] * 4, phrase=step_left, character="rally", chord=C),
        (step_left, step_right),
    )
    same = _joined(0, [72] * 4 + [74] * 4)
    same_ctx = _ctx(melody=[72] * 4 + [74] * 4, phrase=same, character="rally", chord=C)
    leap_left = _joined(0, [74] * 4)
    leap_right = _joined(4, [67] * 4)
    leap_ctx = _with_phrases(
        _ctx(melody=[74] * 4 + [67] * 4, phrase=leap_left, character="rally", chord=G),
        (leap_left, leap_right),
    )
    with compose_meter(METER_44):
        stepped, _support, _low = _render_torroba_bar(step_ctx, 0, step_left, "sonatina")
        joined, _support, _low = _render_torroba_bar(same_ctx, 0, same, "sonatina")
        leaped, _support, _low = _render_torroba_bar(leap_ctx, 0, leap_left, "sonatina")
    assert step_left.closes and not any(note.slur_start or note.slur_stop for note in stepped)
    assert not any(note.duration_beats == 0.25 for note in stepped)
    assert any(note.slur_start for note in joined) and any(note.slur_stop for note in joined)
    assert not any(note.duration_beats == 0.25 for note in leaped)
    assert not any(note.slur_start or note.slur_stop for note in leaped)

    crossed = _two_bars(
        [74] * 8 + [67] * 8,
        (_joined(0, [74] * 8), _joined(8, [67] * 8)),
        {0: G, 1: G},
        character="rally",
    )
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in crossed.lead)
    assert not any(note.slur_start or note.slur_stop for note in crossed.lead if note.midi is not None)

    # Castillo still graces into sonatina. held_step slurs the sounding 72, not the unsung 60.
    for pitches, chords in (
        ([72] * 8 + [64] * 8, {0: C, 1: C}),
        ([60] * 4 + [71] * 4 + [72] * 8, {0: CMAJ7, 1: C}),
    ):
        graced = _two_bars(
            pitches,
            (_joined(0, pitches[:8]), _joined(8, pitches[8:], held=True)),
            chords,
            character="calm",
            character_at=("calm", "rally"),
        )
        grace = [note for note in graced.lead if note.midi is not None and note.duration_beats == 0.25]
        assert [(note.bar, round(note.beat, 2)) for note in grace] == [(0, 3.75)]
    held_step = _two_bars(
        [72] * 4 + [60] * 4 + [71] * 8,
        (_joined(0, [72] * 4 + [60] * 4), _joined(8, [71] * 8, held=True)),
        {0: C, 1: G},
        character="calm",
        character_at=("calm", "rally"),
    )
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in held_step.lead)
    assert _strong(held_step, 0, 0.0).slur_start
    assert _strong(held_step, 1, 0.0).slur_stop

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
    leap = _two_bars([74] * 8 + [67] * 8, (_joined(0, [74] * 8 + [67] * 8, held=True),), {0: G, 1: G})
    pickup = [note for note in leap.lead if note.midi is not None and note.duration_beats == 0.25]
    assert [(note.bar, round(note.beat, 2)) for note in pickup] == [(0, 3.75)]
    assert pickup[0].slur_start and pickup[0].voice == 1 and (pickup[0].velocity or 0) <= 64
    arrival = [note for note in leap.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(arrival) == 1 and arrival[0].midi == 67 and arrival[0].slur_stop
    assert not any(_covers_beat(note, 0, 3.75, 0.25) for note in leap.support)
    assert all(note.bar >= 0 for note in leap.lead)
    assert_playable(leap, profiles="torroba")

    step = _two_bars([71] * 8 + [72] * 8, (_joined(0, [71] * 8 + [72] * 8, held=True),), {0: G, 1: C})
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in step.lead)
    previous = [note for note in step.lead if note.bar == 0 and abs(note.beat - 2.0) < 1e-6 and note.duration_beats >= 0.5]
    arrived = [note for note in step.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(previous) == 1 and previous[0].midi == 71 and previous[0].slur_start
    assert len(arrived) == 1 and arrived[0].midi == 72 and arrived[0].slur_stop

    running = _two_bars([67] * 8 + [74] * 8, (_joined(0, [67] * 8 + [74] * 8, held=True),), {0: G, 1: G})
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
        (_joined(0, [72] * 8), _joined(8, [64] * 8, held=True)),
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
        (_joined(0, step_line[:8]), _joined(8, step_line[8:], held=True)),
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
        (_joined(0, leap_line[:8]), _joined(8, leap_line[8:], held=True)),
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


def _strong(score_or_notes, bar: int, beat: float):
    notes = score_or_notes.lead if hasattr(score_or_notes, "lead") else score_or_notes
    found = [
        note
        for note in notes
        if note.bar == bar and abs(note.beat - beat) < 1e-6 and (note.duration_beats or 0) >= 0.5 and note.midi is not None
    ]
    assert len(found) == 1
    return found[0]


def test_sonatina_slur_is_one_arch_and_skips_a_repeated_note() -> None:
    # G hears Ab, so these strong beats stay a semitone apart after quantization.
    line = [67] * 4 + [68] * 4 + [67] * 4 + [68] * 4
    score = _render(
        line,
        (_joined(0, line, held=True),),
        chords={0: G, 1: G},
        kinds={0: "phrase", 1: "phrase"},
        mode="minor",
        character="rally",
    )
    assert not any(note.slur_start and note.slur_stop for note in score.lead)
    assert _strong(score, 0, 0.0).slur_start and not _strong(score, 0, 0.0).slur_stop
    assert not _strong(score, 0, 2.0).slur_start and not _strong(score, 0, 2.0).slur_stop
    assert not _strong(score, 1, 0.0).slur_start and not _strong(score, 1, 0.0).slur_stop
    assert _strong(score, 1, 2.0).slur_stop and not _strong(score, 1, 2.0).slur_start
    xml = score_to_musicxml(score)
    slurs = [mark for mark in xml.split("<slur ") if mark.startswith("type=")]
    assert [mark.split('"', 2)[1] for mark in slurs] == ["start", "stop"]

    same = _two_bars([72] * 16, (_joined(0, [72] * 16, held=True),), {0: C, 1: C}, character="rally")
    assert not any(note.slur_start or note.slur_stop for note in same.lead if note.midi is not None)

    stepped = [72] * 8 + [68] * 4 + [67] * 4
    joined = _render(
        stepped,
        (_joined(0, stepped, held=True),),
        chords={0: C, 1: G},
        kinds={0: "phrase", 1: "phrase"},
        mode="minor",
        character="rally",
    )
    pickup = [note for note in joined.lead if note.duration_beats == 0.25 and note.midi is not None]
    assert len(pickup) == 1 and pickup[0].slur_start and not pickup[0].slur_stop
    assert not _strong(joined, 1, 0.0).slur_start and not _strong(joined, 1, 0.0).slur_stop
    assert _strong(joined, 1, 2.0).slur_stop and not _strong(joined, 1, 2.0).slur_start
    assert not any(note.slur_start and note.slur_stop for note in joined.lead)


def test_sonatina_pickup_rests_only_its_sixteenth() -> None:
    leap = [74] * 4 + [67] * 4
    phrase = _joined(0, leap)
    ctx = _ctx(melody=leap, phrase=phrase, character="rally", chord=G)
    with compose_meter(METER_44):
        _lead, support, _low = _render_torroba_bar(ctx, 0, phrase, "sonatina")
    assert any(abs(note.beat - 1.5) < 1e-6 and abs((note.duration_beats or 0) - 0.25) < 1e-6 for note in support)
    assert not any(_covers_beat(note, 0, 1.75, 0.25) for note in support)


def test_framed_scherzo_renders_danza() -> None:
    pitches = [72] * 24
    sections = (
        FormSection(0, 1, "intro", 0),
        FormSection(1, 3, "phrase", 0),
        FormSection(3, 4, "outro", 0),
    )
    score = _render(
        pitches,
        (
            _joined(0, pitches[:6], held=True),
            _joined(6, pitches[6:18]),
            _joined(18, pitches[18:]),
        ),
        chords={bar: C for bar in range(4)},
        kinds={0: "intro", 1: "phrase", 2: "phrase", 3: "outro"},
        mode="major",
        character="calm",
        bpm=96,
        meter=METER_68,
        sections=sections,
    )
    body = [note for note in score.lead if note.bar == 1 and note.staccato and note.midi is not None]
    assert {round(note.beat, 2) for note in body} == {0.0, 1.5}
    assert_playable(score, profiles="torroba")


_FIGURE_METERS = {
    "4/4": (METER_44, 8, (0, 4), 4.0),
    "3/4": (METER_34, 6, (0,), 3.0),
    "6/8": (METER_68, 6, (0, 3), 3.0),
}
_FIGURE_BARS = {1: 1, 2: 2, 3: 3, 4: 2, 5: 4, 6: 4, 7: 5, 8: 2}
_FIGURE_PATTERN = {
    1: "sonatina",
    2: "sonatina",
    3: "sonatina",
    4: "sonatina",
    5: "fandanguillo",
    6: "danza",
    7: "castillo",
    8: "castillo",
}


def _span(start: int, eighths: int, low: int, high: int, *, held: bool = False, tail: int = 1) -> Phrase:
    body = [low] * (eighths - tail) + [high] * tail
    return _joined(start, body, held=held)


def _many(
    phrases: tuple[Phrase, ...],
    *,
    kind: str = "4/4",
    bpm: int = 96,
    chord=C,
    chords: dict | None = None,
    mode: str = "major",
    melody: list[int] | None = None,
) -> _Ctx:
    _meter, epb, strong, bar_beats = _FIGURE_METERS[kind]
    end = max(phrase.end for phrase in phrases)
    pitches = list(melody) if melody is not None else [72] * end
    bars = max(1, (len(pitches) + epb - 1) // epb)
    if len(pitches) < bars * epb:
        pitches = [*pitches, *([pitches[-1]] * (bars * epb - len(pitches)))]
    ctx = _ctx(
        melody=pitches,
        phrase=phrases[0],
        kind=kind,
        epb=epb,
        strong=strong,
        bpm=bpm,
        bars=bars,
        chord=chord,
        mode=mode,
        bar_beats=bar_beats,
    )
    chord_at = dict(ctx.chord_at)
    if chords:
        chord_at.update(chords)
    return replace(
        ctx,
        phrases=tuple(phrases),
        chord_at=chord_at,
        kind_at={bar: "phrase" for bar in range(bars + 1)},
        band_at={bar: "mf" for bar in range(bars + 1)},
        regime_at={bar: "sideway" for bar in range(bars + 1)},
    )


def _used(plan: dict, phrase: Phrase, epb: int) -> dict[int, int]:
    """Figure ids on bars whose downbeat this phrase holds."""
    first = (phrase.start + epb - 1) // epb
    if phrase.end <= first * epb:
        return {}
    last = (phrase.end - 1) // epb
    if last < first:
        return {}
    return {bar: plan[bar][0] for bar in range(first, last + 1) if bar in plan}


def _flat_figure(kind: str, figure: int, *, midi: int = 72, chord=C, held: bool = True, bpm: int = 72):
    count = _FIGURE_BARS[figure]
    pattern = _FIGURE_PATTERN[figure]
    meter, epb, _strong, _beats = _FIGURE_METERS[kind]
    phrase = _joined(0, [midi] * (count * epb), held=held)
    ctx = _many((phrase,), kind=kind, bpm=bpm, chord=chord, melody=[midi] * (count * epb))
    parts = []
    with compose_meter(meter):
        for index in range(count):
            parts.append(
                render_torroba_figure(
                    ctx,
                    index,
                    phrase,
                    pattern,
                    figure,
                    index=index,
                    count=count,
                    next_figure=figure if index + 1 < count else None,
                )
            )
    return ctx, phrase, parts


def _figure_score(ctx, parts, bars: int, chord=C) -> Score:
    lead, support, low = [], [], []
    for part_lead, part_support, part_low in parts:
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)
    return Score(
        title="Torroba",
        bpm=ctx.bpm,
        bars=bars,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=tuple(ChordSlot(bar, 1, chord, "sideway", "phrase") for bar in range(bars)),
        high=(),
        lead=tuple(lead),
        support=tuple(support),
        comp=(),
        low=tuple(low),
        dynamics=(),
        harmonies=tuple(HarmonyEvent(bar, chord) for bar in range(bars)),
        liquidity=tuple("mf" for _ in range(bars)),
        phrases=ctx.phrases,
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="torroba",
        bar_beats=ctx.bar_beats,
        beats=3 if ctx.bar_beats == 3 else 4,
        beat_type=8 if ctx.kind == "6/8" else 4,
    )


def _vels(notes, bar: int | None = None) -> list[tuple[float, int]]:
    chosen = [note for note in notes if note.midi is not None and (bar is None or note.bar == bar)]
    return [(round(note.beat, 2), note.velocity) for note in sorted(chosen, key=lambda note: (note.bar, note.beat))]


def test_rise_below_three_suppresses_type_2_and_type_5() -> None:
    quiet = (
        _span(0, 32, 72, 72, held=True, tail=1),
        _span(32, 32, 72, 72, held=True, tail=1),
        _span(64, 32, 70, 72, held=True, tail=1),
    )
    assert quiet[2].rise == 2 and quiet[2].rise < MIN_RISE
    plan = torroba_figure_plan(_many(quiet), ["sonatina", "sonatina", "sonatina"])
    assert _used(plan, quiet[2], 8) == {}
    risen = (
        quiet[0],
        quiet[1],
        _span(64, 32, 67, 72, held=True, tail=1),
    )
    assert risen[2].rise >= MIN_RISE
    sung = torroba_figure_plan(_many(risen), ["sonatina", "sonatina", "sonatina"])
    assert set(_used(sung, risen[2], 8).values()) == {2}

    short = _span(0, 48, 70, 72, held=True, tail=1)
    assert short.rise < MIN_RISE
    denied = torroba_figure_plan(_many((short,)), ["fandanguillo"])
    assert denied == {}
    allowed = _span(0, 48, 67, 72, held=True, tail=1)
    assert allowed.rise >= MIN_RISE
    granted = torroba_figure_plan(_many((allowed,)), ["fandanguillo"])
    assert set(granted.values()) == {(5, 0, 4), (5, 1, 4), (5, 2, 4), (5, 3, 4)}
    # Not enough room for type 5 does not borrow type 2.
    cramped = _span(0, 24, 60, 72, held=True, tail=1)
    assert cramped.rise >= MIN_RISE
    assert torroba_figure_plan(_many((cramped,)), ["fandanguillo"]) == {}
    short_sonatina = _span(0, 16, 72, 72, held=True, tail=1)
    assert torroba_figure_plan(_many((short_sonatina,)), ["sonatina"]) == {}


def test_castillo_figure_gate_follows_tempo_and_length() -> None:
    slow = (
        _span(0, 40, 72, 72, tail=8),
        _span(40, 32, 72, 72, tail=8),
        _span(72, 32, 72, 72, tail=8),
    )
    plan = torroba_figure_plan(_many(slow, bpm=72), ["castillo", "castillo", "castillo"])
    assert _used(plan, slow[0], 8) == {bar: 7 for bar in range(5)}
    assert _used(plan, slow[1], 8) == {}
    assert _used(plan, slow[2], 8) == {9: 8, 10: 8}
    sustain = _render_torroba_bar(_many((slow[1],), bpm=72), 0, slow[1], "castillo")[0]
    sounded = [note for note in sustain if note.midi is not None]
    assert len(sounded) == 1 and sounded[0].duration_beats >= 4

    short = (_span(0, 24, 72, 72, tail=8),)
    cut = torroba_figure_plan(_many(short, bpm=72), ["castillo"])
    assert set(cut) == {0, 1}
    assert set(cut.values()) == {(8, 0, 2), (8, 1, 2)}

    fast = torroba_figure_plan(_many(slow, bpm=96), ["castillo", "castillo", "castillo"])
    assert fast == {}


def test_a_shared_bar_stays_with_the_phrase_that_holds_its_downbeat() -> None:
    """A cut inside a bar does not give that bar to the phrase that starts there."""
    opening = _span(0, 10, 60, 72, tail=4)
    following = _span(10, 38, 72, 72, tail=8)
    assert opening.closes and following.end == 48
    plan = torroba_figure_plan(_many((opening, following), bpm=72), ["sonatina", "castillo"])
    assert _used(plan, opening, 8) == {0: 3, 1: 3}
    assert _used(plan, following, 8) == {2: 8, 3: 8}
    assert 7 not in {figure for figure, _index, _count in plan.values()}


def test_sonatina_close_is_type_3_and_not_type_4() -> None:
    phrases = (
        _span(0, 48, 72, 73, held=True, tail=1),
        _span(48, 32, 60, 65, held=True, tail=1),
        _span(80, 32, 60, 65, held=True, tail=1),
        _span(112, 40, 72, 72, held=True, tail=1),
        _span(152, 32, 60, 64, held=True, tail=1),
        _span(184, 32, 70, 72, tail=4),
    )
    assert phrases[0].rise == 1 and not phrases[0].closes
    assert phrases[2].rise == 5 and phrases[5].closes and phrases[5].rise == 2
    plan = torroba_figure_plan(_many(phrases), ["sonatina"] * 6)
    assert _used(plan, phrases[0], 8) == {0: 4, 1: 4}
    assert _used(plan, phrases[1], 8) == {}
    assert _used(plan, phrases[2], 8) == {11: 2, 12: 2}
    assert _used(plan, phrases[3], 8) == {}
    assert _used(plan, phrases[4], 8) == {20: 1}
    assert _used(plan, phrases[5], 8) == {24: 3, 25: 3, 26: 3}
    assert 4 not in _used(plan, phrases[5], 8).values()


def test_fandanguillo_phrase_holds_one_figure() -> None:
    phrases = (
        _span(0, 48, 60, 65, held=True, tail=1),
        _span(48, 32, 60, 65, held=True, tail=1),
        _span(80, 40, 60, 65, held=True, tail=1),
    )
    plan = torroba_figure_plan(_many(phrases), ["fandanguillo"] * 3)
    assert set(_used(plan, phrases[0], 8).values()) == {5}
    assert _used(plan, phrases[1], 8) == {}
    assert set(_used(plan, phrases[2], 8).values()) == {2}
    for phrase in phrases:
        assert len(set(_used(plan, phrase, 8).values())) <= 1

    closing = _span(0, 48, 60, 65, tail=8)
    assert closing.closes and closing.rise >= MIN_RISE
    closed = torroba_figure_plan(_many((closing,)), ["fandanguillo"])
    assert _used(closed, closing, 8) == {0: 5, 1: 5, 2: 5, 3: 5}


def test_adjacent_phrase_does_not_repeat_a_figure() -> None:
    first = _span(0, 32, 72, 72, tail=8)
    second = _span(32, 32, 72, 72, tail=8)
    assert first.closes and second.closes
    plan = torroba_figure_plan(_many((first, second)), ["sonatina", "sonatina"])
    assert set(_used(plan, first, 8).values()) == {3}
    assert _used(plan, second, 8) == {}
    again = select_torroba_figure(
        _many((second,)), second, "sonatina", n=None, k=None, previous=3
    )
    assert again == (None, ())


def test_danza_on_four_four_does_not_call_type_6() -> None:
    phrase = _span(0, 32, 72, 72, held=True, tail=1)
    assert torroba_figure_plan(_many((phrase,), kind="4/4"), ["danza"]) == {}
    for kind, epb in (("3/4", 6), ("6/8", 6)):
        dancing = _span(0, epb * 4, 72, 72, held=True, tail=1)
        plan = torroba_figure_plan(_many((dancing,), kind=kind), ["danza"])
        assert set(plan) == {0, 1, 2, 3}
        assert set(value[0] for value in plan.values()) == {6}
        closed = _span(0, epb * 4, 72, 72, tail=epb)
        assert closed.closes
        assert torroba_figure_plan(_many((closed,), kind=kind), ["danza"]) == {}


def test_type_1_bass_rings_only_into_another_type_1_bar() -> None:
    phrase = _joined(0, [72] * 16, held=True)
    ctx = _many((phrase,), melody=[72] * 16)
    with compose_meter(METER_44):
        _lead, _support, cut = render_torroba_figure(
            ctx, 0, phrase, "sonatina", 1, index=0, count=1, next_figure=None
        )
        _lead, _support, rings = render_torroba_figure(
            ctx, 0, phrase, "sonatina", 1, index=0, count=1, next_figure=1
        )
    cut_bass = max(cut, key=lambda note: note.beat)
    ring_bass = max(rings, key=lambda note: note.beat)
    assert cut_bass.beat == pytest.approx(2.25)
    assert cut_bass.duration_beats == pytest.approx(1.75)
    assert ring_bass.duration_beats == pytest.approx(2.5)
    changed = replace(ctx, chord_at={0: C, 1: G})
    with compose_meter(METER_44):
        _lead, _support, released = render_torroba_figure(
            changed, 0, phrase, "sonatina", 1, index=0, count=1, next_figure=1
        )
    assert max(released, key=lambda note: note.beat).duration_beats == pytest.approx(1.75)


def test_type_3_harmonic_is_48_only_on_a_node() -> None:
    for midi, velocity in ((67, 48), (62, 48), (72, 64), (60, 64)):
        ctx, phrase, parts = _flat_figure("4/4", 3, midi=midi)
        sustain = [note for note in parts[2][0] if note.midi is not None]
        assert len(sustain) == 1
        assert sustain[0].velocity == velocity
        assert sustain[0].accent is (velocity != 48)
        assert (midi in _HARMONICS) is (velocity == 48)
        bass = [note for note in parts[2][2] if note.midi is not None]
        assert len(bass) == 1 and bass[0].velocity == 60 - _MICRO


def test_type_7_mordent_and_bar_5_bass_keep_the_written_steps() -> None:
    expected = {
        "4/4": [58, 58, 58, 58, 56, 56, 58],
        "3/4": [58, 58, 56, 56, 58],
        "6/8": [58, 58, 56, 56, 58],
    }
    for kind, velocities in expected.items():
        ctx, _phrase, parts = _flat_figure(kind, 7)
        for lead, support, low in parts:
            assert not any(abs(note.duration_beats * 6 - 1) < 1e-3 for note in (*lead, *support, *low))
        mordent = sorted(
            (note for note in parts[0][0] if note.duration_beats == pytest.approx(0.25)),
            key=lambda note: note.beat,
        )
        assert [round(note.beat, 2) for note in mordent] == [1.5, 1.75]
        assert mordent[0].slur_start and mordent[1].slur_stop
        assert [note.velocity for note in mordent] == [64 - 2 * _MICRO, 64 - _MICRO]
        half = [note for note in parts[0][0] if note.beat == pytest.approx(2.0)]
        assert len(half) == 1 and half[0].duration_beats == pytest.approx(2.0 if kind == "4/4" else 1.0)
        assert half[0].velocity == 64
        bass = [note for note in parts[4][2] if note.midi is not None]
        assert [note.velocity for note in bass] == velocities
        assert all(note.duration_beats == pytest.approx(0.5) for note in bass)
        assert bass[-1].midi % 12 == C.pitches[0] % 12
        grace = [note for note in parts[2][0] if abs(note.beat - 0.5) < 0.3]
        support = [note for note in parts[2][1] if note.beat == pytest.approx(0.5)]
        assert len(grace) == 2 and all(note.duration_beats == pytest.approx(0.25) for note in grace)
        assert len(support) == 1 and support[0].duration_beats == pytest.approx(0.5)


def test_type_7_keeps_p_when_the_grace_does_not_fit() -> None:
    melody = [72] * 40
    melody[16] = 81
    melody[17] = 64
    phrase = _joined(0, melody, held=True)
    ctx = _many((phrase,), bpm=72, melody=melody)
    with compose_meter(METER_44):
        lead, _support, _low = render_torroba_figure(
            ctx, 2, phrase, "castillo", 7, index=2, count=5
        )
    odd = [note for note in lead if note.beat == pytest.approx(0.5)]
    assert len(odd) == 1
    assert odd[0].midi == 81
    assert odd[0].duration_beats == pytest.approx(0.5)
    assert not odd[0].slur_start


def test_type_7_odd_eighth_and_pickup_follow_their_own_swell() -> None:
    pitches = [60] * 30 + [72] * 10
    phrase = _joined(0, pitches, held=True)
    assert phrase.rise >= MIN_RISE and phrase.apex.start == 30
    ctx = _many((phrase,), bpm=72, melody=pitches)
    apex = _apex_eighths(ctx.phrases)
    with compose_meter(METER_44):
        second, _support, _low = render_torroba_figure(
            ctx, 1, phrase, "castillo", 7, index=1, count=5
        )
        third, _support, _low = render_torroba_figure(
            ctx, 2, phrase, "castillo", 7, index=2, count=5
        )
    downbeat = _note_velocity(8, 1, apex, phrase)
    pickup_written = _note_velocity(15, 1, apex, phrase)
    assert pickup_written != downbeat
    pickup = [note for note in second if note.beat == pytest.approx(3.5)]
    assert len(pickup) == 1 and pickup[0].velocity == pickup_written
    mordent_written = _note_velocity(11, 1, apex, phrase)
    mordent = sorted((note for note in second if 1.5 <= note.beat < 2.0), key=lambda note: note.beat)
    assert [note.velocity for note in mordent] == [mordent_written - 2 * _MICRO, mordent_written - _MICRO]
    odd_written = _note_velocity(17, 1, apex, phrase)
    assert odd_written != _note_velocity(16, 1, apex, phrase)
    grace = sorted((note for note in third if 0.5 <= note.beat < 1.0), key=lambda note: note.beat)
    assert grace and all(note.velocity == odd_written - _MICRO for note in grace)
    assert grace[-1].midi == 60


def test_type_8_bass_color_stays_under_the_ceiling_and_keeps_a_single_eighth() -> None:
    ctx, _phrase, parts = _flat_figure("4/4", 8, chord=C)
    color = [note for note in parts[0][2] if note.midi is not None]
    assert [(round(note.beat, 2), note.duration_beats) for note in color] == [
        (0.5, pytest.approx(0.5)),
        (1.0, pytest.approx(1.0)),
    ]
    for note in color:
        assert note.midi <= 52
        assert note.velocity == 60 - _MICRO
    ordinary, _phrase, plain = _flat_figure("4/4", 8, chord=G)
    for note in plain[0][2]:
        assert note.midi not in _HARMONICS
        assert note.velocity == 60 - _MICRO
        assert note.midi < 52
    for beat in (0.0, 2.0):
        attacks = [note for note in parts[1][0] if note.beat == pytest.approx(beat)]
        assert len(attacks) == 1 and attacks[0].duration_beats == pytest.approx(0.5)
    first_slur = [note.velocity for note in parts[1][0] if 0.5 <= note.beat < 2]
    assert first_slur == [62, 62, 62]
    second_slur = [note.velocity for note in parts[1][0] if note.beat >= 2.5]
    assert second_slur == [62, 62, 60]
    _ctx34, _phrase34, three = _flat_figure("3/4", 8, chord=C)
    three_lead = [note.velocity for note in three[1][0] if note.beat >= 0.5 and note.duration_beats == pytest.approx(0.5)]
    assert three_lead[:3] == [62, 62, 62]
    six = _flat_figure("6/8", 8, chord=C)[2]
    eighth_three = [note for note in six[0][0] if note.beat == pytest.approx(1.5)]
    assert len(eighth_three) == 1 and eighth_three[0].velocity == 64
    three_open = [note for note in three[0][0] if note.beat == pytest.approx(1.5)]
    assert len(three_open) == 1 and three_open[0].velocity == 62
    closing = _joined(0, [72] * 16)
    assert closing.closes and len(range(closing.start // 8, (closing.end - 1) // 8 + 1)) == 2
    close_ctx = _many((closing,), bpm=72, melody=[72] * 16)
    with compose_meter(METER_44):
        lead, support, low = render_torroba_figure(
            close_ctx, 1, closing, "castillo", 8, index=1, count=2, next_figure=None
        )
    second = [note for note in lead if note.beat >= 2]
    assert len(second) == 1 and second[0].duration_beats == pytest.approx(2.0) and second[0].voice == 1
    assert any(note.duration_beats == pytest.approx(2.0) and note.voice == 3 for note in low)
    assert_playable(_figure_score(close_ctx, [(lead, support, low)], 2), profiles="torroba")
    assert ordinary.kind == "4/4"


@pytest.mark.parametrize("kind", ["4/4", "3/4", "6/8"])
@pytest.mark.parametrize("figure", [1, 2, 3, 4, 5, 7, 8])
def test_figures_stay_playable(kind: str, figure: int) -> None:
    ctx, _phrase, parts = _flat_figure(kind, figure)
    assert_playable(_figure_score(ctx, parts, _FIGURE_BARS[figure] + 1), profiles="torroba")


@pytest.mark.parametrize("kind", ["3/4", "6/8"])
def test_type_6_stays_playable_off_four_four(kind: str) -> None:
    ctx, _phrase, parts = _flat_figure(kind, 6)
    opened = parts[2]
    leads = sorted((note for note in opened[0] if note.midi is not None), key=lambda note: note.beat)
    assert [round(note.beat, 2) for note in leads[:4]] == [0.25, 0.5, 0.75, 1.0]
    assert [note.velocity for note in leads[:3]] == [68 - 2 * _MICRO, 68 - 2 * _MICRO, 68 - _MICRO]
    assert leads[3].velocity == 68 and leads[3].duration_beats == pytest.approx(5.0)
    assert not any(note.beat == pytest.approx(0.0) for note in opened[0])
    bass = sorted(opened[2], key=lambda note: note.beat)
    assert [round(note.beat, 2) for note in bass] == [0.0, 1.5]
    assert bass[0].duration_beats == pytest.approx(0.25) and bass[0].staccato
    assert_playable(_figure_score(ctx, parts, 5), profiles="torroba")


def test_type_4_and_type_5_keep_the_locked_levels() -> None:
    for kind, beat, velocity in (("4/4", 2.0, 64), ("3/4", 2.0, 64), ("6/8", 1.75, 64)):
        _ctx_figure, _phrase, parts = _flat_figure(kind, 4)
        lead = [note for note in parts[0][0] if note.beat == pytest.approx(beat)]
        assert len(lead) == 1 and lead[0].velocity == velocity
    four, _phrase, call = _flat_figure("4/4", 4)
    tail = [note.velocity for note in call[0][0] if note.beat >= 2]
    assert tail == [64, 64 - _MICRO, 64 - _MICRO, 64 - _MICRO]
    weak_bass = [note for note in call[0][2] if note.beat == pytest.approx(3.5)]
    weak_support = [note for note in call[0][1] if note.beat == pytest.approx(3.5)]
    assert len(weak_bass) == 1 and weak_bass[0].velocity == 56
    assert len(weak_support) == 1 and weak_support[0].velocity == 54
    _ctx34, _phrase34, call34 = _flat_figure("3/4", 4)
    bass_five = [note for note in call34[0][2] if note.beat == pytest.approx(2.5)]
    support_five = [note for note in call34[0][1] if note.beat == pytest.approx(2.5)]
    support_four = [note for note in call34[0][1] if note.beat == pytest.approx(2.0)]
    assert len(bass_five) == 1 and bass_five[0].velocity == 56
    assert len(support_five) == 1 and support_five[0].velocity == 54
    assert len(support_four) == 1 and support_four[0].velocity == 56
    assert not any(note.beat == pytest.approx(0.0) for note in call[0][0])
    assert four.kind == "4/4"
    _ctx_figure, _phrase, fan = _flat_figure("4/4", 5)
    assert fan[0][0][0].velocity == 68
    assert fan[0][2][0].velocity == 60
    assert fan[0][1][0].velocity == 56
    handoff = [note.velocity for note in fan[2][0]]
    assert handoff == [68 - 2 * _MICRO, 68 - 2 * _MICRO, 68 - _MICRO, 68]
    slur = sorted(
        (note for note in fan[1][2] if 0.5 <= note.beat < 1.0),
        key=lambda note: note.beat,
    )
    assert [note.midi for note in slur] == [50, 48]
    assert [note.duration_beats for note in slur] == [pytest.approx(0.25), pytest.approx(0.25)]
    assert slur[0].slur_start and slur[1].slur_stop
    assert [note.velocity for note in slur] == [60 - 2 * _MICRO, 60 - _MICRO]


def test_harmonic_48_skips_the_whole_bar_extra() -> None:
    phrase = _joined(0, [60] * 8 + [72] * 8)
    ctx = _ctx(melody=[60] * 8 + [72] * 8, phrase=phrase, bars=2)
    node = NoteEvent(bar=1, beat=0.0, midi=67, duration_beats=4.0, voice=1, velocity=48)
    ordinary = NoteEvent(bar=1, beat=0.0, midi=72, duration_beats=4.0, voice=1, velocity=64)
    assert skips_bar_extra(ctx, node)
    assert not skips_bar_extra(ctx, replace(node, midi=50))
    assert not skips_bar_extra(ctx, replace(node, velocity=58))
    shaped, _support, _low = _shape_dynamics(ctx, [node, ordinary], [], [], set(), ["sonatina", "sonatina"])
    assert shaped[0].velocity == 48
    assert shaped[1].velocity == 64 + 4


def test_weak_lead_follows_the_swell_above_64() -> None:
    """A rising type 4 tail uses `_note_velocity` of that eighth, then one micro step."""
    pitches = [60] * 5 + [72] * 27
    phrase = _joined(0, pitches, held=True)
    assert phrase.rise >= MIN_RISE
    ctx = _many((phrase,), melody=pitches)
    with compose_meter(METER_44):
        lead, _support, _low = render_torroba_figure(
            ctx, 0, phrase, "sonatina", 4, index=0, count=2
        )
    eighth = 5
    written = _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), phrase)
    assert written > 64
    attack = [note for note in lead if note.midi is not None and note.beat == pytest.approx(eighth * 0.5)]
    assert len(attack) == 1
    assert attack[0].velocity == written - _MICRO
    assert attack[0].velocity > 64 - _MICRO
    own = _note_velocity(4, 1, _apex_eighths(ctx.phrases), phrase)
    downbeat = _note_velocity(0, 1, _apex_eighths(ctx.phrases), phrase)
    assert own != downbeat
    strong = [note for note in lead if note.midi is not None and note.beat == pytest.approx(2.0)]
    assert len(strong) == 1 and strong[0].velocity == own


def test_figure_bars_keep_their_own_slur_and_grow_no_pickup() -> None:
    pitches = [72] * 31 + [73]
    score = _render(
        pitches,
        (_joined(0, pitches, held=True),),
        chords={bar: C for bar in range(4)},
        kinds={bar: "phrase" for bar in range(4)},
        mode="major",
        character="rally",
        bpm=96,
    )
    call = [note for note in score.lead if note.bar == 0 and note.midi is not None]
    assert not any(note.beat == pytest.approx(0.0) for note in call)
    assert any(note.slur_start and note.beat == pytest.approx(1.5) for note in call)
    assert not any(note.duration_beats == pytest.approx(0.25) and note.beat == pytest.approx(3.75) for note in score.lead)
    answer = [note for note in score.lead if note.bar == 1 and note.midi is not None and note.beat == pytest.approx(0.0)]
    assert len(answer) == 1 and answer[0].duration_beats == pytest.approx(4.0)
    base = [note for note in score.lead if note.bar == 2 and note.beat == pytest.approx(0.0) and note.midi is not None]
    assert len(base) == 1 and base[0].duration_beats < 4
