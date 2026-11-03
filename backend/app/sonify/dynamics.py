"""Letter dynamics from p to f, as MusicXML 4.0 spells them.

MusicXML prints a dynamic as an empty child of <dynamics>. Liquidity uses the
four middle names p, mp, mf, f. The cool-down diminuendo ends at ppp, which is
not a volume step. fff is unused.

Playback is a sibling <sound dynamics="N"/> element. N is a percentage of
MusicXML's default forte, which is MIDI velocity 90. The percentages below
are chosen so round(N / 100 * 90) is the velocity in the third column.
"""

from __future__ import annotations

from dataclasses import replace
from math import floor, log1p

from app.sonify.groove import groove_at
from app.sonify.model import Score
from app.sonify.params import active

# marking, sound-dynamics percent, intended MIDI velocity
DYNAMICS: tuple[tuple[str, int, int], ...] = (
    ("p", 54, 49),
    ("mp", 71, 64),
    ("mf", 89, 80),
    ("f", 107, 96),
)

MARKINGS: tuple[str, ...] = tuple(row[0] for row in DYNAMICS)
SOUND: dict[str, int] = {marking: percent for marking, percent, _velocity in DYNAMICS}
# Cool-down arrival. 22% of forte is velocity 20, under p at 49.
COOLDOWN_MARKING = "ppp"
SOUND[COOLDOWN_MARKING] = 22

# Marking -> intended MIDI velocity at the default dynamics. Everything is
# derived from this table so `<sound dynamics>` and `<note velocity>` cannot
# drift apart.
BASE_VELOCITY: dict[str, int] = {
    marking: velocity for marking, _percent, velocity in DYNAMICS
}
BASE_VELOCITY[COOLDOWN_MARKING] = 20
PIANO_BASE: dict[str, int] = {"p": 46, "mp": 54, "mf": 62, "f": 68}
FILL_BASE = 64
_CENTER = 64


def contrast_velocity(base: int) -> int:
    """Apply the dynamics contrast to a written velocity, ceiling, or floor."""
    scaled = floor(_CENTER + (base - _CENTER) * active("dynamics") + 0.5)
    return max(1, min(127, scaled))


def apply_contrast(score: Score) -> Score:
    """Stretch every written note velocity around the mp pivot.

    Called once after the writer and the daily/span frame. At the default
    factor this returns the same score object, so Default stays byte-identical.
    """
    if active("dynamics") == 1.0:
        return score
    fields: dict[str, tuple] = {}
    for name in ("high", "lead", "support", "comp", "low"):
        notes = getattr(score, name)
        # `pinned` is final for humanize, not for this pass: this is the
        # dynamics layer itself, and humanize keeps the scaled value after us.
        fields[name] = tuple(
            note if note.velocity is None else replace(note, velocity=contrast_velocity(note.velocity))
            for note in notes
        )
    return replace(score, **fields)


GUITAR_VOICE_FIELDS: tuple[tuple[str, str], ...] = (
    ("lead", "guitar_high"),
    ("support", "guitar_mid"),
    ("low", "guitar_bass"),
)


def apply_voice_balance(score: Score) -> Score:
    """Offset the three guitar streams after humanize, before MusicXML.

    Guitar is one nylon part and MS Basic plays the note velocity, so the
    balance is a velocity offset, not a mixer fader. The knob is a MIDI
    velocity delta in [-8, +8]. This pass must stay after compute_dfi:
    `_volume()` reads event velocity. At 0 it returns the same score object,
    so Default stays byte-identical.
    """
    if score.variant != "guitar":
        return score
    offsets = {name: active(key) for name, key in GUITAR_VOICE_FIELDS}
    if all(offset == 0.0 for offset in offsets.values()):
        return score
    fields: dict[str, tuple] = {}
    for name, offset in offsets.items():
        notes = getattr(score, name)
        fields[name] = tuple(
            note
            if note.velocity is None
            else replace(
                note,
                # The schema step is 1, so `offset` is always integer-valued.
                velocity=max(1, min(127, int(note.velocity + offset))),
            )
            for note in notes
        )
    return replace(score, **fields)


def velocity_for(marking: str) -> int:
    """Velocity after the dynamics knob. At 1.0 this is the old table."""
    return contrast_velocity(BASE_VELOCITY.get(marking, _CENTER))


