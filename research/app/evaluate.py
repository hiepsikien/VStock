from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.classify import NewsLabel
from app.config import (
    BANKS,
    BLOCK_LOOKBACK_DAYS,
    DEBT_TO_EQUITY_MAX,
    DILUTION_SHARE_GROWTH,
    EQUITY_MATCH_BONUS,
    EQUITY_MATCH_CASH,
    INSIDER_BUY_DAYS,
    INSIDER_SELL_DAYS,
    NPL_MAX,
    OTHER_FINANCIALS,
    PROVISION_COVERAGE_MIN,
    QUARTER_DUE_DAYS,
)
from app.pattern import Pattern, Regime

RatioMap = dict[str, list[tuple[str, float]]]


@dataclass
class Fundamentals:
    label: str
    reason: str
    template: str
    metrics: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Verdict:
    symbol: str
    as_of: str
    status: str
    regime_open: bool | None
    regime_reason: str
    fa_label: str
    fa_reason: str
    news_state: str
    news_reason: str
    pattern_ready: bool
    pattern_reason: str
    rs: float | None
    priority: int
    stop_price: float | None
    summary: str
    metrics: list[tuple[str, str]]


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def latest_due_quarter_end(as_of: date, due_days: int = QUARTER_DUE_DAYS) -> date:
    """Latest quarter-end whose filing deadline has arrived."""
    found: date | None = None
    for year in (as_of.year, as_of.year - 1):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            period_end = date(year, month, day)
            if as_of >= period_end + timedelta(days=due_days):
                if found is None or period_end > found:
                    found = period_end
    if found is None:
        return date(as_of.year - 1, 12, 31)
    return found


def _at(points: RatioMap, code: str, report: str) -> float | None:
    for day, value in points.get(code, []):
        if day == report:
            return value
    return None


def _latest_report(points: RatioMap, code: str) -> str | None:
    days = [day for day, _value in points.get(code, [])]
    return max(days) if days else None


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _ty(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value / 1e9:.0f} tỷ"


def _shares(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}"


def _share_growth(points: RatioMap, report: str) -> tuple[float | None, str | None, str | None]:
    rows = {day: value for day, value in points.get("OUTSTANDING_SHARES", []) if value > 0}
    if report not in rows:
        return None, "chưa có số cổ phiếu của kỳ này", None
    ordered = sorted(rows)
    index = ordered.index(report)
    if index < 4:
        return None, "chưa đủ 5 kỳ cổ phiếu", None
    previous_day = ordered[index - 4]
    previous = rows[previous_day]
    if previous <= 0:
        return None, "chưa đủ 5 kỳ cổ phiếu", None
    return rows[report] / previous - 1, None, previous_day


def _share_event_kinds(
    articles: list[dict],
    start: date,
    end: date,
) -> set[str]:
    kinds: set[str] = set()
    for article in articles:
        published = parse_day(article.get("published_at"))
        if published is None or published < start or published > end:
            continue
        kind = article.get("kind")
        if kind in {"bonus_shares", "dilution"}:
            kinds.add(kind)
    return kinds


def _economic_share_growth(
    points: RatioMap,
    report: str,
    articles: list[dict],
) -> tuple[float | None, str | None, str | None, float | None]:
    """Return dilution-only share growth, a gap reason, a note, and the raw share change."""
    raw, gap, previous_day = _share_growth(points, report)
    if raw is None or gap or raw <= DILUTION_SHARE_GROWTH or previous_day is None:
        return raw, gap, None, raw

    report_day = parse_day(report)
    previous = parse_day(previous_day)
    if report_day is None or previous is None:
        return raw, None, None, raw
    kinds = _share_event_kinds(articles, previous, report_day + timedelta(days=120))
    if "dilution" in kinds:
        return raw, None, "phát hành lấy tiền", raw
    if "bonus_shares" in kinds:
        return 0.0, None, "thưởng hoặc tách cổ phiếu, không tính pha loãng", raw

    equity_now = _at(points, "OWNERS_EQUITY_AQ", report)
    equity_then = _at(points, "OWNERS_EQUITY_AQ", previous_day)
    if equity_now is None or equity_then is None or equity_then <= 0:
        return None, "số cổ phiếu tăng, chưa rõ chia tách hay phát hành thêm", None, raw
    matched = (equity_now / equity_then - 1) / raw
    if matched < EQUITY_MATCH_BONUS:
        return 0.0, None, "vốn chủ không tăng theo số cổ phiếu, không tính pha loãng", raw
    if matched > EQUITY_MATCH_CASH:
        return raw, None, "vốn chủ tăng cùng số cổ phiếu", raw
    return None, "số cổ phiếu tăng, chưa rõ chia tách hay phát hành thêm", None, raw


