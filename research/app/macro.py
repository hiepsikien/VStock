from __future__ import annotations

from dataclasses import dataclass, field

from app.config import MACRO_MA_WINDOW, MACRO_NEUTRAL_BAND, MACRO_SYMBOLS
from app.pattern import sma


@dataclass(frozen=True)
class MacroLine:
    code: str
    label: str
    close: float
    ma: float
    change: float
    side: int  # 1 above the band, -1 below, 0 inside it


@dataclass(frozen=True)
class Macro:
    """Cross-market read: should the book take new risk at all."""

    risk: bool | None
    block: bool
    reason: str
    metrics: list[tuple[str, str]] = field(default_factory=list)
    flags: tuple[str, ...] = ()


MACRO_LABELS = {code: label for code, _symbol, label in MACRO_SYMBOLS}
# Cặp chặn: hai chuỗi này cùng đứng trên vùng trung tính thì danh sách mới bị khóa.
BLOCKING_PAIR = ("DXY", "USDVND")


def macro_state(series: dict[str, list[dict]]) -> Macro:
    lines: dict[str, MacroLine] = {}
    for code, _symbol, label in MACRO_SYMBOLS:
        bars = series.get(code) or []
        closes = [float(bar["close"]) for bar in bars if bar.get("close")]
        if len(closes) < MACRO_MA_WINDOW + 1:
            continue
        ma = sma(closes, MACRO_MA_WINDOW)
        if ma is None:
            continue
        close = closes[-1]
        if close > ma * (1 + MACRO_NEUTRAL_BAND):
            side = 1
        elif close < ma * (1 - MACRO_NEUTRAL_BAND):
            side = -1
        else:
            side = 0
        lines[code] = MacroLine(
            code=code,
            label=label,
            close=close,
            ma=ma,
            change=close / closes[-MACRO_MA_WINDOW] - 1,
            side=side,
        )

    if not lines:
        return Macro(None, False, "Chưa tải được dữ liệu vĩ mô")

    flags: list[str] = []
    dxy = lines.get("DXY")
    usdvnd = lines.get("USDVND")
    sp500 = lines.get("SP500")
    oil = lines.get("OIL")

    dxy_stress = bool(dxy and dxy.side == 1 and dxy.change > 0)
    usdvnd_stress = bool(usdvnd and usdvnd.side == 1)
    sp500_stress = bool(sp500 and sp500.side == -1)
    oil_stress = bool(oil and oil.change > 0.15)

    if dxy_stress and dxy:
        flags.append(f"đô la tăng ({dxy.close:,.2f}, {dxy.change:+.1%} {MACRO_MA_WINDOW} phiên)")
    if usdvnd_stress and usdvnd:
        flags.append(f"tỷ giá trên MA{MACRO_MA_WINDOW} ({usdvnd.close:,.0f})")
    if sp500_stress and sp500:
        flags.append(f"S&P 500 dưới MA{MACRO_MA_WINDOW} ({sp500.close:,.0f})")
    if oil_stress and oil:
        flags.append(f"dầu tăng {oil.change:.0%} {MACRO_MA_WINDOW} phiên")

    block = dxy_stress and usdvnd_stress
    metrics: list[tuple[str, str]] = []
    for code, _symbol, label in MACRO_SYMBOLS:
        line = lines.get(code)
        if line is None:
            metrics.append((label, "chưa tải được"))
            continue
        metrics.append(
            (
                label,
                f"{line.close:,.2f} — {line.change:+.1%} {MACRO_MA_WINDOW} phiên, "
                f"{'trên' if line.side == 1 else 'dưới' if line.side == -1 else 'quanh'} "
                f"MA{MACRO_MA_WINDOW}",
            )
        )
    # Yahoo trả từng mã một, nên thiếu một chân của cặp chặn là chuyện thường gặp — và cũng là
    # chuyện không thể kết luận: chưa biết tỷ giá thì cổng chưa chấm được, chứ không phải trung tính.
    # Ba chuỗi còn lại chỉ cảnh báo, thiếu chúng vẫn chấm được.
    absent = [code for code in BLOCKING_PAIR if code not in lines]
    if absent:
        where = ", ".join(MACRO_LABELS[code] for code in absent)
        seen = f" (đã thấy: {'; '.join(flags)})" if flags else ""
        return Macro(
            None,
            False,
            f"Thiếu {where}, cặp đô la và tỷ giá chưa đánh giá được{seen}",
            metrics,
            tuple(flags),
        )
    if not flags:
        return Macro(False, False, "Vĩ mô trung tính: không có cảnh báo liên thị trường", metrics)
    reason = "; ".join(flags)
    if block:
        return Macro(True, True, f"Vĩ mô căng: {reason}. Chưa mở vị thế mới.", metrics, tuple(flags))
    return Macro(True, False, f"Vĩ mô cần theo dõi: {reason}", metrics, tuple(flags))
