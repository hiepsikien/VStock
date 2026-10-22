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
    active_meter,
    MUSICAL_BARS,
    TOTAL_EIGHTHS,
    ChordSlot,
)
from app.sonify.keys import C_REGISTER, active_register
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score, WedgeEvent
from app.sonify.phrasing import (
    BELL_MAX_EIGHTHS,
    BREAKOUT,
    MIN_RISE,
    PERIOD,
    Phrase,
    bell_budget,
    hairpins,
    lift,
    techniques,
    with_rests,
    written,
)
from app.sonify.quantize import SCALE_HIGH, SCALE_LOW, c_major_scale

MINIMALIST_BPM = 118
MINIMALIST_DIVISIONS = 4  # 16th-note resolution (4 divisions per quarter beat)

# Filter / Brightness register bands (mapped from normalized price in [0.0, 1.0])
CLOSED_CUTOFF = 0.35   # Low price -> dark register (C3-B3), staccato, soft
OPEN_CUTOFF = 0.70     # High price -> bright register (C5-C6), tenuto, bright

ARP_VEL_LOW = 48
ARP_VEL_HIGH = 90
BELL_VELOCITY = 64
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


def _concert_shift() -> int:
    """Semitones MusicXML will add. Compose this much lower so the sounding pitch stays put."""
    return C_REGISTER.synth_low - active_register().synth_low


def _window(low: int, high: int) -> tuple[int, int]:
    shift = _concert_shift()
    return low - shift, high - shift


def _keep(midi: int, low: int, high: int) -> int:
    """Move by octaves until the sounding pitch stays inside the C-major window."""
    floor, ceiling = _window(low, high)
    while midi > ceiling:
        midi -= 12
    while midi < floor:
        midi += 12
    return midi


def _arp_chord_ladder(chord: Chord) -> list[int]:
    """Chord tones from C3 to C6, shifted so the sounding line stays in that span."""
    pcs = chord.pitch_classes
    low, high = _window(48, 84)
    return [midi for midi in range(low, high + 1) if midi % 12 in pcs]


