from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.classify import NewsLabel
from app.config import (
    BANKS,
    BLOCK_LOOKBACK_DAYS,
    DEBT_TO_EQUITY_INSURER_MAX,
    DEBT_TO_EQUITY_MAX,
    DILUTION_SHARE_GROWTH,
    EQUITY_MATCH_BONUS,
    EQUITY_MATCH_CASH,
    F_SCORE_MIN_ITEMS,
    F_SCORE_MIN_PASS,
    INDUSTRY_GATE_ENFORCED,
    INSIDER_BUY_DAYS,
    INSIDER_SELL_DAYS,
    INSURERS,
    MACRO_SYMBOLS,
    MARKET_SERIES,
    NPL_MAX,
    PE_CEILING,
    PROVISION_COVERAGE_MIN,
    QUARTER_DUE_DAYS,
    SCORE_ENTRY_MIN,
    SCORE_WEIGHTS,
    SECURITIES,
)
from app.flow import ACCUMULATION, FlowState, flow_score, missing_flow
from app.macro import Macro
from app.money import Money
from app.pattern import Pattern, Regime

RatioMap = dict[str, list[tuple[str, float]]]


@dataclass
class Fundamentals:
    label: str
    reason: str
    template: str
    metrics: list[tuple[str, str]] = field(default_factory=list)
    # Piotroski-style checklist count. None means too few items were computable.
    f_score: int | None = None
    f_score_max: int = 0
    f_score_notes: list[str] = field(default_factory=list)
    # Forensic flags. They never fail a name on their own, they are shown instead.
    warnings: list[str] = field(default_factory=list)


@dataclass
class Valuation:
    label: str
    reason: str
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
    # Composite score. It ranks candidates; the hard gates above still decide the status.
    score: int = 0
    score_parts: list[tuple[str, int]] = field(default_factory=list)
    score_ok: bool = False
    flow_state: str = ""
    flow_reason: str = ""
    flow_level: str = "missing"
    macro_reason: str = ""
    macro_block: bool = False
    # Cổng tiền tệ: mở, thắt, hay chưa chấm vì thiếu chuỗi.
    market_reason: str = ""
    market_open: bool | None = None
    valuation_label: str = ""
    valuation_reason: str = ""
    patterns: tuple[str, ...] = ()
    pattern_score: int = 0
    f_score: int | None = None
    f_score_max: int = 0
    warnings: list[str] = field(default_factory=list)
    # Nền giá: con số đứng sau cổng nền phẳng và khối lượng phá nền.
    base_ceiling: float | None = None
    base_advance: float | None = None
    base_depth: float | None = None
    base_sessions: int = 0
    breakout_volume_ratio: float | None = None
    failed_breakout: str | None = None
    # Số đang dùng chia theo lớp quyết định, dựng ở compose.
    metric_groups: list[tuple[str, list[tuple[str, str]]]] = field(default_factory=list)
    industry_name: str | None = None
    industry_open: bool | None = None

    def row(self) -> dict:
        """Shape used by store.save_verdicts, so the mapping lives in one place."""
        return {
            "as_of": self.as_of,
            "symbol": self.symbol,
            "status": self.status,
            "regime_open": self.regime_open,
            "regime_reason": self.regime_reason,
            "fa_label": self.fa_label,
            "fa_reason": self.fa_reason,
            "news_state": self.news_state,
            "news_reason": self.news_reason,
            "pattern_ready": self.pattern_ready,
            "pattern_reason": self.pattern_reason,
            "rs": self.rs,
            "priority": self.priority,
            "stop_price": self.stop_price,
            "summary": self.summary,
            "metrics": [list(item) for item in self.metrics],
            "score": self.score,
            "flow_state": self.flow_state,
            "extra": {
                "score_parts": [list(item) for item in self.score_parts],
                "score_ok": self.score_ok,
                "flow_reason": self.flow_reason,
                "flow_level": self.flow_level,
                "macro_reason": self.macro_reason,
                "macro_block": self.macro_block,
                "market_reason": self.market_reason,
                "market_open": self.market_open,
                "valuation_label": self.valuation_label,
                "valuation_reason": self.valuation_reason,
                "patterns": list(self.patterns),
                "pattern_score": self.pattern_score,
                "f_score": self.f_score,
                "f_score_max": self.f_score_max,
                "warnings": list(self.warnings),
                "base_ceiling": self.base_ceiling,
                "base_advance": self.base_advance,
                "base_depth": self.base_depth,
                "base_sessions": self.base_sessions,
                "breakout_volume_ratio": self.breakout_volume_ratio,
                "failed_breakout": self.failed_breakout,
                "industry_name": self.industry_name,
                "industry_open": self.industry_open,
                "metric_groups": [
                    [title, [list(metric) for metric in metrics]]
                    for title, metrics in self.metric_groups
                ],
            },
        }


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


