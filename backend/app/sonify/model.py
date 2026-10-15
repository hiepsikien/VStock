"""Values that flow from a price series to a score."""

from __future__ import annotations

from dataclasses import dataclass

from app.sonify.chords import Chord, Regime
from app.sonify.form import ChordSlot
from app.sonify.phrasing import Phrase


@dataclass(frozen=True)
class Bar:
    close: float
    volume: float = 0.0
    ma20: float | None = None
    auction: bool = False


@dataclass(frozen=True)
class NoteEvent:
    """A sounding note, or a rest when midi is None."""

    bar: int
    beat: float
    midi: int | None
    duration_beats: float
    voice: int
    staff: int = 1
    tie_start: bool = False
    tie_stop: bool = False
    slur_start: bool = False
    slur_stop: bool = False
    accent: bool = False
    velocity: int | None = None
    tenuto: bool = False
    tremolo: bool = False


@dataclass(frozen=True)
class WedgeEvent:
    """A hairpin edge. A stop on beat 4.0 closes at the end of the bar."""

    bar: int
    beat: float
    kind: str  # "crescendo" | "diminuendo" | "stop"


@dataclass(frozen=True)
class DynamicEvent:
    bar: int
    marking: str
    sound: int
    beat: float = 0.0


@dataclass(frozen=True)
class HarmonyEvent:
    bar: int
    chord: Chord


@dataclass(frozen=True)
class Score:
    title: str
    bpm: int
    bars: int
    regimes: tuple[Regime, Regime, Regime]
    regime_samples: tuple[int, int, int] | None  # None when regimes were passed in
    slots: tuple[ChordSlot, ...]
    violin: tuple[NoteEvent, ...]
    cello: tuple[NoteEvent, ...]
    piano: tuple[NoteEvent, ...]
    bass: tuple[NoteEvent, ...]
    dynamics: tuple[DynamicEvent, ...]
    harmonies: tuple[HarmonyEvent, ...]
    liquidity: tuple[str, ...]  # p–f band per chord slot; sets how busy the bass is
    phrases: tuple[Phrase, ...]
    violin_wedges: tuple[WedgeEvent, ...]
    cello_wedges: tuple[WedgeEvent, ...]
    violin_dynamics: tuple[DynamicEvent, ...]
    cello_dynamics: tuple[DynamicEvent, ...]
