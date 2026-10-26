"""Phase-1 machine score for one daily symphony.

The contract is `docs/sonify-machine-score.md`. This pass reads a `Score`
written in C and the candles that were rendered. It does not re-render, and
it does not decide whether a renderer change is an improvement.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

from app.sonify.chords import Chord, Regime
from app.sonify.daily_frame import BODY_START, COOL_START, PIECE_END
from app.sonify.dynamics import MARKINGS, MIN_SPAN_RATIO, average_liquidity, percentile
from app.sonify.form import DAILY_ENSEMBLE_SPEC, chord_bias, chords_for_spec, liquidity_windows_for
from app.sonify.keys import MovementCharacter, boundary_regimes, movement_character, movement_mode
from app.sonify.model import Bar, NoteEvent, Score
from app.sonify.quantize import c_major_scale, price_to_scale_index, resample
from app.sonify.regime import moving_average
from app.sonify.render import _window_candles, assign_daily_ambient_bars

Owner = Literal["high", "lead", "support"]
Bend = Literal["high", "body"]
_EIGHTHS = 8
_STRONG = (0, 4)
_BODY_BARS = range(BODY_START, COOL_START)
_FRAME_BARS = (0, 1, 32, 33)
_CATALOG = chords_for_spec(True)
_LETTER_RANK = {marking: index for index, marking in enumerate(MARKINGS)}


@dataclass(frozen=True)
class _Eighth:
    index: int
    bar: int
    eighth: int
    raw: int
    midi: int | None
    degree: int | None
    owner: Owner | None


@dataclass(frozen=True)
class Gates:
    """Contracts the daily symphony renderer holds today. `None` means the gate does not apply."""

    source_on_body: bool
    frame: bool
    narrow_span_all_mf: bool | None


@dataclass(frozen=True)
class Observations:
    character: MovementCharacter
    closing_regime: Regime
    expected_mode: str
    score_mode: str
    mode_wired: bool
    distinct_scale_degrees: int
    melody_span: int | None


@dataclass(frozen=True)
class Fidelity:
    f1: float | None
    f2: float | None
    f3_lead_support: float | None
    f3_high: float | None
    f4: float | None
    f5: float | None
    f6: float


@dataclass(frozen=True)
class Legality:
    m1_lead_support: float | None
    m1_high: float | None
    m1_lead_support_holds: bool
    m2_bass_octave_leaps: int
    m2_melody_unresolved_leaps: int
    m2_parallel_fifths: int
    m3_mean_common: float | None
    m3_zero_common_rate: float | None
    m4_bigram_entropy: float
    m4_longest_chord: int
    m4_liquidity_letters: int
    m5_frame: bool


@dataclass(frozen=True)
class Stratum:
    variant: str
    span: str
    character: MovementCharacter
    distinct_scale_degrees: int
    melody_span: int | None
    volume_span_ratio: float | None
    high_eighths: int
    planner_character: MovementCharacter | None


@dataclass(frozen=True)
class PriceReversed:
    f1: float | None
    f5: float | None


@dataclass(frozen=True)
class VolumeReversed:
    f5: float | None


@dataclass(frozen=True)
class RegimeShuffled:
    """`f6` is omitted when the shuffle does not change any bar's label."""

    f6: float | None
    labels_changed: bool


@dataclass(frozen=True)
class PitchesPermuted:
    f1: float | None
    m1_lead_support: float | None


@dataclass(frozen=True)
class Controls:
    price_reversed: PriceReversed
    volume_reversed: VolumeReversed
    regime_shuffled: RegimeShuffled
    pitches_permuted: PitchesPermuted


