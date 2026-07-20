from __future__ import annotations

from app.domain.quote import Quote


def normalize_entrade_closes(symbol: str, closes: list[float]) -> Quote | None:
    prices = [p for p in closes if p > 0]
    if not prices:
        return None

    price = prices[-1]
    prev = prices[-2] if len(prices) >= 2 else price
    change = round(price - prev, 2)
    change_pct = round((change / prev) * 100, 2) if prev > 0 else 0.0

    return Quote(
        symbol=symbol.upper(),
        price=round(price, 2),
        change=change,
        changePercent=change_pct,
        open=round(prices[0], 2),
        high=round(max(prices), 2),
        low=round(min(prices), 2),
        volume=0,
        ref=round(prev, 2),
        source="entrade",
        stale=True,
    )
