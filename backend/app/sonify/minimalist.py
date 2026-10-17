"""Minimalist / Ambient Techno variant for non-music-savvy traders and Flow State.

Maps market data onto three direct auditory dimensions:
1. Sub-Bass (P4): Four-on-the-floor quarter-note pulse on the MA20 regime chord root.
2. Synth Arpeggio (P1) & Warm Pad (P2) & High Bell (P5): Repetitive 4-note ostinato
   whose register, voicing spread, articulation (staccato -> tenuto), and velocity
   open and close like a cutoff frequency filter as price rises and falls.
   High Bell (P5) only chimes on high breakouts / peaks (~10-15% of the piece).
3. Synth Pulse / Percussion (P3): Rhythmic density driven by liquidity (volume),
   stepping from sparse half-note pulses (p), to quarter pulse (mp), off-beat eighths (mf),
   and driving 16th-note patterns with backbeat accents on beats 2 and 4 (f).
"""

from __future__ import annotations

from app.sonify.chords import Chord, Regime
from app.sonify.dynamics import SOUND
from app.sonify.form import (
    BEATS_PER_BAR,
    EIGHTHS_PER_BAR,
    MUSICAL_BARS,
    ChordSlot,
)
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score, WedgeEvent
from app.sonify.phrasing import PERIOD, Phrase
from app.sonify.quantize import SCALE_HIGH, SCALE_LOW, c_major_scale
from app.sonify.render import (
    BREAKOUT,
    MIN_RISE,
    TOTAL_EIGHTHS,
    _hairpins,
    _lift,
    _with_rests,
    _written,
    techniques,
)

MINIMALIST_BPM = 118
MINIMALIST_DIVISIONS = 4  # 16th-note resolution (4 divisions per quarter beat)

# Filter / Brightness register bands (mapped from normalized price in [0.0, 1.0])
CLOSED_CUTOFF = 0.35   # Low price -> dark register (C3-B3), staccato, soft
OPEN_CUTOFF = 0.70     # High price -> bright register (C5-C6), tenuto, bright

ARP_VEL_LOW = 48
ARP_VEL_HIGH = 90
BELL_VELOCITY = 64
BELL_MAX_EIGHTHS = 36
PAD_VELOCITY = 52
PULSE_VEL_BY_BAND = {
    "p": 49,
    "mp": 64,
    "mf": 76,
    "f": 88,
}


def _normalized_brightness(midi: int) -> float:
    """Normalize a raw melody MIDI pitch in [SCALE_LOW, SCALE_HIGH] to [0.0, 1.0]."""
    span = max(1, SCALE_HIGH - SCALE_LOW)
    return min(1.0, max(0.0, (midi - SCALE_LOW) / span))


def _arp_chord_ladder(chord: Chord) -> list[int]:
    """All chord tones across C3 (48) to C6 (84) in ascending order."""
    pcs = chord.pitch_classes
    return [midi for midi in range(48, 85) if midi % 12 in pcs]


def _synth_arpeggio_part(
    raw_pitches: list[int],
    phrases: tuple[Phrase, ...],
    chord_at: dict[int, Chord],
) -> tuple[tuple[NoteEvent, ...], tuple[WedgeEvent, ...], tuple[DynamicEvent, ...]]:
    """Build the repetitive Synth Arpeggio (P1) with cutoff-filter brightness modulation.

    Every eighth note steps through a 4-note ostinato pattern (0, 1, 2, 1) anchored at
    a chord-tone window whose center pitch and spread follow the normalized price.
    When price rises, the arpeggio opens into higher octaves with higher velocity;
    when price drops, it closes into the low register with muted staccato articulation.
    """
    notes: list[NoteEvent] = []
    wedges: list[WedgeEvent] = []
    dynamics: list[DynamicEvent] = []
    ostinato_offsets = (0, 1, 2, 1, 0, 2, 1, 2)

    for bar in range(MUSICAL_BARS):
        chord = chord_at[bar]
        ladder = _arp_chord_ladder(chord)
        max_base = max(0, len(ladder) - 3)
        for eighth_in_bar in range(EIGHTHS_PER_BAR):
            eighth = bar * EIGHTHS_PER_BAR + eighth_in_bar
            raw_midi = raw_pitches[eighth]
            norm = _normalized_brightness(raw_midi)
            base_idx = round(norm * max_base)
            # In dark/closed state (< CLOSED_CUTOFF), narrow the pattern to 2 tones (0, 1)
            if norm < CLOSED_CUTOFF:
                step_offset = ostinato_offsets[eighth_in_bar] % 2
            else:
                step_offset = ostinato_offsets[eighth_in_bar]
            tone_idx = min(len(ladder) - 1, base_idx + step_offset)
            arp_midi = ladder[tone_idx]
            vel = round(ARP_VEL_LOW + norm * (ARP_VEL_HIGH - ARP_VEL_LOW))
            is_closed = norm < CLOSED_CUTOFF
            is_open = norm >= OPEN_CUTOFF
            is_downbeat = eighth_in_bar in (0, 4)
            notes.append(
                NoteEvent(
                    bar=bar,
                    beat=eighth_in_bar * 0.5,
                    midi=arp_midi,
                    duration_beats=0.5,
                    voice=1,
                    staccato=is_closed,
                    tenuto=is_open and is_downbeat,
                    accent=is_open and eighth_in_bar == 0,
                    velocity=vel,
                )
            )

    # Filter sweep hairpins across phrases that have meaningful price movement
    drift = 0
    for phrase in phrases:
        if _lift(phrase) <= 0.0:
            continue
        if drift != 0:
            dynamics.append(
                DynamicEvent(
                    bar=phrase.start // EIGHTHS_PER_BAR,
                    marking="mp",
                    sound=SOUND["mp"],
                    beat=(phrase.start % EIGHTHS_PER_BAR) * 0.5,
                )
            )
            drift = 0
        phrase_wedges = _hairpins(phrase.start, phrase.end, phrase.apex.start)
        wedges.extend(phrase_wedges)
        for wedge in phrase_wedges:
            drift += {"crescendo": 1, "diminuendo": -1}.get(wedge.kind, 0)

    return tuple(notes), tuple(wedges), tuple(dynamics)


