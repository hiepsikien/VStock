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


def present(record: DailyRecord) -> dict[str, object]:
    """Labels for the sheet. The chip stays a gate check, with no composite score."""
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
                "title": "Cổng",
                "lines": [
                    {"label": "Nến trên thân", "value": _flag(record.gates.source_on_body)},
                    {"label": "Khung p → ppp", "value": _flag(record.gates.frame)},
                    {"label": "Span hẹp toàn mf", "value": _flag(record.gates.narrow_span_all_mf)},
                ],
            },
            {
                "title": "Trung thực",
                "lines": [
                    {"label": "F1 hướng", "value": _fmt(fidelity.f1)},
                    {"label": "F2 hạng", "value": _fmt(fidelity.f2)},
                    {"label": "F3 lead", "value": _fmt(fidelity.f3_lead_support)},
                    {"label": "F3 high", "value": _fmt(fidelity.f3_high)},
                    {"label": "F4 đỉnh", "value": _fmt(fidelity.f4)},
                    {"label": "F5 chữ", "value": _fmt(fidelity.f5)},
                    {"label": "F6 lift", "value": _fmt(fidelity.f6)},
                ],
            },
            {
                "title": "Hợp lệ",
                "lines": [
                    {"label": "M1 lead", "value": _fmt(legality.m1_lead_support)},
                    {"label": "M1 lead giữ", "value": _flag(legality.m1_lead_support_holds)},
                    {"label": "M1 high", "value": _fmt(legality.m1_high)},
                    {"label": "M2 bass quá 8", "value": str(legality.m2_bass_octave_leaps)},
                    {"label": "M2 bước chưa giải", "value": str(legality.m2_melody_unresolved_leaps)},
                    {"label": "M2 quãng 5 song song", "value": str(legality.m2_parallel_fifths)},
                    {"label": "M3 âm chung", "value": _fmt(legality.m3_mean_common)},
                    {"label": "M3 lần đổi trống", "value": _fmt(legality.m3_zero_common_rate)},
                    {"label": "M4 entropy", "value": _fmt(legality.m4_bigram_entropy)},
                    {"label": "M4 hợp âm dài nhất", "value": str(legality.m4_longest_chord)},
                    {"label": "M4 số chữ", "value": str(legality.m4_liquidity_letters)},
                    {"label": "M5 khung", "value": _flag(legality.m5_frame)},
                ],
            },
            {
                "title": "Đối chứng",
                "lines": [
                    {"label": "Đảo giá F1", "value": _fmt(controls.price_reversed.f1)},
                    {"label": "Đảo volume F5", "value": _fmt(controls.volume_reversed.f5)},
                    {
                        "label": "Xáo regime F6",
                        "value": _fmt(controls.regime_shuffled.f6)
                        if controls.regime_shuffled.labels_changed
                        else "Bỏ qua",
                    },
                    {"label": "Hoán vị F1", "value": _fmt(controls.pitches_permuted.f1)},
                    {"label": "Hoán vị M1", "value": _fmt(controls.pitches_permuted.m1_lead_support)},
                ],
            },
        ],
        "notes": notes,
    }


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
