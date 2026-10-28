"""Allocation and realization of classical-guitar scale passages."""

from dataclasses import dataclass, replace

import math

from app.sonify.form import METER_44, METER_68, ChordSlot, FormSection, compose_meter
from app.sonify.chords import AM, C, KIND_MAJOR, Chord
from app.sonify.guitar import BARRIOS_TREMOLO_MIN_BPM
from app.sonify.guitar_bach import _fuga_motif
from app.sonify.guitar_patterns import (
    _Ctx,
    _assert_scale_positions,
    _dur16,
    _eighth_event,
    _playable,
    _spell16,
    _splice,
    _start16,
    assert_playable,
    render_patterned_voices,
    Unplayable,
)
from app.sonify.guitar_scale_passages import (
    SCALE_SIXTEENTH_MIN_BPM,
    ScalePassage,
    _BASS,
    _MELODY_APEX,
    _Slot,
    _assign,
    _color_line,
    _compass,
    _curve,
    _groups_ok,
    _scale_need,
    _majority_pattern,
    _monotone,
    _fast_line,
    _slots,
    _pattern_window,
    _stamp_arrival,
    hairpin_velocities,
    plan_scale_budget,
    realize_scale_passage,
    select_scale_plan,
)
from app.sonify.keys import A_KEY, BB_KEY, C_KEY, D_KEY, EB_KEY, compose_register, register_for
from app.sonify.model import NoteEvent, Phrase, Run, Score


@dataclass(frozen=True)
class _Impulse:
    start: int
    target: int
    direction: str
    net_span: int
    score: float = 1.0
    adjusted_efficiency: float = 1.0
    retreat_spans: tuple = ()
    sub_bar: bool = False


def _phrase(start: int, pitches: list[int]) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs))


def _ctx(
    melody: list[int],
    phrases: tuple[Phrase, ...],
    *,
    epb: int = 8,
    kind: str = "4/4",
    strong: tuple[int, ...] = (0, 4),
    bpm: int = 96,
    ensemble: str = "bach",
    character: str = "rally",
    bands: dict[int, str] | None = None,
    sections: tuple = (),
    impulses: tuple = (),
    raw: list[int] | None = None,
) -> _Ctx:
    bars = len(melody) // epb
    return _Ctx(
        melody=list(melody),
        raw=list(raw if raw is not None else melody),
        chord_at={bar: C for bar in range(bars)},
        kind_at={bar: "phrase" for bar in range(bars)},
        band_at=bands or {bar: "mf" for bar in range(bars)},
        phrases=phrases,
        bars=bars,
        bpm=bpm,
        ensemble=ensemble,
        mode="major",
        character=character,
        character_at=None,
        sections=sections,
        rel_span=0.0,
        semitones=0,
        bass_low=40,
        bass_high=53,
        mid_low=50,
        mid_high=65,
        treble_floor=59,
        treble_top=81,
        ceiling=83,
        epb=epb,
        kind=kind,
        strong=strong,
        bar_beats=epb / 2,
        impulses=tuple(impulses),
    )


def _render(
    melody: list[int],
    phrases: tuple[Phrase, ...],
    impulses: tuple,
    *,
    ensemble: str,
    bpm: int,
    key=C_KEY,
    character: str = "rally",
    bands: dict[int, str] | None = None,
    raw: list[int] | None = None,
    sections: tuple = (),
    rel_span: float = 0.0,
    meter=METER_44,
) -> Score:
    register = register_for(key)
    epb = meter.eighths_per_bar
    bars = len(melody) // epb
    band_at = bands or {bar: "mf" for bar in range(bars)}
    with compose_meter(meter), compose_register(key, register):
        lead, support, low, divisions = render_patterned_voices(
            melody=list(melody),
            raw_pitches=list(raw if raw is not None else melody),
            phrases=phrases,
            chord_at={bar: C for bar in range(bars)},
            kind_at={bar: "phrase" for bar in range(bars)},
            band_at=band_at,
            musical_bars=bars,
            total_eighths=len(melody),
            bpm=bpm,
            ensemble=ensemble,
            mode="major",
            character=character,
            character_at=None,
            sections=sections,
            rel_span=rel_span,
            register=register,
            impulses=tuple(impulses),
        )
    return Score(
        title="Guitar",
        bpm=bpm,
        bars=bars,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=tuple(ChordSlot(bar, 1, C, "sideway", "phrase") for bar in range(bars)),
        high=(),
        lead=tuple(lead),
        support=tuple(support),
        comp=(),
        low=tuple(low),
        dynamics=(),
        harmonies=(),
        liquidity=tuple(band_at[bar] for bar in range(bars)),
        phrases=phrases,
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble=ensemble,
        divisions=divisions,
        key=key,
        bar_beats=meter.quarter_beats,
        scale_eighths=tuple(getattr(lead, "scale_eighths", ())),
        long_scale_eighths=tuple(getattr(lead, "long_scale_eighths", ())),
    )


def _ordered(events: tuple[NoteEvent, ...] | list[NoteEvent], epb: int = 8):
    found = []
    for event in events:
        if event.midi is None:
            continue
        start = event.bar * epb * 2 + int(round(event.beat * 4))
        found.append((start, event))
    found.sort(key=lambda item: item[0])
    return found


def _climb(start: int = 64) -> list[int]:
    """One bar of chord tones on the strong eighths, then a held close."""
    bar = [start, start + 1, start + 1, start + 2, start + 3, start + 5, start + 6, start + 7]
    return bar + [start + 8] + [start + 8] * 23


def test_group1_drops_the_whole_passage() -> None:
    melody = [64, 65, 66, 67, 69, 70, 71, 72] * 4
    phrases = (_phrase(0, melody[:16]), _phrase(16, melody[16:]))
    crossing = _Impulse(8, 20, "up", 8, score=4)
    whole = plan_scale_budget(
        _ctx(melody, (_phrase(0, melody),), impulses=(_Impulse(0, 16, "up", 8, score=4),)),
        ["tremolo"],
    )
    # The gate is open, so the bar after the tremolo region's opening is a scale.
    assert [(item.start, item.target) for item in whole.passages] == [(8, 16)]
    # The tremolo-touching run is shortened. The group-3 remainder is kept.
    for patterns in (
        ["study", "tremolo"],
        ["study", "etude1"],
        ["study", "etude11"],
        ["study", "thumb_cantabile"],
    ):
        plan = plan_scale_budget(_ctx(melody, phrases, impulses=(crossing,)), patterns)
        assert [(item.start, item.target) for item in plan.passages] == [(8, 16)], patterns
    framed = _ctx(
        melody,
        (_phrase(0, melody),),
        sections=(FormSection(0, 4, "phrase", 0),),
        impulses=(_Impulse(0, 8, "up", 8, score=4),),
    )
    # This impulse covers the region's first bar. An empty plan here does not show that scales opened.
    assert plan_scale_budget(framed, ["preludio"]).passages == ()
    opened = plan_scale_budget(
        replace(framed, impulses=(_Impulse(8, 16, "up", 8, score=4),)),
        ["preludio"],
    )
    assert [(item.start, item.target) for item in opened.passages] == [(8, 16)]
    plain = _ctx(melody, (_phrase(0, melody),), impulses=(_Impulse(0, 8, "up", 8, score=4),))
    kept = plan_scale_budget(plain, ["preludio"])
    assert kept.passages and kept.passages[0].start == 0 and kept.passages[0].target == 8
    clear = plan_scale_budget(
        _ctx(melody, phrases, impulses=(_Impulse(0, 8, "up", 8, score=2),)),
        ["study", "tremolo"],
    )
    assert [(item.start, item.target) for item in clear.passages] == [(0, 8)]


def test_sor_at_88_uses_sixteenths_without_grand_solo() -> None:
    assert SCALE_SIXTEENTH_MIN_BPM == 88
    assert BARRIOS_TREMOLO_MIN_BPM == 90
    melody = [64, 65, 66, 67, 69, 70, 71, 72] * 4
    raw = list(range(40, 72))
    score = _render(
        melody,
        (_phrase(0, melody),),
        (_Impulse(2, 8, "up", 8, score=5),),
        ensemble="classic",
        bpm=88,
        raw=raw,
    )
    lead = [note for note in score.lead if note.bar == 0 and note.midi is not None and note.duration_beats <= 0.25]
    assert lead
    assert not any(
        note.bar == 0 and abs(note.beat) < 1e-6 and note.midi is not None for note in score.support
    )


def test_straight_raw_does_not_invent_a_retreat_and_a_real_one_lands() -> None:
    melody = [64, 65, 66, 60, 67, 69, 70, 71, 72] + [72] * 23
    raw = list(range(48, 80))
    straight = _render(
        melody,
        (_phrase(0, melody),),
        (_Impulse(0, 8, "up", 8, score=5),),
        ensemble="classic",
        bpm=96,
        raw=raw,
    )
    pitches = [event.midi for _start, event in _ordered(straight.lead) if _start <= 16]
    assert pitches
    assert 60 not in pitches
    assert pitches[-1] == 72
    assert all(abs(right - left) <= 2 for left, right in zip(pitches, pitches[1:]))
    # A neighbor turn is two deliberate steps. It is not a retreat, so a fall
    # stands alone: the step before it did not fall, and the step after it does not.
    falls = [index for index, (left, right) in enumerate(zip(pitches, pitches[1:])) if right < left]
    assert falls
    for index in falls:
        if index > 0:
            assert pitches[index] >= pitches[index - 1]
        if index + 2 < len(pitches):
            assert pitches[index + 2] >= pitches[index + 1]

    retreated = _render(
        [64, 65, 66, 67, 69, 70, 71, 72] + [72] * 24,
        (_phrase(0, [64, 65, 66, 67, 69, 70, 71, 72] + [72] * 24),),
        (_Impulse(0, 8, "up", 8, score=5, retreat_spans=((1, 2),)),),
        ensemble="classic",
        bpm=96,
        raw=raw,
    )
    notes = _ordered(retreated.lead)
    arrival = next(event.midi for start, event in notes if start == 16)
    assert arrival == 72
    before = [event.midi for start, event in notes if start < 2]
    during = [event.midi for start, event in notes if 2 <= start < 4]
    assert len(before) >= 2 and during
    assert before[-1] > before[0]
    assert min(during) < before[-1]


