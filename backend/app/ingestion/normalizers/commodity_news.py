"""Shared commodity / gold / oil topic helpers for news."""

from __future__ import annotations

# Precise phrases — avoid bare "vàng"/"bạc" (too many false positives).
COMMODITY_TITLE_HINTS: tuple[str, ...] = (
    "giá vàng",
    "vàng sjc",
    "vàng thế giới",
    "vàng trong nước",
    "giá bạc",
    "bạc thế giới",
    "dầu thô",
    "giá dầu",
    "brent",
    "wti",
    "giá xăng",
    "xăng dầu",
    "giá cà phê",
    "giá tiêu",
    "giá cao su",
    "giá thép",
    "spdr gold",
)

GOLD_OIL_HINTS: tuple[str, ...] = (
    "giá vàng",
    "vàng sjc",
    "vàng thế giới",
    "vàng trong nước",
    "giá bạc",
    "bạc thế giới",
    "dầu thô",
    "giá dầu",
    "brent",
    "wti",
    "giá xăng",
    "xăng dầu",
    "spdr gold",
)

# VNDirect often files gold/oil under these groups instead of commodity_news.
COMMODITY_ENRICH_GROUPS: tuple[str, ...] = (
    "stock_news",
    "macro_news",
    "banking_finance_news",
)


def looks_like_commodity(title: str, summary: str = "") -> bool:
    title_l = title.casefold()
    if any(hint in title_l for hint in COMMODITY_TITLE_HINTS):
        return True
    # Abstracts often mention oil/gold in passing — only trust strong gold/oil hints there.
    summary_l = (summary or "").casefold()
    return any(hint in summary_l for hint in GOLD_OIL_HINTS)


def looks_like_gold_or_oil(title: str, summary: str = "") -> bool:
    del summary  # title-only; avoids false positives from unrelated abstracts
    text = title.casefold()
    return any(hint in text for hint in GOLD_OIL_HINTS)