@dataclass(frozen=True)
class DailyRecord:
    gates: Gates
    observations: Observations
    fidelity: Fidelity
    legality: Legality
    stratum: Stratum
    controls: Controls

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def measure_daily(
    bars: Sequence[Bar],
    score: Score,
    *,
    planner_character: MovementCharacter | None = None,
    price_low: float | None = None,
    price_high: float | None = None,
    source_groups: list[list[int]] | None = None,
) -> DailyRecord:
    """Score one rendered daily symphony against the candles it was built from.

    `planner_character`, `price_low`, `price_high`, and `source_groups` are the
    values passed to `render`. None of them is stored on `Score`. The defaults
    match `render(bars)`. F6 prices chords with `planner_character`, so a score
    rendered with another character is mis-priced until that argument is repeated.
    The stratum character is `movement_character` of the closes, which the daily
    renderer does not read.
    """
    if score.variant != "symphony" or score.bars != PIECE_END or score.beats != 4:
        raise ValueError("phase 1 measures a 34-bar daily symphony in 4/4")
    if not bars:
        raise ValueError("need at least one price bar")

    groups = source_groups if source_groups is not None else assign_daily_ambient_bars(len(bars))
    if len(groups) != PIECE_END:
        raise ValueError(f"expected {PIECE_END} source groups, got {len(groups)}")
    low, high = _price_bounds(bars, price_low, price_high)
    raw = _raw_degrees(bars, groups, low, high)
    line = _stitch(score, raw)
    windows = liquidity_windows_for(DAILY_ENSEMBLE_SPEC)
    if len(windows) != len(score.liquidity):
        raise ValueError(
            f"liquidity has {len(score.liquidity)} bands for {len(windows)} windows"
        )
    candle_lists = [
        _window_candles(list(bars), groups, start, length) for start, length in windows
    ]
    volumes = average_liquidity(candle_lists)
    body = [
        (volume, marking)
        for (start, length), volume, marking in zip(windows, volumes, score.liquidity)
        if start >= BODY_START and start + length <= COOL_START
    ]
    body_volumes = [volume for volume, _marking in body]
    body_letters = [marking for _volume, marking in body]
    span_ratio = _span_ratio(volumes)
    distinct = len(set(raw))
    market = _market(bars)
    chords = [_slot(score, bar).chord for bar in _BODY_BARS]
    regimes = [_slot(score, bar).regime for bar in _BODY_BARS]
    by_bar = {bar: chord for bar, chord in zip(_BODY_BARS, chords)}
    fidelity = _fidelity(
        line, distinct, body_volumes, body_letters, chords, regimes, planner_character
    )
    legality = _legality(score, line, chords, body_letters, by_bar)
    gates = Gates(
        source_on_body=_source_on_body(groups),
        frame=legality.m5_frame,
        narrow_span_all_mf=_narrow_span_gate(span_ratio, body_volumes, body_letters),
    )
    melody_span = _melody_span(line)
    observations = Observations(
        character=market[0],
        closing_regime=market[1],
        expected_mode=market[2],
        score_mode=score.mode,
        mode_wired=score.mode == market[2],
        distinct_scale_degrees=distinct,
        melody_span=melody_span,
    )
    stratum = Stratum(
        variant=score.variant,
        span="1D",
        character=market[0],
        distinct_scale_degrees=distinct,
        melody_span=melody_span,
        volume_span_ratio=span_ratio,
        high_eighths=sum(1 for step in line if step.owner == "high"),
        planner_character=planner_character,
    )
    controls = _controls(
        bars,
        groups,
        low,
        high,
        line,
        fidelity.f5,
        windows,
        score.liquidity,
        chords,
        regimes,
        planner_character,
        distinct,
        by_bar,
    )
    return DailyRecord(gates, observations, fidelity, legality, stratum, controls)


def regime_lift(
    chords: Sequence[Chord],
    regimes: Sequence[Regime],
    character: MovementCharacter | None,
) -> float:
    """Catalog cost minus chosen cost. Positive when the chosen chords are cheaper."""
    if len(chords) != len(regimes) or not chords:
        raise ValueError("each body bar needs a chord and a regime")
    chosen = 0.0
    catalog = 0.0
    for chord, regime in zip(chords, regimes):
        chosen += chord_bias(chord, regime, character)
        catalog += sum(chord_bias(item, regime, character) for item in _CATALOG) / len(_CATALOG)
    count = len(chords)
    return catalog / count - chosen / count


def _fidelity(
    line: Sequence[_Eighth],
    distinct: int,
    volumes: Sequence[float],
    letters: Sequence[str],
    chords: Sequence[Chord],
    regimes: Sequence[Regime],
    character: MovementCharacter | None,
) -> Fidelity:
    contour = distinct >= 3
    return Fidelity(
        f1=_direction(line) if contour else None,
        f2=_level(line) if contour else None,
        f3_lead_support=_bend(line, "body"),
        f3_high=_bend(line, "high"),
        f4=_turns(line) if contour else None,
        f5=_liquidity(volumes, letters),
        f6=regime_lift(chords, regimes, character),
    )


