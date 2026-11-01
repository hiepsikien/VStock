"""Torroba: Andalucian harmony, Ab on G, Picardy, and the four guitar patterns."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.sonify.chords import (
    Chord,
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
from app.sonify.keys import C_KEY, EB_KEY
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
    _fill,
    _fill_voices,
    _fallback_body_pattern,
    _note_velocity,
    _owning_pattern,
    _select_body,
    _shape_dynamics,
    assert_playable,
    _FAMILY,
    _patterns,
    form_pattern_ids,
    headline_id,
)
from app.sonify.guitar_torroba import (
    _FIGURES,
    _HARMONICS,
    _Pen,
    _bass_length_eighths,
    _bed,
    _grid_state,
    _half_bass_events,
    _rasgueado_onsets,
    _alcaniz_dance,
    _alcaniz_opening,
    _render_torroba_bar,
    _torroba_bass,
    _torroba_contrast,
    _torroba_primary,
    castillos_wave_row,
    _Attack,
    _realize,
    render_torroba_figure,
    select_torroba_figure,
    select_torroba_spans,
    skips_bar_extra,
    torroba_figure_plan,
    torroba_scale_step,
)
from app.sonify.program import pattern_form, pattern_title
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


def _bridge(bars: int) -> tuple[FormSection, ...]:
    return (FormSection(0, bars, "phrase", 1, bridge=True),)


def _castillo_then_sonatina() -> tuple[FormSection, ...]:
    return (
        FormSection(0, 1, "phrase", 0),
        FormSection(1, 2, "phrase", 1, bridge=True),
    )


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


def _name_sonatina(monkeypatch) -> None:
    """Force Sonatina on 3/4: the picker no longer returns it on its own.

    Calm 3/4 is Castillo — Juglar — Castillo at every tempo now — the old
    `bpm > 72` gate is gone — but the Sonatina renderer is still live code, so
    the tests below name the pattern they exercise instead of leaning on that
    gate. A 3/4 Sonatina still answers with Castillo, which is what the bridge
    fixtures in those tests expect.
    """
    real = _torroba_primary

    def primary(ctx, mood, *, framed_macro: bool = False) -> str:
        if ctx.kind == "3/4":
            return "sonatina"
        return real(ctx, mood, framed_macro=framed_macro)

    monkeypatch.setattr("app.sonify.guitar_patterns._torroba_primary", primary)


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
    # Picardy keeps the placed G. This even thin-Olite stretch then sings it a fifth lower.
    assert under_cm[8] == 67
    assert lead[0] == 60
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
    assert _select_body(rally, phrase, first_body=True, previous=[], section=None) == "olite"
    calm = _ctx(melody=[64] * 8, phrase=phrase, character="calm")
    assert _select_body(calm, phrase, first_body=True, previous=[], section=None) == "olite"
    volatile = _ctx(melody=[64] * 8, phrase=phrase, character="volatile")
    assert _select_body(volatile, phrase, first_body=True, previous=[], section=None) == "olite"
    slow = _ctx(melody=[64] * 8, phrase=phrase, character="selloff", bpm=72)
    assert _select_body(slow, phrase, first_body=True, previous=[], section=None) == "olite"
    selloff = _ctx(melody=[64] * 8, phrase=phrase, character="selloff", bpm=96)
    assert _select_body(selloff, phrase, first_body=True, previous=[], section=None) == "olite"
    scherzo = _ctx(melody=[64] * 6, phrase=_joined(0, [64] * 6), kind="6/8", epb=6, strong=(0, 3), character="calm", bar_beats=3)
    assert _torroba_primary(scherzo, "calm", framed_macro=True) == "danza"
    assert _torroba_primary(scherzo, "calm", framed_macro=False) == "danza"
    four = _ctx(melody=[64] * 8, phrase=phrase, kind="4/4", character="volatile", bpm=108)
    assert _torroba_primary(four, "volatile", framed_macro=True) == "olite"
    assert "danza" != _torroba_primary(four, "calm", framed_macro=True)
    assert _torroba_contrast(scherzo, "danza") == "alcaniz"
    assert _torroba_contrast(scherzo, "sonatina") == "sonatina"
    assert _torroba_contrast(scherzo, "castillo") == "castillo"
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
    assert _select_body(unframed, unframed.phrases[0], first_body=True, previous=[], section=None) == "alcaniz"
    assert _select_body(unframed, unframed.phrases[0], first_body=True, previous=[], section=bridge) == "danza"
    assert _torroba_contrast(four, "castillo") == "olite"
    assert _torroba_contrast(slow, "castillo") == "olite"


def test_dance_writes_a_four_step_gap_and_one_extra_per_bar() -> None:
    phrase = _joined(0, [72] * 6)
    ctx = _ctx(
        melody=[72] * 6,
        phrase=phrase,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        character="volatile",
        bar_beats=3,
    )
    with compose_meter(METER_68):
        lead, _support, _low = _render_torroba_bar(ctx, 0, phrase, "fandanguillo")
    rolled = [note for note in lead if note.beat < 0.25]
    assert len(rolled) == 1
    assert rolled[0].beat == pytest.approx(2 / 12)
    assert rolled[0].duration_beats == pytest.approx(4 / 12)
    assert rolled[0].velocity == 68 and rolled[0].accent
    by_beat = {round(note.beat, 2): note for note in lead if note.duration_beats >= 0.5}
    assert by_beat[1.0].velocity == 64 and not by_beat[1.0].accent
    # Eighth 3 is the secondary strong beat: one degree under 68, and not an accent.
    assert by_beat[1.5].velocity == 66 and not by_beat[1.5].accent
    assert rolled[0].velocity - by_beat[1.0].velocity == 4
    four = _ctx(melody=[72] * 8, phrase=_joined(0, [72] * 8), character="volatile")
    with compose_meter(METER_44):
        four_lead, _support, _low = _render_torroba_bar(four, 0, four.phrases[0], "fandanguillo")
    assert not any(note.duration_beats >= 0.5 and note.beat >= 0.5 for note in four_lead)
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
    # 4/4 holds the downbeat for the bar, including a bar that is not the close.
    assert len(lead) == 1
    assert lead[0].beat == pytest.approx(0.0)
    assert lead[0].duration_beats == pytest.approx(4.0)
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
    assert sonatina is not None and sonatina.snap_calm is None and sonatina.snap_wide is None
    assert sonatina.max_units_per_phrase == 0 and sonatina.max_units_per_sec == 0
    assert dance is not None and (dance.snap_calm, dance.snap_wide) == (70, 73)
    assert dance.max_units_per_phrase == 1 and dance.max_units_per_sec == 3
    assert profile_for("torroba", "fandanguillo").max_units_per_sec == 3
    ctx = _ctx(melody=[72] * 8, phrase=_joined(0, [72] * 8))
    accented = NoteEvent(bar=0, beat=0.0, midi=72, duration_beats=0.5, voice=1, velocity=68, accent=True)
    plain = NoteEvent(bar=0, beat=1.0, midi=72, duration_beats=0.5, voice=1, velocity=72, accent=False)
    inner = NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=0.5, voice=2, velocity=68, accent=True)
    bell = NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=2.0, voice=1, velocity=48, accent=True)
    assert _is_target(ctx, "castillo", accented, "lead", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "castillo", bell, "lead", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "sonatina", accented, "lead", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "sonatina", plain, "lead", ctx.phrases[0], 1.0, 1.0) is False
    assert _is_target(ctx, "fandanguillo", inner, "support", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "danza", accented, "lead", ctx.phrases[0], 0.0, 1.0) is True
    assert _is_target(ctx, "danza", bell, "lead", ctx.phrases[0], 0.0, 1.0) is False
    assert _is_target(ctx, "fandanguillo", bell, "lead", ctx.phrases[0], 0.0, 1.0) is False


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
    quarters = [note for note in lead if note.duration_beats >= 1.0]
    assert [note.midi for note in quarters] == [72, 74]
    assert any(note.slur_start for note in lead) and any(note.slur_stop for note in lead)
    assert not any(note.duration_beats == 0.25 for note in lead)

    leap = [74] * 4 + [67] * 4
    leap_phrase = _joined(0, leap)
    leap_ctx = _ctx(melody=leap, phrase=leap_phrase, character="rally", chord=G)
    with compose_meter(METER_44):
        leaped, _support, _low = _render_torroba_bar(leap_ctx, 0, leap_phrase, "sonatina")
    arrivals = [note for note in leaped if abs(note.beat - 2.0) < 1e-6]
    assert len(arrivals) == 1 and arrivals[0].duration_beats == pytest.approx(1.0) and arrivals[0].midi == 67
    approaches = [note for note in leaped if note.duration_beats == 0.25]
    assert len(approaches) == 1
    assert approaches[0].beat == 1.75 and approaches[0].velocity == 56 and approaches[0].slur_start
    assert arrivals[0].slur_stop

    rising = [67] * 4 + [74] * 4
    # A rally bridge is Castillo, the contrast of Olite. One bar has no Arada span.
    rise_phrase = _joined(0, rising, held=True)
    score = _render(
        rising,
        (rise_phrase,),
        chords={0: G},
        kinds={0: "phrase"},
        mode="major",
        character="rally",
        bpm=96,
        sections=_bridge(1),
    )
    held = [note for note in score.lead if note.midi is not None]
    # Stretch 0. G4 on G is B3, the chord tone under the scale fifth.
    assert [(note.midi, note.duration_beats) for note in held] == [(59, pytest.approx(4.0))]
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
    assert support and all(note.staccato for note in support)
    assert low and all(not note.staccato for note in low)
    assert [round(note.beat, 2) for note in low] == [0.0, 1.5]
    assert all(note.duration_beats == pytest.approx(1.0) for note in low)

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
    from app.sonify.guitar_scale_passages import _trace_scale
    from app.sonify.guitar_torroba import _approaches, _fit_walk, _scale_steps, _two_into

    ctx = SimpleNamespace(mode="minor", treble_floor=59, treble_top=81, ensemble="torroba")
    climbed = torroba_scale_step(ctx, 67, 1, low=59, high=81)
    assert climbed > 67
    stepped = torroba_scale_step(ctx, 70, 1, low=59, high=81)
    assert stepped % 12 != 11
    assert torroba_scale_step(ctx, 70, -1, low=59, high=81) % 12 == 8

    # Ab stands only immediately before G, and only when the bar is G or G7.
    into_g = _scale_steps(ctx, 69, 67, G)
    assert into_g[-1] == 67 and into_g[-2] % 12 == 8
    climbed_line = _scale_steps(ctx, 60, 67, G)
    assert climbed_line[-1] == 67 and climbed_line[-2] % 12 == 8
    assert len(climbed_line) > 3
    fitted = _fit_walk(climbed_line)
    assert fitted is not None and fitted[1] % 12 == 8 and fitted[-1] == 67
    assert abs(fitted[0] - fitted[1]) <= 2 and abs(fitted[1] - fitted[2]) <= 2
    into_d = _scale_steps(ctx, 69, 62, G)
    assert into_d[-1] == 62 and into_d[-2] % 12 != 8
    assert all(note % 12 != 8 for note in into_d)
    assert _scale_steps(ctx, 69, 67, C)[-2:] != [68, 67]

    assert _approaches(ctx, 67, 1, G) == [68]
    assert _approaches(ctx, 67, 1, C)[-1] % 12 != 8
    # Three sixteenths walk onto Ab. They do not keep D–Eb and leap a fourth.
    assert _approaches(ctx, 67, 3, G) == [65, 67, 68]
    assert _approaches(ctx, 74, 3, G)[-1] % 12 != 8

    first, second = _two_into(ctx, 60, 67, G)
    assert (first, second) == (67, 68)
    fallen, before = _two_into(ctx, 72, 67, G)
    assert (fallen, before) == (70, 68)
    _first, other = _two_into(ctx, 60, 67, CM)
    assert other % 12 != 8
    _first, onto_d = _two_into(ctx, 72, 74, G)
    assert onto_d % 12 != 8

    traced = _trace_scale(ctx, 69, 67, "down", False, 59, 81, chord=G)
    assert traced == [69, 68, 67]
    passed = _trace_scale(ctx, 69, 62, "down", False, 50, 81, chord=G)
    assert passed is not None and passed[-1] == 62 and passed[-2] % 12 != 8
    assert all(note % 12 != 8 for note in passed)
    over_c = _trace_scale(ctx, 69, 67, "down", False, 59, 81, chord=C)
    assert over_c is not None and over_c[-2] % 12 != 8


def test_embellish_steps_into_ab_and_a_retreat_uses_the_same_gate() -> None:
    """Ab is declined when the note before it would have to leap. A spare step can take it."""
    from app.sonify.guitar_scale_passages import _embellish, _trace_scale, _with_retreat
    from app.sonify.guitar_torroba import rewrite_torroba_approach

    ctx = SimpleNamespace(mode="minor", treble_floor=59, treble_top=81, ensemble="torroba", semitones=0, ceiling=84, epb=8)
    into_g = _trace_scale(ctx, 60, 67, "up", False, 50, 81, chord=G)
    assert into_g is not None
    heard = _embellish(into_g, len(into_g), ctx, "up", False, 50, 81, G.pitch_classes)
    assert heard == [60, 62, 63, 65, 67]

    roomy = _embellish(into_g, len(into_g) + 2, ctx, "up", False, 50, 81, G.pitch_classes)
    assert roomy == [60, 62, 63, 65, 67, 68, 67]

    into_d = _trace_scale(ctx, 60, 74, "up", False, 50, 81, chord=G)
    assert into_d is not None
    heard_d = _embellish(into_d, len(into_d), ctx, "up", False, 50, 81, G.pitch_classes)
    assert heard_d is not None and heard_d[-1] == 74 and heard_d[-2] % 12 != 8

    above = [72, 70, 69, 67]
    placed = rewrite_torroba_approach(ctx, above, G.pitch_classes, low=50, high=81)
    assert placed == [72, 70, 68, 67]
    flags = [False, False, False, False, True, False]
    retreated = _with_retreat(72, 67, 6, flags, ctx, "down", False, low=50, high=81, chord_pcs=G.pitch_classes)
    assert retreated == [72, 70, 68, 67, 68, 67]
    climbed = _with_retreat(
        60, 67, 6, [False, False, True, False, False, False], ctx, "up", False, low=50, high=81, chord_pcs=G.pitch_classes
    )
    assert climbed == [60, 62, 61, 63, 65, 67]


def test_flat_sung_phrase_arches_the_lead_and_leaves_the_bass() -> None:
    """A flat sung phrase has no swell. The arch is the 6–8 degrees on the lead."""
    from app.sonify.guitar_torroba import apply_torroba_sung_arch

    pitches = [67] * 32
    phrase = _joined(0, pitches)
    assert phrase.rise == 0
    ctx = _ctx(melody=pitches, phrase=phrase, bars=4, character="calm")
    lead = [
        NoteEvent(bar=bar, beat=0.0, midi=67, duration_beats=2.0, voice=1, velocity=64)
        for bar in range(4)
    ]
    bass = [
        NoteEvent(bar=bar, beat=0.0, midi=43, duration_beats=2.0, voice=3, velocity=60)
        for bar in range(4)
    ]
    arched = apply_torroba_sung_arch(ctx, lead, ["castillo"])
    heard = [int(note.velocity or 0) for note in arched]
    assert max(heard) - min(heard) >= 6
    assert max(heard) - min(heard) <= 8
    assert max(heard) <= 72
    assert heard != [64, 64, 64, 64]
    # The pass is lead-only. The same written bass does not take that addition.
    assert [int(note.velocity or 0) for note in bass] == [60, 60, 60, 60]
    danced = apply_torroba_sung_arch(ctx, lead, ["danza"])
    assert [int(note.velocity or 0) for note in danced] == [64, 64, 64, 64]


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
    # Rally's contrast is Castillo, so the joined outro is that cadence, not Sonatina's minor I.
    assert {note % 12 for note in outro_notes} == {4, 7}
    assert long_score.slots[-1].chord.name == "Cm"
    for pattern, meter, character in (
        ("castillo", METER_44, "selloff"),
        ("sonatina", METER_44, "rally"),
        ("olite", METER_44, "volatile"),
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
    """Inner notes after the downbeat chord. The rolled support sits before 0.25."""
    return {
        round(note.beat, 2)
        for note in support
        if note.midi is not None and note.beat >= 0.25
    }


def _at(notes, beat: float):
    found = [note for note in notes if note.midi is not None and abs(note.beat - beat) < 1e-6]
    assert len(found) == 1
    return found[0]


def test_breath_harmonics_and_fandanguillo_grids(monkeypatch) -> None:
    _name_sonatina(monkeypatch)
    # 4/4 Fandanguillo has no melody eighths, so every off-downbeat eighth can take a gap.
    full_gaps = {0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5}
    thin_gaps = {0.5, 1.5, 2.5, 3.5}

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
    assert _gap_beats(split_support) == {0.5, 1.5, 2.5, 3.0, 3.5}
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
    assert [round(note.beat, 2) for note in covered_low] == [0.0, 2.0]
    assert all(note.velocity == 58 and not note.tie_start and not note.tie_stop for note in covered_low)
    assert len(covered_lead) == 1
    assert covered_lead[0].beat == pytest.approx(0.0)
    assert covered_lead[0].duration_beats == pytest.approx(4.0)

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
    assert partial_low[0].velocity == 62
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
    # Olite thin joins the leading eighth to the next strong beat inside the bar.
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in crossed.lead)
    assert any(note.slur_start and note.beat == pytest.approx(1.5) for note in crossed.lead if note.bar == 0)
    assert not any(
        note.midi is not None and note.bar == 1 and note.beat == pytest.approx(0.0) and note.slur_stop
        for note in crossed.lead
    )

    # 3/4 Sonatina with a Castillo bridge. The hold is the
    # downbeat, so a leap graces from that pitch and a step slurs from it.
    castillo_then_sonatina = (
        FormSection(0, 1, "phrase", 0, bridge=True),
        FormSection(1, 2, "phrase", 1),
    )
    graced = _render(
        [76] * 6 + [64] * 6,
        (_joined(0, [76] * 6), _joined(6, [64] * 6, held=True)),
        chords={0: C, 1: C},
        kinds={0: "phrase", 1: "phrase"},
        mode="major",
        character="calm",
        bpm=96,
        meter=METER_34,
        sections=castillo_then_sonatina,
    )
    grace = [note for note in graced.lead if note.midi is not None and note.duration_beats == 0.25]
    assert [(note.bar, round(note.beat, 2)) for note in grace] == [(0, 2.75)]
    assert grace[0].slur_start
    assert _strong(graced, 0, 0.0).midi == 67
    assert _strong(graced, 0, 2.0).midi == 67
    assert _strong(graced, 1, 0.0).midi == 64 and _strong(graced, 1, 0.0).slur_stop
    # Eighth 4 of the Castillo bar is the same held pitch, not the unsung 71.
    stepped_close = _render(
        [72] * 3 + [71] * 3 + [64] * 6,
        (_joined(0, [72] * 3 + [71] * 3), _joined(6, [64] * 6, held=True)),
        chords={0: CMAJ7, 1: C},
        kinds={0: "phrase", 1: "phrase"},
        mode="major",
        character="calm",
        bpm=96,
        meter=METER_34,
        sections=castillo_then_sonatina,
    )
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in stepped_close.lead)
    assert _strong(stepped_close, 0, 0.0).midi == 64
    assert _strong(stepped_close, 0, 2.0).midi == 64
    assert _strong(stepped_close, 1, 0.0).midi == 64 and not _strong(stepped_close, 1, 0.0).slur_stop
    held_step = _render(
        [72] * 3 + [60] * 3 + [62] * 6,
        (_joined(0, [72] * 3 + [60] * 3), _joined(6, [62] * 6, held=True)),
        chords={0: C, 1: G},
        kinds={0: "phrase", 1: "phrase"},
        mode="major",
        character="calm",
        bpm=96,
        meter=METER_34,
        sections=castillo_then_sonatina,
    )
    assert _strong(held_step, 0, 0.0).midi == 64 and _strong(held_step, 0, 0.0).slur_start
    assert _strong(held_step, 0, 2.0).midi == 64
    assert _strong(held_step, 1, 0.0).midi == 62 and _strong(held_step, 1, 0.0).slur_stop

    node = [67] * 8
    node_phrase = _joined(0, node)
    node_ctx = _ctx(melody=node, phrase=node_phrase, character="calm", chord=G, mode="minor")
    with compose_meter(METER_44):
        sung, emptied, _low = _render_torroba_bar(node_ctx, 0, node_phrase, "castillo")
    # The whole bar is the harmonic bell, so the inner voice stays empty.
    assert len(sung) == 1
    assert sung[0].beat == pytest.approx(0.0) and sung[0].midi == 67
    assert sung[0].velocity == 48 and sung[0].duration_beats == pytest.approx(4.0)
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
    roll = round(2 / 12, 2)
    by_beat = {round(note.beat, 2): note for note in lead}
    assert set(by_beat) == {roll, 1.0, 1.5}
    assert by_beat[roll].velocity >= 68 and by_beat[roll].accent and by_beat[roll].midi == 72
    assert by_beat[1.0].velocity == 64 and not by_beat[1.0].accent
    assert by_beat[1.5].velocity == 66 and not by_beat[1.5].accent
    opening = sorted(
        (note for note in (*lead, *support, *low) if note.midi is not None and note.beat < 0.25),
        key=lambda note: note.beat,
    )
    bass = [note for note in opening if note.voice == 3]
    mids = [note for note in opening if note.voice == 2]
    highs = [note for note in opening if note.voice == 1]
    assert 1 <= len(bass) <= 2 and 2 <= len(mids) <= 3 and len(highs) == 1
    assert 5 <= len(opening) <= 6
    assert all(note.beat == pytest.approx(0.0) for note in bass)
    assert all(note.beat == pytest.approx(1 / 12) for note in mids)
    assert highs[0].beat == pytest.approx(2 / 12) and highs[0].midi == 72
    assert all(note.beat + note.duration_beats == pytest.approx(0.5) for note in opening)

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
    roll = round(2 / 12, 2)
    beats = {round(note.beat, 2): note for note in waltzed}
    assert set(beats) == {roll, 1.0, 2.0}
    assert beats[roll].velocity >= 68 and beats[roll].accent
    assert beats[1.0].velocity == 64 and not beats[1.0].accent
    assert beats[2.0].velocity == 64 and not beats[2.0].accent


def _covers_beat(note: NoteEvent, bar: int, beat: float, length: float) -> bool:
    if note.bar != bar or note.midi is None:
        return False
    start = note.beat
    end = note.beat + note.duration_beats
    return start < beat + length - 1e-9 and end > beat + 1e-9


def _two_bars(pitches, phrases, chords, *, character="rally", character_at=None, sections=None):
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
            sections=sections,
            rel_span=0.0,
        )


def _type4_pair(score: Score) -> None:
    """A held 2-bar sonatina is type 4. The grid grace is not planted on a figure bar."""
    sixteenths = [
        (note.bar, round(note.beat, 2))
        for note in score.lead
        if note.midi is not None and note.duration_beats == 0.25
    ]
    assert (0, 0.5) in sixteenths and (0, 0.75) in sixteenths
    assert (0, 3.75) not in sixteenths
    mordent = [
        note
        for note in score.lead
        if note.bar == 0 and note.midi is not None and abs(note.duration_beats * 6 - 1) < 1e-3
    ]
    assert len(mordent) == 3 and mordent[0].slur_start and mordent[-1].slur_stop
    assert not any(note.slur_start and note.slur_stop for note in score.lead)


def _waltz(pitches, phrases, chords, *, sections=None, character="calm", bpm=96):
    bars = len(pitches) // 6
    return _render(
        pitches,
        phrases,
        chords=chords,
        kinds={bar: "phrase" for bar in range(bars)},
        mode="major",
        character=character,
        bpm=bpm,
        meter=METER_34,
        sections=sections,
    )


def test_sonatina_downbeat_leap_step_run_and_castillo_hold(monkeypatch) -> None:
    _name_sonatina(monkeypatch)
    # 3/4 Sonatina, forced by `_name_sonatina`. Two bars with no bridge stay on type 4.
    leap = _waltz(
        [74] * 6 + [67] * 6,
        (_joined(0, [74] * 6 + [67] * 6, held=True),),
        {0: G, 1: G},
    )
    _type4_pair(leap)
    arrival = [note for note in leap.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(arrival) == 1 and arrival[0].midi == 67

    step = _waltz(
        [71] * 6 + [72] * 6,
        (_joined(0, [71] * 6 + [72] * 6, held=True),),
        {0: G, 1: C},
    )
    _type4_pair(step)
    arrived = [note for note in step.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(arrived) == 1 and arrived[0].midi == 72

    running = _waltz(
        [67] * 6 + [74] * 6,
        (_joined(0, [67] * 6 + [74] * 6, held=True),),
        {0: G, 1: G},
    )
    _type4_pair(running)
    apex = [note for note in running.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(apex) == 1 and apex[0].midi == 74
    assert running.scale_eighths == ()

    castillo_bridge = (
        FormSection(0, 1, "phrase", 0, bridge=True),
        FormSection(1, 2, "phrase", 1),
    )
    held = _waltz(
        [76] * 6 + [64] * 6,
        (_joined(0, [76] * 6), _joined(6, [64] * 6, held=True)),
        {0: C, 1: C},
        sections=castillo_bridge,
    )
    grace = [note for note in held.lead if note.midi is not None and note.duration_beats == 0.25]
    assert [(note.bar, round(note.beat, 2)) for note in grace] == [(0, 2.75)]
    assert grace[0].slur_start
    sung = [note for note in held.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(sung) == 1 and sung[0].midi == 64 and sung[0].slur_stop
    for note in held.lead:
        if note.bar != 0 or note.duration_beats == 0.25 or note.midi is None:
            continue
        assert note.beat + note.duration_beats <= 2.75 + 1e-6
    assert_playable(held, profiles="torroba")

    dance = _two_bars([72] * 16, (_joined(0, [72] * 16),), {0: C, 1: C}, character="volatile")
    assert not any(note.midi is not None and note.duration_beats == 0.25 for note in dance.lead)

    # Castillo holds the downbeat. The unsung note at the later eighth does not decide the ornament.
    step_line = [72] * 3 + [60] * 3 + [62] * 6
    held_step = _waltz(
        step_line,
        (_joined(0, step_line[:6]), _joined(6, step_line[6:], held=True)),
        {0: C, 1: G},
        sections=castillo_bridge,
    )
    held_price = [note for note in held_step.lead if note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None]
    assert len(held_price) == 1 and held_price[0].midi == 64
    assert held_price[0].duration_beats == pytest.approx(2.0)
    assert held_price[0].slur_start
    assert _strong(held_step, 0, 2.0).midi == 64
    step_arrival = [note for note in held_step.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(step_arrival) == 1 and step_arrival[0].midi == 62 and step_arrival[0].slur_stop

    leap_line = [60] * 3 + [71] * 3 + [72] * 6
    held_leap = _waltz(
        leap_line,
        (_joined(0, leap_line[:6]), _joined(6, leap_line[6:], held=True)),
        {0: CMAJ7, 1: C},
        sections=castillo_bridge,
    )
    sounded = [note for note in held_leap.lead if note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None]
    assert len(sounded) == 1 and sounded[0].midi == 55
    # C4 is under the floor, so the hold is G3. That still leaps into C5.
    assert any(note.midi is not None and note.duration_beats == 0.25 for note in held_leap.lead)
    assert _strong(held_leap, 0, 2.0).midi == 55
    leap_arrival = [note for note in held_leap.lead if note.bar == 1 and abs(note.beat) < 1e-6 and note.duration_beats >= 0.5]
    assert len(leap_arrival) == 1 and leap_arrival[0].midi == 72 and leap_arrival[0].slur_stop
    assert_playable(leap, profiles="torroba")
    assert_playable(running, profiles="torroba")


def _strong(score_or_notes, bar: int, beat: float):
    notes = score_or_notes.lead if hasattr(score_or_notes, "lead") else score_or_notes
    found = [
        note
        for note in notes
        if note.bar == bar and abs(note.beat - beat) < 1e-6 and (note.duration_beats or 0) >= 0.5 and note.midi is not None
    ]
    assert len(found) == 1
    return found[0]


def test_sonatina_slur_is_one_arch_and_skips_a_repeated_note(monkeypatch) -> None:
    _name_sonatina(monkeypatch)
    # The grid skips a slur when the two eighths repeat the next strong pitch.
    same_phrase = _joined(0, [72] * 8, held=True)
    same_ctx = _ctx(melody=[72] * 8, phrase=same_phrase, character="rally", chord=C)
    with compose_meter(METER_44):
        same_lead, _support, _low = _render_torroba_bar(same_ctx, 0, same_phrase, "sonatina")
    assert not any(note.slur_start or note.slur_stop for note in same_lead if note.midi is not None)
    step = [72] * 4 + [74] * 4
    step_phrase = _joined(0, step, held=True)
    step_ctx = _ctx(melody=step, phrase=step_phrase, character="rally", chord=G)
    with compose_meter(METER_44):
        step_lead, _support, _low = _render_torroba_bar(step_ctx, 0, step_phrase, "sonatina")
    assert any(note.slur_start and not note.slur_stop for note in step_lead)
    assert any(note.slur_stop and not note.slur_start for note in step_lead)
    assert not any(note.slur_start and note.slur_stop for note in step_lead)

    # 3/4 Sonatina. A held 2-bar phrase is type 4, so the answer holds the bar.
    line = [67] * 6 + [68] * 6
    score = _render(
        line,
        (_joined(0, line, held=True),),
        chords={0: G, 1: G},
        kinds={0: "phrase", 1: "phrase"},
        mode="minor",
        character="calm",
        bpm=96,
        meter=METER_34,
    )
    assert not any(note.slur_start and note.slur_stop for note in score.lead)
    answer = [note for note in score.lead if note.bar == 1 and note.midi is not None and note.beat == pytest.approx(0.0)]
    assert len(answer) == 1 and answer[0].duration_beats >= 2


def test_sonatina_inner_uses_the_quarter_that_is_still_ringing() -> None:
    # Eighth 1 and eighth 5 are written higher than the quarters that cover them.
    melody = [60, 67, 67, 67, 64, 71, 71, 71]
    phrase = _joined(0, melody, held=True)
    ctx = _ctx(melody=melody, phrase=phrase, character="rally", chord=C, bpm=96)
    with compose_meter(METER_44):
        lead, support, _low = _render_torroba_bar(ctx, 0, phrase, "sonatina")
    for beat, unsung in ((0.5, 67), (2.5, 71)):
        quarter = next(
            note
            for note in lead
            if note.midi is not None and note.beat <= beat + 1e-9 < note.beat + note.duration_beats
        )
        inner = next(note for note in support if note.midi is not None and abs(note.beat - beat) < 1e-6)
        assert quarter.midi < unsung
        assert inner.midi < quarter.midi
        assert inner.velocity == _bed(quarter.velocity or 64, "mf")[0]
    opening = next(note for note in lead if abs(note.beat) < 1e-6 and note.midi == 60)
    assert opening.velocity == 60


def test_castillo_4_4_holds_the_downbeat_for_the_bar() -> None:
    melody = [60, 60, 60, 64, 65, 65, 65, 67]
    phrase = _joined(0, melody, held=True)
    ctx = _ctx(melody=melody, phrase=phrase, character="selloff", chord=C, bpm=96)
    with compose_meter(METER_44):
        lead, _support, _low = _render_torroba_bar(ctx, 0, phrase, "castillo")
    sounded = [note for note in lead if note.midi is not None]
    assert len(sounded) == 1
    assert sounded[0].midi == 60
    assert sounded[0].beat == pytest.approx(0.0)
    assert sounded[0].duration_beats == pytest.approx(4.0)
    assert not any(abs(note.duration_beats - 1.0 / 6.0) < 1e-6 for note in lead)


def test_3_4_bass_retreats_to_a_chord_tone_the_lead_can_fret() -> None:
    """Fm's F2 does not fit a high lead. The bar keeps a chord bass that does."""
    melody = [72] * 6
    phrase = _joined(0, melody, held=True)
    ctx = _ctx(
        melody=melody,
        phrase=phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        character="calm",
        bar_beats=3.0,
        chord=FM,
        bpm=96,
    )
    with compose_meter(METER_34):
        castillo = _render_torroba_bar(ctx, 0, phrase, "castillo")
        sonatina = _render_torroba_bar(ctx, 0, phrase, "sonatina")
    for lead, support, low in (castillo, sonatina):
        sounded = [note for note in low if note.midi is not None]
        assert sounded and all(note.midi != 41 for note in sounded)
        assert_playable(_figure_score(ctx, [(lead, support, low)], 1, FM), profiles="torroba")
    assert castillo[2][0].duration_beats == pytest.approx(1.5)
    assert sonatina[2][0].duration_beats == pytest.approx(0.5)

    open_phrase = _joined(0, melody, held=True)
    open_ctx = _ctx(
        melody=melody,
        phrase=open_phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        character="calm",
        bar_beats=3.0,
        chord=C,
        bpm=96,
    )
    with compose_meter(METER_34):
        _lead, _support, low = _render_torroba_bar(open_ctx, 0, open_phrase, "castillo")
    assert len(low) == 1 and low[0].midi == 40 and low[0].duration_beats == pytest.approx(1.5)


