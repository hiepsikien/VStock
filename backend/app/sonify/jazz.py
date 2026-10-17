"""Jazz / Lo-Fi Jazz variant with threshold layering, swing playback, and walking bass.

Architecture:
- High-End Accent Layer (> C6, P5 — Vibraphone, MIDI Program 12):
  Appears strictly as a sparse accent/color instrument (10%–15% of total duration)
  at velocity 54–68 (mp–mf) on Breakout events (3-note high jazz bell cluster in C6–G6)
  and high phrase apexes / pinbar peaks (single ringing high note in C6–G6).
- Mid-High Lead Layer (C4–A5, P1 — Alto Saxophone, MIDI Program 66) &
  Low-Mid Handoff Layer (< G3–C4, P2 — Tenor Saxophone, MIDI Program 67):
  Carries the main Close price melody with legato phrasing, hairpins, and swing groove.
  Notes above A5 (81) fold cleanly into the sweet Saxophone register while Vibraphone
  sparkles above C6.
- Mid Layer (C3–C4, P3 — Fender Rhodes Piano, MIDI Program 5):
  Lush 7th/9th Jazz chords (Cmaj9, Fmaj9, Dm9, G9, Am9, Em7) with Charleston
  syncopation (beat 1 dotted-quarter + "and of 2" eighth) and cadence fills.
- Low Layer (C1–C3, P4 — Upright Jazz Bass, MIDI Program 33):
  2-feel half notes on quiet tape ('p') and 4-beat quarter-note Walking Bass with
  diatonic scale approach notes leading into the next bar's root on active tape ('mp'–'f').
"""

from __future__ import annotations

from app.sonify.chords import Chord, Regime, jazz_chord
from app.sonify.form import (
    EIGHTHS_PER_BAR,
    MUSICAL_BARS,
    ChordSlot,
)
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import PERIOD, Phrase, Run
from app.sonify.quantize import c_major_scale
from app.sonify.render import (
    BREAKOUT,
    FILL_VELOCITY,
    HALF_BAR,
    MIN_RISE,
    TOTAL_EIGHTHS,
    _fills,
    _left_hand,
    _melody_parts,
    _with_rests,
    _written,
    comp_pitches,
    techniques,
)

JAZZ_BPM = 82
SAX_CEILING = 81  # A5: top of the sweet Alto Saxophone register
VIBRAPHONE_LOW = 84  # C6: high-end threshold (> C6)
VIBRAPHONE_HIGH = 91  # G6: top of the warm bell register
VIBRAPHONE_VEL_SINGLE = 58  # mp (~50-70 range)
VIBRAPHONE_VEL_CHORD = 64  # mp-mf (~50-70 range)
# Cap high-end Vibraphone accents at 15% of 240 eighths (36 eighths max across 30 bars)
VIBRAPHONE_MAX_EIGHTHS = 36


def _promote_jazz_slots(
    slots: tuple[ChordSlot, ...],
) -> tuple[tuple[ChordSlot, ...], tuple[HarmonyEvent, ...], dict[int, Chord]]:
    """Upgrade triads and seventh chords in slots to 7th/9th Jazz chords."""
    jazz_slots = tuple(
        ChordSlot(
            start=slot.start,
            length=slot.length,
            chord=jazz_chord(slot.chord),
            regime=slot.regime,
            section=slot.section,
        )
        for slot in slots
    )
    harmonies = tuple(
        HarmonyEvent(slot.start, slot.chord)
        for index, slot in enumerate(jazz_slots)
        if index == 0 or slot.chord != jazz_slots[index - 1].chord
    )
    chord_at = {bar: slot.chord for slot in jazz_slots for bar in slot.bars()}
    return jazz_slots, harmonies, chord_at


def _high_bell_voicing(chord: Chord) -> tuple[int, ...]:
    """Build a 3-note high Vibraphone cluster inside C6 (84) to G6 (91)."""
    scale_high = c_major_scale(VIBRAPHONE_LOW, VIBRAPHONE_HIGH)
    chord_tones = [m for m in scale_high if m % 12 in chord.pitch_classes]
    if len(chord_tones) >= 3:
        return tuple(chord_tones[:3])
    # Add diatonic 9th / scale tones in C6..G6 if fewer than 3 chord tones fit
    extra = [m for m in scale_high if m not in chord_tones]
    combined = sorted((chord_tones + extra)[:3])
    return tuple(combined)


