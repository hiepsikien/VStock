"""Turn one daily symphony into the QA sheet the mobile app opens.

The piece is the same one `RecapStore._render` writes for a 1D symphony:
home key, ensemble, and `movement_character` of the closes. The meter reads
that score before humanize. Humanize only moves velocity.
"""

from __future__ import annotations

from app.sonify.keys import CHARACTER_LABEL, movement_character, stock_home_key
from app.sonify.meter import DailyRecord, Gates, measure_daily
from app.sonify.model import Bar, Ensemble


def score_daily_bars(symbol: str, bars: list[Bar], ensemble: Ensemble = "classic") -> dict[str, object]:
    """Score the daily symphony this symbol's recap would write from `bars`."""
    if not bars:
        raise ValueError("need at least one price bar")
    from app.sonify.audio import _compose

    character = movement_character([bar.close for bar in bars], "1D")
    score, _dance = _compose(
        "symphony",
        ensemble,
        bars,
        title=f"{symbol} 1D",
        key=stock_home_key(symbol),
        character=character,
    )
    record = measure_daily(bars, score, planner_character=character)
    return present(record)


def ratio_total(
    f1: float | None,
    f2: float | None,
    f4: float | None,
    m1: float | None,
) -> tuple[float | None, int]:
    """Unweighted mean of the measures that already sit on 0–1.

    Spearman is mapped with `(rho + 1) / 2` before it enters. A missing
    measure is left out. It is not scored as zero. F3, F5, F6, the raw M
    counts, the gates, and the controls stay outside this mean.
    """
    parts: list[float] = []
    if f1 is not None:
        parts.append(f1)
    if f2 is not None:
        parts.append((f2 + 1) / 2)
    if f4 is not None:
        parts.append(f4)
    if m1 is not None:
        parts.append(m1)
    if not parts:
        return None, 0
    return sum(parts) / len(parts), len(parts)


def present(record: DailyRecord) -> dict[str, object]:
    """Labels for the sheet. The chip stays the three gates. The total is the ratio mean."""
    passed = _gates_pass(record.gates)
    notes: list[str] = []
    if not record.observations.mode_wired:
        notes.append(
            "Mode kỳ vọng "
            f"{_mode(record.observations.expected_mode)}, bản đang {_mode(record.observations.score_mode)}."
        )
    if record.fidelity.f1 is None:
        notes.append("Dưới 3 bậc thang trong r, F1 F2 F4 bỏ.")
    if not record.controls.regime_shuffled.labels_changed:
        notes.append("Thân một regime, đối chứng xáo bỏ qua.")
    character = CHARACTER_LABEL.get(record.stratum.character, record.stratum.character)
    notes.append(f"Character {character}.")
    fidelity = record.fidelity
    legality = record.legality
    controls = record.controls
    return {
        "gatesPass": passed,
        "chip": "QA · đạt" if passed else "QA · trượt",
        "blocks": [
            {
                "title": "Tổng",
                "lines": [_row("Điểm tổng", _total_value(record))],
            },
            {
                "title": "Cổng",
                "lines": [
                    _row("Nến trên thân", _flag(record.gates.source_on_body)),
                    _row("Khung p → ppp", _flag(record.gates.frame)),
                    _row("Span hẹp toàn mf", _flag(record.gates.narrow_span_all_mf)),
                ],
            },
            {
                "title": "Trung thực",
                "lines": [
                    _row("F1 hướng", _fmt(fidelity.f1)),
                    _row("F2 hạng", _fmt(fidelity.f2)),
                    _row("F3 lead/support", _fmt(fidelity.f3_lead_support)),
                    _row("F3 high", _fmt(fidelity.f3_high)),
                    _row("F4 điểm ngoặt", _fmt(fidelity.f4)),
                    _row("F5 chữ", _fmt(fidelity.f5)),
                    _row("F6 lift", _fmt(fidelity.f6)),
                ],
            },
            {
                "title": "Hợp lệ",
                "lines": [
                    _row("M1 lead", _fmt(legality.m1_lead_support)),
                    _row("M1 lead giữ", _flag(legality.m1_lead_support_holds)),
                    _row("M1 high", _fmt(legality.m1_high)),
                    _row("M2 bass quá 8", str(legality.m2_bass_octave_leaps)),
                    _row("M2 bước chưa giải", str(legality.m2_melody_unresolved_leaps)),
                    _row("M2 quãng 5 song song", str(legality.m2_parallel_fifths)),
                    _row("M3 âm chung", _fmt(legality.m3_mean_common)),
                    _row("M3 lần đổi trống", _fmt(legality.m3_zero_common_rate)),
                    _row("M4 entropy", _fmt(legality.m4_bigram_entropy)),
                    _row("M4 hợp âm dài nhất", str(legality.m4_longest_chord)),
                    _row("M4 số chữ", str(legality.m4_liquidity_letters)),
                    _row("M5 khung", _flag(legality.m5_frame)),
                ],
            },
            {
                "title": "Đối chứng",
                "lines": [
                    _row("Đảo giá F1", _fmt(controls.price_reversed.f1)),
                    _row("Đảo volume F5", _fmt(controls.volume_reversed.f5)),
                    _row(
                        "Xáo regime F6",
                        _fmt(controls.regime_shuffled.f6)
                        if controls.regime_shuffled.labels_changed
                        else "Bỏ qua",
                    ),
                    _row("Hoán vị F1", _fmt(controls.pitches_permuted.f1)),
                    _row("Hoán vị M1", _fmt(controls.pitches_permuted.m1_lead_support)),
                ],
            },
        ],
        "notes": notes,
    }