def _price(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}"


def _times(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}x"


def _pattern_metrics(pattern: Pattern) -> list[tuple[str, str]]:
    """The numbers behind the base gate, read next to the sentence they produced."""
    return [
        ("Số phiên nền", str(pattern.base_sessions)),
        ("Đỉnh nền", _price(pattern.base_ceiling)),
        ("Đáy nền (dừng lỗ)", _price(pattern.stop)),
        ("Độ sâu nền", _pct(pattern.base_depth)),
        ("Nhịp tăng trước nền", _pct(pattern.base_advance)),
        ("Khối lượng 10 phiên so 10 phiên trước", _times(pattern.volume_ratio)),
        ("Khối lượng nến phá so nền", _times(pattern.breakout_volume_ratio)),
        ("Điểm cấu trúc", f"{pattern.score}/100"),
    ]


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


def _quarter_days(points: RatioMap, code: str) -> list[str]:
    return sorted({day for day, value in points.get(code, []) if value is not None})


def _lagged_value(points: RatioMap, code: str, report: str, steps: int = 4) -> float | None:
    """Value the same number of quarters back so a YoY field lines up with it."""
    days = _quarter_days(points, code)
    if report not in days:
        return None
    index = days.index(report)
    if index < steps:
        return None
    return _at(points, code, days[index - steps])


def score_checklist(
    points: RatioMap,
    report: str,
    *,
    profit: float,
    profit_yoy: float,
    sales: float,
    sales_yoy: float,
    cfo_margin: float,
    debt_ratio: float,
    share_growth: float,
) -> tuple[int | None, int, list[str], list[str]]:
    """Ratio-derived Piotroski checklist.

    Returns score, number of computable items, the items that failed, and forensic
    warnings. The score is None when fewer than F_SCORE_MIN_ITEMS items could be
    computed, because a partial count would overstate the name.

    Limitation: VNDirect Finfo exposes no gross-margin and no receivables code, so
    the gross-margin item is missing and the accrual check uses inventory plus the
    cash-margin trend instead of trade receivables.
    """
    assets_now = _at(points, "TOTAL_ASSETS_AQ", report)
    assets_then = _lagged_value(points, "TOTAL_ASSETS_AQ", report)
    assets_growth = None
    if assets_now is not None and assets_then and assets_then > 0:
        assets_growth = assets_now / assets_then - 1

    current_now = _at(points, "CURRENT_RATIO_AQ", report)
    current_then = _lagged_value(points, "CURRENT_RATIO_AQ", report)
    debt_then = _lagged_value(points, "DEBT_TO_EQUITY_AQ", report)

    checks: list[tuple[str, bool | None]] = [
        ("LNST dương", profit > 0),
        ("Dòng tiền kinh doanh dương", cfo_margin > 0),
        ("Tiền thu về lớn hơn LNST", cfo_margin * sales > profit),
        ("ROA tăng", None if assets_growth is None else profit_yoy > assets_growth),
        (
            "Vòng quay tài sản không giảm",
            None if assets_growth is None else sales_yoy >= assets_growth,
        ),
        (
            "Thanh khoản ngắn hạn tăng",
            None if current_now is None or current_then is None else current_now > current_then,
        ),
        ("Đòn bẩy giảm", None if debt_then is None else debt_ratio < debt_then),
        ("Không phát hành thêm cổ phiếu", share_growth <= DILUTION_SHARE_GROWTH),
    ]

    available = [value for _name, value in checks if value is not None]
    failures = [name for name, value in checks if value is False]
    score = len(available) - len(failures)

    warnings: list[str] = []
    cfo_then = _lagged_value(points, "CFO_TO_SALES_QR", report)
    if profit_yoy > 0 and cfo_then is not None and cfo_margin < cfo_then:
        warnings.append("Lợi nhuận tăng nhưng biên dòng tiền thu hẹp")
    inventory_now = _at(points, "INVENTORY_AQ", report)
    inventory_then = _lagged_value(points, "INVENTORY_AQ", report)
    if inventory_now and inventory_then and inventory_then > 0:
        inventory_growth = inventory_now / inventory_then - 1
        if inventory_growth > sales_yoy + 0.10:
            warnings.append("Tồn kho phình nhanh hơn doanh thu")

    if len(available) < F_SCORE_MIN_ITEMS:
        return None, len(available), failures, warnings
    return score, len(available), failures, warnings