def test_group2_bridge_waits_one_bar_and_ignores_the_tail() -> None:
    rising = [64, 65, 67, 69, 70, 72]
    held = [64] * (9 * 6)
    melody = rising + held
    phrases = (_phrase(0, rising), _phrase(6, held))
    patterns = ["bach_gigue", "bach_gigue"]
    opening = _Impulse(0, 6, "up", 6, score=9)
    bridge = _Impulse(6, 12, "up", 6, score=8)
    plan = plan_scale_budget(
        _ctx(
            melody,
            phrases,
            epb=6,
            kind="6/8",
            strong=(0, 3),
            impulses=(opening, bridge),
        ),
        patterns,
    )
    assert plan.base_intrinsic_eighths >= 3
    assert [(item.start, item.target) for item in plan.passages] == [(6, 12)]

    small = [66, 66, 65, 65, 64, 64]
    tail_melody = small + [64] * (9 * 6)
    tail = plan_scale_budget(
        _ctx(
            tail_melody,
            (_phrase(0, small), _phrase(6, tail_melody[6:])),
            epb=6,
            kind="6/8",
            strong=(0, 3),
            impulses=(
                _Impulse(0, 6, "down", 2, score=3),
                _Impulse(6, 12, "up", 6, score=4),
            ),
        ),
        patterns,
    )
    assert tail.passages and tail.passages[0].start == 6
    assert tail.tier1
    assert tail.passages[0].start - tail.tier1[0].target < 6


def test_full_intrinsic_room_adds_nothing() -> None:
    bar = [64, 66, 67, 69, 70, 72]
    melody = bar * 10
    impulse_up = _Impulse(6, 18, "up", 8, score=5)
    impulse_down = _Impulse(48, 54, "down", 3, score=9)
    plan = plan_scale_budget(
        _ctx(
            melody,
            (_phrase(0, melody),),
            epb=6,
            kind="6/8",
            strong=(0, 3),
            impulses=(impulse_up, impulse_down),
        ),
        ["bach_gigue"],
    )
    assert plan.base_intrinsic_eighths > plan.max_scale_eighths
    assert plan.room == 0
    assert plan.passages == ()
    assert plan.tier1 == ()
    assert plan.perpetual_bars == ()


def test_passages_are_chosen_before_higher_scoring_tier1() -> None:
    melody = [64] * 64
    plan = plan_scale_budget(
        _ctx(
            melody,
            (_phrase(0, melody[:32]), _phrase(32, melody[32:])),
            impulses=(
                _Impulse(0, 17, "up", 8, score=1),
                _Impulse(36, 40, "down", 3, score=90),
            ),
        ),
        ["bach_bourree", "bach_chaconne"],
    )
    assert plan.room == 19
    assert [(item.start, item.target) for item in plan.passages] == [(0, 17)]
    assert plan.tier1 == ()
    assert plan.room_after == 2


def test_perpetual_follows_passages_and_costs_one_bar() -> None:
    body = [64, 65, 66, 67, 69, 70, 71, 72] * 5 + [72] * 16
    plan = plan_scale_budget(
        _ctx(
            body,
            (_phrase(0, body[:40]), _phrase(40, body[40:])),
            bpm=120,
            ensemble="barrios",
            character="volatile",
            bands={bar: "f" for bar in range(7)},
            impulses=(_Impulse(0, 12, "up", 8, score=4),),
        ),
        ["preludio", "tremolo"],
    )
    assert plan.room == 16
    assert plan.passages and plan.passages[0].passage_eighths == 12
    assert plan.perpetual_bars == ()
    assert plan.room_after == 4

    held = [64] * 8 + [72] * 24
    waves = plan_scale_budget(
        _ctx(
            held,
            (_phrase(0, held[:8]), _phrase(8, held[8:])),
            bpm=120,
            ensemble="barrios",
            character="volatile",
            bands={bar: "f" for bar in range(4)},
        ),
        ["preludio", "tremolo"],
    )
    assert waves.passages == ()
    assert waves.perpetual_bars == (1,)
    assert waves.room_after == waves.room - 8


def test_ascending_entry_does_not_swell_downward_from_72() -> None:
    melody = [72, 70, 70, 71, 71, 70, 71, 71, 72] + [70] * 23
    raw = list(range(40, 72))
    score = _render(
        melody,
        (_phrase(0, melody),),
        (_Impulse(1, 8, "up", 6, score=5),),
        ensemble="classic",
        bpm=96,
        raw=raw,
    )
    notes = [event for start, event in _ordered(score.lead) if 2 <= start <= 16]
    assert notes
    velocities = [event.velocity for event in notes]
    # Study is Động năng, mf, so the window is 46–90. The lead before the
    # passage sits on the apex (72), and the first attack takes the soft breath.
    assert velocities[0] == 46
    assert velocities[-1] == 90
    assert velocities[-2] < velocities[-1]
    assert all(value < 90 for value in velocities[:-1])
    assert all(right >= left for left, right in zip(velocities, velocities[1:]))
    from app.sonify.humanize import humanize

    heard = humanize(score, offset_at=lambda *_args: 2)
    heard_notes = [event for start, event in _ordered(heard.lead) if 2 <= start <= 16]
    heard_velocities = [event.velocity for event in heard_notes]
    assert heard_velocities == velocities
    assert all(event.hairpin for event in heard_notes)
    target = next(event for start, event in _ordered(score.lead) if start == 16)
    assert target.midi == melody[8]
    bass_onsets = sorted(
        {
            int(round(note.beat * 2))
            for note in score.low
            if note.bar == 0 and note.midi is not None and not note.tie_stop
        }
    )
    assert bass_onsets == [0, 4]
    assert any(
        note.bar == 1 and abs(note.beat) < 1e-6 and note.midi is not None and not note.tie_stop
        for note in score.low
    )


def test_weak_target_does_not_attack_the_bass() -> None:
    melody = [64, 64, 65, 66, 67, 69, 70, 71, 72] + [72] * 23
    raw = list(range(40, 72))
    score = _render(
        melody,
        (_phrase(0, melody),),
        (_Impulse(2, 6, "up", 6, score=5),),
        ensemble="classic",
        bpm=96,
        raw=raw,
    )
    attacks = [
        note
        for note in score.low
        if note.midi is not None and note.bar == 0 and abs(note.beat - 3.0) < 1e-6 and not note.tie_stop
    ]
    assert attacks == []
    assert any(note.bar == 0 and abs(note.beat - 2.0) < 1e-6 and note.midi is not None for note in score.low)


def test_aborted_passage_leaves_the_pattern_and_the_next_candidate_spends_the_room() -> None:
    # Strong beats are 12 semitones apart. Eighths can travel 8; one split eighth
    # still leaves the line short, so this passage aborts.
    leap = [64, 64, 64, 64, 76, 76, 76, 76]
    line = [64, 65, 66, 60, 67, 69, 70, 71]
    melody = leap + line + [72] + [72] * 15
    raw = list(range(30, 62))
    score = _render(
        melody,
        (_phrase(0, melody),),
        (
            _Impulse(0, 8, "up", 12, score=9),
            _Impulse(9, 16, "up", 6, score=1),
        ),
        ensemble="classic",
        bpm=80,
        raw=raw,
    )
    notes = _ordered(score.lead)
    opening = next(event for start, event in notes if start == 0)
    assert opening.midi == 64 and opening.duration_beats >= 1.5
    second = [event.midi for start, event in notes if 18 <= start <= 32]
    assert 60 not in second
    assert second[-1] == 72


def _attacks(events, eighth: int, epb: int = 8) -> list[NoteEvent]:
    found = []
    for event in events:
        if event.midi is None:
            continue
        start = event.bar * epb + int(round(event.beat * 2))
        if start == eighth:
            found.append(event)
    return found


def _bass_onsets(events, bar: int) -> list[int]:
    by_eighth: dict[int, int] = {}
    for event in events:
        if event.midi is None or event.bar != bar or event.voice != 3:
            continue
        by_eighth.setdefault(int(round(event.beat * 2)), event.midi)
    return [by_eighth[key] for key in sorted(by_eighth)]


def _step_directions(pitches: list[int]) -> list[int]:
    directions = []
    for previous, midi in zip(pitches, pitches[1:]):
        if midi > previous:
            directions.append(1)
        elif midi < previous:
            directions.append(-1)
        else:
            directions.append(0)
    return directions