def _controls(
    bars: Sequence[Bar],
    groups: list[list[int]],
    low: float,
    high: float,
    line: Sequence[_Eighth],
    f5: float | None,
    windows: Sequence[tuple[int, int]],
    letters: Sequence[str],
    chords: Sequence[Chord],
    regimes: Sequence[Regime],
    character: MovementCharacter | None,
    distinct: int,
    by_bar: dict[int, Chord],
) -> Controls:
    reversed_closes = [
        Bar(bars[len(bars) - 1 - index].close, bar.volume, bar.ma20, bar.auction)
        for index, bar in enumerate(bars)
    ]
    reversed_raw = _raw_degrees(reversed_closes, groups, low, high)
    reversed_line = tuple(
        _Eighth(step.index, step.bar, step.eighth, raw, step.midi, step.degree, step.owner)
        for step, raw in zip(line, reversed_raw)
    )
    reversed_volumes = _reversed_volumes(bars)
    volume_values = average_liquidity(
        [
            _window_candles(reversed_volumes, groups, start, length)
            for start, length in windows
        ]
    )
    body_volumes = [
        volume
        for (start, length), volume in zip(windows, volume_values)
        if start >= BODY_START and start + length <= COOL_START
    ]
    body_letters = [
        marking
        for (start, length), marking in zip(windows, letters)
        if start >= BODY_START and start + length <= COOL_START
    ]
    shuffled, labels_changed = _shuffle_regimes(regimes)
    permuted = _permute_pitches(line)
    return Controls(
        price_reversed=PriceReversed(
            f1=_direction(reversed_line) if len(set(reversed_raw)) >= 3 else None,
            f5=f5,
        ),
        volume_reversed=VolumeReversed(f5=_liquidity(body_volumes, body_letters)),
        regime_shuffled=RegimeShuffled(
            f6=regime_lift(chords, shuffled, character) if labels_changed else None,
            labels_changed=labels_changed,
        ),
        pitches_permuted=PitchesPermuted(
            f1=_direction(permuted) if distinct >= 3 else None,
            m1_lead_support=_chord_tone_rate(permuted, "body", by_bar),
        ),
    )


def _reversed_volumes(bars: Sequence[Bar]) -> list[Bar]:
    """Reverse volume and the auction flag together. The flag decides which print is dropped."""
    last = len(bars) - 1
    return [
        Bar(bar.close, bars[last - index].volume, bar.ma20, bars[last - index].auction)
        for index, bar in enumerate(bars)
    ]


def _shuffle_regimes(regimes: Sequence[Regime]) -> tuple[list[Regime], bool]:
    """Permute labels. A one-regime body cannot be permuted, so the control is skipped."""
    original = list(regimes)
    if len(set(original)) < 2:
        return original, False
    shuffled = original.copy()
    random.Random(0).shuffle(shuffled)
    if shuffled == original:
        shuffled = original[1:] + original[:1]
    return shuffled, True


def _permute_pitches(line: Sequence[_Eighth]) -> tuple[_Eighth, ...]:
    """Shuffle sounding pitches. Rests and ownership stay put."""
    sounding = [step.midi for step in line if step.midi is not None]
    random.Random(1).shuffle(sounding)
    scale = c_major_scale()
    cursor = 0
    out: list[_Eighth] = []
    for step in line:
        if step.midi is None:
            out.append(step)
            continue
        midi = sounding[cursor]
        cursor += 1
        out.append(
            _Eighth(
                step.index,
                step.bar,
                step.eighth,
                step.raw,
                midi,
                _degree(midi, scale),
                step.owner,
            )
        )
    return tuple(out)


def _direction(line: Sequence[_Eighth]) -> float | None:
    """Share of steps whose raw degree and written degree move the same way."""
    agree = 0
    total = 0
    for left, right in zip(line, line[1:]):
        if left.degree is None or right.degree is None:
            continue
        raw_step = right.raw - left.raw
        if raw_step == 0:
            continue
        total += 1
        written = right.degree - left.degree
        if (raw_step > 0 and written > 0) or (raw_step < 0 and written < 0):
            agree += 1
    if total == 0:
        return None
    return agree / total


def _level(line: Sequence[_Eighth]) -> float | None:
    raw: list[float] = []
    written: list[float] = []
    for step in line:
        if step.eighth not in _STRONG or step.owner not in ("lead", "support") or step.degree is None:
            continue
        raw.append(float(step.raw))
        written.append(float(step.degree))
    return _spearman(raw, written)


