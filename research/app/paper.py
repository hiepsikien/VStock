from __future__ import annotations

from app import db
from app.config import MA_FAST, ROUND_TRIP_COST
from app.exits import (
    OpenPosition,
    blocking_filing,
    close_at,
    fell_under_base,
    manage_position,
    mark_bar,
    plan_exit,
)
from app.flow import flow_flipped
from app.pattern import Pattern, atr, ma_now


def _from_row(row: dict) -> OpenPosition:
    return OpenPosition(
        symbol=row["symbol"],
        entry_date=row["entry_date"],
        entry_price=row["entry_price"],
        stop=row["stop_price"],
        initial_stop=row["initial_stop"],
        target1=row["target1"],
        atr14=row["atr14"],
        sessions=row["sessions"],
        tp1_done=row["tp1_done"],
        booked_fraction=row["booked_fraction"],
        realised=row["realised"],
        last_price=row["last_price"],
        last_date=row["last_date"],
        exit_date=row["exit_date"],
        exit_price=row["exit_price"],
        exit_reason=row["exit_reason"],
        base_ceiling=row.get("base_ceiling"),
    )


def row_return(row: dict) -> float:
    """Return of one paper slot, mixing the part booked at TP1 with the rest."""
    reference = row["exit_price"]
    if reference is None:
        reference = row["last_price"] if row["last_price"] is not None else row["entry_price"]
    return row["realised"] + (1 - row["booked_fraction"]) * (reference / row["entry_price"] - 1)


def _index_return(index_bars: list[dict], start: str, end: str) -> float | None:
    window = [bar for bar in index_bars if start <= bar["trade_date"] <= end]
    if len(window) < 2 or window[0]["close"] <= 0:
        return None
    return window[-1]["close"] / window[0]["close"] - 1


async def open_position(
    symbol: str,
    bars: list[dict],
    pattern: Pattern | None,
    score: int = 0,
    note: str = "",
) -> str:
    """Open one paper slot at the latest close, using the same plan as the backtest."""
    if not bars:
        return f"{symbol}: chưa có nến để mở vị thế giấy."
    for existing in await db.open_paper_positions():
        if existing["symbol"] == symbol:
            return f"{symbol}: đã có vị thế giấy đang mở."
    bar = bars[-1]
    entry = float(bar["close"])
    if entry <= 0:
        return f"{symbol}: giá đóng cửa không hợp lệ."
    pos = plan_exit(symbol, str(bar["trade_date"]), entry, pattern, atr(bars))
    await db.open_paper_position(
        {
            "symbol": symbol,
            "entry_date": pos.entry_date,
            "entry_price": pos.entry_price,
            "initial_stop": pos.initial_stop,
            "stop_price": pos.stop,
            "target1": pos.target1,
            "atr14": pos.atr14,
            "base_ceiling": pos.base_ceiling,
            "score": score,
            "note": note,
        }
    )
    return (
        f"Đã mở vị thế giấy {symbol} tại {entry:.2f}, dừng lỗ {pos.stop:.2f}, "
        f"chốt một phần tại {pos.target1:.2f}."
    )


def _upto(bars: list[dict], day: str) -> list[dict]:
    return [bar for bar in bars if bar["trade_date"] <= day]


def _flow_upto(points: dict[str, list[tuple[str, float]]], day: str) -> dict[str, list[tuple[str, float]]]:
    return {
        code: [(when, value) for when, value in series if when <= day]
        for code, series in points.items()
    }


async def mark_positions(as_of: str) -> list[str]:
    """Mark every open slot session by session with the shared exit engine.

    Bars are stepped one at a time from the last marked session, so a session the
    operator missed still runs its stop and its trim, and a re-run on a day already
    marked cannot count that session twice.
    """
    messages: list[str] = []
    for row in await db.open_paper_positions():
        bars = [bar for bar in await db.bars(row["symbol"]) if bar["trade_date"] <= as_of]
        if not bars:
            continue
        marked_to = row["last_date"] or row["entry_date"]
        pending = [bar for bar in bars if str(bar["trade_date"]) > marked_to]
        if not pending:
            continue
        pos = _from_row(row)
        articles = await db.articles_for(row["symbol"])
        flow = await db.flow(row["symbol"])
        reason: str | None = None
        for bar in pending:
            day = str(bar["trade_date"])
            window = _upto(bars, day)
            mark_bar(pos, bar)
            filing = blocking_filing(articles, row["entry_date"], day)
            if filing:
                reason = close_at(pos, bar, f"Công bố chặn: {filing}")
            elif flow_flipped(_flow_upto(flow, day), window):
                reason = close_at(pos, bar, "Dòng tiền ngoại đảo chiều")
            elif fell_under_base(pos, bar):
                reason = pos.exit_reason
            else:
                reason = manage_position(
                    pos, bar, ma20=ma_now(window, MA_FAST), atr14=atr(window)
                )
            await db.mark_paper(row["id"], day, pos.last_price or 0.0, pos.unrealised())
            if reason is not None:
                break
        closed = reason is not None
        await db.save_paper_position(
            {
                "id": row["id"],
                "stop_price": pos.stop,
                "sessions": pos.sessions,
                "tp1_done": pos.tp1_done,
                "booked_fraction": pos.booked_fraction,
                "realised": pos.realised,
                "last_price": pos.last_price,
                "last_date": pos.last_date,
                "closed_at": pos.exit_date if closed else None,
                "exit_date": pos.exit_date,
                "exit_price": pos.exit_price,
                "exit_reason": pos.exit_reason,
            }
        )
        if closed:
            messages.append(
                f"{row['symbol']}: đóng vị thế giấy tại {pos.exit_price:.2f} — {reason} "
                f"({pos.realised_return() * 100:+.1f}%)."
            )
    return messages


async def report(limit: int = 50) -> dict:
    """Forward-test summary: what the confirmed signals did against VN-Index while held."""
    rows = await db.recent_paper_positions(limit)
    index_bars = await db.bars("VNINDEX")
    prepared = []
    for row in rows:
        item = dict(row)
        item["return_pct"] = row_return(row)
        window_end = row["exit_date"] or row["last_date"] or row["entry_date"]
        item["index_pct"] = _index_return(index_bars, row["entry_date"], window_end)
        prepared.append(item)

    closed = [item for item in prepared if item["exit_date"]]
    still_open = [item for item in prepared if not item["exit_date"]]
    wins = [item for item in closed if item["return_pct"] > 0]
    returns = [item["return_pct"] for item in prepared]
    index_returns = [item["index_pct"] for item in prepared if item["index_pct"] is not None]

    average = sum(returns) / len(returns) if returns else None
    average_index = sum(index_returns) / len(index_returns) if index_returns else None
    if prepared:
        window = (
            prepared[-1]["entry_date"],
            prepared[0]["last_date"] or prepared[0]["entry_date"],
        )
    else:
        window = ("", "")
    return {
        "rows": prepared,
        "open_count": len(still_open),
        "closed_count": len(closed),
        "count": len(prepared),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "average_return": average,
        "average_index": average_index,
        "alpha": None if average is None or average_index is None else average - average_index,
        "window": window,
        "assumptions": (
            "Mỗi vị thế giấy là một suất vốn bằng nhau, tính theo phần trăm. "
            f"Phí cả vòng {ROUND_TRIP_COST * 100:.2f}% chưa trừ vào lãi của vị thế. "
            "So sánh dùng VN-Index trong đúng cửa sổ nắm giữ của từng vị thế."
        ),
    }
