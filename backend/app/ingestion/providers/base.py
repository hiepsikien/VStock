from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.quote import Quote


class QuoteProvider(ABC):
    name: str
    priority: int = 99
    batch: bool = False
    stale: bool = False

    @abstractmethod
    async def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Return quotes keyed by symbol. Omit symbols that could not be fetched."""