def score_valuation(valuation: dict | None) -> Valuation:
    """P/E ceiling from the market database. It is a snapshot, so the backtest skips it."""
    if not valuation:
        return Valuation("Chưa có số", "Chưa đọc được định giá từ kho thị trường")
    pe = valuation.get("pe")
    pb = valuation.get("pb")
    roe = valuation.get("roe")
    updated = str(valuation.get("updated_at") or "")[:10]
    metrics = [
        ("P/E", "—" if pe is None else f"{pe:.1f}"),
        ("P/B", "—" if pb is None else f"{pb:.2f}"),
        ("ROE", _pct(roe)),
    ]
    if updated:
        metrics.append(("Cập nhật định giá", updated))
    if pe is None or pe <= 0:
        return Valuation("Chưa có số", "Chưa có P/E dương trong kho thị trường", metrics)
    if pe > PE_CEILING:
        return Valuation("Không đạt", f"P/E {pe:.1f} vượt trần {PE_CEILING:.0f}", metrics)
    return Valuation("Đạt", f"P/E {pe:.1f} trong trần {PE_CEILING:.0f}", metrics)


def score_fundamentals(
    symbol: str,
    points: RatioMap,
    articles: list[dict] | None = None,
) -> Fundamentals:
    bank = symbol in BANKS or bool(points.get("BAD_LOANS_RATIO_AQ"))
    if bank:
        return _score_bank(points)
    if symbol in SECURITIES:
        return _score_services(points, articles or [], "securities")
    if symbol in INSURERS:
        return _score_services(points, articles or [], "insurer")
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
    assert sales is not None and cfo_margin is not None and share_growth is not None

    f_score, f_max, f_failed, warnings = score_checklist(
        points,
        report,
        profit=profit,
        profit_yoy=profit_yoy,
        sales=sales,
        sales_yoy=sales_yoy,
        cfo_margin=cfo_margin,
        debt_ratio=debt_ratio,
        share_growth=share_growth,
    )
    if f_score is None:
        metrics.append(("Điểm cơ bản (F-Score)", f"chưa đủ số ({f_max} tiêu chí)"))
    else:
        metrics.append(("Điểm cơ bản (F-Score)", f"{f_score}/{f_max}"))
        if f_failed:
            metrics.append(("Tiêu chí chưa đạt", ", ".join(f_failed)))
    for warning in warnings:
        metrics.append(("Cảnh báo số liệu", warning))

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
    if f_score is not None and f_score < F_SCORE_MIN_PASS:
        failures.append(f"điểm cơ bản yếu {f_score}/{f_max}")

    if failures:
        return Fundamentals(
            "Không đạt",
            ". ".join(failures),
            "corporate",
            metrics,
            f_score,
            f_max,
            f_failed,
            warnings,
        )
    return Fundamentals(
        "Đạt",
        f"Đạt cổng cơ bản trên kỳ {report}",
        "corporate",
        metrics,
        f_score,
        f_max,
        f_failed,
        warnings,
    )


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


