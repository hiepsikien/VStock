#!/usr/bin/env python3
"""Four slow bars of the Preludio, in the three singing voices plus bass.

Each cell is eight sixteenths. Nothing is tied. Every attack is plucked again.

- High, counts 1 and 7. Count 1 lasts six sixteenths; count 7 lasts two.
- Lower middle, voice 2, counts 2, 4, 6, and 8. Counts 2, 6, and 8 are one
  chord tone. Count 4 is two scale steps higher. Each lasts two sixteenths.
- Upper middle, voice 4, counts 3 and 5, the same chord tone. Count 3 lasts
  two sixteenths. Count 5 lasts until the next count 3. Where that reach
  crosses a barline, the remainder is a new note, not a tie.

Velocities stay in 40–70 and move a little around the centers:
high about 60, lower middle about 50, bass about 45, upper middle about 40.

    python backend/scripts/hear_cathedral_voice.py

Writes MusicXML and WAV under backend/scripts/out/.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.sonify.chords import C, G
from app.sonify.form import ChordSlot
from app.sonify.keys import D_KEY
from app.sonify.model import NoteEvent, Score
from app.sonify.musicxml import score_to_musicxml

OUT = Path(__file__).resolve().parent / "out"
BPM = 48
BARS = 5

# Sounding MIDI. Note events are stored in C space; D_KEY sounds them a step higher.
A3 = 57
CS4 = 61
D4 = 62
E4 = 64
FS4 = 66
A4 = 69
B4 = 71
CS5 = 73
D5 = 74
E5 = 76
FS5 = 78
D3 = 50
A2 = 45
D_CHORD = frozenset({2, 6, 9})
A_CHORD = frozenset({9, 1, 4})
D_SCALE = frozenset({1, 2, 4, 6, 7, 9, 11})


@dataclass(frozen=True)
class Cell:
    canto_a: int
    canto_b: int
    low2: int
    low4: int
    low6: int
    low8: int
    up3: int
    up5: int


# Two cells per bar. Inside a cell, 2 = 6 = 8 and 3 = 5. Count 4 is two
# scale steps higher, and that step is still a chord tone under the upper voice.
# Bars 0, 1, 3 are D. Bar 2 is A. Sounding pitches, before the D-key shift.
CELLS = (
    Cell(FS5, E5, D4, FS4, D4, D4, A4, A4),
    Cell(D5, CS5, D4, FS4, D4, D4, A4, A4),
    Cell(FS5, E5, D4, FS4, D4, D4, A4, A4),
    Cell(D5, CS5, D4, FS4, D4, D4, A4, A4),
    Cell(E5, B4, A3, CS4, A3, A3, E4, E4),
    Cell(E5, D5, A3, CS4, A3, A3, E4, E4),
    Cell(FS5, E5, D4, FS4, D4, D4, A4, A4),
    Cell(FS5, E5, D4, FS4, D4, D4, A4, A4),
)
BASS_NOTES = (D3, D3, A2, D3, D3)


def _clamp(velocity: int) -> int:
    return max(40, min(70, velocity))


def _high_velocity(index: int, slot: int) -> int:
    arch = (2, 0, 0, -2, 2, 0, 6, 4)[index]
    inner = (4, -4)[slot]
    return _clamp(60 + arch + inner)


def _lower_velocity(index: int, slot: int) -> int:
    arch = (-2, -4, 0, 2, 0, -2, 4, 2)[index]
    inner = (2, -4, 4, -2)[slot]
    return _clamp(50 + arch + inner)


def _upper_velocity(index: int, slot: int) -> int:
    arch = (0, 0, 2, 0, 2, 0, 4, 2)[index]
    inner = (2, 0)[slot]
    return _clamp(40 + arch + inner)


def _stored(midi: int | None) -> int | None:
    if midi is None:
        return None
    return midi - D_KEY.semitones


def _note(
    bar: int,
    beat: float,
    midi: int | None,
    duration: float,
    voice: int,
    velocity: int | None,
) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=round(beat, 2),
        midi=_stored(midi),
        duration_beats=duration,
        voice=voice,
        velocity=velocity,
    )


def _lead() -> list[NoteEvent]:
    events: list[NoteEvent] = []
    for index, cell in enumerate(CELLS):
        bar = index // 2
        origin = 0.0 if index % 2 == 0 else 2.0
        events.append(_note(bar, origin, cell.canto_a, 1.5, 1, _high_velocity(index, 0)))
        events.append(_note(bar, origin + 1.5, cell.canto_b, 0.5, 1, _high_velocity(index, 1)))
    events.append(_note(4, 0.0, CELLS[-1].canto_a, 4.0, 1, _high_velocity(7, 0)))
    return events


def _lower() -> list[NoteEvent]:
    """Counts 2, 4, 6, and 8. Each is two sixteenths, and none is tied."""
    events: list[NoteEvent] = []
    for index, cell in enumerate(CELLS):
        bar = index // 2
        origin = 0.0 if index % 2 == 0 else 2.0
        prev = CELLS[index - 1] if index else None
        pitches = (cell.low2, cell.low4, cell.low6, cell.low8)
        if prev is None:
            events.append(_note(bar, origin, None, 0.25, 2, None))
        elif index % 2 == 0:
            events.append(_note(bar, origin, prev.low8, 0.25, 2, _lower_velocity(index - 1, 3)))
        for slot, beat in enumerate((0.25, 0.75, 1.25)):
            events.append(
                _note(bar, origin + beat, pitches[slot], 0.5, 2, _lower_velocity(index, slot))
            )
        if index % 2 == 0:
            events.append(_note(bar, origin + 1.75, cell.low8, 0.5, 2, _lower_velocity(index, 3)))
        else:
            events.append(_note(bar, origin + 1.75, cell.low8, 0.25, 2, _lower_velocity(index, 3)))
    events.append(_note(4, 0.0, CELLS[-1].low8, 4.0, 2, _lower_velocity(7, 3)))
    return events


def _upper() -> list[NoteEvent]:
    events: list[NoteEvent] = []
    for index, cell in enumerate(CELLS):
        bar = index // 2
        origin = 0.0 if index % 2 == 0 else 2.0
        prev = CELLS[index - 1] if index else None
        if prev is None:
            events.append(_note(bar, origin, None, 0.50, 4, None))
        elif index % 2 == 0:
            events.append(_note(bar, origin, prev.up5, 0.50, 4, _upper_velocity(index - 1, 1)))
        events.append(_note(bar, origin + 0.50, cell.up3, 0.50, 4, _upper_velocity(index, 0)))
        if index + 1 < len(CELLS) and index % 2 == 0:
            events.append(_note(bar, origin + 1.00, cell.up5, 1.50, 4, _upper_velocity(index, 1)))
        else:
            events.append(_note(bar, origin + 1.00, cell.up5, 1.00, 4, _upper_velocity(index, 1)))
    events.append(_note(4, 0.0, CELLS[-1].up5, 4.0, 4, _upper_velocity(7, 1)))
    return events


def _bass() -> list[NoteEvent]:
    velocities = (46, 44, 48, 46, 42)
    return [_note(bar, 0.0, BASS_NOTES[bar], 4.0, 3, velocities[bar]) for bar in range(BARS)]


def _span(events: list[NoteEvent], voice: int) -> None:
    for bar in range(BARS):
        ordered = sorted(
            (event for event in events if event.bar == bar and event.voice == voice),
            key=lambda event: event.beat,
        )
        total = 0.0
        previous: float | None = None
        for event in ordered:
            if previous is not None and abs(event.beat - previous) < 1e-9 and event.midi is not None:
                continue
            total += event.duration_beats
            previous = event.beat
        if abs(total - 4.0) > 1e-6:
            raise SystemExit(f"voice {voice} bar {bar} lasts {total} beats, not 4")


def _steps_above(origin: int, target: int) -> int | None:
    if target <= origin:
        return None
    steps = 0
    note = origin
    while note < target:
        note += 1
        if note % 12 in D_SCALE:
            steps += 1
            if note == target:
                return steps
    return None


def _check_cells() -> None:
    for index, cell in enumerate(CELLS):
        chord = A_CHORD if index in {4, 5} else D_CHORD
        bass = BASS_NOTES[index // 2]
        ceiling = min(cell.canto_a, cell.canto_b)
        if index + 1 < len(CELLS):
            ceiling = min(ceiling, CELLS[index + 1].canto_a)
        if cell.low2 != cell.low6 or cell.low2 != cell.low8 or cell.up3 != cell.up5:
            raise SystemExit(f"cell {index} does not hold 2=6=8 and 3=5")
        lifted = _steps_above(cell.low2, cell.low4)
        if lifted not in {1, 2}:
            raise SystemExit(f"cell {index} lifts count 4 by {lifted} steps")
        if lifted == 2 and cell.low4 % 12 not in chord:
            raise SystemExit(f"cell {index} lifts count 4 off the chord")
        if not bass < cell.low2 < cell.low4 < cell.up3 < ceiling:
            raise SystemExit(f"cell {index} does not stack under {ceiling}")
        if cell.low2 % 12 not in chord or cell.up3 % 12 not in chord:
            raise SystemExit(f"cell {index} leaves the chord")
        if cell.canto_a % 12 not in chord or cell.canto_b % 12 not in D_SCALE:
            raise SystemExit(f"cell {index} high voice leaves the scale")
    if CELLS[-1].low8 % 12 not in D_CHORD or CELLS[-1].up5 % 12 not in D_CHORD:
        raise SystemExit("the final chord leaves D")


def _score() -> Score:
    _check_cells()
    lead = _lead()
    lower = _lower()
    upper = _upper()
    low = _bass()
    for voice, events in ((1, lead), (2, lower), (4, upper), (3, low)):
        _span(events, voice)
    return Score(
        title="Cathedral voice sketch",
        bpm=BPM,
        bars=BARS,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(
            ChordSlot(0, 2, C, "sideway", "phrase"),
            ChordSlot(2, 1, G, "sideway", "phrase"),
            ChordSlot(3, 2, C, "sideway", "phrase"),
        ),
        high=(),
        lead=tuple(lead),
        support=tuple(lower) + tuple(upper),
        comp=(),
        low=tuple(low),
        key=D_KEY,
        dynamics=(),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="barrios",
        divisions=4,
        beats=4,
        beat_type=4,
        bar_beats=4.0,
    )


def _export(xml_path: Path, wav_path: Path) -> str:
    from app.sonify.audio import find_musescore, musescore_export

    if find_musescore() is None:
        raise RuntimeError("MuseScore is not installed")
    musescore_export(xml_path, wav_path)
    return "MuseScore nylon"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    xml_path = OUT / "cathedral-voice-sketch.musicxml"
    wav_path = OUT / "cathedral-voice-sketch.wav"
    xml_path.write_text(score_to_musicxml(_score()), encoding="utf-8")
    if "tie" in xml_path.read_text(encoding="utf-8"):
        raise SystemExit(f"{xml_path} still contains a tie")
    try:
        engine = _export(xml_path, wav_path)
    except Exception as exc:
        raise SystemExit(f"could not render {xml_path}: {exc}") from exc
    print(engine)
    print(xml_path)
    print(wav_path)
    print("Không có tie. Trong mỗi khung, 2 = 6 = 8 và 3 = 5. Nốt 4 cao hơn hai bậc.")
    print("Giọng Rê. Ô 1, 2, 4 là hợp âm Rê. Ô 3 là hợp âm La.")


if __name__ == "__main__":
    main()
