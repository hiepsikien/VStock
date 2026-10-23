"""1-minute session selection, playback cursor, and cached MuseScore audio."""

from __future__ import annotations

import os
import struct
import threading
import time
import wave
from array import array
from datetime import date, datetime
from pathlib import Path

import pytest

from app.sonify.audio import (
    RECAP_REVISION,
    WORK_KEEP_SEC,
    RecapCancelled,
    RecapStore,
    resolve_executable,
    waveform_peaks,
)
from app.sonify.model import Bar
from app.sonify.playback import candle_index_at, piece_seconds
from app.sonify.render import assign_source_bars
from app.sonify.session import VN, is_session_closed, samples_from_ohlc, session_points
from app.services.sessions import minute_series, summarize_sessions

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
    # Day 1 has no earlier close, so the reference is its first print (100.5 → 103).
    assert sessions[0]["changePercent"] == round((103 - 100.5) / 100.5 * 100, 2)
    # Day 2 is versus the previous session close (103), not its own 09:00 print (104).
    assert sessions[1]["changePercent"] == round((106.5 - 103) / 103 * 100, 2)
    assert sessions[1]["changePercent"] != round((106.5 - 104) / 104 * 100, 2)
    detail = minute_series(_payload(), NEXT)
    assert detail is not None
    assert detail["changePercent"] == sessions[1]["changePercent"]


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


def test_waveform_peaks_read_musescore4_float_wav(tmp_path: Path) -> None:
    path = tmp_path / "float.wav"
    samples = array("f", [0.0] * 400 + [0.5] * 400)
    payload = samples.tobytes()
    fmt = struct.pack("<HHIIHH", 3, 1, 8000, 32000, 4, 32)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(payload)) + payload
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body)
    duration, peaks = waveform_peaks(path, buckets=8)
    assert duration == 0.1
    assert max(peaks) == 1.0
    assert min(peaks) == 0.0


def _export_recorder(calls: list[Path]):
    def export(xml: Path, wav: Path) -> None:
        assert xml.is_file() and xml.stat().st_size > 50
        calls.append(xml)
        _write_wav(wav)

    return export


def test_recap_store_replays_the_same_piece_and_rerenders_when_the_session_grows(tmp_path: Path) -> None:
    calls: list[Path] = []
    closed = datetime(2026, 10, 16, 9, 0, tzinfo=VN)
    store = RecapStore(tmp_path, exporter=_export_recorder(calls), clock=lambda: closed)
    bars = [Bar(100.0 + index, 10.0, 100.0) for index in range(12)]
    first = store.ensure("FPT", DAY, "symphony", bars)
    second = store.ensure("FPT", DAY, "symphony", bars)
    assert first.audio_path == second.audio_path
    assert len(calls) == 1
    assert len(first.peaks) == 96
    assert first.bar_count == 12
    assert f"_{RECAP_REVISION}_12" in first.audio_path.name
    assert first.audio_url.endswith(f"/recap/audio.m4a?variant=symphony&v=12&r={RECAP_REVISION}")

    grown = bars + [Bar(112.0, 10.0, 100.0)]
    third = store.ensure("FPT", DAY, "symphony", grown)
    assert len(calls) == 2
    assert third.bar_count == 13
    assert third.audio_path.is_file()
    assert not first.audio_path.exists()