def _synth_arpeggio_part(
    raw_pitches: list[int],
    phrases: tuple[Phrase, ...],
    chord_at: dict[int, Chord],
    musical_bars: int = MUSICAL_BARS,
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
    meter = active_meter()
    ostinato_by_meter = {
        (4, 4): (0, 1, 2, 1, 0, 2, 1, 2),
        (5, 4): (0, 1, 2, 1, 0, 2, 0, 1, 2, 1),
        (7, 8): (0, 1, 0, 2, 0, 1, 2),
    }
    ostinato_offsets = ostinato_by_meter.get(
        (meter.beats, meter.beat_type), (0, 1, 2, 1, 0, 2, 1, 2)
    )

    for bar in range(musical_bars):
        chord = chord_at[bar]
        ladder = _arp_chord_ladder(chord)
        max_base = max(0, len(ladder) - 3)
        for eighth_in_bar in range(meter.eighths_per_bar):
            eighth = bar * meter.eighths_per_bar + eighth_in_bar
            raw_midi = raw_pitches[eighth]
            norm = _normalized_brightness(raw_midi)
            from app.sonify.groove import groove_at

            groove = groove_at(bar)
            if groove.rally:
                norm = max(norm, OPEN_CUTOFF)
            elif groove.selloff or groove.half:
                norm = min(norm, CLOSED_CUTOFF if groove.half and not groove.selloff else CLOSED_CUTOFF * 0.5)
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
            is_downbeat = eighth_in_bar in meter.strong_eighths
            accent = is_open and eighth_in_bar == 0
            if is_open and (meter.beats, meter.beat_type) == (7, 8) and eighth_in_bar in (2, 4):
                accent = True
            if is_open and (meter.beats, meter.beat_type) == (5, 4) and eighth_in_bar == 6:
                accent = True
                vel = max(1, vel - 8)
            notes.append(
                NoteEvent(
                    bar=bar,
                    beat=eighth_in_bar * 0.5,
                    midi=arp_midi,
                    duration_beats=0.5,
                    voice=1,
                    staccato=is_closed,
                    tenuto=is_open and is_downbeat,
                    accent=accent,
                    velocity=vel,
                )
            )

    # Filter sweep hairpins across phrases that have meaningful price movement
    drift = 0
    for phrase in phrases:
        if lift(phrase) <= 0.0:
            continue
        if drift != 0:
            dynamics.append(
                DynamicEvent(
                    bar=phrase.start // active_meter().eighths_per_bar,
                    marking="mp",
                    sound=SOUND["mp"],
                    beat=(phrase.start % active_meter().eighths_per_bar) * 0.5,
                )
            )
            drift = 0
        phrase_wedges = hairpins(phrase.start, phrase.end, phrase.apex.start)
        wedges.extend(phrase_wedges)
        for wedge in phrase_wedges:
            drift += {"crescendo": 1, "diminuendo": -1}.get(wedge.kind, 0)

    return tuple(notes), tuple(wedges), tuple(dynamics)


def _synth_bell_part(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
    *,
    rel_span: float = 1.0,
    total_eighths: int = TOTAL_EIGHTHS,
    bell_caps: tuple[tuple[int, int, int], ...] | None = None,
) -> tuple[NoteEvent, ...]:
    """High Synth Bell (P5): sparse accent layer (<= 15%, <= 36 eighths) on Breakouts and high peaks."""
    max_eighths = bell_budget(rel_span, BELL_MAX_EIGHTHS)
    if bell_caps is None and max_eighths < 2:
        return with_rests([], total_eighths)
    bell_events: list[NoteEvent] = []
    occupied_bars: set[int] = set()
    spent = 0
    spent_by_section: dict[tuple[int, int], int] = {}
    bell_low, bell_high = _window(84, 91)  # C6 to G6, kept in that sounding register
    scale = c_major_scale(bell_low, bell_high)

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
            bar = run.start // active_meter().eighths_per_bar
            if bar in occupied_bars:
                continue
            length = min(max(2, run.length), PERIOD)
            end = min((bar + 1) * active_meter().eighths_per_bar, run.start + length)
            span_len = end - run.start
            if span_len <= 0:
                continue
            if bell_caps is None:
                room = max_eighths - spent
            else:
                cap = next((item for item in bell_caps if item[0] <= run.start < item[1]), None)
                if cap is None:
                    continue
                room = cap[2] - spent_by_section.get((cap[0], cap[1]), 0)
            if span_len > room:
                if room < 2:
                    continue
                span_len = room
                end = run.start + span_len
            occupied_bars.add(bar)
            spent += span_len
            if bell_caps is not None:
                cap = next(item for item in bell_caps if item[0] <= run.start < item[1])
                key = (cap[0], cap[1])
                spent_by_section[key] = spent_by_section.get(key, 0) + span_len
            chord = chord_at[bar]
            high_tones = [m for m in scale if m % 12 in chord.pitch_classes]
            pool = high_tones if high_tones else list(scale)
            norm = min(1.0, max(0.0, (run.midi - 79) / (96 - 79)))
            target = bell_low + norm * (bell_high - bell_low)
            bell_midi = min(pool, key=lambda m: (abs(m - target), m))
            bell_events.extend(
                written(
                    run.start,
                    span_len,
                    bell_midi,
                    velocity=BELL_VELOCITY,
                    tenuto=True,
                )
            )
            if bell_caps is None and spent >= max_eighths:
                break

    return with_rests(bell_events, total_eighths)


def _warm_pad_part(slots: tuple[ChordSlot, ...]) -> tuple[NoteEvent, ...]:
    """Warm Synth Pad (P2): sustained low-mid chord foundation tracking the MA20 regime."""
    events: list[NoteEvent] = []
    for slot in slots:
        pcs = tuple(p % 12 for p in slot.chord.pitches)
        root_pc = pcs[0]
        third_pc = pcs[1]
        root_midi = _keep(48 + root_pc, 46, 57)
        third_midi = _keep(root_midi + ((third_pc - root_pc) % 12), 46, 68)
        epb = active_meter().eighths_per_bar
        for bar in slot.bars():
            for midi in (root_midi, third_midi):
                for note in written(bar * epb, epb, midi, velocity=PAD_VELOCITY):
                    events.append(note)
    return tuple(events)


def _hit(
    events: list[NoteEvent],
    bar: int,
    beat: float,
    midi: int | None,
    duration: float,
    *,
    staff: int,
    voice: int,
    vel: int,
    accent: bool = False,
) -> None:
    events.append(
        NoteEvent(
            bar=bar,
            beat=beat,
            midi=midi,
            duration_beats=duration,
            voice=voice,
            staff=staff,
            staccato=midi is not None,
            accent=accent and midi is not None,
            velocity=vel if midi is not None else None,
        )
    )


def _pulse_other_meter(
    events: list[NoteEvent],
    bar: int,
    band: str,
    vel: int,
    hi_root: int,
    hi_fifth: int,
    low_stab: int,
) -> bool:
    meter = active_meter()
    signature = (meter.beats, meter.beat_type)
    if signature == (7, 8):
        if band == "p":
            _hit(events, bar, 0.0, hi_root, 2.0, staff=1, voice=1, vel=vel)
            _hit(events, bar, 2.0, hi_root, 1.5, staff=1, voice=1, vel=vel)
        elif band == "mp":
            _hit(events, bar, 0.0, hi_root, 1.0, staff=1, voice=1, vel=vel)
            _hit(events, bar, 1.0, hi_fifth, 1.0, staff=1, voice=1, vel=vel)
            _hit(events, bar, 2.0, hi_root, 1.5, staff=1, voice=1, vel=vel)
        elif band == "mf":
            for eighth in range(7):
                _hit(
                    events, bar, eighth * 0.5,
                    hi_root if eighth % 2 == 0 else hi_fifth,
                    0.5, staff=1, voice=1, vel=vel, accent=eighth in (0, 2, 4),
                )
        else:
            for step in range(14):
                _hit(
                    events, bar, step * 0.25, hi_root, 0.25,
                    staff=1, voice=1, vel=vel, accent=step in (0, 4, 8),
                )
        _hit(events, bar, 0.0, None, meter.quarter_beats, staff=2, voice=5, vel=vel)
        return True
    if signature == (5, 4):
        if band == "p":
            _hit(events, bar, 0.0, hi_root, 3.0, staff=1, voice=1, vel=vel)
            _hit(events, bar, 3.0, hi_fifth, 2.0, staff=1, voice=1, vel=vel)
        elif band == "mp":
            for beat in range(5):
                _hit(
                    events, bar, float(beat),
                    hi_root if beat % 2 == 0 else hi_fifth,
                    1.0, staff=1, voice=1, vel=vel,
                )
        elif band == "mf":
            for eighth in range(10):
                _hit(
                    events, bar, eighth * 0.5,
                    hi_root if eighth % 2 == 0 else hi_fifth,
                    0.5, staff=1, voice=1, vel=vel, accent=eighth in meter.strong_eighths,
                )
        else:
            for step in range(20):
                _hit(
                    events, bar, step * 0.25, hi_root, 0.25,
                    staff=1, voice=1, vel=vel, accent=step in (0, 12),
                )
        if band in ("mf", "f"):
            _hit(events, bar, 0.0, None, 1.0, staff=2, voice=5, vel=vel)
            _hit(events, bar, 1.0, low_stab, 1.0, staff=2, voice=5, vel=vel, accent=band == "f")
            _hit(events, bar, 2.0, None, 2.0, staff=2, voice=5, vel=vel)
            _hit(events, bar, 4.0, low_stab, 1.0, staff=2, voice=5, vel=vel, accent=band == "f")
        else:
            _hit(events, bar, 0.0, None, 5.0, staff=2, voice=5, vel=vel)
        return True
    return False


def _synth_pulse_part(
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
    musical_bars: int = MUSICAL_BARS,
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
    for bar in range(musical_bars):
        band = band_at[bar]
        chord = chord_at[bar]
        vel = PULSE_VEL_BY_BAND[band]
        root_pc = chord.pitches[0] % 12
        fifth_pc = chord.pitches[2] % 12
        hi_root = _keep(72 + root_pc, 72, 83)
        hi_fifth = _keep(72 + fifth_pc, 72, 84)
        low_stab = _keep(48 + fifth_pc, 36, 55)
        from app.sonify.groove import groove_at

        groove = groove_at(bar)
        if groove.trio_thin:
            band = {"f": "mf", "mf": "mp", "mp": "p", "p": "p"}[band]
            vel = PULSE_VEL_BY_BAND[band]
        if groove.tresillo and band in ("mf", "f"):
            for beat, duration in ((0.0, 1.5), (1.5, 1.5), (3.0, 1.0)):
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=hi_root,
                        duration_beats=duration,
                        voice=1,
                        staff=1,
                        staccato=True,
                        velocity=vel,
                    )
                )
                events.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=low_stab,
                        duration_beats=duration,
                        voice=5,
                        staff=2,
                        staccato=True,
                        velocity=vel,
                    )
                )
            continue
        if _pulse_other_meter(events, bar, band, vel, hi_root, hi_fifth, low_stab):
            continue

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
            lifted = _keep(hi_root + 12, 72, 88)
            cycle = (hi_root, hi_fifth, lifted, hi_fifth)
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
        low_stab = _keep(48 + fifth_pc, 36, 55)
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
    from app.sonify.groove import groove_at, silence_second_half

    for bar in {note.bar for note in events if groove_at(note.bar).caesura}:
        events = silence_second_half(events, bar)
    return tuple(events)