def test_fuga_passage_keeps_the_lagged_bass_motif() -> None:
    bar0 = [64, 66, 64, 65, 67, 65, 67, 69]
    bar1 = [69, 70, 70, 71, 71, 72, 72, 72]
    bar2 = [72, 72, 74, 74, 76, 76, 77, 77]
    bar3 = [79] * 8
    melody = bar0 + bar1 + bar2 + bar3
    raw = list(range(40, 40 + len(melody)))
    phrases = (_phrase(0, melody),)
    kwargs = {"ensemble": "bach", "bpm": 96, "character": "volatile", "raw": raw}
    plain = _render(melody, phrases, (), **kwargs)
    score = _render(melody, phrases, (_Impulse(16, 24, "up", 8, score=6),), **kwargs)
    assert any(note.bar == 2 and note.duration_beats <= 0.25 and note.midi is not None for note in score.lead)
    motif = _fuga_motif(_ctx(melody, phrases), 0)
    plain_bass = _bass_onsets(plain.low, 2)
    bass = _bass_onsets(score.low, 2)
    assert len(bass) == len(motif) == len(plain_bass)
    assert _step_directions(bass) == _step_directions(plain_bass)
    assert any(direction != 0 for direction in _step_directions(bass))


def test_subbar_elogio_keeps_the_bartok_slap() -> None:
    melody = [64, 65, 66, 67, 69, 70, 71, 72] + [72] * 24
    raw = list(range(48, 48 + len(melody)))
    phrases = (_phrase(0, melody),)
    kwargs = {"ensemble": "brouwer", "bpm": 108, "character": "volatile", "raw": raw}
    plain = _render(melody, phrases, (), **kwargs)
    short = _render(melody, phrases, (_Impulse(0, 6, "up", 6, score=6),), **kwargs)
    assert any(note.bar == 0 and note.duration_beats <= 0.25 and note.midi is not None for note in short.lead)
    for before, after in ((plain.low, short.low), (plain.support, short.support)):
        original = _attacks(before, 3)
        kept = _attacks(after, 3)
        assert original and kept
        assert [(event.midi, event.accent, event.staccato) for event in original] == [
            (event.midi, event.accent, event.staccato) for event in kept
        ]
        assert all(event.accent and event.staccato for event in kept)
    long = _render(melody, phrases, (_Impulse(0, 8, "up", 8, score=6),), **kwargs)
    assert any(note.bar == 0 and note.duration_beats <= 0.25 and note.midi is not None for note in long.lead)
    assert _attacks(long.low, 3) == []
    assert _attacks(long.support, 3) == []


def test_subbar_elogio_in_six_eight_keeps_one_slap_on_the_strong_eighth() -> None:
    bar = [64, 65, 66, 67, 69, 70]
    melody = bar * 4
    raw = list(range(48, 48 + len(melody)))
    phrases = (_phrase(0, melody),)
    kwargs = {
        "ensemble": "brouwer",
        "bpm": 108,
        "character": "volatile",
        "raw": raw,
        "meter": METER_68,
    }
    plain = _render(melody, phrases, (), **kwargs)
    short = _render(melody, phrases, (_Impulse(0, 4, "up", 6, score=6),), **kwargs)
    assert any(note.bar == 0 and note.duration_beats <= 0.25 and note.midi is not None for note in short.lead)
    plain_bass = [event for event in _attacks(plain.low, 3, epb=6) if event.voice == 3]
    scaled_bass = [event for event in _attacks(short.low, 3, epb=6) if event.voice == 3]
    assert len(plain_bass) == len(scaled_bass) == 1
    assert (scaled_bass[0].midi, scaled_bass[0].accent, scaled_bass[0].staccato) == (
        plain_bass[0].midi,
        plain_bass[0].accent,
        plain_bass[0].staccato,
    )
    assert scaled_bass[0].accent and scaled_bass[0].staccato
    plain_inner = _attacks(plain.support, 3, epb=6)
    scaled_inner = _attacks(short.support, 3, epb=6)
    assert plain_inner and [(event.midi, event.accent, event.staccato) for event in plain_inner] == [
        (event.midi, event.accent, event.staccato) for event in scaled_inner
    ]


def test_retreat_rises_before_it_falls() -> None:
    melody = [64, 65, 66, 67, 69, 70, 71, 72] + [72] * 24
    raw = list(range(48, 80))
    score = _render(
        melody,
        (_phrase(0, melody),),
        (_Impulse(0, 8, "up", 8, score=5, retreat_spans=((2, 3),)),),
        ensemble="classic",
        bpm=96,
        raw=raw,
    )
    notes = _ordered(score.lead)
    downbeat = next(event.midi for grid, event in notes if grid == 0)
    before = [event.midi for grid, event in notes if 0 < grid < 4]
    during = [event.midi for grid, event in notes if 4 <= grid < 8]
    after = [event.midi for grid, event in notes if 8 <= grid < 16]
    assert before and during and after
    assert before[-1] > downbeat
    assert min(during) < before[-1]
    assert after[0] > min(during)
    assert next(event.midi for grid, event in notes if grid == 16) == 72


def test_playable_scale_passage_in_every_ensemble_and_key() -> None:
    melody = _climb()
    raw = list(range(30, 62))
    impulse = (_Impulse(0, 8, "up", 8, score=6),)
    profiles = {
        "bach": "bach",
        "classic": "study",
        "villa": "villa_pattern",
        "barrios": "barrios_preludio",
        "brouwer": "brouwer",
    }
    tempos = {"bach": 96, "classic": 88, "villa": 100, "barrios": 104, "brouwer": 108}
    for ensemble, profile in profiles.items():
        for key in (C_KEY, D_KEY, EB_KEY, A_KEY, BB_KEY):
            score = _render(
                melody,
                (_phrase(0, melody),),
                impulse,
                ensemble=ensemble,
                bpm=tempos[ensemble],
                key=key,
                raw=raw,
            )
            sixteenths = [
                note for note in score.lead if note.duration_beats <= 0.25 and note.midi is not None
            ]
            assert sixteenths, (ensemble, key.name)
            assert_playable(score, key, profile)


def test_hairpin_windows_openings_and_the_long_curve() -> None:
    """Section 2.6.A–C, including the cases a full render does not isolate."""
    assert _pattern_window("elogio_pizz", "p") == (40, 84)
    assert _pattern_window("elogio_pizz", "f") == (48, 96)
    assert _pattern_window("study", "p") == (40, 82)
    assert _pattern_window("elegiaque", "p") == (44, 74)

    elogio = hairpin_velocities(
        5,
        direction="up",
        pattern="elogio_pizz",
        band="p",
        prev=64,
        on_strong=False,
        length=4,
        epb=8,
        pillar=False,
    )
    assert elogio[0] == 40
    assert elogio[-1] == 84
    assert elogio[-2] < 84
    assert max(elogio) == 84

    hat_down = hairpin_velocities(
        5,
        direction="down",
        pattern="elegiaque",
        band="mf",
        prev=60,
        on_strong=False,
        length=4,
        epb=8,
        pillar=False,
    )
    assert hat_down[0] == 72
    assert hat_down[0] != 82
    assert hat_down[-1] == 52
    assert all(value > 52 for value in hat_down[:-1])

    # Baroque dances stay off the sforzando even on a strong beat.
    bourree = hairpin_velocities(
        4,
        direction="down",
        pattern="bach_bourree",
        band="mf",
        prev=60,
        on_strong=True,
        length=4,
        epb=8,
        pillar=False,
    )
    assert bourree[0] == 72
    assert bourree[0] != 84

    for pattern, loud in (("study", 90), ("bach_chaconne", 88)):
        opened = hairpin_velocities(
            4,
            direction="down",
            pattern=pattern,
            band="mf",
            prev=60,
            on_strong=True,
            length=4,
            epb=8,
            pillar=True,
        )
        assert opened[0] == loud
        assert opened[-1] == max(_pattern_window(pattern, "mf")[0], _BASS + 2)
        assert opened[-2] == _pattern_window(pattern, "mf")[0]

    long_up = hairpin_velocities(
        9,
        direction="up",
        pattern="study",
        band="mf",
        prev=72,
        on_strong=True,
        length=16,
        epb=8,
        pillar=False,
    )
    linear_mid = int(round(46 + (90 - 46) * 0.5))
    assert long_up[0] == 46
    assert long_up[-1] == 90
    assert long_up[4] < linear_mid
    assert all(right >= left for left, right in zip(long_up, long_up[1:]))

    plain = hairpin_velocities(
        8,
        direction="up",
        pattern="study",
        band="mf",
        prev=72,
        on_strong=True,
        length=8,
        epb=8,
        pillar=False,
        retreats=[False] * 8,
    )
    retreated = hairpin_velocities(
        8,
        direction="up",
        pattern="study",
        band="mf",
        prev=72,
        on_strong=True,
        length=8,
        epb=8,
        pillar=False,
        retreats=[False, False, True, False, False, False, False, True],
    )
    assert retreated[2] == plain[2] - 3
    assert retreated[-1] == plain[-1] == 90
    assert all(retreated[index] == plain[index] for index in range(8) if index != 2)
    assert all(right >= left for left, right in zip(plain, plain[1:]))