def test_open_session_keeps_each_bar_count_and_closed_session_drops_the_partial(tmp_path: Path) -> None:
    calls: list[Path] = []
    noon = datetime(2026, 10, 14, 12, 0, tzinfo=VN)
    open_store = RecapStore(tmp_path, exporter=_export_recorder(calls), clock=lambda: noon)
    short = [Bar(100.0, 10.0, 100.0) for _ in range(4)]
    first = open_store.ensure("FPT", DAY, "jazz", short)
    grown = short + [Bar(104.0, 10.0, 100.0)]
    second = open_store.ensure("FPT", DAY, "jazz", grown)
    assert first.audio_path.is_file()
    assert second.audio_path.is_file()
    assert open_store.get("FPT", DAY, "jazz", 4) is not None
    assert open_store.get("FPT", DAY, "jazz", 5) is not None

    after = datetime(2026, 10, 14, 15, 0, tzinfo=VN)
    closed_store = RecapStore(tmp_path, exporter=_export_recorder(calls), clock=lambda: after)
    again = closed_store.ensure("FPT", DAY, "jazz", grown)
    assert again.audio_path == second.audio_path
    assert len(calls) == 2
    assert not first.audio_path.exists()
    assert closed_store.get("FPT", DAY, "jazz", 4) is None
    assert closed_store.get("FPT", DAY, "jazz", 5) is not None


def test_prune_drops_stale_export_config_dirs(tmp_path: Path) -> None:
    work = tmp_path / "work"
    fresh = work / "FPT_2026-10-14_symphony_3_12-mscore"
    stale = work / "VNM_2026-10-14_jazz_3_10-mscore"
    fresh.mkdir(parents=True)
    stale.mkdir()
    (fresh / "synthesizer.xml").write_text("<Synthesizer/>", encoding="utf-8")
    (stale / "synthesizer.xml").write_text("<Synthesizer/>", encoding="utf-8")
    expired = time.time() - WORK_KEEP_SEC - 60
    os.utime(stale, (expired, expired))
    RecapStore(tmp_path, exporter=lambda xml, wav: None).prune()
    assert fresh.is_dir()
    assert not stale.exists()


def test_get_does_not_compose(tmp_path: Path) -> None:
    def export(xml: Path, wav: Path) -> None:
        raise AssertionError(f"audio lookup composed {xml}")

    store = RecapStore(tmp_path, exporter=export)
    assert store.get("FPT", DAY, "symphony", 12) is None


def test_prune_drops_other_revisions_and_expired_files(tmp_path: Path) -> None:
    old = tmp_path / f"FPT_2026-10-14_symphony_1_12.m4a"
    current = tmp_path / f"FPT_{DAY.isoformat()}_symphony_{RECAP_REVISION}_12.m4a"
    stray = tmp_path / "notes.txt"
    old.write_bytes(b"old")
    current.write_bytes(b"new")
    stray.write_bytes(b"stray")
    store = RecapStore(tmp_path, exporter=lambda xml, wav: None)
    store.prune()
    assert not old.exists()
    assert not stray.exists()
    assert current.exists()

    expired = time.time() - 40 * 86400
    current.touch()
    os.utime(current, (expired, expired))
    store.prune()
    assert not current.exists()


