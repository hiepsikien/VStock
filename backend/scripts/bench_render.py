"""Measure every phase of the span render pipeline on real data.

The probe plans a real span, then renders the requested movements with a cold
audio cache. It wraps the production functions so each phase is timed:

  plan -> compose -> humanize -> DFI -> MusicXML -> MuseScore -> color
       -> peaks -> AAC encode -> publish/read

Usage (from backend/):

  .venv/bin/python scripts/bench_render.py ACB 1M 0 1 2 3
  .venv/bin/python scripts/bench_render.py ACB 1W 0 --variant symphony
  .venv/bin/python scripts/bench_render.py ACB 3M 0 --fresh

`--fresh` deletes the audio root before rendering, so every movement is cold.
Without it, an existing file is served from cache in a fraction of a ms.

The probe calls `plan_span`, so it fetches live OHLC when the local store is
cold. It never writes the production audio cache unless `--root` points there.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]

from app.services.spans import plan_span  # noqa: E402
from app.sonify import audio  # noqa: E402

timings: dict[str, float] = {}


def timed(name: str, fn):
    def wrapper(*args, **kwargs):
        started = time.monotonic()
        try:
            return fn(*args, **kwargs)
        finally:
            timings[name] = timings.get(name, 0.0) + time.monotonic() - started

    return wrapper


def install_probes() -> None:
    audio._compose = timed("compose", audio._compose)
    audio.humanize_score = timed("humanize", audio.humanize_score)
    audio.compute_dfi = timed("dfi", audio.compute_dfi)
    audio.score_to_musicxml = timed("musicxml", audio.score_to_musicxml)
    audio._color_for_export = timed("color", audio._color_for_export)
    audio.waveform_peaks_with_level = timed("peaks", audio.waveform_peaks_with_level)
    audio._transcode_m4a = timed("encode", audio._transcode_m4a)


def timed_exporter(xml_path: Path, wav_path: Path) -> None:
    started = time.monotonic()
    try:
        audio.musescore_export(xml_path, wav_path)
    finally:
        timings["musescore"] = timings.get("musescore", 0.0) + time.monotonic() - started


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol")
    parser.add_argument("span", choices=("1W", "1M", "3M", "1Y"))
    parser.add_argument("indexes", nargs="*", type=int, default=[0])
    parser.add_argument("--variant", default="guitar")
    parser.add_argument("--ensemble", default="classic")
    parser.add_argument("--root", type=Path, default=Path("tmp/bench-audio"))
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--no-humanize", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    if args.fresh:
        production = Path(os.environ.get("VSTOCK_AUDIO_DIR", "var/audio")).resolve()
        if args.root.resolve() == production:
            raise SystemExit("refusing --fresh on the production audio root")
        if args.root.exists():
            shutil.rmtree(args.root)
    args.root.mkdir(parents=True, exist_ok=True)

    install_probes()
    humanize = not args.no_humanize
    color = not args.no_color

    started = time.monotonic()
    plan = await plan_span(symbol, args.span, args.variant, args.ensemble)
    plan_sec = time.monotonic() - started
    print(
        json.dumps(
            {
                "symbol": symbol,
                "span": args.span,
                "variant": args.variant,
                "ensemble": args.ensemble,
                "as_of": plan.as_of.isoformat(),
                "movements": len(plan.movements),
                "plan_sec": round(plan_sec, 3),
            }
        ),
        flush=True,
    )

    store = audio.RecapStore(root=args.root, exporter=timed_exporter)
    indexes = args.indexes or [0]
    for index in indexes:
        movement = plan.movements[index]
        timings.clear()
        started = time.monotonic()
        asset = store.ensure_movement(
            symbol,
            args.span,
            index,
            args.variant,
            movement,
            None,
            args.ensemble,
            humanize,
            color,
        )
        total = time.monotonic() - started
        print(
            json.dumps(
                {
                    "index": index,
                    "label": movement.label,
                    "bars": movement.candle_count,
                    "bpm": movement.spec.bpm,
                    "meter": f"{movement.spec.meter.beats}/{movement.spec.meter.beat_type}",
                    "audio_sec": round(asset.duration_sec, 2),
                    "render_sec": round(total, 2),
                    "phases": {key: round(value, 3) for key, value in timings.items()},
                    "residual_sec": round(total - sum(timings.values()), 3),
                }
            ),
            flush=True,
        )


asyncio.run(main())
