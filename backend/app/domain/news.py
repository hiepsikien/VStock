from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NewsArticle:
    id: str
    title: str
    summary: str
    source: str
    published_at: str
    url: str
    image_url: str | None = None
    symbols: tuple[str, ...] = field(default_factory=tuple)
    category: str = "news"

    def to_api_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "publishedAt": self.published_at,
            "url": self.url,
            "imageUrl": self.image_url,
            "symbols": list(self.symbols),
            "category": self.category,
        }