_RATIO_SLOTS = 4

_HINTS = {
    "Điểm tổng": (
        "Trung bình không trọng số của các tỷ lệ đang có, mỗi cái đã nằm trên 0–1: F1, F2 sau khi đưa Spearman về (ρ+1)/2, "
        "F4 điểm ngoặt, và M1 lead/support. Trung bình chia cho số thành phần đang có. Thành phần thiếu được bỏ, không tính là 0. "
        "Số 4 trong phần 3/4 ghi bên cạnh là số chỗ tối đa trong bốn tỷ lệ. "
        "Cổng, F3, F5, F6, M2, M3, M4 và các đối chứng đứng ngoài. Đây chưa phải tổng có trọng số của mục 8."
    ),
    "Nến trên thân": "Mọi nến nguồn phải nằm trên ô 2–31. Ô 0–1 và 32–33 là khung, không giữ nến.",
    "Khung p → ppp": "Ô 0 mở p, ô 33 tới ppp. Hai đầu khung đạp chủ âm của hợp âm ô đó.",
    "Span hẹp toàn mf": "Span volume dưới 2 lần và mọi cửa sổ thân có volume dương thì mọi chữ là mf. Cửa sổ im vẫn là p, cổng này không áp.",
    "F1 hướng": "Tỷ lệ bước cùng dấu giữa giá thô và giai điệu đã khâu. Gần 1 là bám hướng, quanh 0,5 là mất contour. Dưới 3 bậc thang thì bỏ.",
    "F2 hạng": "Spearman của giá và giai điệu trên phách mạnh của violin và cello. Flute không vào. Đây là thứ hạng trong phiên, không phải % lợi suất.",
    "F3 lead/support": "Độ bẻ trung bình của lead và support cộng lại, trên phách mạnh. Đơn vị là bậc thang giữa giai điệu và giá. Đây là hóa đơn của snap vào âm hợp âm.",
    "F3 high": "Cùng độ lệch trên flute. Gồm quãng 3 hoặc quãng 5 phía trên nốt snap, và mỗi lần flute hạ bát độ khi chạm trần.",
    "F4 điểm ngoặt": "Recall điểm ngoặt của giá, gồm cả đỉnh và đáy, được giai điệu nhắc lại cùng hướng trong ±1 ô. Cực trị lấy trên nốt đã ghi, kể cả flute bị hạ.",
    "F5 chữ": "Spearman giữa volume cửa sổ và chữ p–f trên ô 2–31. Đây là kiểm tra hàm gán chữ, không phải thanh khoản nghe được.",
    "F6 lift": "Chi phí catalog trừ chi phí hợp âm đã chọn. Dương khi hợp âm rẻ hơn catalog, tức hợp regime hơn.",
    "M1 lead": "Tỷ lệ phách mạnh của violin và cello rơi đúng âm hợp âm. Một lần trượt là lỗi snap.",
    "M1 lead giữ": "Đạt khi mọi phách mạnh của violin và cello đều là âm hợp âm.",
    "M1 high": "Cùng tỷ lệ trên flute. Đây là quãng phối khí, ghi riêng, không nhập vào hợp đồng snap.",
    "M2 bass quá 8": "Số bước bass trên thân nhảy hơn một quãng 8.",
    "M2 bước chưa giải": "Số bước giai điệu hơn một quãng 8 mà bước liền sau không đi ngược lại.",
    "M2 quãng 5 song song": "Hai phách mạnh liên tiếp đều là quãng 5 đúng, và cả hai bè cùng đi một hướng. Bước xiên và bước ngược để ngoài.",
    "M3 âm chung": "Trung bình số pitch class giữ lại mỗi lần đổi hợp âm.",
    "M3 lần đổi trống": "Tỷ lệ lần đổi hợp âm không còn pitch class chung.",
    "M4 entropy": "Entropy bigram pitch-class của đường khâu. Thấp là giai điệu lặp.",
    "M4 hợp âm dài nhất": "Số ô liên tiếp cùng một hợp âm trên thân.",
    "M4 số chữ": "Số chữ liquidity khác nhau trên ô 2–31.",
    "M5 khung": "Cùng hợp đồng khung: ô 0 là p, ô 33 là ppp, hai đầu đạp chủ âm.",
    "Đảo giá F1": "Giữ giai điệu, dựng lại giá từ chuỗi đảo. F1 tụt quanh 0,5 khi giai điệu đang bám giá. F5 đứng yên.",
    "Đảo volume F5": "Giữ chữ, đảo volume cùng cờ auction của đúng cây nến. F5 đổi dấu. Không nốt nào được viết lại.",
    "Xáo regime F6": "Giữ hợp âm, xáo nhãn regime rồi tính lại chi phí. Lift đổi khi nhãn đổi. Về gần 0 chỉ khi lift gốc đang dương rõ. Thân một regime thì bỏ qua.",
    "Hoán vị F1": "Xáo cao độ đường khâu, giữ nhịp và chỗ nghỉ. F1 đổ khi contour đang bám giá.",
    "Hoán vị M1": "Cùng phép hoán vị. M1 của violin và cello đổ vì nốt không còn nằm trên hợp âm.",
}


def _row(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value, "hint": _HINTS[label]}


def _total_value(record: DailyRecord) -> str:
    mean, count = ratio_total(
        record.fidelity.f1,
        record.fidelity.f2,
        record.fidelity.f4,
        record.legality.m1_lead_support,
    )
    if mean is None:
        return "—"
    return f"{_fmt(mean)} · {count}/{_RATIO_SLOTS}"


def _gates_pass(gates: Gates) -> bool:
    if not gates.source_on_body or not gates.frame:
        return False
    return gates.narrow_span_all_mf is not False


def _flag(value: bool | None) -> str:
    if value is None:
        return "Không áp"
    return "Đạt" if value else "Trượt"


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _mode(mode: str) -> str:
    if mode == "minor":
        return "thứ"
    if mode == "major":
        return "trưởng"
    return mode
