"""Even base-grid stretches sing a fifth lower. A 34-bar day stays one pattern."""

import inspect
from dataclasses import replace

from app.sonify.chords import C
from app.sonify.form import METER_34, METER_44, ChordSlot, FormSection, compose_meter
from app.sonify.guitar import render_guitar_score
from app.sonify.guitar_patterns import (
    _Ctx,
    _lower_torroba_pitch,
    _lower_torroba_stretches,
    _patterns,
    _torroba_base_stretches,
    form_pattern_ids,
    render_patterned_voices,
)
from app.sonify.guitar_scale_passages import ScalePassage, ScalePlan
from app.sonify.guitar_torroba import _scale_degree_below, torroba_figure_plan
from app.sonify.keys import C_KEY, compose_register, register_for
from app.sonify.model import HarmonyEvent, NoteEvent, Phrase, Run


def _phrase(start_bar: int, bars: int, epb: int, midi: int = 67) -> Phrase:
    start = start_bar * epb
    end = (start_bar + bars) * epb
    return Phrase(start, end, (Run(start, end - start, midi),), held_over=True)


def _ctx(
    *,
    bars: int,
    phrases: tuple[Phrase, ...],
    kind: str = "4/4",
    epb: int = 8,
    strong: tuple[int, ...] = (0, 4),
    melody: list[int] | None = None,
    character: str = "calm",
    bpm: int = 96,
    sections: tuple = (),
    mode: str = "major",
    semitones: int = 0,
) -> _Ctx:
    count = bars * epb
    line = list(melody) if melody is not None else [67] * count
    kinds = {bar: "phrase" for bar in range(bars)}
    for section in sections:
        for bar in range(section.start, section.end):
            kinds[bar] = section.kind
    return _Ctx(
        melody=line,
        raw=list(line),
        chord_at={bar: C for bar in range(bars)},
        kind_at=kinds,
        band_at={bar: "mf" for bar in range(bars)},
        phrases=phrases,
        bars=bars,
        bpm=bpm,
        ensemble="torroba",
        mode=mode,
        character=character,
        character_at=None,
        sections=sections,
        rel_span=0.02,
        semitones=semitones,
        bass_low=40 - semitones,
        bass_high=53 - semitones,
        mid_low=50 - semitones,
        mid_high=65 - semitones,
        treble_floor=59 - semitones,
        treble_top=81 - semitones,
        ceiling=83 - semitones,
        epb=epb,
        kind=kind,
        strong=strong,
        bar_beats=epb / 2,
        regime_at={bar: "sideway" for bar in range(bars)},
    )


def _framed_day(kind: str, character: str, bars: int = 34, bpm: int = 96) -> _Ctx:
    epb = 8 if kind == "4/4" else 6
    strong = (0, 4) if kind == "4/4" else (0,)
    intro, outro = 2, 2
    sections = (
        FormSection(0, intro, "intro", 0),
        FormSection(intro, bars - outro, "phrase", 0),
        FormSection(bars - outro, bars, "outro", 0),
    )
    phrases = tuple(_phrase(bar, 1, epb) for bar in range(bars))
    return _ctx(
        bars=bars,
        phrases=phrases,
        kind=kind,
        epb=epb,
        strong=strong,
        character=character,
        sections=sections,
        bpm=bpm,
    )


def _lead_at(lead, bar: int, beat: float, *, minimum: float = 0.5) -> NoteEvent:
    found = [
        note
        for note in lead
        if note.midi is not None
        and note.bar == bar
        and abs(note.beat - beat) < 1e-6
        and note.duration_beats + 1e-9 >= minimum
    ]
    assert found, (bar, beat, [(note.beat, note.midi, note.duration_beats) for note in lead if note.bar == bar])
    return found[0]


