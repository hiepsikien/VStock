"""Three open-ended orchestrations for one closed 250 ms bucket.

Symphony, jazz, and minimalist share the tape. They differ in which voices
sound, not in the clock. Nothing here reads a later bucket.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.sonify.chords import Chord, jazz_chord
from app.sonify.model import Variant
from app.sonify.phrasing import comp_pitches
from app.sonify.quantize import C_MAJOR_PCS, SCALE_HIGH, SCALE_LOW

BUCKET_MS = 250
BEAT_NOTES = 4
BAR_NOTES = 16
HIGH_TRIGGER = 79  # G5
HIGH_BUDGET = 0.15
SAX_LOW = 48
SAX_CEILING = 80
SAX_LEAP = 9
CLOSED_CUTOFF = 0.35
OPEN_CUTOFF = 0.70
BASS_RANGE = tuple(note for note in range(36, 49) if note % 12 in C_MAJOR_PCS)


@dataclass(frozen=True)
class Voice:
    role: str
    midi: int
    dur_ms: int
    velocity: int
    wave: str

    def payload(self) -> dict[str, object]:
        return {
            "role": self.role,
            "midi": self.midi,
            "dur_ms": self.dur_ms,
            "velocity": self.velocity,
            "wave": self.wave,
        }


class HighBudget:
    """At most 15% of the recent window may carry a high accent."""

    def __init__(self, window: int = 240) -> None:
        self._flags: deque[int] = deque(maxlen=window)

    def take(self, want: bool) -> bool:
        ratio = (sum(self._flags) / len(self._flags)) if self._flags else 0.0
        granted = bool(want) and ratio < HIGH_BUDGET
        self._flags.append(1 if granted else 0)
        return granted


def sounding_chord(variant: Variant, chord: Chord) -> Chord:
    if variant == "jazz":
        return jazz_chord(chord)
    return chord


def place_sax(midi: int, previous: int | None) -> int:
    """Keep the line inside the sax register and avoid a leap over a ninth."""
    while midi > SAX_CEILING:
        midi -= 12
    while midi < SAX_LOW:
        midi += 12
    if previous is None:
        return midi
    while midi - previous > SAX_LEAP and midi - 12 >= SAX_LOW:
        midi -= 12
    while previous - midi > SAX_LEAP and midi + 12 <= SAX_CEILING:
        midi += 12
    return midi


def approach_note(beat3: int, next_root: int, fifth: int) -> int:
    """One diatonic step from the next root, aimed toward the note just played."""
    if next_root not in BASS_RANGE:
        return fifth
    index = BASS_RANGE.index(next_root)
    above = BASS_RANGE[min(len(BASS_RANGE) - 1, index + 1)]
    below = BASS_RANGE[max(0, index - 1)]
    chosen = above if abs(above - beat3) <= abs(below - beat3) else below
    if chosen == next_root:
        return fifth
    return chosen


def _voice(role: str, midi: int, sixteenths: int, velocity: int, wave: str) -> Voice:
    return Voice(role, midi, sixteenths * BUCKET_MS, max(1, min(127, velocity)), wave)


def _brightness(midi: int) -> float:
    span = max(1, SCALE_HIGH - SCALE_LOW)
    return min(1.0, max(0.0, (midi - SCALE_LOW) / span))


def _accent_pitch(midi: int, low: int, high: int, chord: Chord) -> int:
    """Nearest note that already sits in [low, high].

    A window narrower than an octave does not contain every pitch class.
    Transposing until the note fits then walks off the top and back forever.
    """
    if high < low:
        raise ValueError("register is empty")
    tones = [note for note in range(low, high + 1) if note % 12 in chord.pitch_classes]
    pool = tones or list(range(low, high + 1))
    return min(pool, key=lambda note: (abs(note - midi), note))


def _chord_tone_below(chord: Chord, midi: int) -> int:
    tones = [
        note
        for note in range(SCALE_LOW, SCALE_HIGH + 1)
        if note % 12 in chord.pitch_classes and note < midi
    ]
    if not tones:
        return chord.bass_midi
    return max(tones)


def _upper(chord: Chord, low: int, high: int, skip_root: bool = True) -> list[int]:
    pcs = [pitch % 12 for pitch in chord.pitches]
    if skip_root and len(pcs) > 1:
        pcs = pcs[1:]
    tones: list[int] = []
    for pc in pcs[:3]:
        tone = low + (pc - (low % 12)) % 12
        if low <= tone <= high and tone not in tones:
            tones.append(tone)
    return tones


def _arp_midi(chord: Chord, step: int, brightness: float) -> int:
    ladder = [midi for midi in range(48, 85) if midi % 12 in chord.pitch_classes]
    if not ladder:
        return chord.bass_midi
    offsets = (0, 1, 2, 1, 0, 2, 1, 2)
    max_base = max(0, len(ladder) - 3)
    base = round(brightness * max_base)
    offset = offsets[step % 8]
    if brightness < CLOSED_CUTOFF:
        offset %= 2
    return ladder[min(len(ladder) - 1, base + offset)]


def _bass_pattern(band: str) -> tuple[tuple[int, int, int], ...]:
    """(sixteenth in the bar, length in sixteenths, interval above the root)."""
    if band == "p":
        return ((0, 16, 0),)
    if band == "mp":
        return ((0, 8, 0), (8, 8, 7))
    if band == "mf":
        return ((0, 4, 0), (4, 4, 7), (8, 4, 12), (12, 4, 7))
    return tuple((index * 2, 2, interval) for index, interval in enumerate((0, 0, 12, 0, 7, 7, 12, 7)))


def arrange(
    variant: Variant,
    *,
    seq: int,
    midi: int,
    velocity: int,
    chord: Chord,
    next_chord: Chord,
    band: str,
    prev_sax: int | None,
    allow_high: bool,
    price_held: bool,
) -> tuple[tuple[Voice, ...], int | None]:
    """Voices for this bucket, and the sax pitch to remember (jazz only)."""
    pos = seq % BAR_NOTES
    beat = pos // BEAT_NOTES
    chord = sounding_chord(variant, chord)
    next_chord = sounding_chord(variant, next_chord)
    voices: list[Voice] = []
    sax: int | None = None

    if variant == "symphony":
        voices.append(_voice("violin", midi, 1, velocity, "triangle"))
        if pos % BEAT_NOTES == 0:
            voices.append(_voice("cello", _chord_tone_below(chord, midi), 4, 64, "sine"))
        if pos == 0:
            _root, guide = comp_pitches(chord)
            for tone in guide:
                voices.append(_voice("piano", tone, 8, 58, "triangle"))
        if price_held and pos not in (0,):
            fill = _upper(chord, 60, 76)
            if fill:
                voices.append(_voice("fill", fill[0], 1, 70, "triangle"))
        for start, length, interval in _bass_pattern(band):
            if pos == start:
                voices.append(_voice("bass", chord.bass_midi + interval, length, 72, "sine"))
        if allow_high:
            voices.append(_voice("flute", _accent_pitch(midi, 79, 88, chord), 2, 64, "sine"))

    elif variant == "jazz":
        sax = place_sax(midi, prev_sax)
        voices.append(_voice("sax", sax, 1, velocity, "sawtooth"))
        if pos == 0:
            for tone in _upper(chord, 58, 76):
                voices.append(_voice("rhodes", tone, 6, 62, "triangle"))
        if pos == 6:
            stab = _upper(chord, 58, 76)
            if stab:
                voices.append(_voice("rhodes", stab[-1], 2, 70, "triangle"))
        if allow_high:
            voices.append(_voice("vibe", _accent_pitch(midi, 84, 89, chord), 2, 60, "sine"))
        voices.extend(_jazz_bass(seq, pos, beat, band, chord, next_chord))

    else:
        bright = _brightness(midi)
        arp = _arp_midi(chord, seq, bright)
        if bright < CLOSED_CUTOFF:
            arp_len, arp_vel = 1, 48
        elif bright >= OPEN_CUTOFF:
            arp_len, arp_vel = 2, 90
        else:
            arp_len, arp_vel = 1, round(48 + bright * 42)
        voices.append(_voice("arp", arp, arp_len, arp_vel, "square"))
        if pos == 0:
            for tone in _upper(chord, 60, 76) or [chord.bass_midi + 12]:
                voices.append(_voice("pad", tone, 16, 40, "triangle"))
        voices.extend(_pulse(pos, beat, band, chord))
        if pos % BEAT_NOTES == 0:
            root = chord.bass_midi + (12 if band == "f" and beat == 3 else 0)
            voices.append(_voice("bass", root, 4, 78, "sine"))
        if allow_high:
            voices.append(_voice("bell", _accent_pitch(midi, 84, 96, chord), 2, 64, "sine"))

    return tuple(voices), sax


def wants_high(variant: Variant, midi: int) -> bool:
    if variant == "minimalist":
        return _brightness(midi) >= OPEN_CUTOFF
    return midi >= HIGH_TRIGGER


def _jazz_bass(
    seq: int,
    pos: int,
    beat: int,
    band: str,
    chord: Chord,
    next_chord: Chord,
) -> list[Voice]:
    root = chord.bass_midi
    fifth = root + 7
    if band == "p":
        if pos == 0:
            return [_voice("bass", root, 8, 70, "sine")]
        if pos == 8:
            return [_voice("bass", fifth, 8, 70, "sine")]
        return []
    if pos % BEAT_NOTES != 0:
        return []
    if beat == 0:
        midi = root
    elif beat == 1:
        third_pc = chord.pitches[1] % 12
        midi = root + ((third_pc - (root % 12)) % 12)
        if (seq // BAR_NOTES) % 2:
            midi = fifth
    elif beat == 2:
        midi = root + 12 if band == "f" else fifth
    else:
        midi = approach_note(fifth if band != "f" else root + 12, next_chord.bass_midi, fifth)
    return [_voice("bass", midi, 4, 74, "sine")]


def _pulse(pos: int, beat: int, band: str, chord: Chord) -> list[Voice]:
    root_pc = chord.pitches[0] % 12
    fifth_pc = chord.pitches[2] % 12
    hi_root = 72 + root_pc
    hi_fifth = 72 + fifth_pc
    if hi_fifth > 84:
        hi_fifth -= 12
    voices: list[Voice] = []
    if band == "p" and pos in (0, 8):
        voices.append(_voice("pulse", hi_root, 1, 49, "square"))
    elif band == "mp" and pos % BEAT_NOTES == 0:
        tone = hi_root if beat % 2 == 0 else hi_fifth
        voices.append(_voice("pulse", tone, 1, 64, "square"))
    elif band == "mf" and pos % 2 == 0:
        off = pos % 4 == 2
        voices.append(_voice("pulse", hi_fifth if off else hi_root, 1, 76 if off else 64, "square"))
    elif band == "f":
        cycle = (hi_root, hi_fifth, hi_root + 12 if hi_root + 12 <= 88 else hi_root, hi_fifth)
        accent = pos % 4 == 2
        voices.append(_voice("pulse", cycle[pos % 4], 1, 88 if accent else 80, "square"))
    if band in ("mf", "f") and beat in (1, 3) and pos % BEAT_NOTES == 0:
        stab = 48 + fifth_pc
        if stab > 55:
            stab -= 12
        voices.append(_voice("stab", stab, 1, 84, "square"))
    return voices