def _vibraphone_accent_part(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
) -> tuple[NoteEvent, ...]:
    """Build the high-end Vibraphone part (P5) strictly on Breakouts and High Apexes.

    Controlled rules:
    - Register: strictly >= C6 (84..91).
    - Duty cycle: capped at <= 15% of total piece duration (<= 36 eighths), triggered
      purely by threshold events (Breakout, rising phrase apex, or pitch >= C6) with no
      artificial minimum padding on flat sessions.
    - Breakouts trigger a 3-note ringing chord cluster in C6–G6 (velocity 64).
    - High phrase apexes / pinbar peaks trigger a single ringing bell note in C6–G6 (velocity 58).
    """
    candidates: list[tuple[int, int, int, bool, Run]] = []
    # (priority, start, length, is_breakout, run)
    for phrase in phrases:
        colours = techniques(phrase, pitches, band_at)
        apex = phrase.apex
        for run in phrase.runs:
            is_breakout = colours.get(run.start) == BREAKOUT
            is_apex = run.start == apex.start and phrase.rise >= MIN_RISE
            if is_breakout or is_apex or run.midi >= VIBRAPHONE_LOW:
                bar = run.start // EIGHTHS_PER_BAR
                bar_end = (bar + 1) * EIGHTHS_PER_BAR
                # Ring for 4 eighths (half note) inside the bar, or at least 2 eighths
                avail = min(bar_end - run.start, max(PERIOD, min(run.length, 6)))
                if avail < 2:
                    continue
                priority = (
                    3 if is_breakout else (2 if (is_apex and run.midi >= 76) else 1)
                )
                candidates.append((priority, run.start, avail, is_breakout, run))

    # Sort by musical priority (breakouts first, then highest peaks), then chronological
    ranked = sorted(
        candidates,
        key=lambda item: (-item[0], -item[4].midi, item[1]),
    )

    chosen_spans: list[tuple[int, int, bool, Run]] = []
    used_bars: set[int] = set()
    total_eighths = 0

    for _prio, start, length, is_breakout, run in ranked:
        bar = start // EIGHTHS_PER_BAR
        if bar in used_bars:
            continue
        if total_eighths + length > VIBRAPHONE_MAX_EIGHTHS:
            remain = VIBRAPHONE_MAX_EIGHTHS - total_eighths
            if remain >= 2:
                length = remain
            else:
                continue
        chosen_spans.append((start, length, is_breakout, run))
        used_bars.add(bar)
        total_eighths += length
        if total_eighths >= VIBRAPHONE_MAX_EIGHTHS:
            break

    chosen_spans.sort(key=lambda item: item[0])

    # Build NoteEvents (filling gaps with rests, supporting 3-note chord clusters on breakouts)
    scale_high = c_major_scale(VIBRAPHONE_LOW, VIBRAPHONE_HIGH)
    events: list[NoteEvent] = []
    cursor = 0
    for start, length, is_breakout, run in chosen_spans:
        if start > cursor:
            events.extend(_written(cursor, start - cursor, None))
        bar = start // EIGHTHS_PER_BAR
        chord = chord_at[bar]
        pieces = _written(
            start,
            length,
            scale_high[0],
            velocity=VIBRAPHONE_VEL_CHORD if is_breakout else VIBRAPHONE_VEL_SINGLE,
            tenuto=True,
        )
        if is_breakout:
            cluster = _high_bell_voicing(chord)
            for piece in pieces:
                for tone in cluster:
                    events.append(
                        NoteEvent(
                            bar=piece.bar,
                            beat=piece.beat,
                            midi=tone,
                            duration_beats=piece.duration_beats,
                            voice=1,
                            tie_start=piece.tie_start,
                            tie_stop=piece.tie_stop,
                            tenuto=piece.tenuto,
                            velocity=VIBRAPHONE_VEL_CHORD,
                        )
                    )
        else:
            chord_tones = [m for m in scale_high if m % 12 in chord.pitch_classes]
            bell_midi = chord_tones[-1] if chord_tones else VIBRAPHONE_LOW
            for piece in pieces:
                events.append(
                    NoteEvent(
                        bar=piece.bar,
                        beat=piece.beat,
                        midi=bell_midi,
                        duration_beats=piece.duration_beats,
                        voice=1,
                        tie_start=piece.tie_start,
                        tie_stop=piece.tie_stop,
                        tenuto=piece.tenuto,
                        velocity=VIBRAPHONE_VEL_SINGLE,
                    )
                )
        cursor = start + length

    if cursor < TOTAL_EIGHTHS:
        events.extend(_written(cursor, TOTAL_EIGHTHS - cursor, None))
    return tuple(events)