def _score_services(points: RatioMap, articles: list[dict], template: str) -> Fundamentals:
    """Brokers and insurers: profit, revenue and equity matter, the corporate debt gate does not."""
    report = _latest_report(points, "NET_PROFIT_QR")
    if report is None:
        return Fundamentals("Chưa đủ số", "Chưa có lợi nhuận quý", template)

    profit = _at(points, "NET_PROFIT_QR", report)
    profit_yoy = _at(points, "NET_PROFIT_QR_GRYOY", report)
    sales = _at(points, "NET_SALES_QR", report)
    sales_yoy = _at(points, "NET_SALES_QR_GRYOY", report)
    equity = _at(points, "OWNERS_EQUITY_AQ", report)
    debt_ratio = _at(points, "DEBT_TO_EQUITY_AQ", report)
    share_growth, share_gap, share_note, raw_share_growth = _economic_share_growth(
        points, report, articles
    )

    missing: list[str] = []
    if profit is None:
        missing.append("LNST")
    if profit_yoy is None:
        missing.append("tăng trưởng LNST")
    if sales_yoy is None:
        missing.append("tăng trưởng doanh thu")
    if equity is None:
        missing.append("vốn chủ sở hữu")
    if share_growth is None:
        missing.append(share_gap or "số cổ phiếu")

    debt_ceiling = DEBT_TO_EQUITY_INSURER_MAX if template == "insurer" else None
    metrics = [
        ("Kỳ số liệu", report),
        ("Doanh thu quý", _ty(sales)),
        ("Tăng trưởng doanh thu", _pct(sales_yoy)),
        ("LNST quý", _ty(profit)),
        ("Tăng trưởng LNST", _pct(profit_yoy)),
        ("Vốn chủ sở hữu", _ty(equity)),
        ("Nợ vay / vốn chủ", "—" if debt_ratio is None else f"{debt_ratio:.2f}"),
        ("Tăng cổ phiếu sau 4 quý", _pct(raw_share_growth)),
    ]
    if debt_ceiling is not None:
        metrics.append(("Trần nợ vay / vốn chủ", f"{debt_ceiling:.1f}"))
    else:
        metrics.append(("Ghi chú", "Đòn bẩy margin không chịu trần như doanh nghiệp"))
    if share_note:
        metrics.append(("Cách tính số cổ phiếu", share_note))
    if missing:
        return Fundamentals("Chưa đủ số", "Thiếu " + ", ".join(missing), template, metrics)

    assert profit is not None and profit_yoy is not None and equity is not None
    assert sales_yoy is not None and share_growth is not None
    failures: list[str] = []
    if profit <= 0:
        failures.append("LNST không dương")
    if profit_yoy < 0:
        failures.append("LNST giảm so với cùng kỳ")
    if sales_yoy < 0:
        failures.append("doanh thu giảm so với cùng kỳ")
    if equity <= 0:
        failures.append("vốn chủ không dương")
    if debt_ceiling is not None and debt_ratio is not None and debt_ratio > debt_ceiling:
        failures.append(f"nợ vay/vốn chủ {debt_ratio:.2f} vượt {debt_ceiling:.1f}")
    if share_growth > DILUTION_SHARE_GROWTH:
        per_share = (1 + profit_yoy) / (1 + share_growth) - 1
        metrics.append(("Tăng LNST trên mỗi cổ phiếu", _pct(per_share)))
        if per_share < 0:
            failures.append("pha loãng làm LNST trên mỗi cổ phiếu giảm")

    label = "chứng khoán" if template == "securities" else "bảo hiểm"
    if failures:
        return Fundamentals("Không đạt", ". ".join(failures), template, metrics)
    return Fundamentals("Đạt", f"Đạt cổng {label} trên kỳ {report}", template, metrics)


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


def _rs_points(rs: float | None) -> int:
    """Relative strength pays in full once a name beats the index by ten points."""
    if rs is None or rs <= 0:
        return 0
    weight = SCORE_WEIGHTS["rs"]
    # round, not int: 8/10 of the weight must not collapse to seven on a float artifact.
    return int(round(weight * min(1.0, rs / 0.10)))


