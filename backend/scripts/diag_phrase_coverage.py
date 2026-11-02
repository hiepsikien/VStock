#!/usr/bin/env python3
"""Measure the phrase arch and the within-bar micro contour, per pattern.

Arch (metric in docs/sonify-guitar-phrase-coverage-plan.md §0.1): the apex
mean minus the mean of the two edge quarters. A phrase passes when arch >= 2.

Micro: `velocity - _note_velocity - _shape_dynamics extra`. The wave adds one
constant per bar, so it cancels and the residual range is the pattern's own
within-bar shaping. Thin Torroba textures are labelled from the figure plan,
not from `_bar_pattern`, so `alcaniz_soft`, `olite_thin`, and `JUGLAR_THIN`
are measured separately from their full/opening siblings.

The extra is replicated here for `_WHOLE_BAR_EXTRA` patterns. Two omissions
remain and are deliberate: `relaxed` is local to `render_patterned_voices`, and
`protected_eighths` also includes swarm eighths. The residual for a long note
uses the written duration, not the phrase's run length, so it is a relative
before/after measure rather than a byte-exact reconstruction.

Both layers are measured on the written score (`render`) and, for the arch,
on the heard score (`humanize`). Run from backend/:

    python scripts/diag_phrase_coverage.py
    python scripts/diag_phrase_coverage.py --pattern danza
    python scripts/diag_phrase_coverage.py --json > /tmp/phrase.json

Requires the cached price data used by `plan_span`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from app.sonify import guitar_patterns as gp  # noqa: E402
from app.sonify import guitar_torroba as gt  # noqa: E402
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
_ETUDE_OR_TREMOLO = frozenset({"etude1", "etude11", "tremolo"})
_FIGURE_NAMES = {
    gt.JUGLAR_THIN: "JUGLAR_THIN",
    gt.ALCANIZ_OPENING: "alcaniz_opening",
    gt.ALCANIZ_SOFT: "alcaniz_soft",
    gt.OLITE_THIN: "olite_thin",
    gt.CASTILLO_WALK: "castillo_walk",
    gt.CASTILLO_CADENCE: "castillo_cadence",
}


def _capture(ctx, *args, **kwargs):
    found = _REAL_PATTERNS(ctx, *args, **kwargs)
    _CAPTURED.append((ctx, list(found)))
    return found


def _eighth(note, epb: int) -> int:
    return note.bar * epb + int(math.floor(float(note.beat) * 2 + 1e-9))


def _labels(ctx, patterns) -> dict[int, str]:
    """Bar -> pattern or thin-texture label. The figure plan owns the thin names."""
    labels = {bar: gp._bar_pattern(ctx, bar, patterns) for bar in range(ctx.bars)}
    if getattr(ctx, "ensemble", "") != "torroba":
        return labels
    try:
        plan = gt._castillos_figure_plan(ctx, patterns)
    except Exception:
        return labels
    for bar, (figure, _index, _count) in plan.items():
        labels[bar] = _FIGURE_NAMES.get(figure, f"figure_{figure}")
    return labels


def _singing_events(score, phrase, epb: int, pattern: str) -> list[tuple[int, int]]:
    """Written attacks that carry the phrase's arch, as (eighth, velocity).

    Torroba tremolo has three fingers after the beat and the thumb on it. The
    loudest finger of each beat is `JUGLAR_FINGERS[0]`; the thumb is that value
    plus `JUGLAR_RISE` in `low`. Grouping the lead by beat keeps one attack per
    beat and reads the same arch the thumb then follows.
    """
    if pattern == "torroba_tremolo":
        by_beat: dict[tuple[int, int], tuple[int, int]] = {}
        for note in score.lead:
            if note.midi is None or note.velocity is None or note.tie_stop:
                continue
            onset = _eighth(note, epb)
            if not (phrase.start <= onset < phrase.end):
                continue
            beat = int(math.floor(float(note.beat) + 1e-9))
            key = (note.bar, beat)
            current = by_beat.get(key)
            if current is None or int(note.velocity) > current[1]:
                by_beat[key] = (note.bar * epb + beat * 2, int(note.velocity))
        return sorted(by_beat.values())
    events: list[tuple[int, int]] = []
    for note in score.lead:
        if note.midi is None or note.velocity is None or note.tie_stop:
            continue
        onset = _eighth(note, epb)
        if phrase.start <= onset < phrase.end and _singing(pattern, note):
            events.append((onset, int(note.velocity)))
    events.sort()
    return events


def _singing(pattern: str, note) -> bool:
    """Singing-attack filter. Only the rows implemented here are filtered.

    The plan's §0.2 table also names `bach_allemande`, `cantabile`,
    `chord_melody`, `andante`, `preludio`, `danza`, and `fandanguillo`. Those
    are not implemented yet; their arch is measured on every lead attack.
    """
    if pattern == "bach_prelude":
        # Price note of each 16th pair, not the neighbour.
        return int(round(float(note.beat) * 4)) % 2 == 0
    return True


def _arch(score, phrase, epb: int, pattern: str):
    events = _singing_events(score, phrase, epb, pattern)
    if len(events) < 3:
        return None
    apex = [v for onset, v in events if phrase.apex.start <= onset < phrase.apex.end]
    if not apex:
        return None
    quarter = max(1, (phrase.end - phrase.start) // 4)

    def mean(values):
        return sum(values) / len(values)

    if phrase.apex.end >= phrase.end - quarter:
        edge = [
            v
            for onset, v in events
            if onset < phrase.start + quarter
            and onset not in range(phrase.apex.start, phrase.apex.end)
        ]
    elif phrase.apex.start <= phrase.start + quarter:
        edge = [
            v
            for onset, v in events
            if onset >= phrase.end - quarter
            and onset not in range(phrase.apex.start, phrase.apex.end)
        ]
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


def _pattern(ctx, phrase, patterns) -> str:
    for index, candidate in enumerate(ctx.phrases):
        if candidate is phrase:
            if index >= len(patterns):
                raise ValueError(f"phrase {phrase.start}-{phrase.end} has no pattern")
            return patterns[index]
    raise ValueError(f"phrase {phrase.start}-{phrase.end} is not in ctx.phrases")


def _extra(ctx, note, onset: int, phrase, patterns, epb: int) -> int:
    """The `_shape_dynamics` extra, minus the branches this script cannot see.

    `relaxed` and the swarm half of `protected_eighths` stay out. For the
    Torroba thin textures the extra is one number for the whole bar, so it
    cancels in `max - min` anyway.
    """
    if phrase is None or phrase.rise <= 0:
        return 0
    pattern = gp._bar_pattern(ctx, note.bar, patterns)
    if pattern in _ETUDE_OR_TREMOLO or gt.skips_bar_extra(ctx, note):
        return 0
    anchor = note.bar * epb if pattern in gp._WHOLE_BAR_EXTRA else onset
    return round(4 * swell(phrase, min(max(anchor, phrase.start), phrase.end - 1)))


def _micro(score, ctx, patterns):
    epb = int(round(score.bar_beats * 2)) or 8
    apex = _apex_eighths(ctx.phrases)
    labels = _labels(ctx, patterns)
    by_bar: dict[int, list[int]] = defaultdict(list)
    for note in score.lead:
        if note.midi is None or note.velocity is None or note.tie_stop:
            continue
        onset = _eighth(note, epb)
        phrase = gp._phrase_at(ctx, onset)
        length = max(1, int(round(float(note.duration_beats) * 2)))
        base = gp._note_velocity(onset, length, apex, phrase)
        extra = _extra(ctx, note, onset, phrase, patterns, epb)
        by_bar[note.bar].append(int(note.velocity) - base - extra)
    found: dict[str, list[int]] = defaultdict(list)
    for bar, residual in by_bar.items():
        if len(residual) < 2 or ctx.kind_at.get(bar) in _PEDAL:
            continue
        label = labels.get(bar, gp._bar_pattern(ctx, bar, patterns))
        found[label].append(max(residual) - min(residual))
    return found


def _revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="only print this pattern or texture (repeatable)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON instead of the table",
    )
    return parser.parse_args()


async def _collect() -> tuple[dict, dict, dict]:
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
            epb = int(round(score.bar_beats * 2)) or 8
            heard = humanize(score)
            for phrase in ctx.phrases:
                if (
                    phrase.rise <= 0
                    or ctx.kind_at.get(phrase.start // ctx.epb) in _PEDAL
                ):
                    continue
                pattern = _pattern(ctx, phrase, patterns)
                value = _arch(score, phrase, epb, pattern)
                if value is not None:
                    arches[pattern].append(value)
                heard_value = _arch(heard, phrase, epb, pattern)
                if heard_value is not None:
                    heard_arches[pattern].append(heard_value)
            for pattern, ranges in _micro(score, ctx, patterns).items():
                micro[pattern].extend(ranges)
    return arches, heard_arches, micro


def _rows(arches, heard_arches, micro) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for pattern in sorted(set(arches) | set(heard_arches) | set(micro)):
        written = arches.get(pattern, [])
        heard = heard_arches.get(pattern, [])
        ranges = micro.get(pattern, [])
        rows[pattern] = {
            "n_arch": len(written),
            "written_ok": (
                100 * sum(1 for value in written if value >= 2) / len(written)
                if written
                else None
            ),
            "heard_ok": (
                100 * sum(1 for value in heard if value >= 2) / len(heard)
                if heard
                else None
            ),
            "median_arch": median(written) if written else None,
            "median_heard": median(heard) if heard else None,
            "micro_flat": (
                100 * sum(1 for value in ranges if value <= 1) / len(ranges)
                if ranges
                else None
            ),
            "micro_median": median(ranges) if ranges else None,
            "n_micro": len(ranges),
            "written_values": written,
            "heard_values": heard,
            "micro_ranges": ranges,
        }
    return rows


def _print_table(rows: dict[str, dict], selected: list[str]) -> None:
    print(f"# commit {_revision()}  {date.today().isoformat()}")
    print(
        f"{'pattern':18s} {'n':>4s} {'written':>9s} {'heard':>9s}"
        f" {'median':>8s} {'micro flat':>10s} {'micro med':>10s} {'micro n':>8s}"
    )
    for pattern, row in rows.items():
        if selected and pattern not in selected:
            continue
        written = "-" if row["written_ok"] is None else f"{row['written_ok']:8.0f}%"
        heard = "-" if row["heard_ok"] is None else f"{row['heard_ok']:8.0f}%"
        arch_med = "-" if row["median_arch"] is None else f"{row['median_arch']:8.1f}"
        flat = "-" if row["micro_flat"] is None else f"{row['micro_flat']:9.0f}%"
        med = "-" if row["micro_median"] is None else f"{row['micro_median']:10.1f}"
        print(
            f"{pattern:18s} {row['n_arch']:4d}"
            f" {written:>9s} {heard:>9s} {arch_med:>8s}"
            f" {flat:>10s} {med:>10s} {row['n_micro']:8d}"
        )


async def main() -> int:
    args = _parse_args()
    gp._patterns = _capture  # type: ignore[assignment]
    try:
        arches, heard_arches, micro = await _collect()
    finally:
        gp._patterns = _REAL_PATTERNS  # type: ignore[assignment]
    rows = _rows(arches, heard_arches, micro)
    if args.json:
        print(
            json.dumps(
                {
                    "commit": _revision(),
                    "date": date.today().isoformat(),
                    "cases": [list(case) for case in CASES],
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_table(rows, args.pattern)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
