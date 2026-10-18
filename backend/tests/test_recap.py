"""1-minute session selection, playback cursor, and cached MuseScore audio."""

from __future__ import annotations

import wave
from datetime import date, datetime
from pathlib import Path

from app.sonify.audio import RecapStore, resolve_executable, waveform_peaks
from app.sonify.model import Bar
from app.sonify.playback import candle_index_at, piece_seconds
from app.sonify.render import assign_source_bars
from app.sonify.session import VN, is_session_closed, samples_from_ohlc, session_points
from app.services.sessions import summarize_sessions

DAY = date(2026, 10, 14)
NEXT = date(2026, 10, 15)


def _stamp(day: date, hour: int, minute: int) -> int:
    return int(datetime(day.year, day.month, day.day, hour, minute, tzinfo=VN).timestamp())


def _payload() -> dict:
    rows: list[tuple[int, float, float]] = []
    price = 100.0
    for day in (DAY, NEXT):
        for hour, minute in ((9, 0), (9, 1), (11, 29), (11, 31), (13, 0), (14, 45), (14, 50)):
            price += 0.5
            rows.append((_stamp(day, hour, minute), price, 1000.0))
    return {"t": [row[0] for row in rows], "c": [row[1] for row in rows], "v": [row[2] for row in rows]}


def test_summary_keeps_seven_sessions_and_drops_lunch() -> None:
    sessions = summarize_sessions(_payload(), limit=7)
    assert [row["date"] for row in sessions] == [DAY.isoformat(), NEXT.isoformat()]
    # 09:00, 09:01, 11:29, 13:00, 14:45. Lunch 11:31 and post-close 14:50 are out.
    assert sessions[0]["bars"] == 5
    assert sessions[0]["changePercent"] > 0


def test_session_points_follow_the_chosen_day() -> None:
    points = session_points(samples_from_ohlc(_payload()), DAY)
    assert [point.moment.strftime("%H:%M") for point in points] == [
        "09:00",
        "09:01",
        "11:29",
        "13:00",
        "14:45",
    ]
    assert all(point.moment.date() == DAY for point in points)


def test_closed_session_is_a_finished_vn_day() -> None:
    noon = datetime(2026, 10, 14, 12, 0, tzinfo=VN)
    after_close = datetime(2026, 10, 14, 15, 0, tzinfo=VN)
    assert is_session_closed(DAY, noon) is False
    assert is_session_closed(DAY, after_close) is True
    assert is_session_closed(date(2026, 10, 13), noon) is True


def test_playhead_stays_on_the_candle_inside_its_musical_bar() -> None:
    count = 240
    duration = piece_seconds(30, 90)
    groups = assign_source_bars(count)
    for index in (0, 1, 17, 80, 239):
        group = next(bar for bar, members in enumerate(groups) if index in members)
        elapsed = (index + 0.5) / count * duration
        assert candle_index_at(elapsed, count, duration) == index
        bar_at = min(29, int(elapsed / (duration / 30)))
        assert bar_at == group


def _write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 400 + b"\xff\x7f" * 400)


def test_resolve_executable_accepts_an_absolute_binary(tmp_path: Path) -> None:
    binary = tmp_path / "mscore"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    assert resolve_executable([str(binary), "missing-mscore"]) == str(binary)
    assert resolve_executable(["missing-mscore-bin"]) is None


def test_waveform_peaks_are_normalized() -> None:
    path = Path("/tmp/vstock-peaks.wav")
    _write_wav(path)
    duration, peaks = waveform_peaks(path, buckets=8)
    assert duration == 0.1
    assert len(peaks) == 8
    assert max(peaks) == 1.0
    assert min(peaks) == 0.0


def test_recap_store_replays_the_same_piece_and_rerenders_when_the_session_grows(tmp_path: Path) -> None:
    calls: list[Path] = []

    def export(xml: Path, wav: Path) -> None:
        assert xml.is_file() and xml.stat().st_size > 50
        calls.append(xml)
        _write_wav(wav)

    store = RecapStore(tmp_path, exporter=export)
    bars = [Bar(100.0 + index, 10.0, 100.0) for index in range(12)]
    first = store.ensure("FPT", DAY, "symphony", bars)
    second = store.ensure("FPT", DAY, "symphony", bars)
    assert first.audio_path == second.audio_path
    assert len(calls) == 1
    assert len(first.peaks) == 96
    assert first.bar_count == 12
    assert first.audio_url.endswith("variant=symphony&v=12")

    grown = bars + [Bar(112.0, 10.0, 100.0)]
    third = store.ensure("FPT", DAY, "symphony", grown)
    assert len(calls) == 2
    assert third.bar_count == 13
    assert third.audio_path.is_file()
