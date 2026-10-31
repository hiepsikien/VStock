"""Đo cửa Compass trên giai đoạn chọn. Không chạy giai đoạn xác nhận.

Thứ tự cố định: kiểm tra biên gộp khớp ratio, chọn ngưỡng trên riêng chuỗi dầu,
rồi mới tính spread cổ phiếu. Ba việc này không được đảo.
"""

from __future__ import annotations

import asyncio
from datetime import date

import httpx

from app.compass import (
    GROSS_PROFIT_ITEM,
    MIN_EVENTS,
    MIN_SCORED_EVENTS,
    NET_REVENUE_ITEM,
    PRICE_BETA_SESSIONS,
    SCORED_NAMES,
    SELECT_END,
    SELECT_START,
    WINDOW,
    basket_spread,
    beta_on,
    choose_theta,
    classify,
    common_sessions,
    daily_returns,
    event_starts,
    forward_return,
    gross_margins,
    heuristic_scores,
    margin_pairs,
    mean,
    oil_shock,
    price_beta,
    shock_by_session,
    verdict,
)
from app.config import RESEARCH_HISTORY_START, STATEMENT_LAG_DAYS
from app.industry_screen import dated_returns
from app.ingest import BROWSER_HEADERS, VNDIRECT_RATIOS, VNDIRECT_STATEMENTS, fetch_bars, fetch_macro

REPORT_PATH = __import__("pathlib").Path(__file__).resolve().parents[1] / "reports" / "compass_gate.md"
# Sai khác cho phép khi đối chiếu khoản mục với ratio biên gộp của cùng một quý.
MARGIN_TOLERANCE = 1e-4


async def _statement(
    client: httpx.AsyncClient, symbol: str, item_code: str
) -> list[tuple[str, float]]:
    response = await client.get(
        VNDIRECT_STATEMENTS,
        params={
            "q": f"code:{symbol}~itemCode:{item_code}~reportType:QUARTER",
            "size": 200,
            "sort": "fiscalDate:asc",
        },
        headers=BROWSER_HEADERS,
    )
    response.raise_for_status()
    rows = []
    for row in (response.json() or {}).get("data") or []:
        fiscal = str(row.get("fiscalDate") or "")[:10]
        raw = row.get("numericValue")
        if not fiscal or raw is None:
            continue
        rows.append((fiscal, float(raw)))
    rows.sort()
    return rows


async def _published_margin(client: httpx.AsyncClient, symbol: str) -> tuple[str, float] | None:
    response = await client.get(
        VNDIRECT_RATIOS,
        params={
            "q": f"code:{symbol}~ratioCode:GROSS_MARGIN_QR",
            "size": 1,
            "sort": "reportDate:desc",
        },
        headers=BROWSER_HEADERS,
    )
    response.raise_for_status()
    rows = (response.json() or {}).get("data") or []
    if not rows:
        return None
    return str(rows[0]["reportDate"])[:10], float(rows[0]["value"])


def _closes(bars: list[dict]) -> list[tuple[str, float]]:
    return [(str(bar["trade_date"]), float(bar["close"])) for bar in bars if bar.get("close")]


async def load() -> dict:
    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        macro = await fetch_macro(client, start=RESEARCH_HISTORY_START)
        oil = macro.get("OIL") or []
        books = {}
        checks = {}
        for symbol in SCORED_NAMES:
            revenue = await _statement(client, symbol, NET_REVENUE_ITEM)
            gross = await _statement(client, symbol, GROSS_PROFIT_ITEM)
            bars = await fetch_bars(client, symbol, start=RESEARCH_HISTORY_START)
            published = await _published_margin(client, symbol)
            books[symbol] = {
                "revenue": revenue,
                "gross": gross,
                "closes": _closes(bars),
            }
            checks[symbol] = published
    return {"oil": oil, "books": books, "checks": checks}


def _check_margins(books: dict, checks: dict) -> list[str]:
    """Dừng cả lần đo nếu biên tự tính lệch khỏi GROSS_MARGIN_QR của cùng quý."""
    problems = []
    for symbol in SCORED_NAMES:
        published = checks.get(symbol)
        margins = dict(gross_margins(books[symbol]["revenue"], books[symbol]["gross"]))
        if published is None:
            problems.append(f"{symbol}: không đọc được GROSS_MARGIN_QR")
            continue
        day, published_value = published
        built = margins.get(day)
        if built is None:
            problems.append(f"{symbol}: không có khoản 23100/21001 tại {day}")
            continue
        gap = abs(built - published_value)
        if gap > MARGIN_TOLERANCE:
            problems.append(
                f"{symbol} {day}: khoản mục {built:.6f}, ratio {published_value:.6f}"
            )
    return problems