def test_even_stretches_drop_a_diatonic_fifth_and_figure_bars_stay_up() -> None:
    """Index 0 lowers, including the first stretch. A figure bar splits the run.

    The phrase still lowers the base-grid bars on either side of its figures.
    The next phrase starts the next index, so a bar that merely follows a
    lowered bar stays up when it is its own phrase.
    """
    epb = 8
    phrases = (_phrase(0, 8, epb), _phrase(8, 1, epb))
    ctx = _ctx(bars=9, phrases=phrases)
    patterns = ["sonatina", "sonatina"]
    plan = torroba_figure_plan(ctx, patterns)
    assert _torroba_base_stretches(ctx, plan) == [[2], [4], [7], [8]]
    assert {0, 1, 3, 5, 6} <= set(plan)
    _lower_torroba_stretches(ctx, plan)
    for bar in (2, 7):
        assert ctx.melody[bar * epb : (bar + 1) * epb] == [60] * epb
    for bar in (0, 1, 3, 4, 5, 6, 8):
        assert ctx.melody[bar * epb : (bar + 1) * epb] == [67] * epb


def test_the_fifth_is_four_scale_steps_and_a_strong_eighth_takes_a_chord_tone() -> None:
    ctx = _ctx(bars=1, phrases=(_phrase(0, 1, 8),))
    # F4 down four degrees is B3, six semitones, not midi - 7.
    assert _scale_degree_below(65, 4, "major") == 59
    assert _lower_torroba_pitch(ctx, 1, 65) == 59
    assert _lower_torroba_pitch(ctx, 0, 65) == 55
    # E4's fifth is A3. The downbeat takes G3, the nearest chord tone under it.
    assert _scale_degree_below(64, 4, "major") == 57
    assert _lower_torroba_pitch(ctx, 2, 64) == 57
    assert _lower_torroba_pitch(ctx, 0, 64) == 55


def test_a_fifth_under_the_floor_rises_to_the_scale_tone_on_the_floor() -> None:
    ctx = _ctx(bars=1, phrases=(_phrase(0, 1, 8),))
    # A3 walks G, F, E, D. That fifth is D3, still under sounding 55.
    # The scale tone on the floor is G3.
    assert _scale_degree_below(57, 4, "major") == 50
    assert _lower_torroba_pitch(ctx, 1, 57) == 55
    assert _lower_torroba_pitch(ctx, 1, 57) < 57


def test_a_retimed_day_is_one_pattern_name() -> None:
    for character in ("calm", "selloff"):
        ctx = _framed_day("3/4", character)
        patterns = _patterns(ctx)
        body = [patterns[bar] for bar in range(ctx.bars) if ctx.kind_at[bar] == "phrase"]
        assert body
        assert len(set(body)) == 1
        assert form_pattern_ids(ctx, patterns) == [body[0]]

    rally = _framed_day("4/4", "rally")
    painted = _patterns(rally)
    body = [painted[bar] for bar in range(rally.bars) if rally.kind_at[bar] == "phrase"]
    assert len(set(body)) == 1
    assert form_pattern_ids(rally, painted) == ["olite"]

    # A movement that is not a day still alternates. 72 is the slow calm row.
    longer = _framed_day("3/4", "calm", bars=32, bpm=72)
    painted = _patterns(longer)
    assert form_pattern_ids(longer, painted) == ["castillo", "torroba_tremolo", "castillo"]


def test_lowered_lead_stays_on_voice_1_and_drops_support_at_62() -> None:
    epb = 6
    phrases = (_phrase(0, 1, epb), _phrase(1, 1, epb))
    melody = [67] * (2 * epb)
    register = register_for(C_KEY)
    with compose_meter(METER_34), compose_register(C_KEY, register):
        lead, support, _low, _divisions = render_patterned_voices(
            melody=list(melody),
            raw_pitches=list(melody),
            phrases=phrases,
            chord_at={bar: C for bar in range(2)},
            kind_at={bar: "phrase" for bar in range(2)},
            band_at={bar: "mf" for bar in range(2)},
            musical_bars=2,
            total_eighths=len(melody),
            bpm=96,
            ensemble="torroba",
            mode="major",
            character="calm",
            character_at=None,
            sections=(),
            rel_span=0.02,
            register=register,
        )
    down = _lead_at(lead, 0, 0.0)
    assert down.voice == 1 and down.midi == 60
    later = _lead_at(lead, 0, 2.0)
    assert later.voice == 1 and later.midi == 60
    kept = _lead_at(lead, 1, 0.0)
    assert kept.voice == 1 and kept.midi == 67
    assert all(note.voice == 1 for note in lead if note.midi == 60)
    assert not [note for note in support if note.midi is not None and note.bar == 0]
    assert any(note.midi is not None and note.bar == 1 for note in support)