def test_tier1_eighth_with_one_attack_does_not_divide() -> None:
    melody = [64, 64, 64, 67, 65, 65, 65, 65] + [65] * 8
    passage = ScalePassage(
        start=3,
        target=4,
        direction="down",
        net_span=2,
        score=1.0,
        retreat_spans=(),
        sub_bar=True,
        passage_eighths=1,
        replaced_base_intrinsic_eighths=0,
        tier="tier1",
    )
    slots = [_Slot(3, 0, 2, False, False), _Slot(4, 0, 2, True, False)]
    ctx = _ctx(melody, (_phrase(0, melody),), bpm=80)
    velocities = _curve(ctx, ["study"], passage, slots, 60)
    assert velocities == [72, max(46, _BASS + 2)]

    rising = ScalePassage(
        start=3,
        target=4,
        direction="up",
        net_span=2,
        score=1.0,
        retreat_spans=(),
        sub_bar=True,
        passage_eighths=1,
        replaced_base_intrinsic_eighths=0,
        tier="tier1",
    )
    up = _curve(ctx, ["study"], rising, slots, 60)
    # n = 1 still has a divisor of 1 on an upward N-ramp: open, then loud.
    assert up == [46, 90]


def test_downward_pillar_is_not_under_the_bass_and_villa_does_not_cap_to_44() -> None:
    # 6/8 keeps framed Villa on villa_pattern, so the bass cap in _shape_dynamics runs.
    melody = [72, 71, 70, 69, 67, 66] + [64] * 24
    score = _render(
        melody,
        (_phrase(0, melody),),
        (_Impulse(0, 6, "down", 8, score=6),),
        ensemble="villa",
        bpm=96,
        character="rally",
        raw=list(range(80, 50, -1)),
        sections=(FormSection(0, 1, "intro", 0), FormSection(1, 5, "phrase", 0)),
        meter=METER_68,
    )
    notes = [event for start, event in _ordered(score.lead, epb=6) if start <= 12]
    assert notes
    velocities = [event.velocity for event in notes if event.velocity is not None]
    assert velocities[0] == 90
    assert velocities[-1] == _BASS + 2
    assert velocities[-2] == _pattern_window("villa_pattern", "mf")[0]
    target = next(event for start, event in _ordered(score.lead, epb=6) if start == 12)
    assert target.midi == melody[6]
    assert target.velocity == _BASS + 2
    ringing = [
        note
        for note in score.low
        if note.midi is not None
        and note.velocity is not None
        and note.bar == 1
        and not note.tie_stop
    ]
    assert ringing
    assert all(note.velocity > 44 for note in ringing)
    assert all(note.velocity < target.velocity for note in ringing)


def test_modal_figure_ramps_the_hat_window_and_a_bar_opening_is_not_punched() -> None:
    from app.sonify.guitar_brouwer import _modal_figure, _sarabande_points

    flat = [64, 64, 64, 64, 65, 65, 66, 66]
    phrase = _phrase(0, flat)
    ctx = _ctx(flat, (phrase,), bpm=72, ensemble="brouwer", character="selloff")
    _accent, figure = _sarabande_points(ctx)
    rising = _modal_figure(ctx, 0, figure, ctx.bass_low, phrase)
    rising_vel = [event.velocity for event in rising if event.midi is not None]
    assert rising_vel[0] == 52
    assert rising_vel[-1] == 82
    assert rising_vel[-2] < 82
    assert all(right >= left for left, right in zip(rising_vel, rising_vel[1:]))

    falling_line = [64, 65, 64, 64, 66, 65, 64, 64]
    falling_phrase = _phrase(0, falling_line)
    falling_ctx = _ctx(falling_line, (falling_phrase,), bpm=72, ensemble="brouwer", character="selloff")
    _accent, figure = _sarabande_points(falling_ctx)
    falling = _modal_figure(falling_ctx, 0, figure, falling_ctx.bass_low, falling_phrase)
    falling_vel = [event.velocity for event in falling if event.midi is not None]
    assert falling_vel[0] == 80
    assert falling_vel[-1] == _BASS + 2
    assert all(right <= left for left, right in zip(falling_vel, falling_vel[1:]))

    leap = [60, 72, 72, 72, 70, 68, 66, 64]
    score = _render(
        leap,
        (_phrase(0, leap),),
        (),
        ensemble="brouwer",
        bpm=108,
        character="selloff",
    )
    lead = _ordered(score.lead)
    accent = [event for start, event in lead if start == 4]
    assert accent
    assert all(not event.accent for event in accent)
    velocities = [event.velocity for _start, event in lead if event.velocity is not None]
    assert velocities[0] == 72
    assert velocities[-1] == _BASS + 2
    assert all(right <= left for left, right in zip(velocities, velocities[1:]))
    assert any(event.hairpin for _start, event in lead)
    from app.sonify.humanize import humanize

    # Sor's snap ceiling is 70. The same reprinted hat has to stay 72.
    heard = humanize(replace(score, ensemble="classic"), offset_at=lambda *_args: 2)
    heard_lead = [event.velocity for _start, event in _ordered(heard.lead) if event.velocity is not None]
    assert heard_lead[0] == 72
    assert heard_lead == velocities
    bass_accent = [
        note
        for note in score.low
        if note.midi is not None and note.bar == 0 and abs(note.beat - 1.0) < 1e-6
    ]
    assert bass_accent and all(note.accent for note in bass_accent)


def test_framed_swarm_eighths_skip_the_second_band_pass(monkeypatch) -> None:
    from app.sonify import guitar_patterns as patterns
    from app.sonify import guitar_scale_passages as passages
    from app.sonify.guitar_brouwer import brouwer_group2_window

    melody = [64, 64, 64, 64, 66, 67, 69, 71] + [71] * 8
    seen: dict[str, object] = {}
    real_clear = passages.clear_scale_slurs
    real_shape = patterns._shape_dynamics

    def spy_clear(events, eighths, epb):
        seen["slur"] = set(eighths)
        return real_clear(events, eighths, epb)

    def spy_shape(ctx, lead, support, low, relaxed, patterns_arg=None, scale_eighths=None):
        protected = set(scale_eighths or ())
        seen["shape"] = protected
        before = [
            (event.bar, round(event.beat, 3), event.velocity)
            for event in lead
            if event.midi is not None and event.velocity is not None and event.velocity < 72
        ]
        shaped = real_shape(ctx, lead, support, low, relaxed, patterns_arg, scale_eighths)
        after = [
            (event.bar, round(event.beat, 3), event.velocity)
            for event in shaped[0]
            if event.midi is not None and event.velocity is not None and event.velocity < 72
        ]
        # Compare the protected attacks only. An unprotected note under 72 moves.
        def key(event):
            eighth = event.bar * ctx.epb + int(math.floor(event.beat * 2 + 1e-9))
            return eighth

        kept = {
            (key(event), event.velocity)
            for event in lead
            if event.midi is not None and event.velocity is not None and key(event) in protected
        }
        shaped_kept = {
            (key(event), event.velocity)
            for event in shaped[0]
            if event.midi is not None and event.velocity is not None and key(event) in protected
        }
        seen["kept"] = kept == shaped_kept
        # The band step main removed. A bare pass would still kink these notes.
        old_band_p = -12
        seen["kinked_if_bare"] = any(
            max(44, min(78, velocity + old_band_p)) != velocity
            for event in lead
            if event.midi is not None
            and event.velocity is not None
            and key(event) in protected
            and (velocity := event.velocity) < 72
        )
        seen["below"] = before
        seen["after_below"] = after
        return shaped

    monkeypatch.setattr(passages, "clear_scale_slurs", spy_clear)
    monkeypatch.setattr(patterns, "_shape_dynamics", spy_shape)
    score = _render(
        melody,
        (_phrase(0, melody),),
        (),
        ensemble="brouwer",
        bpm=72,
        character="selloff",
        bands={bar: "p" for bar in range(2)},
        sections=(FormSection(0, 1, "intro", 0), FormSection(1, 2, "outro", 0)),
    )
    window = brouwer_group2_window(_ctx(melody, (_phrase(0, melody),), bpm=72), 0)
    assert window is not None
    swarm = set(range(window[0], window[1] + 1))
    assert swarm <= set(seen["shape"])
    assert swarm <= set(seen["slur"])
    plan = plan_scale_budget(
        _ctx(melody, (_phrase(0, melody),), bpm=72, ensemble="brouwer", character="selloff"),
        ["sarabande", "sarabande"],
    )
    assert swarm.isdisjoint(plan.scale_eighths)
    assert seen["kept"] is True
    assert seen["kinked_if_bare"] is True
    assert score.lead


def _tied_pairs(events: list[NoteEvent], epb: int) -> None:
    """Every `tie_stop` continues a `tie_start` on the same pitch."""
    open_until = None
    open_midi = None
    for event in events:
        if event.midi is None:
            continue
        begin = _start16(event, epb)
        if event.tie_stop:
            assert open_until == begin and open_midi == event.midi
        if event.tie_start:
            open_until = begin + _dur16(event)
            open_midi = event.midi
        else:
            open_until = None
            open_midi = None


