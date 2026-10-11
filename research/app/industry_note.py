"""A monthly industry note. It is stored and compared later. It does not open a trade.

The prompt may contain only figures dated on or before the note day. A missing API key
leaves the note unwritten; the numeric industry gate still runs.
"""

from __future__ import annotations

import calendar
import os
from datetime import date


def monthly_prompt(as_of: str, known: dict[str, str]) -> str:
    lines = [
        f"Ngày {as_of}. Chỉ dùng các số dưới đây, đều đã biết đến hết ngày này.",
        "Chọn ngành ưu tiên trong các ngành đủ mã. Không chọn mã.",
    ]
    for label, value in known.items():
        lines.append(f"- {label}: {value}")
    lines.append("Trả về danh sách ngành, rồi một đoạn lý do.")
    return "\n".join(lines)


def note_beats_gate(note_rate: float, gate_rate: float) -> bool:
    """The note may choose industries only when its later-run rate is higher than the open set."""
    return note_rate > gate_rate


LABELS = {
    "bank": "Ngân hàng",
    "securities": "Chứng khoán",
    "insurer": "Bảo hiểm",
    "real_estate": "Bất động sản",
    "energy": "Năng lượng",
    "materials": "Vật liệu",
    "consumer": "Tiêu dùng",
    "tech": "Công nghệ",
    "transport": "Vận tải",
    "industrial": "Công nghiệp",
    "power": "Điện",
    "agri": "Nông nghiệp",
}


def month_note_days(index_days: list[str], start: str, end: str | None = None) -> list[str]:
    """First session of each month from `start`, inclusive."""
    chosen = []
    seen: set[str] = set()
    for day in index_days:
        if day < start or (end is not None and day > end):
            continue
        key = day[:7]
        if key in seen:
            continue
        seen.add(key)
        chosen.append(day)
    return chosen


def shift_months(day: str, months: int) -> str:
    current = date.fromisoformat(day)
    month_index = current.month - 1 + months
    year = current.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(current.day, last_day)).isoformat()


def parse_picks(text: str) -> list[str]:
    """Industry ids named before the reason paragraph."""
    head = text.split("Lý do")[0]
    found = []
    for industry, label in LABELS.items():
        if label in head:
            found.append(industry)
    return found


def contain_rate(run_industries: list[str], picked: set[str]) -> float:
    if not run_industries:
        return 0.0
    return sum(1 for industry in run_industries if industry in picked) / len(run_industries)


def api_key() -> str | None:
    for name in ("GEMINI_API_KEY", "RESEARCH_LLM_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None
