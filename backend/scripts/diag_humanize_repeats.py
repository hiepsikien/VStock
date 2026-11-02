#!/usr/bin/env python3
"""Audit the repeated-pitch pass against the scope it claims.

The pass is lead only, same bar, consecutive attacks the writer left at one
level. This script measures that scope and the invariants around it:

- same-bar consecutive lead pairs that still share one velocity;
- new `lead <= bass` or `lead <= support` overlaps against the pre-pass score;
- notes under the guitar micro floor (40) in body bars;
- the largest single-note change (must stay at or under `REPEAT_GAP`).

Run from backend/:

    python scripts/diag_humanize_repeats.py

It renders real spans through `plan_span`, so cached price data is required.
The "before" column runs `humanize` with `_separate_repeats` switched off.
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

import app.sonify.humanize as humanize_mod  # noqa: E402
from app.sonify.humanize import humanize  # noqa: E402
from app.sonify.render import render  # noqa: E402
from app.services.spans import plan_span  # noqa: E402

CASES = (
    ("VNM", "1W", "bach"),
    ("VNM", "1W", "classic"),
    ("VNM", "1W", "barrios"),
    ("VNM", "1W", "villa"),
    ("VNM", "1W", "brouwer"),
    ("VNM", "1W", "torroba"),
    ("ACB", "1M", "torroba"),
)
_PEDAL = frozenset({"intro", "outro", "warmup", "cooldown"})


def _pedal_bars(score) -> set[int]:
    return {
        bar
        for slot in score.slots
        if getattr(slot, "section", None) in _PEDAL
        for bar in slot.bars()
    }


def _equal_pairs(score) -> int:
    """Same-bar consecutive lead attacks that still share one velocity."""
    pedal = _pedal_bars(score)
    by_bar: dict[int, list] = defaultdict(list)
    for note in score.lead:
        if note.midi is None or note.velocity is None or note.tie_stop or note.bar in pedal:
            continue
        by_bar[note.bar].append(note)
    total = 0
    for notes in by_bar.values():
        notes.sort(key=lambda note: note.beat)
        for left, right in zip(notes, notes[1:]):
            if left.midi == right.midi and left.velocity == right.velocity:
                total += 1
    return total


def _violations(score) -> set[tuple[int, float]]:
    """Lead attacks that do not sit above an overlapping bass/support note."""
    pedal = _pedal_bars(score)
    found: set[tuple[int, float]] = set()
    for lead in score.lead:
        if lead.midi is None or lead.velocity is None or lead.tie_stop or lead.bar in pedal:
            continue
        for other in (*score.low, *score.support):
            if other.midi is None or other.velocity is None or other.tie_stop:
                continue
            if other.bar != lead.bar:
                continue
            if (
                other.beat < lead.beat + lead.duration_beats
                and lead.beat < other.beat + other.duration_beats
                and lead.velocity <= other.velocity
            ):
                found.add((lead.bar, round(float(lead.beat), 2)))
                break
    return found


def _under_floor(score) -> int:
    pedal = _pedal_bars(score)
    return sum(
        1
        for field in ("lead", "support", "low")
        for note in getattr(score, field)
        if note.midi is not None
        and note.velocity is not None
        and not note.tie_stop
        and note.bar not in pedal
        and note.velocity < 40
    )


def _max_change(before, after) -> int:
    return max(
        (
            abs(int(b.velocity or 0) - int(a.velocity or 0))
            for a, b in zip(before.lead, after.lead)
            if a.velocity != b.velocity
        ),
        default=0,
    )


async def main() -> int:
    real = humanize_mod._separate_repeats

    def switched_off(original, heard, ensemble, **kwargs):
        return heard

    print(f"{'ensemble':10s} {'eq before':>9s} {'eq after':>8s} {'new viol':>8s} {'<40':>7s} {'max move':>8s}")
    for symbol, span, ensemble in CASES:
        plan = await plan_span(symbol, span, "guitar", ensemble=ensemble)
        movement = plan.movements[0]
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
            movement_index=0,
        )
        humanize_mod._separate_repeats = switched_off
        before = humanize(score)
        humanize_mod._separate_repeats = real
        after = humanize(score)
        new_violations = _violations(after) - _violations(before)
        print(
            f"{ensemble:10s} {_equal_pairs(before):9d} {_equal_pairs(after):8d}"
            f" {len(new_violations):8d} {_under_floor(before):4d}->{_under_floor(after):2d}"
            f" {_max_change(before, after):8d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
