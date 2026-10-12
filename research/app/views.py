"""Số dựng sẵn cho các trang: đèn cổng thị trường, phễu, thay đổi giữa hai phiên, cảnh báo sổ giấy.

Không đọc kho, không gọi mạng: hàm nhận đúng những gì `web.py` đã đọc, nên test được mà không
cần server. Không hàm nào ở đây đổi trạng thái của mã; chúng chỉ sắp lại cho dễ đọc.
"""

from __future__ import annotations

import html
import re

from app.config import (
    BREADTH_CLOSE,
    BREADTH_GATE_ENFORCED,
    BREADTH_MA_WINDOW,
    BREADTH_OPEN,
    INDUSTRY_GATE_ENFORCED,
    MAX_HOLD_SESSIONS,
    STATUS_RANK,
    TIME_STOP_SESSIONS,
)
from app.industries import CREDIT_INDUSTRIES, LEAD_SERIES, REGIME_INDUSTRIES
from app.industry_note import LABELS as INDUSTRY_LABELS
from app.industry_screen import IndustryDay
from app.money import Money
from app.pattern import Regime

NEWS_LABELS = {"Mở": "Sạch", "Chờ": "Chờ công bố", "Loại": "Có tin chặn", "Chưa chấm": "Chưa chấm"}
FLOW_LABELS = {
    "accumulation": "Gom hàng",
    "support": "Ủng hộ",
    "neutral": "Trung tính",
    "weak": "Bán ròng",
    "block": "Bán vào đà tăng",
    "missing": "Chưa có",
}
STATE_WORDS = {"open": "Mở", "closed": "Đóng", "watch": "Theo dõi", "unknown": "Chưa chấm"}
# Cảnh báo sổ giấy: còn chừng này tới dừng lỗ, hoặc chừng này phiên tới mốc đóng theo lịch.
STOP_NEAR = 0.03
CLOCK_NEAR = 5


def industry_name(code: str | None) -> str:
    if not code:
        return ""
    return INDUSTRY_LABELS.get(code, code)


def news_label(state: str) -> str:
    return NEWS_LABELS.get(state, state or "—")


def flow_label(level: str, state: str = "") -> str:
    return FLOW_LABELS.get(level, state or "—")


def _light(
    key: str, name: str, state: str, detail: str, *, enforced: bool, href: str, word: str = ""
) -> dict:
    return {
        "key": key,
        "name": name,
        "state": state,
        "word": word or STATE_WORDS[state],
        "detail": detail,
        "enforced": enforced,
        "href": href,
    }


def _macro_state(reason: str, block: bool) -> str:
    if block or reason.startswith("Vĩ mô căng"):
        return "closed"
    if reason.startswith("Vĩ mô cần theo dõi"):
        return "watch"
    if reason.startswith("Vĩ mô trung tính"):
        return "open"
    return "unknown"


def _after_colon(text: str) -> str:
    return text.split(":", 1)[1].strip() if ":" in text else text


