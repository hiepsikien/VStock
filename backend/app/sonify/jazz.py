"""Jazz / Lo-Fi Jazz variant with threshold layering, swing playback, and walking bass.

Architecture:
- High-End Accent Layer (>= C6, P5 — Vibraphone, MIDI Program 12):
  Appears strictly as a sparse accent/color instrument (<= 15% of total duration,
  <= 36 eighths) at velocity 58–64 (mp–mf) inside the standard 3-octave Vibraphone
  ceiling C6–F6 (84–89) on Breakout events (3-note high jazz bell cluster) and high
  phrase apexes / peaks (melodic bell tones following the price contour).
- Mid-High Lead Layer (G3–Ab5, P1 — Alto Saxophone, MIDI Program 66) &
  Low-Mid Handoff Layer (C3–C4, P2 — Tenor Saxophone, MIDI Program 67):
  Carries the main Close price melody with 1:1 scale resolution on all phrases
  inside the Saxophone register (<= Ab5 = 80), handing high peaks to Vibraphone via
  yield_spans and transposing only phrases that still exceed Ab5 down by whole octaves.
- Mid Layer (F2–B4, P3 — Fender Rhodes Piano, MIDI Program 5):
  Lush 7th/9th Jazz chords (Cmaj9, Fmaj9, Dm9, G9, Am9, Em7) with the 9th voiced
  inside/above the guide tones, Charleston syncopation (beat 1 dotted-quarter +
  "and of 2" eighth), and cadence fills.
- Low Layer (A1–C4, P4 — Upright Jazz Bass, MIDI Program 33):
  2-feel half notes on quiet tape ('p') and 4-beat quarter-note Walking Bass with
  diatonic scale approach notes leading into the next bar's root on active tape ('mp'–'f').
"""

from __future__ import annotations

from app.sonify.chords import Chord, Regime, jazz_chord
from app.sonify.form import (
    EIGHTHS_PER_BAR,
    HALF_BAR,
    MUSICAL_BARS,
    TOTAL_EIGHTHS,
    ChordSlot,
)
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import (
    BREAKOUT,
    FILL_VELOCITY,
    MIN_RISE,
    PERIOD,
    Phrase,
    Run,
    _fills,
    _left_hand,
    _melody_parts,
    _with_rests,
    _written,
    comp_pitches,
    runs_of,
    techniques,
)
from app.sonify.quantize import c_major_scale

JAZZ_BPM = 82
SAX_LOW = 48  # C3: bottom of Tenor Saxophone register
SAX_CEILING = 80  # Ab5 (G5 = 79 in C major): top of realistic Alto Saxophone range
VIBRAPHONE_LOW = 84  # C6: high-end bell threshold
VIBRAPHONE_HIGH = 89  # F6: top of the standard 3-octave Vibraphone (F3–F6)
VIBRAPHONE_VEL_SINGLE = 58  # mp
VIBRAPHONE_VEL_CHORD = 64  # mp-mf
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


def _bell_pitch(melody_midi: int, chord: Chord, scale_high: tuple[int, ...]) -> int:
    """Select a Vibraphone chord tone in C6–F6 (84–89) tracking the price contour."""
    chord_tones = [m for m in scale_high if m % 12 in chord.pitch_classes]
    pool = chord_tones if chord_tones else list(scale_high)
    norm = min(1.0, max(0.0, (melody_midi - 76) / (95 - 76)))
    target = VIBRAPHONE_LOW + norm * (VIBRAPHONE_HIGH - VIBRAPHONE_LOW)
    return min(pool, key=lambda m: (abs(m - target), m))


def _high_bell_voicing(
    melody_midi: int,
    chord: Chord,
    scale_high: tuple[int, ...],
) -> tuple[int, ...]:
    """Build a 3-note high Vibraphone cluster inside C6 (84) to F6 (89) around the peak."""
    chord_tones = [m for m in scale_high if m % 12 in chord.pitch_classes]
    extra = [m for m in scale_high if m not in chord_tones]
    lead = _bell_pitch(melody_midi, chord, scale_high)
    ranked = sorted(
        chord_tones + extra,
        key=lambda m: (m not in chord_tones, abs(m - lead), m),
    )
    return tuple(sorted(ranked[:3]))