def _sub_bass_part(
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
    musical_bars: int = MUSICAL_BARS,
) -> tuple[NoteEvent, ...]:
    """Four-on-the-floor Sub-Bass (P4): steady quarter-note kick/bass pulse on every beat."""
    events: list[NoteEvent] = []
    for bar in range(musical_bars):
        chord = chord_at[bar]
        band = band_at[bar]
        root = _keep(chord.bass_midi, 36, 47)
        meter = active_meter()
        signature = (meter.beats, meter.beat_type)
        from app.sonify.groove import groove_at, silence_second_half

        groove = groove_at(bar)
        bar_notes: list[NoteEvent] = []
        if signature == (7, 8):
            pulses = (
                ((0.0, 2.0), (2.0, 1.5))
                if groove.half or groove.trio_thin
                else ((0.0, 1.0), (1.0, 1.0), (2.0, 1.5))
            )
            for index, (beat, duration) in enumerate(pulses):
                midi = _keep(root + 12, 48, 59) if band == "f" and index == len(pulses) - 1 else root
                bar_notes.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=midi,
                        duration_beats=duration,
                        voice=1,
                        tenuto=index == 0,
                    )
                )
        elif signature == (4, 4) and groove.tresillo:
            for beat, duration in ((0.0, 1.5), (1.5, 1.5), (3.0, 1.0)):
                bar_notes.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=root,
                        duration_beats=duration,
                        voice=1,
                        tenuto=beat == 0.0,
                    )
                )
        elif groove.half or groove.trio_thin:
            spans = ((0.0, 2.5), (2.5, 2.5)) if signature == (5, 4) else ((0.0, 2.0), (2.0, 2.0))
            for beat, duration in spans:
                bar_notes.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=root,
                        duration_beats=duration,
                        voice=1,
                        tenuto=beat == 0.0,
                    )
                )
        else:
            quarters = 5 if signature == (5, 4) else BEATS_PER_BAR
            for beat in range(quarters):
                lifted = band == "f" and (
                    beat == quarters - 1 if signature == (5, 4) else beat == 3
                )
                midi = _keep(root + 12, 48, 59) if lifted else root
                bar_notes.append(
                    NoteEvent(
                        bar=bar,
                        beat=float(beat),
                        midi=midi,
                        duration_beats=1.0,
                        voice=1,
                        tenuto=beat == 0 or (signature == (5, 4) and beat == 3),
                    )
                )
        if groove.caesura:
            bar_notes = silence_second_half(bar_notes, bar)
        events.extend(bar_notes)
    return tuple(events)