def test_flat_price_steps_to_a_neighbor_instead_of_repeating() -> None:
    melody = [64] * 8
    ctx = _ctx(melody, (_phrase(0, melody),), ensemble="sor")
    assert _monotone(64, 64, 3, ctx, "up", False) == [64, 64, 64]
    rising = _monotone(64, 64, 3, ctx, "up", False, ornament=True)
    falling = _monotone(64, 64, 3, ctx, "down", False, ornament=True)
    assert rising is not None and falling is not None
    assert rising[0] == rising[-1] == 64
    assert falling[0] == falling[-1] == 64
    assert rising[1] > 64 and falling[1] < 64
    assert 1 <= abs(rising[1] - 64) <= 2
    assert 1 <= abs(falling[1] - 64) <= 2
    moving = _monotone(64, 67, 4, ctx, "up", False)
    assert moving == [64, 65, 67, 67]
    boxed = replace(ctx, treble_floor=64, treble_top=64, ceiling=64)
    assert _monotone(64, 64, 3, boxed, "up", False) == [64, 64, 64]
    raw = [10, 10, 10, 10, 14, 16, 18, 20]
    held = [64, 64, 64, 64, 67, 69, 71, 72]
    flat_ctx = _ctx(held, (_phrase(0, held),), ensemble="sor", bpm=96, raw=raw)
    passage = ScalePassage(
        start=0,
        target=4,
        direction="up",
        net_span=4,
        score=1.0,
        retreat_spans=(),
        sub_bar=True,
        passage_eighths=4,
        replaced_base_intrinsic_eighths=0,
    )
    slots = _slots(flat_ctx, ["study"], passage)
    assigned = _assign(flat_ctx, passage, slots)
    assert assigned is not None
    offbeat = next(index for index, slot in enumerate(slots) if slot.eighth == 0 and slot.sub == 1)
    assert assigned[offbeat] != 64
    assert 1 <= abs(assigned[offbeat] - 64) <= 2
    landing = next(index for index, slot in enumerate(slots) if slot.eighth == 1 and slot.sub == 0)
    assert assigned[landing] == 64


def test_scale_need_and_the_composer_endings() -> None:
    """Section 2. E–C needs five in-set steps. Bach and Sor do not share a cadence."""
    melody = [60] * 8
    low, high = _compass(_ctx(melody, (_phrase(0, melody),), ensemble="bach"), None)
    bach = _ctx(melody, (_phrase(0, melody),), ensemble="bach")
    sor = _ctx(melody, (_phrase(0, melody),), ensemble="sor")
    barrios = _ctx(melody, (_phrase(0, melody),), ensemble="barrios")
    villa = _ctx(melody, (_phrase(0, melody),), ensemble="villa")
    brouwer = _ctx(melody, (_phrase(0, melody),), ensemble="brouwer")
    assert _scale_need(bach, 64, 72, "up", False, low, high) == 5
    assert math.ceil(abs(72 - 64) / 2) == 4
    for house in (bach, sor, barrios, villa, brouwer):
        assert _scale_need(house, 64, 72, "up", False, low, high) == 5

    # Two spare steps into C. Bach falls to B. Sor steps up to D.
    bach_line = _monotone(64, 72, 8, bach, "up", True)
    sor_line = _monotone(64, 72, 8, sor, "up", False)
    assert bach_line is not None and sor_line is not None
    assert bach_line[-3:] == [72, 71, 72]
    assert sor_line[-3:] == [72, 74, 72]
    assert bach_line[-2:] != sor_line[-2:]

    # The same split when the leading tone is outside the major set (D# before E).
    bach_e = _monotone(60, 64, 5, bach, "up", False)
    sor_e = _monotone(60, 64, 5, sor, "up", False)
    assert bach_e == [60, 62, 64, 63, 64]
    assert sor_e == [60, 62, 64, 65, 64]

    # One leftover step is not a turn. Sor repeats. Bach may take the leading tone.
    assert _monotone(60, 62, 3, sor, "up", False) == [60, 62, 62]
    assert _monotone(60, 62, 3, bach, "up", False) == [60, 61, 62]

    # Spare steps after the walk hold the closing anchor. The opening note is not repeated.
    held = _monotone(60, 62, 8, sor, "up", False)
    assert held is not None and held[0] == 60 and held[-1] == 62
    assert held.count(60) == 1 and held.count(62) > 1
    assert held[-3:] == [62, 64, 62]
    # A shortened walk does not sit on the anchor before the last note.
    brouwer_fast = _fast_line(brouwer, 60, 65, 7, "up", False, low, high)
    assert brouwer_fast is not None and brouwer_fast[-1] == 65
    assert 65 not in brouwer_fast[:-1]

    # Barrios keeps the chromatic approach on the last weak note, aimed from a diatonic degree.
    barrios_line = _monotone(60, 64, 5, barrios, "up", False)
    assert barrios_line == [60, 62, 64, 63, 64]
    assert barrios_line[-3] % 12 in {0, 2, 4, 5, 7, 9, 11}
    descending = _monotone(72, 67, 6, barrios, "down", False)
    assert descending is not None and descending[-2] == 68 and descending[-1] == 67

    # Villa prefers Bb under C when that whole step still reaches, and does not open a string here.
    villa_down = _monotone(72, 67, 6, villa, "down", False)
    assert villa_down is not None
    assert 70 in villa_down
    assert not any(pitch in {40, 45, 50, 55, 59, 64} for pitch in villa_down)

    long = ScalePassage(0, 8, "up", 8, 1.0, (), False, 8, 0)
    short = ScalePassage(0, 4, "up", 4, 1.0, (), True, 4, 0)
    assert _compass(bach, long) == (52, 83)
    assert _compass(sor, long) == (52, 83)
    assert _compass(barrios, long) == (52, 83)
    assert _compass(villa, long) == (40, 83)
    assert _compass(brouwer, long) == (40, 83)
    assert _compass(bach, short) == (57, 83)


def test_groups_ok_uses_sounding_pitches() -> None:
    """A written pitch below the nut can still be an open string after the key shift."""
    slots = [_Slot(0, sub, 1, False, False) for sub in range(4)]
    # D major: written 38, 43 sound as the open E and A strings.
    assert _groups_ok(slots, [38, 43, 38, 43], 2)


def test_scale_positions_use_sounding_pitches() -> None:
    """The score-level hand check adds the key, the same way the group check does.

    A whole step stays inside the four-semitone gate. Written 38 has no string
    until D major makes it the open E.
    """
    sixteenths = [
        NoteEvent(bar=0, beat=0.0, midi=38, duration_beats=0.25, voice=1),
        NoteEvent(bar=0, beat=0.25, midi=40, duration_beats=0.25, voice=1),
    ]
    _assert_scale_positions(sixteenths, 8, D_KEY.semitones)
    try:
        _assert_scale_positions(sixteenths, 8, 0)
    except Unplayable:
        return
    raise AssertionError("written 38 is not an open string until the key is added")


def test_stamp_arrival_keeps_the_tie_and_carries_the_landing_velocity() -> None:
    epb = 8
    # Five eighths is 10 sixteenths, so the sustain is already two tied events.
    lead = _spell16(2, 10, 67, epb, 1, 64)
    assert any(event.tie_start for event in lead) and any(event.tie_stop for event in lead)
    stamped = _stamp_arrival(lead, 2, 67, 82, epb)
    _tied_pairs(stamped, epb)
    covered = [
        event
        for event in stamped
        if event.midi is not None and _start16(event, epb) >= 4
    ]
    assert covered
    assert all(event.velocity == 82 and event.midi == 67 for event in covered)
    prefix = [
        event
        for event in stamped
        if event.midi is not None and _start16(event, epb) < 4
    ]
    assert prefix and all(event.velocity == 64 for event in prefix)

    cut = _splice(lead, 0, 4, [], epb)
    landed = _stamp_arrival(cut, 2, 67, 90, epb)
    _tied_pairs(landed, epb)
    tail = [
        event
        for event in landed
        if event.midi is not None and _start16(event, epb) >= 4
    ]
    assert tail and all(event.velocity == 90 and event.midi == 67 for event in tail)


def _pad(parts: list[tuple[str, int]], bars: int) -> list[tuple[str, int]]:
    """Extend a layout with study bars so a kept span is not rejected by the 30% room."""
    have = sum(count for _pattern, count in parts)
    if bars > have:
        parts = [*parts, ("study", bars - have)]
    return parts


def _plan(parts: list[tuple[str, int]], impulse: _Impulse, **kwargs):
    epb = kwargs.get("epb", 8)
    total = sum(count for _pattern, count in parts) * epb
    melody = kwargs.pop("melody", [64] * total)
    phrases: list[Phrase] = []
    patterns: list[str] = []
    cursor = 0
    for pattern, count in parts:
        length = count * epb
        phrases.append(_phrase(cursor, melody[cursor : cursor + length]))
        patterns.append(pattern)
        cursor += length
    kinds = kwargs.pop("kinds", None)
    ctx = _ctx(melody, tuple(phrases), impulses=(impulse,), **kwargs)
    if kinds is not None:
        ctx = replace(ctx, kind_at=kinds)
    return plan_scale_budget(ctx, patterns)


def _spans(parts, impulse, **kwargs) -> list[tuple[int, int]]:
    plan = _plan(parts, impulse, **kwargs)
    return [(item.start, item.target) for item in plan.passages]


def test_host_regions_clip_to_the_four_numeric_spans() -> None:
    """epb = 8. The passage is the clipped span, and the loop runs after every shrink."""
    up = "up"
    # Etude opens at eighth 16. One eighth of approach is dropped; the later bars stay.
    opened = _plan(_pad([("study", 2), ("etude1", 3)], 7), _Impulse(15, 40, up, 8, score=7.5, retreat_spans=((0, 50),)))
    assert [(item.start, item.target) for item in opened.passages] == [(24, 40)]
    assert 16 not in range(opened.passages[0].start, opened.passages[0].target)
    assert opened.passages[0].score == 7.5
    assert opened.passages[0].retreat_spans == ((24, 40),)
    assert opened.passages[0].passage_eighths == 16
    assert opened.passages[0].replaced_base_intrinsic_eighths == 0
    # A later host region opens at 32. The loop excludes that bar too.
    assert _spans(
        _pad([("study", 2), ("etude1", 2), ("thumb_cantabile", 2)], 8),
        _Impulse(15, 40, up, 8, score=7.5),
    ) == [(24, 32)]
    # Tremolo sits against the etude opening. Keeping the long front, then clipping, leaves the Sor bar.
    assert _spans(
        _pad([("study", 1), ("tremolo", 1), ("etude1", 2)], 4),
        _Impulse(0, 32, up, 8),
    ) == [(0, 8)]
    # The opening is the trailing edge. Shrink, then the loop clips the tremolo.
    assert _spans(
        _pad([("study", 1), ("tremolo", 1), ("etude1", 1)], 4),
        _Impulse(0, 24, up, 8),
    ) == [(0, 8)]
    # The opening is the leading edge. Shrink, then the loop clips the tremolo.
    assert _spans(
        _pad([("etude1", 1), ("tremolo", 1), ("study", 2)], 7),
        _Impulse(0, 32, up, 8),
    ) == [(16, 32)]


