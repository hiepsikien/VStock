from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db, paper
from app.backtest import run_backtest
from app.chart import build_chart
from app.config import (
    MARKET_GATE_REQUIRED,
    MARKET_SERIES,
    POLICY_RATE_HISTORY,
    STATUS_RANK,
)
from app.evaluate import SCORE_CEILINGS
from app.industries import set_industry_map
from app.ingest import load_exchanges
from app.money import LABELS, money_state, thresholds
from app.pattern import assess_pattern
from app.pipeline import busy, run_session

ROOT = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _status_class(status: str) -> str:
    return {
        "Được vào": "enter",
        "Theo dõi": "watch",
        "Chờ": "wait",
        "Chưa chấm": "unstamped",
        "Loại": "out",
        "Khóa": "locked",
    }.get(status, "unstamped")


templates.env.filters["pct"] = _pct
templates.env.globals["status_class"] = _status_class


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await db.init_db()
    stored = await db.symbol_industry()
    set_industry_map({symbol: row["industry"] for symbol, row in stored.items()})
    yield
    await db.close_db()


app = FastAPI(title="VStock Research", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.middleware("http")
async def no_store(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def _ordered(verdicts: list[dict]) -> list[dict]:
    """Best score first inside a state, the way the walk ranks its candidates.

    The state itself leads: a name that may be bought outranks one on watch. Inside a state the
    composite score decides, with the insider-buy flag and then the ticker as tie-breakers — the
    same order the backtest buys in, so the page and the measurement read the list alike.
    """
    return sorted(
        verdicts,
        key=lambda item: (
            STATUS_RANK.get(item["status"], 9),
            -item["score"],
            -item["priority"],
            item["symbol"],
        ),
    )


@app.get("/")
async def dashboard(request: Request, notice: str = "", error: str = ""):
    verdicts = _ordered(await db.latest_verdicts())
    counts: dict[str, int] = {}
    for item in verdicts:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "verdicts": verdicts,
            "counts": counts,
            "universe": await db.universe(),
            "run": await db.latest_run(),
            "decisions": await db.recent_decisions(),
            "paper": await paper.report(),
            "notice": notice,
            "error": error,
            "busy": busy(),
            "regime": verdicts[0]["regime_reason"] if verdicts else "",
            "macro": verdicts[0]["macro_reason"] if verdicts else "",
            # Cổng tiền tệ đọc từ chuỗi đã lưu, nên nó đứng được trên bảng cả khi phiên
            # chưa chấm lại mã nào.
            "money": money_state(await db.market_points()).reason,
        },
    )


def _money_value(code: str, value: float) -> str:
    if code == "USDVND":
        return f"{value:,.0f}"
    if code == "NHNN_NET":
        return f"{value:+,.0f}"
    return f"{value:,.2f}"


@app.get("/market")
async def market_page(request: Request):
    """Cổng tiền tệ. Một trang riêng, vì các chuỗi này thuộc về thị trường chứ không thuộc mã nào."""
    points = await db.market_points()
    money = money_state(points)
    notes = dict(money.metrics)
    rows = []
    for code, label, unit, symbol in MARKET_SERIES:
        series = points.get(code) or []
        rows.append(
            {
                "code": code,
                "label": label,
                "unit": unit,
                "source": symbol or "bảng quyết định",
                "sessions": len(series),
                "last_day": series[-1][0] if series else "",
                "last_value": _money_value(code, series[-1][1]) if series else "—",
                "note": notes.get(label, ""),
                "required": code in MARKET_GATE_REQUIRED,
            }
        )
    days = [row["last_day"] for row in rows if row["last_day"]]
    return templates.TemplateResponse(
        request,
        "market.html",
        {
            "money": money,
            "rows": rows,
            "thresholds": thresholds(),
            "missing": [LABELS.get(code, code) for code in money.absent],
            "short": [
                (LABELS.get(code, code), have, need) for code, have, need in money.short
            ],
            "policy": POLICY_RATE_HISTORY,
            "latest_day": max(days) if days else "",
        },
    )


@app.post("/run")
async def run():
    if busy():
        return RedirectResponse("/?error=Đang+chạy+một+phiên+khác", status_code=303)
    message = await run_session()
    if message.startswith("Phiên lỗi") or message.startswith("Đang chạy"):
        return RedirectResponse(f"/?error={_query(message)}", status_code=303)
    return RedirectResponse(f"/?notice={_query(message)}", status_code=303)


