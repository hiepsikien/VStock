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
from dataclasses import dataclass
from typing import Literal

from app.sonify.chords import (
    CHORDS,
    REGIME_BIAS,
    Chord,
    Regime,
    progression,
    tonic,
    tonic_chords,
    transition_probability,
)
from app.sonify.quantize import bar_quantization_loss, c_major_scale, quantize_chord_tone

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
SAME_ROOT_QUALITY_CHANGE_PENALTY = 0.35
PEDAL_STAY_COST = 0.0
PHRASE_TONIC_BONUS = 0.25
CROSS_BAR_BREAK_PENALTY = 1.2

Section = Literal["intro", "phrase", "outro"]


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


def _prev_last_touched_strong(raw_pitches: Sequence[int], bar: int) -> bool:
    """Whether the final eighth of `bar - 1` belongs to a run that touches a strong beat.

    Matches `quantize_strong_beats`: the eighth at `bar * 8 - 1` is snapped to
    `prev_chord` only when its run reaches strong beat 4 of `bar - 1` (all eighths
    4..7 of `bar - 1` share that pitch) or continues onto strong beat 0 of `bar`
    (`held_across`). Otherwise it is a weak-beat passing note and keeps its raw pitch.
    """
    prev_last = raw_pitches[bar * EIGHTHS_PER_BAR - 1]
    if prev_last == raw_pitches[bar * EIGHTHS_PER_BAR]:
        return True
    prev_bar_start = (bar - 1) * EIGHTHS_PER_BAR
    return all(raw_pitches[prev_bar_start + e] == prev_last for e in range(4, EIGHTHS_PER_BAR))