def render_minimalist_score(
    *,
    title: str,
    chosen: tuple[Regime, ...],
    sample_indexes: tuple[int, ...] | None,
    slots: tuple[ChordSlot, ...],
    raw_pitches: list[int],
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    dynamics: tuple[DynamicEvent, ...],
    harmonies: tuple[HarmonyEvent, ...],
    bands: list[str],
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
    rel_span: float = 1.0,
    musical_bars: int = MUSICAL_BARS,
    total_eighths: int = TOTAL_EIGHTHS,
    bpm: int = MINIMALIST_BPM,
    bell_caps: tuple[tuple[int, int, int], ...] | None = None,
) -> Score:
    """Assemble the Minimalist Techno score."""
    bell = _synth_bell_part(
        phrases,
        pitches,
        band_at,
        chord_at,
        rel_span=rel_span,
        total_eighths=total_eighths,
        bell_caps=bell_caps,
    )
    arp_notes, arp_wedges, arp_dynamics = _synth_arpeggio_part(
        raw_pitches, phrases, chord_at, musical_bars
    )
    pad = _warm_pad_part(slots)
    pulse = _synth_pulse_part(chord_at, band_at, musical_bars)
    sub_bass = _sub_bass_part(chord_at, band_at, musical_bars)

    return Score(
        title=title,
        bpm=bpm,
        bars=musical_bars,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=slots,
        high=bell,
        lead=arp_notes,
        support=pad,
        comp=pulse,
        low=sub_bass,
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        lead_wedges=arp_wedges,
        support_wedges=(),
        lead_dynamics=arp_dynamics,
        support_dynamics=(),
        variant="minimalist",
        divisions=MINIMALIST_DIVISIONS,
        swing=False,
    )
