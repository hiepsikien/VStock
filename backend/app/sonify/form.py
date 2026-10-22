"""30-bar daily recap: intro, three 8-bar phrases, outro.

Tempo is 90. A bar is 4 beats (8 eighths). Regime changes land on the phrase
downbeats — musical bars 3, 11 and 19 when counted from 1 — which already
includes the 2-bar intro. Intro and outro pedal the tonic of the neighbouring
phrase instead of running a progression of their own. Inside the three 8-bar
phrases, when raw pitches are provided, harmony is chosen bar-by-bar with a
Viterbi Markov chain over triads and seventh chords that balances quantization
loss against acoustic chord transition probabilities and a gentle regime bias,
merging consecutive bars that stay on the same chord into one ChordSlot.
Without pitches, plan_slots falls back to the regime reference loops.
Liquidity is always measured on the fixed 14-window grid (LIQUIDITY_WINDOWS)
so dynamics and bass pulse depend only on volume, never on the price path.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from app.sonify.chords import (
    CHORDS,
    HOME_MAJOR,
    HOME_MINOR,
    MINOR_CATALOG,
    REGIME_BIAS,
    Chord,
    Regime,
    _ROOT_REGIME_BIAS,
    borrowed_transition,
    chords_for_spec,
    is_subdominant,
    minor_bias,
    minor_root_probability,
    progression,
    same_harmonic_root,
    tonic,
    tonic_chords,
    transition_probability,
)
from app.sonify.keys import MovementCharacter
from app.sonify.quantize import (
    bar_quantization_loss,
    c_major_scale,
    melody_pitch_classes,
    quantize_chord_tone,
    sing_leading,
)

MUSICAL_BARS = 30
BEATS_PER_BAR = 4
EIGHTHS_PER_BAR = 8
HALF_BAR = 4
TOTAL_EIGHTHS = MUSICAL_BARS * EIGHTHS_PER_BAR
BPM = 90
PHRASE_STARTS = (2, 10, 18)
PHRASE_BARS = 8
OUTRO_START = 26
SECTION_STARTS = (0, *PHRASE_STARTS, OUTRO_START)

# Fixed 14-window grid (start_bar, length) for volume / liquidity dynamics:
# 2-bar intro, twelve 2-bar windows across the three phrases, 4-bar outro.
LIQUIDITY_WINDOWS: tuple[tuple[int, int], ...] = (
    (0, 2),
    *((start, 2) for start in range(PHRASE_STARTS[0], OUTRO_START, 2)),
    (OUTRO_START, MUSICAL_BARS - OUTRO_START),
)

TRANSITION_WEIGHT = 0.6
SECOND_BAR_STAY_COST = 0.15
EXTENDED_STAY_PENALTY = 0.25
SINGLE_BAR_CHANGE_PENALTY = 0.65
_CHARACTER_SEVENTH = {"rally": 0.05, "selloff": 0.05, "volatile": 0.0, "calm": 0.08}
_CHARACTER_BAR_CHANGE = {"rally": 0.60, "selloff": 0.60, "volatile": 0.45, "calm": 0.80}
_DIATONIC_DELTA: dict[str, dict[str, float]] = {
    "rally": {
        "C": -0.08, "Cmaj7": -0.08, "F": -0.08, "Fmaj7": -0.08, "G": -0.08, "G7": -0.08,
        "Am": 0.06, "Am7": 0.06, "Dm": 0.06, "Dm7": 0.06, "Em": 0.06, "Em7": 0.06,
    },
    "selloff": {
        "Am": -0.08, "Am7": -0.08, "Dm": -0.08, "Dm7": -0.08, "Em": -0.08, "Em7": -0.08,
        "C": 0.06, "Cmaj7": 0.06,
    },
    "volatile": {},
    "calm": {},
}
_BORROWED_DELTA: dict[str, dict[str, float]] = {
    "rally": {"D7": -0.06, "C7": -0.06, "A7": -0.06},
    "selloff": {"Fm": -0.06, "Gm": -0.06, "Ab": -0.06, "Eb": -0.06, "Bm7b5": -0.06, "E7": -0.06},
    "volatile": {},
    "calm": {},
}
SAME_ROOT_QUALITY_CHANGE_PENALTY = 0.35
PEDAL_STAY_COST = 0.0
PHRASE_TONIC_BONUS = 0.25
# Matches the smaller diatonic self-stays (F and D are 0.16 in _ROOT_TRANSITIONS).
# A borrowed chord may hold for a second bar, but bars after that cost the same
# as staying on a diatonic root. prob 1.0 would make those later bars almost free.
BORROWED_HOLD_PROB = 0.16
CROSS_BAR_BREAK_PENALTY = 1.2

Section = Literal["intro", "phrase", "outro", "warmup", "cooldown"]
_PEDAL: frozenset[str] = frozenset({"intro", "outro", "warmup", "cooldown"})
WHOLE_BAR_BEATS = frozenset({3.0, 4.0, 6.0})


@dataclass(frozen=True)
class Meter:
    """One time signature. `quarter_beats` is the bar length in quarter notes."""

    beats: int
    beat_type: int
    eighths_per_bar: int
    strong_eighths: tuple[int, ...]
    subbar_breaks: tuple[int, ...]
    extra_weights: tuple[tuple[int, float], ...] = ()

    @property
    def quarter_beats(self) -> float:
        return self.eighths_per_bar / 2


METER_44 = Meter(4, 4, 8, (0, 4), (4,))
METER_34 = Meter(3, 4, 6, (0,), (4,), ((4, 0.8),))
METER_68 = Meter(6, 8, 6, (0, 3), (3,))
METER_128 = Meter(12, 8, 12, (0, 3, 6, 9), (3, 6, 9))
METER_54 = Meter(5, 4, 10, (0, 6), (6,))
METER_64 = Meter(6, 4, 12, (0, 4, 8), (6,))
METER_78 = Meter(7, 8, 7, (0, 2, 4), (2, 4))

_METER: ContextVar[Meter] = ContextVar("sonify_meter", default=METER_44)


def active_meter() -> Meter:
    return _METER.get()


@contextmanager
def compose_meter(meter: Meter):
    token = _METER.set(meter)
    try:
        yield
    finally:
        _METER.reset(token)


def swing_for(variant: str, meter: Meter) -> bool:
    """Jazz swings 4/4 and 3/4. 12/8 is already four groups of three, so it stays straight."""
    return variant == "jazz" and meter.beat_type == 4


@dataclass(frozen=True)
class FormSection:
    """One harmonic region. `regime_slot` indexes the regime tuple passed at plan time."""

    start: int
    end: int
    kind: Section
    regime_slot: int
    bridge: bool = False
    trio: bool = False


@dataclass(frozen=True)
class FormSpec:
    """Bar grid for one movement. The 30-bar daily recap stays `DAILY_SPEC`."""

    bars: int
    bpm: int
    sections: tuple[FormSection, ...]
    # Exclusive end bars of the phrase grid. The live export does not cut the
    # score here; MuseScore writes the whole movement once. slice_score can
    # still rebase a span of these bars if a file is ever split again.
    chunks: tuple[int, ...] = ()
    borrowed: bool = False
    meter: Meter = METER_44

    @property
    def eighths(self) -> int:
        return self.bars * self.meter.eighths_per_bar

    @property
    def regime_slots(self) -> int:
        return max(section.regime_slot for section in self.sections) + 1

    @property
    def section_starts(self) -> tuple[int, ...]:
        return tuple(section.start for section in self.sections)

    @property
    def phrase_starts(self) -> tuple[int, ...]:
        return tuple(section.start for section in self.sections if section.kind == "phrase")

    def spans(
        self, regimes: Sequence[Regime]
    ) -> tuple[tuple[int, int, Regime, Section], ...]:
        if len(regimes) != self.regime_slots:
            raise ValueError(f"expected {self.regime_slots} regimes, got {len(regimes)}")
        return tuple(
            (section.start, section.end, regimes[section.regime_slot], section.kind)
            for section in self.sections
        )

    def chunk_bounds(self) -> tuple[tuple[int, int], ...]:
        if not self.chunks:
            return ((0, self.bars),)
        bounds: list[tuple[int, int]] = []
        start = 0
        for end in self.chunks:
            bounds.append((start, end))
            start = end
        if start != self.bars:
            raise ValueError("chunk ends must cover the movement")
        return tuple(bounds)


def liquidity_windows_for(spec: FormSpec) -> tuple[tuple[int, int], ...]:
    """Intro and outro are one window each. Phrases split into 2-bar windows."""
    windows: list[tuple[int, int]] = []
    for section in spec.sections:
        if section.kind in ("warmup", "cooldown"):
            continue
        if section.kind in ("intro", "outro"):
            windows.append((section.start, section.end - section.start))
            continue
        bar = section.start
        while bar < section.end:
            windows.append((bar, min(2, section.end - bar)))
            bar += 2
    return tuple(windows)


# Same grid as the constants above, so a daily plan with this spec matches the
# historical 30-bar path.
DAILY_SPEC = FormSpec(
    bars=MUSICAL_BARS,
    bpm=BPM,
    sections=(
        FormSection(0, PHRASE_STARTS[0], "intro", 0),
        FormSection(PHRASE_STARTS[0], PHRASE_STARTS[1], "phrase", 0),
        FormSection(PHRASE_STARTS[1], PHRASE_STARTS[2], "phrase", 1),
        FormSection(PHRASE_STARTS[2], OUTRO_START, "phrase", 2),
        FormSection(OUTRO_START, MUSICAL_BARS, "outro", 2),
    ),
    chunks=(),
    borrowed=False,
)


# 1D Ambient keeps the 30-bar price body and attaches a frame around it.
# Bars 0–1 warm up. Bars 2–31 are the old day, with the former intro joined to
# phrase 1 and the former outro joined to phrase 3 so those minutes follow the
# price. Bars 32–33 cool down. 60 BPM makes each frame 8s, and the body
# stays 2:00.
DAILY_WARMUP_BARS = 2
DAILY_BODY_BARS = MUSICAL_BARS
DAILY_COOLDOWN_BARS = 2
DAILY_AMBIENT_BARS = DAILY_WARMUP_BARS + DAILY_BODY_BARS + DAILY_COOLDOWN_BARS
DAILY_AMBIENT_SPEC = FormSpec(
    bars=DAILY_AMBIENT_BARS,
    bpm=60,
    sections=(
        FormSection(0, DAILY_WARMUP_BARS, "intro", 0),
        FormSection(DAILY_WARMUP_BARS, DAILY_WARMUP_BARS + PHRASE_STARTS[1], "phrase", 0),
        FormSection(
            DAILY_WARMUP_BARS + PHRASE_STARTS[1],
            DAILY_WARMUP_BARS + PHRASE_STARTS[2],
            "phrase",
            1,
        ),
        FormSection(
            DAILY_WARMUP_BARS + PHRASE_STARTS[2],
            DAILY_WARMUP_BARS + MUSICAL_BARS,
            "phrase",
            2,
        ),
        FormSection(DAILY_WARMUP_BARS + MUSICAL_BARS, DAILY_AMBIENT_BARS, "outro", 2),
    ),
    borrowed=True,
)


# Symphony, jazz, and minimalist use the same 34-bar day. The old intro and
# outro stay inside the body as phrase bars, so those minutes follow the price.
# Only the attached warm-up and cool-down pedal the tonic.
DAILY_ENSEMBLE_SPEC = FormSpec(
    bars=DAILY_AMBIENT_BARS,
    bpm=BPM,
    sections=(
        FormSection(0, DAILY_WARMUP_BARS, "intro", 0),
        FormSection(DAILY_WARMUP_BARS, DAILY_WARMUP_BARS + PHRASE_STARTS[0], "phrase", 0),
        FormSection(
            DAILY_WARMUP_BARS + PHRASE_STARTS[0],
            DAILY_WARMUP_BARS + PHRASE_STARTS[1],
            "phrase",
            0,
        ),
        FormSection(
            DAILY_WARMUP_BARS + PHRASE_STARTS[1],
            DAILY_WARMUP_BARS + PHRASE_STARTS[2],
            "phrase",
            1,
        ),
        FormSection(
            DAILY_WARMUP_BARS + PHRASE_STARTS[2],
            DAILY_WARMUP_BARS + OUTRO_START,
            "phrase",
            2,
        ),
        FormSection(
            DAILY_WARMUP_BARS + OUTRO_START,
            DAILY_WARMUP_BARS + MUSICAL_BARS,
            "phrase",
            2,
        ),
        FormSection(DAILY_WARMUP_BARS + MUSICAL_BARS, DAILY_AMBIENT_BARS, "outro", 2),
    ),
    borrowed=True,
)


@dataclass(frozen=True)
class ChordSlot:
    start: int
    length: int
    chord: Chord
    regime: Regime
    section: Section

    def bars(self) -> range:
        return range(self.start, self.start + self.length)


def _section_spans(
    regimes: tuple[Regime, Regime, Regime],
) -> tuple[tuple[int, int, Regime, Section], ...]:
    return (
        (0, PHRASE_STARTS[0], regimes[0], "intro"),
        (PHRASE_STARTS[0], PHRASE_STARTS[1], regimes[0], "phrase"),
        (PHRASE_STARTS[1], PHRASE_STARTS[2], regimes[1], "phrase"),
        (PHRASE_STARTS[2], OUTRO_START, regimes[2], "phrase"),
        (OUTRO_START, MUSICAL_BARS, regimes[2], "outro"),
    )


_UP_EXTRA = frozenset({"D7", "C7"})
_DOWN_EXTRA = frozenset({"Fm", "Gm", "Ab", "Eb", "E7", "Bm7b5"})
_SIDE_EXTRA = frozenset({"Bb", "Bb7", "C7", "A7", "F#dim7"})
_PASSING = frozenset({"Bm7b5", "F#dim7"})


def _borrowed_allowed(chord: Chord, regime: Regime, phrase_downbeat: bool) -> bool:
    """Diatonic chords stay. Extras are regime-gated, and passing chords miss the downbeat."""
    if chord in CHORDS:
        return True
    if phrase_downbeat and chord.name in _PASSING:
        return False
    extras = {"uptrend": _UP_EXTRA, "downtrend": _DOWN_EXTRA, "sideway": _SIDE_EXTRA}[regime]
    return chord.name in extras


def _prev_last_touched_strong(
    raw_pitches: Sequence[int], bar: int, meter: Meter | None = None
) -> bool:
    """Whether the final eighth of `bar - 1` belongs to a run that touches a strong beat.

    The run counts when it holds from the last strong eighth through the end of
    the bar, or when the same pitch continues onto the next downbeat.
    """
    grid = METER_44 if meter is None else meter
    epb = grid.eighths_per_bar
    prev_last = raw_pitches[bar * epb - 1]
    if prev_last == raw_pitches[bar * epb]:
        return True
    prev_bar_start = (bar - 1) * epb
    last_strong = grid.strong_eighths[-1]
    return all(raw_pitches[prev_bar_start + e] == prev_last for e in range(last_strong, epb))


def _breaks_held_note_across_barline(
    boundary_pitch: int,
    prev_chord: Chord,
    curr_chord: Chord,
    scale: tuple[int, ...],
    index_of: dict[int, int],
    mode: str = "major",
) -> bool:
    """Whether changing from prev_chord to curr_chord forces a held note to split pitches.

    Matches `quantize_strong_beats` in `phrasing.py`: when a run holds the same raw
    pitch across a bar line (`raw[bar*8 - 1] == raw[bar*8]`, the same condition
    `runs_of` uses to merge eighths into one Run), `quantize_strong_beats` snaps
    both sides to a single shared chord tone whenever `prev_chord & curr_chord`
    has a tone within 1 scale step of `boundary_pitch`. A split happens only when
    no such common tone exists and the two chords snap `boundary_pitch` to
    different notes.
    """
    if prev_chord == curr_chord:
        return False
    if mode == "minor" and boundary_pitch % 12 == 10:
        prev_sung = sing_leading(boundary_pitch) if prev_chord.name in ("G", "G7") else boundary_pitch
        curr_sung = sing_leading(boundary_pitch) if curr_chord.name in ("G", "G7") else boundary_pitch
        if prev_sung != curr_sung:
            return True
    common = melody_pitch_classes(prev_chord.pitch_classes & curr_chord.pitch_classes, scale)
    if common:
        snapped_common = quantize_chord_tone(boundary_pitch, common, scale)
        if abs(index_of[snapped_common] - index_of[boundary_pitch]) <= 1:
            return False
    prev_snapped = quantize_chord_tone(boundary_pitch, prev_chord.pitch_classes, scale)
    curr_snapped = quantize_chord_tone(boundary_pitch, curr_chord.pitch_classes, scale)
    return prev_snapped != curr_snapped


def chord_bias(chord: Chord, regime: Regime, character: MovementCharacter | None) -> float:
    """Per-chord cost. `None` reads the baked `REGIME_BIAS` table, sevenths included."""
    if character is None:
        return REGIME_BIAS[regime][chord] if chord in REGIME_BIAS[regime] else 0.08
    if chord in CHORDS:
        seventh = _CHARACTER_SEVENTH[character] if len(chord.pitches) == 4 else 0.0
        return (
            _ROOT_REGIME_BIAS[regime][chord.root_step]
            + seventh
            + _DIATONIC_DELTA[character].get(chord.name, 0.0)
        )
    return 0.08 + _BORROWED_DELTA[character].get(chord.name, 0.0)


def _bar_change_penalty(character: MovementCharacter | None) -> float:
    if character is None:
        return SINGLE_BAR_CHANGE_PENALTY
    return _CHARACTER_BAR_CHANGE[character]


def plan_markov_chords(
    regimes: tuple[Regime, ...] | tuple[Regime, Regime, Regime],
    raw_pitches: Sequence[int],
    scale: tuple[int, ...] | None = None,
    spec: FormSpec | None = None,
    character: MovementCharacter | None = None,
    outro_override: Literal["major", "minor"] | None = None,
    mode: Literal["major", "minor"] = "major",
    home_pedal: bool = False,
    harmonic_bridge: bool = True,
    character_at: Sequence[MovementCharacter | None] | None = None,
    gap_leads: Sequence[str | None] | None = None,
) -> tuple[Chord, ...]:
    """Decode the lowest-loss 30-bar Markov chord path via Viterbi.

    Intro (bars 0–1) and outro (bars 26–29) pedal the tonic of the neighbouring
    phrase (selecting the tonic triad or tonic seventh chord and holding it
    steady across the pedal section). Inside the three 8-bar phrases, each bar
    state tracks (chord, held_bars) with held_bars in {1, 2}, where 1 is the
    opening bar of a harmonic root inside a section and 2 means that root has
    held for two or more bars (a triad and its seventh chord share the same
    root, so switching C <-> Cmaj7 counts as staying on the root rather than
    resetting held_bars to 1, and carries a small quality-change cost).
    Completing a 2-bar breath is cheap, changing roots after 1 bar is chosen
    whenever the new chord reduces quantization loss, and staying on the same
    chord for 3+ bars is chosen whenever staying preserves the melody notes
    better than moving.
    """
    if spec is None:
        if len(regimes) != 3:
            raise ValueError("expected one regime per phrase")
        musical_bars = MUSICAL_BARS
        section_starts = SECTION_STARTS
        phrase_starts = PHRASE_STARTS
        spans = _section_spans(regimes)  # type: ignore[arg-type]
        borrowed = False
    else:
        musical_bars = spec.bars
        section_starts = spec.section_starts
        phrase_starts = spec.phrase_starts
        spans = spec.spans(regimes)
        borrowed = spec.borrowed
    meter = METER_44 if spec is None else spec.meter
    epb = meter.eighths_per_bar
    bar_slot = [0] * musical_bars
    trio_bars: set[int] = set()
    trio_downbeats: set[int] = set()
    coda_v: set[int] = set()
    coda_iv: set[int] = set()
    if spec is not None:
        for index, section in enumerate(spec.sections):
            for bar in range(section.start, min(section.end, musical_bars)):
                bar_slot[bar] = section.regime_slot
            if section.trio:
                trio_downbeats.add(section.start)
                mid = section.start + max(1, (section.end - section.start) // 2)
                trio_bars.update(range(section.start, mid))
            if section.kind != "outro" or index == 0:
                continue
            previous = spec.sections[index - 1]
            if previous.kind != "phrase" or section.start - previous.start < 2:
                continue
            coda_v.add(section.start - 1)
            coda_v.add(section.start - 2)
            if spec.bars == DAILY_AMBIENT_BARS and section.start == DAILY_WARMUP_BARS + MUSICAL_BARS:
                coda_iv.update((28, 29))
    penalties: list[float] = []
    bar_character: list[MovementCharacter | None] = []
    for bar in range(musical_bars):
        chosen = character
        if character_at is not None and bar < len(character_at) and character_at[bar] is not None:
            chosen = character_at[bar]
        penalty = _bar_change_penalty(chosen)
        if chosen == "volatile" and bar_slot[bar] == 1:
            penalty = 0.35
        penalties.append(penalty)
        bar_character.append(chosen)
    for regime in regimes:
        progression(regime)
    expected_eighths = musical_bars * epb
    if len(raw_pitches) != expected_eighths:
        raise ValueError(f"expected {expected_eighths} eighth-note pitches, got {len(raw_pitches)}")
    active_scale = c_major_scale() if scale is None else scale
    index_of = {note: index for index, note in enumerate(active_scale)}

    bar_regime: list[Regime] = []
    bar_section: list[Section] = []
    for start, end, regime, section in spans:
        bar_regime.extend([regime] * (end - start))
        bar_section.extend([section] * (end - start))

    catalog = MINOR_CATALOG if mode == "minor" else chords_for_spec(borrowed)
    bridge_starts = {
        section.start
        for section in (spec.sections if spec is not None and harmonic_bridge else ())
        if section.bridge
    }
    bridge_cadence: set[int] = set()
    if spec is not None and harmonic_bridge:
        for section in spec.sections:
            if section.bridge and section.end - section.start >= 2:
                bridge_cadence.add(section.end - 2)
                bridge_cadence.add(section.end - 1)
    states = [(chord, held) for chord in catalog for held in (1, 2)]
    dp: list[dict[tuple[Chord, int], float]] = [{} for _ in range(musical_bars)]
    back: list[dict[tuple[Chord, int], tuple[Chord, int] | None]] = [
        {} for _ in range(musical_bars)
    ]

    for bar in range(musical_bars):
        bar_notes = raw_pitches[bar * epb : (bar + 1) * epb]
        regime = bar_regime[bar]
        section = bar_section[bar]
        if mode == "minor" or home_pedal:
            allowed_tonics = HOME_MINOR if mode == "minor" else HOME_MAJOR
        else:
            allowed_tonics = tonic_chords(regime)
            if section in ("outro", "cooldown") and outro_override == "major":
                allowed_tonics = tonic_chords("uptrend")
            elif section in ("outro", "cooldown") and outro_override == "minor":
                allowed_tonics = tonic_chords("downtrend")
        new_section = bar in section_starts
        previous_pitch = raw_pitches[bar * epb - 1] if bar > 0 else None
        phrase_downbeat = bar in phrase_starts

        def emit(notes: Sequence[int], chord: Chord, **extra: int | None) -> float:
            return bar_quantization_loss(
                notes,
                chord.pitch_classes,
                active_scale,
                strong_eighths=meter.strong_eighths,
                extra_weights=meter.extra_weights,
                mode=mode,
                chord_name=chord.name,
                previous_pitch=extra.get("previous_pitch"),
                previous_snapped=extra.get("previous_snapped"),
            )

        for chord in catalog:
            if (
                mode != "minor"
                and borrowed
                and not _borrowed_allowed(chord, regime, phrase_downbeat)
            ):
                dp[bar][(chord, 1)] = float("inf")
                dp[bar][(chord, 2)] = float("inf")
                back[bar][(chord, 1)] = None
                back[bar][(chord, 2)] = None
                continue
            if mode == "minor" and chord.name == "F#dim7" and phrase_downbeat:
                dp[bar][(chord, 1)] = float("inf")
                dp[bar][(chord, 2)] = float("inf")
                back[bar][(chord, 1)] = None
                back[bar][(chord, 2)] = None
                continue
            if section in _PEDAL and chord not in allowed_tonics:
                dp[bar][(chord, 1)] = float("inf")
                dp[bar][(chord, 2)] = float("inf")
                back[bar][(chord, 1)] = None
                back[bar][(chord, 2)] = None
                continue

            if mode == "minor":
                base_bias = minor_bias(chord, regime)
            else:
                base_bias = chord_bias(chord, regime, bar_character[bar])
            if bar in bridge_starts and is_subdominant(chord, mode):
                base_bias -= PHRASE_TONIC_BONUS
            elif phrase_downbeat and chord in allowed_tonics and bar not in bridge_starts:
                base_bias -= PHRASE_TONIC_BONUS
            if bar in bridge_cadence and chord.name in ("G", "G7"):
                base_bias -= PHRASE_TONIC_BONUS
            if (
                mode == "minor"
                and regime == "uptrend"
                and bar in trio_bars
                and chord.name in ("Eb", "Ebmaj7", "Ab", "Abmaj7")
            ):
                base_bias -= 0.12
            if (
                bar in trio_downbeats
                and mode == "minor"
                and regime == "uptrend"
                and chord.name in ("Eb", "Ebmaj7")
            ):
                base_bias -= PHRASE_TONIC_BONUS
            if bar in coda_v and chord.name in ("G", "G7", "G9"):
                base_bias -= PHRASE_TONIC_BONUS
            if bar in coda_iv and is_subdominant(chord, mode):
                base_bias -= 0.15
            if gap_leads is not None and bar < len(gap_leads):
                lead = gap_leads[bar]
                if lead == "up" and chord.name in ("G7", "D7"):
                    base_bias -= PHRASE_TONIC_BONUS
                elif lead == "down" and chord.name in ("E7", "Fm"):
                    base_bias -= PHRASE_TONIC_BONUS

            if bar == 0:
                emission = emit(bar_notes, chord) + base_bias
                dp[0][(chord, 1)] = emission
                back[0][(chord, 1)] = None
                dp[0][(chord, 2)] = float("inf")
                back[0][(chord, 2)] = None
                continue

            # Two equal adjacent eighth-note pitches across the barline form a single
            # held Run in `runs_of(raw_pitches, ...)`.
            held_across = raw_pitches[bar * epb - 1] == raw_pitches[bar * epb]
            boundary_pitch = raw_pitches[bar * epb]
            if previous_pitch is None:
                raise RuntimeError("expected previous_pitch for bar > 0")
            prev_last_touched_strong = _prev_last_touched_strong(raw_pitches, bar, meter)
            if not prev_last_touched_strong or bar_notes[0] % 12 in chord.pitch_classes:
                uniform_emission = (
                    emit(
                        bar_notes,
                        chord,
                        previous_pitch=previous_pitch,
                        previous_snapped=previous_pitch,
                    )
                    + base_bias
                )
                prev_snapped_by_chord = None
                emission_by_prev_snapped = None
            else:
                uniform_emission = 0.0
                prev_snapped_by_chord = {
                    prev_chord: quantize_chord_tone(
                        previous_pitch, prev_chord.pitch_classes, active_scale
                    )
                    for prev_chord in catalog
                }
                emission_by_prev_snapped = {
                    snapped_val: (
                        emit(
                            bar_notes,
                            chord,
                            previous_pitch=previous_pitch,
                            previous_snapped=snapped_val,
                        )
                        + base_bias
                    )
                    for snapped_val in set(prev_snapped_by_chord.values())
                }

            for target_held in (1, 2):
                best_prev: tuple[Chord, int] | None = None
                best_cost = float("inf")
                for prev_chord, prev_held in states:
                    if dp[bar - 1][(prev_chord, prev_held)] == float("inf"):
                        continue
                    # Intro and outro hold one steady tonic pedal across all bars of the section.
                    if section in _PEDAL and not new_section and prev_chord != chord:
                        continue
                    if mode == "minor":
                        same_root = (
                            prev_chord.root_step == chord.root_step
                            and prev_chord.alter == chord.alter
                        )
                    elif borrowed:
                        same_root = same_harmonic_root(prev_chord, chord)
                    else:
                        same_root = prev_chord.root_step == chord.root_step
                    if new_section:
                        if target_held != 1:
                            continue
                    elif same_root:
                        if target_held != 2:
                            continue
                    elif target_held != 1:
                        continue

                    if (
                        (borrowed or mode == "minor")
                        and chord.quality_group == "diminished"
                        and target_held != 1
                    ):
                        continue
                    if mode == "minor":
                        root_prob = minor_root_probability(prev_chord, chord)
                        if root_prob <= 0.0:
                            continue
                    else:
                        prob = transition_probability(prev_chord, chord)
                        if prob <= 0.0 and borrowed:
                            prob = borrowed_transition(prev_chord, chord)
                        # A borrowed chord has no self-edge in the diatonic table. Staying
                        # on it is still a legal hold; only the passing diminished is one bar.
                        if (
                            prob <= 0.0
                            and borrowed
                            and prev_chord == chord
                            and chord.quality_group != "diminished"
                        ):
                            prob = BORROWED_HOLD_PROB
                        if prob <= 0.0:
                            continue

                        # Each root's probability mass is split equally across its triad and
                        # seventh chord, so `prob * 2.0` recovers the root-to-root transition probability.
                        # Borrowed catalogs do not have two chords per root, so they read the
                        # root table directly.
                        if not borrowed or (prev_chord in CHORDS and chord in CHORDS):
                            root_prob = prob * 2.0
                        else:
                            root_prob = max(prob, borrowed_transition(prev_chord, chord))
                    if not new_section and same_root:
                        if section in _PEDAL:
                            trans_cost = PEDAL_STAY_COST
                        elif prev_held == 1:
                            trans_cost = SECOND_BAR_STAY_COST
                        else:
                            trans_cost = (
                                -TRANSITION_WEIGHT * math.log(root_prob) + EXTENDED_STAY_PENALTY
                            )
                    else:
                        trans_cost = -TRANSITION_WEIGHT * math.log(root_prob)
                        if not new_section and prev_held == 1:
                            trans_cost += penalties[bar]
                    if same_root and prev_chord != chord:
                        trans_cost += SAME_ROOT_QUALITY_CHANGE_PENALTY

                    if held_across and _breaks_held_note_across_barline(
                        boundary_pitch, prev_chord, chord, active_scale, index_of, mode
                    ):
                        trans_cost += CROSS_BAR_BREAK_PENALTY

                    if emission_by_prev_snapped is None or prev_snapped_by_chord is None:
                        emission = uniform_emission
                    else:
                        emission = emission_by_prev_snapped[prev_snapped_by_chord[prev_chord]]
                    total = dp[bar - 1][(prev_chord, prev_held)] + trans_cost + emission
                    if total < best_cost:
                        best_cost = total
                        best_prev = (prev_chord, prev_held)

                dp[bar][(chord, target_held)] = best_cost
                back[bar][(chord, target_held)] = best_prev

    last_state = min(states, key=lambda state: dp[musical_bars - 1][state])
    path: list[Chord] = [last_state[0]]
    current: tuple[Chord, int] | None = last_state
    for bar in range(musical_bars - 1, 0, -1):
        if current is None:
            raise RuntimeError(f"missing Viterbi backpointer at bar {bar}")
        current = back[bar][current]
        if current is None:
            raise RuntimeError(f"missing Viterbi predecessor at bar {bar}")
        path.append(current[0])
    path.reverse()
    return tuple(path)


def plan_slots(
    regimes: tuple[Regime, ...] | tuple[Regime, Regime, Regime],
    raw_pitches: Sequence[int] | None = None,
    scale: tuple[int, ...] | None = None,
    spec: FormSpec | None = None,
    character: MovementCharacter | None = None,
    outro_override: Literal["major", "minor"] | None = None,
    mode: Literal["major", "minor"] = "major",
    home_pedal: bool = False,
    harmonic_bridge: bool = True,
    character_at: Sequence[MovementCharacter | None] | None = None,
    gap_leads: Sequence[str | None] | None = None,
) -> tuple[ChordSlot, ...]:
    if spec is None and len(regimes) != 3:
        raise ValueError("expected one regime per phrase")
    for regime in regimes:
        progression(regime)
    musical_bars = MUSICAL_BARS if spec is None else spec.bars

    if raw_pitches is None and spec is not None:
        raise ValueError("a form spec needs raw pitches")
    if raw_pitches is None:
        slots = [ChordSlot(0, 2, tonic(regimes[0]), regimes[0], "intro")]
        for phrase, start in enumerate(PHRASE_STARTS):
            for index, chord in enumerate(progression(regimes[phrase])):
                slots.append(
                    ChordSlot(start + index * 2, 2, chord, regimes[phrase], "phrase")
                )
        slots.append(
            ChordSlot(
                OUTRO_START, MUSICAL_BARS - OUTRO_START, tonic(regimes[2]), regimes[2], "outro"
            )
        )
    else:
        chords = plan_markov_chords(
            regimes,
            raw_pitches,
            scale,
            spec,
            character,
            outro_override,
            mode,
            home_pedal,
            harmonic_bridge,
            character_at,
            gap_leads,
        )
        slots = []
        spans = _section_spans(regimes) if spec is None else spec.spans(regimes)  # type: ignore[arg-type]
        for sec_start, sec_end, regime, section in spans:
            cursor = sec_start
            while cursor < sec_end:
                chord = chords[cursor]
                stop = cursor + 1
                while stop < sec_end and chords[stop] == chord:
                    stop += 1
                slots.append(ChordSlot(cursor, stop - cursor, chord, regime, section))
                cursor = stop

    covered = [bar for slot in slots for bar in slot.bars()]
    if covered != list(range(musical_bars)):
        raise RuntimeError("chord slots do not cover the form")
    return tuple(slots)

