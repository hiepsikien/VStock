from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.backtest import run_backtest
from app.config import STATUS_RANK
from app.ingest import load_exchanges
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
    return sorted(verdicts, key=lambda item: (STATUS_RANK.get(item["status"], 9), -item["priority"], item["symbol"]))


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
            "notice": notice,
            "error": error,
            "busy": busy(),
            "regime": verdicts[0]["regime_reason"] if verdicts else "",
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
    return templates.TemplateResponse(
        request,
        "symbol.html",
        {
            "symbol": sym,
            "item": item,
            "articles": await db.articles_for(sym),
            "decisions": await db.decisions_for(sym),
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
    return RedirectResponse(f"{target}?notice={_query(label)}", status_code=303)


@app.get("/backtest")
async def backtest_page(request: Request):
    symbols = await db.universe()
    index_bars = await db.bars("VNINDEX")
    result = run_backtest(
        index_bars,
        {symbol: await db.bars(symbol) for symbol in symbols},
        {symbol: await db.ratios(symbol) for symbol in symbols},
        {symbol: await db.articles_for(symbol) for symbol in symbols},
        load_exchanges(),
    )
    return templates.TemplateResponse(request, "backtest.html", {"result": result})


def _query(value: str) -> str:
    from urllib.parse import quote

    return quote(value)
