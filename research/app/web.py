from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app import db, paper
from app.backtest import run_backtest_with_industries
from app.chart import build_chart, build_line_chart
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
    INDUSTRY_GATE_ENFORCED,
    MA_WINDOW,
    MACRO_SYMBOLS,
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
from app.pattern import assess_pattern, market_regime
from app.pipeline import busy, run_session
from app.scheduled import VN
from app.tracking import breadth_rows, filter_counts, filter_view, run_rows, schedule_view
from app.views import (
    flow_label,
    funnel,
    gate_chain,
    group_changes,
    held_by_market,
    hold_reason,
    industry_name,
    lane,
    lane_counts,
    market_headline,
    market_lights,
    news_label,
    paper_alerts,
    render_markdown,
    stamp_lights,
    status_changes,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
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
templates.env.globals["news_label"] = news_label
templates.env.globals["flow_label"] = flow_label
templates.env.globals["industry_name"] = industry_name


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
    # Cancelled before the pool goes, a run in flight keeps its "started" mark and reads as
    # stopped midway, rather than catching the killed worker and storing it as an error.
    tasks = [job.task for job in (backtest_job, filter_job) if job.running]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
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
    same order the backtest buys in, so the page and the measurement read the list alike. While
    the market gates hold the list, the state is the one the name would have if they opened, so
    a locked table still ranks the names that are ready ahead of the rest.
    """
    return sorted(
        verdicts,
        key=lambda item: (
            STATUS_RANK.get(lane(item), 9),
            -item["score"],
            -item["priority"],
            item["symbol"],
        ),
    )


async def _index_days() -> list[str]:
    return [str(bar["trade_date"]) for bar in await db.bars("VNINDEX")]


async def _market_lights(points: dict, verdicts: list[dict]) -> tuple[list[dict], dict]:
    shares = points.get(BREADTH_SERIES) or []
    states = dict(points.get(BREADTH_STATE_SERIES) or [])
    last_day, last_share = shares[-1] if shares else ("", None)
    state = states.get(last_day)
    index_bars = await db.bars("VNINDEX")
    lights = market_lights(
        market_regime(index_bars),
        money_state(points),
        verdicts,
        last_share,
        None if state is None else state > 0.5,
    )
    session = verdicts[0]["as_of"] if verdicts else ""
    money_days = [points[code][-1][0] for code in MARKET_GATE_REQUIRED if points.get(code)]
    days = {
        "index": str(index_bars[-1]["trade_date"]) if index_bars else "",
        "money": max(money_days) if money_days else "",
        "macro": session,
        "breadth": last_day,
        "industry": session,
    }
    headline = market_headline(lights)
    headline["session"] = session
    headline["stale"] = stamp_lights(lights, days, session)
    return lights, headline


def _page(request: Request, name: str, active: str, context: dict):
    return templates.TemplateResponse(request, name, {"active": active, **context})


@app.get("/")
async def dashboard(request: Request, notice: str = "", error: str = ""):
    verdicts = _ordered(await db.latest_verdicts())
    as_of = verdicts[0]["as_of"] if verdicts else ""
    previous_day, previous = await db.previous_statuses(as_of) if as_of else ("", {})
    changes = status_changes(verdicts, previous) if previous else []
    changed = {change["symbol"]: change for change in changes}
    decided = {
        row["symbol"] for row in await db.recent_decisions(500) if row["as_of"] == as_of
    }
    for item in verdicts:
        item["lane"] = lane(item)
        item["held"] = held_by_market(item)
        item["change"] = changed.get(item["symbol"])
        item["industry_label"] = industry_name(item.get("industry_name"))
    points = await db.market_points()
    lights, headline = await _market_lights(points, verdicts)
    report = await paper.report()
    alerts = paper_alerts(await db.open_paper_positions())
    to_confirm = [item for item in verdicts if item["status"] == "Được vào" and item["symbol"] not in decided]
    schedule = schedule_view(await _index_days(), points.get(BREADTH_STATE_SERIES) or [], datetime.now(VN))
    return _page(
        request,
        "dashboard.html",
        "today",
        {
            "verdicts": verdicts,
            "as_of": as_of,
            "lights": lights,
            "headline": headline,
            "funnel": funnel(verdicts),
            "lanes": lane_counts(verdicts),
            "hold": hold_reason(verdicts),
            "held_lanes": {item["lane"] for item in verdicts if item["held"]},
            "missing_open": bool(verdicts) and not any(item.get("open_status") for item in verdicts),
            "changes": group_changes(changes),
            "previous_day": previous_day,
            "to_confirm": to_confirm,
            "alerts": alerts,
            "paper": report,
            "industries": sorted({item["industry_label"] for item in verdicts if item["industry_label"]}),
            "notice": notice,
            "error": error,
            "busy": busy(),
            "run": await db.latest_run(),
            "schedule": schedule,
        },
    )


def _money_value(code: str, value: float) -> str:
    if code == "USDVND":
        return f"{value:,.0f}"
    if code == "NHNN_NET":
        return f"{value:+,.0f}"
    return f"{value:,.2f}"


def _index_chart(index_bars: list[dict], sessions: int = 250) -> dict | None:
    """VN-Index và MA200 của chính nó, một năm gần nhất: khoảng cách là cổng thị trường."""
    closes = [(str(bar["trade_date"]), float(bar["close"])) for bar in index_bars if bar["close"] > 0]
    total = 0.0
    averages = []
    for index, (day, close) in enumerate(closes):
        total += close
        if index >= MA_WINDOW:
            total -= closes[index - MA_WINDOW][1]
        if index >= MA_WINDOW - 1:
            averages.append((day, total / MA_WINDOW))
    return build_line_chart(
        [
            {"name": "VN-Index", "kind": "index", "points": closes[-sessions:]},
            {"name": f"MA{MA_WINDOW}", "kind": "ma", "points": averages[-sessions:]},
        ],
        value_format="{:,.0f}",
    )


def _macro_rows(verdicts: list[dict]) -> list[tuple[str, str]]:
    labels = {label for _code, _symbol, label in MACRO_SYMBOLS}
    groups = dict(verdicts[0]["metric_groups"]) if verdicts else {}
    return [(label, value) for label, value in groups.get("Thị trường", []) if label in labels]


@app.get("/market")
async def market_page(request: Request):
    """Mọi cổng toàn thị trường ở một chỗ: VN-Index, vĩ mô, tiền tệ, độ rộng."""
    points = await db.market_points()
    money = money_state(points)
    verdicts = await db.latest_verdicts()
    lights, headline = await _market_lights(points, verdicts)
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
    index_bars = await db.bars("VNINDEX")
    return _page(
        request,
        "market.html",
        "market",
        {
            "lights": lights,
            "headline": headline,
            "regime": market_regime(index_bars),
            "index_chart": _index_chart(index_bars),
            "macro": verdicts[0]["macro_reason"] if verdicts else "",
            "macro_rows": _macro_rows(verdicts),
            "money": money,
            "rows": rows,
            "thresholds": thresholds(),
            "missing": [LABELS.get(code, code) for code in money.absent],
            "short": [
                (LABELS.get(code, code), have, need) for code, have, need in money.short
            ],
            "policy": POLICY_RATE_HISTORY,
            "latest_day": max(days) if days else "",
            "breadth": _breadth_view(points, [str(bar["trade_date"]) for bar in index_bars]),
        },
    )


def _breadth_view(points: dict[str, list[tuple[str, float]]], index_days: list[str]) -> dict:
    """Số độ rộng mà phiên live đã lưu, xếp theo phiên VN-Index để phiên bỏ lỡ hiện ra."""
    shares = points.get(BREADTH_SERIES) or []
    states = points.get(BREADTH_STATE_SERIES) or []
    state_of = dict(states)
    last_day, last_share = shares[-1] if shares else ("", None)
    state = state_of.get(last_day)
    recent = breadth_rows(index_days, shares, states)
    return {
        "reason": breadth_reason(last_share, None if state is None else state > 0.5) if shares else "",
        "last_day": last_day,
        "sessions": len(shares),
        "recent": [{**row, "share": _pct(row["share"])} for row in recent],
        "unrecorded": sum(1 for row in recent if row["open"] is None),
        "chart": build_line_chart(
            [{"name": "Độ rộng", "kind": "breadth", "points": shares[-250:]}],
            levels=[
                {"value": BREADTH_OPEN, "label": f"mở {BREADTH_OPEN:.0%}", "kind": "open"},
                {"value": BREADTH_CLOSE, "label": f"đóng {BREADTH_CLOSE:.0%}", "kind": "closed"},
            ],
            value_format="{:.0%}",
        ),
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
    view = {}
    if result and not state["error"]:
        try:
            view = filter_view(Counts(**result))
        except TypeError:
            state = {**state, "error": "số đã lưu theo định dạng cũ, không đọc được nữa; bấm “Đếm mẫu” để đếm lại"}
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


@app.post("/lab/filter-count")
@app.post("/market/filter-count")
async def start_filter_count():
    if not busy():
        filter_job.start(await _filter_key(), _count_filter)
    return RedirectResponse("/lab#bo-loc-do-rong", status_code=303)


_BACK = {"/": "/", "/ops": "/ops"}


@app.post("/run")
async def run(back: str = Form("/")):
    target = _BACK.get(back, "/")
    if busy():
        return RedirectResponse(f"{target}?error=Đang+chạy+một+phiên+khác", status_code=303)
    message = await run_session()
    if message.startswith("Phiên lỗi") or message.startswith("Đang chạy"):
        return RedirectResponse(f"{target}?error={_query(message)}", status_code=303)
    return RedirectResponse(f"{target}?notice={_query(message)}", status_code=303)


@app.post("/universe")
async def update_universe(symbol: str = Form(""), action: str = Form("add")):
    cleaned = "".join(ch for ch in symbol.upper() if ch.isalnum())
    if action == "remove" and cleaned:
        await db.remove_symbol(cleaned)
        return RedirectResponse(f"/ops?notice={_query('Đã bỏ ' + cleaned)}#danh-sach", status_code=303)
    if len(cleaned) < 2 or len(cleaned) > 8:
        return RedirectResponse("/ops?error=Mã+không+hợp+lệ#danh-sach", status_code=303)
    await db.add_symbol(cleaned)
    return RedirectResponse(
        f"/ops?notice={_query('Đã thêm ' + cleaned + '. Chạy phiên để chấm mã này.')}#danh-sach",
        status_code=303,
    )


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
    return _page(
        request,
        "symbol.html",
        "today",
        {
            "symbol": sym,
            "item": item,
            "chain": gate_chain(item) if item else [],
            "held": held_by_market(item) if item else False,
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


@app.get("/paper")
async def paper_page(request: Request):
    """Sổ đo tiến: vị thế giấy mở từ các lần xác nhận, và nhật ký mọi lần xác nhận hay bỏ qua."""
    report = await paper.report(200)
    for row in report["rows"]:
        last = row.get("last_price") or row["entry_price"]
        row["room_stop"] = last / row["stop_price"] - 1 if row["stop_price"] else None
        row["to_target"] = None if row.get("tp1_done") else row["target1"] / last - 1
    return _page(
        request,
        "paper.html",
        "paper",
        {
            "paper": report,
            "alerts": paper_alerts(report["rows"]),
            "decisions": await db.recent_decisions(100),
        },
    )


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


_BACKTEST_BACK = {"/backtest": "/backtest", "/lab": "/lab#do-sau-phi"}


@app.post("/backtest/run")
async def start_backtest(back: str = Form("/backtest")):
    if not busy():
        backtest_job.start(await _backtest_key(), _walk)
    return RedirectResponse(_BACKTEST_BACK.get(back, "/backtest"), status_code=303)


async def _backtest_state() -> dict:
    symbols = len(await db.universe())
    state = await backtest_job.state(await _backtest_key())
    return {
        "result": None if state["error"] else state["result"],
        "failed": bool(state["error"]),
        "running": state["running"],
        "line": status_line(
            state,
            what=f"phép đo trên {symbols} mã",
            button="Chạy phép đo",
            takes="Thường mất vài phút",
            refresh=20,
            session_busy=busy(),
        ),
    }


@app.get("/backtest")
async def backtest_page(request: Request):
    return _page(request, "backtest.html", "lab", {**await _backtest_state(), "busy": busy()})


def _report_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return path.stem


# Thí nghiệm nào đọc báo cáo nào: thẻ của trang Nghiên cứu dẫn thẳng tới số đã đo.
_EXPERIMENT_REPORTS = {
    "breadth": ("breadth_gate", "breadth_gate_explained"),
    "industry": ("industry_gate", "industry_sweep"),
}


def _reports(names: tuple[str, ...]) -> list[dict]:
    out = []
    for name in names:
        path = REPORTS / f"{name}.md"
        if path.exists():
            out.append({"name": name, "title": _report_title(path)})
    return out


@app.get("/lab")
async def lab_page(request: Request):
    """Mỗi giả thuyết một thẻ: đang đo gì, đã đủ mẫu chưa, luật có đang khóa danh sách không."""
    known = {name for names in _EXPERIMENT_REPORTS.values() for name in names}
    others = sorted(path.stem for path in REPORTS.glob("*.md") if path.stem not in known)
    breadth_filter = await _breadth_filter()
    return _page(
        request,
        "lab.html",
        "lab",
        {
            "backtest": await _backtest_state(),
            "breadth_filter": breadth_filter,
            "breadth_enforced": BREADTH_GATE_ENFORCED,
            "industry_enforced": INDUSTRY_GATE_ENFORCED,
            "breadth_reports": _reports(_EXPERIMENT_REPORTS["breadth"]),
            "industry_reports": _reports(_EXPERIMENT_REPORTS["industry"]),
            "other_reports": _reports(tuple(others)),
            "busy": busy(),
        },
    )


@app.get("/lab/report/{name}")
async def report_page(request: Request, name: str):
    path = REPORTS / f"{name}.md"
    if not name.replace("_", "").isalnum() or not path.exists():
        raise HTTPException(status_code=404)
    return _page(
        request,
        "report.html",
        "lab",
        {
            "name": name,
            "title": _report_title(path),
            "body": Markup(render_markdown(path.read_text(encoding="utf-8"))),
        },
    )


@app.get("/ops")
async def ops_page(request: Request, notice: str = "", error: str = ""):
    """Hệ thống có chạy đúng không: lịch chạy, các lần chạy, độ tươi của dữ liệu, danh sách mã."""
    points = await db.market_points()
    index_days = await _index_days()
    verdicts = await db.latest_verdicts()
    freshness = [
        ("Nến VN-Index mới nhất", index_days[-1] if index_days else "chưa có"),
        ("Phiên chấm gần nhất", verdicts[0]["as_of"] if verdicts else "chưa có"),
        ("Số mã đã chấm", str(len(verdicts))),
    ]
    for code, label, _unit, _symbol in MARKET_SERIES:
        series = points.get(code) or []
        freshness.append((label, f"{series[-1][0]} ({len(series)} phiên)" if series else "chưa có số"))
    shares = points.get(BREADTH_SERIES) or []
    freshness.append(("Độ rộng", f"{shares[-1][0]} ({len(shares)} phiên)" if shares else "chưa có số"))
    return _page(
        request,
        "ops.html",
        "ops",
        {
            "notice": notice,
            "error": error,
            "busy": busy(),
            "run": await db.latest_run(),
            "runs": run_rows(await db.recent_runs(20), busy()),
            "schedule": schedule_view(
                index_days, points.get(BREADTH_STATE_SERIES) or [], datetime.now(VN)
            ),
            "freshness": freshness,
            "universe": await db.universe(),
        },
    )


def _query(value: str) -> str:
    from urllib.parse import quote

    return quote(value)
