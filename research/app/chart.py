"""Nến Nhật cho trang chi tiết mã, kèm cột khối lượng và hình học của mẫu giá đã khớp.

Khung giá nằm trên, cột khối lượng nằm dưới, hai khung dùng chung khe thời gian nên cột nào
cũng thẳng với nến của nó. Toạ độ được dựng ở đây theo pixel rồi đưa sang template, nên
Jinja chỉ việc lặp và in. Không thêm thư viện vẽ nào: SVG nằm thẳng trong `symbol.html`.
"""

from __future__ import annotations

from app.pattern import Pattern, Shape

# Khung nhìn là `sessions` phiên cuối, nên cửa sổ nền 20 phiên luôn nằm trong hình.
CHART_SESSIONS = 120
CHART_WIDTH = 960
CHART_HEIGHT = 340
CHART_PAD = {"left": 6, "right": 62, "top": 14, "bottom": 22}
# Phần trăm mỗi khe thời gian để trống giữa hai nến.
CANDLE_GAP = 0.3
TICK_COUNT = 4
# Khung khối lượng lấy chỗ từ khung giá, cách nhau một khe để hai thang không dính vào nhau.
VOLUME_HEIGHT = 54
VOLUME_GAP = 10
VOLUME_TICK_COUNT = 2

_LABELS = {
    "base": "Nền 20 phiên",
    "double_bottom": "Đáy đôi",
    "vcp": "VCP",
    "flag": "Cờ",
    "abcd": "ABCD",
}


def _label(shape: Shape) -> str:
    return _LABELS.get(shape.kind, shape.kind)


def _volume_text(value: float) -> str:
    """Khối lượng trên trục dọc, viết ngắn cho vừa khe nhãn bên phải.

    Đổi đơn vị ở mức mà dạng ngắn hơn vẫn đọc đúng: dưới 10.000 giữ nguyên con số, và chỉ từ
    999.950 mới nhảy lên "tr" để không có nhãn nào phải in thành "1000.0k".
    """
    if value >= 999_950:
        return f"{value / 1_000_000:,.1f}tr"
    if value >= 10_000:
        return f"{value / 1_000:,.1f}k"
    return f"{value:,.0f}"


