from __future__ import annotations

from app.domain.quote import Quote
from app.ingestion.normalizers.vps import vnd_to_display
from app.services.http_utils import safe_float, safe_int


def normalize_kbs_row(row: dict, symbol: str) -> Quote | None:
    sym = symbol.upper()
    close = safe_float(
        row.get("close")
        or row.get("closePrice")
        or row.get("Close")
        or row.get("matchedPrice")
        or row.get("lastPrice"),
    )
    if close <= 0:
        return None

    price = vnd_to_display(close)
    ref_raw = safe_float(row.get("refPrice") or row.get("referencePrice") or row.get("basicPrice"))
    ref = vnd_to_display(ref_raw) if ref_raw > 0 else price
    change = round(price - ref, 2) if ref > 0 else 0.0
    change_pct = round((change / ref) * 100, 2) if ref > 0 else 0.0

    return Quote(
        symbol=sym,
        price=price,
        change=change,
        changePercent=change_pct,
        open=round(vnd_to_display(safe_float(row.get("open") or row.get("openPrice"))), 2),
        high=round(vnd_to_display(safe_float(row.get("high") or row.get("highPrice"))), 2),
        low=round(vnd_to_display(safe_float(row.get("low") or row.get("lowPrice"))), 2),
        volume=safe_int(row.get("volume") or row.get("totalVolume")),
        ref=ref,
        source="kbs",
        stale=True,
    )