def _clamp_sax_register(notes: list[NoteEvent]) -> list[NoteEvent]:
    """Keep Alto Saxophone inside its warm C4–A5 ceiling (<= 81) while Vibraphone covers > C6."""
    clamped: list[NoteEvent] = []
    for note in notes:
        midi = note.midi
        if midi is not None:
            while midi > SAX_CEILING:
                midi -= 12
        clamped.append(
            NoteEvent(
                bar=note.bar,
                beat=note.beat,
                midi=midi,
                duration_beats=note.duration_beats,
                voice=note.voice,
                staff=note.staff,
                tie_start=note.tie_start,
                tie_stop=note.tie_stop,
                slur_start=note.slur_start,
                slur_stop=note.slur_stop,
                accent=note.accent,
                velocity=note.velocity,
                tenuto=note.tenuto,
                staccato=note.staccato,
            )
        )
    return clamped


def _rhodes_voicing(chord: Chord) -> tuple[int, tuple[int, ...]]:
    """Return left-hand root (F2–E3) and right-hand guide+9th tones in A3–A4."""
    root, guide = comp_pitches(chord)
    if len(chord.pitches) >= 5:
        ninth_pc = chord.pitches[4] % 12
        ninth_midi = 60 + ninth_pc  # C4–B4
        if ninth_midi <= max(guide):
            ninth_midi += 12
        if ninth_midi <= 72 and ninth_midi not in guide:
            return root, (*guide, ninth_midi)
    return root, guide


def _rhodes_comping_part(
    slots: tuple[ChordSlot, ...],
    cadences: list[tuple[Run, str]],
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
) -> list[NoteEvent]:
    """Build Fender Rhodes Piano (P3) with Charleston syncopation and Jazz fills.

    On active phrase bars where no cadence fill starts in the first half-bar, Rhodes
    plays a classic Jazz Charleston comping figure on beats 1.0 (dotted quarter, 1.5 beats)
    and 1.5 ("and of 2", eighth note, 0.5 beats). On intro/outro or quiet bars ('p'),
    it plays a warm half-note chord cushion on beat 1.0.
    """
    fills = _fills(cadences, chord_at)
    first_fill: dict[int, int] = {}
    for start, _length, _midi in fills:
        bar = start // EIGHTHS_PER_BAR
        first_fill[bar] = min(first_fill.get(bar, start), start)

    right_events: list[NoteEvent] = []
    for slot in slots:
        _root, voicing = _rhodes_voicing(slot.chord)
        for bar in slot.bars():
            downbeat = bar * EIGHTHS_PER_BAR
            avail_eighths = min(HALF_BAR, first_fill.get(bar, downbeat + HALF_BAR) - downbeat)
            use_charleston = (
                slot.section == "phrase"
                and band_at[bar] != "p"
                and avail_eighths == HALF_BAR
                and bar % 2 == 0
            )
            if use_charleston:
                for midi in voicing:
                    right_events.append(
                        NoteEvent(bar=bar, beat=0.0, midi=midi, duration_beats=1.5, voice=1)
                    )
                for midi in voicing:
                    right_events.append(
                        NoteEvent(
                            bar=bar,
                            beat=1.5,
                            midi=midi,
                            duration_beats=0.5,
                            voice=1,
                            tenuto=True,
                        )
                    )
            else:
                for midi in voicing:
                    right_events.append(
                        NoteEvent(
                            bar=bar,
                            beat=0.0,
                            midi=midi,
                            duration_beats=avail_eighths * 0.5,
                            voice=1,
                        )
                    )

    for start, length, midi in fills:
        right_events.extend(_written(start, length, midi, velocity=FILL_VELOCITY))

    piano: list[NoteEvent] = list(_with_rests(right_events, TOTAL_EIGHTHS))
    for slot in slots:
        piano.extend(_left_hand(slot))
    return piano


