"""Benchmark Markov harmony vs fixed loops on saved session JSONs and write MusicXML."""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "out"
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.sonify.chords import SEVENTHS, TRIADS
from app.sonify.form import plan_slots
from app.sonify.model import Bar
from app.sonify.musicxml import score_to_musicxml
from app.sonify.quantize import c_major_scale, price_to_scale_index, resample
from app.sonify.render import (
    EIGHTHS_PER_BAR,
    STRONG_EIGHTHS,
    _quantize_strong_beats,
    assign_source_bars,
    render,
)

AUCTION_LABELS = frozenset({"09:00", "09:15", "14:30", "14:45"})


def _load_session_bars(path: Path) -> tuple[str, str, list[Bar]]:
    payload = json.loads(path.read_text())
    symbol = payload["symbol"]
    day = payload["day"]
    bars = [
        Bar(
            close=float(row["close"]),
            volume=float(row["volume"]),
            ma20=float(row["ma20"]),
            auction=row["t"] in AUCTION_LABELS,
        )
        for row in payload["bars"]
    ]
    return symbol, day, bars


def _raw_eighths(bars: list[Bar], scale: tuple[int, ...]) -> list[int]:
    groups = assign_source_bars(len(bars))
    low = min(bar.close for bar in bars)
    high = max(bar.close for bar in bars)
    held = bars[0].close
    raw: list[int] = []
    for group in groups:
        closes = [bars[index].close for index in group] if group else [held]
        held = closes[-1]
        for close in resample(closes, EIGHTHS_PER_BAR):
            raw.append(scale[price_to_scale_index(close, low, high, len(scale))])
    return raw


def main() -> None:
    scale = c_major_scale()
    for json_path in sorted(OUT_DIR.glob("*_*.json")):
        symbol, day, bars = _load_session_bars(json_path)
        title = f"{symbol} {day} 1-Day Recap"
        score = render(bars, title=title)
        xml_path = OUT_DIR / f"{symbol}_{day}_harmony.musicxml"
        xml_path.write_text(score_to_musicxml(score))

        raw = _raw_eighths(bars, scale)
        markov_chord_at = {bar: slot.chord for slot in score.slots for bar in slot.bars()}
        fixed_slots = plan_slots(score.regimes)
        fixed_chord_at = {bar: slot.chord for slot in fixed_slots for bar in slot.bars()}

        markov_snapped = _quantize_strong_beats(raw, markov_chord_at, scale)
        fixed_snapped = _quantize_strong_beats(raw, fixed_chord_at, scale)

        strong_positions = [bar * EIGHTHS_PER_BAR + e for bar in range(30) for e in STRONG_EIGHTHS]
        fixed_strong_bends = sum(1 for pos in strong_positions if fixed_snapped[pos] != raw[pos])
        markov_strong_bends = sum(1 for pos in strong_positions if markov_snapped[pos] != raw[pos])
        fixed_all_bends = sum(1 for a, b in zip(raw, fixed_snapped) if a != b)
        markov_all_bends = sum(1 for a, b in zip(raw, markov_snapped) if a != b)

        triad_bars = sum(1 for b in range(30) if markov_chord_at[b] in TRIADS)
        seventh_bars = sum(1 for b in range(30) if markov_chord_at[b] in SEVENTHS)
        slot_summary = ", ".join(f"{s.chord.name}({s.length})" for s in score.slots)
        print(
            f"{symbol}_{day} (regimes={score.regimes}): "
            f"strong_bends {fixed_strong_bends}/60 -> {markov_strong_bends}/60 | "
            f"all_bends {fixed_all_bends}/240 -> {markov_all_bends}/240 | "
            f"triads={triad_bars}/30, 7ths={seventh_bars}/30"
        )
        print(f"  slots: {slot_summary}")


if __name__ == "__main__":
    main()
