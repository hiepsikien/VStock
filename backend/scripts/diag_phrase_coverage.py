#!/usr/bin/env python3
"""Measure the phrase arch and the within-bar micro contour, per pattern.

Arch (metric in docs/sonify-guitar-phrase-coverage-plan.md §0.1): the apex
mean minus the edge furthest from it. A phrase passes when arch >= 2.

Micro: `velocity - _note_velocity - _shape_dynamics extra`. The wave adds one
constant per bar, so it cancels and the residual range is the pattern's own
within-bar shaping.

Both layers are measured on the written score (`render`) and, for the arch,
on the heard score (`humanize`). Run from backend/:

    python scripts/diag_phrase_coverage.py

Requires the cached price data used by `plan_span`.
"""

from __future__ import annotations

import asyncio
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from app.sonify import guitar_patterns as gp  # noqa: E402
from app.sonify.guitar import _apex_eighths  # noqa: E402
from app.sonify.humanize import humanize  # noqa: E402
from app.sonify.phrasing import swell  # noqa: E402
from app.sonify.render import render  # noqa: E402
from app.services.spans import plan_span  # noqa: E402

CASES = (
    ("VNM", "1W", "bach"),
    ("VNM", "1W", "classic"),
    ("VNM", "1W", "barrios"),
    ("VNM", "1W", "villa"),
    ("VNM", "1W", "brouwer"),
    ("VNM", "1W", "torroba"),
    ("VIC", "1M", "torroba"),
    ("MSN", "1M", "torroba"),
    ("ACB", "1M", "torroba"),
)
_PEDAL = frozenset({"intro", "outro", "warmup", "cooldown"})
_REAL_PATTERNS = gp._patterns
_CAPTURED: list = []


def _capture(ctx, *args, **kwargs):
    found = _REAL_PATTERNS(ctx, *args, **kwargs)
    _CAPTURED.append((ctx, list(found)))
    return found


gp._patterns = _capture  # type: ignore[assignment]


def _eighth(note, epb: int) -> int:
    return note.bar * epb + int(math.floor(float(note.beat) * 2 + 1e-9))


def _singing(pattern: str, note) -> bool:
    """Rough singing-attack filter per the plan's §0.2 table."""
    if pattern == "torroba_tremolo":
        # First finger of each beat. The other two sit on sixteenths after it.
        return int(round((float(note.beat) % 1.0) * 4)) % 4 == 0
    if pattern == "bach_prelude":
        # Price note of each 16th pair, not the neighbor.
        return int(round(float(note.beat) * 4)) % 2 == 0
    return True