def test_bass_attack_is_omitted_when_no_length_frets() -> None:
    phrase = _joined(0, [60] * 8, held=True)
    ctx = _ctx(melody=[60] * 8, phrase=phrase, chord=C, bpm=96)
    blocked = [NoteEvent(bar=0, beat=0.0, midi=48, duration_beats=2.0, voice=1)]
    assert _bass_length_eighths(ctx, 48, 0, 0, blocked, limit=4) is None
    assert _half_bass_events(ctx, 0, 0, 48, 58, blocked) == []
    # The opening eighth is free. A longer hold meets the lead and is cut, not forced.
    later = [NoteEvent(bar=0, beat=0.5, midi=48, duration_beats=1.5, voice=1)]
    assert _bass_length_eighths(ctx, 52, 0, 0, later, limit=4) == 1
    kept = _half_bass_events(ctx, 0, 0, 52, 58, later)
    assert kept and kept[0].duration_beats == pytest.approx(0.5)
    assert kept[0].midi == 52


def test_sonatina_pickup_rests_only_its_sixteenth() -> None:
    leap = [74] * 4 + [67] * 4
    phrase = _joined(0, leap)
    ctx = _ctx(melody=leap, phrase=phrase, character="rally", chord=G)
    with compose_meter(METER_44):
        _lead, support, _low = _render_torroba_bar(ctx, 0, phrase, "sonatina")
    # Support sits on eighths 1 and 5. The grace sixteenth at 1.75 is empty underneath.
    assert not any(abs((note.duration_beats or 0) - 0.25) < 1e-6 for note in support)
    assert not any(_covers_beat(note, 0, 1.75, 0.25) for note in support)