def _bend(line: Sequence[_Eighth], which: Bend) -> float | None:
    gaps: list[int] = []
    for step in line:
        if step.eighth not in _STRONG or step.degree is None:
            continue
        owned = step.owner == "high" if which == "high" else step.owner in ("lead", "support")
        if owned:
            gaps.append(abs(step.degree - step.raw))
    if not gaps:
        return None
    return sum(gaps) / len(gaps)


def _turns(line: Sequence[_Eighth]) -> float | None:
    raw = _extrema([step.raw for step in line])
    if not raw:
        return None
    written = _extrema([step.degree for step in line])
    hits = 0
    for index, kind in raw:
        bar = line[index].bar
        if any(other == kind and abs(line[place].bar - bar) <= 1 for place, other in written):
            hits += 1
    return hits / len(raw)


def _extrema(values: Sequence[int | None]) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    index = 0
    size = len(values)
    while index < size:
        if values[index] is None:
            index += 1
            continue
        end = index
        while end + 1 < size and values[end + 1] == values[index]:
            end += 1
        left = values[index - 1] if index > 0 else None
        right = values[end + 1] if end + 1 < size else None
        if left is not None and right is not None:
            height = values[index]
            assert height is not None
            if left <= height - 1 and right <= height - 1:
                found.append((index, "peak"))
            elif left >= height + 1 and right >= height + 1:
                found.append((index, "valley"))
        index = end + 1
    return found


def _liquidity(volumes: Sequence[float], letters: Sequence[str]) -> float | None:
    if len(volumes) != len(letters) or len(letters) < 2 or len(set(letters)) < 2:
        return None
    ranks = [float(_LETTER_RANK[letter]) for letter in letters]
    return _spearman([float(volume) for volume in volumes], ranks)


def _legality(
    score: Score,
    line: Sequence[_Eighth],
    chords: Sequence[Chord],
    letters: Sequence[str],
    by_bar: dict[int, Chord],
) -> Legality:
    lead_rate = _chord_tone_rate(line, "body", by_bar)
    common = _common_tones(chords)
    frame = _frame_holds(score)
    return Legality(
        m1_lead_support=lead_rate,
        m1_high=_chord_tone_rate(line, "high", by_bar),
        m1_lead_support_holds=lead_rate is None or lead_rate == 1.0,
        m2_bass_octave_leaps=_bass_leaps(score),
        m2_melody_unresolved_leaps=_unresolved_leaps(line),
        m2_parallel_fifths=_parallel_fifths(score, line),
        m3_mean_common=common[0],
        m3_zero_common_rate=common[1],
        m4_bigram_entropy=_bigram_entropy(line),
        m4_longest_chord=_longest_run(chords),
        m4_liquidity_letters=len(set(letters)),
        m5_frame=frame,
    )


def _chord_tone_rate(
    line: Sequence[_Eighth], which: Bend, by_bar: dict[int, Chord]
) -> float | None:
    hits = 0
    total = 0
    for step in line:
        if step.eighth not in _STRONG or step.midi is None:
            continue
        owned = step.owner == "high" if which == "high" else step.owner in ("lead", "support")
        if not owned:
            continue
        total += 1
        if step.midi % 12 in by_bar[step.bar].pitch_classes:
            hits += 1
    if total == 0:
        return None
    return hits / total


def _frame_holds(score: Score) -> bool:
    for events in (score.lead_dynamics, score.support_dynamics, score.dynamics):
        opening = [event for event in events if event.bar == 0 and event.beat == 0.0]
        closing = [event for event in events if event.bar == PIECE_END - 1]
        if not opening or any(event.marking != "p" for event in opening):
            return False
        if not any(event.marking == "ppp" for event in closing):
            return False
    for bar in _FRAME_BARS:
        root = _slot(score, bar).chord.pitches[0] % 12
        sounding = [
            note.midi
            for notes in (score.lead, score.support, score.low)
            for note in notes
            if note.bar == bar and note.midi is not None
        ]
        if not sounding or any(midi % 12 != root for midi in sounding):
            return False
    return True