def test_one_export_slot_runs_one_render_at_a_time(tmp_path: Path) -> None:
    current = 0
    peak = 0
    guard = threading.Lock()

    def export(xml: Path, wav: Path) -> None:
        nonlocal current, peak
        with guard:
            current += 1
            peak = max(peak, current)
        time.sleep(0.25)
        with guard:
            current -= 1
        _write_wav(wav)

    store = RecapStore(tmp_path, exporter=export, slots=1)
    bars = [Bar(100.0, 1.0, 100.0)]

    def run(symbol: str) -> None:
        store.ensure(symbol, DAY, "symphony", bars)

    threads = [threading.Thread(target=run, args=(symbol,)) for symbol in ("FPT", "VNM")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert peak == 1


def test_cancel_before_export_does_not_start_the_renderer(tmp_path: Path) -> None:
    def export(xml: Path, wav: Path) -> None:
        raise AssertionError("cancelled export still ran")

    store = RecapStore(tmp_path, exporter=export, slots=1)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(RecapCancelled):
        store.ensure("FPT", DAY, "symphony", [Bar(100.0, 1.0, 100.0)], cancel)
    assert list(tmp_path.glob("*.m4a")) == []
    assert list(tmp_path.glob("*.wav")) == []


def test_cancel_during_export_does_not_publish(tmp_path: Path) -> None:
    from app.sonify.audio import _raise_if_cancelled

    cancel = threading.Event()

    def export(xml: Path, wav: Path) -> None:
        cancel.set()
        time.sleep(0.05)
        _raise_if_cancelled()
        _write_wav(wav)

    store = RecapStore(tmp_path, exporter=export, slots=1)
    with pytest.raises(RecapCancelled):
        store.ensure("FPT", DAY, "minimalist", [Bar(100.0, 1.0, 100.0)], cancel)
    assert list(tmp_path.glob("*.m4a")) == []
    assert list(tmp_path.glob("*.wav")) == []
    assert list(tmp_path.glob("*.json")) == []


def test_musescore_export_applies_soundfont_via_config_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sonify import audio as audio_mod

    binary = tmp_path / "mscore"
    seen = tmp_path / "seen.txt"
    font = tmp_path / "General.sf3"
    font.write_bytes(b"sf")
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "import wave\n"
        f"seen = Path({str(seen)!r})\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['--help']:\n"
        "    print('--config-folder')\n"
        "    raise SystemExit(0)\n"
        "seen.write_text('\\n'.join(args), encoding='utf-8')\n"
        "config = Path(args[1])\n"
        "seen.with_suffix('.snap').write_text(\n"
        "    (config / 'synthesizer.xml').read_text(encoding='utf-8')\n"
        "    + (config / 'MuseScore' / 'MuseScore3.ini').read_text(encoding='utf-8'),\n"
        "    encoding='utf-8',\n"
        ")\n"
        "out = Path(args[args.index('-o') + 1])\n"
        "with wave.open(str(out), 'wb') as handle:\n"
        "    handle.setnchannels(1)\n"
        "    handle.setsampwidth(2)\n"
        "    handle.setframerate(8000)\n"
        "    handle.writeframes(b'\\x00\\x00' * 800)\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    silenced: list[str] = []

    def silence() -> Callable[[], None]:
        silenced.append("off")

        def restore() -> None:
            silenced.append("on")

        return restore

    monkeypatch.setattr(audio_mod, "_silence_metronome", silence)
    monkeypatch.setenv("MUSESCORE_BIN", str(binary))
    monkeypatch.setenv("MUSESCORE_SOUNDFONT", str(font))
    audio_mod._config_folder_support.pop(str(binary), None)
    xml = tmp_path / "in.musicxml"
    xml.write_text("<score/>", encoding="utf-8")
    wav = tmp_path / "out.wav"
    audio_mod.musescore_export(xml, wav)
    args = seen.read_text(encoding="utf-8").splitlines()
    assert args[0] == "-c"
    config = Path(args[1])
    snap = seen.with_suffix(".snap").read_text(encoding="utf-8")
    assert str(font) in snap
    assert str(font.parent) in snap
    assert not config.exists()
    assert wav.is_file()

    plain = tmp_path / "mscore4"
    plain_seen = tmp_path / "plain.txt"
    plain.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "import wave\n"
        f"seen = Path({str(plain_seen)!r})\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['--help']:\n"
        "    print('usage')\n"
        "    raise SystemExit(0)\n"
        "seen.write_text('\\n'.join(args), encoding='utf-8')\n"
        "out = Path(args[args.index('-o') + 1])\n"
        "with wave.open(str(out), 'wb') as handle:\n"
        "    handle.setnchannels(1)\n"
        "    handle.setsampwidth(2)\n"
        "    handle.setframerate(8000)\n"
        "    handle.writeframes(b'\\x00\\x00' * 800)\n",
        encoding="utf-8",
    )
    plain.chmod(0o755)
    monkeypatch.setenv("MUSESCORE_BIN", str(plain))
    audio_mod._config_folder_support.pop(str(plain), None)
    wav4 = tmp_path / "out4.wav"
    audio_mod.musescore_export(xml, wav4)
    plain_args = plain_seen.read_text(encoding="utf-8").splitlines()
    assert plain_args[0] == "-o"
    assert "-c" not in plain_args
    assert silenced == ["off", "on", "off", "on"]


