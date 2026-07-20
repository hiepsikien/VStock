from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.news import NewsArticle


class NewsProvider(ABC):
    name: str
    priority: int = 99

    @abstractmethod
    async def fetch_market_news(self, limit: int) -> list[NewsArticle]:
        """Return latest market news articles."""

    @abstractmethod
    async def fetch_symbol_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        """Return news articles related to a stock symbol."""