def _bass_leaps(score: Score) -> int:
    sounding: dict[int, int] = {}
    for note in score.low:
        if note.midi is None or note.bar < BODY_START or note.bar >= COOL_START:
            continue
        start = _onset(note)
        current = sounding.get(start)
        if current is None or note.midi < current:
            sounding[start] = note.midi
    ordered = [sounding[start] for start in sorted(sounding)]
    return sum(1 for left, right in zip(ordered, ordered[1:]) if abs(right - left) > 12)


def _unresolved_leaps(line: Sequence[_Eighth]) -> int:
    intervals: list[int] = []
    previous: int | None = None
    for step in line:
        if step.midi is None:
            previous = None
            continue
        if previous is not None and step.midi != previous:
            intervals.append(step.midi - previous)
        previous = step.midi
    unresolved = 0
    for index, interval in enumerate(intervals):
        if abs(interval) <= 12:
            continue
        following = intervals[index + 1] if index + 1 < len(intervals) else 0
        if following == 0 or (following > 0) == (interval > 0):
            unresolved += 1
    return unresolved


def _parallel_fifths(score: Score, line: Sequence[_Eighth]) -> int:
    bass = _bass_at(score)
    strong = [step for step in line if step.eighth in _STRONG]
    pairs = 0
    for left, right in zip(strong, strong[1:]):
        left_bass = bass.get(left.index)
        right_bass = bass.get(right.index)
        if left.midi is None or right.midi is None or left_bass is None or right_bass is None:
            continue
        melody_step = right.midi - left.midi
        bass_step = right_bass - left_bass
        if melody_step == 0 or bass_step == 0 or (melody_step > 0) != (bass_step > 0):
            continue
        if (left.midi - left_bass) % 12 != 7 or (right.midi - right_bass) % 12 != 7:
            continue
        pairs += 1
    return pairs


def _bass_at(score: Score) -> dict[int, int]:
    sounding: dict[int, int] = {}
    origin = BODY_START * _EIGHTHS
    for note in score.low:
        if note.midi is None:
            continue
        start, end = _span(note)
        for eighth in range(start, end):
            if eighth < origin or eighth >= COOL_START * _EIGHTHS:
                continue
            index = eighth - origin
            current = sounding.get(index)
            if current is None or note.midi < current:
                sounding[index] = note.midi
    return sounding


def _common_tones(chords: Sequence[Chord]) -> tuple[float | None, float | None]:
    shared: list[int] = []
    for left, right in zip(chords, chords[1:]):
        if left == right:
            continue
        shared.append(len(left.pitch_classes & right.pitch_classes))
    if not shared:
        return None, None
    return sum(shared) / len(shared), sum(1 for count in shared if count == 0) / len(shared)


def _bigram_entropy(line: Sequence[_Eighth]) -> float:
    bigrams: list[tuple[int, int]] = []
    for left, right in zip(line, line[1:]):
        if left.midi is None or right.midi is None:
            continue
        bigrams.append((left.midi % 12, right.midi % 12))
    if not bigrams:
        return 0.0
    counts = Counter(bigrams)
    total = len(bigrams)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _longest_run(chords: Sequence[Chord]) -> int:
    longest = 1
    run = 1
    for left, right in zip(chords, chords[1:]):
        if left == right:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return longest


def _narrow_span_gate(
    span_ratio: float | None, volumes: Sequence[float], letters: Sequence[str]
) -> bool | None:
    if span_ratio is None or span_ratio >= MIN_SPAN_RATIO or any(volume <= 0 for volume in volumes):
        return None
    return all(letter == "mf" for letter in letters)


def _span_ratio(volumes: Sequence[float]) -> float | None:
    traded = [volume for volume in volumes if volume > 0]
    if not traded:
        return None
    low = percentile(traded, 0.10)
    high = percentile(traded, 0.90)
    if low <= 0 or high <= 0:
        return None
    return high / low


def _source_on_body(groups: Sequence[Sequence[int]]) -> bool:
    if any(groups[bar] for bar in (0, 1, 32, 33)):
        return False
    seen = [index for bar in _BODY_BARS for index in groups[bar]]
    return seen == list(range(len(seen))) and len(seen) == sum(len(group) for group in groups)


def _market(bars: Sequence[Bar]) -> tuple[MovementCharacter, Regime, str]:
    closes = [bar.close for bar in bars]
    averages = [bar.ma20 for bar in bars]
    if any(average is None for average in averages):
        computed = moving_average(closes)
        averages = [
            bar.ma20 if bar.ma20 is not None else computed[index] for index, bar in enumerate(bars)
        ]
    _opening, closing = boundary_regimes(closes, averages)
    character = movement_character(closes, "1D")
    return character, closing, movement_mode(character, closing)