def sound_for(marking: str) -> int:
    """Playback percent derived from the velocity, not a second table."""
    return int(round(velocity_for(marking) / 90 * 100))


def piano_velocity_for(marking: str) -> int:
    return contrast_velocity(PIANO_BASE.get(marking, 64))


def piano_base(marking: str) -> int:
    """The written piano velocity before the score-wide contrast pass."""
    return PIANO_BASE.get(marking, 64)


def fill_velocity() -> int:
    return contrast_velocity(FILL_BASE)


def fill_base() -> int:
    return FILL_BASE

# The bass sits under the melody. Its busiest band still drives eighth notes,
# but the printed and played loudness stops at this letter.
BASS_CEILING = "mp"

# p90 must be at least this many times p10 before the piece leaves mf.
# A 7% gap (150k against 160k) stays put; a real doubling opens the scale.
MIN_SPAN_RATIO = 2.0
# A single print many times a normal minute — the opening and closing
# auctions, or an unlabeled spike — is clipped to this multiple of the
# median before the slot average is taken.
CLIP_MULTIPLE = 4.0


def marking_for_volume(volume: float, low: float, high: float) -> str:
    """Map one slot's average volume onto p–f.

    low and high are the 10th and 90th percentile of the traded slots only:
    an untraded slot is p and must not drag low to zero, or the log scale
    anchors at log1p(0) and every traded slot lands near f. A session with no
    volume at all is missing data, not a quiet tape, so it stays mf. With a
    gap smaller than MIN_SPAN_RATIO, every traded slot is mf.
    """
    if high <= 0:
        return "mf"
    if volume <= 0:
        return MARKINGS[0]
    if low <= 0 or high / low < MIN_SPAN_RATIO:
        return "mf"
    floor = log1p(low)
    ceiling = log1p(high)
    norm = (log1p(volume) - floor) / (ceiling - floor)
    norm = min(1.0, max(0.0, norm))
    index = min(len(MARKINGS) - 1, int(norm * len(MARKINGS)))
    return MARKINGS[index]


def bass_marking(band: str) -> str:
    return MARKINGS[min(MARKINGS.index(band), MARKINGS.index(BASS_CEILING))]


# MuseScore Basic hears these velocities on the piano. Muse Sounds hears the
# printed letter, which piano_marking collapses to p or mp.
PIANO_VELOCITY: dict[str, int] = {"p": 46, "mp": 54, "mf": 62, "f": 68}


def effective_comp_band(band: str, bar: int | None = None) -> str:
    """The piano bed after the groove flags that thin the comp, not the bass rhythm."""
    groove = groove_at(bar) if bar is not None else None
    if groove is not None and groove.chamber:
        return "p"
    if groove is not None and groove.trio_thin:
        return {"f": "mf", "mf": "mp", "mp": "p", "p": "p"}[band]
    if groove is not None and groove.half and band == "mp":
        return "p"
    return band


def piano_marking(band: str) -> str:
    """Printed piano letter. mf and f share mp; p and mp share p."""
    if band in ("mf", "f"):
        return "mp"
    return "p"


def positive_median(volumes: list[float]) -> float:
    positive = sorted(volume for volume in volumes if volume > 0)
    if not positive:
        return 0.0
    mid = len(positive) // 2
    if len(positive) % 2:
        return positive[mid]
    return (positive[mid - 1] + positive[mid]) / 2


def average_liquidity(groups: list[list[float]]) -> list[float]:
    """Mean volume per candle, after clipping spikes to CLIP_MULTIPLE × median.

    An empty group (a slot whose candles were all auction prints) takes the
    median of the other slots, so it does not become the loudest bar in the piece.
    """
    positive = [volume for group in groups for volume in group if volume > 0]
    ceiling = positive_median(positive) * CLIP_MULTIPLE
    raw: list[float | None] = []
    for group in groups:
        if not group:
            raw.append(None)
            continue
        kept = [min(volume, ceiling) if ceiling > 0 else volume for volume in group]
        raw.append(sum(kept) / len(kept))
    known = [level for level in raw if level is not None]
    fallback = positive_median(known) if known else 0.0
    return [fallback if level is None else level for level in raw]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    low_index = int(rank)
    high_index = min(low_index + 1, len(ordered) - 1)
    weight = rank - low_index
    return ordered[low_index] * (1 - weight) + ordered[high_index] * weight
