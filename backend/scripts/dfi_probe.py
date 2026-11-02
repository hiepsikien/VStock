"""Reproduce the DFI v4 re-baseline.

Usage (from backend/):
  .venv/bin/python scripts/dfi_probe.py ACB 3M guitar torroba
  .venv/bin/python scripts/dfi_probe.py ACB 3M ambient classic --source grid
  .venv/bin/python scripts/dfi_probe.py ACB 3M guitar torroba --classify

It prints, per movement:

  v4 score       the score the server computes today
  v4 motion      the Motion component the server computes today
  anchors        Motion read from price-trace attacks, no eps filter
  anchors+eps    the documented window-eps rule on the attacks
  grid+eps       the same eps rule on the eighth grid
  counterfactual re-blend with `--source` (anchors or grid)

`--classify` adds the pair tables: raw pairs, pairs after dropping (0,0),
holds, ornaments, and per-window tau.

The probe never writes the renderer or the audio cache.  It does call
`plan_span`, which fetches live OHLC when the local store is cold, so the
numbers depend on the data date.  The header prints `as_of`; record it with
any table copied into the plan.  The plan's §7 tables are the historical
pre-v4 baseline; this probe reports v4.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]

from app.services import dfi as dfi_service  # noqa: E402
from app.services.spans import plan_span  # noqa: E402
from app.sonify import dfi as D  # noqa: E402

ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def motion_stats(points, eps: float):
    """Unclamped `dfi._motion` with a configurable price filter.

    Returns `(tau_or_none, pair_count)`.  `_motion` clamps at 0, which hides
    the negative taus that explain a 0.000 component; the probe needs them.
    """
    usable = [point for point in points if point.pitch is not None]
    pairs = list(zip(usable, usable[1:]))
    pairs = [
        (left, right)
        for left, right in pairs
        if abs(right.price - left.price) > eps
        or abs((right.pitch or 0.0) - (left.pitch or 0.0)) > D._EPS
    ]
    x = [abs(right.price - left.price) for left, right in pairs]
    y = [abs(right.pitch - left.pitch) for left, right in pairs]
    if len(pairs) < 4 or all(abs(value - x[0]) <= D._EPS for value in x):
        anchors = [usable[0]] if usable else []
        for point in usable[1:]:
            if point.pitch != anchors[-1].pitch:
                anchors.append(point)
        if len(anchors) >= 2:
            pairs = list(zip(anchors, anchors[1:]))
            x = [abs(right.price - left.price) for left, right in pairs]
            y = [abs(right.pitch - left.pitch) for left, right in pairs]
    if len(pairs) < 4 or all(abs(value - x[0]) <= D._EPS for value in x):
        return None, 0
    if all(abs(value - y[0]) <= D._EPS for value in y):
        return 0.0, len(pairs)
    tau = D.kendall_tau_b(x, y)
    return tau, len(pairs)


def anchor_points(score, windows, epb):
    """One point per price-note attack, frame bars excluded, grouped by window."""
    frame = frozenset(score.frame_bars)
    points = []
    seen = set()
    for point in score.price_trace:
        if point.pitch is None or point.bar in frame:
            continue
        window = D._window_of(windows, point.bar)
        if window is None:
            continue
        eighth = point.bar * epb + int(round(point.beat * 2))
        if eighth in seen:
            continue
        seen.add(eighth)
        points.append(
            D._Point(
                eighth=eighth,
                price=point.price,
                pitch=point.pitch,
                window=window,
                phrase=D._phrase_of(score.phrases, eighth),
            )
        )
    points.sort(key=lambda item: item.eighth)
    by_window = {}
    for point in D._deregister(points):
        by_window.setdefault(point.window, []).append(point)
    return by_window


def grid_points(score, variant, windows, pitch_at):
    """`compute` does `_deregister(_grid(...))`; mirror it exactly."""
    points = D._deregister(
        D._grid(score, variant, pitch_at, frozenset(score.frame_bars), windows)
    )
    by_window = {}
    for point in points:
        by_window.setdefault(point.window, []).append(point)
    return by_window


def blend(base, motion: float | None) -> float | None:
    """Re-blend the published components with a new Motion value."""
    parts = [
        (D.WEIGHT_SHAPE, base.shape),
        (D.WEIGHT_MOTION, motion),
        (D.WEIGHT_STRUCTURE, base.structure),
        (D.WEIGHT_RESOLUTION, base.resolution),
        (D.WEIGHT_VOLUME, base.volume),
    ]
    parts = [(weight, value) for weight, value in parts if value is not None]
    if not parts:
        return None
    value = sum(weight * item for weight, item in parts) / sum(
        weight for weight, _item in parts
    )
    return max(0.0, min(100.0, 100.0 * value * base.coverage))


def all_motion(by_window, eps_by_window, *, eps_mode: bool) -> float | None:
    """Average Motion over windows.

    `eps_mode=False` is the counterfactual "no eps filter": it runs the same
    stats with the tiny `_EPS` threshold, so the probe still shows the
    before/after effect now that production `_motion` always takes eps.
    """
    total = weight = 0.0
    for index in sorted(by_window):
        if eps_mode:
            # Production path, so the probe stays in parity with `_motion`.
            value, count, _low = D._motion(
                by_window[index], eps_by_window[index]
            )
        else:
            # Counterfactual: the same stats with the tiny threshold.
            tau, count = motion_stats(by_window[index], D._EPS)
            value = None if tau is None else max(0.0, tau)
        if value is not None:
            total += value * count
            weight += count
    return None if not weight else total / weight


def classify_grid(by_window, eps_by_window, *, movement: str, windows, epb: int) -> None:
    """The §1.1 table: where Motion's evidence goes, on the eighth grid."""
    print()
    print(f"### movement {movement} — grid pairs")
    print(
        "| window | steps | usable pairs | after (0,0) | hold | ornament | "
        "1-tick | eps | tau |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for index in sorted(by_window):
        points = [point for point in by_window[index] if point.pitch is not None]
        raw = list(zip(points, points[1:]))
        kept = [
            (left, right)
            for left, right in raw
            if abs(right.price - left.price) > D._EPS
            or abs((right.pitch or 0.0) - (left.pitch or 0.0)) > D._EPS
        ]
        holds = sum(
            1
            for left, right in kept
            if abs(right.price - left.price) > D._EPS
            and abs((right.pitch or 0.0) - (left.pitch or 0.0)) <= D._EPS
        )
        ornaments = sum(
            1
            for left, right in kept
            if abs(right.price - left.price) <= D._EPS
            and abs((right.pitch or 0.0) - (left.pitch or 0.0)) > D._EPS
        )
        one_tick = sum(
            1
            for left, right in kept
            if abs(abs(right.price - left.price) - 0.05) <= 1e-9
        )
        value, _count = motion_stats(by_window[index], D._EPS)
        start, end = windows[index]
        # Windows are contiguous bar spans today; if that changes, derive
        # `steps` from the actual eighth range instead.
        steps = (end - start) * epb - 1
        eps = eps_by_window.get(index, D._EPS)
        print(
            f"| {index} | {steps} | {len(raw)} | {len(kept)} | {holds} | "
            f"{ornaments} | {one_tick} | {eps:.4f} | "
            f"{'—' if value is None else f'{value:.3f}'} |"
        )


def classify_anchors(by_window, eps_by_window, *, movement: str) -> None:
    """The minimalist check: anchor pairs and tau before/after the eps filter."""
    print()
    print(f"### movement {movement} — anchor pairs")
    print("| window | pairs | hold | ornament | 1-tick | tau | pairs+eps | tau+eps |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for index in sorted(by_window):
        points = [point for point in by_window[index] if point.pitch is not None]
        pairs = list(zip(points, points[1:]))
        holds = sum(
            1
            for left, right in pairs
            if abs(right.price - left.price) > D._EPS
            and abs((right.pitch or 0.0) - (left.pitch or 0.0)) <= D._EPS
        )
        ornaments = sum(
            1
            for left, right in pairs
            if abs(right.price - left.price) <= D._EPS
            and abs((right.pitch or 0.0) - (left.pitch or 0.0)) > D._EPS
        )
        one_tick = sum(
            1
            for left, right in pairs
            if abs(abs(right.price - left.price) - 0.05) <= 1e-9
        )
        value, _count = motion_stats(by_window[index], D._EPS)
        filtered, filtered_count = motion_stats(
            by_window[index], eps_by_window.get(index, D._EPS)
        )
        print(
            f"| {index} | {len(pairs)} | {holds} | {ornaments} | {one_tick} | "
            f"{'—' if value is None else f'{value:.3f}'} | {filtered_count} | "
            f"{'—' if filtered is None else f'{filtered:.3f}'} |"
        )


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


async def probe(
    symbol: str, span: str, variant: str, ensemble: str, source: str, show_classify: bool
) -> None:
    plan = await plan_span(symbol, span, variant=variant, ensemble=ensemble)
    print(f"# {symbol} {span} {variant}/{ensemble}  source={source}")
    print(f"as_of: {plan.as_of.isoformat()}  (numbers depend on this date)")
    print()
    print("| movement | v4 score | v4 motion | anchors | anchors+eps | grid+eps | counterfactual |")
    print("|---|---:|---:|---:|---:|---:|---:|")

    rows: list[dict] = []
    details: list[dict] = []
    for index, movement in enumerate(plan.movements):
        roman = ROMAN[index] if index < len(ROMAN) else str(index + 1)
        score = dfi_service._movement_score(
            symbol, span, index, movement, variant, ensemble, humanize=True
        )
        base = D.compute(score, variant=variant, ensemble=ensemble)
        if base is None:
            rows.append({"index": index, "roman": roman, "base": None})
            continue

        epb = max(1, int(round(score.bar_beats * 2)))
        windows = list(score.analysis_windows) or [(0, score.bars)]
        lookup = D._PitchLookup(score.price_trace, score.bar_beats)
        grid = grid_points(
            score, variant, windows, lambda position: lookup.at(position)
        )
        closes = list(score.source_closes) or list(score.price_eighths)
        common = dict(
            session_low=min(closes),
            session_high=max(closes),
            median_close=D.median(closes),
        )
        eps_by_window = {
            window: D._phrase_eps(chunk, **common)
            for window, chunk in (
                (chunk[0].window, chunk) for chunk in grid.values() if chunk
            )
        }
        anchors = anchor_points(score, windows, epb)

        anchor = all_motion(anchors, eps_by_window, eps_mode=False)
        anchor_eps = all_motion(anchors, eps_by_window, eps_mode=True)
        grid_eps = all_motion(grid, eps_by_window, eps_mode=True)
        shown = anchor_eps if source == "anchors" else grid_eps
        score_v4 = blend(base, shown)
        rows.append(
            {
                "index": index,
                "roman": roman,
                "base": base,
                "anchor": anchor,
                "anchor_eps": anchor_eps,
                "grid_eps": grid_eps,
                "score_v4": score_v4,
            }
        )
        details.append(
            {
                "index": index,
                "roman": roman,
                "grid": grid,
                "anchors": anchors,
                "eps_by_window": eps_by_window,
                "windows": windows,
                "epb": epb,
            }
        )

    # Main table first so it can be copied into the plan without interleaving.
    for row in rows:
        label = f"{row['index']} ({row['roman']})"
        if row["base"] is None:
            print(f"| {label} | — | — | — | — | — | — |")
            continue
        score_v4 = row["score_v4"]
        print(
            f"| {label} | {row['base'].score:.1f} | {row['base'].motion:.3f} | "
            f"{fmt(row['anchor'])} | {fmt(row['anchor_eps'])} | "
            f"{fmt(row['grid_eps'])} | "
            f"{'—' if score_v4 is None else f'{score_v4:.1f}'} |"
        )

    if show_classify:
        for detail in details:
            label = f"{detail['index']} ({detail['roman']})"
            classify_grid(
                detail["grid"],
                detail["eps_by_window"],
                movement=label,
                windows=detail["windows"],
                epb=detail["epb"],
            )
            classify_anchors(
                detail["anchors"], detail["eps_by_window"], movement=label
            )

    print()
    print(
        "`anchors` = price notes only, no eps. `anchors+eps` = the documented "
        "window-eps rule. `grid+eps` = eighth grid reference. "
        "`counterfactual` re-blends with `--source`."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", nargs="?", default="ACB")
    parser.add_argument("span", nargs="?", default="3M")
    parser.add_argument("variant", nargs="?", default="guitar")
    parser.add_argument("ensemble", nargs="?", default="torroba")
    parser.add_argument(
        "--source",
        choices=("anchors", "grid"),
        default="anchors",
        help="Motion source for the v4 score column",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="print the §1.1 pair table after each movement",
    )
    args = parser.parse_args()
    asyncio.run(
        probe(
            args.symbol,
            args.span,
            args.variant,
            args.ensemble,
            args.source,
            args.classify,
        )
    )


if __name__ == "__main__":
    main()