def market_lights(
    regime: Regime,
    money: Money,
    verdicts: list[dict],
    breadth_share: float | None,
    breadth_open: bool | None,
) -> list[dict]:
    """Một đèn cho mỗi cổng toàn thị trường, theo đúng thứ tự `compose` xét chúng."""
    if regime.open is None or regime.close is None or not regime.ma200:
        index_detail = regime.reason
    else:
        gap = regime.close / regime.ma200 - 1
        index_detail = f"{regime.close:,.2f} so với MA200 {regime.ma200:,.2f} ({gap:+.1%})"
    lights = [
        _light(
            "index",
            "VN-Index / MA200",
            "unknown" if regime.open is None else ("open" if regime.open else "closed"),
            index_detail,
            enforced=True,
            href="/market#vn-index",
        ),
        _light(
            "money",
            "Tiền tệ",
            "unknown" if money.open is None else ("open" if money.open else "closed"),
            "Tiền chưa thắt" if money.open else _after_colon(money.reason),
            enforced=True,
            href="/market#tien-te",
        ),
    ]
    first = verdicts[0] if verdicts else {}
    macro_reason = first.get("macro_reason") or "Chưa có phiên nào"
    lights.append(
        _light(
            "macro",
            "Vĩ mô",
            _macro_state(macro_reason, bool(first.get("macro_block"))),
            _after_colon(macro_reason),
            enforced=True,
            href="/market#vi-mo",
        )
    )
    if breadth_share is None:
        breadth_detail = "Chưa có phiên nào lưu độ rộng"
    else:
        breadth_detail = (
            f"{breadth_share:.0%} mã trên MA{BREADTH_MA_WINDOW} "
            f"(mở từ {BREADTH_OPEN:.0%}, đóng từ {BREADTH_CLOSE:.0%})"
        )
    lights.append(
        _light(
            "breadth",
            "Độ rộng",
            "unknown" if breadth_open is None else ("open" if breadth_open else "closed"),
            breadth_detail,
            enforced=BREADTH_GATE_ENFORCED,
            href="/market#do-rong",
        )
    )
    industries: dict[str, bool | None] = {}
    for item in verdicts:
        if item.get("industry_name"):
            industries[item["industry_name"]] = item.get("industry_open")
    opened = sorted(industry_name(code) for code, state in industries.items() if state)
    if industries:
        industry_detail = "Mở: " + ", ".join(opened) if opened else "Không nhóm nào mở"
        industry_state = "closed" if not opened else ("open" if len(opened) == len(industries) else "watch")
        industry_word = f"{len(opened)}/{len(industries)} nhóm mở"
    else:
        industry_detail, industry_state, industry_word = "Chưa có phiên nào ghi ngành", "unknown", ""
    lights.append(
        _light(
            "industry",
            "Ngành",
            industry_state,
            industry_detail,
            enforced=INDUSTRY_GATE_ENFORCED,
            href="/market#nganh",
            word=industry_word,
        )
    )
    return lights


def market_headline(lights: list[dict]) -> dict:
    """Một câu cho cả danh sách, chỉ từ các cổng đang được phép khóa."""
    enforced = [light for light in lights if light["enforced"]]
    closed = [light for light in enforced if light["state"] == "closed" and light["key"] != "macro"]
    unknown = [light for light in enforced if light["state"] == "unknown"]
    macro = next((light for light in enforced if light["key"] == "macro"), None)
    if closed:
        names = ", ".join(f"{light['name']} ({light['detail']})" for light in closed)
        return {"state": "closed", "text": f"Danh sách đang khóa: {names}."}
    if unknown:
        names = ", ".join(light["name"] for light in unknown)
        return {"state": "unknown", "text": f"Chưa chấm được cổng thị trường: thiếu số ở {names}."}
    if macro and macro["state"] == "closed":
        return {"state": "watch", "text": f"Thị trường mở nhưng vĩ mô chặn vào lệnh mới: {macro['detail']}."}
    return {"state": "open", "text": "Thị trường mở: danh sách được xét tiếp theo từng mã."}


def stamp_lights(lights: list[dict], days: dict[str, str], session: str) -> bool:
    """Ghi ngày của số sau mỗi đèn; True khi có đèn đọc số khác phiên mà bảng mã đã chấm."""
    for light in lights:
        light["day"] = days.get(light["key"], "")
        light["stale"] = bool(session and light["day"] and light["day"] != session)
    return any(light["stale"] for light in lights)


def hold_reason(verdicts: list[dict]) -> str:
    """Vì sao danh sách bị giữ: "locked" (cổng khóa), "unknown" (cổng thiếu số), "macro" (vĩ mô chặn lệnh mới)."""
    held = [item for item in verdicts if held_by_market(item)]
    if not held:
        return ""
    if any(item["status"] == "Khóa" for item in held):
        return "locked"
    if any(item["status"] == "Chưa chấm" for item in held):
        return "unknown"
    return "macro"


def held_by_market(item: dict) -> bool:
    """Trạng thái thật khác trạng thái nếu thị trường mở: chỉ cổng toàn thị trường làm được vậy."""
    return bool(item.get("open_status")) and item["open_status"] != item["status"]


def lane(item: dict) -> str:
    """Nhóm của một mã trên bảng: trạng thái nếu thị trường mở khi có, không thì trạng thái thật."""
    return item.get("open_status") or item["status"]