def _walking_bass_bar(
    chord: Chord,
    next_chord: Chord,
    band: str,
    bar: int,
    section: str,
    scale_bass: tuple[int, ...],
) -> list[NoteEvent]:
    """Generate one bar of Upright Jazz Bass (P4).

    - Intro/outro or 'p' liquidity: 2-feel half notes (Root on beat 1, Fifth on beat 3).
    - Active phrase bars ('mp', 'mf', 'f'): 4-beat quarter-note Walking Bass:
      Beat 1: Root (C2–B2)
      Beat 2: Diatonic 3rd or 5th
      Beat 3: Perfect 5th (or Octave on 'f')
      Beat 4: Diatonic scale approach note (1 step above or below next bar's Root).
    """
    root = chord.bass_midi
    fifth = root + 7
    if section == "outro":
        return [
            NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=4.0, voice=1),
        ]
    if band == "p" or section == "intro":
        return [
            NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=2.0, voice=1),
            NoteEvent(bar=bar, beat=2.0, midi=fifth, duration_beats=2.0, voice=1),
        ]

    # 4-beat Walking Bass
    third_pc = chord.pitches[1] % 12
    root_pc = chord.pitches[0] % 12
    third = root + ((third_pc - root_pc) % 12)
    beat2 = third if bar % 2 == 0 else fifth
    beat3 = (root + 12) if band == "f" else fifth

    # Diatonic approach note on beat 4 leading to next_chord's root
    next_root = next_chord.bass_midi
    if next_root in scale_bass:
        n_idx = scale_bass.index(next_root)
        above = scale_bass[min(len(scale_bass) - 1, n_idx + 1)]
        below = scale_bass[max(0, n_idx - 1)]
        # Pick the approach note closer to beat3 (so the bass line walks smoothly)
        beat4 = above if abs(above - beat3) <= abs(below - beat3) else below
        if beat4 == next_root:
            beat4 = fifth
    else:
        beat4 = fifth

    return [
        NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=1.0, midi=beat2, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=2.0, midi=beat3, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=3.0, midi=beat4, duration_beats=1.0, voice=1),
    ]


def render_jazz_score(
    *,
    title: str,
    chosen: tuple[Regime, Regime, Regime],
    sample_indexes: tuple[int, int, int] | None,
    slots: tuple[ChordSlot, ...],
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    dynamics: tuple[DynamicEvent, ...],
    bands: list[str],
    band_at: dict[int, str],
) -> Score:
    """Assemble the 30-bar Lo-Fi / Cool Jazz score."""
    jazz_slots, harmonies, chord_at = _promote_jazz_slots(slots)
    section_at = {bar: slot.section for slot in jazz_slots for bar in slot.bars()}

    vibraphone = _vibraphone_accent_part(phrases, pitches, band_at, chord_at)
    alto_sax, tenor_sax, cadences = _melody_parts(pitches, phrases, band_at, yield_spans=None)
    clamped_alto = _clamp_sax_register(alto_sax.notes)

    rhodes = _rhodes_comping_part(jazz_slots, cadences, chord_at, band_at)

    scale_bass = c_major_scale(33, 60)
    bass: list[NoteEvent] = []
    for bar in range(MUSICAL_BARS):
        next_chord = chord_at[min(MUSICAL_BARS - 1, bar + 1)]
        bass.extend(
            _walking_bass_bar(
                chord_at[bar],
                next_chord,
                band_at[bar],
                bar,
                section_at[bar],
                scale_bass,
            )
        )

    return Score(
        title=title,
        bpm=JAZZ_BPM,
        bars=MUSICAL_BARS,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=jazz_slots,
        flute=vibraphone,
        violin=_with_rests(clamped_alto, TOTAL_EIGHTHS),
        cello=_with_rests(tenor_sax.notes, TOTAL_EIGHTHS),
        piano=tuple(rhodes),
        bass=tuple(bass),
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        violin_wedges=tuple(alto_sax.wedges),
        cello_wedges=tuple(tenor_sax.wedges),
        violin_dynamics=tuple(alto_sax.dynamics),
        cello_dynamics=tuple(tenor_sax.dynamics),
        variant="jazz",
        divisions=2,
        swing=True,
    )