def test_framed_scherzo_renders_danza() -> None:
    pitches = [72] * 30
    sections = (
        FormSection(0, 1, "intro", 0),
        FormSection(1, 3, "phrase", 0),
        FormSection(3, 4, "phrase", 1),
        FormSection(4, 5, "outro", 1),
    )
    score = _render(
        pitches,
        (
            _joined(0, pitches[:6], held=True),
            _joined(6, pitches[6:18]),
            _joined(18, pitches[18:24]),
            _joined(24, pitches[24:], held=True),
        ),
        chords={bar: C for bar in range(5)},
        kinds={0: "intro", 1: "phrase", 2: "phrase", 3: "phrase", 4: "outro"},
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
    """Fandanguillo enters at rise 1. Sonatina open follows the span table, not MIN_RISE."""
    quiet = (
        _span(0, 32, 72, 72, held=True, tail=1),
        _span(32, 32, 72, 72, held=True, tail=1),
        _span(64, 32, 70, 72, held=True, tail=1),
    )
    assert quiet[2].rise == 2 and quiet[2].rise < MIN_RISE
    plan = torroba_figure_plan(_many(quiet), ["sonatina", "sonatina", "sonatina"])
    # L=4, n rotated off the previous figure: type 4 on (0, 1) and type 1 on bar 3.
    assert _used(plan, quiet[2], 8) == {8: 4, 9: 4, 11: 1}
    flat = _span(0, 48, 72, 72, held=True, tail=48)
    assert flat.rise == 0
    assert torroba_figure_plan(_many((flat,)), ["fandanguillo"]) == {}
    short = _span(0, 48, 70, 72, held=True, tail=1)
    assert 1 <= short.rise < MIN_RISE
    granted = torroba_figure_plan(_many((short,)), ["fandanguillo"])
    assert set(granted.values()) == {(5, 0, 4), (5, 1, 4), (5, 2, 4), (5, 3, 4)}
    # Not enough room for type 5 does not borrow type 2.
    cramped = _span(0, 24, 60, 72, held=True, tail=1)
    assert cramped.rise >= MIN_RISE
    assert torroba_figure_plan(_many((cramped,)), ["fandanguillo"]) == {}
    short_sonatina = _span(0, 16, 72, 72, held=True, tail=1)
    assert short_sonatina.rise < MIN_RISE
    assert torroba_figure_plan(_many((short_sonatina,)), ["sonatina"]) == {
        0: (4, 0, 2),
        1: (4, 1, 2),
    }


def test_castillo_figure_gate_follows_tempo_and_length() -> None:
    slow = (
        _span(0, 40, 72, 72, tail=8),
        _span(40, 32, 72, 72, tail=8),
        _span(72, 32, 72, 72, tail=8),
    )
    plan = torroba_figure_plan(_many(slow, bpm=72), ["castillo", "castillo", "castillo"])
    assert _used(plan, slow[0], 8) == {bar: 7 for bar in range(5)}
    # L=4, odd n: type 8 on slots (1, 2). The next phrase rotates off that type 8.
    assert _used(plan, slow[1], 8) == {6: 8, 7: 8}
    assert _used(plan, slow[2], 8) == {10: 8, 11: 8}
    sustain = _render_torroba_bar(_many((slow[1],), bpm=72), 0, slow[1], "castillo")[0]
    sounded = [note for note in sustain if note.midi is not None]
    assert len(sounded) == 1 and sounded[0].duration_beats >= 4

    short = (_span(0, 24, 72, 72, tail=8),)
    cut = torroba_figure_plan(_many(short, bpm=72), ["castillo"])
    assert set(cut) == {0, 1}
    assert set(cut.values()) == {(8, 0, 2), (8, 1, 2)}

    fast = torroba_figure_plan(_many(slow, bpm=96), ["castillo", "castillo", "castillo"])
    assert _used(fast, slow[0], 8) == {bar: 7 for bar in range(5)}
    assert _used(fast, slow[1], 8) == {6: 8, 7: 8}
    assert _used(fast, slow[2], 8) == {10: 8, 11: 8}


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
    assert _used(plan, phrases[0], 8) == {0: 4, 1: 4, 3: 2, 4: 2}
    assert _used(plan, phrases[1], 8) == {6: 1, 8: 4, 9: 4}
    assert _used(plan, phrases[2], 8) == {10: 1, 12: 4, 13: 4}
    assert _used(plan, phrases[3], 8) == {14: 4, 15: 4, 17: 1}
    assert _used(plan, phrases[4], 8) == {20: 2, 21: 2, 22: 1}
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
    assert _used(plan, phrases[1], 8) == {7: 2, 8: 2}
    assert set(_used(plan, phrases[2], 8).values()) == {5}
    for phrase in phrases:
        assert len(set(_used(plan, phrase, 8).values())) <= 1

    closing = _span(0, 48, 60, 65, tail=8)
    assert closing.closes and closing.rise >= MIN_RISE
    closed = torroba_figure_plan(_many((closing,)), ["fandanguillo"])
    assert _used(closed, closing, 8) == {0: 5, 1: 5, 2: 5, 3: 5}


def test_adjacent_phrase_does_not_repeat_a_figure() -> None:
    first = _span(0, 48, 60, 72, held=True, tail=1)
    second = _span(48, 48, 60, 72, held=True, tail=1)
    assert not first.closes and not second.closes
    plan = torroba_figure_plan(_many((first, second)), ["sonatina", "sonatina"])
    # L=6 even opens on type 4 and ends on type 2. The next odd turn would
    # open on type 2, so it rotates to the even row and opens on type 4.
    assert _used(plan, first, 8)[0] == 4
    assert _used(plan, second, 8)[6] == 4
    assert 2 in _used(plan, first, 8).values()
    closing = _span(0, 32, 72, 72, tail=8)
    again = select_torroba_figure(
        _many((closing,)), closing, "sonatina", n=None, k=None, previous=3
    )
    assert again == (3, (1, 2, 3))


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
        longer = _span(0, epb * 5, 72, 72, tail=epb)
        assert longer.closes
        extended = torroba_figure_plan(_many((longer,), kind=kind), ["danza"])
        assert set(extended) == {0, 1, 2, 3}
        assert set(value[0] for value in extended.values()) == {6}


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
        assert len(bass) == 1 and bass[0].velocity == 62 - _MICRO


def test_type_7_mordent_and_bar_5_bass_keep_the_written_steps() -> None:
    expected = {
        "4/4": [60, 60, 60, 60, 58, 58, 60],
        "3/4": [60, 60, 58, 58, 60],
        "6/8": [60, 60, 58, 58, 60],
    }
    for kind, velocities in expected.items():
        ctx, _phrase, parts = _flat_figure(kind, 7)
        mordent = sorted(
            (note for note in parts[0][0] if abs(note.duration_beats * 6 - 1) < 1e-3),
            key=lambda note: note.beat,
        )
        sixth = 1.0 / 6.0
        assert [note.beat for note in mordent] == pytest.approx([1.5, 1.5 + sixth, 1.5 + 2 * sixth])
        assert mordent[0].slur_start and mordent[2].slur_stop
        assert [note.velocity for note in mordent] == [64 - 2 * _MICRO, 64 - 3 * _MICRO, 64 - 2 * _MICRO]
        half = [note for note in parts[0][0] if note.beat == pytest.approx(2.0)]
        assert len(half) == 1 and half[0].duration_beats == pytest.approx(2.0 if kind == "4/4" else 1.0)
        assert half[0].velocity == 64
        bass = [note for note in parts[4][2] if note.midi is not None]
        chord_bass = [note for note in bass if note.beat < 0.25]
        running = [note for note in bass if note.beat >= 0.5 - 1e-9]
        assert len(chord_bass) == 1
        assert chord_bass[0].beat == pytest.approx(0.0)
        assert chord_bass[0].duration_beats == pytest.approx(0.5)
        assert chord_bass[0].velocity == 60
        assert [note.velocity for note in running] == velocities
        assert all(note.duration_beats == pytest.approx(0.5) for note in running)
        assert running[-1].midi % 12 == C.pitches[0] % 12
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
        first, _support, _low = render_torroba_figure(
            ctx, 0, phrase, "castillo", 7, index=0, count=5
        )
        second, _support, _low = render_torroba_figure(
            ctx, 1, phrase, "castillo", 7, index=1, count=5
        )
        third, _support, _low = render_torroba_figure(
            ctx, 2, phrase, "castillo", 7, index=2, count=5
        )
    opening = _note_velocity(0, 1, apex, phrase)
    first_mordent_written = _note_velocity(3, 1, apex, phrase)
    resolved = _note_velocity(4, 1, apex, phrase)
    assert first_mordent_written != opening and resolved != opening
    first_mordent = sorted((note for note in first if 1.5 <= note.beat < 2.0), key=lambda note: note.beat)
    assert [note.velocity for note in first_mordent] == [
        first_mordent_written - 2 * _MICRO,
        first_mordent_written - 3 * _MICRO,
        first_mordent_written - 2 * _MICRO,
    ]
    half = [note for note in first if note.beat == pytest.approx(2.0)]
    assert len(half) == 1 and half[0].duration_beats == pytest.approx(2.0)
    assert half[0].velocity == resolved
    downbeat = _note_velocity(8, 1, apex, phrase)
    held_written = _note_velocity(12, 1, apex, phrase)
    assert held_written != downbeat
    held = [note for note in second if note.beat == pytest.approx(2.0)]
    assert len(held) == 1 and held[0].duration_beats == pytest.approx(1.5)
    assert held[0].velocity == held_written - _MICRO
    pickup_written = _note_velocity(15, 1, apex, phrase)
    assert pickup_written != downbeat
    pickup = [note for note in second if note.beat == pytest.approx(3.5)]
    assert len(pickup) == 1 and pickup[0].velocity == pickup_written
    mordent_written = _note_velocity(11, 1, apex, phrase)
    mordent = sorted((note for note in second if 1.5 <= note.beat < 2.0), key=lambda note: note.beat)
    assert [note.velocity for note in mordent] == [
        mordent_written - 2 * _MICRO,
        mordent_written - 3 * _MICRO,
        mordent_written - 2 * _MICRO,
    ]
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
        assert note.velocity == 62 - _MICRO
    ordinary, _phrase, plain = _flat_figure("4/4", 8, chord=G)
    for note in plain[0][2]:
        assert note.midi not in _HARMONICS
        assert note.velocity == 62 - _MICRO
        assert note.midi < 52
    for beat in (0.0, 2.0):
        attacks = [note for note in parts[1][0] if note.beat == pytest.approx(beat)]
        assert len(attacks) == 1 and attacks[0].duration_beats == pytest.approx(0.5)
    first_slur = [note.velocity for note in parts[1][0] if 0.5 <= note.beat < 2]
    assert first_slur == [64, 64, 64]
    second_slur = [note.velocity for note in parts[1][0] if note.beat >= 2.5]
    assert second_slur == [62, 62, 62]
    _ctx34, _phrase34, three = _flat_figure("3/4", 8, chord=C)
    three_lead = [note.velocity for note in three[1][0] if note.beat >= 0.5 and note.duration_beats == pytest.approx(0.5)]
    assert three_lead[:3] == [64, 64, 64]
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
    for kind, beat, velocity in (("4/4", 2.0, 64), ("3/4", 2.0, 64), ("6/8", 2.0, 64)):
        _ctx_figure, _phrase, parts = _flat_figure(kind, 4)
        lead = [note for note in parts[0][0] if note.beat == pytest.approx(beat)]
        assert len(lead) == 1 and lead[0].velocity == velocity
    four, _phrase, call = _flat_figure("4/4", 4)
    tail = [note.velocity for note in call[0][0] if note.beat >= 2]
    assert tail == [64, 64 - _MICRO, 64 - _MICRO, 64 - _MICRO]
    weak_bass = [note for note in call[0][2] if note.beat == pytest.approx(3.5)]
    weak_support = [note for note in call[0][1] if note.beat == pytest.approx(3.5)]
    assert len(weak_bass) == 1 and weak_bass[0].velocity == 58
    assert len(weak_support) == 1 and weak_support[0].velocity == 54
    _ctx34, _phrase34, call34 = _flat_figure("3/4", 4)
    bass_five = [note for note in call34[0][2] if note.beat == pytest.approx(2.5)]
    support_five = [note for note in call34[0][1] if note.beat == pytest.approx(2.5)]
    support_four = [note for note in call34[0][1] if note.beat == pytest.approx(2.0)]
    assert len(bass_five) == 1 and bass_five[0].velocity == 58
    assert len(support_five) == 1 and support_five[0].velocity == 54
    assert len(support_four) == 1 and support_four[0].velocity == 56
    assert not any(note.beat == pytest.approx(0.0) for note in call[0][0])
    assert four.kind == "4/4"
    _ctx_figure, _phrase, fan = _flat_figure("4/4", 5)
    assert fan[0][0][0].velocity == 68
    assert fan[0][2][0].velocity == 64
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
    assert [note.velocity for note in slur] == [64 - 2 * _MICRO, 64 - _MICRO]


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


def test_figure_bars_keep_their_own_slur_and_grow_no_pickup(monkeypatch) -> None:
    _name_sonatina(monkeypatch)
    # 4/4 no longer selects Sonatina. The same four-bar hold on 3/4 is type 4.
    pitches = [72] * 24
    score = _render(
        pitches,
        (_joined(0, pitches, held=True),),
        chords={bar: C for bar in range(4)},
        kinds={bar: "phrase" for bar in range(4)},
        mode="major",
        character="calm",
        bpm=96,
        meter=METER_34,
    )
    call = [note for note in score.lead if note.bar == 0 and note.midi is not None]
    assert not any(note.beat == pytest.approx(0.0) for note in call)
    assert any(note.slur_start and note.beat == pytest.approx(1.5) for note in call)
    assert not any(
        note.midi is not None and note.duration_beats == pytest.approx(0.25) and note.beat == pytest.approx(3.75)
        for note in score.lead
    )
    answer = [note for note in score.lead if note.bar == 1 and note.midi is not None and note.beat == pytest.approx(0.0)]
    assert len(answer) == 1 and answer[0].duration_beats == pytest.approx(3.0)
    base = [note for note in score.lead if note.bar == 2 and note.beat == pytest.approx(0.0) and note.midi is not None]
    assert len(base) == 1 and base[0].duration_beats < 3


def _opening(lead, support, low, *, limit: float = 0.25) -> list[NoteEvent]:
    """Sounding attacks inside the first sixteenth. Rests do not count."""
    notes = [
        note
        for note in (*lead, *support, *low)
        if note.midi is not None and 0.0 <= note.beat < limit - 1e-9
    ]
    return sorted(notes, key=lambda note: (note.beat, -note.voice))


def _assert_eighth_roll(
    lead,
    support,
    low,
    *,
    lead_velocity: int | None = None,
    bass_velocity: int | None = None,
    support_velocity: int | None = None,
    accent: bool = True,
    min_strings: int = 5,
    max_strings: int = 6,
) -> None:
    opening = _opening(lead, support, low)
    bass = [note for note in opening if note.voice == 3]
    mids = [note for note in opening if note.voice == 2]
    highs = [note for note in opening if note.voice == 1]
    assert bass and mids and len(highs) == 1
    assert min_strings <= len(opening) <= max_strings
    assert all(note.beat == pytest.approx(0.0) and note.duration_beats == pytest.approx(0.5) for note in bass)
    assert all(
        note.beat == pytest.approx(1 / 12) and note.duration_beats == pytest.approx(5 / 12) for note in mids
    )
    assert highs[0].beat == pytest.approx(2 / 12)
    assert highs[0].duration_beats == pytest.approx(4 / 12)
    assert all(note.beat + note.duration_beats == pytest.approx(0.5) for note in opening)
    assert highs[0].accent is accent
    # The volume wave moves a finished score. Written levels are the figure's.
    if lead_velocity is not None:
        assert highs[0].velocity == lead_velocity
    if bass_velocity is not None:
        assert {note.velocity for note in bass} == {bass_velocity}
    if support_velocity is not None:
        assert {note.velocity for note in mids} == {support_velocity}


def _assert_type7_roll(lead, support, low, bar_beats: float, *, written: bool = False) -> None:
    opening = _opening(lead, support, low)
    bass = [note for note in opening if note.voice == 3]
    mids = [note for note in opening if note.voice == 2]
    highs = [note for note in opening if note.voice == 1]
    assert len(bass) == 1 and 1 <= len(mids) <= 2 and len(highs) == 1
    assert 3 <= len(opening) <= 4
    assert bass[0].beat == pytest.approx(0.0) and bass[0].duration_beats == pytest.approx(0.5)
    assert all(
        note.beat == pytest.approx(1 / 12) and note.duration_beats == pytest.approx(5 / 12) for note in mids
    )
    assert highs[0].beat == pytest.approx(2 / 12)
    assert highs[0].duration_beats == pytest.approx(bar_beats - 2 / 12)
    assert highs[0].beat + highs[0].duration_beats == pytest.approx(bar_beats)
    assert highs[0].accent
    if written:
        assert highs[0].velocity == 64
        assert {note.velocity for note in mids} == {54}
        assert bass[0].velocity == 60


def _assert_block(lead, support, low) -> None:
    """Every attack in the first sixteenth shares the downbeat.

    A carried bass leaves only the lead there. That lead is still not rolled.
    """
    opening = _opening(lead, support, low)
    assert opening
    assert all(note.beat == pytest.approx(0.0) for note in opening)


_UNISON = Chord("C", "C", "major", "", (60,))


def _pattern_score(kind: str, pattern: str, *, character: str, bpm: int, bars: int = 4):
    meter, epb, _strong, _beats = _FIGURE_METERS[kind]
    row = [72] * (epb * bars)
    return _render(
        row,
        (_joined(0, row),),
        chords={bar: C for bar in range(bars)},
        kinds={bar: "phrase" for bar in range(bars)},
        mode="major",
        character=character,
        bpm=bpm,
        meter=meter,
    )


def _engrave(ctx, parts) -> Score:
    """Fill a figure the way the score renderer does, on the twelfth grid."""
    score = _figure_score(ctx, parts, ctx.bars)
    epb = ctx.epb
    return replace(
        score,
        lead=tuple(_fill(list(score.lead), score.bars, epb, 1)),
        support=tuple(_fill_voices(list(score.support), score.bars, epb, 2)),
        low=tuple(_fill(list(score.low), score.bars, epb, 3)),
        divisions=12,
    )


def _streams(measure: ET.Element) -> list[list[ET.Element]]:
    streams: list[list[ET.Element]] = [[]]
    for child in measure:
        if child.tag == "backup":
            streams.append([])
        elif child.tag in {"note", "forward"}:
            streams[-1].append(child)
    return streams


def _first_attack(stream: list[ET.Element]) -> ET.Element:
    for note in stream:
        if note.tag == "note" and note.find("rest") is None:
            return note
    raise AssertionError("voice has no sounding note")


def _assert_measures_sum(score: Score) -> None:
    root = ET.fromstring(score_to_musicxml(score))
    expected = int(round(score.bar_beats * score.divisions))
    for measure in root.find("part").findall("measure"):
        for stream in _streams(measure):
            total = 0
            for item in stream:
                if item.tag == "forward" or (item.tag == "note" and item.find("chord") is None):
                    total += int(item.find("duration").text)
            assert total == expected


def _assert_tied_fifth(stream: list[ET.Element]) -> None:
    """A 5-unit chord is a 32nd triplet rest, then tied 32nds, then tied eighths."""
    rest = stream[0]
    assert rest.tag == "note" and rest.find("rest") is not None
    assert rest.find("duration").text == "1"
    assert rest.find("type").text == "32nd"
    assert _time_modification(rest) == ("3", "2", "32nd")
    index = 1
    heads: list[ET.Element] = []
    while (
        index < len(stream)
        and stream[index].tag == "note"
        and stream[index].find("rest") is None
        and stream[index].find("duration").text == "1"
    ):
        heads.append(stream[index])
        index += 1
    tails: list[ET.Element] = []
    while (
        index < len(stream)
        and stream[index].tag == "note"
        and stream[index].find("duration").text == "4"
    ):
        tails.append(stream[index])
        index += 1
    assert heads and len(heads) == len(tails)
    for place, head in enumerate(heads):
        assert head.find("type").text == "32nd"
        assert head.find("tie").get("type") == "start"
        assert (head.find("chord") is not None) is (place > 0)
        assert head.get("dynamics") == heads[0].get("dynamics") and head.get("dynamics") is not None
        assert head.find("dot") is None
        assert _time_modification(head) == ("3", "2", "32nd")
    for place, tail in enumerate(tails):
        assert tail.find("type").text == "eighth"
        assert [tie.get("type") for tie in tail.findall("tie")] == ["stop"]
        assert (tail.find("chord") is not None) is (place > 0)
        assert tail.get("dynamics") == heads[0].get("dynamics")
        assert tail.find("dot") is None
        assert _time_modification(tail) == ("3", "2", "32nd")


def _assert_eighth_xml(measure: ET.Element) -> None:
    lead, support, bass = _streams(measure)[0], _streams(measure)[1], _streams(measure)[-1]
    assert bass[0].tag == "note" and bass[0].find("rest") is None
    assert (bass[0].find("duration").text, bass[0].find("type").text) == ("6", "eighth")
    assert bass[0].find("dot") is None and bass[0].find("time-modification") is None
    place = 1
    while place < len(bass) and bass[place].find("chord") is not None:
        assert bass[place].find("duration").text == "6"
        assert bass[place].find("time-modification") is None
        place += 1
    lead_note = _first_attack(lead)
    assert (lead_note.find("duration").text, lead_note.find("type").text) == ("4", "eighth")
    assert lead_note.find("dot") is None
    assert _time_modification(lead_note) == ("3", "2", "16th")
    assert lead[0].find("rest") is not None
    assert lead[0].find("duration").text == "2"
    assert lead[0].find("type").text == "16th"
    assert _time_modification(lead[0]) == ("3", "2", "16th")
    _assert_tied_fifth(support)
    _assert_complete_tuplets(measure)


def _time_modification(note: ET.Element) -> tuple[str, str, str]:
    modification = note.find("time-modification")
    assert modification is not None
    return (
        modification.find("actual-notes").text,
        modification.find("normal-notes").text,
        modification.find("normal-type").text,
    )


def _assert_plain_tail(notes: list[ET.Element], kind: str) -> None:
    if kind == "4/4":
        expect = (("36", "half", True), ("6", "eighth", False))
    else:
        expect = (("24", "half", False), ("6", "eighth", False))
    assert len(notes) == len(expect)
    for note, (duration, note_type, dotted) in zip(notes, expect):
        assert note.find("duration").text == duration
        assert note.find("type").text == note_type
        assert (note.find("dot") is not None) is dotted
        assert note.find("time-modification") is None
        assert note.find("chord") is None
    assert [tie.get("type") for tie in notes[0].findall("tie")] == ["stop", "start"]
    assert [tie.get("type") for tie in notes[-1].findall("tie")] == ["stop"]


def _assert_complete_tuplets(measure: ET.Element) -> None:
    """A rasgueado eighth is a finished 3:2. No forward, and no 24:23 hold."""
    assert not any(child.tag == "forward" for child in measure.iter())
    for note in measure.iter("note"):
        modification = note.find("time-modification")
        if modification is None:
            continue
        assert modification.find("actual-notes").text in {"3", "6"}
        if modification.find("actual-notes").text == "3":
            assert modification.find("normal-notes").text == "2"


def _assert_held_lead_xml(measure: ET.Element, units: int, kind: str) -> None:
    lead_stream = _streams(measure)[0]
    assert all(item.tag != "forward" for item in lead_stream)
    bar_units = 48 if kind == "4/4" else 36
    if units == bar_units - 2:
        rest, head = lead_stream[0], lead_stream[1]
        assert rest.find("rest") is not None
        assert rest.find("duration").text == "2"
        assert rest.find("type").text == "16th"
        assert _time_modification(rest) == ("3", "2", "16th")
        assert head.find("rest") is None
        assert (head.find("duration").text, head.find("type").text) == ("4", "eighth")
        assert [tie.get("type") for tie in head.findall("tie")] == ["start"]
        assert _time_modification(head) == ("3", "2", "16th")
        _assert_plain_tail(lead_stream[2:], kind)
    elif units == bar_units - 1:
        rest, head, eighth = lead_stream[0], lead_stream[1], lead_stream[2]
        assert rest.find("rest") is not None
        assert rest.find("duration").text == "1"
        assert rest.find("type").text == "32nd"
        assert _time_modification(rest) == ("3", "2", "32nd")
        assert (head.find("duration").text, head.find("type").text) == ("1", "32nd")
        assert [tie.get("type") for tie in head.findall("tie")] == ["start"]
        assert _time_modification(head) == ("3", "2", "32nd")
        assert (eighth.find("duration").text, eighth.find("type").text) == ("4", "eighth")
        assert [tie.get("type") for tie in eighth.findall("tie")] == ["stop", "start"]
        assert _time_modification(eighth) == ("3", "2", "32nd")
        _assert_plain_tail(lead_stream[3:], kind)
    else:
        raise AssertionError(units)
    _assert_complete_tuplets(measure)


@pytest.mark.parametrize("kind", ["4/4", "3/4", "6/8"])
def test_rolled_rasgueado_onsets_releases_and_block_chords(kind: str) -> None:
    """Section 4.9: five rolls, and every other chord still speaks together."""
    assert _rasgueado_onsets([1, 2, 3]) == {3: 0.0, 2: 1 / 12, 1: 2 / 12}
    assert _rasgueado_onsets([1, 3]) == {3: 0.0, 1: 1 / 12}
    assert _rasgueado_onsets([2, 1]) == {2: 0.0, 1: 1 / 12}
    assert _rasgueado_onsets([1]) == {1: 0.0}
    _meter, _epb, _strong, bar_beats = _FIGURE_METERS[kind]

    _ctx2, _phrase2, type2 = _flat_figure(kind, 2)
    _assert_eighth_roll(
        *type2[0],
        lead_velocity=64,
        bass_velocity=60,
        support_velocity=54,
        accent=False,
        min_strings=3,
        max_strings=4,
    )
    _assert_block(*type2[1])
    meter, epb, _strong, _beats = _FIGURE_METERS[kind]
    dance_phrase = _joined(0, [72] * (_FIGURE_BARS[2] * epb), held=True)
    dance_ctx = _many(
        (dance_phrase,),
        kind=kind,
        bpm=72,
        chord=C,
        melody=[72] * (_FIGURE_BARS[2] * epb),
    )
    with compose_meter(meter):
        danced = render_torroba_figure(
            dance_ctx, 0, dance_phrase, "fandanguillo", 2, index=0, count=2, next_figure=2
        )
    _assert_eighth_roll(
        *danced,
        lead_velocity=68,
        bass_velocity=64,
        support_velocity=56,
        accent=True,
    )

    _ctx3, _phrase3, type3 = _flat_figure(kind, 3)
    _assert_eighth_roll(
        *type3[0],
        lead_velocity=64,
        bass_velocity=60,
        support_velocity=54,
        accent=False,
        min_strings=3,
        max_strings=4,
    )

    _ctx5, _phrase5, type5 = _flat_figure(kind, 5)
    _assert_eighth_roll(*type5[0], lead_velocity=68, bass_velocity=64, support_velocity=56)
    _assert_block(*type5[3])

    _ctx7, _phrase7, type7 = _flat_figure(kind, 7)
    for index in range(4):
        _assert_block(*type7[index])
    _assert_type7_roll(*type7[4], bar_beats, written=True)

    _ctx8, _phrase8, type8 = _flat_figure(kind, 8)
    _assert_block(*type8[0])
    _assert_block(*type8[1])

    _ctx4, _phrase4, type4 = _flat_figure(kind, 4)
    _assert_block(*type4[0])
    assert not any(note.beat < 0.25 and note.midi is not None for note in type4[0][0])

    if kind != "4/4":
        _ctx6, _phrase6, type6 = _flat_figure(kind, 6)
        _assert_block(*type6[0])
        assert {note.voice for note in _opening(*type6[0])} >= {1, 2, 3}
        _assert_block(*type6[1])
        _assert_block(*type6[2])
        opened = _opening(*type6[2])
        assert [note.voice for note in opened] == [3, 2]
        assert all(note.duration_beats == pytest.approx(0.25) for note in opened)

    _meter, epb, strong, _beats = _FIGURE_METERS[kind]
    # Held, so the downbeat is not a close and the beds stay 68 / 64 / 56.
    phrase = _joined(0, [72] * epb, held=True)
    grid = _ctx(
        melody=[72] * epb,
        phrase=phrase,
        kind=kind,
        epb=epb,
        strong=strong,
        character="volatile",
        bar_beats=bar_beats,
        chord=C,
    )
    with compose_meter(meter):
        dance = _render_torroba_bar(grid, 0, phrase, "fandanguillo")
    _assert_eighth_roll(*dance, lead_velocity=68, bass_velocity=64, support_velocity=56)
    assert_playable(_figure_score(grid, [dance], 1), profiles="torroba")

    if kind != "4/4":
        danza_ctx = replace(grid, character="calm")
        with compose_meter(meter):
            danza = _render_torroba_bar(danza_ctx, 0, phrase, "danza")
        _assert_block(*danza)
        opened = _opening(*danza)
        assert opened
        assert all(note.staccato for note in opened if note.voice != 3)
        assert all(not note.staccato for note in opened if note.voice == 3)
        assert_playable(_figure_score(danza_ctx, [danza], 1), profiles="torroba")


def test_two_voice_roll_closes_the_gap_and_a_lone_lead_stays_on_the_beat() -> None:
    for kind in ("4/4", "3/4", "6/8"):
        _meter, _epb, _strong, bar_beats = _FIGURE_METERS[kind]
        _ctx2, _phrase2, type2 = _flat_figure(kind, 2, midi=59, chord=_UNISON)
        pair = _opening(*type2[0])
        assert [note.voice for note in pair] == [3, 1]
        assert [note.beat for note in pair] == pytest.approx([0.0, 1 / 12])
        assert [note.duration_beats for note in pair] == pytest.approx([0.5, 5 / 12])
        block = _opening(*type2[1])
        assert [note.voice for note in block] == [3, 1]
        assert all(note.beat == pytest.approx(0.0) for note in block)

        _ctx7, phrase7, type7 = _flat_figure(kind, 7, midi=59, chord=_UNISON)
        held = _opening(*type7[4])
        assert [note.voice for note in held] == [3, 1]
        assert [note.beat for note in held] == pytest.approx([0.0, 1 / 12])
        assert [note.duration_beats for note in held] == pytest.approx([0.5, bar_beats - 1 / 12])
        for index in range(4):
            earlier = _opening(*type7[index])
            assert earlier
            assert all(note.beat == pytest.approx(0.0) for note in earlier)

        meter = _FIGURE_METERS[kind][0]
        with compose_meter(meter):
            missing_bass = _Pen(
                _ctx7, 4, phrase7, "castillo", index=4, count=5, next_figure=None
            )
            missing_bass.rasgueado(
                [
                    (3, None, 60, 0, {}),
                    (2, 55, 56, 0, {}),
                    (1, 72, 64, 0, {"accent": True}),
                ],
                {3: 0.5, 2: 0.5, 1: missing_bass.beats},
            )
            lead, support, low = missing_bass.finish()
            alone = _Pen(_ctx7, 0, phrase7, "castillo", index=0, count=5, next_figure=None)
            alone.rasgueado(
                [
                    (3, None, 60, 0, {}),
                    (2, None, 56, 0, {}),
                    (1, 72, 64, 0, {"accent": True}),
                ],
                {3: 0.5, 2: 0.5, 1: 0.5},
            )
            only_lead, only_support, only_low = alone.finish()
        assert low == []
        assert [note.beat for note in (*support, *lead)] == pytest.approx([0.0, 1 / 12])
        assert support[0].duration_beats == pytest.approx(0.5)
        assert lead[0].duration_beats == pytest.approx(missing_bass.beats - 1 / 12)
        assert only_support == [] and only_low == []
        assert only_lead[0].beat == pytest.approx(0.0)
        assert only_lead[0].duration_beats == pytest.approx(0.5)


def test_type_1_bass_cuts_at_the_barline_before_a_rolled_successor() -> None:
    phrase = _joined(0, [72] * 16, held=True)
    ctx = _many((phrase,), melody=[72] * 16)
    for nxt in (None, 2, 3, 5, 7):
        with compose_meter(METER_44):
            _lead, _support, bass = render_torroba_figure(
                ctx, 0, phrase, "sonatina", 1, index=0, count=1, next_figure=nxt
            )
        cut = max(bass, key=lambda note: note.beat)
        assert cut.beat == pytest.approx(2.25)
        assert cut.duration_beats == pytest.approx(1.75)


@pytest.mark.parametrize("kind", ["4/4", "3/4", "6/8"])
def test_rolled_chord_scores_engrave_on_division_12(kind: str) -> None:
    meter, epb, _strong, bar_beats = _FIGURE_METERS[kind]
    if kind == "6/8":
        dance = _pattern_score(kind, "fandanguillo", character="volatile", bpm=96)
        assert dance.divisions == 12
        _assert_eighth_roll(
            [note for note in dance.lead if note.bar == 0],
            [note for note in dance.support if note.bar == 0],
            [note for note in dance.low if note.bar == 0],
        )
        assert_playable(dance, profiles="torroba")
        _assert_measures_sum(dance)
        root = ET.fromstring(score_to_musicxml(dance))
        _assert_eighth_xml(root.find("part").findall("measure")[0])
    else:
        other = _pattern_score(kind, "olite", character="volatile", bpm=96)
        assert other.divisions != 12
        assert_playable(other, profiles="torroba")

    if kind == "6/8":
        calm = _pattern_score(kind, "danza", character="calm", bpm=72, bars=5)
        assert calm.divisions != 12
        assert_playable(calm, profiles="torroba")
    elif kind == "4/4":
        # Rally's bridge is Castillo, so a five-bar phrase still engraves Arada.
        row = [72] * (epb * 5)
        slow = _render(
            row,
            (_joined(0, row),),
            chords={bar: C for bar in range(5)},
            kinds={bar: "phrase" for bar in range(5)},
            mode="major",
            character="rally",
            bpm=72,
            meter=meter,
            sections=(FormSection(0, 5, "phrase", 0, bridge=True),),
        )
        assert slow.divisions == 12
        for bar in range(4):
            _assert_block(
                [note for note in slow.lead if note.bar == bar],
                [note for note in slow.support if note.bar == bar],
                [note for note in slow.low if note.bar == bar],
            )
        _assert_type7_roll(
            [note for note in slow.lead if note.bar == 4],
            [note for note in slow.support if note.bar == 4],
            [note for note in slow.low if note.bar == 4],
            bar_beats,
        )
        assert_playable(slow, profiles="torroba")
        _assert_measures_sum(slow)
        slow_root = ET.fromstring(score_to_musicxml(slow))
        bar5 = slow_root.find("part").findall("measure")[4]
        _assert_held_lead_xml(bar5, epb * 6 - 2, kind)
        bass_note = _first_attack(_streams(bar5)[-1])
        assert (bass_note.find("duration").text, bass_note.find("type").text) == ("6", "eighth")
        assert bass_note.find("dot") is None
        assert bass_note.find("time-modification") is None
        _assert_tied_fifth(_streams(bar5)[1])
    else:
        # 3/4 Castillo opens with the rasgueado of `CASTILLO_WALK` (divisions=12).
        # A 1-bar phrase stays on the base grid (divisions != 12).
        slow = _pattern_score(kind, "castillo", character="calm", bpm=72, bars=5)
        assert slow.divisions == 12
        _assert_eighth_roll(
            [note for note in slow.lead if note.bar == 0],
            [note for note in slow.support if note.bar == 0],
            [note for note in slow.low if note.bar == 0],
        )
        assert_playable(slow, profiles="torroba")
        _assert_measures_sum(slow)
        one_bar = _pattern_score(kind, "castillo", character="calm", bpm=72, bars=1)
        assert one_bar.divisions != 12
        lead = [note for note in one_bar.lead if note.bar == 0 and note.midi is not None]
        assert len(lead) == 1
        assert lead[0].beat == pytest.approx(0.0)
        assert lead[0].duration_beats == pytest.approx(3.0)
        bass = [note for note in one_bar.low if note.bar == 0 and note.beat == pytest.approx(0.0)]
        assert len(bass) == 1 and bass[0].duration_beats == pytest.approx(1.5)
        assert_playable(one_bar, profiles="torroba")

    _ctx2, _phrase2, pair_parts = _flat_figure(kind, 2, midi=59, chord=_UNISON)
    pair_score = _engrave(_ctx2, pair_parts)
    assert pair_score.divisions == 12
    _assert_measures_sum(pair_score)
    pair_bar = ET.fromstring(score_to_musicxml(pair_score)).find("part").findall("measure")[0]
    pair_bass = _first_attack(_streams(pair_bar)[-1])
    _assert_tied_fifth(_streams(pair_bar)[0])
    assert pair_bass.find("duration").text == "6"
    assert pair_bass.find("time-modification") is None

    _ctx7, _phrase7, held_parts = _flat_figure(kind, 7, midi=59, chord=_UNISON)
    held_score = _engrave(_ctx7, held_parts)
    _assert_measures_sum(held_score)
    held_bar = ET.fromstring(score_to_musicxml(held_score)).find("part").findall("measure")[4]
    _assert_held_lead_xml(held_bar, epb * 6 - 1, kind)
    assert _first_attack(_streams(held_bar)[-1]).find("duration").text == "6"
    opening_rest = _streams(held_bar)[0][0]
    assert opening_rest.find("rest") is not None
    assert opening_rest.find("duration").text == "1"
    assert opening_rest.find("type").text == "32nd"

    # 3/4 calm above 72 is Sonatina. Selloff stays Castillo (with `CASTILLO_WALK` on 3/4).
    quiet_character = "selloff" if kind in {"4/4", "3/4"} else "calm"
    quiet = _pattern_score(kind, "castillo", character=quiet_character, bpm=96)
    if kind == "3/4":
        assert quiet.divisions == 12
    else:
        assert quiet.divisions != 12
    assert_playable(quiet, profiles="torroba")
    assert meter.eighths_per_bar == epb


def _framed_scherzo(character: str):
    pitches = [72] * 48
    return _render(
        pitches,
        (
            _joined(0, pitches[:6], held=True),
            _joined(6, pitches[6:42]),
            _joined(42, pitches[42:], held=True),
        ),
        chords={bar: C for bar in range(8)},
        kinds={0: "intro", 7: "outro", **{bar: "phrase" for bar in range(1, 7)}},
        mode="major",
        character=character,
        bpm=96,
        meter=METER_68,
        sections=(
            FormSection(0, 1, "intro", 0),
            FormSection(1, 7, "phrase", 0),
            FormSection(7, 8, "outro", 0),
        ),
    )


def test_intro_and_danza_stay_block_chords_when_a_roll_sets_division_12() -> None:
    framed = _framed_scherzo("volatile")
    assert framed.divisions == 12
    for bar in (0, 7):
        _assert_block(
            [note for note in framed.lead if note.bar == bar],
            [note for note in framed.support if note.bar == bar],
            [note for note in framed.low if note.bar == bar],
        )
    _assert_eighth_roll(
        [note for note in framed.lead if note.bar == 1],
        [note for note in framed.support if note.bar == 1],
        [note for note in framed.low if note.bar == 1],
    )
    assert_playable(framed, profiles="torroba")
    _assert_measures_sum(framed)

    danza = _framed_scherzo("calm")
    assert danza.divisions != 12
    body = _opening(
        [note for note in danza.lead if note.bar == 1],
        [note for note in danza.support if note.bar == 1],
        [note for note in danza.low if note.bar == 1],
    )
    assert body and all(note.beat == pytest.approx(0.0) for note in body)
    assert_playable(danza, profiles="torroba")


def _assert_type7_bar5_kept(score: Score, bar: int) -> None:
    """The rolled lead and the seven-eighth bass run survive boundary rewrites."""
    rolled = [
        note
        for note in score.lead
        if note.bar == bar and note.midi is not None and note.beat < 0.25
    ]
    assert len(rolled) == 1
    assert rolled[0].beat == pytest.approx(2 / 12)
    assert rolled[0].duration_beats == pytest.approx(score.bar_beats - 2 / 12)
    running = sorted(
        (
            note
            for note in score.low
            if note.bar == bar and note.midi is not None and note.beat >= 0.5 - 1e-9
        ),
        key=lambda note: note.beat,
    )
    assert [round(note.beat, 2) for note in running] == [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    assert all(note.duration_beats == pytest.approx(0.5) for note in running)
    # Steps -1, -1, -1, -1, -2, -2, -1. One bar center shifts them together.
    base = running[0].velocity
    assert [note.velocity - base for note in running] == [0, 0, 0, 0, -2, -2, 0]
    assert running[-1].midi % 12 == C.pitches[0] % 12


def test_type_7_bar_5_keeps_the_roll_across_a_boundary_and_a_pattern_change() -> None:
    framed = _render(
        [72] * 56,
        (_joined(0, [72] * 8, held=True), _joined(8, [72] * 40), _joined(48, [72] * 8)),
        chords={bar: C for bar in range(7)},
        kinds={0: "intro", **{bar: "phrase" for bar in range(1, 6)}, 6: "outro"},
        mode="major",
        character="rally",
        bpm=72,
        sections=(
            FormSection(0, 1, "intro", 0),
            FormSection(1, 6, "phrase", 0, bridge=True),
            FormSection(6, 7, "outro", 0),
        ),
    )
    _assert_type7_bar5_kept(framed, 5)
    assert_playable(framed, profiles="torroba")

    crossed = _render(
        [72] * 48,
        (_joined(0, [72] * 40), _joined(40, [72] * 8)),
        chords={bar: C for bar in range(6)},
        kinds={bar: "phrase" for bar in range(6)},
        mode="major",
        character="rally",
        bpm=72,
        sections=(
            FormSection(0, 5, "phrase", 0, bridge=True),
            FormSection(5, 6, "phrase", 1),
        ),
    )
    _assert_type7_bar5_kept(crossed, 4)
    assert_playable(crossed, profiles="torroba")


def test_block_drops_a_bass_the_melody_cannot_fret() -> None:
    """F2 under a high price does not fit a block chord. A fan may still fret higher Fs."""
    only_f = Chord("F", "F", "major", "", (65,))
    cases = (
        ("fandanguillo", "4/4", METER_44, 8, (0, 4), 4.0),
        ("danza", "6/8", METER_68, 6, (0, 3), 3.0),
    )
    for pattern, kind, meter, epb, strong, bar_beats in cases:
        phrase = _joined(0, [76] * epb, held=True)
        ctx = _ctx(
            melody=[76] * epb,
            phrase=phrase,
            kind=kind,
            epb=epb,
            strong=strong,
            character="volatile" if pattern == "fandanguillo" else "calm",
            bar_beats=bar_beats,
            chord=only_f,
        )
        with compose_meter(meter):
            lead, support, low = _render_torroba_bar(ctx, 0, phrase, pattern)
        opening = _opening(lead, support, low)
        if pattern == "danza":
            assert low == []
            assert len(opening) == 1 and opening[0].voice == 1
            assert opening[0].beat == pytest.approx(0.0)
        else:
            assert sorted(note.midi for note in opening) == [53, 65, 76]
            assert [note.voice for note in opening] == [3, 2, 1]
            assert [note.beat for note in opening] == pytest.approx([0.0, 1 / 12, 2 / 12])
        assert_playable(_figure_score(ctx, [(lead, support, low)], 2), profiles="torroba")


def test_fandanguillo_phrase_gate_bass_intervals_chord_dynamics_and_scale_arrival() -> None:
    """Lock the four BKC 1M rasgueado cleanups."""
    from app.sonify.guitar_scale_passages import _stamp_arrival
    from app.sonify.guitar_torroba import _rasgueado_voicing

    # 1. Multi-bar phrase rolls bar 0 and keeps bar 1 a block chord; 1-bar phrases
    # in a multi-phrase score (even when total bars <= 4) stay block chords.
    long_phrase = _joined(0, [72] * 16, held=True)
    long_ctx = _with_phrases(
        _ctx(melody=[72] * 16, phrase=long_phrase, character="volatile", bars=2, chord=C),
        (long_phrase,),
    )
    with compose_meter(METER_44):
        bar0 = _render_torroba_bar(long_ctx, 0, long_phrase, "fandanguillo")
        bar1 = _render_torroba_bar(long_ctx, 1, long_phrase, "fandanguillo")
    _assert_eighth_roll(*bar0, lead_velocity=68, accent=True)
    _assert_block(*bar1)

    short_phrases = tuple(_joined(bar * 8, [72] * 8, held=True) for bar in range(4))
    short_ctx = _with_phrases(
        _ctx(melody=[72] * 32, phrase=short_phrases[0], character="volatile", bars=4, chord=C),
        short_phrases,
    )
    with compose_meter(METER_44):
        for bar, phrase in enumerate(short_phrases):
            _assert_block(*_render_torroba_bar(short_ctx, bar, phrase, "fandanguillo"))

    # 2. Two bass notes are only 4th, 5th, or octave; adjacent strings stay >= 3 semitones apart.
    for chord in (C, CM, G, G7, FM, AF, BF, F, AM, EM, DM, DM7):
        chk_ctx = _ctx(melody=[72] * 8, phrase=_joined(0, [72] * 8), chord=chord)
        bass, support, lead = _rasgueado_voicing(chk_ctx, 0, 72, 6)
        if len(bass) == 2:
            assert (bass[1] - bass[0]) in {5, 7, 12}
        full = [*bass, *support, lead]
        assert all(right - left >= 3 for left, right in zip(full, full[1:]))
    c_bass, c_sup, c_lead = _rasgueado_voicing(
        _ctx(melody=[72] * 8, phrase=_joined(0, [72] * 8), chord=C), 0, 72, 6
    )
    assert [*c_bass, *c_sup, c_lead] == [40, 52, 55, 60, 67, 72]

    # 3. Every head and tail note of `_add_tied_fifth` carries the exact dynamics string (56 -> "62.22").
    flat_score = _engrave(long_ctx, [bar0, bar1])
    measure0 = ET.fromstring(score_to_musicxml(flat_score)).find("part").findall("measure")[0]
    support_stream = _streams(measure0)[1]
    tied_notes = [
        item for item in support_stream if item.tag == "note" and item.find("rest") is None and int(item.find("duration").text) in {1, 4}
    ]
    assert len(tied_notes) == 6
    assert all(note.get("dynamics") == "62.22" for note in tied_notes)

    # 4. `_stamp_arrival` on a rolled downbeat keeps the 2/12 offset, 4/12 duration, and roll velocity.
    rolled_lead = [
        NoteEvent(bar=1, beat=2 / 12, midi=72, duration_beats=4 / 12, voice=1, velocity=68, accent=True),
        NoteEvent(bar=1, beat=1.0, midi=72, duration_beats=0.5, voice=1, velocity=64),
    ]
    for arrival_vel in (46, 74):
        stamped = _stamp_arrival(rolled_lead, 8, 74, arrival_vel, 8)
        assert stamped[0].beat == pytest.approx(2 / 12)
        assert stamped[0].duration_beats == pytest.approx(4 / 12)
        assert stamped[0].midi == 74
        assert stamped[0].velocity == 68
        assert stamped[0].accent is True


def _beats(notes: list[NoteEvent]) -> list[float]:
    return [round(note.beat, 4) for note in notes]


def test_castillos_mood_table_and_printed_names() -> None:
    assert pattern_title("torroba_tremolo", "torroba") == "Juglar"
    assert pattern_title("alcaniz", "torroba") == "Alcaniz"
    assert pattern_title("olite", "torroba") == "Olite"
    assert pattern_title("tremolo", "barrios") == "Tremolo"
    assert pattern_form(["castillo", "torroba_tremolo", "castillo"], "torroba") == "Castillo — Juglar — Castillo"
    assert "zafra" not in _FIGURES and "redaba" not in _FIGURES
    assert "zafra" not in _FAMILY and "redaba" not in _FAMILY
    named = " ".join(getattr(fn, "__name__", "") for fn in _FIGURES.values())
    assert "zafra" not in named and "redaba" not in named
    assert {9, 10, 11, 12} <= set(_FIGURES)

    four = _ctx(melody=[64] * 8, phrase=_joined(0, [64] * 8), kind="4/4", bpm=96)
    for mood in ("calm", "rally", "selloff", "volatile"):
        assert _torroba_primary(four, mood, framed_macro=True) != "danza"
        assert _torroba_primary(four, mood, framed_macro=False) != "danza"
    assert _torroba_primary(four, "calm", framed_macro=True) == "olite"
    assert _torroba_primary(four, "selloff", framed_macro=True) == "olite"
    assert _torroba_contrast(four, "sonatina") == "castillo"
    assert _torroba_primary(four, "rally", framed_macro=True) == "olite"
    assert _torroba_primary(four, "volatile", framed_macro=True) == "olite"
    assert _torroba_primary(four, "rally", framed_macro=False) == "olite"
    assert _torroba_contrast(four, "castillo") == "olite"
    assert _torroba_contrast(four, "olite") == "castillo"
    waltz = _ctx(melody=[64] * 6, phrase=_joined(0, [64] * 6), kind="3/4", epb=6, strong=(0,), bpm=72, bar_beats=3)
    assert _torroba_primary(waltz, "calm") == "castillo"
    assert _torroba_primary(waltz, "rally") == "torroba_tremolo"
    assert _torroba_primary(waltz, "selloff") == "castillo"
    assert _torroba_primary(waltz, "volatile") == "danza"
    fast_waltz = replace(waltz, bpm=96)
    # The `bpm > 72` gate is gone: calm 3/4 is Castillo — Juglar — Castillo at
    # every tempo, because the Juglar density follows the tempo by itself.
    assert _torroba_primary(fast_waltz, "calm") == "castillo"
    assert _torroba_contrast(fast_waltz, "castillo", "calm") == "torroba_tremolo"
    for bpm in (60, 72, 96, 120, 140):
        tempo_waltz = replace(waltz, bpm=bpm)
        assert _torroba_primary(tempo_waltz, "calm") == "castillo"
        assert _torroba_contrast(tempo_waltz, "castillo", "calm") == "torroba_tremolo"
        assert _torroba_primary(tempo_waltz, "selloff") == "castillo"
        assert _torroba_contrast(tempo_waltz, "castillo", "selloff") == "danza"
        assert _torroba_contrast(tempo_waltz, "sonatina", "calm") == "castillo"
    assert _torroba_contrast(replace(waltz, character="calm"), "castillo", "calm") == "torroba_tremolo"
    assert _torroba_contrast(replace(waltz, character="selloff"), "castillo", "selloff") == "danza"
    assert _torroba_contrast(waltz, "torroba_tremolo") == "danza"
    assert _torroba_contrast(waltz, "danza") == "torroba_tremolo"

    scherzo = _ctx(
        melody=[64] * 6,
        phrase=_joined(0, [64] * 6),
        kind="6/8",
        epb=6,
        strong=(0, 3),
        bpm=96,
        bar_beats=3,
    )
    assert _torroba_primary(scherzo, "calm", framed_macro=True) == "danza"
    assert _torroba_primary(scherzo, "rally", framed_macro=True) == "alcaniz"
    assert _torroba_primary(scherzo, "volatile", framed_macro=True) == "fandanguillo"
    assert _torroba_primary(scherzo, "selloff", framed_macro=True) == "fandanguillo"
    assert _torroba_primary(scherzo, "rally", framed_macro=False) == "alcaniz"
    assert _torroba_contrast(scherzo, "alcaniz") == "danza"
    assert _torroba_contrast(scherzo, "fandanguillo") == "danza"
    assert _torroba_contrast(scherzo, "danza") == "alcaniz"
    assert _torroba_contrast(scherzo, "castillo") == "castillo"

    juglar = profile_for("torroba", "torroba_tremolo")
    sonatina = profile_for("torroba", "sonatina")
    alcaniz = profile_for("torroba", "alcaniz")
    olite = profile_for("torroba", "olite")
    danza = profile_for("torroba", "danza")
    assert juglar is not None and sonatina is not None
    assert juglar.snap_calm is None and juglar.snap_wide is None
    assert (juglar.max_units_per_phrase, juglar.max_units_per_sec) == (0, 0)
    assert alcaniz is not None and danza is not None and olite is not None
    assert (alcaniz.snap_calm, alcaniz.snap_wide, alcaniz.max_units_per_sec) == (70, 73, 3)
    assert (olite.snap_calm, olite.snap_wide, olite.max_units_per_sec) == (70, 73, 3)
    assert (danza.snap_calm, danza.snap_wide) == (70, 73)


def test_juglar_never_stands_alone_in_a_waltz_movement() -> None:
    """Juglar is always framed by an idiom (tempo plan §6, rule 1).

    A 3/4 movement may open on `torroba_tremolo` (rally), but its contrast is
    Danza; calm opens on Castillo with Juglar in the middle, and volatile opens
    on Danza whose contrast is Juglar. Only a selloff waltz sings no Juglar at
    all. No tempo changes that: the frame is a table, not a BPM gate.
    """
    waltz = _ctx(
        melody=[64] * 6,
        phrase=_joined(0, [64] * 6),
        kind="3/4",
        epb=6,
        strong=(0,),
        bpm=96,
        bar_beats=3,
    )
    for bpm in (72, 96, 112, 124, 140):
        ctx = replace(waltz, bpm=bpm)
        juglar_moods: list[str] = []
        for mood in ("calm", "rally", "selloff", "volatile"):
            primary = _torroba_primary(ctx, mood)
            contrast = _torroba_contrast(ctx, primary, mood)
            assert primary != contrast, (bpm, mood, primary)
            if "torroba_tremolo" in (primary, contrast):
                juglar_moods.append(mood)
        assert juglar_moods == ["calm", "rally", "volatile"], bpm


def _macro(kind: str, epb: int, strong: tuple[int, ...], bpm: int, character: str, *, bridge: bool, trio: bool, moods: list[str] | None, bar_beats: float):
    bars = 8
    melody = [72] * (bars * epb)
    intro = _joined(0, [72] * epb, held=True)
    left = _joined(epb, [72] * (2 * epb), held=True)
    middle = _joined(3 * epb, [72] * (2 * epb), held=True)
    right = _joined(5 * epb, [72] * (2 * epb), held=True)
    outro = _joined(7 * epb, [72] * epb, held=True)
    kinds = {0: "intro", 7: "outro"}
    for bar in range(1, 7):
        kinds[bar] = "phrase"
    middle_section = FormSection(3, 5, "phrase", 1, bridge=bridge, trio=trio)
    sections = (
        FormSection(0, 1, "intro", 0),
        FormSection(1, 3, "phrase", 0),
        middle_section,
        FormSection(5, 7, "phrase", 0),
        FormSection(7, 8, "outro", 0),
    )
    ctx = _ctx(
        melody=melody,
        phrase=left,
        kind=kind,
        epb=epb,
        strong=strong,
        bpm=bpm,
        character=character,
        bars=bars,
        bar_beats=bar_beats,
        sections=sections,
    )
    return replace(
        ctx,
        phrases=(intro, left, middle, right, outro),
        kind_at=kinds,
        character_at=moods,
        chord_at={bar: C for bar in range(bars)},
        band_at={bar: "mf" for bar in range(bars)},
    )


def test_framed_castillos_follow_the_middle_mood() -> None:
    epb = 8
    bars = 34
    intro = _joined(0, [72] * epb, held=True)
    body = _joined(epb, [72] * ((bars - 2) * epb), held=True)
    outro = _joined((bars - 1) * epb, [72] * epb, held=True)
    kinds = {0: "intro", bars - 1: "outro"}
    for bar in range(1, bars - 1):
        kinds[bar] = "phrase"
    one_day = _ctx(
        melody=[72] * (bars * epb),
        phrase=body,
        kind="4/4",
        bpm=96,
        character="volatile",
        bars=bars,
        sections=(
            FormSection(0, 1, "intro", 0),
            FormSection(1, bars - 1, "phrase", 0),
            FormSection(bars - 1, bars, "outro", 0),
        ),
    )
    one_day = replace(
        one_day,
        phrases=(intro, body, outro),
        kind_at=kinds,
        chord_at={bar: C for bar in range(bars)},
        band_at={bar: "mf" for bar in range(bars)},
    )
    assert _patterns(one_day) == ["pedal", "olite", "pedal"]

    calm = _macro("6/8", 6, (0, 3), 120, "calm", bridge=False, trio=True, moods=None, bar_beats=3.0)
    assert _patterns(calm) == ["pedal", "danza", "alcaniz", "danza", "pedal"]
    rally = _macro("6/8", 6, (0, 3), 120, "rally", bridge=False, trio=True, moods=None, bar_beats=3.0)
    assert _patterns(rally) == ["pedal", "alcaniz", "danza", "alcaniz", "pedal"]
    volatile = _macro("6/8", 6, (0, 3), 120, "volatile", bridge=False, trio=True, moods=None, bar_beats=3.0)
    assert _patterns(volatile) == ["pedal", "fandanguillo", "danza", "fandanguillo", "pedal"]
    selloff = _macro("6/8", 6, (0, 3), 120, "selloff", bridge=False, trio=True, moods=None, bar_beats=3.0)
    assert _patterns(selloff) == ["pedal", "fandanguillo", "danza", "fandanguillo", "pedal"]

    slow_calm = ["calm"] * 8
    juglar = _macro("3/4", 6, (0,), 72, "rally", bridge=True, trio=False, moods=slow_calm, bar_beats=3.0)
    assert _patterns(juglar) == ["pedal", "castillo", "torroba_tremolo", "castillo", "pedal"]
    slow_hot = ["rally"] * 8
    danced = _macro("3/4", 6, (0,), 72, "calm", bridge=True, trio=False, moods=slow_hot, bar_beats=3.0)
    assert _patterns(danced) == ["pedal", "torroba_tremolo", "danza", "torroba_tremolo", "pedal"]


def test_juglar_chunk_is_one_thumb_and_three_fingers() -> None:
    phrase = Phrase(0, 6, (Run(0, 2, 67), Run(2, 2, 72), Run(4, 2, 69)))
    melody = [67, 67, 72, 72, 69, 69]
    ctx = _ctx(
        melody=melody,
        phrase=phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        bpm=72,
        character="calm",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_34):
        lead, support, low = _render_torroba_bar(ctx, 0, phrase, "torroba_tremolo")
    # No inner note: a chunk is exactly four plucks, so the thumb is the second line.
    assert support == []
    assert [round(note.beat) for note in low] == [0, 1, 2]
    assert all(note.duration_beats == pytest.approx(1.0) for note in low)
    assert all(note.midi == 40 for note in low)
    assert [note.velocity for note in low] == [62, 74, 67]
    for quarter, eighth in enumerate((0, 2, 4)):
        attacks = [note for note in lead if quarter - 1e-9 <= note.beat < quarter + 1 - 1e-9]
        assert [round(note.beat * 12) for note in attacks] == [
            quarter * 12 + 3,
            quarter * 12 + 6,
            quarter * 12 + 9,
        ]
        assert {note.midi for note in attacks} == {melody[eighth]}
        assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in attacks)
        assert attacks[0].velocity > attacks[1].velocity > attacks[2].velocity
        assert attacks[0].velocity - attacks[2].velocity == 4
        # The thumb sings over the chunk instead of bedding under it (5.1).
        assert low[quarter].velocity == attacks[0].velocity + 2
        if eighth == 0:
            assert attacks[0].accent and not attacks[1].accent and not attacks[2].accent
            ordinary = _note_velocity(0, 1, _apex_eighths(ctx.phrases), phrase)
            assert attacks[0].velocity == ordinary and ordinary < 68
        else:
            assert all(not note.accent for note in attacks)
    # One sixteenth grid: every finger sits a quarter of the way into its beat.
    assert len(lead) == 9
    assert all(round((note.beat % 1) * 4) in {1, 2, 3} for note in lead)
    accented = NoteEvent(bar=0, beat=0.25, midi=67, duration_beats=0.25, voice=1, velocity=60, accent=True)
    plain = NoteEvent(bar=0, beat=0.5, midi=67, duration_beats=0.25, voice=1, velocity=56)
    assert _is_target(ctx, "torroba_tremolo", accented, "lead", phrase, 0.25, 1.0) is False
    assert _is_target(ctx, "torroba_tremolo", plain, "lead", phrase, 0.5, 1.0) is False

    thin_phrase = Phrase(0, 6, (Run(0, 6, 67),))
    thin_ctx = replace(ctx, melody=[67] * 6, phrases=(thin_phrase,))
    with compose_meter(METER_34):
        thin_lead, thin_support, thin_low = _render_torroba_bar(thin_ctx, 0, thin_phrase, "torroba_tremolo")
    # A flat sentence still sings chunks: the grid state only adds the accent.
    assert thin_support == []
    assert len(thin_lead) == 9
    assert thin_lead[0].accent and not any(note.accent for note in thin_lead[1:])
    assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in thin_lead)
    assert len(thin_low) == 3 and all(note.duration_beats == pytest.approx(1.0) for note in thin_low)

    first = Phrase(0, 6, (Run(0, 3, 67), Run(3, 3, 69)))
    second = Phrase(6, 12, (Run(6, 3, 67), Run(9, 3, 69)))
    pushed_ctx = replace(
        ctx,
        melody=[67, 67, 67, 69, 69, 69, 67, 67, 67, 69, 69, 69],
        phrases=(first, second),
        bars=2,
        chord_at={0: C, 1: C},
        kind_at={0: "phrase", 1: "phrase"},
        band_at={0: "mf", 1: "mf"},
    )
    with compose_meter(METER_34):
        pushed, _support, _low = _render_torroba_bar(pushed_ctx, 1, second, "torroba_tremolo")
    assert len(pushed) == 9
    downbeat = next(note for note in pushed if note.beat == pytest.approx(0.25))
    assert downbeat.accent and downbeat.velocity < 68
    closing = Phrase(6, 12, (Run(6, 6, 67),))
    closing_ctx = replace(pushed_ctx, phrases=(first, closing))
    with compose_meter(METER_34):
        closed, _support, _low = _render_torroba_bar(closing_ctx, 1, closing, "torroba_tremolo")
    assert len(closed) == 9
    assert closed[0].accent
    assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in closed)

    # The shape does not read the tempo: 120 BPM is the same chunk on the same grid.
    fast_ctx = replace(ctx, bpm=120)
    with compose_meter(METER_34):
        fast, _support, fast_low = _render_torroba_bar(fast_ctx, 0, phrase, "torroba_tremolo")
    assert [round(note.beat * 12) for note in fast] == [
        3, 6, 9, 15, 18, 21, 27, 30, 33
    ]
    assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in fast)
    assert len(fast_low) == 3

    rising = phrase
    gap = [
        NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=4 / 12, voice=1, velocity=60, accent=True),
        NoteEvent(bar=0, beat=4 / 12, midi=67, duration_beats=4 / 12, voice=1, velocity=56),
    ]
    shaped, _support, _low = _shape_dynamics(ctx, gap, [], [], set(), ["torroba_tremolo"])
    assert shaped[0].velocity - shaped[1].velocity == 4

    score = Score(
        title="Juglar",
        bpm=72,
        bars=1,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(ChordSlot(0, 1, C, "sideway", "phrase"),),
        high=(),
        lead=tuple(lead),
        support=(),
        comp=(),
        low=(),
        dynamics=(),
        harmonies=(HarmonyEvent(0, C),),
        liquidity=("mf",),
        phrases=(phrase,),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="torroba",
        divisions=4,
        beats=3,
        beat_type=4,
        bar_beats=3.0,
        mode="major",
    )
    xml = score_to_musicxml(score)
    assert "<grace" not in xml
    # Three sixteenths per beat: no 3:2 tuplet left anywhere in the bar.
    assert xml.count("<type>16th</type>") == 9
    assert "<time-modification>" not in xml
    assert rising.rise >= MIN_RISE


