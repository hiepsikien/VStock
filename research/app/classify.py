from __future__ import annotations

from dataclasses import dataclass

IGNORE_CATEGORIES = frozenset(
    {"stock_news", "macro_news", "commodity_news", "real_estate_news", "news"}
)


@dataclass(frozen=True)
class NewsLabel:
    kind: str
    effect: str


_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("suspension", "block", ("tạm ngừng giao dịch", "đình chỉ giao dịch", "hủy niêm yết", "huỷ niêm yết")),
    (
        "audit_exception",
        "block",
        ("ý kiến kiểm toán ngoại trừ", "ý kiến ngoại trừ", "từ chối đưa ý kiến", "kiểm toán từ chối"),
    ),
    (
        "insider_sell",
        "wait",
        ("đăng ký bán", "đăng ký giao dịch bán", "đăng ký thực hiện bán"),
    ),
    (
        "insider_buy",
        "priority",
        ("đăng ký mua", "đăng ký giao dịch mua", "đăng ký thực hiện mua"),
    ),
    (
        "bonus_shares",
        "context",
        (
            "thưởng cổ phiếu",
            "cổ tức bằng cổ phiếu",
            "cổ tức cổ phiếu",
            "trả cổ tức bằng cổ phiếu",
            "chia cổ phiếu",
            "tách cổ phiếu",
            "chia tách",
            "tăng vốn từ lợi nhuận",
            "nguồn vốn chủ sở hữu",
        ),
    ),
    (
        "dilution",
        "context",
        (
            "chào bán riêng lẻ",
            "phát hành cho cổ đông hiện hữu",
            "chào bán ra công chúng",
            "phát hành thêm",
            "có thu tiền",
        ),
    ),
    ("earnings_release", "clock", ("báo cáo tài chính", "bctc")),
    (
        "dividend",
        "context",
        ("cổ tức", "không hưởng quyền", "ngày giao dịch không hưởng quyền"),
    ),
)


def classify_article(title: str, summary: str, category: str) -> NewsLabel:
    """Map a headline onto one event kind. Commentary categories never become events."""
    if (category or "").strip() in IGNORE_CATEGORIES:
        return NewsLabel("ignore", "none")
    text = f"{title or ''} {summary or ''}".lower()
    for kind, effect, phrases in _RULES:
        if not any(phrase in text for phrase in phrases):
            continue
        if kind == "suspension" and "trái phiếu" in text:
            continue
        return NewsLabel(kind, effect)
    if (category or "").strip() in {"disclosure", "company_news"}:
        return NewsLabel("other", "none")
    return NewsLabel("ignore", "none")
