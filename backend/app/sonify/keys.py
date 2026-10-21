"""Five concert keys within ±3 semitones of C, and the movement plan that picks them.

Scores stay in C. MusicXML adds `KeySpec.semitones` once, and spells the sounding
pitch from `KeySpec.fifths`. Register ceilings drop and floors rise before the
notes are written, so the sounding line still sits inside the C sweet spot.
"""

from __future__ import annotations

import zlib
from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal

from app.sonify.chords import Chord, Regime, tonic
from app.sonify.regime import classify_window

MovementCharacter = Literal["rally", "selloff", "volatile", "calm"]
OutroOverride = Literal["major", "minor"]

_LETTERS = "CDEFGAB"
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
_REGIME_BARS = 5

# Unshifted sweet spot. These match the constants in phrasing.py, render.py, and jazz.py.
_FLUTE_CEILING = 88
_VIOLIN_CEILING = 84
_VIOLIN_LOWEST = 55
_CELLO_HANDBACK = 60
_SAX_CEILING = 80


@dataclass(frozen=True)
class KeySpec:
    name: str
    label: str
    fifths: int
    semitones: int
    tonic_step: str
    tonic_alter: int


@dataclass(frozen=True)
class Register:
    """C-space bounds. Positive shifts lower the ceiling; negative shifts raise the floor."""

    flute_ceiling: int = _FLUTE_CEILING
    violin_ceiling: int = _VIOLIN_CEILING
    violin_lowest: int = _VIOLIN_LOWEST
    cello_handback: int = _CELLO_HANDBACK
    sax_ceiling: int = _SAX_CEILING


EB_KEY = KeySpec("Eb", "Mi♭", -3, 3, "E", -1)
BB_KEY = KeySpec("Bb", "Si♭", -2, -2, "B", -1)
C_KEY = KeySpec("C", "Đô", 0, 0, "C", 0)
D_KEY = KeySpec("D", "Rê", 2, 2, "D", 0)
A_KEY = KeySpec("A", "La", 3, -3, "A", 0)
KEY_RING: tuple[KeySpec, ...] = (EB_KEY, BB_KEY, C_KEY, D_KEY, A_KEY)
C_REGISTER = Register()

_REGISTER: ContextVar[Register] = ContextVar("sonify_register", default=C_REGISTER)