def test_alcaniz_dance_soft_and_opening() -> None:
    opening = Phrase(0, 18, (Run(0, 8, 67), Run(8, 7, 72), Run(15, 3, 69)))
    later = Phrase(18, 24, (Run(18, 2, 67), Run(20, 2, 74), Run(22, 2, 69)))
    even = Phrase(24, 30, (Run(24, 2, 67), Run(26, 2, 74), Run(28, 2, 69)))
    melody = [67] * 8 + [72] * 7 + [69] * 3 + [67, 67, 74, 74, 69, 69] + [67, 67, 74, 74, 69, 69]
    ctx = _ctx(
        melody=melody,
        phrase=opening,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        bpm=96,
        character="rally",
        bars=5,
        bar_beats=3,
        chord=C,
    )
    ctx = replace(
        ctx,
        phrases=(opening, later, even),
        chord_at={bar: C for bar in range(5)},
        kind_at={bar: "phrase" for bar in range(5)},
        band_at={bar: "mf" for bar in range(5)},
    )
    with compose_meter(METER_68):
        opened, opened_support, _opened_low = _render_torroba_bar(ctx, 0, opening, "alcaniz")
        danced, danced_support, danced_low = _render_torroba_bar(ctx, 2, opening, "alcaniz")
        second, _second_support, _second_low = _render_torroba_bar(ctx, 3, later, "alcaniz")
    assert any(note.slur_start for note in opened) and any(note.slur_stop for note in opened)
    slurred = sorted((note for note in opened if note.slur_start or (note.beat == pytest.approx(1.0))), key=lambda note: note.beat)
    assert [note.midi for note in slurred[:2]] == [71, 69]
    assert all(not note.accent for note in opened if abs(note.beat - 0.5) < 1e-6 or abs(note.beat - 1.0) < 1e-6)
    assert any(note.accent and note.beat == pytest.approx(0.0) and (note.velocity or 0) >= 68 for note in opened)
    assert any(note.beat == pytest.approx(2.0) and note.voice == 1 for note in opened)
    assert opened_support
    for beat in (2.0, 2.5):
        sung = next(note.midi for note in opened if note.beat == pytest.approx(beat))
        held = [note for note in opened_support if note.beat == pytest.approx(beat)]
        assert len(held) == 1
        assert sung - held[0].midi in {3, 4, 8, 9}
        assert held[0].midi < sung
    # A under C: the third is F, a scale tone. The sixth is C, a chord tone.
    # The highest chord tone under A is E, a fourth, which must not be used.
    probe = Phrase(0, 6, (Run(0, 4, 64), Run(4, 2, 69)))
    probe_ctx = _ctx(
        melody=[64, 64, 64, 64, 69, 69],
        phrase=probe,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        bpm=96,
        character="rally",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_68):
        probe_lead, probe_support, _probe_low = _render_torroba_bar(probe_ctx, 0, probe, "alcaniz")
    for beat in (2.0, 2.5):
        sung = next(note.midi for note in probe_lead if note.beat == pytest.approx(beat))
        held = [note for note in probe_support if note.beat == pytest.approx(beat)]
        assert sung == 69 and len(held) == 1
        assert sung - held[0].midi in {3, 4, 8, 9}
        assert held[0].midi % 12 in C.pitch_classes
    assert not any(note.slur_start for note in danced)
    assert _beats([note for note in danced if note.voice == 1]) == [0.0, 1.5]
    sounded = [*danced, *danced_support, *danced_low]
    assert any(note.beat == pytest.approx(1.0) and note.voice == 2 for note in danced_support)
    assert not any(note.beat == pytest.approx(2.5) for note in sounded)
    assert [note.duration_beats for note in danced_low] == [pytest.approx(1.0), pytest.approx(1.0)]
    assert any(note.beat == pytest.approx(0.5) and note.voice == 3 for note in danced_low)
    danced_leads = sorted(danced, key=lambda note: note.beat)
    dance_apex = _apex_eighths(ctx.phrases)
    down_level = _note_velocity(12, 1, dance_apex, opening)
    secondary_level = _note_velocity(15, 1, dance_apex, opening)
    assert danced_leads[0].accent and danced_leads[0].velocity == max(down_level, 68)
    assert not danced_leads[1].accent and danced_leads[1].velocity == max(secondary_level - 2, 66)
    assert not any(note.slur_start for note in second)
    assert _beats(second) == [0.0, 1.5]
    plan = torroba_figure_plan(ctx, ["alcaniz", "alcaniz", "alcaniz"])
    assert plan[0][0] == 10 and plan[1][0] == 10
    assert 2 not in plan and 3 not in plan and 4 not in plan

    soft_phrase = Phrase(0, 6, (Run(0, 3, 67), Run(3, 3, 69)))
    soft_ctx = _ctx(
        melody=[67, 67, 67, 69, 69, 69],
        phrase=soft_phrase,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        bpm=96,
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_68):
        soft, soft_support, soft_low = _render_torroba_bar(soft_ctx, 0, soft_phrase, "alcaniz")
    assert len(soft_support) == 1 and soft_support[0].beat == pytest.approx(1.0) and soft_support[0].voice == 2
    assert [note.duration_beats for note in soft] == [pytest.approx(1.5), pytest.approx(1.5)]
    assert all(not note.accent for note in soft)
    assert soft[0].velocity == 64 and soft[0].velocity < 68
    assert len(soft_low) == 1 and soft_low[0].beat == pytest.approx(0.0) and soft_low[0].duration_beats == pytest.approx(1.0)
    assert castillos_wave_row(soft_ctx, 0, ["alcaniz"], "alcaniz") == "castillo"
    assert castillos_wave_row(ctx, 2, ["alcaniz", "alcaniz", "alcaniz"], "alcaniz") == "alcaniz"

    pushed_left = Phrase(0, 6, (Run(0, 3, 67), Run(3, 3, 69)))
    pushed_right = Phrase(6, 12, (Run(6, 3, 67), Run(9, 3, 69)))
    pushed_ctx = replace(
        soft_ctx,
        melody=[67, 67, 67, 69, 69, 69, 67, 67, 67, 69, 69, 69],
        phrases=(pushed_left, pushed_right),
        bars=2,
        chord_at={0: C, 1: C},
        kind_at={0: "phrase", 1: "phrase"},
        band_at={0: "mf", 1: "mf"},
    )
    with compose_meter(METER_68):
        pushed, _support, _low = _render_torroba_bar(pushed_ctx, 1, pushed_right, "alcaniz")
    assert _beats(pushed) == [0.0, 1.5]
    assert all(not note.accent for note in pushed)
    assert pushed[0].velocity == 64 and pushed[0].velocity < 68
    four = _ctx(melody=[67] * 8, phrase=_joined(0, [67] * 8, held=True), kind="4/4", chord=C)
    with compose_meter(METER_44):
        off, _support, _low = _render_torroba_bar(four, 0, four.phrases[0], "alcaniz")
    assert _beats(off) == [0.0]
    assert len(off) == 1