def compose_score(
    fundamentals: Fundamentals,
    flow: FlowState,
    pattern: Pattern,
    rs: float | None,
    priority: int,
) -> tuple[int, list[tuple[str, int]]]:
    """Composite 0-100. It ranks candidates, the gates still decide the status."""
    parts = [
        ("Cơ bản", SCORE_WEIGHTS["fa"] if fundamentals.label == "Đạt" else 0),
        ("Dòng tiền", flow_score(flow.level)),
        ("Nền giá", int(SCORE_WEIGHTS["pattern"] * pattern.score / 100)),
        ("Sức mạnh", _rs_points(rs)),
        ("Tin", SCORE_WEIGHTS["news"] if priority else SCORE_WEIGHTS["news"] // 2),
    ]
    return sum(value for _label, value in parts), parts


# The points each bar of the score table is worth, keyed the way compose_score labels them.
# The page draws a bar against the ceiling of its own line, so a part that is full shows a
# full bar even when another part of the same name scores higher.
SCORE_CEILINGS = {
    "Cơ bản": SCORE_WEIGHTS["fa"],
    "Dòng tiền": flow_score(ACCUMULATION),
    "Nền giá": SCORE_WEIGHTS["pattern"],
    "Sức mạnh": SCORE_WEIGHTS["rs"],
    "Tin": SCORE_WEIGHTS["news"],
}

# Where every number belongs on the symbol page. compose() stores the groups it built from the
# producers; a verdict stored before that grouping existed only has the flat list, so here the label
# is the clue. Titles match the groups compose() builds and the headings the page looks up, and
# tests/test_layers.py keeps the labels level with what the producers emit.
UNPLACED_SECTION = "Khác"

METRIC_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Cơ bản",
        (
            "Kỳ số liệu",
            "Doanh thu thuần quý",
            "Doanh thu quý",
            "Tăng trưởng doanh thu",
            "LNST công ty mẹ quý",
            "LNST quý",
            "Tăng trưởng LNST",
            "Tăng trưởng LN từ hoạt động kinh doanh",
            "Tiền từ hoạt động kinh doanh quý",
            "Nợ vay / vốn chủ",
            "Trần nợ vay / vốn chủ",
            "Nợ xấu",
            "Bao phủ nợ xấu",
            "Vốn chủ sở hữu",
            "Tăng trưởng cho vay",
            "Tăng cổ phiếu sau 4 quý",
            "Tăng LNST trên mỗi cổ phiếu",
            "Cách tính số cổ phiếu",
            "Ghi chú",
            "Điểm cơ bản (F-Score)",
            "Tiêu chí chưa đạt",
            "Cảnh báo số liệu",
        ),
    ),
    ("Định giá", ("P/E", "P/B", "ROE", "Cập nhật định giá")),
    ("Dòng tiền ngoại", ("Dòng tiền ngoại", "Giá trị ròng", "Room ngoại còn")),
    (
        "Thị trường",
        tuple(label for _code, _symbol, label in MACRO_SYMBOLS)
        + tuple(label for _code, label, _unit, _symbol in MARKET_SERIES),
    ),
    (
        "Nền giá",
        (
            "Số phiên nền",
            "Đỉnh nền",
            "Đáy nền (dừng lỗ)",
            "Độ sâu nền",
            "Nhịp tăng trước nền",
            "Khối lượng 10 phiên so 10 phiên trước",
            "Khối lượng nến phá so nền",
            "Điểm cấu trúc",
        ),
    ),
)


def group_metrics(metrics) -> list[tuple[str, list[tuple[str, str]]]]:
    """Sort a flat list of numbers into the sections of the page, keeping their order.

    A row stored without metric_groups loses the boundaries between layers, so each label is placed
    on its own. A label no section claims still reaches the page, under UNPLACED_SECTION, instead of
    being dropped.
    """
    places = {label: title for title, labels in METRIC_SECTIONS for label in labels}
    buckets: dict[str, list[tuple[str, str]]] = {title: [] for title, _labels in METRIC_SECTIONS}
    unplaced: list[tuple[str, str]] = []
    for label, value in metrics:
        title = places.get(label)
        if title is None:
            unplaced.append((label, value))
        else:
            buckets[title].append((label, value))
    groups = [(title, rows) for title, rows in buckets.items() if rows]
    if unplaced:
        groups.append((UNPLACED_SECTION, unplaced))
    return groups


