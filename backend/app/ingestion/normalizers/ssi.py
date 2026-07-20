from __future__ import annotations

from app.domain.quote import Quote
from app.ingestion.normalizers.vps import vnd_to_display
from app.services.http_utils import safe_float, safe_int


def normalize_ssi_stock(data: dict, symbol: str) -> Quote | None:
    sym = symbol.upper()
    matched = safe_float(data.get("matchedPrice"))
    if matched <= 0:
        return None

    ref_raw = safe_float(data.get("refPrice") or data.get("referencePrice"))
    price = vnd_to_display(matched)
    ref = vnd_to_display(ref_raw) if ref_raw > 0 else price

    change_raw = safe_float(data.get("priceChange"))
    change_pct = safe_float(data.get("priceChangePercent"))
    if change_raw != 0:
        change = vnd_to_display(abs(change_raw)) if change_raw > 1000 else round(change_raw, 2)
        if change_raw < 0:
            change = -change
    elif ref > 0:
        change = round(price - ref, 2)
    else:
        change = 0.0

    if change_pct == 0 and ref > 0:
        change_pct = round((change / ref) * 100, 2)

    return Quote(
        symbol=sym,
        price=price,
        change=change,
        changePercent=round(change_pct, 2),
        open=round(vnd_to_display(safe_float(data.get("openPrice"))), 2),
        high=round(vnd_to_display(safe_float(data.get("highest"))), 2),
        low=round(vnd_to_display(safe_float(data.get("lowest"))), 2),
        volume=safe_int(data.get("nmTotalTradedQty") or data.get("matchedVolume")),
        ref=ref,
        source="ssi_iboard",
        stale=False,
    )