def lane_counts(verdicts: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for item in verdicts:
        counts[lane(item)] = counts.get(lane(item), 0) + 1
    return sorted(counts.items(), key=lambda pair: STATUS_RANK.get(pair[0], 9))


def funnel(verdicts: list[dict]) -> list[dict]:
    """Bao nhiêu mã còn lại sau từng lớp của riêng mã, theo thứ tự `compose` xét chúng."""
    steps = [
        ("Danh sách", lambda item: True),
        (
            "Qua cơ bản và định giá",
            lambda item: item["fa_label"] == "Đạt" and item.get("valuation_label") != "Không đạt",
        ),
        ("Tin sạch", lambda item: item["news_state"] == "Mở"),
        ("Nền giá sẵn", lambda item: bool(item["pattern_ready"])),
        ("Dòng tiền không chặn", lambda item: item.get("flow_state") != "Chờ"),
    ]
    remaining = list(verdicts)
    total = len(verdicts) or 1
    out = []
    for name, keep in steps:
        remaining = [item for item in remaining if keep(item)]
        out.append({"name": name, "count": len(remaining), "share": len(remaining) / total})
    entered = sum(1 for item in verdicts if item["status"] == "Được vào")
    out.append({"name": "Được vào thật", "count": entered, "share": entered / total, "final": True})
    return out


def status_changes(
    verdicts: list[dict], previous: dict[str, tuple[str, str]]
) -> list[dict]:
    """Mã đổi trạng thái so với phiên đã lưu trước, kể cả trạng thái nếu thị trường mở."""
    changes = []
    for item in verdicts:
        before = previous.get(item["symbol"])
        if before is None:
            changes.append(
                {"symbol": item["symbol"], "before": "", "after": item["status"], "kind": "new"}
            )
            continue
        status_before, open_before = before
        if status_before != item["status"]:
            changes.append(
                {"symbol": item["symbol"], "before": status_before, "after": item["status"], "kind": "status"}
            )
        elif open_before and item.get("open_status") and open_before != item["open_status"]:
            changes.append(
                {"symbol": item["symbol"], "before": open_before, "after": item["open_status"], "kind": "open"}
            )
    rank = lambda change: (STATUS_RANK.get(change["after"], 9), change["symbol"])  # noqa: E731
    return sorted(changes, key=rank)


def group_changes(changes: list[dict]) -> list[dict]:
    """Một dòng cho mỗi kiểu chuyển, để cả danh sách cùng đổi không thành trăm dòng."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for change in changes:
        groups.setdefault((change["kind"], change["before"], change["after"]), []).append(change["symbol"])
    return [
        {"kind": kind, "before": before, "after": after, "symbols": symbols}
        for (kind, before, after), symbols in groups.items()
    ]


def paper_alerts(rows: list[dict]) -> list[dict]:
    """Vị thế đang mở cần nhìn: sát dừng lỗ, hoặc sắp tới mốc đóng theo số phiên."""
    alerts = []
    for row in rows:
        if row.get("exit_date"):
            continue
        last = row.get("last_price") or row["entry_price"]
        stop = row["stop_price"]
        room = last / stop - 1 if stop else None
        if room is not None and room <= STOP_NEAR:
            alerts.append({"symbol": row["symbol"], "text": f"cách dừng lỗ {room:.1%} ({stop:,.2f})", "level": "bad"})
        sessions = row.get("sessions") or 0
        if not row.get("tp1_done") and sessions >= TIME_STOP_SESSIONS - CLOCK_NEAR:
            alerts.append(
                {
                    "symbol": row["symbol"],
                    "text": f"{sessions}/{TIME_STOP_SESSIONS} phiên chưa chạm mốc chốt 1/3, sắp đóng vì tiền chết",
                    "level": "wait",
                }
            )
        elif sessions >= MAX_HOLD_SESSIONS - CLOCK_NEAR:
            alerts.append(
                {"symbol": row["symbol"], "text": f"{sessions}/{MAX_HOLD_SESSIONS} phiên, sắp đủ trần nắm", "level": "wait"}
            )
    return alerts


_MACRO_DOWNGRADES = ("Vĩ mô chặn vào", "Vĩ mô chưa có số")


def _market_decides(item: dict) -> bool:
    """Cổng toàn thị trường đổi trạng thái của mã: Khóa, Chưa chấm vì thiếu số, hay vĩ mô hạ Được vào."""
    status, summary = item["status"], item["summary"]
    if item.get("open_status"):
        if status != item["open_status"]:
            return True
        # Cả hai đều Chưa chấm: cổng thị trường thiếu số nếu lý do thật khác lý do của riêng mã.
        return status == "Chưa chấm" and summary != (item.get("open_summary") or "")
    # Phiên lưu trước khi có open_status: đọc từ trạng thái, lý do và các cờ đã lưu.
    if status == "Khóa":
        return True
    if status == "Chưa chấm":
        return (item.get("regime_open") is None and summary == item.get("regime_reason")) or (
            item.get("market_open") is None and bool(item.get("market_reason")) and summary == item.get("market_reason")
        )
    return summary.startswith(_MACRO_DOWNGRADES)


def _market_step(item: dict, decides: bool) -> tuple[str, str, str]:
    """(trạng thái, lý do, chữ riêng) của ô Thị trường."""
    if decides:
        state = {"Khóa": "closed", "Chưa chấm": "unknown"}.get(item["status"], "closed")
        # Vĩ mô tải lỗi cũng hạ Được vào xuống Theo dõi, nhưng đó là thiếu số chứ không phải cổng đóng.
        if item["summary"].startswith(_MACRO_DOWNGRADES[1]):
            state = "unknown"
        return state, item["summary"], ""
    if item.get("regime_open") is False or item.get("market_open") is False:
        return "closed", item.get("regime_reason") or item.get("market_reason") or "", ""
    if item.get("regime_open") is None or item.get("market_open") is None:
        return "unknown", item.get("market_reason") or item.get("regime_reason") or "", ""
    # Vĩ mô chỉ hạ một mã sắp vào; với mã đã dừng ở lớp của chính nó thì vĩ mô không đổi gì.
    if item.get("macro_block"):
        return "watch", item.get("macro_reason") or "", "Vĩ mô chặn lệnh mới"
    return "open", item.get("regime_reason") or "", ""


def _stock_decider(item: dict) -> str | None:
    """Ô quyết định trong các lớp của riêng mã, cùng thứ tự với `evaluate._stock_status`."""
    status = item.get("open_status") or item["status"]
    summary = item.get("open_summary") or item["summary"]
    news, fa = item["news_state"], item["fa_label"]
    if status == "Chưa chấm" and summary == (item.get("pattern_reason") or ""):
        return "Nền giá"
    if news == "Loại":
        return "Tin"
    if fa == "Không đạt":
        return "Cơ bản"
    if item.get("valuation_label") == "Không đạt":
        return "Định giá"
    if news == "Chưa chấm":
        return "Tin"
    if fa not in ("Đạt", "Không đạt"):
        return "Cơ bản"
    if news == "Chờ":
        return "Tin"
    if not item["pattern_ready"]:
        return "Nền giá"
    if item.get("flow_state") == "Chờ":
        return "Dòng tiền"
    if INDUSTRY_GATE_ENFORCED and item.get("industry_open") is False:
        return "Ngành"
    return None


INDUSTRY_STRIP_SESSIONS = 120
INDUSTRY_SHARE_SESSIONS = 250
INDUSTRY_CHANGES = 4


def _pct_or(value: float | None, missing: str) -> str:
    return missing if value is None else f"{value:+.1%}"


def _industry_conditions(industry: str, day: IndustryDay, window: int) -> list[dict]:
    """Từng điều kiện của luật ngành, đúng như `industry_screen.wave_open` xét, kèm số đã đọc."""
    excess = day.excess
    conditions = [
        {
            "name": f"Nhóm mạnh hơn VN-Index {window} phiên",
            "ok": excess is not None and excess > 0,
            "value": (
                f"chưa đủ {window} phiên"
                if excess is None
                else f"nhóm {day.own:+.1%}, VN-Index {day.index:+.1%}, chênh {excess:+.1%}"
            ),
        }
    ]
    if industry in LEAD_SERIES:
        conditions.append(
            {
                "name": f"Giá dầu tăng {window} phiên",
                "ok": day.lead is not None and day.lead > 0,
                "value": _pct_or(day.lead, "chưa có số dầu"),
            }
        )
    if industry in CREDIT_INDUSTRIES:
        conditions.append(
            {
                "name": "Tín dụng ngân hàng tăng",
                "ok": day.credit is not None and day.credit > 0,
                "value": (
                    "chưa có báo cáo quý"
                    if day.credit is None
                    else f"trung vị tăng trưởng cho vay cùng kỳ {day.credit:+.1%}"
                ),
            }
        )
    if industry in REGIME_INDUSTRIES:
        conditions.append(
            {
                "name": "VN-Index trên MA200",
                "ok": day.regime is True,
                "value": {True: "trên", False: "dưới"}.get(day.regime, "chưa đủ số"),
            }
        )
    return conditions


def _industry_kind(industry: str) -> str:
    if industry in LEAD_SERIES:
        return "Theo giá dầu" if industry == "energy" else "Theo giá dầu (đại diện hàng hóa)"
    if industry in CREDIT_INDUSTRIES:
        return "Theo tín dụng ngân hàng"
    return "Theo VN-Index trên MA200"


def _strip(days: list[str], records: list[IndustryDay], sessions: int) -> list[dict]:
    """Các đoạn mở/đóng liền nhau của `sessions` phiên gần nhất, độ rộng theo phần trăm."""
    tail = list(zip(days, records))[-sessions:]
    segments: list[dict] = []
    for day, record in tail:
        if segments and segments[-1]["open"] == record.open:
            segments[-1]["end"] = day
            segments[-1]["sessions"] += 1
        else:
            segments.append({"open": record.open, "start": day, "end": day, "sessions": 1})
    for segment in segments:
        segment["width"] = round(100 * segment["sessions"] / len(tail), 3)
    return segments


def industry_panel(
    days: list[str],
    by_industry: dict[str, list[IndustryDay]],
    members_by_industry: dict[str, list[str]],
    window: int,
) -> list[dict]:
    """Mỗi nhóm ngành một dòng: đang mở hay đóng, từ phiên nào, vì điều kiện nào, lịch sử gần đây."""
    rows = []
    for industry, records in by_industry.items():
        if not records:
            continue
        last = records[-1]
        start = len(records) - 1
        while start > 0 and records[start - 1].open == last.open:
            start -= 1
        changes = [
            {"day": days[position], "open": records[position].open}
            for position in range(1, len(records))
            if records[position].open != records[position - 1].open
        ]
        recent = records[-INDUSTRY_SHARE_SESSIONS:]
        rows.append(
            {
                "code": industry,
                "name": industry_name(industry),
                "kind": _industry_kind(industry),
                "members": members_by_industry.get(industry, []),
                "open": last.open,
                "since": days[start],
                # Trạng thái đã như vậy từ phiên đầu tiên có nến thì không biết nó bắt đầu từ bao giờ.
                "since_known": start > 0,
                "sessions": len(records) - start,
                "conditions": _industry_conditions(industry, last, window),
                "excess": last.excess,
                "changes": list(reversed(changes[-INDUSTRY_CHANGES:])),
                "strip": _strip(days, records, INDUSTRY_STRIP_SESSIONS),
                "open_share": sum(1 for record in recent if record.open) / len(recent),
            }
        )
    rows.sort(key=lambda row: (not row["open"], -(row["excess"] if row["excess"] is not None else -9)))
    return rows


def gate_chain(item: dict) -> list[dict]:
    """Chuỗi cổng của một mã, theo thứ tự xét, kèm cổng đã quyết định trạng thái."""
    market_decides = item["status"] != "Được vào" and _market_decides(item)
    market = _market_step(item, market_decides)
    fa = {"Đạt": "open", "Không đạt": "closed"}.get(item["fa_label"], "unknown")
    valuation = {"Đạt": "open", "Không đạt": "closed"}.get(item.get("valuation_label") or "", "unknown")
    news = {"Mở": "open", "Chờ": "watch", "Loại": "closed"}.get(item["news_state"], "unknown")
    flow = {"Mở": "open", "Chờ": "closed"}.get(item.get("flow_state") or "", "unknown")
    industry_open = item.get("industry_open")
    steps = [
        {"name": "Thị trường", "state": market[0], "detail": market[1], "word": market[2]},
        {"name": "Cơ bản", "state": fa, "detail": f"{item['fa_label']}. {item.get('fa_reason') or ''}"},
        {
            "name": "Định giá",
            "state": valuation,
            "detail": f"{item.get('valuation_label') or '—'}. {item.get('valuation_reason') or ''}",
        },
        {"name": "Tin", "state": news, "detail": f"{news_label(item['news_state'])}. {item.get('news_reason') or ''}"},
        {
            "name": "Nền giá",
            "state": "open" if item["pattern_ready"] else "watch",
            "detail": item.get("pattern_reason") or "",
        },
        {
            "name": "Dòng tiền",
            "state": flow,
            "detail": f"{flow_label(item.get('flow_level') or '', item.get('flow_state') or '')}. {item.get('flow_reason') or ''}",
        },
        {
            "name": "Ngành",
            "state": "unknown" if industry_open is None else ("open" if industry_open else "closed"),
            "detail": industry_name(item.get("industry_name")) or "Không có nhóm đã đo",
            "observe": not INDUSTRY_GATE_ENFORCED,
        },
    ]
    for step in steps:
        step["word"] = step.get("word") or STATE_WORDS[step["state"]]
    # Thiếu P/E hay thiếu số khối ngoại không chặn mã, nên ô đó nói "chưa có số" chứ không "chưa chấm".
    for step in steps[2], steps[5]:
        if step["state"] == "unknown":
            step["word"] = "Chưa có số"
    if item["status"] != "Được vào":
        decider = "Thị trường" if market_decides else _stock_decider(item)
        for step in steps:
            if step["name"] == decider:
                step["decides"] = True
    return steps


_CODE = re.compile(r"`([^`]+)`")
_INLINE = [
    (re.compile(r"\*\*(?!\s)([^*]+?)(?<!\s)\*\*"), r"<strong>\1</strong>"),
    # Dấu * đứng giữa hai khoảng trắng là phép nhân, không phải chữ nghiêng.
    (re.compile(r"(?<![*\w])\*(?![\s*])([^*\n]+?)(?<!\s)\*(?![*\w])"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), r'<a href="\2" rel="noreferrer">\1</a>'),
]


def _inline(text: str) -> str:
    # Khối mã giữ nguyên chữ; dấu nháy cũng được thoát để một URL không ra khỏi thuộc tính href.
    out = []
    for index, part in enumerate(_CODE.split(text)):
        escaped = html.escape(part, quote=True)
        if index % 2:
            out.append(f"<code>{escaped}</code>")
            continue
        for pattern, replacement in _INLINE:
            escaped = pattern.sub(replacement, escaped)
        out.append(escaped)
    return "".join(out)


def _table(rows: list[str]) -> str:
    cells = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows]
    head, body = cells[0], [row for row in cells[2:]]
    out = ["<table><thead><tr>", *[f"<th>{_inline(cell)}</th>" for cell in head], "</tr></thead><tbody>"]
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def render_markdown(text: str) -> str:
    """Đủ markdown cho các báo cáo trong `reports/`: tiêu đề, đoạn, danh sách, bảng, khối mã."""
    lines = text.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    index = 0

    def flush() -> None:
        if paragraph:
            out.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            block = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(block))}</code></pre>")
            index += 1
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1)) + 1
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[index + 1].strip()):
            flush()
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index])
                index += 1
            out.append(_table(rows))
            continue
        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            flush()
            ordered = bullet.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while index < len(lines):
                match = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[index])
                if match:
                    items.append(match.group(3))
                elif lines[index].strip() and lines[index].startswith(("  ", "\t")) and items:
                    items[-1] += " " + lines[index].strip()
                else:
                    break
                index += 1
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + f"</{tag}>")
            continue
        if not stripped:
            flush()
        else:
            paragraph.append(stripped)
        index += 1
    flush()
    return "\n".join(out)