def build_chart(
    bars: list[dict],
    pattern: Pattern | None,
    sessions: int = CHART_SESSIONS,
) -> dict | None:
    """Candles for the tail of the series plus the geometry behind the pattern sentence.

    The pattern is computed on the whole series while the frame is only its tail, so a
    structure whose pivots fall outside the frame is dropped instead of drawn clipped.
    Nothing is resampled: a bar outside the frame is simply not there.
    """
    window = bars[-sessions:] if sessions and len(bars) > sessions else list(bars)
    if len(window) < 2:
        return None
    dates = [str(bar["trade_date"]) for bar in window]
    position = {day: index for index, day in enumerate(dates)}
    high = max(float(bar["high"]) for bar in window)
    low = min(float(bar["low"]) for bar in window)
    if high <= low:
        return None

    span = CHART_WIDTH - CHART_PAD["left"] - CHART_PAD["right"]
    slot = span / len(window)
    volumes = [float(bar.get("volume") or 0.0) for bar in window]
    peak_volume = max(volumes)
    plot_top = CHART_PAD["top"]
    # The volume pane is carved out of the bottom with a gap above it; with nothing to draw there
    # the price plot takes the whole card back instead of leaving a blank strip.
    volume_top = CHART_HEIGHT - CHART_PAD["bottom"] - VOLUME_HEIGHT
    plot_bottom = (
        volume_top - VOLUME_GAP if peak_volume > 0 else CHART_HEIGHT - CHART_PAD["bottom"]
    )
    plot_height = plot_bottom - plot_top

    def x_of(day: str) -> float | None:
        index = position.get(day)
        if index is None:
            return None
        return CHART_PAD["left"] + index * slot + slot / 2

    def y_of(price: float) -> float:
        return plot_top + (high - price) / (high - low) * plot_height

    def pixel(point: tuple[str, float]) -> tuple[float, float] | None:
        x = x_of(point[0])
        if x is None:
            return None
        return round(x, 2), round(y_of(point[1]), 2)

    candles = []
    for index, (bar, volume) in enumerate(zip(window, volumes)):
        open_price = float(bar["open"])
        close_price = float(bar["close"])
        top = y_of(max(open_price, close_price))
        bottom = y_of(min(open_price, close_price))
        candles.append(
            {
                "x": round(CHART_PAD["left"] + index * slot + slot * CANDLE_GAP / 2, 2),
                "width": round(max(1.0, slot * (1 - CANDLE_GAP)), 2),
                "center": round(CHART_PAD["left"] + index * slot + slot / 2, 2),
                "y": round(top, 2),
                "height": round(max(1.0, bottom - top), 2),
                "high_y": round(y_of(float(bar["high"])), 2),
                "low_y": round(y_of(float(bar["low"])), 2),
                "up": close_price >= open_price,
                "title": (
                    f"{bar['trade_date']} · O {open_price:.2f} H {float(bar['high']):.2f} "
                    f"L {float(bar['low']):.2f} C {close_price:.2f} · V {_volume_text(volume)}"
                ),
            }
        )

    # One column per session, scaled to the heaviest bar in the frame. Each column borrows the
    # candle's slot and colour instead of recomputing them, so the two can never drift apart; a
    # session with no volume keeps its slot but draws nothing.
    volume = None
    if peak_volume > 0:
        shares = [value / peak_volume for value in volumes]
        volume = {
            "top": round(volume_top, 2),
            "floor": round(volume_top + VOLUME_HEIGHT, 2),
            "label": "KL",
            "max_text": _volume_text(peak_volume),
            "ticks": [
                {
                    "y": round(volume_top + VOLUME_HEIGHT * (1 - step / VOLUME_TICK_COUNT), 2),
                    "text": _volume_text(peak_volume * step / VOLUME_TICK_COUNT),
                }
                for step in range(1, VOLUME_TICK_COUNT + 1)
            ],
            "bars": [
                {
                    "x": candle["x"],
                    "width": candle["width"],
                    "up": candle["up"],
                    "y": round(volume_top + VOLUME_HEIGHT * (1 - share), 2),
                    "height": round(VOLUME_HEIGHT * share, 2),
                    "title": f"{bar['trade_date']} · KL {_volume_text(value)}",
                }
                for candle, bar, value, share in zip(candles, window, volumes, shares)
            ],
        }


    boxes: list[dict] = []
    lines: list[dict] = []
    polylines: list[dict] = []
    legend: list[str] = []
    for shape in pattern.geometry if pattern else ():
        drawn = False
        if shape.box is not None:
            start, end, shape_low, shape_high = shape.box
            left = x_of(start)
            right = x_of(end)
            if left is not None and right is not None:
                top = y_of(shape_high)
                bottom = y_of(shape_low)
                boxes.append(
                    {
                        "x": round(min(left, right), 2),
                        "y": round(min(top, bottom), 2),
                        "width": round(max(2.0, abs(right - left)), 2),
                        "height": round(max(2.0, abs(bottom - top)), 2),
                        "kind": shape.kind,
                    }
                )
                drawn = True
                if shape.kind == "base":
                    # The ceiling is the level a breakout has to clear, so it gets its own
                    # line out to the last session instead of only the edge of the box.
                    right_edge = CHART_PAD["left"] + (len(window) - 1) * slot + slot / 2
                    lines.append(
                        {
                            "x1": round(left, 2),
                            "y1": round(top, 2),
                            "x2": round(max(right, right_edge), 2),
                            "y2": round(top, 2),
                            "kind": "ceiling",
                            "label": "Đỉnh nền",
                        }
                    )
        points = [pixel(point) for point in shape.points]
        if len(points) >= 2 and all(point is not None for point in points):
            clean = [point for point in points if point is not None]
            polylines.append(
                {
                    "points": " ".join(f"{x},{y}" for x, y in clean),
                    "kind": shape.kind,
                    "start": clean[0],
                }
            )
            drawn = True
        for segment in shape.segments:
            first = pixel(segment[0])
            second = pixel(segment[1])
            if first is not None and second is not None:
                lines.append(
                    {
                        "x1": first[0],
                        "y1": first[1],
                        "x2": second[0],
                        "y2": second[1],
                        "kind": shape.kind,
                        "label": _label(shape),
                    }
                )
                drawn = True
        if drawn:
            name = _label(shape)
            if name not in legend:
                legend.append(name)

    ticks = []
    for step in range(TICK_COUNT + 1):
        price = low + (high - low) * step / TICK_COUNT
        ticks.append({"y": round(y_of(price), 2), "text": f"{price:,.2f}"})

    breakout = None
    if pattern is not None and pattern.base_ceiling is not None and candles:
        if float(window[-1]["close"]) > pattern.base_ceiling:
            ratio = pattern.breakout_volume_ratio
            breakout = {
                "x": candles[-1]["center"],
                # The breakout bar is often the highest in the frame, so the label is lifted
                # off the pad edge instead of letting its ascender clip at the top.
                "y": round(max(candles[-1]["high_y"] - 8, 12.0), 2),
                "text": f"Nến phá {ratio:.1f}x nền" if ratio else "Nến phá nền",
            }

    return {
        "width": CHART_WIDTH,
        "height": CHART_HEIGHT,
        "plot_right": CHART_WIDTH - CHART_PAD["right"],
        "sessions": len(window),
        "first_date": dates[0],
        "last_date": dates[-1],
        "high": round(high, 2),
        "low": round(low, 2),
        "candles": candles,
        "volume": volume,
        "boxes": boxes,
        "lines": lines,
        "polylines": polylines,
        "ticks": ticks,
        "legend": legend,
        "breakout": breakout,
    }