def _arch(score, ctx, phrase, epb: int):
    pattern = _pattern(ctx, phrase, _CAPTURED[-1][1])
    events = []
    for note in score.lead:
        if note.midi is None or note.velocity is None or note.tie_stop:
            continue
        onset = _eighth(note, epb)
        if phrase.start <= onset < phrase.end and _singing(pattern, note):
            events.append((onset, int(note.velocity)))
    events.sort()
    if len(events) < 3:
        return None
    apex = [v for onset, v in events if phrase.apex.start <= onset < phrase.apex.end]
    if not apex:
        return None
    quarter = max(1, (phrase.end - phrase.start) // 4)

    def mean(values):
        return sum(values) / len(values)

    if phrase.apex.end >= phrase.end - quarter:
        edge = [v for onset, v in events if onset < phrase.start + quarter and onset not in range(phrase.apex.start, phrase.apex.end)]
    elif phrase.apex.start <= phrase.start + quarter:
        edge = [v for onset, v in events if onset >= phrase.end - quarter and onset not in range(phrase.apex.start, phrase.apex.end)]
    else:
        edge = [
            v
            for onset, v in events
            if (onset < phrase.start + quarter or onset >= phrase.end - quarter)
            and onset not in range(phrase.apex.start, phrase.apex.end)
        ]
    if not edge:
        return None
    return mean(apex) - mean(edge)


def _pattern(ctx, phrase, patterns):
    index = next((i for i, p in enumerate(ctx.phrases) if p is phrase), 0)
    return patterns[index] if index < len(patterns) else "?"


def _micro(score, ctx, patterns):
    epb = int(round(score.bar_beats * 2)) or 8
    apex = _apex_eighths(ctx.phrases)
    by_bar: dict[int, list[int]] = defaultdict(list)
    for note in score.lead:
        if note.midi is None or note.velocity is None or note.tie_stop:
            continue
        onset = _eighth(note, epb)
        phrase = next((p for p in ctx.phrases if p.start <= onset < p.end), None)
        base = gp._note_velocity(onset, 1, apex, phrase)
        extra = 0
        if phrase is not None and phrase.rise > 0:
            pattern = gp._bar_pattern(ctx, note.bar, patterns)
            anchor = note.bar * epb if pattern in gp._WHOLE_BAR_EXTRA else onset
            extra = round(4 * swell(phrase, min(max(anchor, phrase.start), phrase.end - 1)))
        by_bar[note.bar].append(int(note.velocity) - base - extra)
    found = defaultdict(list)
    for bar, residual in by_bar.items():
        if len(residual) < 2 or ctx.kind_at.get(bar) in _PEDAL:
            continue
        found[gp._bar_pattern(ctx, bar, patterns)].append(max(residual) - min(residual))
    return found


async def main() -> int:
    arches: dict[str, list[int]] = defaultdict(list)
    heard_arches: dict[str, list[int]] = defaultdict(list)
    micro: dict[str, list[int]] = defaultdict(list)
    for symbol, span, ensemble in CASES:
        plan = await plan_span(symbol, span, "guitar", ensemble=ensemble)
        for index, movement in enumerate(plan.movements):
            _CAPTURED.clear()
            score = render(
                movement.bars,
                variant="guitar",
                ensemble=ensemble,
                title=f"{symbol} {span}",
                form=movement.spec,
                source_groups=movement.groups,
                key=movement.key,
                character=movement.character,
                outro_override=movement.outro_override,
                framed=False,
                mode=movement.mode,
                home_pedal=movement.home_pedal,
                character_at=movement.bar_characters,
                gap_leads=movement.gap_leads,
                movement_index=index,
            )
            if not _CAPTURED:
                continue
            ctx, patterns = _CAPTURED[-1]
            heard = humanize(score)
            for phrase in ctx.phrases:
                if (
                    phrase.rise <= 0
                    or ctx.kind_at.get(phrase.start // ctx.epb) in _PEDAL
                ):
                    continue
                pattern = _pattern(ctx, phrase, patterns)
                value = _arch(score, ctx, phrase, int(round(score.bar_beats * 2)) or 8)
                if value is not None:
                    arches[pattern].append(value)
                heard_value = _arch(heard, ctx, phrase, int(round(score.bar_beats * 2)) or 8)
                if heard_value is not None:
                    heard_arches[pattern].append(heard_value)
            for pattern, ranges in _micro(score, ctx, patterns).items():
                micro[pattern].extend(ranges)

    print(f"{'pattern':18s} {'n':>4s} {'written':>9s} {'heard':>9s} {'micro flat':>10s}")
    for pattern in sorted(arches):
        values = arches[pattern]
        heard_values = heard_arches.get(pattern, [])
        ranges = micro.get(pattern, [])
        ok = 100 * sum(1 for value in values if value >= 2) / len(values)
        heard_ok = (
            100 * sum(1 for value in heard_values if value >= 2) / len(heard_values)
            if heard_values
            else 0
        )
        flat = 100 * sum(1 for value in ranges if value <= 1) / len(ranges) if ranges else 0
        print(
            f"{pattern:18s} {len(values):4d}"
            f" {ok:8.0f}% {heard_ok:8.0f}% {flat:9.0f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