def test_olite_chords_walk_and_thin_close() -> None:
    phrase = Phrase(0, 24, (Run(0, 10, 60), Run(10, 11, 67), Run(21, 3, 64)))
    melody = [60] * 8 + [60, 60, 60, 60, 64, 60, 60, 60] + [72] + [60] * 7
    ctx = _ctx(
        melody=melody,
        phrase=phrase,
        kind="4/4",
        bpm=96,
        character="volatile",
        bars=3,
        chord=C,
    )
    ctx = replace(
        ctx,
        chord_at={bar: C for bar in range(3)},
        kind_at={bar: "phrase" for bar in range(3)},
        band_at={bar: "mf" for bar in range(3)},
    )
    with compose_meter(METER_44):
        still_lead, still_support, _still_low = _render_torroba_bar(ctx, 0, phrase, "olite")
        short_lead, short_support, _short_low = _render_torroba_bar(ctx, 1, phrase, "olite")
    chords = [note for note in still_lead if abs(note.beat) < 1e-6 or abs(note.beat - 2.0) < 1e-6]
    assert len(chords) == 2 and all(note.accent and (note.velocity or 0) >= 68 for note in chords)
    assert still_support
    weak = [note for note in still_lead if abs(note.beat) > 1e-6 and abs(note.beat - 2.0) > 1e-6]
    # A repeated pitch no longer rests. The first eighth of the group is a mordent triplet.
    triplet = sorted((note for note in weak if abs(note.duration_beats * 6 - 1) < 1e-3), key=lambda note: note.beat)
    assert len(triplet) >= 3
    assert triplet[0].slur_start and triplet[0].midi == 60
    walked = sorted(
        (note for note in short_lead if abs(note.beat) > 1e-6 and abs(note.beat - 2.0) > 1e-6),
        key=lambda note: note.beat,
    )
    assert [note.midi for note in walked] == [62, 64, 64, 65, 71, 72]
    assert all(not note.accent for note in walked)
    assert not any(note.beat == pytest.approx(walked_beat) for note in short_support for walked_beat in (0.5, 1.0, 1.5, 2.5, 3.0, 3.5))
    assert castillos_wave_row(ctx, 0, ["olite"], "olite") == "olite"

    closing = Phrase(0, 8, (Run(0, 4, 60), Run(4, 4, 72)))
    close_ctx = _ctx(melody=[60] * 4 + [72] * 4, phrase=closing, character="volatile", chord=C)
    with compose_meter(METER_44):
        thin_lead, thin_support, thin_low = _render_torroba_bar(close_ctx, 0, closing, "olite")
    assert thin_support == []
    assert _beats(thin_lead) == [0.0, 1.5, 2.0]
    assert thin_lead[0].duration_beats == pytest.approx(1.5)
    assert thin_lead[-1].duration_beats == pytest.approx(2.0)
    assert all(not note.accent for note in thin_lead)
    assert thin_lead[0].velocity == 60 and thin_lead[0].velocity < 68
    assert [round(note.beat, 2) for note in thin_low] == [0.0, 2.0]
    assert all(not note.tie_start and not note.tie_stop for note in thin_low)
    assert castillos_wave_row(close_ctx, 0, ["olite"], "olite") == "castillo"
    assert torroba_figure_plan(close_ctx, ["olite"])[0][0] == 12

    left = Phrase(0, 8, (Run(0, 5, 60), Run(5, 3, 62)))
    right = Phrase(8, 16, (Run(8, 5, 60), Run(13, 3, 62)))
    pair_melody = [60, 62, 64, 64, 64, 62, 62, 62, 60, 62, 62, 62, 62, 62, 62, 62]
    pair = _ctx(melody=pair_melody, phrase=left, bars=2, character="volatile", chord=C)
    pair = replace(
        pair,
        phrases=(left, right),
        chord_at={0: C, 1: C},
        kind_at={0: "phrase", 1: "phrase"},
        band_at={0: "mf", 1: "mf"},
    )
    with compose_meter(METER_44):
        first_lead, first_support, _first_low = _render_torroba_bar(pair, 0, left, "olite")
        second_lead, second_support, _second_low = _render_torroba_bar(pair, 1, right, "olite")
    assert _beats(first_lead) == [0.0, 1.5, 2.0, 3.5] and first_support == []
    assert all(not note.accent for note in first_lead)
    second_weak = sorted(
        (note for note in second_lead if abs(note.beat) > 1e-6 and abs(note.beat - 2.0) > 1e-6),
        key=lambda note: note.beat,
    )
    assert [note.midi for note in second_weak[:3]] == [62, 62, 62]
    assert second_support
    down = next(note for note in second_lead if note.beat == pytest.approx(0.0))
    assert not down.accent and down.velocity == 64 and down.velocity < 68
    assert castillos_wave_row(pair, 1, ["olite", "olite"], "olite") == "castillo"
    closed = Phrase(8, 16, (Run(8, 8, 60),))
    closed_ctx = replace(pair, phrases=(left, closed))
    with compose_meter(METER_44):
        stayed, stayed_support, _stayed_low = _render_torroba_bar(closed_ctx, 1, closed, "olite")
    assert _beats(stayed) == [0.0, 1.5, 2.0] and stayed_support == []
    assert all(not note.accent for note in stayed)