@app.post("/universe")
async def update_universe(symbol: str = Form(""), action: str = Form("add")):
    cleaned = "".join(ch for ch in symbol.upper() if ch.isalnum())
    if action == "remove" and cleaned:
        await db.remove_symbol(cleaned)
        return RedirectResponse(f"/?notice={_query('Đã bỏ ' + cleaned)}", status_code=303)
    if len(cleaned) < 2 or len(cleaned) > 8:
        return RedirectResponse("/?error=Mã+không+hợp+lệ", status_code=303)
    await db.add_symbol(cleaned)
    return RedirectResponse(f"/?notice={_query('Đã thêm ' + cleaned + '. Chạy phiên để chấm mã này.')}", status_code=303)


@app.get("/symbol/{symbol}")
async def symbol_page(request: Request, symbol: str, error: str = "", notice: str = ""):
    sym = symbol.upper()
    item = await db.verdict(sym)
    bars = await db.bars(sym)
    index_bars = await db.bars("VNINDEX")
    # The chart is drawn from the stored bars, and the pattern is recomputed from the same
    # series, so the picture and the sentence under it describe one 20-session window.
    pattern = (
        assess_pattern(bars, index_bars, load_exchanges().get(sym))
        if item and bars and index_bars
        else None
    )
    return templates.TemplateResponse(
        request,
        "symbol.html",
        {
            "symbol": sym,
            "item": item,
            "chart": build_chart(bars, pattern),
            "score_ceilings": SCORE_CEILINGS,
            "articles": await db.articles_for(sym),
            "decisions": await db.decisions_for(sym),
            "paper": await db.paper_for(sym),
            "error": error,
            "notice": notice,
        },
    )


@app.post("/decisions")
async def decide(
    symbol: str = Form(...),
    as_of: str = Form(...),
    signal_status: str = Form(...),
    action: str = Form(...),
    note: str = Form(""),
):
    sym = "".join(ch for ch in symbol.upper() if ch.isalnum())
    action = action if action in {"confirm", "skip"} else ""
    note = note.strip()[:500]
    target = f"/symbol/{sym}"
    if not action:
        return RedirectResponse(f"{target}?error={_query('Thao tác không hợp lệ')}", status_code=303)
    if action == "confirm" and signal_status != "Được vào" and not note:
        return RedirectResponse(
            f"{target}?error={_query('Xác nhận khi tín hiệu không phải Được vào cần ghi chú lệch.')}",
            status_code=303,
        )
    if action == "skip" and signal_status == "Được vào" and not note:
        return RedirectResponse(
            f"{target}?error={_query('Bỏ qua mã Được vào cần ghi chú.')}",
            status_code=303,
        )
    await db.add_decision(as_of, sym, signal_status, action, note)
    label = "Đã ghi xác nhận" if action == "confirm" else "Đã ghi bỏ qua"
    if action == "confirm" and signal_status == "Được vào":
        bars = await db.bars(sym)
        index_bars = await db.bars("VNINDEX")
        pattern = (
            assess_pattern(bars, index_bars, load_exchanges().get(sym))
            if bars and index_bars
            else None
        )
        item = await db.verdict(sym)
        label += ". " + await paper.open_position(
            sym, bars, pattern, (item or {}).get("score") or 0, note
        )
    return RedirectResponse(f"{target}?notice={_query(label)}", status_code=303)


# The portfolio walk is ~10s on a 30-symbol book, and the page reloads for every
# glance, so the last walk is kept until a session changes what is stored.
_backtest_cache: dict[str, object] = {"key": None, "result": None, "at": ""}


async def _backtest_key() -> tuple:
    run = await db.latest_run() or {}
    return (
        run.get("id"),
        run.get("status"),
        run.get("finished_at"),
        tuple(await db.universe()),
    )


def backtest_computed_at() -> str:
    return str(_backtest_cache["at"] or "")


async def backtest_result(fresh: bool = False) -> dict:
    """Reuse the last walk until data, universe or run state moves."""
    key = await _backtest_key()
    cached = _backtest_cache["result"]
    if not fresh and cached is not None and _backtest_cache["key"] == key:
        return cached
    symbols = await db.universe()
    result = run_backtest(
        await db.bars("VNINDEX"),
        {symbol: await db.bars(symbol) for symbol in symbols},
        {symbol: await db.ratios(symbol) for symbol in symbols},
        {symbol: await db.articles_for(symbol) for symbol in symbols},
        load_exchanges(),
        {symbol: await db.flow(symbol) for symbol in symbols},
        await db.market_points(),
    )
    _backtest_cache.update(
        {"key": key, "result": result, "at": datetime.now().strftime("%H:%M:%S %d/%m")}
    )
    return result


@app.get("/backtest")
async def backtest_page(request: Request, fresh: int = 0):
    result = await backtest_result(fresh=bool(fresh))
    return templates.TemplateResponse(
        request,
        "backtest.html",
        {
            "result": result,
            "paper": await paper.report(),
            "computed_at": backtest_computed_at(),
        },
    )


def _query(value: str) -> str:
    from urllib.parse import quote

    return quote(value)