def score_fundamentals(
    symbol: str,
    points: RatioMap,
    articles: list[dict] | None = None,
) -> Fundamentals:
    if symbol in OTHER_FINANCIALS:
        return Fundamentals(
            "Chưa đủ số",
            "Chưa có bộ chỉ tiêu cho chứng khoán hoặc bảo hiểm",
            "unsupported",
        )

    bank = symbol in BANKS or bool(points.get("BAD_LOANS_RATIO_AQ"))

    if bank:
        return _score_bank(points)
    if not points.get("NET_SALES_QR") and not points.get("NET_PROFIT_QR"):
        return Fundamentals("Chưa đủ số", "Chưa tải được kết quả kinh doanh", "missing")
    return _score_corporate(points, articles or [])


def _score_corporate(points: RatioMap, articles: list[dict]) -> Fundamentals:
    report = _latest_report(points, "NET_PROFIT_QR")
    if report is None:
        return Fundamentals("Chưa đủ số", "Chưa có lợi nhuận quý", "corporate")

    sales = _at(points, "NET_SALES_QR", report)
    sales_yoy = _at(points, "NET_SALES_QR_GRYOY", report)
    profit = _at(points, "NET_PROFIT_QR", report)
    profit_yoy = _at(points, "NET_PROFIT_QR_GRYOY", report)
    operating_yoy = _at(points, "OPERATING_PROFIT_QR_GRYOY", report)
    cfo_margin = _at(points, "CFO_TO_SALES_QR", report)
    debt_ratio = _at(points, "DEBT_TO_EQUITY_AQ", report)
    share_growth, share_gap, share_note, raw_share_growth = _economic_share_growth(
        points, report, articles
    )

    missing: list[str] = []
    if sales is None:
        missing.append("doanh thu")
    if sales_yoy is None:
        missing.append("tăng trưởng doanh thu")
    if profit is None:
        missing.append("LNST")
    if profit_yoy is None:
        missing.append("tăng trưởng LNST")
    if operating_yoy is None:
        missing.append("tăng trưởng lợi nhuận từ hoạt động kinh doanh")
    if cfo_margin is None or sales is None:
        missing.append("tiền từ hoạt động kinh doanh")
    if debt_ratio is None:
        missing.append("nợ vay trên vốn chủ")
    if share_growth is None:
        missing.append(share_gap or "số cổ phiếu")

    cfo = None if cfo_margin is None or sales is None else cfo_margin * sales
    metrics = [
        ("Kỳ số liệu", report),
        ("Doanh thu thuần quý", _ty(sales)),
        ("Tăng trưởng doanh thu", _pct(sales_yoy)),
        ("LNST công ty mẹ quý", _ty(profit)),
        ("Tăng trưởng LNST", _pct(profit_yoy)),
        ("Tăng trưởng LN từ hoạt động kinh doanh", _pct(operating_yoy)),
        ("Tiền từ hoạt động kinh doanh quý", _ty(cfo)),
        ("Nợ vay / vốn chủ", "—" if debt_ratio is None else f"{debt_ratio:.2f}"),
        ("Tăng cổ phiếu sau 4 quý", _pct(raw_share_growth)),
    ]
    if share_note:
        metrics.append(("Cách tính số cổ phiếu", share_note))
    if missing:
        return Fundamentals(
            "Chưa đủ số",
            "Thiếu " + ", ".join(missing),
            "corporate",
            metrics,
        )

    assert profit is not None and sales_yoy is not None and profit_yoy is not None
    assert operating_yoy is not None and cfo is not None and debt_ratio is not None
    assert share_growth is not None
    failures: list[str] = []
    if profit <= 0:
        failures.append("LNST không dương")
    if sales_yoy < 0:
        failures.append("doanh thu giảm so với cùng kỳ")
    if profit_yoy < 0:
        failures.append("LNST giảm so với cùng kỳ")
    if profit_yoy > 0 and operating_yoy < 0:
        failures.append("LNST tăng trong khi lợi nhuận từ hoạt động kinh doanh giảm")
    if cfo <= 0:
        failures.append("tiền từ hoạt động kinh doanh không dương")
    if debt_ratio > DEBT_TO_EQUITY_MAX:
        failures.append(f"nợ vay/vốn chủ {debt_ratio:.2f} vượt {DEBT_TO_EQUITY_MAX:.1f}")
    if share_growth > DILUTION_SHARE_GROWTH:
        per_share = (1 + profit_yoy) / (1 + share_growth) - 1
        metrics.append(("Tăng LNST trên mỗi cổ phiếu", _pct(per_share)))
        if per_share < 0:
            failures.append("pha loãng làm LNST trên mỗi cổ phiếu giảm")

    if failures:
        return Fundamentals("Không đạt", ". ".join(failures), "corporate", metrics)
    return Fundamentals("Đạt", f"Đạt cổng cơ bản trên kỳ {report}", "corporate", metrics)


