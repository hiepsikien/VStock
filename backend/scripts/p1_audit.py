"""Broad audit of P1's `_written_deviations` trim across patterns.

Usage (from backend/):
  .venv/bin/python scripts/p1_audit.py tmp/p1_audit.json
  .venv/bin/python scripts/p1_audit.py tmp/p1_before.json --mode before

Compares the finished score with P1 trim and without it (profile bounds:
d_lo/d_hi from `PROFILES`) for the same movement.  `--mode before` restores
the old upper trim (`min(profile.d_hi, measured 99th)`) so the historical
table in `docs/sonify-guitar-p1-tide-audit.md` can be reproduced from HEAD.

The script fetches live OHLC when the local store is cold, so the numbers
depend on the data date.  It is diagnostic only; it does not change code or
the audio cache.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]

from app.services import dfi as dfi_service
from app.services.spans import plan_span
from app.sonify import guitar_patterns as GP
from app.sonify import guitar_wave as GW

CASES = [
    ("AAA", "1M"),
    ("ACB", "1M"),
    ("VNM", "1W"),
    ("VCB", "3M"),
]
ENSEMBLES = ["classic", "bach", "barrios", "villa", "brouwer", "torroba"]
PARTS = ("high", "lead", "support", "comp", "low")


@dataclass
class Run:
    score: object
    captured: dict
    deviations: dict
    waves: dict


@contextmanager
def capture_guitar():
    captured: dict = {}
    original_patterns = GP._patterns

    def patterns(ctx):
        found = original_patterns(ctx)
        captured["ctx"] = ctx
        captured["patterns"] = found
        return found

    GP._patterns = patterns
    try:
        yield captured
    finally:
        GP._patterns = original_patterns


def run_score(symbol, span, index, movement, ensemble, *, mode: str) -> Run:
    """Render one movement.

    `mode` is `current`, `before`, or `none`. `none` is the profile baseline;
    `before` applies the old `min(profile.d_hi, measured 99th)` trim.
    """
    deviations: dict = {}
    waves: dict = {}
    original_dev = GW._written_deviations
    original_wave = GW._make_wave

    def dev(ctx, voices, patterns, pedal):
        found = original_dev(ctx, voices, patterns, pedal)
        deviations.update(found)
        return {} if mode == "none" else found

    def wave(ctx, volumes, section, start, end, pattern, profile, span_, deviation=None, piece_median=None):
        if mode == "before" and deviation is not None:
            d_lo = max(profile.d_lo, deviation.d_lo)
            d_hi = min(profile.d_hi, deviation.d_hi_diagnostic)
            if d_hi < d_lo:
                d_hi = d_lo
            trimmed = replace(profile, d_lo=d_lo, d_hi=d_hi)
            made = original_wave(
                ctx, volumes, section, start, end, pattern, trimmed, span_, None, piece_median
            )
        else:
            made = original_wave(
                ctx, volumes, section, start, end, pattern, profile, span_, deviation, piece_median
            )
        waves[(start, end, pattern, made.span_start, made.span_end)] = {
            "c_lo": made.c_lo,
            "c_hi": made.c_hi,
            "v_floor": made.v_floor,
            "v_ceil": made.v_ceil,
            "gain": made.gain,
            "deviation": None
            if deviation is None
            else (deviation.d_lo, deviation.d_hi_diagnostic),
        }
        return made

    GW._written_deviations = dev
    GW._make_wave = wave
    try:
        with capture_guitar() as captured:
            score = dfi_service._movement_score(
                symbol, span, index, movement, "guitar", ensemble, humanize=False
            )
    finally:
        GW._written_deviations = original_dev
        GW._make_wave = original_wave
    return Run(score, captured, deviations, waves)


def note_map(score):
    out = {}
    for part in PARTS:
        for event in getattr(score, part):
            if event.midi is None or event.velocity is None:
                continue
            key = (part, event.bar, round(float(event.beat), 4), int(event.midi))
            # Keep the loudest duplicate if two notes coincide.
            out[key] = max(out.get(key, 0), int(event.velocity))
    return out


def velocity_stats(values):
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "min": ordered[0],
        "max": ordered[-1],
        "p05": ordered[max(0, int(0.05 * (len(ordered) - 1)))],
        "p95": ordered[int(0.95 * (len(ordered) - 1))],
    }


def dev_limits(ensemble: str, deviations: dict) -> dict[str, int | None]:
    """Profile headroom per row. `None` means the row has no entry in PROFILES."""
    return {
        row: (profile.d_hi if profile is not None else None)
        for row in deviations
        for profile in (GW.profile_for(ensemble, row),)
    }


async def audit_case(symbol, span, ensemble, mode, results):
    plan = await plan_span(symbol, span, variant="guitar", ensemble=ensemble)
    for index, movement in enumerate(plan.movements):
        new = run_score(symbol, span, index, movement, ensemble, mode=mode)
        old = run_score(symbol, span, index, movement, ensemble, mode="none")

        ctx = new.captured.get("ctx")
        patterns = new.captured.get("patterns") or []
        if ctx is None:
            continue
        new_notes = note_map(new.score)
        old_notes = note_map(old.score)
        common = sorted(set(new_notes) & set(old_notes))

        per_voice: dict[tuple[str, str], list[int]] = defaultdict(list)
        per_voice_new: dict[tuple[str, str], list[int]] = defaultdict(list)
        per_voice_old: dict[tuple[str, str], list[int]] = defaultdict(list)
        for key in common:
            part, bar, beat, midi = key
            pattern = GP._bar_pattern(ctx, bar, patterns)
            delta = new_notes[key] - old_notes[key]
            per_voice[(pattern, part)].append(delta)
            per_voice_new[(pattern, part)].append(new_notes[key])
            per_voice_old[(pattern, part)].append(old_notes[key])

        wave_rows = []
        for key in sorted(set(new.waves) & set(old.waves)):
            n = new.waves[key]
            o = old.waves[key]
            wave_rows.append(
                {
                    "wave": key,
                    "c_lo_new": round(n["c_lo"], 3),
                    "c_hi_new": round(n["c_hi"], 3),
                    "c_lo_old": round(o["c_lo"], 3),
                    "c_hi_old": round(o["c_hi"], 3),
                    "d_c_hi": round(n["c_hi"] - o["c_hi"], 3),
                    "d_c_lo": round(n["c_lo"] - o["c_lo"], 3),
                    "deviation": n["deviation"],
                }
            )

        results.append(
            {
                "case": f"{symbol} {span} {ensemble}",
                "symbol": symbol,
                "span": span,
                "ensemble": ensemble,
                "movement": index,
                "bars": new.score.bars,
                "deviations": {
                    row: (value.d_lo, value.d_hi_diagnostic)
                    for row, value in new.deviations.items()
                },
                "dev_limits": dev_limits(ensemble, new.deviations),
                "waves": wave_rows,
                "per_voice": {
                    f"{pattern}|{part}": {
                        "delta": velocity_stats(values),
                        "new": velocity_stats(per_voice_new[(pattern, part)]),
                        "old": velocity_stats(per_voice_old[(pattern, part)]),
                    }
                    for (pattern, part), values in per_voice.items()
                },
            }
        )
    print(f"done {symbol} {span} {ensemble}", file=sys.stderr)


def summarize(results):
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {"delta": [], "new": [], "old": []})
    dev_rows: dict[str, list[tuple[float, float, int | None]]] = defaultdict(list)
    wave_hi: dict[str, list[float]] = defaultdict(list)
    for item in results:
        for key, stats in item["per_voice"].items():
            pattern, part = key.split("|", 1)
            n = stats["delta"].get("n", 0)
            if n:
                agg[(pattern, part)]["delta"].append(
                    (n, stats["delta"]["mean"], stats["delta"]["max"])
                )
                agg[(pattern, part)]["new"].append(
                    (n, stats["new"]["mean"], stats["new"]["max"])
                )
                agg[(pattern, part)]["old"].append(
                    (n, stats["old"]["mean"], stats["old"]["max"])
                )
        for row, (lo, hi) in item["deviations"].items():
            dev_rows[row].append((lo, hi, item["dev_limits"].get(row)))
        for wave in item["waves"]:
            pattern = wave["wave"][2]
            wave_hi[pattern].append(wave["d_c_hi"])

    print("\n## Tide top change by pattern")
    print("| pattern | waves | mean Δc_hi | max Δc_hi |")
    print("|---|---:|---:|---:|")
    for pattern, values in sorted(wave_hi.items(), key=lambda kv: -statistics.mean(kv[1])):
        print(
            f"| `{pattern}` | {len(values)} | "
            f"{statistics.mean(values):+.2f} | {max(values):+.2f} |"
        )

    print("\n## Note delta by pattern and voice (weighted)")
    print("| pattern | voice | notes | mean Δ | max Δ | mean new | max new | mean old | max old |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    rows = []
    for (pattern, part), buckets in agg.items():
        def weighted(items, index):
            total = sum(item[0] for item in items)
            return None if not total else sum(item[0] * item[index] for item in items) / total

        n = sum(item[0] for item in buckets["delta"])
        rows.append(
            (
                pattern,
                part,
                n,
                weighted(buckets["delta"], 1),
                max(item[2] for item in buckets["delta"]),
                weighted(buckets["new"], 1),
                max(item[2] for item in buckets["new"]),
                weighted(buckets["old"], 1),
                max(item[2] for item in buckets["old"]),
            )
        )
    for row in sorted(rows, key=lambda item: (-item[3], item[0], item[1])):
        pattern, part, n, mean_d, max_d, mean_new, max_new, mean_old, max_old = row
        print(
            f"| `{pattern}` | {part} | {n} | {mean_d:+.2f} | {max_d:+d} | "
            f"{mean_new:.1f} | {max_new} | {mean_old:.1f} | {max_old} |"
        )

    print("\n## Measured deviations by row")
    print("| row | samples | profile d_hi | d_lo | d_hi | samples below profile |")
    print("|---|---:|---:|---:|---:|---:|")
    for row, values in sorted(dev_rows.items()):
        lo = statistics.median(v[0] for v in values)
        hi = statistics.median(v[1] for v in values)
        limits = [v[2] for v in values if v[2] is not None]
        limit_text = "—" if not limits else f"{statistics.median(limits):+.0f}"
        trimmed = sum(1 for _, h, cap in values if cap is not None and h < cap)
        print(f"| `{row}` | {len(values)} | {limit_text} | {lo:+.0f} | {hi:+.0f} | {trimmed} |")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="tmp/p1_audit.json")
    parser.add_argument(
        "--mode",
        choices=("current", "before"),
        default="current",
        help="current = trim d_lo only; before = old trim of both tails",
    )
    args = parser.parse_args()
    results = []
    for symbol, span in CASES:
        for ensemble in ENSEMBLES:
            try:
                await audit_case(symbol, span, ensemble, args.mode, results)
            except Exception as error:  # noqa: BLE001
                print(f"skip {symbol} {span} {ensemble}: {error}", file=sys.stderr)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    summarize(results)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