def test_host_grid_yields_whole_bars_and_group3_keeps_a_short_remainder() -> None:
    up = "up"
    # The next whole bar of a region that already has one bar is a scale.
    assert _spans([("etude1", 4)], _Impulse(8, 16, up, 8)) == [(8, 16)]
    # A fragment shorter than one bar on the host itself yields nothing.
    assert _spans([("etude1", 4)], _Impulse(18, 22, up, 4)) == []
    # A target on the barline does not swallow the etude bar that begins there.
    assert _spans(_pad([("study", 2), ("etude1", 2)], 7), _Impulse(0, 16, up, 8)) == [(0, 16)]
    assert _spans([("etude1", 4)], _Impulse(4, 16, up, 6)) == [(8, 16)]
    # A few eighths of etude at the edge leave the group-3 remainder.
    assert _spans(_pad([("study", 2), ("etude1", 2)], 6), _Impulse(14, 20, up, 6)) == [(14, 16)]
    # Sor covers the etude opening and the bar after it. The front stays; target is the opening.
    assert _spans(_pad([("study", 2), ("etude1", 2)], 6), _Impulse(8, 32, up, 8)) == [(8, 16)]
    # A one-bar tremolo in the middle is that region's opening. The gate is open,
    # so the front stays and the back is not part of this passage. Pedal inside
    # still drops the passage. An edge pedal is clipped.
    assert _spans(_pad([("study", 1), ("tremolo", 1), ("study", 1)], 6), _Impulse(0, 24, up, 8)) == [(0, 8)]
    assert _spans(_pad([("study", 1), ("tremolo", 1), ("study", 1)], 6), _Impulse(0, 24, up, 5)) == []
    assert _spans(_pad([("study", 3)], 6), _Impulse(0, 24, up, 8), kinds={1: "intro"}) == []
    assert _spans(_pad([("study", 3)], 8), _Impulse(2, 16, up, 6), kinds={0: "warmup"}) == [(8, 16)]
    assert _spans(_pad([("study", 3)], 9), _Impulse(0, 18, up, 6), kinds={2: "cooldown"}) == [(0, 16)]
    # Both sides of a middle opening are shorter than two eighths.
    assert _spans(_pad([("study", 1), ("etude1", 1)], 4), _Impulse(7, 17, up, 6)) == []
    # A group-3 run shorter than a bar still overlays.
    assert _spans([("study", 4)], _Impulse(1, 4, up, 3)) == [(1, 4)]


def test_group2_opening_rejects_the_whole_passage_even_at_an_edge() -> None:
    """Bach and Brouwer are not edge-shrunk. A host opening may still discard a group-2 back."""
    up = "up"
    # Middle: a host-style split would have kept [8, 16). The whole passage is dropped.
    assert _spans(_pad([("study", 2), ("bach_gigue", 2)], 6), _Impulse(8, 40, up, 8)) == []
    # Leading edge: shrinking start to 8 would have kept [8, 24).
    assert _spans(_pad([("bach_gigue", 2), ("study", 2)], 8), _Impulse(0, 24, up, 8)) == []
    # Trailing edge: shrinking target to 16 would have kept [8, 16).
    assert _spans(_pad([("study", 2), ("bach_sarabande", 2)], 4), _Impulse(8, 24, up, 8)) == []
    assert _spans(_pad([("study", 2), ("sarabande", 2)], 4), _Impulse(8, 24, up, 6), ensemble="brouwer") == []
    # The host opening discards the group-2 back. The front no longer touches group 2, so it stays.
    assert _spans(
        _pad([("study", 2), ("etude1", 1), ("bach_gigue", 2)], 8),
        _Impulse(0, 32, up, 8),
    ) == [(0, 16)]
    # Still touching group 2 after the clip, but the original run is not a major bridge.
    assert _spans(_pad([("bach_gigue", 2)], 6), _Impulse(8, 20, up, 5)) == []
    assert _spans(_pad([("bach_gigue", 2)], 4), _Impulse(8, 14, up, 8)) == []
    # A major bridge that does not cover the opening is kept.
    kept = _plan(_pad([("bach_gigue", 3)], 4), _Impulse(8, 16, up, 6, score=4.0))
    assert [(item.start, item.target) for item in kept.passages] == [(8, 16)]
    assert kept.passages[0].score == 4.0


def test_barline_target_does_not_yield_the_next_bar_and_lands_on_the_melody() -> None:
    plan = _plan(
        _pad([("study", 2), ("etude1", 2)], 7),
        _Impulse(0, 16, "up", 8, score=5),
        ensemble="classic",
    )
    assert [(item.start, item.target) for item in plan.passages] == [(0, 16)]
    melody = _climb()
    passage = ScalePassage(0, 16, "up", 8, 5.0, (), False, 16, 0, "passage")
    ctx = _ctx(melody, (_phrase(0, melody),), ensemble="classic", bpm=96)
    lead = _eighth_event(0, len(melody), melody[0], 8, 1, 72)
    realized = realize_scale_passage(ctx, passage, ["study"], lead, [], [])
    assert realized is not None
    heard, _support, _low = realized
    arrival = [event for event in heard if event.midi is not None and _start16(event, 8) == passage.target * 2]
    assert arrival
    assert all(event.midi == ctx.melody[passage.target] for event in arrival)


