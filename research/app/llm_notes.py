"""Replay one industry note on the first session of each month from 2023-02-14.

`python -m app.llm_notes --dry-run` builds every prompt and does not call the model.
Without that flag, months already stored are kept and the rest are sent to Gemini.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from app import db
from app.industries import CREDIT_INDUSTRIES, LEAD_SERIES, gated_industries, industry_of, members
from app.industry_note import (
    LABELS,
    contain_rate,
    month_note_days,
    monthly_prompt,
    note_beats_gate,
    parse_picks,
    shift_months,
)
from app.industry_report import _credit, _load, _universe_for_year
from app.industry_screen import (
    CONFIRM_END,
    OPERABLE_START,
    average_by_day,
    dated_returns,
    find_runs,
    is_open,
    previous_session,
    rolling_compound,
)
from app.pattern import market_regime


def _load_env() -> None:
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _pct(value: float | None) -> str:
    if value is None:
        return "chưa có số"
    return f"{value * 100:+.1f}%"


def month_snapshot(
    note_day: str,
    bars: dict,
    market: dict,
    index_days: list[str],
    year_members: dict,
    credit_by_day: dict,
) -> tuple[str, dict[str, str], list[str]] | None:
    """Prompt inputs for one note day. Every figure ends on the previous session."""
    yesterday = previous_session(index_days, note_day)
    if yesterday is None:
        return None
    anchor, universe = year_members.get(int(note_day[:4]), (None, []))
    if anchor is None or note_day < anchor or len(universe) < 3:
        return None
    index = [bar for bar in bars["VNINDEX"] if bar["trade_date"] <= yesterday]
    index_return = rolling_compound(dated_returns(index)).get(yesterday)
    regime = market_regime(index)
    credit = credit_by_day.get(yesterday)
    oil_bars = [
        {"trade_date": day, "close": value}
        for day, value in market.get("OIL", [])
        if day <= yesterday
    ]
    oil_return = rolling_compound(dated_returns(oil_bars)).get(yesterday) if oil_bars else None
    known = {
        "VN-Index 60 phiên": _pct(index_return),
        "VN-Index so với MA200": "trên MA200" if regime.open else "dưới MA200",
        "Tăng trưởng dư nợ ngân hàng, quý đã công bố": _pct(credit),
        "Dầu 60 phiên": _pct(oil_return),
    }
    numeric: list[str] = []
    for industry in gated_industries(universe):
        series = [
            dated_returns([bar for bar in bars[symbol] if bar["trade_date"] <= yesterday])
            for symbol in members(industry, universe)
            if symbol in bars
        ]
        own = rolling_compound(average_by_day(series)).get(yesterday)
        excess = None if own is None or index_return is None else own - index_return
        lead_return = oil_return if industry in LEAD_SERIES else None
        bits = [
            f"lợi suất 60 phiên {_pct(own)}",
            f"so với VN-Index {_pct(excess)}",
            f"{len(members(industry, universe))} mã",
        ]
        if industry in LEAD_SERIES:
            bits.append(f"dầu 60 phiên {_pct(oil_return)}")
        if industry in CREDIT_INDUSTRIES:
            bits.append(f"tăng trưởng dư nợ {_pct(credit)}")
        known[LABELS[industry]] = ", ".join(bits)
        if is_open(
            industry,
            universe,
            excess=excess,
            lead_return=lead_return,
            credit_growth=credit,
            regime_open=regime.open,
        ):
            numeric.append(industry)
    return monthly_prompt(note_day, known), known, numeric


def _runs_after(bars: dict, universe: list[str], start: str, end: str) -> list[str]:
    found = []
    for symbol in universe:
        if symbol not in bars:
            continue
        industry = industry_of(symbol)
        if industry is None:
            continue
        for day, _index, _change in find_runs(bars[symbol], start, end):
            if start < day <= end:
                found.append(industry)
    return found


def score_stored(
    notes: list[dict],
    bars: dict,
    market: dict,
    index_days: list[str],
    year_members: dict,
    credit_by_day: dict,
) -> list[str]:
    """Compare each stored note with runs that start in the following three months."""
    last = index_days[-1]
    lines = []
    note_hits = gate_hits = scored = 0
    for row in notes:
        note_day = row["as_of"]
        horizon = shift_months(note_day, 3)
        if horizon > last:
            lines.append(f"{note_day}: chưa đủ ba tháng sau để chấm.")
            continue
        snapshot = month_snapshot(note_day, bars, market, index_days, year_members, credit_by_day)
        if snapshot is None:
            continue
        _prompt, _known, numeric = snapshot
        universe = year_members[int(note_day[:4])][1]
        runs = _runs_after(bars, universe, note_day, horizon)
        picks = set(parse_picks(row["response"]))
        note_rate = contain_rate(runs, picks)
        gate_rate = contain_rate(runs, set(numeric))
        scored += 1
        note_hits += note_rate
        gate_hits += gate_rate
        lines.append(
            f"{note_day}: {len(runs)} đợt trong ba tháng sau, "
            f"nhận định {note_rate:.0%}, cổng số {gate_rate:.0%}."
        )
    if scored:
        note_mean = note_hits / scored
        gate_mean = gate_hits / scored
        verdict = (
            "Nhận định chứa đợt tăng thường hơn cổng số."
            if note_beats_gate(note_mean, gate_mean)
            else "Nhận định chưa thường hơn cổng số, nên chưa được chọn ngành."
        )
        lines.append(
            f"Trung bình {scored} tháng đã chấm: nhận định {note_mean:.0%}, cổng số {gate_mean:.0%}. {verdict}"
        )
    return lines


async def replay(dry_run: bool) -> None:
    _load_env()
    bars, ratios, market = _load()
    index_days = [bar["trade_date"] for bar in bars["VNINDEX"]]
    credit_by_day = _credit(ratios, index_days)
    year_members = {
        year: _universe_for_year(year, bars, ratios, index_days) for year in range(2023, 2027)
    }
    days = month_note_days(index_days, OPERABLE_START, index_days[-1] if index_days else None)
    ready = []
    for day in days:
        snapshot = month_snapshot(day, bars, market, index_days, year_members, credit_by_day)
        if snapshot is not None:
            ready.append((day, snapshot))
    print(f"Tháng từ {OPERABLE_START} đến {CONFIRM_END}: {len(ready)} nhận định dựng được.")
    if ready:
        print(f"Đầu {ready[0][0]}, cuối {ready[-1][0]}.")
    if dry_run:
        print("Dry-run: không gọi mô hình.")
        return
    from app.industry_note import api_key

    key = api_key()
    model = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    if not key:
        print("Chưa có khóa Gemini. Các prompt đã dựng được, lượt gọi chưa chạy.")
        return
    from google import genai

    await db.init_db()
    stored = {row["as_of"] for row in await db.industry_notes()}
    client = genai.Client(api_key=key)
    for day, (prompt, _known, _numeric) in ready:
        if day in stored:
            continue
        response = client.models.generate_content(model=model, contents=prompt)
        text = (response.text or "").strip()
        picks = ",".join(parse_picks(text))
        await db.save_industry_note(day, prompt, text, picks)
        print(day, picks or "(không chọn)")
    notes = await db.industry_notes()
    for line in score_stored(notes, bars, market, index_days, year_members, credit_by_day):
        print(line)
    await db.close_db()


def main() -> None:
    asyncio.run(replay("--dry-run" in sys.argv))


if __name__ == "__main__":
    main()