def _synth_bell_part(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
) -> tuple[NoteEvent, ...]:
    """High Synth Bell (P5): sparse accent layer (<= 15%, <= 36 eighths) on Breakouts and high peaks."""
    bell_events: list[NoteEvent] = []
    occupied_bars: set[int] = set()
    total_eighths = 0
    scale = c_major_scale(84, 91)  # C6 to G6 high bell register

    for phrase in phrases:
        colours = techniques(phrase, pitches, band_at)
        apex = phrase.apex
        candidates = [
            run
            for run in phrase.runs
            if colours.get(run.start) == BREAKOUT
            or (phrase.rise >= MIN_RISE and run.start == apex.start and run.midi >= 79)
        ]
        for run in candidates[:1]:
            bar = run.start // EIGHTHS_PER_BAR
            if bar in occupied_bars:
                continue
            length = min(max(2, run.length), PERIOD)
            end = min((bar + 1) * EIGHTHS_PER_BAR, run.start + length)
            span_len = end - run.start
            if span_len <= 0:
                continue
            if total_eighths + span_len > BELL_MAX_EIGHTHS:
                remain = BELL_MAX_EIGHTHS - total_eighths
                if remain < 2:
                    continue
                span_len = remain
                end = run.start + span_len
            occupied_bars.add(bar)
            total_eighths += span_len
            chord = chord_at[bar]
            high_tones = [m for m in scale if m % 12 in chord.pitch_classes]
            pool = high_tones if high_tones else list(scale)
            norm = min(1.0, max(0.0, (run.midi - 79) / (96 - 79)))
            target = 84 + norm * (91 - 84)
            bell_midi = min(pool, key=lambda m: (abs(m - target), m))
            bell_events.extend(
                _written(
                    run.start,
                    span_len,
                    bell_midi,
                    velocity=BELL_VELOCITY,
                    tenuto=True,
                )
            )
            if total_eighths >= BELL_MAX_EIGHTHS:
                break

    return _with_rests(bell_events, TOTAL_EIGHTHS)


def _warm_pad_part(slots: tuple[ChordSlot, ...]) -> tuple[NoteEvent, ...]:
    """Warm Synth Pad (P2): sustained low-mid chord foundation tracking the MA20 regime."""
    events: list[NoteEvent] = []
    for slot in slots:
        pcs = tuple(p % 12 for p in slot.chord.pitches)
        root_pc = pcs[0]
        third_pc = pcs[1]
        root_midi = 48 + root_pc  # C3-B3
        if root_midi > 57:
            root_midi -= 12
        third_midi = root_midi + ((third_pc - root_pc) % 12)
        for bar in slot.bars():
            events.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=root_midi,
                    duration_beats=float(BEATS_PER_BAR),
                    voice=1,
                    velocity=PAD_VELOCITY,
                )
            )
            events.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=third_midi,
                    duration_beats=float(BEATS_PER_BAR),
                    voice=1,
                    velocity=PAD_VELOCITY,
                )
            )
    return tuple(events)