def _host_realized(pattern: str, start: int, target: int, **kwargs):
    ensemble = kwargs.get("ensemble", "villa")
    bpm = kwargs.get("bpm", 96)
    bass_low = kwargs.get("bass_low", 40)
    bass_high = kwargs.get("bass_high", 53)
    sections = kwargs.get("sections", ())
    melody = kwargs.get("melody", _climb() + [72] * 16)
    chord = kwargs.get("chord")
    ctx = replace(
        _ctx(melody, (_phrase(0, melody),), bpm=bpm, ensemble=ensemble, sections=sections),
        bass_low=bass_low,
        bass_high=bass_high,
        semitones=kwargs.get("semitones", 0),
    )
    if chord is not None:
        ctx = replace(ctx, chord_at={bar: chord for bar in range(ctx.bars)})
    passage = ScalePassage(
        start, target, "up", 8, 5.0, (), (target - start) < 8, target - start, 0, "passage"
    )
    support = list(_eighth_event(start, 2, 60, 8, 2, 56))
    support.append(NoteEvent(bar=start // 8, beat=0.5, midi=62, duration_beats=1 / 6, voice=2, velocity=50))
    low = list(_eighth_event(16, 16, 41, 8, 3, 57))
    lead = _eighth_event(0, len(melody), melody[0], 8, 1, 72)
    return ctx, passage, realize_scale_passage(ctx, passage, [pattern], lead, support, low)


def _bass_attacks(events, start: int, target: int) -> list[tuple[int, int, float, int]]:
    found = []
    for event in events:
        if event.midi is None or event.tie_stop:
            continue
        eighth = _start16(event, 8) // 2
        if start <= eighth < target:
            found.append((eighth, event.midi, event.duration_beats, event.velocity))
    found.sort()
    return found


def test_yielded_host_bars_use_the_pattern_bass_and_an_empty_inner_voice() -> None:
    framed = (FormSection(0, 6, "phrase", 0),)
    _ctx_etude, _passage, etude = _host_realized("etude1", 8, 16)
    assert etude is not None
    _lead, support, low = etude
    assert _bass_attacks(low, 8, 16) == [(8, 48, 4.0, _BASS)]
    assert support == [] or all(event.midi is None or _start16(event, 8) // 2 >= 16 for event in support)
    assert not any(event.midi is not None and 8 <= _start16(event, 8) // 2 < 16 for event in support)

    _ctx11, _passage11, etude11 = _host_realized("etude11", 8, 16)
    assert etude11 is not None
    _lead11, support11, low11 = etude11
    assert _bass_attacks(low11, 8, 16) == [
        (8, 48, 1.0, _BASS),
        (10, 48, 1.0, _BASS),
        (12, 48, 1.0, _BASS),
        (14, 48, 1.0, _BASS),
    ]
    assert not any(event.midi is not None and 8 <= _start16(event, 8) // 2 < 16 for event in support11)

    for ensemble in ("villa", "barrios"):
        _ctx_thumb, _passage_thumb, thumb = _host_realized("thumb_cantabile", 8, 16, ensemble=ensemble)
        assert thumb is not None, ensemble
        lead, support_thumb, low_thumb = thumb
        attacks = _bass_attacks(low_thumb, 8, 16)
        assert len(attacks) == 1
        eighth, midi, duration, velocity = attacks[0]
        assert (eighth, duration, velocity) == (8, 4.0, _BASS)
        assert 48 <= midi <= 64
        assert all(event.voice == 1 for event in lead if event.midi is not None and 16 <= _start16(event, 8) < 32)
        assert not any(event.midi is not None and 8 <= _start16(event, 8) // 2 < 16 for event in support_thumb)

    # 40..47 can be played under this eighth-note line, and it is still not a thumb root.
    slow = _line_pitches("thumb_cantabile", bpm=80, ensemble="villa")
    assert slow is not None
    assert all(_playable([43, pitch]) for pitch in slow)
    accepted = _host_realized("thumb_cantabile", 8, 16, bpm=80, bass_high=53)[2]
    assert accepted is not None
    assert all(48 <= midi <= 64 for _eighth, midi, _duration, _velocity in _bass_attacks(accepted[2], 8, 16))

    # The ordinary bass ceiling sounds at 53. B and written A minor only have a
    # root from sounding 54 up, so the thumb window has to search that high.
    b_major = Chord("B", "B", KIND_MAJOR, "", (71, 75, 78))
    b_ctx, _b_passage, b_thumb = _host_realized(
        "thumb_cantabile", 8, 16, bpm=80, bass_high=53, chord=b_major
    )
    assert b_thumb is not None
    assert [midi + b_ctx.semitones for _eighth, midi, _duration, _velocity in _bass_attacks(b_thumb[2], 8, 16)] == [59]
    d_register = register_for(D_KEY)
    am_ctx, _am_passage, am_thumb = _host_realized(
        "thumb_cantabile",
        8,
        16,
        bpm=80,
        chord=AM,
        semitones=D_KEY.semitones,
        bass_low=d_register.guitar_floor,
        bass_high=d_register.guitar_bass_top,
    )
    assert am_thumb is not None
    assert [midi + am_ctx.semitones for _eighth, midi, _duration, _velocity in _bass_attacks(am_thumb[2], 8, 16)] == [59]

    for pattern in ("etude1", "etude11"):
        assert _host_realized(pattern, 8, 16, bass_low=44, bass_high=46)[2] is None
        assert _host_realized(pattern, 8, 16)[2] is not None
    assert _host_realized("preludio", 16, 32, ensemble="barrios", sections=framed, bass_low=44, bass_high=46)[2] is None

    both = _host_realized("preludio", 16, 32, ensemble="barrios", sections=framed)[2]
    assert both is not None
    _lead_both, support_both, low_both = both
    chain = [
        event
        for event in low_both
        if event.midi is not None and 32 <= _start16(event, 8) < 64
    ]
    assert [(event.midi, event.duration_beats, event.velocity, event.tie_start, event.tie_stop) for event in chain] == [
        (48, 4.0, _BASS, True, False),
        (48, 4.0, _BASS, False, True),
    ]
    assert sum(event.duration_beats for event in chain) == 8.0
    assert not any(event.midi is not None and 16 <= _start16(event, 8) // 2 < 32 for event in support_both)

    one = _host_realized("preludio", 16, 24, ensemble="barrios", sections=framed)[2]
    assert one is not None
    _lead_one, _support_one, low_one = one
    assert _bass_attacks(low_one, 16, 24) == [(16, 48, 2.0, _BASS), (20, 48, 2.0, _BASS)]
    outside = [
        event
        for event in low_one
        if event.midi is not None and _start16(event, 8) == 48
    ]
    assert outside
    assert all(event.midi == 41 and event.velocity == 57 and not event.tie_stop for event in outside)

    # Below 88 the eighth-note host bar still leaves the inner voice empty.
    slow_host = _host_realized("etude1", 8, 16, bpm=80)[2]
    assert slow_host is not None
    assert not any(event.midi is not None and 8 <= _start16(event, 8) // 2 < 16 for event in slow_host[1])


def _line_pitches(pattern: str, *, bpm: int, ensemble: str) -> list[int] | None:
    from app.sonify.guitar_scale_passages import _line

    melody = _climb() + [72] * 16
    ctx = _ctx(melody, (_phrase(0, melody),), bpm=bpm, ensemble=ensemble)
    passage = ScalePassage(8, 16, "up", 8, 5.0, (), False, 8, 0, "passage")
    built = _line(ctx, [pattern], passage)
    if built is None:
        return None
    return built[1]


def test_barrios_thumb_steps_with_barrios_scale_step(monkeypatch) -> None:
    calls = {"barrios": 0, "villa": 0}
    import app.sonify.guitar_scale_passages as passages

    real_barrios = passages.barrios_scale_step
    real_villa = passages.villa_scale_step

    def barrios(ctx, pitch, direction, **kwargs):
        calls["barrios"] += 1
        return real_barrios(ctx, pitch, direction, **kwargs)

    def villa(ctx, pitch, direction, **kwargs):
        calls["villa"] += 1
        return real_villa(ctx, pitch, direction, **kwargs)

    monkeypatch.setattr(passages, "barrios_scale_step", barrios)
    monkeypatch.setattr(passages, "villa_scale_step", villa)
    realized = _host_realized("thumb_cantabile", 8, 16, ensemble="barrios")[2]
    assert realized is not None
    assert calls["barrios"] > 0
    assert calls["villa"] == 0


def test_villa_open_strings_wait_for_sixteenth_runs(monkeypatch) -> None:
    import app.sonify.guitar_scale_passages as passages

    calls = {"open": 0}
    real = passages.villa_open_candidates

    def wrapped(ctx, pitch, direction):
        calls["open"] += 1
        return real(ctx, pitch, direction)

    monkeypatch.setattr(passages, "villa_open_candidates", wrapped)
    calls["open"] = 0
    assert _host_realized("etude1", 8, 16, bpm=80, ensemble="villa")[2] is not None
    assert calls["open"] == 0
    calls["open"] = 0
    assert _host_realized("etude1", 8, 16, bpm=96, ensemble="villa")[2] is not None
    assert calls["open"] > 0

    # A run longer than two bars stays on eighths until its last bar.
    # Those eighths must not take an open string even though the BPM allows sixteenths.
    melody = []
    cursor = 60
    for index in range(40):
        melody.append(min(76, cursor))
        if index % 2 == 0:
            cursor += 1
    ctx = _ctx(melody, (_phrase(0, melody),), bpm=96, ensemble="villa")
    passage = ScalePassage(0, 24, "up", 8, 5.0, (), False, 24, 0, "passage")
    slots = _slots(ctx, ["etude1"], passage)
    assigned = _assign(ctx, passage, slots)
    assert assigned is not None
    assert any(slot.dur16 == 2 and slot.eighth < 16 for slot in slots)
    assert any(slot.dur16 == 1 and slot.eighth >= 16 for slot in slots)
    monkeypatch.setattr(passages, "villa_open_candidates", lambda *_args, **_kwargs: [])
    plain = _color_line(ctx, passage, slots, list(assigned))
    calls["open"] = 0
    monkeypatch.setattr(passages, "villa_open_candidates", wrapped)
    colored = _color_line(ctx, passage, slots, list(assigned))
    for slot, left, right in zip(slots, plain, colored):
        if slot.dur16 != 1:
            assert left == right
    assert calls["open"] > 0


def test_etude_and_thumb_hairpin_windows_follow_the_majority_pattern() -> None:
    thumb = hairpin_velocities(
        5,
        direction="down",
        pattern="thumb_cantabile",
        band="mf",
        prev=60,
        on_strong=True,
        length=8,
        epb=8,
        pillar=True,
    )
    preludio = hairpin_velocities(
        5,
        direction="down",
        pattern="preludio",
        band="mf",
        prev=60,
        on_strong=True,
        length=8,
        epb=8,
        pillar=True,
    )
    for curve in (thumb, preludio):
        assert curve[0] == 72
        assert curve[0] != 82
        assert curve[-1] == max(52, _BASS + 2)
        assert curve[-1] != 52
    etude = hairpin_velocities(
        5,
        direction="down",
        pattern="etude1",
        band="mf",
        prev=60,
        on_strong=True,
        length=8,
        epb=8,
        pillar=True,
    )
    assert etude[0] == 90
    assert etude[-1] == max(46, _BASS + 2)
    melody = [64] * 40
    phrases = (_phrase(0, melody[:32]), _phrase(32, melody[32:]))
    ctx = _ctx(melody, phrases, ensemble="classic")
    passage = ScalePassage(0, 40, "down", 8, 1.0, (), False, 40, 0, "passage")
    # Thirty-two elegiaque eighths and one etude bar. The window stays Hát.
    assert _majority_pattern(ctx, ["elegiaque", "etude1"], passage) == "elegiaque"


def test_etude1_hairpin_survives_humanize() -> None:
    climb_bar = [64, 65, 65, 66, 67, 69, 70, 71]
    melody = [64] * 24 + climb_bar + [72] + [72] * 15
    phrases = (_phrase(0, melody[:16]), _phrase(16, melody[16:]))
    score = _render(
        melody,
        phrases,
        (_Impulse(24, 32, "up", 8, score=6),),
        ensemble="villa",
        bpm=96,
        character="rally",
        raw=list(range(40, 40 + len(melody))),
    )
    notes = [event for start, event in _ordered(score.lead) if 48 <= start <= 64]
    assert notes
    velocities = [event.velocity for event in notes]
    assert velocities[0] == 46
    assert velocities[-1] == 90
    assert all(event.hairpin for event in notes)
    assert not any(
        event.midi is not None and event.bar == 3 for event in score.support
    )
    bass = [
        event
        for event in score.low
        if event.bar == 3 and event.midi is not None and not event.tie_stop
    ]
    assert len(bass) == 1 and bass[0].duration_beats == 4.0
    from app.sonify.humanize import humanize

    heard = humanize(score, offset_at=lambda *_args: 2)
    heard_notes = [event for start, event in _ordered(heard.lead) if 48 <= start <= 64]
    assert [event.velocity for event in heard_notes] == velocities
    assert all(event.hairpin for event in heard_notes)


def test_all_etude1_body_spends_the_full_passage_inside_thirty_percent() -> None:
    short = _plan([("etude1", 10)], _Impulse(0, 32, "up", 8, score=5))
    assert short.base_intrinsic_eighths == 0
    assert short.body_eighths == 80
    assert short.room == (30 * 80) // 100 == 24
    assert len(short.passages) == 1
    assert (short.passages[0].start, short.passages[0].target) == (8, 32)
    assert short.passages[0].passage_eighths == 24
    assert short.passages[0].replaced_base_intrinsic_eighths == 0
    assert short.room_after == 0
    long = _plan([("etude1", 84)], _Impulse(8, 16, "up", 6, score=1))
    assert long.base_intrinsic_eighths == 0
    assert long.room == (30 * long.body_eighths) // 100 == 201


def test_thumb_root_on_a_yielded_bar_keeps_the_bass_velocity() -> None:
    import math

    from app.sonify.guitar_wave import apply_guitar_wave

    bars = 2
    volumes = [math.exp(1.6) - 1, math.exp(1.6) - 1]
    melody = [72] + [60] * (bars * 8 - 1)
    phrase = _phrase(0, melody)
    ctx = replace(
        _ctx(melody, (phrase,), ensemble="villa", sections=(FormSection(0, bars, "phrase", 0),)),
        bar_volumes=volumes,
        rel_span=0.02,
        section_rel_spans={0: 0.02},
    )
    low = [
        NoteEvent(bar=0, beat=0.0, midi=48, duration_beats=4.0, voice=3, velocity=60),
        NoteEvent(bar=1, beat=0.0, midi=48, duration_beats=4.0, voice=3, velocity=60),
    ]
    lead = [NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=0.5, voice=1, velocity=64)]
    patterns = ["thumb_cantabile"]
    _lead, _support, plain = apply_guitar_wave(ctx, lead, [], low, patterns)
    assert plain[0].velocity != 60
    # Eighths 0..8 occupy bar 0. Eighth 8 is only the arrival on bar 1.
    _lead, _support, locked = apply_guitar_wave(ctx, lead, [], low, patterns, None, set(range(0, 9)))
    assert locked[0].velocity == 60
    assert locked[1].velocity == plain[1].velocity
    assert locked[1].velocity != 60


_HOSTS = ("etude1", "etude11", "thumb_cantabile", "preludio")


def _framed_sections(bars: int) -> tuple[FormSection, ...]:
    return (FormSection(0, bars, "phrase", 0),)


def test_short_impulses_on_tremolo_or_a_host_are_not_passages() -> None:
    """Three eighths miss the one-bar gate. The span is not stretched to a bar."""
    up = "up"
    for pattern in ("tremolo", "thumb_cantabile"):
        assert _spans([(pattern, 4)], _Impulse(18, 21, up, 8)) == [], pattern
        assert _spans([(pattern, 4)], _Impulse(18, 21, up, 3)) == [], pattern


def test_a_host_bar_below_the_gate_stays_on_the_pattern() -> None:
    """epb 8, [8, 24), net_span 5, etude1 opens at 0. No passage and no scale in the cycle."""
    impulse = _Impulse(8, 24, "up", 5, score=4)
    assert _spans([("etude1", 4)], impulse) == []
    melody = [64, 65, 67, 69, 71, 72, 74, 76] * 4
    score = _render(
        melody,
        (_phrase(0, melody),),
        (impulse,),
        ensemble="villa",
        bpm=96,
        character="rally",
        sections=(FormSection(0, 1, "warmup", 0),),
    )
    for bar in (1, 2):
        lead_sixteenths = [
            note
            for note in score.lead
            if note.bar == bar and note.midi is not None and abs(note.duration_beats - 0.25) < 1e-9
        ]
        cycle = [
            note
            for note in score.support
            if note.bar == bar and note.midi is not None and abs(note.duration_beats - 0.25) < 1e-9
        ]
        assert len(lead_sixteenths) < 8, bar
        assert len(cycle) >= 8, bar


def test_a_host_bar_inside_group3_below_the_gate_drops_the_passage() -> None:
    """epb 8, [0, 32), net_span 5. Bar 2 is etude1. The other bars are study."""
    assert _spans(
        _pad([("study", 2), ("etude1", 1), ("study", 1)], 7),
        _Impulse(0, 32, "up", 5),
    ) == []


def test_tremolo_that_misses_the_gate_keeps_an_edge_and_drops_the_middle() -> None:
    up = "up"
    # Seven bars leave room for the 16-eighth remainder. Six bars cap it at 14.
    assert _spans(
        _pad([("study", 2), ("tremolo", 1)], 7),
        _Impulse(0, 24, up, 5),
    ) == [(0, 16)]
    assert _spans(
        _pad([("study", 1), ("tremolo", 1), ("study", 1)], 7),
        _Impulse(0, 24, up, 5),
    ) == []


def test_a_tremolo_region_yields_the_bars_after_its_opening() -> None:
    """epb 8, [8, 40), net_span >= 6, tremolo opens at eighth 8. Passage is [16, 40)."""
    assert _spans(
        _pad([("study", 1), ("tremolo", 4)], 10),
        _Impulse(8, 40, "up", 8),
    ) == [(16, 40)]


def test_an_inward_snap_on_a_yielded_grid_does_not_grow_the_span() -> None:
    """[12, 22) clears the gate but no whole bar survives. Choro keeps the overlay."""
    up = "up"
    impulse = _Impulse(12, 22, up, 7)
    framed = _framed_sections(4)
    for pattern in ("tremolo", *_HOSTS):
        kwargs = {"sections": framed} if pattern == "preludio" else {}
        assert _spans([(pattern, 4)], impulse, **kwargs) == [], pattern
    # Five bars so the 10-eighth overlay fits under the 30% cap. Four bars leave room 9.
    assert _spans(_pad([("choro", 4)], 5), impulse) == [(12, 22)]
    assert _spans(_pad([("andante", 4)], 5), impulse) == [(12, 22)]
    assert _spans(_pad([("preludio", 4)], 5), impulse) == [(12, 22)]


def test_a_three_eighth_choro_impulse_keeps_a_group3_passage() -> None:
    assert _spans([("choro", 2)], _Impulse(0, 3, "up", 2)) == [(0, 3)]
    for pattern in ("study", "andante", "villa_pattern", "chord_melody"):
        assert _spans([(pattern, 2)], _Impulse(1, 4, "up", 3)) == [(1, 4)], pattern


def test_one_tremolo_bar_in_the_middle_of_a_sor_impulse_keeps_only_the_front() -> None:
    """epb 8, [0, 32), net_span >= 6, tremolo exactly [16, 24). Passage is [0, 16)."""
    assert _spans(
        _pad([("study", 2), ("tremolo", 1), ("study", 2)], 7),
        _Impulse(0, 32, "up", 8),
    ) == [(0, 16)]


def test_tremolo_after_the_region_opening_stays_inside_the_passage() -> None:
    """Opens at 0. [8, 24) is still tremolo and [24, 32) is Sor. Passage is [8, 32)."""
    assert _spans(
        _pad([("tremolo", 3), ("study", 1)], 10),
        _Impulse(8, 32, "up", 8),
    ) == [(8, 32)]


def test_a_stepwise_run_on_tremolo_or_a_host_uses_the_bars_after_the_opening() -> None:
    up = "up"
    melody = [60, 62, 64, 65, 67, 69, 71, 72] * 8
    framed = _framed_sections(8)
    for pattern in ("tremolo", "etude1", "etude11", "thumb_cantabile"):
        assert _spans(
            _pad([(pattern, 4)], 7),
            _Impulse(8, 24, up, 8),
            melody=melody,
        ) == [(8, 24)], pattern
    assert _spans(
        _pad([("preludio", 4)], 7),
        _Impulse(8, 24, up, 8),
        melody=melody,
        sections=framed,
        ensemble="barrios",
    ) == [(8, 24)]


def test_a_leap_the_line_cannot_draw_does_not_spend_room() -> None:
    melody = [64, 71, 71, 71, 71, 71, 71, 71, 71] + [71] * 23
    raw = [64] * len(melody)
    impulse = _Impulse(0, 8, "up", 7, score=5)
    ctx = _ctx(
        melody,
        (_phrase(0, melody),),
        impulses=(impulse,),
        ensemble="classic",
        bpm=96,
        raw=raw,
    )
    passage = ScalePassage(0, 8, "up", 7, 5.0, (), False, 8, 0, "passage")
    lead = _eighth_event(0, len(melody), melody[0], 8, 1, 72)
    assert realize_scale_passage(ctx, passage, ["study"], lead, [], []) is None

    def accept(item: ScalePassage) -> bool:
        return realize_scale_passage(ctx, item, ["study"], lead, [], []) is not None

    plan = select_scale_plan(ctx, ["study"], accept_passage=accept, accept_tier1=lambda _item: False)
    assert plan.passages == ()
    assert plan.room_after == plan.room
    assert plan.room > 8
