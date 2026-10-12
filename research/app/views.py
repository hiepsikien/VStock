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
from app.industry_note import LABELS as INDUSTRY_LABELS
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
            href="/lab#cong-nganh",
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


def gate_chain(item: dict) -> list[dict]:
    """Chuỗi cổng của một mã, theo thứ tự xét, kèm cổng đã quyết định trạng thái."""
    # Phiên lưu trước khi có open_status vẫn đọc được cổng thị trường từ các cờ đã lưu.
    if held_by_market(item) or item.get("regime_open") is False or item.get("market_open") is False:
        market = ("closed", item["summary"] if item["status"] == "Khóa" else item.get("regime_reason") or "")
    elif item.get("macro_block") and item["status"] != "Được vào":
        market = ("closed", item.get("macro_reason") or "")
    elif item.get("regime_open") is None or item.get("market_open") is None:
        market = ("unknown", item["summary"] if item["status"] == "Chưa chấm" else item.get("market_reason") or "")
    else:
        market = ("open", item.get("regime_reason") or "")
    fa = {"Đạt": "open", "Không đạt": "closed"}.get(item["fa_label"], "unknown")
    valuation = {"Đạt": "open", "Không đạt": "closed"}.get(item.get("valuation_label") or "", "unknown")
    news = {"Mở": "open", "Chờ": "watch", "Loại": "closed"}.get(item["news_state"], "unknown")
    flow = {"Mở": "open", "Chờ": "closed"}.get(item.get("flow_state") or "", "unknown")
    industry_open = item.get("industry_open")
    steps = [
        {"name": "Thị trường", "state": market[0], "detail": market[1], "blocks": True},
        {"name": "Cơ bản", "state": fa, "detail": f"{item['fa_label']}. {item.get('fa_reason') or ''}", "blocks": True},
        {
            "name": "Định giá",
            "state": valuation,
            "detail": f"{item.get('valuation_label') or '—'}. {item.get('valuation_reason') or ''}",
            # Thiếu P/E không chặn mã, nên ô này không bao giờ là cổng quyết định khi chỉ thiếu số.
            "blocks": valuation == "closed",
        },
        {"name": "Tin", "state": news, "detail": f"{news_label(item['news_state'])}. {item.get('news_reason') or ''}", "blocks": True},
        {
            "name": "Nền giá",
            "state": "open" if item["pattern_ready"] else "watch",
            "detail": item.get("pattern_reason") or "",
            "blocks": True,
        },
        {
            "name": "Dòng tiền",
            "state": flow,
            "detail": f"{flow_label(item.get('flow_level') or '', item.get('flow_state') or '')}. {item.get('flow_reason') or ''}",
            "blocks": flow == "closed",
        },
        {
            "name": "Ngành",
            "state": "unknown" if industry_open is None else ("open" if industry_open else "closed"),
            "detail": industry_name(item.get("industry_name")) or "Không có nhóm đã đo",
            "blocks": INDUSTRY_GATE_ENFORCED,
            "observe": not INDUSTRY_GATE_ENFORCED,
        },
    ]
    for step in steps:
        step["word"] = STATE_WORDS[step["state"]]
    # Thiếu P/E hay thiếu số khối ngoại không chặn mã, nên ô đó nói "chưa có số" chứ không "chưa chấm".
    for step in steps[2], steps[5]:
        if step["state"] == "unknown":
            step["word"] = "Chưa có số"
    if item["status"] != "Được vào":
        for step in steps:
            if step["blocks"] and step["state"] != "open":
                step["decides"] = True
                break
    return steps


_INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\w)"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), r'<a href="\2" rel="noreferrer">\1</a>'),
]


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    for pattern, replacement in _INLINE:
        out = pattern.sub(replacement, out)
    return out


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