def _score_bank(points: RatioMap) -> Fundamentals:
    report = _latest_report(points, "NET_PROFIT_QR")
    if report is None:
        return Fundamentals("Chưa đủ số", "Chưa có lợi nhuận quý", "bank")

    profit = _at(points, "NET_PROFIT_QR", report)
    profit_yoy = _at(points, "NET_PROFIT_QR_GRYOY", report)
    npl = _at(points, "BAD_LOANS_RATIO_AQ", report)
    coverage = _at(points, "PROVISION_BAD_LOANS_AQ", report)
    equity = _at(points, "OWNERS_EQUITY_AQ", report)
    loan_growth = _at(points, "CUSTOMER_LOANS_AQ_GRYOY", report)
    missing: list[str] = []
    if profit is None:
        missing.append("LNST")
    if profit_yoy is None:
        missing.append("tăng trưởng LNST")
    if npl is None:
        missing.append("nợ xấu")
    if coverage is None:
        missing.append("dự phòng")
    if equity is None:
        missing.append("vốn chủ")

    metrics = [
        ("Kỳ số liệu", report),
        ("LNST quý", _ty(profit)),
        ("Tăng trưởng LNST", _pct(profit_yoy)),
        ("Nợ xấu", _pct(npl)),
        ("Bao phủ nợ xấu", _pct(coverage)),
        ("Vốn chủ sở hữu", _ty(equity)),
        ("Tăng trưởng cho vay", _pct(loan_growth)),
    ]
    if missing:
        return Fundamentals("Chưa đủ số", "Thiếu " + ", ".join(missing), "bank", metrics)

    assert profit is not None and profit_yoy is not None and npl is not None
    assert coverage is not None and equity is not None
    failures: list[str] = []
    if profit <= 0:
        failures.append("LNST không dương")
    if profit_yoy < 0:
        failures.append("LNST giảm so với cùng kỳ")
    if npl > NPL_MAX:
        failures.append(f"nợ xấu {_pct(npl)} vượt {_pct(NPL_MAX)}")
    if coverage < PROVISION_COVERAGE_MIN:
        failures.append(f"bao phủ nợ xấu {_pct(coverage)} dưới {_pct(PROVISION_COVERAGE_MIN)}")
    if equity <= 0:
        failures.append("vốn chủ không dương")
    if failures:
        return Fundamentals("Không đạt", ". ".join(failures), "bank", metrics)
    return Fundamentals("Đạt", f"Đạt cổng ngân hàng trên kỳ {report}", "bank", metrics)