def _score(loaded: dict) -> dict:
    books = loaded["books"]
    oil_bars = loaded["oil"]
    shock = oil_shock(oil_bars)
    closes = {symbol: books[symbol]["closes"] for symbol in SCORED_NAMES}
    sessions = common_sessions(closes, SCORED_NAMES)
    on_session = shock_by_session(sessions, shock)
    theta = choose_theta(sessions, on_session, SELECT_START, SELECT_END)
    oil_events = [] if theta is None else event_starts(sessions, on_session, theta, SELECT_START, SELECT_END)

    pairs = {
        symbol: margin_pairs(gross_margins(books[symbol]["revenue"], books[symbol]["gross"]), shock)
        for symbol in SCORED_NAMES
    }
    close_map = {symbol: dict(closes[symbol]) for symbol in SCORED_NAMES}
    stock_daily = {symbol: daily_returns(closes[symbol]) for symbol in SCORED_NAMES}
    oil_daily = dict(dated_returns(oil_bars))

    scored = []
    dropped = []
    if theta is None:
        return {
            "theta": None,
            "oil_events": [],
            "scored": scored,
            "dropped": dropped,
            "sessions": len(sessions),
            "pairs": {symbol: len(pairs[symbol]) for symbol in SCORED_NAMES},
        }

    for day in oil_events:
        oil_move = on_session[day]
        betas = {symbol: beta_on(pairs[symbol], day) for symbol in SCORED_NAMES}
        z_scores = {symbol: beta * oil_move for symbol, beta in betas.items() if beta is not None}
        price = {
            symbol: price_beta(stock_daily[symbol], oil_daily, day)
            for symbol in SCORED_NAMES
        }
        price_scores = {symbol: beta * oil_move for symbol, beta in price.items() if beta is not None}
        forwards = {
            symbol: forward_return(close_map[symbol], sessions, day) for symbol in SCORED_NAMES
        }
        if any(value is None for value in forwards.values()):
            dropped.append((day, "thiếu giá thoát"))
            continue
        filled = {symbol: value for symbol, value in forwards.items() if value is not None}
        z_signs = classify(z_scores)
        heuristic_signs = classify(heuristic_scores(oil_move))
        price_signs = classify(price_scores)
        detail = f"dấu Z {_sign_text(z_scores)}; dấu điểm giá {_sign_text(price_scores)}"
        if z_signs is None:
            dropped.append((day, f"Z không đủ hai mã mỗi phía ({detail})"))
            continue
        if price_signs is None:
            dropped.append((day, f"β giá không đủ hai mã mỗi phía ({detail})"))
            continue
        if heuristic_signs is None:
            dropped.append((day, f"dấu viết tay không đủ hai mã mỗi phía ({detail})"))
            continue
        scored.append(
            {
                "day": day,
                "oil": oil_move,
                "betas": betas,
                "price": price,
                "z": basket_spread(z_signs, filled),
                "heuristic": basket_spread(heuristic_signs, filled),
                "price_spread": basket_spread(price_signs, filled),
                "z_signs": z_signs,
            }
        )
    return {
        "theta": theta,
        "oil_events": oil_events,
        "scored": scored,
        "dropped": dropped,
        "sessions": len(sessions),
        "pairs": {symbol: len(pairs[symbol]) for symbol in SCORED_NAMES},
    }


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.2f}%"