LINE_HEIGHT = 220


def build_line_chart(
    series: list[dict],
    *,
    levels: list[dict] | None = None,
    value_format: str = "{:,.0f}",
    height: int = LINE_HEIGHT,
) -> dict | None:
    """Đường theo phiên cho các trang thị trường, cùng khung với nến của trang mã.

    `series` là [{"name", "kind", "points": [(ngày, giá trị)]}]; chuỗi đầu tiên đặt trục thời
    gian, điểm của chuỗi sau không có ngày đó thì bỏ. `levels` là các mốc ngang đã khai báo,
    như ngưỡng mở và đóng của độ rộng, để đường được đọc cạnh luật của nó.
    """
    if not series or len(series[0]["points"]) < 2:
        return None
    levels = levels or []
    dates = [str(day) for day, _value in series[0]["points"]]
    position = {day: index for index, day in enumerate(dates)}
    values = [float(value) for item in series for day, value in item["points"] if str(day) in position]
    values += [float(level["value"]) for level in levels]
    high, low = max(values), min(values)
    if high <= low:
        high, low = high + 1, low - 1
    pad = (high - low) * 0.06
    high, low = high + pad, low - pad

    plot_right = CHART_WIDTH - CHART_PAD["right"]
    span = plot_right - CHART_PAD["left"]
    plot_top = CHART_PAD["top"]
    plot_bottom = height - CHART_PAD["bottom"]
    step = span / max(1, len(dates) - 1)

    def x_of(index: int) -> float:
        return round(CHART_PAD["left"] + index * step, 2)

    def y_of(value: float) -> float:
        return round(plot_top + (high - value) / (high - low) * (plot_bottom - plot_top), 2)

    lines = []
    for item in series:
        kept = [(position[str(day)], float(value)) for day, value in item["points"] if str(day) in position]
        if len(kept) < 2:
            continue
        lines.append(
            {
                "name": item["name"],
                "kind": item.get("kind", ""),
                "points": " ".join(f"{x_of(index)},{y_of(value)}" for index, value in kept),
                "last_text": value_format.format(kept[-1][1]),
                "last_y": y_of(kept[-1][1]),
            }
        )
    return {
        "width": CHART_WIDTH,
        "height": height,
        "plot_right": plot_right,
        "plot_bottom": plot_bottom,
        "sessions": len(dates),
        "first_date": dates[0],
        "last_date": dates[-1],
        "lines": lines,
        "levels": [
            {**level, "y": y_of(float(level["value"]))} for level in levels
        ],
        "ticks": [
            {"y": y_of(low + (high - low) * index / TICK_COUNT), "text": value_format.format(low + (high - low) * index / TICK_COUNT)}
            for index in range(1, TICK_COUNT)
        ],
    }
