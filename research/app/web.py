from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db, paper
from app.backtest import run_backtest_with_industries
from app.chart import build_chart
from app.breadth import breadth_reason
from app.breadth_filter import Counts
from app.config import (
    BREADTH_CLOSE,
    BREADTH_FILTER_START,
    BREADTH_GATE_ENFORCED,
    BREADTH_MA_WINDOW,
    BREADTH_OPEN,
    BREADTH_SERIES,
    BREADTH_STATE_SERIES,
    MARKET_GATE_REQUIRED,
    MARKET_SERIES,
    POLICY_RATE_HISTORY,
    STATUS_RANK,
)
from app.evaluate import SCORE_CEILINGS
from app.industries import industry_labels, load_industry_map
from app.ingest import load_exchanges
from app.jobs import Job, status_line
from app.money import LABELS, money_state, thresholds
from app.pattern import assess_pattern
from app.pipeline import busy, run_session
from app.scheduled import VN
from app.tracking import breadth_rows, filter_counts, filter_view, run_rows, schedule_view

logger = logging.getLogger(__name__)
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


# Phép đo sau phí và phép đếm mẫu bộ lọc là CPU thuần Python, chạy hàng phút. Trên một luồng
# của tiến trình web, chúng giữ GIL và làm mọi trang khác chờ, nên chạy ở tiến trình riêng.
_pool: ProcessPoolExecutor | None = None


def _process_pool() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=2)
    return _pool


async def _in_process(function, *args):
    global _pool
    try:
        return await asyncio.get_running_loop().run_in_executor(_process_pool(), function, *args)
    except BrokenProcessPool:
        # A worker that died takes the pool with it; the next call starts a new one.
        _pool = None
        raise


async def run_walk(inputs: tuple) -> dict:
    return await _in_process(run_backtest_with_industries, industry_labels(), *inputs)


async def count_filter_sample():
    return await _in_process(filter_counts, BREADTH_FILTER_START)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await db.init_db()
    await load_industry_map()
    yield
    _stop_pool()
    await db.close_db()


def _stop_pool() -> None:
    """Kill the workers: Python joins them at exit, so a walk in flight would hold up a stop or
    a --reload for minutes. The walk in flight is lost."""
    global _pool
    if _pool is None:
        return
    for process in list((_pool._processes or {}).values()):
        process.terminate()
    _pool.shutdown(wait=True, cancel_futures=True)
    _pool = None


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


async def _index_days() -> list[str]:
    return [str(bar["trade_date"]) for bar in await db.bars("VNINDEX")]


@app.get("/")
async def dashboard(request: Request, notice: str = "", error: str = ""):
    verdicts = _ordered(await db.latest_verdicts())
    counts: dict[str, int] = {}
    for item in verdicts:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    points = await db.market_points()
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
            "money": money_state(points).reason,
            "runs": run_rows(await db.recent_runs(8), busy()),
            "schedule": schedule_view(
                await _index_days(), points.get(BREADTH_STATE_SERIES) or [], datetime.now(VN)
            ),
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
            "breadth": _breadth_view(points, await _index_days()),
            "breadth_filter": await _breadth_filter(),
            "busy": busy(),
        },
    )


def _breadth_view(points: dict[str, list[tuple[str, float]]], index_days: list[str]) -> dict:
    """Số độ rộng mà phiên live đã lưu, xếp theo phiên VN-Index để phiên bỏ lỡ hiện ra."""
    shares = points.get(BREADTH_SERIES) or []
    states = points.get(BREADTH_STATE_SERIES) or []
    state_of = dict(states)
    last_day, last_share = shares[-1] if shares else ("", None)
    state = state_of.get(last_day)
    return {
        "reason": breadth_reason(last_share, None if state is None else state > 0.5) if shares else "",
        "last_day": last_day,
        "sessions": len(shares),
        "recent": [{**row, "share": _pct(row["share"])} for row in breadth_rows(index_days, shares, states)],
        "enforced": BREADTH_GATE_ENFORCED,
        "rule": (
            f"Tỷ lệ mã của rổ 200 trong năm đóng cửa trên MA{BREADTH_MA_WINDOW}. Mở khi từ "
            f"{BREADTH_OPEN:.0%}, đóng khi từ {BREADTH_CLOSE:.0%} trở xuống, ở giữa giữ trạng thái trước."
        ),
    }


filter_job = Job("breadth_filter_counts")


async def _filter_key() -> list:
    run = await db.latest_run() or {}
    states = (await db.market_points()).get(BREADTH_STATE_SERIES) or []
    return [run.get("id"), run.get("status"), len(states), states[-1] if states else None]


async def _count_filter() -> dict:
    return asdict(await count_filter_sample())


async def _breadth_filter() -> dict:
    """Số đếm đã lưu của mẫu bộ lọc; đọc cả kho nến nên chỉ đếm khi bấm nút."""
    state = await filter_job.state(await _filter_key())
    result = state["result"]
    view = filter_view(Counts(**result)) if result and not state["error"] else {}
    return {
        **view,
        "running": state["running"],
        "line": status_line(
            state,
            what="mẫu bộ lọc độ rộng",
            button="Đếm mẫu",
            takes="Thường mất khoảng 10 giây",
            refresh=5,
            session_busy=busy(),
        ),
    }


@app.post("/market/filter-count")
async def start_filter_count():
    if not busy():
        filter_job.start(await _filter_key(), _count_filter)
    return RedirectResponse("/market#bo-loc-do-rong", status_code=303)


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


# The portfolio walk takes minutes on the 106-symbol list. It runs in a worker process (on the
# event loop it froze every other page) and only from the button on its page.
backtest_job = Job("backtest_walk")


async def _backtest_key() -> list:
    run = await db.latest_run() or {}
    return [run.get("id"), run.get("status"), run.get("finished_at"), await db.universe()]


async def _walk() -> dict:
    symbols = await db.universe()
    inputs = (
        await db.bars("VNINDEX"),
        {symbol: await db.bars(symbol) for symbol in symbols},
        {symbol: await db.ratios(symbol) for symbol in symbols},
        {symbol: await db.articles_for(symbol) for symbol in symbols},
        load_exchanges(),
        {symbol: await db.flow(symbol) for symbol in symbols},
        await db.market_points(),
    )
    return await run_walk(inputs)


@app.post("/backtest/run")
async def start_backtest():
    if not busy():
        backtest_job.start(await _backtest_key(), _walk)
    return RedirectResponse("/backtest", status_code=303)


@app.get("/backtest")
async def backtest_page(request: Request):
    symbols = len(await db.universe())
    state = await backtest_job.state(await _backtest_key())
    return templates.TemplateResponse(
        request,
        "backtest.html",
        {
            "result": None if state["error"] else state["result"],
            "running": state["running"],
            "busy": busy(),
            "line": status_line(
                state,
                what=f"phép đo trên {symbols} mã",
                button="Chạy phép đo",
                takes="Thường mất vài phút",
                refresh=20,
                session_busy=busy(),
            ),
            "paper": await paper.report(),
        },
    )


def _query(value: str) -> str:
    from urllib.parse import quote

    return quote(value)