def test_castillos_second_half_uses_the_sentence_that_opens_there() -> None:
    """A sentence that starts mid-bar brings its own swell. The price note stays."""
    rise = [60, 62, 64, 67, 69, 71, 72, 74]
    opening = _joined(0, [72] * 4, held=True)
    following = _joined(4, rise)
    assert following.rise >= MIN_RISE and following.apex.start > 4
    melody = [72] * 4 + rise
    olite = _many((opening, following), kind="4/4", melody=melody)
    with compose_meter(METER_44):
        olite_lead, _support, _low = _render_torroba_bar(olite, 0, opening, "olite")
    apex = _apex_eighths(olite.phrases)
    local = _note_velocity(4, 1, apex, following)
    borrowed = _note_velocity(4, 1, apex, opening)
    assert local == 60 and borrowed == 64
    chord = next(note for note in olite_lead if note.beat == pytest.approx(2.0))
    first = next(note for note in olite_lead if note.beat == pytest.approx(0.0))
    assert chord.midi == melody[4] and chord.velocity == local and not chord.accent
    assert first.velocity == borrowed

    soft_open = _joined(0, [72] * 3, held=True)
    soft_next = _joined(3, rise)
    alcaniz = _many((soft_open, soft_next), kind="6/8", melody=[72] * 3 + rise)
    with compose_meter(METER_68):
        alcaniz_lead, _support, _low = _render_torroba_bar(alcaniz, 0, soft_open, "alcaniz")
    apex = _apex_eighths(alcaniz.phrases)
    later = next(note for note in alcaniz_lead if note.beat == pytest.approx(1.5))
    early = next(note for note in alcaniz_lead if note.beat == pytest.approx(0.0))
    assert later.midi == 60 and later.duration_beats == pytest.approx(1.5)
    assert later.velocity == _note_velocity(3, 1, apex, soft_next)
    assert later.velocity != _note_velocity(3, 1, apex, soft_open)
    assert early.velocity == _note_velocity(0, 1, apex, soft_open)

    juglar_open = _joined(0, [72] * 4, held=True)
    juglar_next = _joined(4, rise)
    juglar = _many((juglar_open, juglar_next), kind="3/4", melody=melody)
    with compose_meter(METER_34):
        juglar_lead, _support, _low = _render_torroba_bar(juglar, 0, juglar_open, "torroba_tremolo")
    apex = _apex_eighths(juglar.phrases)
    downbeat = next(note for note in juglar_lead if note.beat == pytest.approx(0.25))
    last = next(note for note in juglar_lead if note.beat == pytest.approx(2.25))
    owned = _note_velocity(4, 1, apex, juglar_next)
    assert last.midi == melody[4] and last.duration_beats == pytest.approx(0.25)
    # Eighth 4 opens the next sentence and is not that sentence's apex, so the 3/4 slope steps it.
    assert last.velocity == max(40, owned - 2)
    assert downbeat.velocity == _note_velocity(0, 1, apex, juglar_open)
    assert last.velocity != downbeat.velocity


def test_type3_scale_follows_each_eighth_of_the_sentence() -> None:
    """A scale cell is a sentence, not one velocity copied from its last note."""
    pitches = [60] * 8 + list(range(62, 70)) + [74] * 8
    phrase = _joined(0, pitches, held=True)
    assert phrase.rise >= MIN_RISE and phrase.apex.start == 16
    ctx = _many((phrase,), melody=pitches)
    with compose_meter(METER_44):
        lead, _support, _low = render_torroba_figure(
            ctx, 1, phrase, "sonatina", 3, index=1, count=3
        )
    heard = sorted((note for note in lead if note.midi is not None), key=lambda note: note.beat)
    assert len(heard) == 8
    apex = _apex_eighths(ctx.phrases)
    expected = []
    for eighth in range(8):
        local = _note_velocity(8 + eighth, 1, apex, phrase)
        step = 0 if eighth == 7 else 1
        expected.append(local - step * _MICRO)
    assert [note.velocity for note in heard] == expected
    assert expected[0] < expected[-1]
    stamped = [
        _note_velocity(15, 1, apex, phrase) - (0 if eighth == 7 else _MICRO) for eighth in range(8)
    ]
    assert expected != stamped
    shaped, _shaped_support, _shaped_low = _shape_dynamics(
        ctx, list(heard), [], [], set(), ["sonatina", "sonatina", "sonatina"]
    )
    gap = expected[-1] - expected[0]
    assert shaped[-1].velocity - shaped[0].velocity == gap


def test_rasgueado_clusters_keep_a_local_sentence() -> None:
    """Two strums in one bar do not share the downbeat. The later strum has risen."""
    pitches = [60, 61, 62, 64, 65, 67, 72, 72] + [70] * 8
    phrase = _joined(0, pitches, held=True)
    assert phrase.rise >= MIN_RISE and phrase.apex.start == 6
    ctx = _many((phrase,), melody=pitches)
    with compose_meter(METER_44):
        lead, _support, _low = render_torroba_figure(
            ctx, 0, phrase, "fandanguillo", 2, index=0, count=2
        )
    apex = _apex_eighths(ctx.phrases)

    def cluster(beat: float) -> list[NoteEvent]:
        return sorted(
            (note for note in lead if note.midi is not None and beat <= note.beat < beat + 1),
            key=lambda note: note.beat,
        )

    opening = cluster(0.5)
    later = cluster(2.5)
    assert len(opening) == 4 and len(later) == 4
    # Eighth 1 is still under the dance floor. Eighth 5 has risen past it.
    assert opening[0].velocity == max(_note_velocity(1, 1, apex, phrase), 68) - _MICRO
    assert later[0].velocity == max(_note_velocity(5, 1, apex, phrase), 68) - _MICRO
    assert later[0].velocity > opening[0].velocity


def test_a_new_sentence_inside_a_figure_bar_opens_at_its_own_swell() -> None:
    opening = _joined(0, [72] * 4, held=True)
    following = _joined(4, [60, 62, 64, 67, 69, 71, 72, 74])
    assert following.rise >= MIN_RISE and following.apex.start > 4
    ctx = _many((opening, following), melody=[72] * 4 + [60, 62, 64, 67, 69, 71, 72, 74])
    with compose_meter(METER_44):
        lead, support, low = render_torroba_figure(
            ctx, 0, opening, "sonatina", 4, index=0, count=2
        )
        grid_lead, _grid_support, grid_low = _render_torroba_bar(ctx, 0, opening, "sonatina")
    attack = [note for note in lead if note.midi is not None and note.beat == pytest.approx(2.0)]
    bass = [note for note in low if note.midi is not None and note.beat == pytest.approx(2.0)]
    inner = [note for note in support if note.midi is not None and note.beat == pytest.approx(2.0)]
    grid_attack = [
        note
        for note in grid_lead
        if note.midi is not None and note.beat == pytest.approx(2.0) and note.duration_beats >= 0.5
    ]
    grid_bass = [note for note in grid_low if note.midi is not None and note.beat == pytest.approx(2.0)]
    assert len(attack) == 1 and len(bass) == 1 and len(inner) == 1
    assert len(grid_attack) == 1 and len(grid_bass) == 1
    apex = _apex_eighths(ctx.phrases)
    local = _note_velocity(4, 1, apex, following)
    borrowed = _note_velocity(4, 1, apex, opening)
    assert local == 60 and borrowed == 64
    assert attack[0].velocity == local
    assert attack[0].velocity > bass[0].velocity > inner[0].velocity
    assert grid_attack[0].velocity == local
    assert grid_attack[0].velocity > grid_bass[0].velocity


def test_type_4_weak_eighth_keeps_lead_above_bass_above_support() -> None:
    """A sentence that opens on the last eighth still leaves one micro step between voices.

    Lead 60 holds the strong bass at 58. The weak bass is 4 under that, and the
    inner voice takes one more step, so the two would meet at 54. The weak bass
    stays one step above the inner voice. In 4/4 the lead then drops to 58.
    In 3/4 and 6/8 the weak lead has no step and stays at 60.
    """
    rise = [60, 62, 64, 67, 69, 71, 72, 74]
    cases = (
        ("4/4", 7, 3.5, 60 - _MICRO),
        ("3/4", 5, 2.5, 60),
        ("6/8", 5, 2.5, 60),
    )
    for kind, eighth, beat, heard_lead in cases:
        meter, _epb, _strong, _beats = _FIGURE_METERS[kind]
        opening = _joined(0, [72] * eighth, held=True)
        following = _joined(eighth, rise)
        assert following.rise >= MIN_RISE and following.apex.start > eighth
        melody = [72] * eighth + rise
        ctx = _many((opening, following), kind=kind, melody=melody)
        with compose_meter(meter):
            lead, support, low = render_torroba_figure(
                ctx, 0, opening, "sonatina", 4, index=0, count=2
            )
        apex = _apex_eighths(ctx.phrases)
        assert _note_velocity(eighth, 1, apex, following) == 60
        sung = [note for note in lead if note.midi is not None and note.beat == pytest.approx(beat)]
        bass = [note for note in low if note.midi is not None and note.beat == pytest.approx(beat)]
        inner = [note for note in support if note.midi is not None and note.beat == pytest.approx(beat)]
        assert len(sung) == 1 and len(bass) == 1 and len(inner) == 1
        assert sung[0].velocity == heard_lead
        assert bass[0].velocity == 56
        assert inner[0].velocity == 54
        assert sung[0].velocity > bass[0].velocity > inner[0].velocity


