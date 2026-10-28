"""Allocation and realization of classical-guitar scale passages."""

from dataclasses import dataclass, replace

import math

from app.sonify.form import METER_44, METER_68, ChordSlot, FormSection, compose_meter
from app.sonify.chords import C
from app.sonify.guitar import BARRIOS_TREMOLO_MIN_BPM
from app.sonify.guitar_bach import _fuga_motif
from app.sonify.guitar_patterns import (
    _Ctx,
    _dur16,
    _spell16,
    _splice,
    _start16,
    assert_playable,
    render_patterned_voices,
)
from app.sonify.guitar_scale_passages import (
    SCALE_SIXTEENTH_MIN_BPM,
    ScalePassage,
    _BASS,
    _Slot,
    _assign,
    _curve,
    _monotone,
    _slots,
    _pattern_window,
    _stamp_arrival,
    hairpin_velocities,
    plan_scale_budget,
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
    forbidden = {
        "tremolo": ["study", "tremolo"],
        "etude1": ["study", "etude1"],
        "etude11": ["study", "etude11"],
        "thumb_cantabile": ["study", "thumb_cantabile"],
    }
    for name, patterns in forbidden.items():
        plan = plan_scale_budget(_ctx(melody, phrases, impulses=(crossing,)), patterns)
        assert plan.passages == (), name
    framed = _ctx(
        melody,
        (_phrase(0, melody),),
        sections=(FormSection(0, 4, "phrase", 0),),
        impulses=(_Impulse(0, 8, "up", 8, score=4),),
    )
    assert plan_scale_budget(framed, ["preludio"]).passages == ()
    plain = _ctx(melody, (_phrase(0, melody),), impulses=(_Impulse(0, 8, "up", 8, score=4),))
    kept = plan_scale_budget(plain, ["preludio"])
    assert kept.passages and kept.passages[0].start == 0 and kept.passages[0].target == 8
    # A run that stops before the tremolo bar stays. The crossing run is not shortened.
    clear = plan_scale_budget(
        _ctx(melody, phrases, impulses=(_Impulse(0, 8, "up", 8, score=2), crossing)),
        ["study", "tremolo"],
    )
    assert [ (item.start, item.target) for item in clear.passages ] == [(0, 8)]


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
    assert all(right >= left for left, right in zip(pitches, pitches[1:]))
    assert pitches[-1] == 72

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
    assert moving is not None
    assert moving[0] == 64 and moving[-1] == 67
    assert all(right >= left for left, right in zip(moving, moving[1:]))
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