def _breaks_held_note_across_barline(
    boundary_pitch: int,
    prev_chord: Chord,
    curr_chord: Chord,
    scale: tuple[int, ...],
    index_of: dict[int, int],
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
    common = prev_chord.pitch_classes & curr_chord.pitch_classes
    if common:
        snapped_common = quantize_chord_tone(boundary_pitch, common, scale)
        if abs(index_of[snapped_common] - index_of[boundary_pitch]) <= 1:
            return False
    prev_snapped = quantize_chord_tone(boundary_pitch, prev_chord.pitch_classes, scale)
    curr_snapped = quantize_chord_tone(boundary_pitch, curr_chord.pitch_classes, scale)
    return prev_snapped != curr_snapped


def plan_markov_chords(
    regimes: tuple[Regime, Regime, Regime],
    raw_pitches: Sequence[int],
    scale: tuple[int, ...] | None = None,
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
    if len(regimes) != 3:
        raise ValueError("expected one regime per phrase")
    for regime in regimes:
        progression(regime)
    expected_eighths = MUSICAL_BARS * EIGHTHS_PER_BAR
    if len(raw_pitches) != expected_eighths:
        raise ValueError(f"expected {expected_eighths} eighth-note pitches, got {len(raw_pitches)}")
    active_scale = c_major_scale() if scale is None else scale
    index_of = {note: index for index, note in enumerate(active_scale)}

    bar_regime: list[Regime] = []
    bar_section: list[Section] = []
    for start, end, regime, section in _section_spans(regimes):
        bar_regime.extend([regime] * (end - start))
        bar_section.extend([section] * (end - start))

    states = [(chord, held) for chord in CHORDS for held in (1, 2)]
    dp: list[dict[tuple[Chord, int], float]] = [{} for _ in range(MUSICAL_BARS)]
    back: list[dict[tuple[Chord, int], tuple[Chord, int] | None]] = [
        {} for _ in range(MUSICAL_BARS)
    ]

    for bar in range(MUSICAL_BARS):
        bar_notes = raw_pitches[bar * EIGHTHS_PER_BAR : (bar + 1) * EIGHTHS_PER_BAR]
        regime = bar_regime[bar]
        section = bar_section[bar]
        bias = REGIME_BIAS[regime]
        allowed_tonics = tonic_chords(regime)
        new_section = bar in SECTION_STARTS
        previous_pitch = raw_pitches[bar * EIGHTHS_PER_BAR - 1] if bar > 0 else None

        for chord in CHORDS:
            if section in ("intro", "outro") and chord not in allowed_tonics:
                dp[bar][(chord, 1)] = float("inf")
                dp[bar][(chord, 2)] = float("inf")
                back[bar][(chord, 1)] = None
                back[bar][(chord, 2)] = None
                continue

            base_bias = bias[chord]
            if bar in PHRASE_STARTS and chord in allowed_tonics:
                base_bias -= PHRASE_TONIC_BONUS

            if bar == 0:
                emission = (
                    bar_quantization_loss(bar_notes, chord.pitch_classes, active_scale)
                    + base_bias
                )
                dp[0][(chord, 1)] = emission
                back[0][(chord, 1)] = None
                dp[0][(chord, 2)] = float("inf")
                back[0][(chord, 2)] = None
                continue

            # Two equal adjacent eighth-note pitches across the barline form a single
            # held Run in `runs_of(raw_pitches, ...)`.
            held_across = raw_pitches[bar * EIGHTHS_PER_BAR - 1] == raw_pitches[bar * EIGHTHS_PER_BAR]
            boundary_pitch = raw_pitches[bar * EIGHTHS_PER_BAR]
            if previous_pitch is None:
                raise RuntimeError("expected previous_pitch for bar > 0")
            prev_last_touched_strong = _prev_last_touched_strong(raw_pitches, bar)
            if not prev_last_touched_strong or bar_notes[0] % 12 in chord.pitch_classes:
                uniform_emission = (
                    bar_quantization_loss(
                        bar_notes,
                        chord.pitch_classes,
                        active_scale,
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
                    for prev_chord in CHORDS
                }
                emission_by_prev_snapped = {
                    snapped_val: (
                        bar_quantization_loss(
                            bar_notes,
                            chord.pitch_classes,
                            active_scale,
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
                    if section in ("intro", "outro") and not new_section and prev_chord != chord:
                        continue
                    same_root = prev_chord.root_step == chord.root_step
                    if new_section:
                        if target_held != 1:
                            continue
                    elif same_root:
                        if target_held != 2:
                            continue
                    elif target_held != 1:
                        continue

                    prob = transition_probability(prev_chord, chord)
                    if prob <= 0.0:
                        continue

                    # Each root's probability mass is split equally across its triad and
                    # seventh chord, so `prob * 2.0` recovers the root-to-root transition probability.
                    root_prob = prob * 2.0
                    if not new_section and same_root:
                        if section in ("intro", "outro"):
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
                            trans_cost += SINGLE_BAR_CHANGE_PENALTY
                    if same_root and prev_chord != chord:
                        trans_cost += SAME_ROOT_QUALITY_CHANGE_PENALTY

                    if held_across and _breaks_held_note_across_barline(
                        boundary_pitch, prev_chord, chord, active_scale, index_of
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

    last_state = min(states, key=lambda state: dp[MUSICAL_BARS - 1][state])
    path: list[Chord] = [last_state[0]]
    current: tuple[Chord, int] | None = last_state
    for bar in range(MUSICAL_BARS - 1, 0, -1):
        if current is None:
            raise RuntimeError(f"missing Viterbi backpointer at bar {bar}")
        current = back[bar][current]
        if current is None:
            raise RuntimeError(f"missing Viterbi predecessor at bar {bar}")
        path.append(current[0])
    path.reverse()
    return tuple(path)


def plan_slots(
    regimes: tuple[Regime, Regime, Regime],
    raw_pitches: Sequence[int] | None = None,
    scale: tuple[int, ...] | None = None,
) -> tuple[ChordSlot, ...]:
    if len(regimes) != 3:
        raise ValueError("expected one regime per phrase")
    for regime in regimes:
        progression(regime)

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
        chords = plan_markov_chords(regimes, raw_pitches, scale)
        slots = []
        for sec_start, sec_end, regime, section in _section_spans(regimes):
            cursor = sec_start
            while cursor < sec_end:
                chord = chords[cursor]
                stop = cursor + 1
                while stop < sec_end and chords[stop] == chord:
                    stop += 1
                slots.append(ChordSlot(cursor, stop - cursor, chord, regime, section))
                cursor = stop

    covered = [bar for slot in slots for bar in slot.bars()]
    if covered != list(range(MUSICAL_BARS)):
        raise RuntimeError("chord slots do not cover the 30-bar form")
    return tuple(slots)

