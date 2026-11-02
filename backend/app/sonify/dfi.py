"""DFI — Data Fidelity Index.

The index answers one question: how faithfully does a sonified piece reflect
its source data?  The first dataset is the stock price line plus volume; the
metric is not tied to stocks, and the same components apply to any ordered
series.  It is deliberately not a score for musical quality.

The metric reads the writer's own `price_trace`, the resampled close series,
and the liquidity windows that were already used to compose the score.  It
never guesses the price note from "the highest sounding note": guitar thumb
cantabile, Bach preludes, and Ambient holds all put the line somewhere else.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, replace
from statistics import median
from typing import Iterable, Literal, Sequence

from app.sonify.model import NoteEvent, PriceTracePoint, Score

DFI_VERSION = "3"

WEIGHT_SHAPE = 0.33
WEIGHT_MOTION = 0.21
WEIGHT_STRUCTURE = 0.19
WEIGHT_RESOLUTION = 0.17
WEIGHT_VOLUME = 0.10

# Talk about the musical grid with a clear unit: one quarter beat is two
# eighths regardless of meter.
_EPS = 1e-9


@dataclass(frozen=True)
class DfiBreakdown:
    score: float
    band: Literal["very-clear", "clear", "fair", "faint", "very-faint"]
    shape: float | None
    motion: float | None
    structure: float | None
    resolution: float | None
    volume: float | None
    coverage: float
    coverage_detail: float | None
    opportunity: float
    confidence: Literal["low", "medium", "high"]
    n_moves: int
    n_sounding: int
    version: str = DFI_VERSION

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "band": self.band,
            "shape": None if self.shape is None else round(self.shape, 4),
            "motion": None if self.motion is None else round(self.motion, 4),
            "structure": None if self.structure is None else round(self.structure, 4),
            "resolution": None if self.resolution is None else round(self.resolution, 4),
            "volume": None if self.volume is None else round(self.volume, 4),
            "coverage": round(self.coverage, 4),
            "coverage_detail": (
                None if self.coverage_detail is None else round(self.coverage_detail, 4)
            ),
            "opportunity": round(self.opportunity, 4),
            "confidence": self.confidence,
            "n_moves": self.n_moves,
            "n_sounding": self.n_sounding,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "DfiBreakdown | None":
        try:
            return cls(
                score=float(payload["score"]),
                band=payload["band"],
                shape=_optional_float(payload.get("shape")),
                motion=_optional_float(payload.get("motion")),
                structure=_optional_float(payload.get("structure")),
                resolution=_optional_float(payload.get("resolution")),
                volume=_optional_float(payload.get("volume")),
                coverage=float(payload["coverage"]),
                coverage_detail=_optional_float(payload.get("coverage_detail")),
                opportunity=float(payload.get("opportunity") or 0.0),
                confidence=payload.get("confidence", "low"),
                n_moves=int(payload.get("n_moves") or 0),
                n_sounding=int(payload.get("n_sounding") or 0),
                version=str(payload.get("version") or DFI_VERSION),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


# ---------------------------------------------------------------------------
# Trace builders


def _event_eighth(event: NoteEvent, epb: int) -> int | None:
    """Nearest eighth, or None when the note sits off the eighth grid.

    Guitar preludes write passing sixteenths between price notes.  Those are
    ornaments, not a second price reading, so they must not enter the trace.
    """
    grid = event.beat * 2.0
    if abs(grid - round(grid)) > 0.01:
        return None
    return event.bar * epb + int(round(grid))


def trace_from_notes(
    notes: Iterable[NoteEvent],
    *,
    line: Sequence[int],
    prices: Sequence[float],
    epb: int,
    bar_beats: float,
    frame_bars: frozenset[int] = frozenset(),
    role: Literal["attack", "anchor"] = "attack",
    octave_tolerant: bool = False,
    max_octaves: int = 3,
    voice: str = "lead",
) -> tuple[PriceTracePoint, ...]:
    """Match the notes that actually carry `line` at their attack.

    `line` is the price pitch for every eighth.  Guitar passes its *placed*
    melody (after octave shifts and compression); Symphony and Jazz pass the
    quantized line, with octave tolerance because Jazz transposes whole
    phrases.  A held note stays one trace point: its duration tells Coverage
    that the line is still sounding and tells Shape/Motion that the pitch did
    not move while price did.
    """
    found: list[PriceTracePoint] = []
    index_by_key: dict[tuple[int, float], int] = {}
    open_ties: dict[int, int] = {}
    for note in notes:
        if note.midi is None:
            continue
        if note.bar in frame_bars:
            continue
        if note.tie_stop and note.midi in open_ties:
            index = open_ties[note.midi]
            previous = found[index]
            found[index] = replace(
                previous,
                duration_beats=previous.duration_beats + max(note.duration_beats, 0.01),
            )
            if not note.tie_start:
                open_ties.pop(note.midi, None)
            continue
        eighth = _event_eighth(note, epb)
        if eighth is None or eighth < 0 or eighth >= len(line):
            continue
        target = line[eighth]
        diff = note.midi - target
        matches = diff == 0
        if not matches and octave_tolerant:
            matches = diff % 12 == 0 and abs(diff) <= 12 * max_octaves and diff != 0
        if not matches:
            continue
        price = prices[eighth] if eighth < len(prices) else 0.0
        point = PriceTracePoint(
            bar=note.bar,
            beat=note.beat,
            duration_beats=max(note.duration_beats, 0.01),
            price=price,
            pitch=float(note.midi),
            role=role,
            voice=voice,
        )
        key = (note.bar, round(note.beat, 4))
        if key in index_by_key:
            index = index_by_key[key]
            if abs(diff) < abs(found[index].pitch - target):  # type: ignore[operator]
                found[index] = point
        else:
            index_by_key[key] = len(found)
            found.append(point)
        if note.tie_start:
            open_ties[note.midi] = index_by_key[key]
    return tuple(sorted(found, key=lambda point: (point.bar, point.beat)))


def trace_register_per_bar(
    notes: Iterable[NoteEvent],
    *,
    prices: Sequence[float],
    epb: int,
    bar_beats: float,
    frame_bars: frozenset[int] = frozenset(),
) -> tuple[PriceTracePoint, ...]:
    """Minimalist encodes price as the arpeggio register, not as one pitch."""
    points: list[PriceTracePoint] = []
    by_bar: dict[int, list[NoteEvent]] = {}
    for note in notes:
        if note.midi is None or note.bar in frame_bars:
            continue
        by_bar.setdefault(note.bar, []).append(note)
    for bar in sorted(by_bar):
        events = by_bar[bar]
        weight = sum(max(event.duration_beats, 0.01) for event in events)
        if weight <= 0:
            continue
        centroid = sum(event.midi * max(event.duration_beats, 0.01) for event in events) / weight
        start = bar * epb
        chunk = list(prices[start : start + epb])
        price = sum(chunk) / len(chunk) if chunk else 0.0
        points.append(
            PriceTracePoint(
                bar=bar,
                beat=0.0,
                duration_beats=bar_beats,
                price=price,
                pitch=centroid,
                role="register",
                voice="lead",
            )
        )
    return tuple(points)


# ---------------------------------------------------------------------------
# Statistics


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        rank = (index + end - 1) / 2.0 + 1.0
        for position in range(index, end):
            ranks[order[position]] = rank
        index = end
    return ranks


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = len(x)
    if n < 2:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    var_x = sum((a - mean_x) ** 2 for a in x)
    var_y = sum((b - mean_y) ** 2 for b in y)
    if var_x <= _EPS or var_y <= _EPS:
        return None
    return cov / math.sqrt(var_x * var_y)


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    return _pearson(_average_ranks(x), _average_ranks(y))


def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = len(x)
    if n < 2:
        return None
    concordant = discordant = tie_x = tie_y = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = x[i] - x[j]
            dy = y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tie_x += 1
            elif dy == 0:
                tie_y += 1
            elif (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1
    n0 = n * (n - 1) / 2
    denom = math.sqrt((n0 - tie_x) * (n0 - tie_y))
    if denom <= _EPS:
        return None
    return (concordant - discordant) / denom


# ---------------------------------------------------------------------------
# Grid


@dataclass(frozen=True)
class _Point:
    eighth: int
    price: float
    pitch: float | None
    window: int
    phrase: int | None


def _phrase_of(phrases: Sequence, eighth: int) -> int | None:
    for index, phrase in enumerate(phrases):
        if phrase.start <= eighth < phrase.end:
            return index
    return None


def _window_of(windows: Sequence[tuple[int, int]], bar: int) -> int | None:
    for index, (start, end) in enumerate(windows):
        if start <= bar < end:
            return index
    return None


def _trace_bounds(point: PriceTracePoint, bar_beats: float) -> tuple[float, float]:
    start = point.bar + point.beat / bar_beats
    end = start + max(point.duration_beats, 0.01) / bar_beats
    return start, end


class _PitchLookup:
    def __init__(self, trace: Sequence[PriceTracePoint], bar_beats: float) -> None:
        self.bar_beats = bar_beats
        self.items = sorted(
            ((*_trace_bounds(point, bar_beats), point) for point in trace if point.pitch is not None),
            key=lambda item: (item[0], item[1]),
        )

    def at(self, position: float) -> float | None:
        best: PriceTracePoint | None = None
        best_key: tuple[float, float] = (-1.0, -1.0)
        for start, end, point in self.items:
            if start - 1e-9 <= position < end - 1e-9:
                key = (point.weight, start)
                if best is None or key > best_key:
                    best = point
                    best_key = key
        return None if best is None else best.pitch


def _grid(
    score: Score,
    variant: str,
    pitch_at,
    frame_bars: frozenset[int],
    windows: Sequence[tuple[int, int]],
) -> list[_Point]:
    epb = max(1, int(round(score.bar_beats * 2)))
    points: list[_Point] = []
    prices = score.price_eighths
    for eighth, price in enumerate(prices):
        bar = eighth // epb
        if bar in frame_bars or bar >= score.bars:
            continue
        window = _window_of(windows, bar)
        if window is None:
            continue
        points.append(
            _Point(
                eighth=eighth,
                price=price,
                pitch=pitch_at(eighth / epb),
                window=window,
                phrase=_phrase_of(score.phrases, eighth),
            )
        )
    return points


def _deregister(points: Sequence[_Point]) -> list[_Point]:
    """Remove octave jumps at phrase seams before ranking the contour.

    Jazz transposes a whole phrase by 0/12/24 semitones and guitar writers
    change register between phrases.  The jump is a written decision, not a
    price move, so each phrase is shifted by the nearest whole octave to the
    pitch that was already sounding.  Shape/Motion/Resolution then read the
    contour inside a section without rewarding or punishing the seam.
    """
    adjusted = list(points)
    last_pitch: float | None = None
    phrase: int | None = None
    shift = 0.0
    for index, point in enumerate(points):
        if point.phrase != phrase:
            phrase = point.phrase
            shift = 0.0
            if point.pitch is not None and last_pitch is not None:
                shift = round((last_pitch - point.pitch) / 12.0) * 12.0
        if point.pitch is None:
            continue
        value = point.pitch + shift
        adjusted[index] = replace(point, pitch=value)
        last_pitch = value
    return adjusted


def _phrase_eps(
    points: Sequence[_Point],
    *,
    session_low: float,
    session_high: float,
    median_close: float,
) -> float:
    prices = [point.price for point in points]
    floor = 0.0005 * median_close
    if len(prices) < 4:
        span = session_high - session_low
    else:
        span = max(prices) - min(prices)
    deltas = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    typical = median(deltas) if deltas else 0.0
    return max(0.05 * span, 0.25 * typical, floor)


def _phrase_points(points: Sequence[_Point], phrase: int) -> list[_Point]:
    return [point for point in points if point.phrase == phrase]


# ---------------------------------------------------------------------------
# Sub-scores


def _shape(points: Sequence[_Point], eps: float) -> tuple[float | None, float]:
    usable = [point for point in points if point.pitch is not None]
    prices = [point.price for point in usable]
    if len(usable) < 2:
        return None, 0.0
    if (max(prices) - min(prices)) <= eps:
        return None, 0.0
    if len(usable) >= 4:
        rho = spearman(prices, [point.pitch for point in usable])  # type: ignore[list-item]
        if rho is None:
            return None, 0.0
        return max(0.0, rho), float(len(usable))
    # Ambient: too few anchors for a rank correlation. Reward same-direction
    # consecutive pairs instead, with half the evidence weight.
    pairs = list(zip(usable, usable[1:]))
    if not pairs:
        return None, 0.0
    agree = sum(
        1
        for left, right in pairs
        if (right.price - left.price) * (right.pitch - left.pitch) > 0  # type: ignore[operator]
    )
    return agree / len(pairs), 0.5 * len(pairs)


def _motion(points: Sequence[_Point], eps: float) -> tuple[float | None, float, bool]:
    usable = [point for point in points if point.pitch is not None]
    pairs = list(zip(usable, usable[1:]))
    # Price only changes at a source-bar boundary, so most eighth steps are
    # (no price move, no pitch move).  They carry no rank information, but
    # Kendall tau-b counts them as ties and dilutes a real 0.6 to 0.05.
    # A hold over a moving price (x > 0, y == 0) stays and is still penalized.
    pairs = [
        (left, right)
        for left, right in pairs
        if abs(right.price - left.price) > _EPS
        or abs((right.pitch or 0.0) - (left.pitch or 0.0)) > _EPS
    ]
    x = [abs(right.price - left.price) for left, right in pairs]
    y = [abs(right.pitch - left.pitch) for left, right in pairs]  # type: ignore[operator]
    low_evidence = False
    if len(pairs) < 4 or all(abs(value - x[0]) <= _EPS for value in x):
        # Anchor-to-anchor fallback: drop pure holds, keep attacks.  A hold
        # over a price move still counts in the normal path; this path only
        # rescues a phrase with too few overlap points.
        anchors = [usable[0]] if usable else []
        for point in usable[1:]:
            if point.pitch != anchors[-1].pitch:
                anchors.append(point)
        if len(anchors) >= 2:
            pairs = list(zip(anchors, anchors[1:]))
            x = [abs(right.price - left.price) for left, right in pairs]
            y = [abs(right.pitch - left.pitch) for left, right in pairs]  # type: ignore[operator]
            low_evidence = True
    if len(pairs) < 4 or all(abs(value - x[0]) <= _EPS for value in x):
        return None, 0.0, low_evidence
    tau = kendall_tau_b(x, y)
    if tau is None:
        return None, 0.0, low_evidence
    return max(0.0, tau), float(len(pairs)), low_evidence


def _extrema(points: Sequence[_Point]) -> float:
    if len(points) < 2:
        return 0.0
    n = len(points)
    reach = max(1.0, n / 2.0)
    price_values = [point.price for point in points]
    pitch_values = [point.pitch for point in points]
    apex_price = max(range(n), key=lambda index: (price_values[index], -index))
    apex_pitch = max(range(n), key=lambda index: (pitch_values[index], -index))  # type: ignore[type-var]
    trough_price = min(range(n), key=lambda index: (price_values[index], index))
    trough_pitch = min(range(n), key=lambda index: (pitch_values[index], index))  # type: ignore[type-var]
    apex = 1.0 - min(1.0, abs(apex_price - apex_pitch) / reach)
    trough = 1.0 - min(1.0, abs(trough_price - trough_pitch) / reach)
    return (apex + trough) / 2.0


def _structure(
    phrases: Sequence[Sequence[_Point]],
    eps_by_phrase: Sequence[float],
) -> tuple[float | None, float]:
    extrema_weight = 0.0
    extrema_sum = 0.0
    trend_hits = 0
    trend_n = 0
    ranges: list[tuple[float, float]] = []
    for index, points in enumerate(phrases):
        usable = [point for point in points if point.pitch is not None]
        if len(usable) < 2:
            continue
        prices = [point.price for point in usable]
        pitches = [point.pitch for point in usable]
        price_move = prices[-1] - prices[0]
        pitch_move = pitches[-1] - pitches[0]  # type: ignore[operator]
        if abs(price_move) > eps_by_phrase[index]:
            trend_n += 1
            if (price_move > 0) == (pitch_move > 0):
                trend_hits += 1
        if len(usable) >= 4 and (max(prices) - min(prices)) > eps_by_phrase[index]:
            extrema_sum += _extrema(usable) * len(usable)
            extrema_weight += len(usable)
            ranges.append((max(prices) - min(prices), max(pitches) - min(pitches)))  # type: ignore[type-var]
    extrema = extrema_sum / extrema_weight if extrema_weight else None
    trend = trend_hits / trend_n if trend_n else None
    range_tau = None
    if len(ranges) >= 4:
        range_tau = kendall_tau_b(
            [item[0] for item in ranges], [item[1] for item in ranges]
        )
        if range_tau is not None:
            range_tau = max(0.0, range_tau)
    if len(ranges) >= 4 and range_tau is not None and extrema is not None and trend is not None:
        return 0.50 * extrema + 0.30 * range_tau + 0.20 * trend, float(extrema_weight)
    parts = [value for value in (extrema, trend) if value is not None]
    if not parts:
        return None, 0.0
    if extrema is not None and trend is not None:
        return 0.70 * extrema + 0.30 * trend, float(extrema_weight)
    return sum(parts) / len(parts), float(extrema_weight or trend_n)


def _resolution(points: Sequence[_Point], eps: float, pitch_step: float) -> tuple[float | None, float]:
    usable = [point for point in points if point.pitch is not None]
    pairs = list(zip(usable, usable[1:]))
    true_positive = false_negative = false_positive = 0
    for left, right in pairs:
        price_moves = abs(right.price - left.price) > eps
        pitch_moves = abs(right.pitch - left.pitch) > pitch_step  # type: ignore[operator]
        if price_moves and pitch_moves:
            true_positive += 1
        elif price_moves:
            false_negative += 1
        elif pitch_moves:
            false_positive += 1
    if true_positive + false_negative == 0:
        return None, 0.0
    recall = true_positive / (true_positive + false_negative)
    if true_positive + false_positive == 0:
        return recall, float(len(pairs))
    precision = true_positive / (true_positive + false_positive)
    if precision + recall <= _EPS:
        return 0.0, float(len(pairs))
    return 2 * precision * recall / (precision + recall), float(len(pairs))


def _dynamic_gain(score: Score):
    """Loudness multiplier of the printed dynamic in force at a note.

    MuseScore plays the letter dynamic, not the note velocity.  A score can
    print p/mp/mf/f per window while every `NoteEvent.velocity` stays around
    64, so velocity alone reads a real volume contour as silence.
    """
    events = sorted(score.dynamics, key=lambda item: (item.bar, item.beat))
    if not events:
        return lambda _bar, _beat: 1.0
    bar_beats = max(score.bar_beats, 1.0)
    positions = [event.bar + event.beat / bar_beats for event in events]
    gains = [event.sound / 90.0 for event in events]

    def gain(bar: int, beat: float) -> float:
        position = bar + beat / bar_beats
        index = bisect_right(positions, position) - 1
        return gains[index] if index >= 0 else 1.0

    return gain


def _volume(score: Score) -> float | None:
    windows = score.volume_windows
    volumes = score.window_volumes
    if not windows or len(windows) != len(volumes):
        return None
    notes = [
        event
        for part in (score.high, score.lead, score.support, score.comp, score.low)
        for event in part
    ]
    gain = _dynamic_gain(score)
    energies: list[float] = []
    used_volumes: list[float] = []
    for (start, length), volume in zip(windows, volumes):
        if volume <= 0:
            continue
        beats = max(length * score.bar_beats, 1.0)
        energy = 0.0
        for event in notes:
            if event.midi is None or not (start <= event.bar < start + length):
                continue
            velocity = 64 if event.velocity is None else event.velocity
            energy += max(event.duration_beats, 0.01) * velocity * gain(event.bar, event.beat)
        energies.append(energy / beats)
        used_volumes.append(volume)
    if len(used_volumes) < 4 or len(set(round(value, 9) for value in used_volumes)) < 3:
        return None
    if all(abs(value - used_volumes[0]) <= _EPS for value in used_volumes):
        return None
    tau = kendall_tau_b(used_volumes, energies)
    return None if tau is None else max(0.0, tau)


def _coverage(
    score: Score,
    frame_bars: frozenset[int],
    windows: Sequence[tuple[int, int]],
    eps_by_window: dict[int, float],
    session_eps: float,
    points: Sequence[_Point],
    pitch_at,
    epb: int,
) -> tuple[float, float | None]:
    closes = list(score.source_closes)
    groups = score.source_groups
    if not closes or not groups:
        return 1.0, None
    location: dict[int, tuple[int, int, int]] = {}
    for musical_bar, group in enumerate(groups):
        count = len(group)
        for position, source in enumerate(group):
            location[source] = (musical_bar, position, count)
    weights: list[float] = []
    sounds: list[int] = []
    for source, close in enumerate(closes):
        place = location.get(source)
        if place is None:
            continue
        musical_bar, position, count = place
        if musical_bar in frame_bars:
            continue
        window = _window_of(windows, musical_bar)
        eps = eps_by_window.get(window, session_eps) if window is not None else session_eps
        if source == 0:
            weight = eps
        else:
            weight = max(abs(close - closes[source - 1]), eps)
        start = musical_bar + position / count
        end = musical_bar + (position + 1) / count
        sounding = 0
        for point in score.price_trace:
            if point.pitch is None:
                continue
            point_start, point_end = _trace_bounds(point, score.bar_beats)
            if point_start < end - 1e-9 and point_end > start + 1e-9:
                sounding = 1
                break
        weights.append(weight)
        sounds.append(sounding)
    total = sum(weights)
    coverage = 1.0 if total <= _EPS else sum(w * s for w, s in zip(weights, sounds)) / total

    # Diagnostic only: the variant's own grid, never the cross-genre number.
    detail_weights: list[float] = []
    detail_sounds: list[int] = []
    for index in range(1, len(points)):
        left, right = points[index - 1], points[index]
        if right.window != left.window:
            continue
        eps = eps_by_window.get(right.window, session_eps)
        weight = max(abs(right.price - left.price), eps)
        detail_weights.append(weight)
        detail_sounds.append(1 if pitch_at(right.eighth / epb) is not None else 0)
    detail_total = sum(detail_weights)
    detail = (
        None
        if detail_total <= _EPS
        else sum(w * s for w, s in zip(detail_weights, detail_sounds)) / detail_total
    )
    return coverage, detail


# ---------------------------------------------------------------------------
# Public entry point


def _band(score: float) -> Literal["very-clear", "clear", "fair", "faint", "very-faint"]:
    if score >= 85:
        return "very-clear"
    if score >= 70:
        return "clear"
    if score >= 55:
        return "fair"
    if score >= 40:
        return "faint"
    return "very-faint"


def compute(score: Score, *, variant: str, ensemble: str = "classic") -> DfiBreakdown | None:
    """Return the DFI for a finished (and, ideally, humanized) score."""
    if not score.price_trace or not score.price_eighths:
        return None
    epb = max(1, int(round(score.bar_beats * 2)))
    frame_bars = frozenset(score.frame_bars)
    lookup = _PitchLookup(score.price_trace, score.bar_beats)

    def pitch_at(position: float) -> float | None:
        return lookup.at(position)

    windows = list(score.analysis_windows) or [(0, score.bars)]
    points = _deregister(_grid(score, variant, pitch_at, frame_bars, windows))
    if not points:
        return None

    closes = list(score.source_closes) or list(score.price_eighths)
    session_low = min(closes)
    session_high = max(closes)
    median_close = median(closes)

    by_window: dict[int, list[_Point]] = {}
    for point in points:
        by_window.setdefault(point.window, []).append(point)
    window_order = sorted(by_window)
    window_points = [by_window[index] for index in window_order]
    eps_by_window = {
        index: _phrase_eps(
            chunk,
            session_low=session_low,
            session_high=session_high,
            median_close=median_close,
        )
        for index, chunk in zip(window_order, window_points)
    }
    session_eps = max(
        0.05 * (session_high - session_low),
        0.0005 * median_close,
    )

    n_moves = 0
    ordered = sorted(points, key=lambda point: point.eighth)
    for left, right in zip(ordered, ordered[1:]):
        if right.eighth - left.eighth != 1:
            continue
        if abs(right.price - left.price) > eps_by_window[right.window]:
            n_moves += 1
    n_sounding = sum(1 for point in score.price_trace if point.pitch is not None)
    if n_moves < 4:
        return None

    shape_sum = shape_weight = 0.0
    motion_sum = motion_weight = 0.0
    resolution_sum = resolution_weight = 0.0
    for chunk in window_points:
        eps = eps_by_window[chunk[0].window]
        value, weight = _shape(chunk, eps)
        if value is not None:
            shape_sum += value * weight
            shape_weight += weight
        value, weight, _low = _motion(chunk, eps)
        if value is not None:
            motion_sum += value * weight
            motion_weight += weight
        value, weight = _resolution(chunk, eps, 2.0 if variant == "minimalist" else 1.0)
        if value is not None:
            resolution_sum += value * weight
            resolution_weight += weight

    structure_value, structure_weight = _structure(
        window_points, [eps_by_window[index] for index in window_order]
    )
    volume = _volume(score)
    coverage, coverage_detail = _coverage(
        score,
        frame_bars,
        windows,
        eps_by_window,
        session_eps,
        points,
        pitch_at,
        epb,
    )

    components: list[tuple[float, float]] = []
    if shape_weight:
        components.append((WEIGHT_SHAPE, shape_sum / shape_weight))
    if motion_weight:
        components.append((WEIGHT_MOTION, motion_sum / motion_weight))
    if structure_value is not None and structure_weight:
        components.append((WEIGHT_STRUCTURE, structure_value))
    if resolution_weight:
        components.append((WEIGHT_RESOLUTION, resolution_sum / resolution_weight))
    if volume is not None:
        components.append((WEIGHT_VOLUME, volume))
    if len(components) < 2:
        return None
    weight_total = sum(weight for weight, _value in components)
    blended = sum(weight * value for weight, value in components) / weight_total
    total = max(0.0, min(100.0, 100.0 * blended * coverage))

    if n_moves >= 24 and n_sounding >= 48 and len(score.window_volumes) >= 8:
        confidence: Literal["low", "medium", "high"] = "high"
    elif n_moves >= 8 and n_sounding >= 16:
        confidence = "medium"
    else:
        confidence = "low"

    return DfiBreakdown(
        score=total,
        band=_band(total),
        shape=None if not shape_weight else shape_sum / shape_weight,
        motion=None if not motion_weight else motion_sum / motion_weight,
        structure=structure_value,
        resolution=None if not resolution_weight else resolution_sum / resolution_weight,
        volume=volume,
        coverage=coverage,
        coverage_detail=coverage_detail,
        opportunity=min(1.0, n_moves / 24.0),
        confidence=confidence,
        n_moves=n_moves,
        n_sounding=n_sounding,
    )
