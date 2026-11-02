"""Reproduce the DFI v4 re-baseline without changing the production code.

Usage (from backend/):
  .venv/bin/python scripts/dfi_probe.py ACB 3M guitar torroba
  .venv/bin/python scripts/dfi_probe.py ACB 3M ambient classic --source grid
  .venv/bin/python scripts/dfi_probe.py ACB 3M symphony classic

It prints, per movement:

  v3           the score the server serves today
  anchors      Motion read from price-trace attacks, no eps filter
  anchors+eps  the planned v4 rule (attacks + the documented phrase eps)
  grid+eps     the same eps rule on the eighth grid (ambient reference)

The script is read-only: it calls `plan_span` and `_movement_score`, never the
renderer or the audio cache.  It does not model the symphony Flute fill; that
needs the production trace change and is measured in the implementation PR.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

sys.path[:0] = ["/Users/andynguyen/Projects/VStock/backend"]

from app.services import dfi as dfi_service  # noqa: E402
from app.services.spans import plan_span  # noqa: E402
from app.sonify import dfi as D  # noqa: E402


def motion_with_eps(points, eps: float):
    """`dfi._motion` with the documented eps filter.

    The production copy currently filters with `_EPS = 1e-9`; this mirrors the
    planned change so the probe can measure it before the code lands.
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
        return None, 0.0
    if all(abs(value - y[0]) <= D._EPS for value in y):
        return 0.0, float(len(pairs))
    tau = D.kendall_tau_b(x, y)
    if tau is None:
        return None, 0.0
    return max(0.0, tau), float(len(pairs))


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
    by_window = {}
    for point in D._grid(
        score, variant, pitch_at, frozenset(score.frame_bars), windows
    ):
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
    total = weight = 0.0
    for index in sorted(by_window):
        if eps_mode:
            value, count = motion_with_eps(by_window[index], eps_by_window[index])
        else:
            value, count, _low = D._motion(
                by_window[index], eps_by_window.get(index, D._EPS)
            )
        if value is not None:
            total += value * count
            weight += count
    return None if not weight else total / weight


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


async def probe(symbol: str, span: str, variant: str, ensemble: str, source: str) -> None:
    plan = await plan_span(symbol, span, variant=variant, ensemble=ensemble)
    print(f"# {symbol} {span} {variant}/{ensemble}  source={source}")
    print()
    print("| movement | v3 score | v3 motion | anchors | anchors+eps | grid+eps | score v4 |")
    print("|---|---:|---:|---:|---:|---:|---:|")

    for index, movement in enumerate(plan.movements):
        score = dfi_service._movement_score(
            symbol, span, index, movement, variant, ensemble, humanize=True
        )
        base = D.compute(score, variant=variant, ensemble=ensemble)
        if base is None:
            print(f"| {index} | — | — | — | — | — | — |")
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
        print(
            f"| {index} | {base.score:.1f} | {base.motion:.3f} | "
            f"{fmt(anchor)} | {fmt(anchor_eps)} | {fmt(grid_eps)} | "
            f"{'—' if score_v4 is None else f'{score_v4:.1f}'} |"
        )

    print()
    print(
        "`anchors` = price notes only, no eps. `anchors+eps` = planned "
        "Motion. `grid+eps` = ambient reference. `score v4` uses the "
        "selected source."
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
    args = parser.parse_args()
    asyncio.run(probe(args.symbol, args.span, args.variant, args.ensemble, args.source))


if __name__ == "__main__":
    main()