def _vibraphone_accent_part(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
) -> tuple[tuple[NoteEvent, ...], list[tuple[int, int, bool, Run]]]:
    """Build the high-end Vibraphone part (P5) strictly on Breakouts and High Apexes.

    Controlled rules:
    - Register: strictly in C6–F6 (84..89), matching the standard 3-octave Vibraphone ceiling.
    - Duty cycle: capped at <= 15% of total piece duration (<= 36 eighths), triggered
      purely by threshold events (Breakout, rising phrase apex, or pitch >= C6) with no
      artificial minimum padding on flat sessions.
    - Breakouts trigger a 3-note ringing chord cluster in C6–F6 (velocity 64).
    - High phrase apexes / peaks trigger melodic bell notes in C6–F6 (velocity 58)
      that follow the price contour rather than repeating a static ceiling pitch.
    """
    candidates: list[tuple[int, int, int, bool, Run]] = []
    for phrase in phrases:
        colours = techniques(phrase, pitches, band_at)
        apex = phrase.apex
        for run in phrase.runs:
            is_breakout = colours.get(run.start) == BREAKOUT
            is_apex = run.start == apex.start and phrase.rise >= MIN_RISE
            if is_breakout or is_apex or run.midi >= VIBRAPHONE_LOW:
                bar = run.start // EIGHTHS_PER_BAR
                bar_end = (bar + 1) * EIGHTHS_PER_BAR
                avail = min(bar_end - run.start, max(PERIOD, min(run.length, 6)))
                if avail < 2:
                    continue
                priority = (
                    3 if is_breakout else (2 if (is_apex and run.midi >= 76) else 1)
                )
                candidates.append((priority, run.start, avail, is_breakout, run))

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

    scale_high = c_major_scale(VIBRAPHONE_LOW, VIBRAPHONE_HIGH)
    events: list[NoteEvent] = []
    cursor = 0
    for start, length, is_breakout, run in chosen_spans:
        if start > cursor:
            events.extend(_written(cursor, start - cursor, None))
        bar = start // EIGHTHS_PER_BAR
        chord = chord_at[bar]
        if is_breakout:
            pieces = _written(
                start,
                length,
                scale_high[0],
                velocity=VIBRAPHONE_VEL_CHORD,
                tenuto=True,
            )
            cluster = _high_bell_voicing(run.midi, chord, scale_high)
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
            bell_line = [
                _bell_pitch(pitches[eighth], chord_at[eighth // EIGHTHS_PER_BAR], scale_high)
                for eighth in range(start, start + length)
            ]
            bell_runs = [
                Run(start + r.start, r.length, r.midi)
                for r in runs_of(bell_line, 0, len(bell_line))
            ]
            has_slur = len(bell_runs) > 1
            for r_idx, b_run in enumerate(bell_runs):
                events.extend(
                    _written(
                        b_run.start,
                        b_run.length,
                        b_run.midi,
                        slur_start=has_slur and r_idx == 0,
                        slur_stop=has_slur and r_idx == len(bell_runs) - 1,
                        velocity=VIBRAPHONE_VEL_SINGLE,
                        tenuto=r_idx == 0,
                    )
                )
        cursor = start + length

    if cursor < TOTAL_EIGHTHS:
        events.extend(_written(cursor, TOTAL_EIGHTHS - cursor, None))
    return tuple(events), chosen_spans


def _sax_melody_curve(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    chosen_spans: list[tuple[int, int, bool, Run]],
) -> tuple[list[int], tuple[Phrase, ...], list[tuple[int, int]]]:
    """Keep phrases within the Saxophone register (<= Ab5 = 80) at full 1:1 resolution.

    Phrases that already fit within <= Ab5 (80), or whose only notes above Ab5 are
    covered by a non-breakout Vibraphone yield span, stay at their exact 1:1 pitches
    so small 1-step price movements never flatten out. Only phrases that still exceed
    Ab5 are transposed down by whole octaves (12 or 24 semitones) when their lowest
    note stays >= C3 (48), or monotonically compressed within the phrase onto C3–G5
    when a single phrase is too wide for a whole-octave shift.
    """
    scale = c_major_scale(SAX_LOW, 96)
    ceiling_idx = scale.index(79)  # G5 (79), highest C-major scale tone <= SAX_CEILING (80)
    yield_spans: list[tuple[int, int]] = []
    sax_pitches = list(pitches)
    temp_phrases: list[Phrase] = []

    for phrase in phrases:
        p_vibe = [
            (st, st + ln)
            for st, ln, is_b, r in chosen_spans
            if not is_b
            and st >= phrase.start
            and st + ln <= phrase.end
            and r.midi > SAX_CEILING
        ]
        norm_vibe = [
            (ys, phrase.end if ye == phrase.end - 1 else ye)
            for ys, ye in p_vibe
        ]
        rem_high = [
            r.midi
            for r in phrase.runs
            if r.midi > SAX_CEILING
            and not any(ys <= r.start and r.end <= ye for ys, ye in norm_vibe)
        ]
        if not rem_high:
            if norm_vibe:
                yield_spans.extend(norm_vibe)
            temp_phrases.append(phrase)
            continue

        top = max(r.midi for r in phrase.runs)
        bot = min(r.midi for r in phrase.runs)
        shift = 12 if top - 12 <= SAX_CEILING else 24
        if bot - shift >= SAX_LOW:
            runs = [Run(r.start, r.length, r.midi - shift) for r in phrase.runs]
            for eighth in range(phrase.start, phrase.end):
                sax_pitches[eighth] -= shift
        else:
            top_idx = scale.index(top)
            bot_idx = scale.index(bot)
            span_idx = max(1, top_idx - bot_idx)
            target_bot_idx = max(0, ceiling_idx - span_idx)
            for eighth in range(phrase.start, phrase.end):
                idx = scale.index(pitches[eighth])
                rel = (idx - bot_idx) / span_idx
                mapped_idx = round(target_bot_idx + rel * (ceiling_idx - target_bot_idx))
                sax_pitches[eighth] = scale[mapped_idx]
            runs = [
                part
                for r in phrase.runs
                for part in runs_of(sax_pitches, r.start, r.end)
            ]
        temp_phrases.append(Phrase(phrase.start, phrase.end, tuple(runs), False))

    sax_phrases = tuple(
        Phrase(
            p.start,
            p.end,
            p.runs,
            phrases[i].held_over
            and p.end < TOTAL_EIGHTHS
            and sax_pitches[p.end] == sax_pitches[p.end - 1],
        )
        for i, p in enumerate(temp_phrases)
    )
    return sax_pitches, sax_phrases, yield_spans


def _rhodes_voicing(chord: Chord) -> tuple[int, tuple[int, ...]]:
    """Return left-hand root (F2–E3) and right-hand guide+9th tones in A3–B4."""
    root, guide = comp_pitches(chord)
    if len(chord.pitches) >= 5:
        ninth_pc = chord.pitches[4] % 12
        ninth_midi = 60 + ninth_pc  # C4–B4
        if ninth_midi < min(guide):
            ninth_midi += 12
        if ninth_midi <= 72 and ninth_midi not in guide:
            return root, tuple(sorted((*guide, ninth_midi)))
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

    vibraphone, chosen_spans = _vibraphone_accent_part(phrases, pitches, band_at, chord_at)
    sax_pitches, sax_phrases, yield_spans = _sax_melody_curve(
        pitches, phrases, chosen_spans
    )
    alto_sax, tenor_sax, cadences = _melody_parts(
        sax_pitches, sax_phrases, band_at, yield_spans=yield_spans
    )

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
        violin=_with_rests(alto_sax.notes, TOTAL_EIGHTHS),
        cello=_with_rests(tenor_sax.notes, TOTAL_EIGHTHS),
        piano=tuple(rhodes),
        bass=tuple(bass),
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=sax_phrases,
        violin_wedges=tuple(alto_sax.wedges),
        cello_wedges=tuple(tenor_sax.wedges),
        violin_dynamics=tuple(alto_sax.dynamics),
        cello_dynamics=tuple(tenor_sax.dynamics),
        variant="jazz",
        divisions=2,
        swing=True,
    )
