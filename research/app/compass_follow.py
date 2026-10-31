"""LNST và giá bốn mã sau cú sốc dầu. Không đổi cửa spread.

LNST là khoản 23000, mức của quý kết quả so với quý trước cú sốc, chia doanh thu quý
trước cú sốc. Giá là lợi suất từ phiên công bố quý trước cú sốc đến phiên công bố quý
kết quả. Công bố ở đây là ngày kết thúc quý cộng 45 ngày, đúng đồng hồ của sổ.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import httpx

from app.compass import (
    LAG_HORIZONS,
    NET_INCOME_ITEM,
    NET_REVENUE_ITEM,
    SCORED_NAMES,
    SELECT_END,
    npat_projection_pairs,
    oil_shock,
    ols,
    price_projection_pairs,
)
from app.compass_report import _closes, _statement
from app.config import RESEARCH_HISTORY_START
from app.ingest import fetch_bars, fetch_macro

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "compass_follow.md"


def _fit(pairs: list[tuple[float, float]]) -> tuple[float | None, int]:
    if len(pairs) < 2:
        return None, len(pairs)
    slope = ols([oil for oil, _delta in pairs], [delta for _oil, delta in pairs])
    return slope, len(pairs)


async def load() -> dict:
    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        macro = await fetch_macro(client, start=RESEARCH_HISTORY_START)
        oil = macro.get("OIL") or []
        books = {}
        for symbol in SCORED_NAMES:
            revenue = await _statement(client, symbol, NET_REVENUE_ITEM)
            npat = await _statement(client, symbol, NET_INCOME_ITEM)
            bars = await fetch_bars(client, symbol, start=RESEARCH_HISTORY_START)
            books[symbol] = {"revenue": revenue, "npat": npat, "closes": _closes(bars)}
    return {"oil": oil, "books": books}


def follow_table(loaded: dict) -> tuple[dict, dict]:
    shock = oil_shock(loaded["oil"])
    profit = {}
    price = {}
    for symbol in SCORED_NAMES:
        book = loaded["books"][symbol]
        fiscal = sorted(set(dict(book["npat"])) & set(dict(book["revenue"])))
        profit[symbol] = [
            _fit(npat_projection_pairs(book["npat"], book["revenue"], shock, horizon, SELECT_END))
            for horizon in LAG_HORIZONS
        ]
        price[symbol] = [
            _fit(price_projection_pairs(book["closes"], fiscal, shock, horizon, SELECT_END))
            for horizon in LAG_HORIZONS
        ]
    return profit, price


def _cell(beta: float | None, count: int) -> str:
    if beta is None:
        return f"— (n={count})"
    return f"{beta * 0.25 * 100:+.2f} (n={count})"


def _rows(table: dict) -> list[str]:
    lines = [
        "| Mã | h = 0 | h = 1 | h = 2 | h = 3 | h = 4 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for symbol in SCORED_NAMES:
        cells = " | ".join(_cell(beta, count) for beta, count in table[symbol])
        lines.append(f"| {symbol} | {cells} |")
    return lines


def render(profit: dict, price: dict) -> str:
    lines = [
        "# LNST và giá sau cú sốc dầu",
        "",
        f"Số liệu kéo ngày {date.today().isoformat()}. Quý kết quả kết thúc không muộn hơn {SELECT_END}.",
        "Mỗi ô là mức đi cùng một cú sốc dầu +25% ở quý 0.",
        "h = 0 là quý xảy ra cú sốc. h = 4 là bốn quý sau quý đó. Mốc nào cũng được in. Không chọn mốc.",
        "",
        "LNST là khoản 23000, lợi nhuận sau thuế của cổ đông công ty mẹ.",
        "Số LNST là mức LNST quý kết quả trừ mức LNST quý liền trước cú sốc, chia doanh thu quý liền trước cú sốc, rồi nhân 100.",
        "Đơn vị ô LNST: điểm phần trăm doanh thu quý trước cú sốc. Không phải phần trăm tăng của chính dòng LNST, và không phải tổng lợi nhuận của các quý ở giữa.",
        "",
        "Giá lấy tại phiên giao dịch đầu tiên không sớm hơn ngày kết thúc quý cộng 45 ngày, và không muộn quá 10 ngày.",
        "Số giá là lợi suất nắm giữ từ phiên công bố của quý liền trước cú sốc đến phiên công bố của quý kết quả, nhân 100.",
        "Đơn vị ô giá: phần trăm. Ngày công bố của quý kết thúc 31/12/2024 rơi sang 2025. Đó vẫn là quý kết quả trong giai đoạn chọn.",
        "Bảng không đổi ngưỡng dầu và không đổi `Được vào`.",
        "",
        "## Lợi nhuận sau thuế",
        "",
    ]
    lines.extend(_rows(profit))
    lines.extend(["", "## Giá cổ phiếu", ""])
    lines.extend(_rows(price))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    loaded = asyncio.run(load())
    if not loaded["oil"]:
        raise SystemExit("Không tải được CL=F")
    text = render(*follow_table(loaded))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
