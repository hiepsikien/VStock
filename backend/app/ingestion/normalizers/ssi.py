from __future__ import annotations

from app.domain.quote import Quote
from app.ingestion.normalizers.vps import vnd_to_display
from app.services.http_utils import safe_float, safe_int


def normalize_ssi_stock(data: dict, symbol: str) -> Quote | None:
    sym = symbol.upper()
    matched = safe_float(data.get("matchedPrice"))
    if matched <= 0:
        return None

    ref_raw = safe_float(data.get("refPrice") or data.get("referencePrice") or data.get("priorClosePrice"))
    price = vnd_to_display(matched)
    ref = vnd_to_display(ref_raw) if ref_raw > 0 else price

    # Always derive change in display units (nghìn đồng). SSI priceChange is VND and
    # must not be shown raw — previous heuristic also flipped the sign for negatives.
    change = round(price - ref, 2) if ref > 0 else 0.0

    change_pct = safe_float(data.get("priceChangePercent"))
    if ref > 0:
        computed_pct = round((change / ref) * 100, 2)
        if change_pct == 0:
            change_pct = computed_pct
        elif (change < 0 and change_pct > 0) or (change > 0 and change_pct < 0):
            change_pct = -abs(change_pct)
        elif change == 0:
            change_pct = 0.0

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
