from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QuoteSource = Literal["vps", "ssi_iboard", "entrade", "kbs"]


@dataclass(frozen=True)
class Quote:
    """Canonical quote model. Prices in nghìn đồng (display units)."""

    symbol: str
    price: float
    change: float
    changePercent: float
    open: float
    high: float
    low: float
    volume: int
    ref: float = 0.0
    source: QuoteSource = "vps"
    stale: bool = False

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "change": self.change,
            "changePercent": self.changePercent,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "ref": self.ref,
        }