def test_a_passage_reads_the_original_line_and_leaves_the_other_eighths_lowered(monkeypatch) -> None:
    epb = 6
    phrases = (_phrase(0, 1, epb), _phrase(1, 1, epb))
    melody = [67] * (2 * epb)
    seen: dict[str, list[int]] = {}
    real_plan = ScalePlan(
        0,
        0,
        0,
        0,
        (
            ScalePassage(
                start=0,
                target=0,
                direction="up",
                net_span=0,
                score=1.0,
                retreat_spans=(),
                sub_bar=True,
                passage_eighths=1,
                replaced_base_intrinsic_eighths=0,
            ),
        ),
        (),
        (),
        0,
    )

    def fake(ctx, patterns, lead, support, low):
        del patterns
        seen["melody"] = list(ctx.melody)
        rewritten = []
        for event in lead:
            if event.bar == 0 and abs(event.beat) < 1e-6 and event.midi is not None:
                rewritten.append(replace(event, midi=67))
            else:
                rewritten.append(event)
        return rewritten, support, low, real_plan

    monkeypatch.setattr("app.sonify.guitar_scale_passages.apply_scale_passages", fake)
    register = register_for(C_KEY)
    with compose_meter(METER_34), compose_register(C_KEY, register):
        lead, _support, _low, _divisions = render_patterned_voices(
            melody=list(melody),
            raw_pitches=list(melody),
            phrases=phrases,
            chord_at={bar: C for bar in range(2)},
            kind_at={bar: "phrase" for bar in range(2)},
            band_at={bar: "mf" for bar in range(2)},
            musical_bars=2,
            total_eighths=len(melody),
            bpm=96,
            ensemble="torroba",
            mode="major",
            character="calm",
            character_at=None,
            sections=(),
            rel_span=0.02,
            register=register,
        )
    assert seen["melody"] == melody
    assert _lead_at(lead, 0, 0.0).midi == 67
    assert _lead_at(lead, 0, 2.0).midi == 60
    assert _lead_at(lead, 1, 0.0).midi == 67


def test_render_guitar_score_forwards_movement_index(monkeypatch) -> None:
    parameter = inspect.signature(render_guitar_score).parameters["movement_index"]
    assert parameter.default is None
    seen: dict[str, int | None] = {}

    def spy(**kwargs):
        seen["movement_index"] = kwargs["movement_index"]
        return [], [], [], 2

    monkeypatch.setattr("app.sonify.guitar_patterns.render_patterned_voices", spy)
    pitches = [72] * 8
    slots = (ChordSlot(0, 1, C, "sideway", "phrase"),)
    register = register_for(C_KEY)
    with compose_meter(METER_44), compose_register(C_KEY, register):
        render_guitar_score(
            title="Torroba",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=pitches,
            phrases=(_phrase(0, 1, 8),),
            dynamics=(),
            bands=["mf"],
            band_at={0: "mf"},
            musical_bars=1,
            total_eighths=8,
            bpm=96,
            ensemble="torroba",
            harmonies=(HarmonyEvent(0, C),),
            mode="major",
            character="calm",
            sections=(FormSection(0, 1, "phrase", 0),),
            rel_span=0.0,
            movement_index=0,
        )
    assert seen["movement_index"] == 0