def compose(
    symbol: str,
    as_of: date,
    points: RatioMap,
    articles: list[dict],
    regime: Regime,
    pattern: Pattern,
    *,
    require_clock: bool,
    valuation: dict | None = None,
    flow: FlowState | None = None,
    macro: Macro | None = None,
    market: Money | None = None,
    industry_name: str | None = None,
    industry_open: bool | None = None,
) -> Verdict:
    fundamentals = score_fundamentals(symbol, points, _articles_for_symbol(symbol, articles, as_of))
    valuation_state = score_valuation(valuation)
    flow_state = flow or missing_flow()
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
    # Cổng tiền tệ đứng cạnh cổng VN-Index và là cổng AND: danh sách chỉ được xét tiếp khi
    # tiền chưa thắt. Chuỗi còn thiếu thì "Chưa chấm", cùng kiểu với một mã thiếu báo cáo,
    # và không mã nào bị tự loại vì chuyện tiền tệ.
    elif market is not None and market.open is None:
        status = "Chưa chấm"
        summary = market.reason
    elif market is not None and market.open is False:
        status = "Khóa"
        summary = market.reason
    elif (
        news_state == "Loại"
        or fundamentals.label == "Không đạt"
        or valuation_state.label == "Không đạt"
    ):
        status = "Loại"
        if news_state == "Loại":
            summary = news_reason
        elif fundamentals.label == "Không đạt":
            summary = fundamentals.reason
        else:
            summary = f"Định giá: {valuation_state.reason}"
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

    # Flow và vĩ mô chỉ hạ cấp một lệnh sắp vào, không đổi các trạng thái khác.
    if status == "Được vào" and flow_state.state == "Chờ":
        status = "Chờ"
        summary = flow_state.reason
    if status == "Được vào" and macro is not None and macro.block:
        status = "Theo dõi"
        summary = f"Vĩ mô chặn vào: {macro.reason}"
    # Vĩ mô tải lỗi thì macro_state không dựng được dòng nào và trả risk None. Dữ liệu thiếu
    # không phải là dữ liệu tốt: hạ lệnh sắp vào xuống Theo dõi, cùng chỗ với lần chặn đã thấy,
    # thay vì để cổng rủi ro mở vì lý do không liên quan tới thị trường.
    elif status == "Được vào" and macro is not None and macro.risk is None:
        status = "Theo dõi"
        summary = f"Vĩ mô chưa có số: {macro.reason}"

    # Cổng ngành chỉ đổi Được vào khi phép đo đã cho phép. Trước đó nó chỉ được ghi vào verdict.
    if status == "Được vào" and INDUSTRY_GATE_ENFORCED and industry_open is False:
        status = "Theo dõi"
        summary = "Ngành đang đóng"

    if status == "Được vào" and priority:
        summary = "Ưu tiên vì có đăng ký mua. " + summary

    score, score_parts = compose_score(fundamentals, flow_state, pattern, pattern.rs, priority)
    effective_priority = max(priority, flow_state.priority) if status == "Được vào" else 0

    # The numbers, grouped by the layer that decides: the page reads them in that order.
    metric_groups = [
        ("Cơ bản", list(fundamentals.metrics)),
        ("Định giá", list(valuation_state.metrics)),
        ("Dòng tiền ngoại", list(flow_state.metrics)),
        # Cổng thị trường gồm hai phần: VN-Index trên MA200 và liên thị trường, rồi tiền tệ.
        (
            "Thị trường",
            (list(macro.metrics) if macro else []) + (list(market.metrics) if market else []),
        ),
        ("Nền giá", _pattern_metrics(pattern)),
    ]
    # The same numbers in one list, for a reader that has no room for sections, and for the store,
    # which files a row written without groups back into sections by label (see group_metrics).
    metrics = [metric for _title, rows in metric_groups for metric in rows]

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
        priority=effective_priority,
        stop_price=pattern.stop,
        summary=summary,
        metrics=metrics,
        score=score,
        score_parts=score_parts,
        score_ok=score >= SCORE_ENTRY_MIN,
        flow_state=flow_state.state,
        flow_reason=flow_state.reason,
        flow_level=flow_state.level,
        macro_reason=macro.reason if macro else "",
        macro_block=bool(macro and macro.block),
        market_reason=market.reason if market else "",
        market_open=market.open if market else None,
        valuation_label=valuation_state.label,
        valuation_reason=valuation_state.reason,
        patterns=pattern.patterns,
        pattern_score=pattern.score,
        f_score=fundamentals.f_score,
        f_score_max=fundamentals.f_score_max,
        warnings=fundamentals.warnings,
        base_ceiling=pattern.base_ceiling,
        base_advance=pattern.base_advance,
        base_depth=pattern.base_depth,
        base_sessions=pattern.base_sessions,
        breakout_volume_ratio=pattern.breakout_volume_ratio,
        failed_breakout=pattern.failed_breakout,
        metric_groups=metric_groups,
        industry_name=industry_name,
        industry_open=industry_open,
    )