def test_musescore_export_uses_installed_musesounds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    import sqlite3

    from app.sonify import audio as audio_mod

    library = tmp_path / "Instruments"
    library.mkdir()
    database = library / ".instruments"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE instruments (id integer PRIMARY KEY, path text, state integer, version text, package_key integer, name text, abbreviation text)"
        )
        connection.execute("CREATE TABLE packages (key integer PRIMARY KEY, guid text, path text, name text)")
        connection.execute("INSERT INTO packages VALUES (1, 'g', 'Muse Strings', 'Muse Strings')")
        connection.execute(
            "INSERT INTO instruments VALUES (91, 'Muse Strings/Violins 1', 1, '0.4', 1, ' Violins 1', 'Vln')"
        )
    binary = tmp_path / "mscore"
    seen = tmp_path / "seen.txt"
    assigned = tmp_path / "assigned.json"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, zipfile, wave\n"
        "from pathlib import Path\n"
        f"seen = Path({str(seen)!r})\n"
        f"assigned = Path({str(assigned)!r})\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['--help']:\n"
        "    print('usage')\n"
        "    raise SystemExit(0)\n"
        "seen.write_text((seen.read_text(encoding='utf-8') if seen.exists() else '') + '\\n'.join(args) + '\\n---\\n', encoding='utf-8')\n"
        "out = Path(args[args.index('-o') + 1])\n"
        "src = Path(args[-1])\n"
        "if out.suffix == '.mscz':\n"
        "    mscx = ('<?xml version=\"1.0\"?><museScore><Score>'\n"
        "            '<Part id=\"1\"><Instrument id=\"violin\"><instrumentId>strings.violin</instrumentId></Instrument></Part>'\n"
        "            '<Part id=\"2\"><Instrument id=\"saw-synth\"><instrumentId>synth.tone.sawtooth</instrumentId></Instrument></Part>'\n"
        "            '</Score></museScore>')\n"
        "    with zipfile.ZipFile(out, 'w') as archive:\n"
        "        archive.writestr('score.mscx', mscx)\n"
        "        archive.writestr('audiosettings.json', '{\"tracks\": []}')\n"
        "else:\n"
        "    with zipfile.ZipFile(src) as archive:\n"
        "        assigned.write_text(archive.read('audiosettings.json').decode('utf-8'), encoding='utf-8')\n"
        "    with wave.open(str(out), 'wb') as handle:\n"
        "        handle.setnchannels(1)\n"
        "        handle.setsampwidth(2)\n"
        "        handle.setframerate(8000)\n"
        "        handle.writeframes(b'\\x00\\x00' * 800)\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    monkeypatch.setattr(audio_mod, "_silence_metronome", lambda: (lambda: None))
    monkeypatch.setattr(audio_mod, "_muse_sounds_cache", None)
    monkeypatch.setenv("MUSESCORE_BIN", str(binary))
    monkeypatch.setenv("MUSESOUNDS_DIR", str(library))
    monkeypatch.delenv("MUSESCORE_SOUNDFONT", raising=False)
    audio_mod._config_folder_support.pop(str(binary), None)
    xml = tmp_path / "in.musicxml"
    xml.write_text(
        "<score><instrument-name>Violin</instrument-name><instrument-name>Lead 2 (sawtooth)</instrument-name></score>",
        encoding="utf-8",
    )
    wav = tmp_path / "out.wav"
    audio_mod.musescore_export(xml, wav)
    calls = [
        [line for line in block.splitlines() if line]
        for block in seen.read_text(encoding="utf-8").split("---")
    ]
    calls = [block for block in calls if block]
    assert calls[0][0] == "-o"
    assert calls[0][1].endswith(".mscz")
    assert calls[1][0] == "-o"
    assert calls[1][2].endswith(".mscz")
    settings = json.loads(assigned.read_text(encoding="utf-8"))
    assert settings["activeSoundProfile"] == "MuseSounds"
    by_part = {track["partId"]: track for track in settings["tracks"]}
    violin = by_part["1"]["in"]["resourceMeta"]
    assert violin["id"] == "91"
    assert violin["type"] == "muse_sampler_sound_pack"
    assert violin["attributes"]["museUID"] == "91"
    assert violin["attributes"]["museName"] == "Violins 1"
    synth = by_part["2"]["in"]["resourceMeta"]
    assert synth["type"] == "fluid_soundfont"
    assert synth["id"] == "MS Basic"
    assert wav.is_file()
    assert not wav.with_suffix(".mscz").exists()


