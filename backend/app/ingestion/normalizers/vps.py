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


def _price_field(item: dict, *keys: str) -> float:
    for key in keys:
        raw = safe_float(item.get(key))
        if raw <= 0:
            continue
        return vnd_to_display(raw) if raw >= 1000 else round(raw, 2)
    return 0.0


def normalize_vps_item(item: dict) -> Quote | None:
    symbol = str(item.get("sym") or "").upper()
    if not symbol:
        return None

    ref = _price_field(item, "r")
    last = _price_field(item, "lastPrice")
    if last <= 0:
        # Outside session VPS often zeros lastPrice but keeps closePrice in VND.
        last = _price_field(item, "closePrice")
    if last <= 0 and ref > 0:
        last = ref
    if last <= 0:
        return None

    open_price = _price_field(item, "openPrice")
    high = _price_field(item, "highPrice")
    low = _price_field(item, "lowPrice")
    volume = safe_int(item.get("lot") or item.get("lastVolume") or item.get("ptVol"))

    # Incomplete board snapshot (common pre/post market) — let failover providers fill OHLC/KL.
    if open_price <= 0 and high <= 0 and low <= 0 and volume <= 0:
        return None

    if open_price <= 0:
        open_price = last
    if high <= 0:
        high = max(last, open_price)
    if low <= 0:
        low = min(last, open_price) if open_price > 0 else last

    change = last - ref if ref > 0 else 0.0
    change_pc = abs(safe_float(item.get("changePc")))
    if change < 0:
        change_pc = -change_pc
    elif change == 0:
        change_pc = 0.0
    elif change_pc == 0 and ref > 0:
        change_pc = round((change / ref) * 100, 2)

    return Quote(
        symbol=symbol,
        price=round(last, 2),
        change=round(change, 2),
        changePercent=round(change_pc, 2),
        open=round(open_price, 2),
        high=round(high, 2),
        low=round(low, 2),
        volume=volume,
        ref=round(ref, 2) if ref > 0 else round(last, 2),
        source="vps",
        stale=False,
    )