def test_a_closing_figure_thins_the_inner_voice_and_drops_it_to_p() -> None:
    pitches = [72] * 24
    closing = _joined(0, pitches)
    assert closing.closes
    held = _joined(0, pitches, held=True)
    assert not held.closes

    def support_at(phrase: Phrase) -> list[NoteEvent]:
        ctx = _many((phrase,), melody=pitches, bpm=72)
        with compose_meter(METER_44):
            _lead, support, _low = render_torroba_figure(
                ctx, 2, phrase, "castillo", 7, index=2, count=3
            )
        return [note for note in support if note.midi is not None]

    breathed = support_at(closing)
    sustained = support_at(held)
    assert breathed and sustained
    assert all(int(note.beat * 2 + 1e-9) % 2 == 0 for note in breathed)
    assert any(int(note.beat * 2 + 1e-9) % 2 == 1 for note in sustained)
    assert {note.velocity for note in breathed} == {50, 48}
    assert {note.velocity for note in sustained} == {56, 54}

    # A 1-eighth closing tail on a rolled downbeat keeps the rolled support strings.
    one_tail = _joined(0, [72] * 9)
    rest_phrase = _joined(9, [72] * 7, held=True)
    assert one_tail.closes
    roll_ctx = _many((one_tail, rest_phrase), melody=[72] * 16, bpm=72)
    with compose_meter(METER_44):
        roll_lead, roll_support, roll_low = render_torroba_figure(
            roll_ctx, 1, one_tail, "castillo", 7, index=4, count=5
        )
    _assert_type7_roll(roll_lead, roll_support, roll_low, 4.0)
    assert {note.velocity for note in roll_support if note.midi is not None} == {50 - _MICRO}


def test_a_headless_roll_keeps_its_inner_strings_on_a_one_eighth_close() -> None:
    """No bass pulls the rolled inner strings onto beat 0. The close still keeps them.

    A block chord on the same one-eighth tail has no fan, so its inner voice
    on the downbeat still drops out.
    """
    only_g = Chord("G", "G", "major", "", (55,))
    one_tail = _joined(0, [73] * 9)
    rest_phrase = _joined(9, [73] * 7, held=True)
    assert one_tail.closes
    roll_ctx = _many((one_tail, rest_phrase), melody=[73] * 16, bpm=72, chord=only_g)
    block_phrase = _joined(0, [72] * 9)
    block_rest = _joined(9, [72] * 7, held=True)
    block_ctx = _many((block_phrase, block_rest), melody=[72] * 16, bpm=72, chord=C)
    with compose_meter(METER_44):
        lead, support, low = render_torroba_figure(
            roll_ctx, 1, one_tail, "castillo", 7, index=4, count=5
        )
        _block_lead, block_support, _block_low = render_torroba_figure(
            block_ctx, 1, block_phrase, "castillo", 7, index=1, count=5
        )
    opening = _opening(lead, support, low)
    mids = [note for note in opening if note.voice == 2]
    highs = [note for note in opening if note.voice == 1]
    assert mids and len(highs) == 1
    assert not any(note.voice == 3 for note in opening)
    assert all(note.beat == pytest.approx(0.0) for note in mids)
    assert highs[0].beat == pytest.approx(1 / 12)
    assert {note.velocity for note in mids} == {50 - _MICRO}
    assert not any(note.midi is not None and note.beat <= 1e-9 for note in block_support)


def test_juglar_bar_before_the_return_stays_a_chunk() -> None:
    """Bar 68 is the second-to-last bar of the Juglar region. Bar 69 is the last."""
    epb = 6
    start = 68 * epb
    closing = Phrase(start, 70 * epb, (Run(start, 2 * epb, 67),))
    returned = Phrase(70 * epb, 71 * epb, (Run(70 * epb, epb, 72),))
    bars = 71
    melody = [67] * (70 * epb) + [72] * epb
    ctx = _ctx(
        melody=melody,
        phrase=closing,
        kind="3/4",
        epb=epb,
        strong=(0,),
        bpm=72,
        character="calm",
        bars=bars,
        bar_beats=3,
        chord=C,
    )
    ctx = replace(
        ctx,
        phrases=(closing, returned),
        chord_at={bar: C for bar in range(bars)},
        kind_at={bar: "phrase" for bar in range(bars)},
        band_at={bar: "mf" for bar in range(bars)},
    )
    patterns = ["torroba_tremolo", "castillo"]
    assert closing.closes and closing.rise < MIN_RISE
    with compose_meter(METER_34):
        earlier, _support, earlier_low = _render_torroba_bar(ctx, 68, closing, "torroba_tremolo", patterns)
        last, _support, last_low = _render_torroba_bar(ctx, 69, closing, "torroba_tremolo", patterns)
        plan = torroba_figure_plan(ctx, patterns)
    assert len(earlier) == 9
    assert all(abs(note.duration_beats - 0.25) < 1e-9 for note in earlier)
    assert earlier[0].accent
    assert [round(note.beat, 2) for note in last] == [0.0, 1.0, 2.0]
    assert all(note.duration_beats == pytest.approx(1.0) for note in last)
    assert all(not note.accent for note in last)
    # The chunk bar bounces the thumb on every beat; the quarter-note bar holds one.
    assert len(earlier_low) == 3
    assert all(note.duration_beats == pytest.approx(1.0) for note in earlier_low)
    assert len(last_low) == 1 and last_low[0].duration_beats == pytest.approx(1.5)
    assert 68 not in plan
    assert plan[69][0] == 9


def test_castillo_bass_is_one_beat_and_the_lead_holds_the_bar() -> None:
    phrase = _joined(0, [72] * 8)
    ctx = _ctx(melody=[72] * 8, phrase=phrase, character="calm", chord=C)
    with compose_meter(METER_44):
        lead, _support, low = _render_torroba_bar(ctx, 0, phrase, "castillo")
    assert [round(note.beat, 2) for note in low] == [0.0, 2.0]
    assert all(note.duration_beats == pytest.approx(2.0) for note in low)
    assert all(not note.tie_start and not note.tie_stop for note in low)
    assert len(lead) == 1
    assert lead[0].beat == pytest.approx(0.0)
    assert lead[0].duration_beats == pytest.approx(4.0)


def test_alcaniz_and_olite_keep_thin_then_pushed() -> None:
    first = Phrase(0, 6, (Run(0, 3, 67), Run(3, 3, 69)))
    second = Phrase(6, 12, (Run(6, 3, 67), Run(9, 3, 69)))
    ctx = _ctx(
        melody=[67, 67, 67, 69, 69, 69, 67, 67, 67, 69, 69, 69],
        phrase=first,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        bpm=120,
        character="rally",
        bars=2,
        bar_beats=3,
        chord=C,
    )
    ctx = replace(
        ctx,
        phrases=(first, second),
        chord_at={0: C, 1: C},
        kind_at={0: "phrase", 1: "phrase"},
        band_at={0: "mf", 1: "mf"},
    )
    assert first.rise < MIN_RISE and not first.closes
    assert _grid_state(ctx, ["alcaniz", "alcaniz"]) == {0: "thin", 1: "pushed"}
    assert _grid_state(ctx, ["olite", "olite"]) == {0: "thin", 1: "pushed"}
    assert _grid_state(ctx, ["torroba_tremolo", "torroba_tremolo"]) == {0: "full", 1: "full"}


def _one_bar_phrases(bars: int, epb: int) -> tuple[Phrase, ...]:
    return tuple(
        Phrase(bar * epb, (bar + 1) * epb, (Run(bar * epb, epb, 60),))
        for bar in range(bars)
    )


def _slot_score(
    widths: list[int],
    *,
    kind: str = "4/4",
    character: str = "selloff",
    bridge_at: int | None = None,
    moods: list[str] | None = None,
) -> _Ctx:
    epb = 8 if kind == "4/4" else 6
    strong = (0, 4) if kind == "4/4" else ((0,) if kind == "3/4" else (0, 3))
    intro = 4
    cursor = intro
    sections = [FormSection(0, intro, "intro", 0)]
    kinds = {bar: "intro" for bar in range(intro)}
    for slot, width in enumerate(widths):
        start, end = cursor, cursor + width
        sections.append(
            FormSection(start, end, "phrase", slot, bridge=bridge_at == slot, trio=False)
        )
        kinds.update({bar: "phrase" for bar in range(start, end)})
        cursor = end
    bars = cursor
    ctx = _ctx(
        melody=[60] * (bars * epb),
        phrase=_one_bar_phrases(1, epb)[0],
        kind=kind,
        epb=epb,
        strong=strong,
        bpm=96 if kind == "4/4" else 72,
        character=character,
        bars=bars,
        bar_beats=4.0 if kind == "4/4" else 3.0,
        sections=tuple(sections),
    )
    return replace(
        ctx,
        phrases=_one_bar_phrases(bars, epb),
        kind_at=kinds,
        character_at=moods,
        chord_at={bar: C for bar in range(bars)},
        band_at={bar: "mf" for bar in range(bars)},
    )


def _body_pattern(ctx: _Ctx, patterns: list[str], bar: int) -> str:
    from app.sonify.guitar_patterns import _bar_pattern

    return _bar_pattern(ctx, bar, patterns)


def test_slot_splits_follow_the_aba_windows() -> None:
    from app.sonify.span import split_into

    epb = 8
    one = _ctx(
        melody=[60] * (32 * epb),
        phrase=_one_bar_phrases(1, epb)[0],
        kind="4/4",
        bpm=90,
        character="selloff",
        bars=32,
        sections=(
            FormSection(0, 4, "intro", 0),
            FormSection(4, 28, "phrase", 0),
            FormSection(28, 32, "outro", 0),
        ),
    )
    kinds = {bar: "phrase" for bar in range(32)}
    kinds.update({bar: "intro" for bar in range(4)})
    kinds.update({bar: "outro" for bar in range(28, 32)})
    one = replace(
        one,
        phrases=_one_bar_phrases(32, epb),
        kind_at=kinds,
        chord_at={bar: C for bar in range(32)},
        band_at={bar: "mf" for bar in range(32)},
    )
    painted = _patterns(one)
    assert split_into(32, 3) == [10, 11, 11]
    expected = ["olite"] * 10 + ["castillo"] * 11 + ["olite"] * 11
    for bar, pattern in enumerate(expected):
        if one.kind_at[bar] in {"intro", "outro"}:
            continue
        assert _body_pattern(one, painted, bar) == pattern
    assert form_pattern_ids(one, painted) == ["olite", "castillo", "olite"]

    # The year opener's outro is its own slot. It is not a third phrase region.
    opener = _slot_score([36, 36])
    opener = replace(
        opener,
        bars=opener.bars + 4,
        sections=opener.sections + (FormSection(opener.bars, opener.bars + 4, "outro", 2),),
        kind_at={**opener.kind_at, **{bar: "outro" for bar in range(opener.bars, opener.bars + 4)}},
        phrases=_one_bar_phrases(opener.bars + 4, epb),
        chord_at={bar: C for bar in range(opener.bars + 4)},
        band_at={bar: "mf" for bar in range(opener.bars + 4)},
        melody=[60] * ((opener.bars + 4) * epb),
    )
    painted = _patterns(opener)
    second = 4 + 36
    for bar in range(4, second):
        assert _body_pattern(opener, painted, bar) == "olite"
    for bar in range(second, second + 36):
        pattern = "castillo" if bar < second + 18 else "olite"
        assert _body_pattern(opener, painted, bar) == pattern

    two = _slot_score([16, 11])
    painted = _patterns(two)
    # Slot 1 starts after the intro and the 16-bar opening.
    start = 4 + 16
    left = 11 // 2
    for bar in range(start, start + 11):
        pattern = "castillo" if bar < start + left else "olite"
        assert _body_pattern(two, painted, bar) == pattern

    three = _slot_score([32, 32, 32])
    painted = _patterns(three)
    middle = 4 + 32
    for offset, pattern in enumerate(["olite"] * 12 + ["castillo"] * 8 + ["olite"] * 12):
        assert _body_pattern(three, painted, middle + offset) == pattern
    for bar in range(4, 4 + 32):
        assert _body_pattern(three, painted, bar) == "olite"
    for bar in range(4 + 64, 4 + 96):
        assert _body_pattern(three, painted, bar) == "olite"

    four = _slot_score([32, 32, 32, 32])
    painted = _patterns(four)
    # Four sessions: the middle session is index 2, the one that starts at the midpoint.
    middle = 4 + 64
    for offset, pattern in enumerate(["olite"] * 12 + ["castillo"] * 8 + ["olite"] * 12):
        assert _body_pattern(four, painted, middle + offset) == pattern
    for bar in range(4 + 32, 4 + 64):
        assert _body_pattern(four, painted, bar) == "olite"

    five = _slot_score([8, 8, 8, 8, 8])
    painted = _patterns(five)
    middle = 4 + 16
    assert [_body_pattern(five, painted, middle + offset) for offset in range(8)] == ["castillo"] * 8

    bridged = _slot_score([16, 24, 16], bridge_at=1)
    painted = _patterns(bridged)
    bridge = 4 + 16
    for bar in range(bridge, bridge + 24):
        assert _body_pattern(bridged, painted, bar) == "castillo"
    for bar in list(range(4, bridge)) + list(range(bridge + 24, bridge + 24 + 16)):
        assert _body_pattern(bridged, painted, bar) == "olite"
    assert form_pattern_ids(bridged, painted) == ["olite", "castillo", "olite"]

    calm = ["calm"] * 12 + ["selloff"] * 12
    waltz = _slot_score([8, 8], kind="3/4", character="selloff", bridge_at=1, moods=calm)
    painted = _patterns(waltz)
    assert form_pattern_ids(waltz, painted) == ["castillo", "torroba_tremolo", "castillo"]


def _bars_phrase(length: int, *, closes: bool) -> Phrase:
    eighths = length * 8
    return _joined(0, [60] * eighths, held=not closes)


def test_figure_spans_lock_the_castillo_and_sonatina_table() -> None:
    """Section 6.3. Each length, open and close, even n and odd n."""
    castillo_even = {
        1: [],
        2: [(8, (0, 1))],
        3: [(8, (0, 1))],
        4: [(8, (0, 1))],
        5: [(7, (0, 1, 2, 3, 4))],
        6: [(7, (0, 1, 2, 3, 4))],
        7: [(7, (0, 1, 2, 3, 4))],
        8: [(7, (0, 1, 2, 3, 4))],
    }
    castillo_odd = {
        1: [],
        2: [(8, (0, 1))],
        3: [(8, (0, 1))],
        4: [(8, (1, 2))],
        5: [(8, (0, 1)), (8, (3, 4))],
        6: [(8, (0, 1)), (8, (3, 4))],
        7: [(7, (0, 1, 2, 3, 4))],
        8: [(8, (0, 1)), (8, (4, 5)), (1, (2,))],
    }
    sonatina_open = {
        1: {0: [], 1: [], 2: []},
        2: {0: [(4, (0, 1))], 1: [(2, (0, 1))], 2: [(1, (0,))]},
        3: {0: [(4, (0, 1))], 1: [(2, (1, 2))], 2: [(1, (0, 1))]},
        4: {
            0: [(4, (0, 1)), (1, (3,))],
            1: [(2, (1, 2)), (1, (3,))],
            2: [(1, (0,)), (4, (2, 3))],
        },
        5: {0: [(4, (0, 1)), (1, (3,))], 1: [(4, (0, 1)), (2, (3, 4))]},
        6: {0: [(4, (0, 1)), (2, (3, 4))], 1: [(2, (0, 1)), (4, (3, 4))]},
        7: {0: [(4, (0, 1)), (1, (3,)), (2, (5, 6))], 1: [(4, (0, 1)), (1, (3,)), (2, (5, 6))]},
        8: {0: [(4, (0, 1)), (1, (3,)), (2, (5, 6))], 1: [(4, (0, 1)), (1, (3,)), (2, (5, 6))]},
    }
    sonatina_close = {
        1: [(3, (0,))],
        2: [(3, (0, 1))],
        3: [(3, (0, 1, 2))],
        4: [(3, (1, 2, 3))],
        5: [(3, (2, 3, 4))],
        6: [(1, (0,)), (3, (3, 4, 5))],
        7: [(4, (0, 1)), (3, (4, 5, 6))],
        8: [(4, (0, 1)), (3, (5, 6, 7))],
    }
    for length in range(1, 9):
        phrase = _bars_phrase(length, closes=False)
        ctx = _many((phrase,), bpm=96)
        assert select_torroba_spans(ctx, phrase, "castillo", n=0, previous=None) == castillo_even[length]
        assert select_torroba_spans(ctx, phrase, "castillo", n=1, previous=None) == castillo_odd[length]
        for turn, expected in sonatina_open[length].items():
            assert select_torroba_spans(ctx, phrase, "sonatina", n=turn, previous=None) == expected
        closed = _bars_phrase(length, closes=True)
        close_ctx = _many((closed,), bpm=96)
        assert closed.closes
        assert select_torroba_spans(close_ctx, closed, "sonatina", n=0, previous=None) == sonatina_close[length]
        assert select_torroba_spans(close_ctx, closed, "sonatina", n=1, previous=None) == sonatina_close[length]
        # Two type-8 spans in one phrase each restart slot_index at 0.
        if length == 8:
            plan = torroba_figure_plan(ctx, ["castillo"])
            # n=0 is the type-7 turn. Force the odd turn by asking the selector.
            spans = castillo_odd[8]
            assigned = []
            for figure, slots in spans:
                for slot_index, _local in enumerate(slots):
                    assigned.append((figure, slot_index, len(slots)))
            assert assigned.count((8, 0, 2)) == 2
            assert plan  # the even turn still paints type 7
    for turn, expected in ((0, 13), (1, 14)):
        epb = _FIGURE_METERS["3/4"][1]
        phrase = _joined(0, [60] * (5 * epb), held=True)
        ctx = _many((phrase,), kind="3/4", bpm=72)
        assert select_torroba_spans(ctx, phrase, "castillo", n=turn, previous=None) == [
            (expected, (0, 1, 2, 3, 4))
        ]
        long_phrase = _joined(0, [60] * (11 * epb), held=True)
        long_ctx = _many((long_phrase,), kind="3/4", bpm=72)
        assert select_torroba_spans(long_ctx, long_phrase, "castillo", n=turn, previous=None) == [
            (expected, tuple(range(9))),
            (expected, (9, 10)),
        ]
        full = _joined(0, [60] * (18 * epb), held=True)
        full_ctx = _many((full,), kind="3/4", bpm=72)
        assert select_torroba_spans(full_ctx, full, "castillo", n=turn, previous=None) == [
            (expected, tuple(range(9))),
            (expected, tuple(range(9, 18))),
        ]
    epb_68 = _FIGURE_METERS["6/8"][1]
    for turn in (0, 1):
        phrase = _joined(0, [60] * (5 * epb_68), held=True)
        ctx = _many((phrase,), kind="6/8", bpm=72)
        assert select_torroba_spans(ctx, phrase, "castillo", n=turn, previous=None) == []


