from __future__ import annotations

BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

ENTRADE_HEADERS = {
    **BROWSER_HEADERS,
    "Origin": "https://www.dnse.com.vn",
    "Referer": "https://www.dnse.com.vn/",
}


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def safe_int(value: object, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def format_market_cap(value_vnd: float) -> str:
    """Format VND market cap for UI (compact Vietnamese units)."""
    if value_vnd <= 0:
        return "—"
    nghin_ty = value_vnd / 1e12
    if nghin_ty >= 1:
        return f"{nghin_ty:.1f} NT"
    ty = value_vnd / 1e9
    if ty >= 1:
        return f"{ty:.1f} T"
    trieu = value_vnd / 1e6
    if trieu >= 1:
        return f"{trieu:.0f} Tr"
    return f"{value_vnd:,.0f} ₫"
