"""Melodic phrases, cut where the price stalls or leaps.

A close that stays on one scale tone for several eighths is a held note. A
held note of at least PERIOD eighths (two beats) ends a phrase once the
phrase is MIN_EIGHTHS long; an earlier one stays inside the phrase. A phrase
that reaches MAX_EIGHTHS without one is cut after its longest COMMA-length
note, then after a BEAT-length note followed by a wide LEAP, then after its
latest note change, and only then mid-note. A note cut mid-note is held over
into the next phrase rather than closing this one. Section starts open a new
phrase unless the closing phrase carries up to PERIOD eighths across the bar
line to finish on a held note or before a wide leap.
"""

from __future__ import annotations

from dataclasses import dataclass

PERIOD = 4
COMMA = 3
BEAT = 2
LEAP = 5
MIN_EIGHTHS = 16
MAX_EIGHTHS = 32


@dataclass(frozen=True)
class Run:
    """Consecutive eighths on one pitch."""

    start: int
    length: int
    midi: int

    @property
    def end(self) -> int:
        return self.start + self.length


@dataclass(frozen=True)
class Phrase:
    start: int
    end: int
    runs: tuple[Run, ...]
    # The last note goes on sounding into the next phrase of the same section.
    held_over: bool = False

    @property
    def apex(self) -> Run:
        """The first run on the highest pitch: the phrase's local price high."""
        return max(self.runs, key=lambda run: (run.midi, -run.start))

    @property
    def cadence(self) -> Run:
        return self.runs[-1]

    @property
    def closes(self) -> bool:
        return self.cadence.length >= PERIOD and not self.held_over

    @property
    def rise(self) -> int:
        """Semitones from the lowest note in the phrase up to its apex."""
        return self.apex.midi - min(run.midi for run in self.runs)


def runs_of(pitches: list[int], start: int, end: int) -> list[Run]:
    runs: list[Run] = []
    for index in range(start, end):
        midi = pitches[index]
        if runs and runs[-1].midi == midi:
            runs[-1] = Run(runs[-1].start, runs[-1].length + 1, midi)
        else:
            runs.append(Run(index, 1, midi))
    return runs


def _clip(runs: list[Run], start: int, end: int) -> tuple[Run, ...]:
    clipped: list[Run] = []
    for run in runs:
        low = max(run.start, start)
        high = min(run.end, end)
        if low < high:
            clipped.append(Run(low, high - low, run.midi))
    return tuple(clipped)


def _leap_after(runs: list[Run], run: Run) -> int:
    for following in runs:
        if following.start == run.end:
            return abs(following.midi - run.midi)
    return 0


def _cut(runs: list[Run], start: int, end: int) -> int:
    """Where the phrase opened at start ends, inside a section ending at end."""
    low = start + MIN_EIGHTHS
    high = min(start + MAX_EIGHTHS, end - MIN_EIGHTHS)
    candidates = [run for run in runs if low <= run.end <= high]

    def held(run: Run) -> int:
        return run.end - max(run.start, start)

    for run in candidates:
        if held(run) >= PERIOD:
            return run.end
    if end - start <= MAX_EIGHTHS:
        return end
    commas = [run for run in candidates if held(run) >= COMMA]
    if commas:
        return max(commas, key=lambda run: (held(run), run.end)).end
    leaps = [run for run in candidates if held(run) >= BEAT and _leap_after(runs, run) >= LEAP]
    if leaps:
        return max(leaps, key=lambda run: (_leap_after(runs, run), held(run), run.end)).end
    if candidates:
        return candidates[-1].end
    return high


def _settle_edge(runs: list[Run], start: int, edge: int, next_edge: int) -> int:
    """Let a phrase carry up to PERIOD eighths across a section bar line to resolve."""
    high = min(edge + PERIOD, start + MAX_EIGHTHS, next_edge - MIN_EIGHTHS)
    if high <= edge:
        return edge

    def held(run: Run) -> int:
        return run.end - max(run.start, start)

    at_edge = next((run for run in runs if run.start < edge <= run.end), None)
    if at_edge is not None:
        if at_edge.end == edge and held(at_edge) >= COMMA:
            return edge
        if edge - max(at_edge.start, start) >= PERIOD:
            return edge

    after = [run for run in runs if edge < run.end <= high]
    for run in after:
        if held(run) >= PERIOD:
            return run.end
    commas = [run for run in after if held(run) >= COMMA]
    if commas:
        return max(commas, key=lambda run: (held(run), run.end)).end
    leaps = [run for run in after if held(run) >= BEAT and _leap_after(runs, run) >= LEAP]
    if leaps:
        return max(leaps, key=lambda run: (_leap_after(runs, run), held(run), run.end)).end
    return edge


def plan_phrases(pitches: list[int], section_starts: tuple[int, ...]) -> tuple[Phrase, ...]:
    """Phrases over a line of one pitch per eighth; section starts are eighth indexes."""
    total = len(pitches)
    bounds = sorted({0, *(start for start in section_starts if 0 < start < total)})
    bounds.append(total)
    section_set = set(bounds)
    runs = runs_of(pitches, 0, total)
    phrases: list[Phrase] = []
    cursor = 0
    for index, edge in enumerate(bounds[1:], 1):
        while cursor < edge:
            if edge - cursor <= MAX_EIGHTHS and edge < total:
                edge = _settle_edge(runs, cursor, edge, bounds[index + 1])
            cut = _cut(runs, cursor, edge)
            held_over = (
                cut < total and cut not in section_set and pitches[cut] == pitches[cut - 1]
            )
            phrases.append(Phrase(cursor, cut, _clip(runs, cursor, cut), held_over))
            cursor = cut
    return tuple(phrases)


def swell(phrase: Phrase, onset: int) -> float:
    """0 at the phrase edges and 1 at the apex, linear in between."""
    apex = phrase.apex.start
    if onset <= apex:
        if apex == phrase.start:
            return 1.0
        return (onset - phrase.start) / (apex - phrase.start)
    return 1.0 - (onset - apex) / (phrase.end - apex)