def test_soft_lead_drops_four_and_the_pillar_bass_stays() -> None:
    """Knob 1: a steps>=2 lead is heard 4 under 64. A steps-0 bass pillar stays at 62."""
    phrase = _joined(0, [64] * 8, held=True)
    ctx = _many((phrase,), bpm=96, melody=[64] * 8)
    attacks = [
        _Attack(0.0, 64, 0.5, 1, 64, 0),
        _Attack(0.0, 40, 1.0, 3, 62, 0),
        _Attack(2.0, 64, 0.5, 1, 64, 2),
        _Attack(2.0, 40, 1.0, 3, 62, 0),
        _Attack(2.0, 55, 0.5, 2, 56, 0),
    ]
    lead, support, low = _realize(ctx, 0, attacks)
    pillar = next(note for note in low if note.beat == pytest.approx(0.0))
    assert pillar.velocity == 62
    soft = next(note for note in lead if note.beat == pytest.approx(2.0))
    assert soft.velocity == 60
    covered_bass = next(note for note in low if note.beat == pytest.approx(2.0))
    assert covered_bass.velocity == 58
    assert support[0].velocity == 54
    alone, _support, _low = _realize(ctx, 0, [_Attack(2.0, 64, 0.5, 1, 64, 2)])
    assert alone[0].velocity == 60


@pytest.mark.parametrize("figure", [13, 14])
@pytest.mark.parametrize("length", [2, 3, 4, 5, 6, 7, 8, 9])
def test_castillo_34_sentences_engrave_and_remain_playable(figure: int, length: int) -> None:
    meter, epb, strong, bar_beats = _FIGURE_METERS["3/4"]
    pitches = [64 + (idx % 5) for idx in range(length * epb)]
    phrase = _joined(0, pitches, held=True)
    ctx = _ctx(
        melody=pitches,
        phrase=phrase,
        kind="3/4",
        epb=epb,
        strong=strong,
        bpm=72,
        character="selloff",
        bars=length,
        chord=EM,
        mode="minor",
        bar_beats=bar_beats,
    )
    parts = [
        render_torroba_figure(ctx, bar, phrase, "castillo", figure, index=bar, count=length)
        for bar in range(length)
    ]
    score = _engrave(ctx, parts)
    assert_playable(score, profiles="torroba")
    _assert_measures_sum(score)
    if figure == 13:
        # Bar 0 opens with the rasgueado fan; the final bar holds the whole-bar bass arrival.
        assert any(0.0 < note.beat < 0.25 for note in score.lead if note.bar == 0)
        last_bass = [
            note
            for note in score.low
            if note.bar == length - 1 and note.midi is not None and note.beat == pytest.approx(0.0)
        ]
        assert last_bass and sum(note.duration_beats for note in last_bass) == pytest.approx(3.0)
    else:
        # Bar 0 is the shared hold/pickup bar (#11); the final bar ends on three quarter bass steps.
        first_bass = [
            note
            for note in score.low
            if note.bar == 0 and note.midi is not None and note.beat == pytest.approx(0.0)
        ]
        assert first_bass and sum(note.duration_beats for note in first_bass) == pytest.approx(3.0)
        final_bass = [
            note
            for note in score.low
            if note.bar == length - 1 and note.midi is not None
        ]
        assert [round(note.beat, 2) for note in final_bass] == [0.0, 1.0, 2.0]


def test_castillo_34_sentences_keep_micro_velocity_contours() -> None:
    meter, epb, strong, bar_beats = _FIGURE_METERS["3/4"]
    pitches = [67] * (9 * epb)
    phrase = _joined(0, pitches, held=True)
    ctx = _ctx(
        melody=pitches,
        phrase=phrase,
        kind="3/4",
        epb=epb,
        strong=strong,
        bpm=72,
        character="selloff",
        bars=9,
        chord=EM,
        mode="minor",
        bar_beats=bar_beats,
    )
    # Sentence 1 (type 13):
    # Bar 0 (`fan`): rolled chord lead at 64, then eighths 1..5 climb from 60 -> 60 -> 62 -> 62 -> 64.
    fan_lead, _fan_sup, _fan_low = render_torroba_figure(ctx, 0, phrase, "castillo", 13, index=0, count=9)
    assert [note.velocity for note in fan_lead if note.midi is not None] == [64, 60, 60, 62, 62, 64]
    # Bar 1 (`quarters`): three quarter notes taper 64 -> 62 -> 60.
    q_lead, _q_sup, _q_low = render_torroba_figure(ctx, 1, phrase, "castillo", 13, index=1, count=9)
    assert [note.velocity for note in q_lead if note.midi is not None] == [64, 62, 60]
    # Bar 2 (`turn`): upper-neighbor eighth group shapes 64, 60, 62, 60, then quarter 62.
    t_lead, _t_sup, _t_low = render_torroba_figure(ctx, 2, phrase, "castillo", 13, index=2, count=9)
    assert [note.velocity for note in t_lead if note.midi is not None] == [64, 60, 62, 60, 62]
    # Bar 8 (`hold`, bar #11): whole-bar bass under pickup eighths rising to the quarter arrival.
    h_lead, _h_sup, h_low = render_torroba_figure(ctx, 8, phrase, "castillo", 13, index=8, count=9)
    assert h_low[0].duration_beats == pytest.approx(3.0)
    assert h_lead[0].velocity < h_lead[-1].velocity == 64

    # Sentence 2 (type 14):
    # Bars 1 and 2 (`chords_a` -> `chords_b`): crescendo across the two three-chord bars.
    ca_lead, _ca_sup, _ca_low = render_torroba_figure(ctx, 1, phrase, "castillo", 14, index=1, count=9)
    cb_lead, _cb_sup, _cb_low = render_torroba_figure(ctx, 2, phrase, "castillo", 14, index=2, count=9)
    assert [note.velocity for note in ca_lead if note.midi is not None] == [60, 60, 62]
    assert [note.velocity for note in cb_lead if note.midi is not None] == [62, 62, 64]
    # Bar 3 (`burst`): downbeat 64, then the mordent and the two later quarters settle at 60.
    burst_lead, _burst_sup, _burst_low = render_torroba_figure(ctx, 3, phrase, "castillo", 14, index=3, count=9)
    assert [note.velocity for note in burst_lead if note.midi is not None] == [64, 60, 60, 60, 60, 60]
    # Bar 4 (`echo`): three chords taper 64 -> 62 -> 60.
    ec_lead, _ec_sup, _ec_low = render_torroba_figure(ctx, 4, phrase, "castillo", 14, index=4, count=9)
    assert [note.velocity for note in ec_lead if note.midi is not None] == [64, 62, 60]
    # Bar 5 (`dotted`): dotted-quarter 64, light eighth 60, quarter 62.
    dt_lead, _dt_sup, _dt_low = render_torroba_figure(ctx, 5, phrase, "castillo", 14, index=5, count=9)
    assert [note.velocity for note in dt_lead if note.midi is not None] == [64, 60, 62]
    # Bar 8 (`final`): the held G4 stays the written 64, not a harmonic 48.
    # The bass line arrives on E and steps 58 -> 60 -> 62.
    fn_lead, _fn_sup, fn_low = render_torroba_figure(ctx, 8, phrase, "castillo", 14, index=8, count=9)
    assert [(note.midi, note.velocity) for note in fn_lead if note.midi is not None] == [(67, 64)]
    assert fn_lead[0].accent is True
    bass = [note for note in fn_low if note.midi is not None]
    assert [note.velocity for note in bass] == [58, 60, 62]
    assert [note.midi for note in bass] == [50, 51, 52]


def test_cadence_bass_arrives_on_the_root_and_arada_keeps_its_window() -> None:
    """The cadence bass steps into the root. Arada's scale stays in 40–52 when transposed."""
    _meter, epb, strong, bar_beats = _FIGURE_METERS["3/4"]
    # Em has no degree under E2, so the line rises D–Eb–E into E3 instead of leaping to the open string.
    for lead, chord, mode, line in (
        (60, EM, "minor", [50, 51, 52]),
        (64, EM, "minor", [50, 51, 52]),
        (67, EM, "minor", [50, 51, 52]),
        (72, EM, "minor", [50, 51, 52]),
        (76, EM, "minor", [50, 51, 52]),
        (67, C, "major", [45, 47, 48]),
    ):
        pitches = [lead] * (9 * epb)
        phrase = _joined(0, pitches, held=True)
        ctx = _ctx(
            melody=pitches,
            phrase=phrase,
            kind="3/4",
            epb=epb,
            strong=strong,
            bpm=72,
            character="selloff",
            bars=9,
            chord=chord,
            mode=mode,
            bar_beats=bar_beats,
        )
        _sung, _support, low = render_torroba_figure(ctx, 8, phrase, "castillo", 14, index=8, count=9)
        bass = [note.midi for note in low if note.midi is not None]
        assert bass == line
    arada = [67] * 40
    phrase = _joined(0, arada, held=True)
    ctx = _ctx(melody=arada, phrase=phrase, kind="4/4", bars=5, chord=EM, mode="minor")
    ctx.semitones = 3
    _lead, _support, low = render_torroba_figure(ctx, 4, phrase, "castillo", 7, index=4, count=5)
    written = [note.midi for note in low if note.midi is not None and note.beat > 0]
    assert written
    assert all(40 <= midi <= 52 for midi in written)


def test_castillo_34_repeats_past_nine_bars_and_stays_playable() -> None:
    """A phrase longer than nine bars repeats the sentence instead of sustaining the tail."""
    _meter, epb, strong, bar_beats = _FIGURE_METERS["3/4"]
    for length, semitones, key in ((12, 0, C_KEY), (18, 0, C_KEY), (18, 3, EB_KEY)):
        pitches = [60 + (index % 7) for index in range(length * epb)]
        phrase = _joined(0, pitches, held=True)
        ctx = _ctx(
            melody=pitches,
            phrase=phrase,
            kind="3/4",
            epb=epb,
            strong=strong,
            bpm=72,
            character="selloff",
            bars=length,
            chord=EM,
            mode="minor",
            bar_beats=bar_beats,
        )
        ctx.semitones = semitones
        for turn in (0, 1):
            spans = select_torroba_spans(ctx, phrase, "castillo", n=turn, previous=None)
            covered = [bar for _figure, slots in spans for bar in slots]
            assert covered == list(range(length))
            parts = [
                render_torroba_figure(
                    ctx, bar, phrase, "castillo", figure, index=slot_index, count=len(slots)
                )
                for figure, slots in spans
                for slot_index, bar in enumerate(slots)
            ]
            score = _engrave(ctx, parts)
            assert_playable(score, key=key, profiles="torroba")
            _assert_measures_sum(score)


def _lead_in_eighth(notes, offset: int) -> NoteEvent:
    """The one sounding lead whose onset falls in this eighth, including a rolled downbeat."""
    found = [
        note
        for note in notes
        if note.midi is not None and offset - 1e-9 <= note.beat * 2 < offset + 1 - 1e-9
    ]
    assert len(found) == 1
    return found[0]


def _six_eight(melody: list[int], phrase: Phrase, *, bars: int | None = None):
    return _ctx(
        melody=melody,
        phrase=phrase,
        kind="6/8",
        epb=6,
        strong=(0, 3),
        character="calm",
        bars=bars,
        bar_beats=3,
        chord=C,
    )


def test_six_eight_dance_grid_writes_a_secondary_accent() -> None:
    """Danza and Fandanguillo 6/8, written before the wave, on a flat phrase."""
    phrase = _joined(0, [72] * 6)
    assert phrase.rise == 0
    ctx = _six_eight([72] * 6, phrase)
    with compose_meter(METER_68):
        danced, _support, _low = _render_torroba_bar(ctx, 0, phrase, "danza")
        fan, _support, _low = _render_torroba_bar(ctx, 0, phrase, "fandanguillo")
    ordered = sorted((note for note in danced if note.midi is not None), key=lambda note: note.beat)
    assert [round(note.beat, 2) for note in ordered] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    assert [note.velocity for note in ordered] == [68, 64, 64, 66, 64, 64]
    assert [note.accent for note in ordered] == [True, False, False, False, False, False]

    down = _lead_in_eighth(fan, 0)
    middle = _lead_in_eighth(fan, 2)
    secondary = _lead_in_eighth(fan, 3)
    assert down.beat != pytest.approx(0.0)
    assert [down.velocity, middle.velocity, secondary.velocity] == [68, 64, 66]
    assert down.accent and not middle.accent and not secondary.accent


def test_alcaniz_dance_secondary_accent_and_opening_arrival() -> None:
    """Full dance steps eighth 3. Pushed stays ordinary. The opening arrival stays accented."""
    phrase = _joined(0, [72] * 6, held=True)
    assert phrase.rise == 0
    ctx = _six_eight([72] * 6, phrase)
    with compose_meter(METER_68):
        full, _support, _low = _alcaniz_dance(ctx, 0, phrase, accented=True)
        pushed, _support, _low = _alcaniz_dance(ctx, 0, phrase, accented=False)
        opened, _support, _low = _alcaniz_opening(ctx, 0, phrase)
    full_leads = sorted(full, key=lambda note: note.beat)
    pushed_leads = sorted(pushed, key=lambda note: note.beat)
    assert [note.velocity for note in full_leads] == [68, 66]
    assert [note.accent for note in full_leads] == [True, False]
    assert [round(note.beat, 2) for note in full_leads] == [0.0, 1.5]
    assert [note.velocity for note in pushed_leads] == [64, 64]
    assert [note.accent for note in pushed_leads] == [False, False]
    arrival = _at(opened, 1.5)
    assert arrival.velocity == 68 and arrival.accent and arrival.slur_stop

    left = _joined(0, [72] * 6, held=True)
    right = _joined(6, [72] * 6, held=True)
    pushed_ctx = _many((left, right), kind="6/8", melody=[72] * 12)
    with compose_meter(METER_68):
        rendered, _support, _low = _render_torroba_bar(pushed_ctx, 1, right, "alcaniz")
    rendered_leads = sorted(rendered, key=lambda note: note.beat)
    assert [note.duration_beats for note in rendered_leads] == [pytest.approx(0.5), pytest.approx(0.5)]
    assert [note.velocity for note in rendered_leads] == [64, 64]
    assert all(not note.accent for note in rendered_leads)


def test_three_four_offbeats_step_outside_the_owning_apex() -> None:
    """Sonatina 3/4 writes 64, 62, 62 outside a flat phrase's trivial apex."""
    melody = [72, 72, 72, 72, 72, 72]
    phrase = _joined(0, melody, held=True)
    assert phrase.rise == 0
    assert abs(melody[0] - melody[4]) <= 2
    ctx = _ctx(
        melody=melody,
        phrase=phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        character="calm",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_34):
        lead, _support, _low = _render_torroba_bar(ctx, 0, phrase, "sonatina")
    assert _at(lead, 0.0).velocity == 64 and _at(lead, 0.0).accent
    assert _at(lead, 1.0).velocity == 62 and _at(lead, 1.0).duration_beats == pytest.approx(0.5)
    assert _at(lead, 1.5).velocity == 62 and _at(lead, 1.5).duration_beats == pytest.approx(0.5)
    assert _at(lead, 2.0).velocity == 62 and _at(lead, 2.0).duration_beats == pytest.approx(1.0)
    assert not any(note.midi is not None and note.beat == pytest.approx(2.5) for note in lead)

    # Rise 1 still has a real apex. Eighth 4 keeps its written level; eighth 2 drops.
    small = [71, 71, 71, 71, 72, 71]
    small_phrase = _joined(0, small, held=True)
    assert small_phrase.rise == 1
    assert len({run.midi for run in small_phrase.runs}) > 1
    assert small_phrase.apex.start == 4 and abs(small[0] - small[4]) <= 2
    small_ctx = _ctx(
        melody=small,
        phrase=small_phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        character="calm",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_34):
        small_lead, _support, _low = _render_torroba_bar(small_ctx, 0, small_phrase, "sonatina")
    small_apex = _apex_eighths(small_ctx.phrases)
    apex_level = _note_velocity(4, 1, small_apex, small_phrase)
    off_level = _note_velocity(2, 1, small_apex, small_phrase)
    assert apex_level == 72 and off_level == 64
    assert _at(small_lead, 2.0).velocity == apex_level
    assert _at(small_lead, 1.0).velocity == max(40, off_level - 2)
    assert _at(small_lead, 0.0).velocity == 64 and _at(small_lead, 0.0).accent

    # A sentence that opens on eighth 4 keeps that eighth when the peak is there.
    opening = _joined(0, [72, 72, 72, 72], held=True)
    following = _joined(4, [74, 72])
    assert following.rise > 0 and following.apex.start == 4
    split = [72, 72, 72, 72, 74, 72]
    assert abs(split[0] - split[4]) <= 2
    split_ctx = _many((opening, following), kind="3/4", melody=split)
    with compose_meter(METER_34):
        split_lead, _support, _low = _render_torroba_bar(split_ctx, 0, opening, "sonatina")
    apex = _apex_eighths(split_ctx.phrases)
    kept = _note_velocity(4, 1, apex, following)
    assert kept == 72
    assert _at(split_lead, 2.0).velocity == kept
    assert _at(split_lead, 0.0).velocity == 64 and _at(split_lead, 0.0).accent
    assert _at(split_lead, 1.0).velocity == 62
    assert _at(split_lead, 1.5).velocity == 62

    # 4/4 does not take the 3/4 slope.
    four_phrase = _joined(0, [72] * 8, held=True)
    four = _ctx(melody=[72] * 8, phrase=four_phrase, kind="4/4", character="calm", chord=C)
    with compose_meter(METER_44):
        four_lead, _support, _low = _render_torroba_bar(four, 0, four_phrase, "sonatina")
    assert _at(four_lead, 0.0).velocity == 64 and _at(four_lead, 0.0).accent
    assert _at(four_lead, 1.0).velocity == 64
    assert _at(four_lead, 2.0).velocity == 64 and _at(four_lead, 2.0).accent


def test_juglar_flat_bar_steps_the_later_beats() -> None:
    """Beat 1 stays 64. Beats 2 and 3 step the fingers down to 62 on a chunk and on a quarter-note bar."""
    phrase = _joined(0, [72] * 6, held=True)
    assert phrase.rise == 0
    ctx = _ctx(
        melody=[72] * 6,
        phrase=phrase,
        kind="3/4",
        epb=6,
        strong=(0,),
        bpm=72,
        character="calm",
        bar_beats=3,
        chord=C,
    )
    with compose_meter(METER_34):
        fingers, _support, _low = _render_torroba_bar(ctx, 0, phrase, "torroba_tremolo")
        quarters, _support, _low = _render_torroba_bar(ctx, 0, phrase, "torroba_tremolo", ["torroba_tremolo"])
    for quarter, eighth in enumerate((0, 2, 4)):
        attacks = sorted(
            (note for note in fingers if quarter - 1e-9 <= note.beat < quarter + 1 - 1e-9),
            key=lambda note: note.beat,
        )
        assert len(attacks) == 3
        assert attacks[0].velocity == (64 if eighth == 0 else 62)
        assert attacks[1].velocity == attacks[0].velocity - 3
        assert attacks[2].velocity == attacks[0].velocity - 4
        assert attacks[0].accent is (eighth == 0)
    ordered = sorted(quarters, key=lambda note: note.beat)
    assert [note.velocity for note in ordered] == [64, 62, 62]
    assert [note.duration_beats for note in ordered] == [pytest.approx(1.0), pytest.approx(1.0), pytest.approx(1.0)]
    assert all(not note.accent for note in ordered)


@pytest.mark.parametrize("kind", ["4/4", "3/4", "6/8"])
def test_type4_call_sixteenths_take_two_steps(kind: str) -> None:
    """Flat phrase: both sixteenths share steps 2, and the eighth stays at steps 1."""
    _ctx_figure, phrase, parts = _flat_figure(kind, 4)
    assert phrase.rise == 0
    lead = [note for note in parts[0][0] if note.midi is not None]
    first = _at(lead, 0.5)
    second = _at(lead, 0.75)
    eighth = _at(lead, 1.0)
    assert first.duration_beats == pytest.approx(0.25)
    assert second.duration_beats == pytest.approx(0.25)
    assert eighth.duration_beats == pytest.approx(0.5)
    assert first.velocity == 60 and second.velocity == 60
    assert eighth.velocity == 62
    assert not first.tenuto and not second.tenuto and not eighth.tenuto