def _price_bounds(
    bars: Sequence[Bar], price_low: float | None, price_high: float | None
) -> tuple[float, float]:
    closes = [bar.close for bar in bars]
    low = min(closes) if price_low is None else price_low
    high = max(closes) if price_high is None else price_high
    return low, high


def _raw_degrees(
    bars: Sequence[Bar], groups: Sequence[Sequence[int]], low: float, high: float
) -> list[int]:
    scale = c_major_scale()
    held = bars[0].close
    raw: list[int] = []
    for bar in _BODY_BARS:
        group = groups[bar]
        if group:
            closes = [bars[index].close for index in group]
            held = closes[-1]
        else:
            closes = [held]
        for close in resample(closes, _EIGHTHS):
            raw.append(price_to_scale_index(close, low, high, len(scale)))
    return raw


def _stitch(score: Score, raw: Sequence[int]) -> tuple[_Eighth, ...]:
    scale = c_major_scale()
    origin = BODY_START * _EIGHTHS
    out: list[_Eighth] = []
    for offset, degree in enumerate(raw):
        eighth = origin + offset
        high = _covering(score.high, eighth)
        lead = _covering(score.lead, eighth)
        support = _covering(score.support, eighth)
        owner, note = _owner(high, lead, support)
        midi = None if note is None else note.midi
        out.append(
            _Eighth(
                offset,
                BODY_START + offset // _EIGHTHS,
                offset % _EIGHTHS,
                degree,
                midi,
                None if midi is None else _degree(midi, scale),
                owner,
            )
        )
    return tuple(out)


def _owner(
    high: NoteEvent | None, lead: NoteEvent | None, support: NoteEvent | None
) -> tuple[Owner | None, NoteEvent | None]:
    if high is not None:
        return "high", high
    if lead is not None and support is not None:
        if _onset(lead) >= _onset(support):
            return "lead", lead
        return "support", support
    if lead is not None:
        return "lead", lead
    if support is not None:
        return "support", support
    return None, None


def _covering(notes: Sequence[NoteEvent], eighth: int) -> NoteEvent | None:
    found: NoteEvent | None = None
    found_at = -1
    for note in notes:
        if note.midi is None:
            continue
        start, end = _span(note)
        if start <= eighth < end and start >= found_at:
            found = note
            found_at = start
    return found


def _onset(note: NoteEvent) -> int:
    return _span(note)[0]


def _span(note: NoteEvent) -> tuple[int, int]:
    start = note.bar * _EIGHTHS + int(round(note.beat * 2))
    length = int(round(note.duration_beats * 2))
    return start, start + max(length, 0)


def _degree(midi: int, scale: tuple[int, ...]) -> int | None:
    classes = {note % 12 for note in scale}
    if midi % 12 not in classes:
        return None
    table = {note: index for index, note in enumerate(scale)}
    if midi in table:
        return table[midi]
    origin = scale[0]
    step = 1 if midi > origin else -1
    cursor = origin
    index = 0
    for _ in range(128):
        if cursor == midi:
            return index
        cursor += step
        if cursor % 12 in classes:
            index += step
    return None


def _slot(score: Score, bar: int):
    for slot in score.slots:
        if slot.start <= bar < slot.start + slot.length:
            return slot
    raise ValueError(f"bar {bar} has no chord")


def _melody_span(line: Sequence[_Eighth]) -> int | None:
    degrees = [step.degree for step in line if step.degree is not None]
    if not degrees:
        return None
    return max(degrees) - min(degrees)


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    return _pearson(_ranks(left), _ranks(right))


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor
        while end + 1 < len(order) and values[order[end + 1]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end) / 2 + 1
        for index in range(cursor, end + 1):
            ranks[order[index]] = rank
        cursor = end + 1
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    size = len(left)
    mean_left = sum(left) / size
    mean_right = sum(right) / size
    covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    left_scale = math.sqrt(sum((a - mean_left) ** 2 for a in left))
    right_scale = math.sqrt(sum((b - mean_right) ** 2 for b in right))
    if left_scale == 0 or right_scale == 0:
        return None
    return covariance / (left_scale * right_scale)
