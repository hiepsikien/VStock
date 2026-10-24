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
Mode = Literal["major", "minor"]

_LETTERS = "CDEFGAB"
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
_MINOR_STEPS = (0, 2, 3, 5, 7, 8, 10)
_REGIME_BARS = 5

# Unshifted sweet spot. phrasing.py, render.py, jazz.py, and voices.py read these.
_FLUTE_CEILING = 88
_VIOLIN_CEILING = 84
_VIOLIN_LOWEST = 55
_CELLO_HANDBACK = 60
_SAX_CEILING = 80
_VIBRAPHONE_HIGH = 89  # F6
_SYNTH_LOW = 48  # C3
_SYNTH_HIGH = 84  # C6


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
    vibraphone_high: int = _VIBRAPHONE_HIGH
    synth_low: int = _SYNTH_LOW
    synth_high: int = _SYNTH_HIGH
    fill_high: int = 79  # G5, the classic fill top
    support_floor: int = 48  # C3, the classic cello-pedal bottom
    lead_floor: int = 0  # raised only when a lead voice sits above violin_lowest
    # Written pitches in C-space. Sounding guitar limits shift both ways with the key.
    guitar_floor: int = 40
    guitar_bass_top: int = 53
    guitar_mid_low: int = 50
    guitar_mid_high: int = 65
    guitar_treble_floor: int = 59
    guitar_treble_top: int = 81
    guitar_ceiling: int = 83


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

# 1D uses the close-to-close return first, then the session range. HOSE days are
# narrow: 0.45% separates a rally or a selloff, and a 1.35% high–low is volatile.
# The old 1.2% / 2.8% pair left ordinary 0.5–1% sessions in `calm`.
_SPAN_THRESHOLD: dict[str, tuple[float, float]] = {
    "1D": (0.0045, 0.0135),
    "1W": (0.020, 0.035),
    "1M": (0.020, 0.035),
    "3M": (0.040, 0.065),
    "1Y": (0.040, 0.065),
}

CHARACTER_LABEL = {
    "rally": "Tăng giá",
    "selloff": "Bán tháo",
    "volatile": "Giằng co",
    "calm": "Tích lũy",
}


def active_register() -> Register:
    return _REGISTER.get()


@contextmanager
def compose_register(key: KeySpec, register: Register | None = None):
    """Lower ceilings and raise floors for the duration of one `render` call."""
    token = _REGISTER.set(register if register is not None else register_for(key))
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
        vibraphone_high=_VIBRAPHONE_HIGH - up,
        synth_low=_SYNTH_LOW - key.semitones,
        synth_high=_SYNTH_HIGH - key.semitones,
        guitar_floor=40 - key.semitones,
        guitar_bass_top=53 - key.semitones,
        guitar_mid_low=50 - key.semitones,
        guitar_mid_high=65 - key.semitones,
        guitar_treble_floor=59 - key.semitones,
        guitar_treble_top=81 - key.semitones,
        guitar_ceiling=83 - key.semitones,
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
    """Classify one movement or one session. Trend is tested before the range."""
    trend, vol_th = _SPAN_THRESHOLD[span]
    if len(closes) < 2 or closes[0] == 0 or min(closes) <= 0:
        return "calm"
    low = min(closes)
    high = max(closes)
    return_pct = (closes[-1] - closes[0]) / closes[0]
    volatility = (high - low) / low
    if return_pct >= trend:
        return "rally"
    if return_pct <= -trend:
        return "selloff"
    if span == "1D" and volatility >= 0.010 and high > low:
        close_pos = (closes[-1] - low) / (high - low)
        if close_pos >= 0.72:
            return "rally"
        if close_pos <= 0.28:
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


def movement_mode(character: MovementCharacter, closing: Regime) -> Mode:
    """Parallel major or minor. Volatile flips only when the movement closes down."""
    if character == "selloff":
        return "minor"
    if character == "volatile" and closing == "downtrend":
        return "minor"
    return "major"


def signature_fifths(key: KeySpec, mode: Mode) -> int:
    """Parallel natural minor adds three flats. The sounding shift stays on `semitones`."""
    if mode == "minor":
        return key.fifths - 3
    return key.fifths


def key_label(key: KeySpec, mode: Mode = "major") -> str:
    """The tonic name. Parallel minor keeps that tonic and says so."""
    if mode == "minor":
        return f"{key.label} thứ"
    return key.label


