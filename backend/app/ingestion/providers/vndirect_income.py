from __future__ import annotations

from datetime import date

import httpx

from app.services.http_utils import BROWSER_HEADERS

VNDIRECT_STATEMENTS = "https://api-finfo.vndirect.com.vn/v4/financial_statements"

# Non-bank P&L
ITEM_NET_REVENUE = 21001  # Doanh thu thuần
ITEM_NET_INCOME_PARENT = 23000  # LNST công ty mẹ
ITEM_NET_INCOME_AFTER_TAX = 23003  # LNST sau thuế

# Bank P&L proxies (no 21001 on bank statements)
ITEM_BANK_NII = 421900  # Thu nhập lãi thuần
ITEM_BANK_TOI = 421701  # Tổng thu nhập hoạt động


def _fiscal_meta(fiscal_date: str, report_type: str) -> dict:
    # fiscalDate is YYYY-MM-DD
    year = int(fiscal_date[:4])
    month = int(fiscal_date[5:7])
    quarter = None
    if report_type == "QUARTER":
        quarter = (month - 1) // 3 + 1
    return {"fiscalDate": fiscal_date, "year": year, "quarter": quarter}


async def _fetch_series(
    client: httpx.AsyncClient,
    symbol: str,
    item_code: int,
    report_type: str,
    size: int,
) -> list[tuple[str, float]]:
    resp = await client.get(
        VNDIRECT_STATEMENTS,
        params={
            "q": f"code:{symbol}~itemCode:{item_code}~reportType:{report_type}",
            "size": size,
            "sort": "fiscalDate:desc",
        },
    )
    if resp.status_code != 200:
        return []
    rows = (resp.json() or {}).get("data") or []
    out: list[tuple[str, float]] = []
    for row in rows:
        fiscal = row.get("fiscalDate")
        raw = row.get("numericValue")
        if not fiscal or raw is None:
            continue
        out.append((str(fiscal)[:10], float(raw)))
    return out


def _merge_periods(
    revenue: list[tuple[str, float]],
    income: list[tuple[str, float]],
    report_type: str,
    limit: int,
) -> list[dict]:
    rev_map = dict(revenue)
    inc_map = dict(income)
    dates = sorted(set(rev_map) | set(inc_map), reverse=True)[:limit]
    period_type = "annual" if report_type == "ANNUAL" else "quarter"
    periods: list[dict] = []
    for fiscal in dates:
        meta = _fiscal_meta(fiscal, report_type)
        periods.append(
            {
                "periodType": period_type,
                "fiscalDate": meta["fiscalDate"],
                "year": meta["year"],
                "quarter": meta["quarter"],
                "netRevenue": rev_map.get(fiscal),
                "netIncome": inc_map.get(fiscal),
            }
        )
    return periods


async def fetch_symbol_income(symbol: str) -> dict:
    """Latest annual + last 4 quarters of revenue and LNST from VNDirect Finfo."""
    sym = symbol.upper()
    result = {
        "symbol": sym,
        "revenueLabel": "Doanh thu thuần",
        "latestAnnual": None,
        "lastQuarters": [],
        "asOf": date.today().isoformat(),
    }

    async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS) as client:
        # Prefer parent NPAT; fall back to after-tax NPAT.
        annual_income = await _fetch_series(client, sym, ITEM_NET_INCOME_PARENT, "ANNUAL", 4)
        quarter_income = await _fetch_series(client, sym, ITEM_NET_INCOME_PARENT, "QUARTER", 6)
        if not annual_income:
            annual_income = await _fetch_series(
                client, sym, ITEM_NET_INCOME_AFTER_TAX, "ANNUAL", 4
            )
        if not quarter_income:
            quarter_income = await _fetch_series(
                client, sym, ITEM_NET_INCOME_AFTER_TAX, "QUARTER", 6
            )

        annual_rev = await _fetch_series(client, sym, ITEM_NET_REVENUE, "ANNUAL", 4)
        quarter_rev = await _fetch_series(client, sym, ITEM_NET_REVENUE, "QUARTER", 6)
        revenue_label = "Doanh thu thuần"

        if not annual_rev and not quarter_rev:
            # Banks / credit institutions
            annual_rev = await _fetch_series(client, sym, ITEM_BANK_NII, "ANNUAL", 4)
            quarter_rev = await _fetch_series(client, sym, ITEM_BANK_NII, "QUARTER", 6)
            revenue_label = "Thu nhập lãi thuần"
            if not annual_rev and not quarter_rev:
                annual_rev = await _fetch_series(client, sym, ITEM_BANK_TOI, "ANNUAL", 4)
                quarter_rev = await _fetch_series(client, sym, ITEM_BANK_TOI, "QUARTER", 6)
                if annual_rev or quarter_rev:
                    revenue_label = "Tổng thu nhập hoạt động"

        result["revenueLabel"] = revenue_label
        annual_periods = _merge_periods(annual_rev, annual_income, "ANNUAL", 1)
        result["latestAnnual"] = annual_periods[0] if annual_periods else None
        result["lastQuarters"] = _merge_periods(quarter_rev, quarter_income, "QUARTER", 4)

    return result
