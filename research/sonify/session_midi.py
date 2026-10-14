"""One trading session as a MIDI file.

FPT on 2026-10-14, 1-minute bars, key of C major, 4/4 at 80 BPM.
Each minute is one eighth note. The violin plays the C major scale across
C3–C7, four octaves. Bass stays on the narrower C2–C5 register.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

import numpy as np

SYMBOL = "FPT"
SESSION_DAY = "2026-10-14"
RESOLUTION = "1"
BPM = 80
PPQ = 480
EIGHTHS_PER_BAR = 8
EIGHTH_TICKS = PPQ // 2
# About 50 ms of overlap so a moving line connects instead of pecking.
LEGATO_TICKS = 30

# C major scale: C D E F G A B. The key is C; the melody is not limited
# to the C-E-G triad.
SCALE_PCS = (0, 2, 4, 5, 7, 9, 11)
# Violin spans four octaves. The extra octave is the one below C4,
# so the top of the day stays at C7 and the bottom opens down to C3.
VIOLIN_LOW = 48  # C3
VIOLIN_HIGH = 96  # C7
# Bass keeps the previous three-octave window, then drops one octave.
BASS_LOW = 48  # C3
BASS_HIGH = 84  # C6
BASS_DROP = 12

# Volume relative to the session median. Positions are eighths inside a 4/4 bar.
SPARSE_BELOW = 0.7  # downbeat only
DENSE_FROM = 1.6  # a quarter-note pulse
BASS_TICKS = PPQ  # quarter note: a pulse with body, not a click
PIANO_VELOCITY = 78

# Lunch is a long hole. Compress it to one silent measure.
# The ATC halt is shorter and keeps its real length in eighth notes.
LUNCH_GAP_MINUTES = 40
LUNCH_REST_EIGHTHS = EIGHTHS_PER_BAR

TZ = timezone(timedelta(hours=7))
OUT_DIR = Path(__file__).resolve().parent / "out"
ENTRADE = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.dnse.com.vn",
    "Referer": "https://www.dnse.com.vn/",
}
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class Bar:
    ts: int
    label: str
    close: float
    volume: float
    ma20: float


@dataclass
class Slot:
    kind: str  # "bar" | "rest"
    label: str
    close: float | None = None
    volume: float | None = None
    ma20: float | None = None
    ratio: float | None = None


def note_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def fetch_payload() -> dict:
    now = int(datetime.now(tz=TZ).timestamp())
    start = now - 5 * 24 * 3600
    url = f"{ENTRADE}?from={start}&to={now}&symbol={SYMBOL}&resolution={RESOLUTION}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def bars_from_payload(payload: dict) -> list[Bar]:
    stamps = payload["t"]
    closes = payload["c"]
    volumes = payload["v"]
    series: list[tuple[int, float, float]] = []
    for ts, close, volume in zip(stamps, closes, volumes):
        series.append((int(ts), float(close), float(volume)))
    series.sort()

    ma_ready: list[tuple[int, float, float, float]] = []
    for i, (ts, close, volume) in enumerate(series):
        window = [c for _, c, _ in series[max(0, i - 19) : i + 1]]
        ma_ready.append((ts, close, volume, sum(window) / len(window)))

    today = []
    for ts, close, volume, ma20 in ma_ready:
        stamp = datetime.fromtimestamp(ts, TZ)
        if stamp.date().isoformat() != SESSION_DAY:
            continue
        today.append(Bar(ts, stamp.strftime("%H:%M"), close, volume, ma20))
    if not today:
        raise SystemExit(f"No {SYMBOL} bars on {SESSION_DAY}")
    return today


def map_price(price: float, lo: float, hi: float, midi_low: int, midi_high: int) -> float:
    if hi <= lo:
        return (midi_low + midi_high) / 2
    span = (price - lo) / (hi - lo)
    return midi_low + span * (midi_high - midi_low)


def snap_scale(midi_value: float, midi_low: int, midi_high: int) -> int:
    best = int(round(midi_value))
    best_dist = 999.0
    for note in range(midi_low - 12, midi_high + 13):
        if note % 12 not in SCALE_PCS:
            continue
        dist = abs(note - midi_value)
        if dist < best_dist:
            best_dist = dist
            best = note
    return best


def melody_midi(price: float, lo: float, hi: float) -> int:
    return snap_scale(map_price(price, lo, hi, VIOLIN_LOW, VIOLIN_HIGH), VIOLIN_LOW, VIOLIN_HIGH)


def bass_midi(price: float, lo: float, hi: float) -> int:
    return snap_scale(map_price(price, lo, hi, BASS_LOW, BASS_HIGH), BASS_LOW, BASS_HIGH) - BASS_DROP


def bass_hits(eighth_in_bar: int, ratio: float) -> bool:
    # A hot minute always speaks, even on an off-beat eighth.
    # Quieter minutes stay on the quarter-note grid so the bass can breathe.
    if ratio >= DENSE_FROM:
        return True
    if ratio >= SPARSE_BELOW:
        return eighth_in_bar in (0, 4)
    return eighth_in_bar == 0


def bass_ticks(ratio: float) -> int:
    if ratio >= DENSE_FROM:
        return EIGHTH_TICKS
    return BASS_TICKS


def bass_velocity(ratio: float) -> int:
    scaled = max(0.0, min(ratio, 3.0)) / 3.0
    return int(40 + scaled * 70)


def _rests_until_downbeat(slots: list[Slot], label: str, minimum: int) -> None:
    """Keep the next trading bar on beat 1, so a break does not shift the groove."""
    need = minimum
    remain = (EIGHTHS_PER_BAR - ((len(slots) + need) % EIGHTHS_PER_BAR)) % EIGHTHS_PER_BAR
    slots.extend(Slot("rest", label) for _ in range(need + remain))


def build_slots(bars: list[Bar]) -> list[Slot]:
    med = median(bar.volume for bar in bars)
    slots: list[Slot] = []
    for i, bar in enumerate(bars):
        if i > 0:
            gap_min = (bar.ts - bars[i - 1].ts) / 60
            extra = int(round(gap_min)) - 1
            if extra >= LUNCH_GAP_MINUTES:
                _rests_until_downbeat(slots, "lunch", LUNCH_REST_EIGHTHS)
            elif extra > 0:
                slots.extend(Slot("rest", "gap") for _ in range(extra))
        slots.append(
            Slot("bar", bar.label, bar.close, bar.volume, bar.ma20, bar.volume / med)
        )
    return slots


def vlq(value: int) -> bytes:
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def midi_track(events: list[tuple[int, int, bytes]]) -> bytes:
    ordered = sorted(events)
    body = bytearray()
    last = 0
    for tick, _order, data in ordered:
        body += vlq(tick - last)
        body += data
        last = tick
    body += vlq(0) + bytes([0xFF, 0x2F, 0x00])
    return b"MTrk" + len(body).to_bytes(4, "big") + bytes(body)


def meta_text(kind: int, text: str) -> bytes:
    raw = text.encode()
    return bytes([0xFF, kind, len(raw)]) + raw


def write_midi(path: Path, slots: list[Slot], lo: float, hi: float) -> dict:
    us_per_beat = int(60_000_000 / BPM)
    tempo = bytes(
        [
            0xFF,
            0x51,
            0x03,
            (us_per_beat >> 16) & 0xFF,
            (us_per_beat >> 8) & 0xFF,
            us_per_beat & 0xFF,
        ]
    )
    time_sig = bytes([0xFF, 0x58, 0x04, 0x04, 0x02, 0x18, 0x08])

    piano: list[tuple[int, int, bytes]] = [
        (0, 0, meta_text(0x03, f"{SYMBOL} {SESSION_DAY} violin")),
        (0, 1, tempo),
        (0, 2, time_sig),
        (0, 3, bytes([0xC0, 40])),  # violin
    ]
    bass: list[tuple[int, int, bytes]] = [
        (0, 0, meta_text(0x03, f"{SYMBOL} {SESSION_DAY} bass")),
        (0, 1, bytes([0xC1, 33])),  # finger bass
    ]

    score: list[dict] = []
    prev_close: float | None = None
    prev_piano: int | None = None
    agree = 0
    compared = 0
    wrong_way = 0
    flattened = 0
    piano_run: dict | None = None

    def close_piano_run(next_index: int | None) -> None:
        nonlocal piano_run
        if piano_run is None:
            return
        start = piano_run["start"] * EIGHTH_TICKS
        end = piano_run["end"] * EIGHTH_TICKS
        if next_index is not None and next_index == piano_run["end"]:
            end += LEGATO_TICKS
        note = piano_run["note"]
        piano.append((start, 10, bytes([0x90, note, PIANO_VELOCITY])))
        piano.append((end, 0, bytes([0x80, note, 0])))
        piano_run = None

    for index, slot in enumerate(slots):
        tick = index * EIGHTH_TICKS
        eighth = index % EIGHTHS_PER_BAR
        row: dict = {
            "beat": index,
            "bar": index // EIGHTHS_PER_BAR + 1,
            "pos": eighth + 1,
            "label": slot.label,
        }
        if slot.kind == "rest" or slot.close is None or slot.ma20 is None or slot.ratio is None:
            close_piano_run(None)
            row["event"] = slot.label
            score.append(row)
            continue

        piano_note = melody_midi(slot.close, lo, hi)
        bass_note = bass_midi(slot.ma20, lo, hi)
        if piano_run is not None and piano_run["note"] == piano_note:
            piano_run["end"] = index + 1
        else:
            close_piano_run(index)
            piano_run = {"note": piano_note, "start": index, "end": index + 1}

        played = bass_hits(eighth, slot.ratio)
        velocity = bass_velocity(slot.ratio)
        if played:
            bass.append((tick, 10, bytes([0x91, bass_note, velocity])))
            bass.append((tick + bass_ticks(slot.ratio), 0, bytes([0x81, bass_note, 0])))

        if prev_close is not None and prev_piano is not None:
            price_step = slot.close - prev_close
            note_step = piano_note - prev_piano
            if price_step != 0:
                compared += 1
                if note_step == 0:
                    flattened += 1
                elif (price_step > 0) == (note_step > 0):
                    agree += 1
                else:
                    wrong_way += 1

        prev_close = slot.close
        prev_piano = piano_note
        row.update(
            {
                "event": "note",
                "close": slot.close,
                "ma20": round(slot.ma20, 3),
                "ratio": round(slot.ratio, 2),
                "piano": note_name(piano_note),
                "piano_midi": piano_note,
                "bass": note_name(bass_note) if played else "—",
                "bass_midi": bass_note if played else None,
                "bass_vel": velocity if played else 0,
            }
        )
        score.append(row)

    close_piano_run(None)

    header = (
        b"MThd"
        + (6).to_bytes(4, "big")
        + (1).to_bytes(2, "big")
        + (2).to_bytes(2, "big")
        + PPQ.to_bytes(2, "big")
    )
    path.write_bytes(header + midi_track(piano) + midi_track(bass))
    return {
        "compared": compared,
        "agree": agree,
        "flattened": flattened,
        "wrong_way": wrong_way,
        "score": score,
    }


def synth_wav(path: Path, slots: list[Slot], lo: float, hi: float) -> None:
    sr = 44100
    eighth = 30 / BPM
    overlap = LEGATO_TICKS / PPQ * (60 / BPM)
    total = int(sr * (len(slots) * eighth + 1.5))
    mix = np.zeros(total, dtype=np.float64)

    def render(midi: int, start: float, dur: float, vel: int, kind: str) -> None:
        freq = 440.0 * 2 ** ((midi - 69) / 12)
        n = max(1, int(sr * dur))
        t = np.arange(n) / sr
        if kind == "violin":
            wave = (
                np.sin(2 * np.pi * freq * t)
                + 0.45 * np.sin(2 * np.pi * freq * 2 * t)
                + 0.28 * np.sin(2 * np.pi * freq * 3 * t)
                + 0.16 * np.sin(2 * np.pi * freq * 4 * t)
                + 0.08 * np.sin(2 * np.pi * freq * 5 * t)
            )
            env = np.ones(n)
            attack = min(n // 2, int(sr * 0.08))
            release = min(n - attack, int(sr * 0.09))
            if attack:
                env[:attack] = np.linspace(0, 1, attack)
            if release:
                env[-release:] *= np.linspace(1, 0, release)
        else:
            wave = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2 * t)
            env = np.exp(-2.4 * t)
            attack = min(n // 2, int(sr * 0.02))
            if attack:
                env[:attack] *= np.linspace(0, 1, attack)
        i0 = int(sr * start)
        i1 = min(total, i0 + n)
        if i1 <= i0:
            return
        mix[i0:i1] += (vel / 127) * 0.32 * env[: i1 - i0] * wave[: i1 - i0]

    run: dict | None = None

    def close_run(into_note: bool) -> None:
        nonlocal run
        if run is None:
            return
        dur = (run["end"] - run["start"]) * eighth
        if into_note:
            dur += overlap
        render(run["note"], run["start"] * eighth, dur, PIANO_VELOCITY, "violin")
        run = None

    for index, slot in enumerate(slots):
        if slot.kind != "bar" or slot.close is None or slot.ma20 is None or slot.ratio is None:
            close_run(False)
            continue
        piano_note = melody_midi(slot.close, lo, hi)
        if run is not None and run["note"] == piano_note:
            run["end"] = index + 1
        else:
            close_run(True)
            run = {"note": piano_note, "start": index, "end": index + 1}
        if bass_hits(index % EIGHTHS_PER_BAR, slot.ratio):
            bass_note = bass_midi(slot.ma20, lo, hi)
            dur = bass_ticks(slot.ratio) / PPQ * (60 / BPM)
            render(bass_note, index * eighth, dur, bass_velocity(slot.ratio), "bass")
    close_run(False)

    peak = np.max(np.abs(mix)) or 1.0
    pcm = np.clip(mix / peak * 0.9, -1, 1)
    samples = (pcm * 32767).astype(np.int16)
    import wave

    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(samples.tobytes())


def print_score(report: dict, bars: list[Bar]) -> None:
    closes = [bar.close for bar in bars]
    print(f"{SYMBOL} {SESSION_DAY}  {bars[0].label}-{bars[-1].label}  1-minute  eighths")
    print(
        f"close {closes[0]:.2f} -> {closes[-1]:.2f}  "
        f"low {min(closes):.2f}  high {max(closes):.2f}  "
        f"bars {len(bars)}  bpm {BPM}"
    )
    compared = report["compared"]
    print(
        f"piano vs price: {report['agree']}/{compared} same direction, "
        f"{report['flattened']} flattened, {report['wrong_way']} reversed"
    )
    print()
    previous = None
    for row in report["score"]:
        if row.get("event") != "note":
            if previous != row["label"]:
                print(f"{row['label']:5}  rest")
                previous = row["label"]
            continue
        if row["piano"] == previous:
            continue
        bass = row["bass"]
        print(
            f"{row['label']}  px {row['close']:6.2f}  {previous or '—':4} -> {row['piano']:4}"
            f"  bass {bass:4}  vol {row['ratio']:4.2f}x"
        )
        previous = row["piano"]


def _pitch_xml(midi: int) -> str:
    name = NOTE_NAMES[midi % 12]
    step = name[0]
    alter = "<alter>1</alter>" if name.endswith("#") else ""
    octave = midi // 12 - 1
    return f"<pitch><step>{step}</step>{alter}<octave>{octave}</octave></pitch>"


def _spell_eighths(count: int) -> list[tuple[int, str]]:
    """Break a run of eighth notes into whole, half, quarter, and eighth values."""
    pieces: list[tuple[int, str]] = []
    left = count
    for size, name in ((8, "whole"), (4, "half"), (2, "quarter"), (1, "eighth")):
        while left >= size:
            pieces.append((size, name))
            left -= size
    return pieces


def _tied_notes(midi: int | None, eighths: int, tie_stop: bool, tie_start: bool, velocity: int) -> str:
    pieces = _spell_eighths(eighths)
    chunks: list[str] = []
    for index, (size, name) in enumerate(pieces):
        stop = tie_stop or index > 0
        start = tie_start or index < len(pieces) - 1
        ties = ""
        notations = ""
        if midi is not None and (stop or start):
            tie_tags = ""
            tied_tags = ""
            if stop:
                tie_tags += '<tie type="stop"/>'
                tied_tags += '<tied type="stop"/>'
            if start:
                tie_tags += '<tie type="start"/>'
                tied_tags += '<tied type="start"/>'
            ties = tie_tags
            notations = f"<notations>{tied_tags}</notations>"
        head = "<rest/>" if midi is None else _pitch_xml(midi)
        sound = "" if midi is None else f'<sound dynamics="{velocity}"/>'
        chunks.append(
            "<note>"
            f"{head}<duration>{size}</duration><type>{name}</type>"
            f"{ties}{notations}{sound}"
            "</note>"
        )
    return "".join(chunks)


def _coverage(events: list[tuple[int, int, int | None, int]]) -> list[tuple[int, int, int | None, int]]:
    """Fill gaps between sounding events with rests. Events are start, end, midi, velocity."""
    covered: list[tuple[int, int, int | None, int]] = []
    cursor = 0
    for start, end, midi, velocity in events:
        if start > cursor:
            covered.append((cursor, start, None, 0))
        covered.append((start, end, midi, velocity))
        cursor = end
    return covered


def _piano_events(slots: list[Slot], lo: float, hi: float) -> list[tuple[int, int, int | None, int]]:
    events: list[tuple[int, int, int | None, int]] = []
    index = 0
    while index < len(slots):
        slot = slots[index]
        if slot.kind != "bar" or slot.close is None:
            nxt = index + 1
            while nxt < len(slots) and (slots[nxt].kind != "bar" or slots[nxt].close is None):
                nxt += 1
            events.append((index, nxt, None, 0))
            index = nxt
            continue
        note = melody_midi(slot.close, lo, hi)
        nxt = index + 1
        while nxt < len(slots) and slots[nxt].kind == "bar" and slots[nxt].close is not None:
            if melody_midi(slots[nxt].close, lo, hi) != note:
                break
            nxt += 1
        events.append((index, nxt, note, PIANO_VELOCITY))
        index = nxt
    return events


def _bass_events(slots: list[Slot], lo: float, hi: float) -> list[tuple[int, int, int | None, int]]:
    raw: list[tuple[int, int, int | None, int]] = []
    index = 0
    while index < len(slots):
        slot = slots[index]
        if (
            slot.kind != "bar"
            or slot.ma20 is None
            or slot.ratio is None
            or not bass_hits(index % EIGHTHS_PER_BAR, slot.ratio)
        ):
            index += 1
            continue
        length = 1 if slot.ratio >= DENSE_FROM else 2
        end = min(index + length, len(slots))
        for nxt in range(index + 1, end):
            later = slots[nxt]
            if later.kind != "bar" or later.ratio is None or bass_hits(nxt % EIGHTHS_PER_BAR, later.ratio):
                end = nxt
                break
        note = bass_midi(slot.ma20, lo, hi)
        raw.append((index, end, note, bass_velocity(slot.ratio)))
        index = end
    covered = _coverage(raw)
    if covered and covered[-1][1] < len(slots):
        covered.append((covered[-1][1], len(slots), None, 0))
    elif not covered:
        covered.append((0, len(slots), None, 0))
    return covered


def _part_xml(part_id: str, events: list[tuple[int, int, int | None, int]], total: int) -> str:
    padded = list(events)
    remainder = (EIGHTHS_PER_BAR - (total % EIGHTHS_PER_BAR)) % EIGHTHS_PER_BAR
    if remainder:
        padded.append((total, total + remainder, None, 0))
        total += remainder

    measures: list[list[str]] = []
    current: list[str] = []
    filled = 0
    for start, end, midi, velocity in padded:
        cursor = start
        length = end - start
        first = True
        while length:
            room = EIGHTHS_PER_BAR - (cursor % EIGHTHS_PER_BAR)
            take = min(length, room)
            continues = length > take
            current.append(
                _tied_notes(
                    midi,
                    take,
                    tie_stop=midi is not None and not first,
                    tie_start=midi is not None and continues,
                    velocity=velocity,
                )
            )
            filled += take
            cursor += take
            length -= take
            first = False
            if filled == EIGHTHS_PER_BAR:
                measures.append(current)
                current = []
                filled = 0
    if current:
        raise SystemExit(f"{part_id} ended inside a measure ({filled} eighths filled)")

    body: list[str] = []
    for number, notes in enumerate(measures, start=1):
        head = ""
        if number == 1:
            head = (
                "<attributes>"
                "<divisions>2</divisions>"
                "<key><fifths>0</fifths></key>"
                "<time><beats>4</beats><beat-type>4</beat-type></time>"
                f"<clef><sign>{'G' if part_id == 'P1' else 'F'}</sign>"
                f"<line>{2 if part_id == 'P1' else 4}</line></clef>"
                "</attributes>"
                '<direction placement="above">'
                "<direction-type><metronome>"
                "<beat-unit>quarter</beat-unit>"
                f"<per-minute>{BPM}</per-minute>"
                "</metronome></direction-type>"
                f'<sound tempo="{BPM}"/>'
                "</direction>"
            )
        body.append(f'<measure number="{number}">{head}{"".join(notes)}</measure>')
    return f'<part id="{part_id}">{"".join(body)}</part>'


def write_musicxml(path: Path, slots: list[Slot], lo: float, hi: float) -> None:
    piano = _part_xml("P1", _piano_events(slots, lo, hi), len(slots))
    bass = _part_xml("P2", _bass_events(slots, lo, hi), len(slots))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="4.0">'
        f"<work><work-title>{SYMBOL} {SESSION_DAY}</work-title></work>"
        "<identification>"
        '<creator type="composer">VStock</creator>'
        "<encoding><software>research/sonify/session_midi.py</software></encoding>"
        "</identification>"
        "<part-list>"
        '<score-part id="P1"><part-name>Violin</part-name>'
        '<score-instrument id="P1-I1"><instrument-name>Violin</instrument-name></score-instrument>'
        '<midi-instrument id="P1-I1"><midi-channel>1</midi-channel><midi-program>41</midi-program></midi-instrument>'
        "</score-part>"
        '<score-part id="P2"><part-name>Bass</part-name>'
        '<score-instrument id="P2-I1"><instrument-name>Finger Bass</instrument-name></score-instrument>'
        '<midi-instrument id="P2-I1"><midi-channel>2</midi-channel><midi-program>34</midi-program></midi-instrument>'
        "</score-part>"
        "</part-list>"
        f"{piano}{bass}"
        "</score-partwise>"
    )
    path.write_text(xml)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = fetch_payload()
    bars = bars_from_payload(payload)
    closes = [bar.close for bar in bars]
    lo, hi = min(closes), max(closes)
    slots = build_slots(bars)
    stem = OUT_DIR / f"{SYMBOL}_{SESSION_DAY}"
    report = write_midi(stem.with_suffix(".mid"), slots, lo, hi)
    synth_wav(stem.with_suffix(".wav"), slots, lo, hi)
    write_musicxml(stem.with_suffix(".musicxml"), slots, lo, hi)
    (stem.with_suffix(".json")).write_text(
        json.dumps(
            {
                "symbol": SYMBOL,
                "day": SESSION_DAY,
                "bpm": BPM,
                "resolution": RESOLUTION,
                "scale": "C major",
                "bass_drop": BASS_DROP,
                "price_low": lo,
                "price_high": hi,
                "bars": [
                    {
                        "t": bar.label,
                        "close": bar.close,
                        "volume": bar.volume,
                        "ma20": round(bar.ma20, 4),
                    }
                    for bar in bars
                ],
            },
            indent=2,
        )
    )
    print_score(report, bars)
    seconds = len(slots) * 30 / BPM
    print(
        f"\n{seconds:.0f}s  {stem.with_suffix('.mid')}  "
        f"{stem.with_suffix('.wav')}  {stem.with_suffix('.musicxml')}"
    )


if __name__ == "__main__":
    main()