def spelling_key(key: KeySpec, mode: Mode) -> KeySpec:
    if mode == "major":
        return key
    return KeySpec(
        key.name,
        key.label,
        signature_fifths(key, mode),
        key.semitones,
        key.tonic_step,
        key.tonic_alter,
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


def jazz_month_keys(
    home: KeySpec,
    characters: Sequence[MovementCharacter],
    edges: Sequence[tuple[Regime, Regime]],
) -> tuple[KeySpec, ...]:
    """One set. Head, ballad, and finale stay home. Only the short tune steps once."""
    if len(characters) != 4 or len(edges) != 4:
        raise ValueError("a month sonata needs four movements")
    step = _chapter_two(_index(home), characters[2], edges[1][1], edges[2][0])
    return (home, home, KEY_RING[step], home)


def jazz_quarter_keys(
    home: KeySpec,
    characters: Sequence[MovementCharacter],
    edges: Sequence[tuple[Regime, Regime]],
) -> tuple[KeySpec, ...]:
    """Three tunes, all at home. There is no short tune to step away on."""
    if len(characters) != 3 or len(edges) != 3:
        raise ValueError("a quarter needs three movements")
    return (home, home, home)


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


def transpose_chord(chord: Chord, key: KeySpec, mode: Mode = "major") -> Chord:
    """Shift a C-space chord and spell it in thirds from the destination root."""
    if key.semitones == 0 and key.fifths == 0:
        return chord
    pitches = tuple(pitch + key.semitones for pitch in chord.pitches)
    diatonic = _diatonic(key, mode)
    root_step, root_alter = _spell_chord_root(pitches, key, diatonic)
    root_letter = _LETTERS.index(root_step)
    tones: list[tuple[int, str, int]] = []
    for index, pitch in enumerate(pitches):
        pc = pitch % 12
        span = chord.degrees[index] if chord.degrees else index * 2
        step = _LETTERS[(root_letter + span) % 7]
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
        degrees=chord.degrees,
    )


def midi_to_spelled_pitch(
    midi: int, key: KeySpec, harmony: Chord | None = None, mode: Mode = "major"
) -> tuple[str, int, int]:
    """Step, alter, octave for a sounding MIDI note already shifted into `key`."""
    from app.sonify.musicxml import midi_to_pitch

    spell = spelling_key(key, mode)
    if spell.fifths == 0 and spell.semitones == 0 and mode == "major":
        return midi_to_pitch(midi, harmony)
    pitch_class = midi % 12
    if harmony is not None:
        spelled = transpose_chord(harmony, spell, mode).spelling(pitch_class)
        if spelled is not None:
            step, alter = spelled
            return step, alter, _octave(midi, step, alter)
    diatonic = _diatonic(spell, mode)
    if pitch_class in diatonic:
        step, alter = diatonic[pitch_class]
        return step, alter, _octave(midi, step, alter)
    step, alter = _spell_root(pitch_class, key, diatonic)
    return step, alter, _octave(midi, step, alter)


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


def _diatonic(key: KeySpec, mode: Mode = "major") -> dict[int, tuple[str, int]]:
    tonic_pc = key.semitones % 12
    letter = _LETTERS.index(key.tonic_step)
    steps = _MINOR_STEPS if mode == "minor" else _MAJOR_STEPS
    spellings: dict[int, tuple[str, int]] = {}
    for degree, interval in enumerate(steps):
        step = _LETTERS[(letter + degree) % 7]
        spellings[(tonic_pc + interval) % 12] = (step, _alter_for(step, (tonic_pc + interval) % 12))
    return spellings


def _octave(midi: int, step: str, alter: int) -> int:
    """MusicXML octave of a letter, so C♭ and B♯ stay on the sounding MIDI note."""
    return (midi - _NATURAL[step] - alter) // 12 - 1


def _alter_for(step: str, pitch_class: int) -> int:
    alter = (pitch_class - _NATURAL[step]) % 12
    if alter > 6:
        alter -= 12
    return alter


def _spell_chord_root(
    pitches: tuple[int, ...], key: KeySpec, diatonic: dict[int, tuple[str, int]]
) -> tuple[str, int]:
    """Pick a root whose stacked thirds stay inside single accidentals."""
    pitch_class = pitches[0] % 12
    candidates = [
        (step, alter)
        for step in _LETTERS
        if -2 <= (alter := _alter_for(step, pitch_class)) <= 2
    ]

    def preference(item: tuple[str, int]) -> tuple[int, int, int, int, str]:
        step, alter = item
        worst = abs(alter)
        letter = _LETTERS.index(step)
        for index, pitch in enumerate(pitches):
            tone = _LETTERS[(letter + index * 2) % 7]
            worst = max(worst, abs(_alter_for(tone, pitch % 12)))
        if key.fifths < 0:
            direction = alter
        elif key.fifths > 0:
            direction = -alter
        else:
            direction = 0
        diatonic_penalty = 0 if diatonic.get(pitch_class) == item else 1
        # Both stacks are single accidentals: follow the key before the
        # smaller accidental, so Ab in Eb is C♭–E♭–G♭ rather than B–D♯–F♯.
        return (worst, diatonic_penalty, direction, abs(alter), step)

    return min(candidates, key=preference)


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

    def preference(item: tuple[str, int]) -> tuple[int, int, str]:
        step, alter = item
        # The smaller accidental wins. A tie follows the key: flats take the
        # flatter spelling, sharps the sharper one.
        if key.fifths < 0:
            direction = alter
        elif key.fifths > 0:
            direction = -alter
        else:
            direction = 0
        return (abs(alter), direction, step)

    return min(candidates, key=preference)