def render(loaded: dict, problems: list[str], scored_run: dict) -> str:
    lines = [
        "# Cửa Compass — giai đoạn chọn",
        "",
        f"Số liệu kéo ngày {date.today().isoformat()}. Chỉ giai đoạn {SELECT_START} → {SELECT_END}.",
        "Giai đoạn xác nhận chưa chạy. Kết quả dưới đây không đổi `Được vào`.",
        "",
        "## Luật đã khóa trước khi đọc spread",
        "",
        "- Đích hồi quy: biên lợi nhuận gộp quý này trừ quý liền trước. Tử là khoản 23100, mẫu là khoản 21001, cùng đơn vị tiền.",
        f"- Quý được nhìn sau {STATEMENT_LAG_DAYS} ngày kể từ ngày kết thúc quý. β cửa sổ mở rộng, tối thiểu 12 cặp. Thiếu thì mã rời ngày đó.",
        f"- Vế phải và cú sốc ngày: lợi suất {WINDOW} phiên của CL=F, biết đến hết phiên đang xét.",
        "- Mua giá đóng cửa phiên sau tín hiệu, giữ 60 phiên. Sự kiện là lần cắt ngưỡng, không lấy phiên đang đứng sẵn trên ngưỡng.",
        f"- Dấu viết tay: PVD +, GAS +, DCM −, DPM −. NT2 đứng ngoài cả ba spread.",
        f"- β giá: OLS lợi suất ngày, {PRICE_BETA_SESSIONS} phiên chung, chỉ phiên trước ngày tín hiệu.",
        f"- Ngưỡng là mức lớn nhất trong lưới 0.10, 0.12, 0.15, 0.18, 0.20, 0.25 còn ít nhất {MIN_EVENTS} sự kiện dầu. Lưới không được nới sau bước này.",
        f"- Chấm khi còn ít nhất {MIN_SCORED_EVENTS} sự kiện mà cả ba cách chia phía đều đủ hai mã. Spread là trung bình lợi suất phía dương trừ phía âm. Cửa thắng là trung bình spread của Z dương, lớn hơn dấu viết tay, và lớn hơn β giá.",
        "- Lợi suất tới của một sự kiện mở trong giai đoạn chọn có thể kết thúc sau 2024-12-31. Đó vẫn là kết quả của sự kiện đã mở, không phải một sự kiện của giai đoạn xác nhận.",
        "",
    ]
    if problems:
        lines.append("## Dừng")
        lines.append("")
        lines.append("Biên gộp tự tính không khớp GROSS_MARGIN_QR. Spread không được tính.")
        lines.append("")
        for problem in problems:
            lines.append(f"- {problem}")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Đối chiếu biên gộp")
    lines.append("")
    lines.append("Khoản 23100 / 21001 khớp `GROSS_MARGIN_QR` của quý mới nhất từng mã, sai số dưới 0,01 điểm phần trăm.")
    lines.append("")
    theta = scored_run["theta"]
    oil_count = len(scored_run["oil_events"])
    lines.append("## Ngưỡng dầu")
    lines.append("")
    if theta is None:
        lines.append(
            f"Không có mức nào trên lưới đủ {MIN_EVENTS} sự kiện dầu không chồng trong giai đoạn chọn. "
            "Spread không được tính và lưới không được hạ."
        )
        lines.append("")
        return "\n".join(lines)
    lines.append(
        f"Ngưỡng khóa ở {theta:.2f}. Sự kiện dầu trong giai đoạn chọn: {oil_count}. "
        f"Lịch chung của bốn mã: {scored_run['sessions']} phiên."
    )
    pair_text = ", ".join(f"{symbol} {scored_run['pairs'][symbol]} cặp" for symbol in SCORED_NAMES)
    lines.append(f"Cặp biên gộp dùng được: {pair_text}.")
    lines.append("")

    scored = scored_run["scored"]
    spreads_z = [row["z"] for row in scored]
    spreads_h = [row["heuristic"] for row in scored]
    spreads_p = [row["price_spread"] for row in scored]
    outcome = verdict(spreads_z, spreads_h, spreads_p)
    labels = {"qua": "Qua cửa giai đoạn chọn", "truot": "Trượt cửa giai đoạn chọn", "chua_du": "Chưa đủ sự kiện để chấm"}
    lines.append("## Kết quả")
    lines.append("")
    lines.append(f"{labels[outcome]}. Sự kiện chấm được: {len(scored)}. Sự kiện dầu bị loại: {len(scored_run['dropped'])}.")
    lines.append("")
    lines.append(f"- Spread Z: {_pct(mean(spreads_z))}")
    lines.append(f"- Spread dấu viết tay: {_pct(mean(spreads_h))}")
    lines.append(f"- Spread β giá: {_pct(mean(spreads_p))}")
    lines.append("")
    lines.append("| Phiên | Dầu 60 phiên | PVD | GAS | DCM | DPM | Spread Z | Dấu viết tay | β giá |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in scored:
        betas = row["betas"]
        lines.append(
            "| {day} | {oil} | {pvd} | {gas} | {dcm} | {dpm} | {z} | {h} | {p} |".format(
                day=row["day"],
                oil=_pct(row["oil"]),
                pvd=_fmt_beta(betas["PVD"]),
                gas=_fmt_beta(betas["GAS"]),
                dcm=_fmt_beta(betas["DCM"]),
                dpm=_fmt_beta(betas["DPM"]),
                z=_pct(row["z"]),
                h=_pct(row["heuristic"]),
                p=_pct(row["price_spread"]),
            )
        )
    lines.append("")
    if scored_run["dropped"]:
        lines.append("Sự kiện dầu không vào trung bình:")
        lines.append("")
        for day, reason in scored_run["dropped"]:
            lines.append(f"- {day}: {reason}")
        lines.append("")
    lines.append(
        "Dấu β trong bảng là hệ số biên gộp đang có hiệu lực tại phiên đó, không phải điểm Z. "
        "Điểm Z là hệ số này nhân với lợi suất dầu của phiên."
    )
    lines.append("")
    return "\n".join(lines)


def _sign_text(scores: dict[str, float]) -> str:
    parts = []
    for symbol in SCORED_NAMES:
        value = scores.get(symbol)
        if value is None:
            parts.append(f"{symbol} thiếu")
        elif value > 0:
            parts.append(f"{symbol}+")
        elif value < 0:
            parts.append(f"{symbol}−")
        else:
            parts.append(f"{symbol} 0")
    return " ".join(parts)


def _fmt_beta(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.3f}"


def main() -> None:
    loaded = asyncio.run(load())
    problems = _check_margins(loaded["books"], loaded["checks"])
    scored_run = {
        "theta": None,
        "oil_events": [],
        "scored": [],
        "dropped": [],
        "sessions": 0,
        "pairs": {},
    }
    if not problems:
        if not loaded["oil"]:
            problems = ["Không tải được CL=F"]
        else:
            scored_run = _score(loaded)
    text = render(loaded, problems, scored_run)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
