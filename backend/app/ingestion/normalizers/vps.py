from __future__ import annotations

from app.domain.quote import Quote
from app.services.http_utils import safe_float, safe_int


def vnd_to_display(value: float) -> float:
    """Convert full VND to nghìn đồng display units when needed."""
    if value <= 0:
        return 0.0
    if value >= 1000:
        return round(value / 1000.0, 2)
    return round(value, 2)


def normalize_vps_item(item: dict) -> Quote | None:
    symbol = str(item.get("sym") or "").upper()
    if not symbol:
        return None

    ref = safe_float(item.get("r"))
    last = safe_float(item.get("lastPrice"))
    if last <= 0 and ref > 0:
        last = ref

    change = last - ref if ref > 0 else 0.0
    change_pc = abs(safe_float(item.get("changePc")))
    if change < 0:
        change_pc = -change_pc
    elif change == 0:
        change_pc = 0.0

    return Quote(
        symbol=symbol,
        price=round(last, 2),
        change=round(change, 2),
        changePercent=round(change_pc, 2),
        open=round(safe_float(item.get("openPrice")), 2),
        high=round(safe_float(item.get("highPrice")), 2),
        low=round(safe_float(item.get("lowPrice")), 2),
        volume=safe_int(item.get("lot")),
        ref=round(ref, 2),
        source="vps",
        stale=False,
    )