_HOME: dict[str, KeySpec] = {}
for _symbol in ("VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "STB", "HDB", "TPB"):
    _HOME[_symbol] = BB_KEY
for _symbol in ("FPT", "MWG", "DGW", "FRT", "PNJ", "CTR", "CMG"):
    _HOME[_symbol] = D_KEY
for _symbol in ("HPG", "HSG", "NKG", "VIC", "VHM", "VRE", "NVL", "KDH", "SSI", "VND", "HCM", "VCI"):
    _HOME[_symbol] = EB_KEY
for _symbol in ("VNM", "MSN", "SAB", "GAS", "POW", "REE", "PLX", "BVH"):
    _HOME[_symbol] = C_KEY
for _symbol in ("GMD", "HAH", "DGC", "DPM", "DCM", "VHC", "ANV", "PTB"):
    _HOME[_symbol] = A_KEY

_SPAN_THRESHOLD: dict[str, tuple[float, float]] = {
    "1W": (0.020, 0.035),
    "1M": (0.020, 0.035),
    "3M": (0.040, 0.065),
    "1Y": (0.040, 0.065),
}


def active_register() -> Register:
    return _REGISTER.get()


@contextmanager
def compose_register(key: KeySpec):
    """Lower ceilings and raise floors for the duration of one `render` call."""
    token = _REGISTER.set(register_for(key))
    try:
        yield
    finally:
        _REGISTER.reset(token)


def register_for(key: KeySpec) -> Register:
    up = max(0, key.semitones)
    down = max(0, -key.semitones)
    return Register(
        flute_ceiling=_FLUTE_CEILING - up,
        violin_ceiling=_VIOLIN_CEILING - up,
        violin_lowest=_VIOLIN_LOWEST + down,
        cello_handback=_CELLO_HANDBACK + down,
        sax_ceiling=_SAX_CEILING - up,
    )


def stock_home_key(symbol: str) -> KeySpec:
    """One stable key per ticker. Unknown tickers use crc32, not Python's salted hash."""
    code = symbol.strip().upper()
    mapped = _HOME.get(code)
    if mapped is not None:
        return mapped
    index = zlib.crc32(code.encode("utf-8")) % len(KEY_RING)
    return KEY_RING[index]


def movement_character(closes: Sequence[float], span: str) -> MovementCharacter:
    """Classify one movement. `1D` never calls this; it stays on the untouched bias table."""
    trend, vol_th = _SPAN_THRESHOLD[span]
    if len(closes) < 2 or closes[0] == 0 or min(closes) <= 0:
        return "calm"
    return_pct = (closes[-1] - closes[0]) / closes[0]
    volatility = (max(closes) - min(closes)) / min(closes)
    if return_pct >= trend:
        return "rally"
    if return_pct <= -trend:
        return "selloff"
    if volatility >= vol_th:
        return "volatile"
    return "calm"


def boundary_regimes(
    closes: Sequence[float], mas: Sequence[float | None]
) -> tuple[Regime, Regime]:
    """Opening and closing regime of a movement, for the volatile tie-break."""
    window = _REGIME_BARS
    return (
        classify_window(list(closes[:window]), list(mas[:window])),
        classify_window(list(closes[-window:]), list(mas[-window:])),
    )


def finale_outro(
    opening: MovementCharacter, finale: MovementCharacter
) -> OutroOverride | None:
    if opening == "selloff" and finale == "rally":
        return "major"
    if opening == "rally" and finale == "selloff":
        return "minor"
    return None


def month_keys(
    home: KeySpec,
    characters: Sequence[MovementCharacter],
    edges: Sequence[tuple[Regime, Regime]],
) -> tuple[KeySpec, ...]:
    """Sonata: I at home, II by character, III the other neighbor, IV home."""
    if len(characters) != 4 or len(edges) != 4:
        raise ValueError("a month sonata needs four movements")
    home_index = _index(home)
    second = _chapter_two(home_index, characters[1], edges[0][1], edges[1][0])
    third = _chapter_three(home_index, second)
    return (home, KEY_RING[second], KEY_RING[third], home)


def quarter_keys(
    home: KeySpec,
    characters: Sequence[MovementCharacter],
    edges: Sequence[tuple[Regime, Regime]],
) -> tuple[KeySpec, ...]:
    """Concerto: I at home, II by the same rule as the sonata, III home."""
    if len(characters) != 3 or len(edges) != 3:
        raise ValueError("a quarter needs three movements")
    home_index = _index(home)
    second = _chapter_two(home_index, characters[1], edges[0][1], edges[1][0])
    return (home, KEY_RING[second], home)


def year_key(
    home: KeySpec,
    season: int,
    character: MovementCharacter,
    *,
    frame: bool,
) -> KeySpec:
    """Calendar season around the home key. The first movement, the last, Q1, and Q4 stay home.

    Q2 and Q3 may step one ring index when the month is a rally or a selloff.
    Q1 and Q4 do not, so the year still opens and closes on the home key.
    """
    if frame or season in (0, 3):
        return home
    base = _season_base(_index(home), season)
    if character == "selloff" and base > 0:
        base -= 1
    elif character == "rally" and base < 4:
        base += 1
    return KEY_RING[base]


def transpose_chord(chord: Chord, key: KeySpec) -> Chord:
    """Shift a C-space chord and spell it in thirds from the destination root."""
    if key.semitones == 0 and key.fifths == 0:
        return chord
    pitches = tuple(pitch + key.semitones for pitch in chord.pitches)
    diatonic = _diatonic(key)
    root_step, root_alter = _spell_root(pitches[0] % 12, key, diatonic)
    root_letter = _LETTERS.index(root_step)
    tones: list[tuple[int, str, int]] = []
    for index, pitch in enumerate(pitches):
        pc = pitch % 12
        step = _LETTERS[(root_letter + index * 2) % 7]
        alter = _alter_for(step, pc)
        if diatonic.get(pc) != (step, alter):
            tones.append((pc, step, alter))
    return Chord(
        chord.name,
        root_step,
        chord.kind,
        chord.kind_text,
        pitches,
        alter=root_alter,
        tones=tuple(tones),
    )


def midi_to_spelled_pitch(
    midi: int, key: KeySpec, harmony: Chord | None = None
) -> tuple[str, int, int]:
    """Step, alter, octave for a sounding MIDI note already shifted into `key`."""
    from app.sonify.musicxml import midi_to_pitch

    if key.fifths == 0 and key.semitones == 0:
        return midi_to_pitch(midi, harmony)
    pitch_class = midi % 12
    octave = midi // 12 - 1
    if harmony is not None:
        spelled = transpose_chord(harmony, key).spelling(pitch_class)
        if spelled is not None:
            step, alter = spelled
            return step, alter, octave
    diatonic = _diatonic(key)
    if pitch_class in diatonic:
        step, alter = diatonic[pitch_class]
        return step, alter, octave
    step, alter = _spell_root(pitch_class, key, diatonic)
    return step, alter, octave


def _index(key: KeySpec) -> int:
    return KEY_RING.index(key)


def _triad(regime: Regime) -> frozenset[int]:
    return frozenset(pitch % 12 for pitch in tonic(regime).pitches[:3])


def _common(previous: Regime, previous_key: KeySpec, nxt: Regime, next_key: KeySpec) -> int:
    before = {(pc + previous_key.semitones) % 12 for pc in _triad(previous)}
    after = {(pc + next_key.semitones) % 12 for pc in _triad(nxt)}
    return len(before & after)


def _chapter_two(
    home: int, character: MovementCharacter, previous_end: Regime, opening: Regime
) -> int:
    if home == 0:
        return 1
    if home == 4:
        return 3
    left = home - 1
    right = home + 1
    if character in ("selloff", "calm"):
        return left
    if character == "rally":
        return right
    home_key = KEY_RING[home]
    left_count = _common(previous_end, home_key, opening, KEY_RING[left])
    right_count = _common(previous_end, home_key, opening, KEY_RING[right])
    if right_count > left_count:
        return right
    return left


def _chapter_three(home: int, second: int) -> int:
    if home in (0, 4):
        return 2
    left = home - 1
    right = home + 1
    return right if second == left else left


def _season_base(home: int, season: int) -> int:
    if season == 1:
        if home == 0:
            return 1
        if home == 4:
            return 3
        return home + 1
    if season == 2:
        if home in (0, 4):
            return 2
        return home - 1
    return home


def _diatonic(key: KeySpec) -> dict[int, tuple[str, int]]:
    tonic_pc = key.semitones % 12
    letter = _LETTERS.index(key.tonic_step)
    spellings: dict[int, tuple[str, int]] = {}
    for degree, interval in enumerate(_MAJOR_STEPS):
        step = _LETTERS[(letter + degree) % 7]
        spellings[(tonic_pc + interval) % 12] = (step, _alter_for(step, (tonic_pc + interval) % 12))
    return spellings


def _alter_for(step: str, pitch_class: int) -> int:
    alter = (pitch_class - _NATURAL[step]) % 12
    if alter > 6:
        alter -= 12
    return alter


def _spell_root(
    pitch_class: int, key: KeySpec, diatonic: dict[int, tuple[str, int]]
) -> tuple[str, int]:
    spelled = diatonic.get(pitch_class)
    if spelled is not None:
        return spelled
    candidates = [
        (step, alter)
        for step in _LETTERS
        if -2 <= (alter := _alter_for(step, pitch_class)) <= 2
    ]
    if key.fifths < 0:
        return min(candidates, key=lambda item: item[1])
    if key.fifths > 0:
        return max(candidates, key=lambda item: item[1])
    return min(candidates, key=lambda item: (abs(item[1]), item[0]))
