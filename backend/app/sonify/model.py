"""Values that flow from a price series to a score."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.sonify.chords import Chord, Regime
from app.sonify.form import ChordSlot
from app.sonify.keys import C_KEY, KeySpec

PERIOD = 4

Variant = Literal["symphony", "jazz", "minimalist", "ambient"]
VARIANTS: tuple[Variant, ...] = ("symphony", "jazz", "minimalist", "ambient")

StreamVariant = Literal["symphony", "jazz", "minimalist", "ambient"]
STREAM_VARIANTS: tuple[StreamVariant, ...] = ("symphony", "jazz", "minimalist", "ambient")


@dataclass(frozen=True)
class Bar:
    close: float
    volume: float = 0.0
    ma20: float | None = None
    auction: bool = False


@dataclass(frozen=True)
class Run:
    """Consecutive eighths on one pitch."""

    start: int
    length: int
    midi: int

    @property
    def end(self) -> int:
        return self.start + self.length


@dataclass(frozen=True)
class Phrase:
    start: int
    end: int
    runs: tuple[Run, ...]
    # The last note goes on sounding into the next phrase of the same section.
    held_over: bool = False

    @property
    def apex(self) -> Run:
        """The first run on the highest pitch: the phrase's local price high."""
        return max(self.runs, key=lambda run: (run.midi, -run.start))

    @property
    def cadence(self) -> Run:
        return self.runs[-1]

    @property
    def closes(self) -> bool:
        return self.cadence.length >= PERIOD and not self.held_over

    @property
    def rise(self) -> int:
        """Semitones from the lowest note in the phrase up to its apex."""
        return self.apex.midi - min(run.midi for run in self.runs)


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
    staccato: bool = False


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
    """A rendered 30-bar score across five role-neutral parts (P5 high, P1 lead, P2 support, P3 comp, P4 low).

    Primary fields use role-neutral names (`high`, `lead`, `support`, `comp`, `low`,
    `lead_wedges`, `support_wedges`, `lead_dynamics`, `support_dynamics`), while classic
    chamber names (`flute`, `violin`, `cello`, `piano`, `bass`, `violin_wedges`,
    `cello_wedges`, `violin_dynamics`, `cello_dynamics`) are preserved as read-only properties.
    """

    title: str
    bpm: int
    bars: int
    regimes: tuple[Regime, Regime, Regime]
    regime_samples: tuple[int, int, int] | None  # None when regimes were passed in
    slots: tuple[ChordSlot, ...]
    high: tuple[NoteEvent, ...]
    lead: tuple[NoteEvent, ...]
    support: tuple[NoteEvent, ...]
    comp: tuple[NoteEvent, ...]
    low: tuple[NoteEvent, ...]
    dynamics: tuple[DynamicEvent, ...]
    harmonies: tuple[HarmonyEvent, ...]
    liquidity: tuple[str, ...]  # p–f band per chord slot; sets how busy the bass is
    phrases: tuple[Phrase, ...]
    lead_wedges: tuple[WedgeEvent, ...]
    support_wedges: tuple[WedgeEvent, ...]
    lead_dynamics: tuple[DynamicEvent, ...]
    support_dynamics: tuple[DynamicEvent, ...]
    variant: Variant = "symphony"
    divisions: int = 2
    swing: bool = False
    key: KeySpec = C_KEY

    # Backwards-compatible chamber part aliases
    @property
    def flute(self) -> tuple[NoteEvent, ...]:
        return self.high

    @property
    def violin(self) -> tuple[NoteEvent, ...]:
        return self.lead

    @property
    def cello(self) -> tuple[NoteEvent, ...]:
        return self.support

    @property
    def piano(self) -> tuple[NoteEvent, ...]:
        return self.comp

    @property
    def bass(self) -> tuple[NoteEvent, ...]:
        return self.low

    @property
    def violin_wedges(self) -> tuple[WedgeEvent, ...]:
        return self.lead_wedges

    @property
    def cello_wedges(self) -> tuple[WedgeEvent, ...]:
        return self.support_wedges

    @property
    def violin_dynamics(self) -> tuple[DynamicEvent, ...]:
        return self.lead_dynamics

    @property
    def cello_dynamics(self) -> tuple[DynamicEvent, ...]:
        return self.support_dynamics