def _synth_pulse_part(
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
) -> tuple[NoteEvent, ...]:
    """Rhythmic Pulse / Electronic Percussion (P3): volume controls rhythmic density.

    Staff 1 (upper hi-hat / synth pulse):
    - 'p':  half-note pulse (2 hits/bar)
    - 'mp': quarter-note pulse (4 hits/bar)
    - 'mf': eighth-note pulse with off-beat accents (8 hits/bar)
    - 'f':  16th-note driving techno pattern (16 hits/bar)

    Staff 2 (lower backbeat clap / synth stab on beats 2 and 4):
    - Rests on 'p' and 'mp'; active on 'mf' and 'f' on beats 2 and 4.
    """
    events: list[NoteEvent] = []
    for bar in range(MUSICAL_BARS):
        band = band_at[bar]
        chord = chord_at[bar]
        vel = PULSE_VEL_BY_BAND[band]
        root_pc = chord.pitches[0] % 12
        fifth_pc = chord.pitches[2] % 12
        hi_root = 72 + root_pc   # C5-B5
        hi_fifth = 72 + fifth_pc
        if hi_fifth > 84:
            hi_fifth -= 12

        # Staff 1: Rhythmic density
        if band == "p":
            for beat in (0.0, 2.0):
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=hi_root,
                        duration_beats=2.0,
                        voice=1,
                        staff=1,
                        staccato=True,
                        velocity=vel,
                    )
                )
        elif band == "mp":
            for step in range(4):
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=float(step),
                        midi=hi_root if step % 2 == 0 else hi_fifth,
                        duration_beats=1.0,
                        voice=1,
                        staff=1,
                        staccato=True,
                        velocity=vel,
                    )
                )
        elif band == "mf":
            for eighth in range(8):
                off_beat = eighth % 2 == 1
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=eighth * 0.5,
                        midi=hi_fifth if off_beat else hi_root,
                        duration_beats=0.5,
                        voice=1,
                        staff=1,
                        staccato=True,
                        accent=off_beat,
                        velocity=vel if off_beat else vel - 12,
                    )
                )
        else:  # band == "f": 16th-note techno burst
            cycle = (hi_root, hi_fifth, hi_root + 12 if hi_root + 12 <= 88 else hi_root, hi_fifth)
            for sixteenth in range(16):
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=sixteenth * 0.25,
                        midi=cycle[sixteenth % 4],
                        duration_beats=0.25,
                        voice=1,
                        staff=1,
                        staccato=True,
                        accent=sixteenth % 4 == 2,
                        velocity=vel if sixteenth % 4 == 2 else vel - 8,
                    )
                )

        # Staff 2: Backbeat on beats 2 and 4 when volume is mf or f
        low_stab = 48 + fifth_pc
        if low_stab > 55:
            low_stab -= 12
        if band in ("mf", "f"):
            for beat, is_hit in ((0.0, False), (1.0, True), (2.0, False), (3.0, True)):
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=low_stab if is_hit else None,
                        duration_beats=1.0,
                        voice=5,
                        staff=2,
                        staccato=is_hit,
                        accent=is_hit and band == "f",
                        velocity=vel if is_hit else None,
                    )
                )
        else:
            events.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=None,
                    duration_beats=float(BEATS_PER_BAR),
                    voice=5,
                    staff=2,
                )
            )
    return tuple(events)


def _sub_bass_part(
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
) -> tuple[NoteEvent, ...]:
    """Four-on-the-floor Sub-Bass (P4): steady quarter-note kick/bass pulse on every beat."""
    events: list[NoteEvent] = []
    for bar in range(MUSICAL_BARS):
        chord = chord_at[bar]
        band = band_at[bar]
        root = chord.bass_midi
        for beat in range(BEATS_PER_BAR):
            # On high-volume bars ('f'), beat 4 lifts an octave for pumping drive
            midi = root + 12 if (band == "f" and beat == 3) else root
            events.append(
                NoteEvent(
                    bar=bar,
                    beat=float(beat),
                    midi=midi,
                    duration_beats=1.0,
                    voice=1,
                    tenuto=beat == 0,
                )
            )
    return tuple(events)


def render_minimalist_score(
    *,
    title: str,
    chosen: tuple[Regime, Regime, Regime],
    sample_indexes: tuple[int, int, int] | None,
    slots: tuple[ChordSlot, ...],
    raw_pitches: list[int],
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    dynamics: tuple[DynamicEvent, ...],
    harmonies: tuple[HarmonyEvent, ...],
    bands: list[str],
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
) -> Score:
    """Assemble the 30-bar Minimalist Techno score."""
    bell = _synth_bell_part(phrases, pitches, band_at, chord_at)
    arp_notes, arp_wedges, arp_dynamics = _synth_arpeggio_part(raw_pitches, phrases, chord_at)
    pad = _warm_pad_part(slots)
    pulse = _synth_pulse_part(chord_at, band_at)
    sub_bass = _sub_bass_part(chord_at, band_at)

    return Score(
        title=title,
        bpm=MINIMALIST_BPM,
        bars=MUSICAL_BARS,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=slots,
        flute=bell,
        violin=arp_notes,
        cello=pad,
        piano=pulse,
        bass=sub_bass,
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        violin_wedges=arp_wedges,
        cello_wedges=(),
        violin_dynamics=arp_dynamics,
        cello_dynamics=(),
        variant="minimalist",
        divisions=MINIMALIST_DIVISIONS,
        swing=False,
    )