def _articles_for_symbol(symbol: str, articles: list[dict], as_of: date) -> list[dict]:
    kept: list[dict] = []
    for article in articles:
        published = parse_day(article.get("published_at"))
        if published is None or published > as_of:
            continue
        symbols = article.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [part for part in symbols.split(",") if part]
        if symbol not in {item.upper() for item in symbols}:
            continue
        if article.get("kind") in (None, "ignore"):
            continue
        kept.append(article)
    kept.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    return kept


def news_gate(
    symbol: str,
    articles: list[dict],
    as_of: date,
    *,
    require_clock: bool,
) -> tuple[str, str, int]:
    """Return news state, reason, and insider-buy priority (1 or 0)."""
    due = latest_due_quarter_end(as_of)
    relevant = _articles_for_symbol(symbol, articles, as_of)
    blocks = []
    sells = []
    buys = []
    clocks = []
    for article in relevant:
        published = parse_day(article.get("published_at"))
        if published is None:
            continue
        age = (as_of - published).days
        kind = article.get("kind")
        if kind in {"suspension", "audit_exception"} and age <= BLOCK_LOOKBACK_DAYS:
            blocks.append(article)
        elif kind == "insider_sell" and age <= INSIDER_SELL_DAYS:
            sells.append(article)
        elif kind == "insider_buy" and age <= INSIDER_BUY_DAYS:
            buys.append(article)
        elif kind == "earnings_release" and published >= due:
            clocks.append(article)

    if blocks:
        title = blocks[0].get("title") or "Công bố rủi ro"
        return "Loại", title, 0
    priority = 1 if buys else 0
    buy_note = f" Có đăng ký mua ngày {parse_day(buys[0].get('published_at'))}." if buys else ""
    if require_clock and not clocks:
        return (
            "Chưa chấm",
            f"Quý đến hạn kết thúc {due.isoformat()} chưa có bài công bố báo cáo trong tin đã tải.",
            priority,
        )
    if sells:
        title = sells[0].get("title") or "Đăng ký bán"
        return "Chờ", title, priority
    if clocks:
        published = parse_day(clocks[0].get("published_at"))
        return "Mở", f"Có bài công bố báo cáo từ {published.isoformat()}.{buy_note}", priority
    return "Mở", f"Không có công bố chặn trong cửa sổ đang xét.{buy_note}", priority


def compose(
    symbol: str,
    as_of: date,
    points: RatioMap,
    articles: list[dict],
    regime: Regime,
    pattern: Pattern,
    *,
    require_clock: bool,
) -> Verdict:
    fundamentals = score_fundamentals(symbol, points, _articles_for_symbol(symbol, articles, as_of))
    news_state, news_reason, priority = news_gate(
        symbol, articles, as_of, require_clock=require_clock
    )

    if pattern.unadjusted:
        status = "Chưa chấm"
        summary = pattern.reason
    elif regime.open is None:
        status = "Chưa chấm"
        summary = regime.reason
    elif regime.open is False:
        status = "Khóa"
        summary = regime.reason
    elif news_state == "Loại" or fundamentals.label == "Không đạt":
        status = "Loại"
        summary = news_reason if news_state == "Loại" else fundamentals.reason
    elif fundamentals.label == "Chưa đủ số" or news_state == "Chưa chấm":
        status = "Chưa chấm"
        summary = news_reason if news_state == "Chưa chấm" else fundamentals.reason
    elif news_state == "Chờ":
        status = "Chờ"
        summary = news_reason
    elif pattern.ready:
        status = "Được vào"
        summary = pattern.reason
    else:
        status = "Theo dõi"
        summary = pattern.reason

    if status == "Được vào" and priority:
        summary = "Ưu tiên vì có đăng ký mua. " + summary

    return Verdict(
        symbol=symbol,
        as_of=as_of.isoformat(),
        status=status,
        regime_open=regime.open,
        regime_reason=regime.reason,
        fa_label=fundamentals.label,
        fa_reason=fundamentals.reason,
        news_state=news_state,
        news_reason=news_reason,
        pattern_ready=pattern.ready,
        pattern_reason=pattern.reason,
        rs=pattern.rs,
        priority=priority if status == "Được vào" else 0,
        stop_price=pattern.stop,
        summary=summary,
        metrics=fundamentals.metrics,
    )
