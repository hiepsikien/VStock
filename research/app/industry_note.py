"""A monthly industry note. It is stored and compared later. It does not open a trade.

The prompt may contain only figures dated on or before the note day. A missing API key
leaves the note unwritten; the numeric industry gate still runs.
"""

from __future__ import annotations

import os


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


def api_key() -> str | None:
    for name in ("GEMINI_API_KEY", "RESEARCH_LLM_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None
