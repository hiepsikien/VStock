"""Số để theo dõi trên dashboard: lịch chạy, độ rộng từng phiên, và phép đo bộ lọc độ rộng.

Phần bộ lọc chỉ có số đếm. Trước lần đo một lần, luật chốt trước không cho xem lợi nhuận, tỷ lệ
thắng hay số nào suy ra kết quả (docs/breadth-signal-filter.md), nên trang web không có chúng.
"""

from __future__ import annotations

from datetime import date, datetime

from app.breadth_filter import Counts
from app.config import (
    BREADTH_FILTER_MAX_MONTHS,
    BREADTH_FILTER_MIN_MONTHS,
    BREADTH_FILTER_MIN_SIGNALS,
    BREADTH_FILTER_START,
)
from app.scheduled import VN, expected_session

SOURCES = {"web": "Nút Chạy phiên", "lịch": "Lịch chạy", "": "—"}


def _vn_time(stamp: str | None) -> str:
    if not stamp:
        return "—"
    return datetime.fromisoformat(stamp).astimezone(VN).strftime("%d/%m %H:%M")


def run_rows(runs: list[dict]) -> list[dict]:
    rows = []
    for run in runs:
        seconds = None
        if run.get("finished_at"):
            seconds = round(
                (datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["started_at"])).total_seconds()
            )
        rows.append(
            {
                "started": _vn_time(run["started_at"]),
                "seconds": seconds,
                "status": run["status"],
                "source": SOURCES.get(run.get("source") or "", run.get("source") or "—"),
                "message": run.get("message") or "",
            }
        )
    return rows


def schedule_view(index_days: list[str], states: list[tuple[str, float]], now: datetime) -> dict:
    """Phiên lẽ ra đã đóng cửa có trạng thái độ rộng chưa, và bao nhiêu phiên đo đã thiếu nó."""
    expected = expected_session(now)
    stored = {day for day, _value in states}
    last_index = index_days[-1] if index_days else ""
    measured = [day for day in index_days if day >= BREADTH_FILTER_START]
    missing = [day for day in measured if day not in stored]
    if expected in stored:
        warning = ""
    elif last_index < expected:
        warning = (
            f"Kho chưa có nến VN-Index phiên {expected} (mới nhất: {last_index or 'chưa có'}). "
            "Nguồn có thể chưa cập nhật, hoặc là ngày nghỉ."
        )
    else:
        warning = f"Phiên {expected} chưa có trạng thái độ rộng."
    return {
        "expected": expected,
        "warning": warning,
        "measured": len(measured),
        "missing": missing,
        "start": BREADTH_FILTER_START,
    }


def breadth_rows(
    index_days: list[str], shares: list[tuple[str, float]], states: list[tuple[str, float]], limit: int = 20
) -> list[dict]:
    """Các phiên VN-Index gần nhất, kể cả phiên không lưu độ rộng, để phiên bỏ lỡ hiện ra."""
    share_of = dict(shares)
    state_of = dict(states)
    rows = []
    for day in reversed(index_days[-limit:]):
        rows.append(
            {
                "day": day,
                "share": share_of.get(day),
                "open": None if day not in state_of else state_of[day] >= 0.5,
                "measured": day >= BREADTH_FILTER_START,
            }
        )
    return rows


def _add_months(start: str, months: int) -> str:
    day = date.fromisoformat(start)
    total = day.month - 1 + months
    return day.replace(year=day.year + total // 12, month=total % 12 + 1).isoformat()


def filter_counts(start: str = BREADTH_FILTER_START) -> Counts:
    """Chỉ số đếm của mẫu, để worker process không phải gửi lại cả kho nến."""
    from app.breadth_filter import _sample

    return _sample(start)[1]


def filter_view(counts: Counts) -> dict:
    if counts.ready:
        status = "Đã đủ điều kiện đo: chạy lệnh đo một lần."
    elif counts.expired:
        status = "Đã quá hạn chót: lệnh đo sẽ kết luận theo luật, kể cả \"không đủ mẫu\"."
    else:
        status = "Chưa đủ điều kiện đo."
    return {
        "counts": counts,
        "status": status,
        "started": counts.last_day >= counts.start,
        "min_signals": BREADTH_FILTER_MIN_SIGNALS,
        "min_months": BREADTH_FILTER_MIN_MONTHS,
        "max_months": BREADTH_FILTER_MAX_MONTHS,
        "deadline": _add_months(counts.start, BREADTH_FILTER_MAX_MONTHS),
    }
