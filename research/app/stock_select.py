"""Shortlist inside an open industry: drop balance-sheet breaches, keep the stronger half, rank by cheapness."""

from __future__ import annotations

from datetime import date

from app.config import (
    BANKS,
    DEBT_TO_EQUITY_INSURER_MAX,
    DEBT_TO_EQUITY_MAX,
    DILUTION_SHARE_GROWTH,
    INSURERS,
    NPL_MAX,
    PROVISION_COVERAGE_MIN,
    SECURITIES,
)
from app.evaluate import _at, _economic_share_growth, _latest_report, growth_yoy
from app.valuation import cheap_versus


def balance_sheet_block(symbol: str, points: dict, articles: list[dict] | None = None) -> str | None:
    """Debt, bad loans, or harmful dilution. A weak profit year is not a reason to leave the list."""
    articles = articles or []
    if symbol in BANKS or points.get("BAD_LOANS_RATIO_AQ"):
        report = _latest_report(points, "NET_PROFIT_QR")
        if report is None:
            return None
        npl = _at(points, "BAD_LOANS_RATIO_AQ", report)
        coverage = _at(points, "PROVISION_BAD_LOANS_AQ", report)
        equity = _at(points, "OWNERS_EQUITY_AQ", report)
        if npl is not None and npl > NPL_MAX:
            return "nợ xấu vượt trần"
        if coverage is not None and coverage < PROVISION_COVERAGE_MIN:
            return "bao phủ nợ xấu dưới trần"
        if equity is not None and equity <= 0:
            return "vốn chủ không dương"
        return None
    report = _latest_report(points, "NET_PROFIT_QR")
    if report is None:
        return None
    debt = _at(points, "DEBT_TO_EQUITY_AQ", report)
    ceiling = DEBT_TO_EQUITY_INSURER_MAX if symbol in INSURERS else DEBT_TO_EQUITY_MAX
    if symbol not in SECURITIES and debt is not None and debt > ceiling:
        return "nợ vay vượt trần"
    profit_yoy, _derived = growth_yoy(points, "NET_PROFIT_QR_GRYOY", "NET_PROFIT_QR", report)
    share_growth, _gap, _note, _raw = _economic_share_growth(points, report, articles)
    if (
        share_growth is not None
        and profit_yoy is not None
        and share_growth > DILUTION_SHARE_GROWTH
        and (1 + profit_yoy) / (1 + share_growth) - 1 < 0
    ):
        return "pha loãng làm lợi nhuận trên mỗi cổ phiếu giảm"
    return None


def position_rank(symbol: str, market_caps: dict[str, float | None], revenues: dict[str, float | None]) -> int:
    """Better of the market-cap rank and the revenue rank. Rank 1 is the largest."""
    def _rank(values: dict[str, float | None]) -> int | None:
        ordered = sorted(
            ((value, name) for name, value in values.items() if value is not None),
            reverse=True,
        )
        for index, (_value, name) in enumerate(ordered, start=1):
            if name == symbol:
                return index
        return None

    ranks = [rank for rank in (_rank(market_caps), _rank(revenues)) if rank is not None]
    if not ranks:
        return len(market_caps) + 1
    return min(ranks)


def shortlist(
    rows: list[dict],
    *,
    per_industry: int = 3,
) -> list[str]:
    """rows need symbol, block, position, cheap_industry, cheap_self. Already one open industry."""
    eligible = [row for row in rows if not row.get("block")]
    if not eligible:
        return []
    eligible.sort(key=lambda row: row["position"])
    kept = eligible[: max(1, (len(eligible) + 1) // 2)]

    def _cheap_key(row: dict) -> tuple:
        industry = row.get("cheap_industry")
        own = row.get("cheap_self")
        return (
            industry is None,
            industry if industry is not None else 0,
            own is None,
            own if own is not None else 0,
        )

    kept.sort(key=_cheap_key)
    return [row["symbol"] for row in kept[:per_industry]]


def revenue_on(symbol: str, points: dict, as_of: date) -> float | None:
    """Latest visible quarterly sales, or customer loans for a bank."""
    from app.valuation import _visible

    if symbol in BANKS or points.get("CUSTOMER_LOANS_AQ"):
        series = points.get("CUSTOMER_LOANS_AQ") or []
    else:
        series = points.get("NET_SALES_QR") or []
    visible = _visible(series, as_of, 45)
    if not visible:
        return None
    return visible[-1][1]


def cheap_pair(current: float | None, own_history: list[float], peer_values: list[float]) -> tuple[float | None, float | None]:
    own = None
    positives = sorted(value for value in own_history if value and value > 0)
    if positives:
        mid = positives[len(positives) // 2]
        own = cheap_versus(current, mid)
    peers = sorted(value for value in peer_values if value and value > 0)
    peer = cheap_versus(current, peers[len(peers) // 2] if peers else None)
    return own, peer