def test_nylon_guitar_stays_on_ms_basic_so_note_velocities_speak(tmp_path: Path) -> None:
    import json
    import zipfile

    from app.sonify.audio import _assign_installed_sounds

    mscz = tmp_path / "guitar.mscz"
    body = (
        '<?xml version="1.0"?><museScore><Score>'
        '<Part id="1"><Instrument id="guitar">'
        "<instrumentId>pluck.guitar.nylon-string</instrumentId></Instrument></Part>"
        "</Score></museScore>"
    )
    with zipfile.ZipFile(mscz, "w") as archive:
        archive.writestr("score.mscx", body)
        archive.writestr("audiosettings.json", '{"tracks": []}')
    # Even with the MuseSounds nylon installed, the part must not take it:
    # that sampler ignores per-note velocity, which carries the guitar balance.
    assert _assign_installed_sounds(mscz, {"Acoustic Nylon": ("77", "Muse Guitars")})
    with zipfile.ZipFile(mscz) as archive:
        settings = json.loads(archive.read("audiosettings.json"))
    assert settings["activeSoundProfile"] == "MS Basic"
    track = settings["tracks"][0]["in"]["resourceMeta"]
    assert track["type"] == "fluid_soundfont"
    assert track["id"] == "MS Basic"


def test_assign_installed_sounds_removes_partial_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import zipfile

    from app.sonify import audio as audio_mod

    mscz = tmp_path / "piece.mscz"
    mscx = (
        '<?xml version="1.0"?><museScore><Score>'
        '<Part id="1"><Instrument id="violin">'
        "<instrumentId>strings.violin</instrumentId></Instrument></Part>"
        "</Score></museScore>"
    )
    with zipfile.ZipFile(mscz, "w") as archive:
        archive.writestr("score.mscx", mscx)
        archive.writestr("audiosettings.json", '{"tracks": []}')
    original = mscz.read_bytes()
    real_zip = zipfile.ZipFile

    def broken_zip(path, mode="r", *args, **kwargs):
        if mode == "w":
            Path(path).write_bytes(b"partial")
            raise OSError("disk full")
        return real_zip(path, mode, *args, **kwargs)

    monkeypatch.setattr(audio_mod.zipfile, "ZipFile", broken_zip)
    with pytest.raises(OSError, match="disk full"):
        audio_mod._assign_installed_sounds(mscz, {"Violins 1": ("91", "Muse Strings")})
    assert not mscz.with_suffix(".mscz.tmp").exists()
    assert mscz.read_bytes() == original


def test_silence_metronome_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys

    from app.sonify import audio as audio_mod

    if sys.platform != "darwin":
        pytest.skip("MuseScore 4 metronome preference is a macOS defaults key")
    domain = "org.vstock.recap.metronome-test"
    monkeypatch.setattr(audio_mod, "_METRONOME_DOMAIN", domain)
    subprocess.run(["defaults", "delete", domain], check=False, capture_output=True)
    try:
        restore = audio_mod._silence_metronome()
        restore()
        read = subprocess.run(
            ["defaults", "read", domain, audio_mod._METRONOME_KEY],
            check=False,
            capture_output=True,
            text=True,
        )
        assert read.stdout.strip() == "0"
    finally:
        subprocess.run(["defaults", "delete", domain], check=False, capture_output=True)
