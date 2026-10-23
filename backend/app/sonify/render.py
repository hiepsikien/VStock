"""Build a 30-bar score: violin, cello, and flute on the price, light piano comping, bass on liquidity."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.sonify.chords import Chord, Regime, fifth_above_bass, progression
from app.sonify.ensemble import fit_ensemble, tune_register
from app.sonify.dynamics import (
    MARKINGS,
    PIANO_VELOCITY,
    SOUND,
    average_liquidity,
    bass_marking,
    effective_comp_band,
    marking_for_volume,
    percentile,
    piano_marking,
)
from app.sonify.form import (
    BPM,
    DAILY_AMBIENT_BARS,
    DAILY_AMBIENT_SPEC,
    DAILY_BODY_BARS,
    DAILY_ENSEMBLE_SPEC,
    DAILY_SPEC,
    DAILY_WARMUP_BARS,
    METER_44,
    active_meter,
    compose_meter,
    swing_for,
    HALF_BAR,
    LIQUIDITY_WINDOWS,
    MUSICAL_BARS,
    PHRASE_STARTS,
    SECTION_STARTS,
    TOTAL_EIGHTHS,
    ChordSlot,
    FormSpec,
    liquidity_windows_for,
    plan_slots,
)
from app.sonify.harmony import dialect_for
from app.sonify.keys import (
    C_KEY,
    KeySpec,
    MovementCharacter,
    OutroOverride,
    active_register,
    compose_register,
    register_for,
)
from app.sonify.jazz import render_jazz_score
from app.sonify.minimalist import render_minimalist_score
from app.sonify.model import (
    VARIANTS,
    Bar,
    DynamicEvent,
    Ensemble,
    HarmonyEvent,
    NoteEvent,
    Phrase,
    Run,
    Score,
    Variant,
    WedgeEvent,
)
from app.sonify.phrasing import (
    BREAKOUT,
    FILL_VELOCITY,
    MIN_RISE,
    WEDGE_MIN,
    _wedge_at,
    comp_pitches,
    fills,
    hairpins,
    left_hand,
    lift,
    melody_parts,
    plan_phrases,
    quantize_strong_beats,
    runs_of,
    techniques,
    with_rests,
    written,
)
from app.sonify.quantize import c_major_scale, c_natural_minor_scale, price_to_scale_index, resample
from app.sonify.regime import REGIME_BARS, classify_window

FLUTE_TRIGGER = 79  # G5: Flute enters on high apex (>= G5) or Breakout
FLUTE_HANDBACK = 76  # E5: Flute keeps soaring while melody stays at or above E5
FLUTE_OVERLAP = 2  # eighths (1 beat) of dovetail harmony before Violin yields
MIN_VIOLIN_SPAN = 3  # eighths: Violin fragments <= FLUTE_OVERLAP (1–2 eighths) merge into Flute
FLUTE_DIP_FLOOR = 69  # A4: Flute bridges short (< MIN_VIOLIN_SPAN) dips down to A4
FLUTE_VELOCITY = 64  # mp ceiling so high flute stays airy and sweet

ROOT, FIFTH, OCTAVE = 0, 7, 12
# One bar of bass per dynamic: (start eighth, length in eighths, interval).
# A busier slot attacks more often, not only louder.
_HELD = ((0, 8, ROOT),)
_HALVES = ((0, 4, ROOT), (4, 4, FIFTH))
_QUARTERS = ((0, 2, ROOT), (2, 2, FIFTH), (4, 2, OCTAVE), (6, 2, FIFTH))
_EIGHTHS = (
    (0, 1, ROOT),
    (1, 1, ROOT),
    (2, 1, OCTAVE),
    (3, 1, ROOT),
    (4, 1, FIFTH),
    (5, 1, FIFTH),
    (6, 1, OCTAVE),
    (7, 1, FIFTH),
)
BASS_PATTERNS = {
    "p": _HELD,
    "mp": _HALVES,
    "mf": _QUARTERS,
    "f": _EIGHTHS,
}
_BASS_68 = {
    "p": ((0, 6, ROOT),),
    "mp": ((0, 3, ROOT), (3, 3, FIFTH)),
    "mf": ((0, 2, ROOT), (2, 1, FIFTH), (3, 2, OCTAVE), (5, 1, FIFTH)),
    "f": (
        (0, 1, ROOT),
        (1, 1, FIFTH),
        (2, 1, OCTAVE),
        (3, 1, ROOT),
        (4, 1, FIFTH),
        (5, 1, FIFTH),
    ),
}
_BASS_34 = {
    "p": ((0, 6, ROOT),),
    "mp": ((0, 4, ROOT), (4, 2, FIFTH)),
    "mf": ((0, 2, ROOT), (2, 2, FIFTH), (4, 2, FIFTH)),
    "f": (
        (0, 1, ROOT),
        (1, 1, FIFTH),
        (2, 1, OCTAVE),
        (3, 1, ROOT),
        (4, 1, FIFTH),
        (5, 1, FIFTH),
    ),
}


def _bass_pattern(
    marking: str, bar: int | None = None, *, under_cello: bool = False
) -> tuple[tuple[int, int, int], ...]:
    from app.sonify.form import active_meter
    from app.sonify.groove import groove_at

    meter = active_meter()
    groove = groove_at(bar) if bar is not None else None
    if groove is not None and groove.chamber:
        marking = "p"
    elif groove is not None and groove.trio_thin:
        marking = {"f": "mf", "mf": "mp", "mp": "p", "p": "p"}[marking]
    elif groove is not None and groove.half and marking == "mp":
        marking = "p"
    if groove is not None and groove.tresillo and (meter.beats, meter.beat_type) == (4, 4):
        pattern: tuple[tuple[int, int, int], ...] = ((0, 3, ROOT), (3, 3, FIFTH), (6, 2, ROOT))
    elif (meter.beats, meter.beat_type) == (6, 8):
        pattern = _BASS_68[marking]
    elif (meter.beats, meter.beat_type) == (3, 4):
        pattern = _BASS_34[marking]
    else:
        pattern = BASS_PATTERNS[marking]
    if (groove is not None and groove.selloff) or under_cello:
        pattern = tuple((start, length, ROOT if interval == OCTAVE else interval) for start, length, interval in pattern)
    elif groove is not None and groove.rally and marking in ("mf", "f"):
        pattern = tuple(
            (start, length, OCTAVE if start in (0, 4) and interval == FIFTH else interval)
            for start, length, interval in pattern
        )
    return pattern


def assign_source_bars(count: int, musical_bars: int = MUSICAL_BARS) -> list[list[int]]:
    """Drop each source index into one musical bar, in order.

    The first source bar always lands in musical bar 0. When there are fewer
    source bars than musical bars, the empty bars later repeat the price that
    was already sounding.
    """
    if count < 1:
        raise ValueError("need at least one source bar")
    groups: list[list[int]] = [[] for _ in range(musical_bars)]
    for index in range(count):
        group = (index * musical_bars) // count
        if group >= musical_bars:
            group = musical_bars - 1
        groups[group].append(index)
    return groups


def _frame_edges(spec: FormSpec | None) -> tuple[int, int]:
    if spec is None:
        return 0, MUSICAL_BARS
    warmup = 0
    cooldown = spec.bars
    for section in spec.sections:
        if section.kind == "warmup":
            warmup = section.end
        elif section.kind == "cooldown":
            cooldown = section.start
    return warmup, cooldown


def _assign_framed(count: int, musical_bars: int, warmup: int, body_end: int) -> list[list[int]]:
    body = assign_source_bars(count, body_end - warmup)
    groups: list[list[int]] = [[] for _ in range(musical_bars)]
    for offset, members in enumerate(body):
        groups[warmup + offset] = members
    return groups


def assign_daily_ambient_bars(count: int) -> list[list[int]]:
    """Map every candle across the 30-bar body. The frame bars stay empty.

    The body is the old 30-bar grid shifted two bars right, so the minutes that
    used to sit in the intro and the outro stay in the price line. Bars 0–1
    and 32–33 are the warm-up and the cool-down.
    """
    if count < 1:
        raise ValueError("need at least one source bar")
    body = assign_source_bars(count, DAILY_BODY_BARS)
    groups: list[list[int]] = [[] for _ in range(DAILY_AMBIENT_BARS)]
    for offset, members in enumerate(body):
        groups[DAILY_WARMUP_BARS + offset] = members
    return groups


def _sample_index(groups: list[list[int]], musical_bar: int) -> int:
    if groups[musical_bar]:
        return groups[musical_bar][0]
    for previous in range(musical_bar - 1, -1, -1):
        if groups[previous]:
            return groups[previous][-1]
    return 0


def _phrase_regime(bars: list[Bar], groups: list[list[int]], musical_bar: int) -> tuple[int, str]:
    start = _sample_index(groups, musical_bar)
    window = bars[start : start + REGIME_BARS]
    regime = classify_window(
        [bar.close for bar in window],
        [bar.ma20 for bar in window],
    )
    return start, regime


def _window_candles(
    bars: list[Bar], groups: list[list[int]], start: int, length: int
) -> list[float]:
    """Continuous-auction volume only inside one fixed bar window. ATO/ATC prints are not liquidity."""
    volumes: list[float] = []
    for musical_bar in range(start, start + length):
        for index in groups[musical_bar]:
            bar = bars[index]
            if bar.auction:
                continue
            volumes.append(bar.volume)
    return volumes


def _slot_candles(bars: list[Bar], groups: list[list[int]], slot: ChordSlot) -> list[float]:
    """Continuous-auction volume only. ATO/ATC prints are not liquidity."""
    return _window_candles(bars, groups, slot.start, slot.length)


def flute_harmony_pitch(
    melody_midi: int,
    chord: Chord,
    scale: tuple[int, ...],
) -> int:
    """A diatonic third or fifth above the melody (3, 4, or 7 semitones), preferring chord tones.

    Only true thirds (+3, +4 semitones) and perfect fifths (+7 semitones) are
    allowed — never a fourth (+5) or tritone (+6).
    """
    from app.sonify.quantize import scale_from_classes

    classes = frozenset(note % 12 for note in scale)
    extended = scale_from_classes(scale[0], scale[-1] + 24, classes)
    if melody_midi in extended:
        idx = extended.index(melody_midi)
        diatonic_candidates = [
            extended[idx + step]
            for step in (2, 4)
            if idx + step < len(extended)
            and (extended[idx + step] - melody_midi) in (3, 4, 7)
        ]
        chord_matches = [
            note for note in diatonic_candidates if note % 12 in chord.pitch_classes
        ]
        if chord_matches:
            return chord_matches[0]
        if diatonic_candidates:
            return diatonic_candidates[0]
    chord_tones = [
        melody_midi + offset
        for offset in (3, 4, 7)
        if (melody_midi + offset) % 12 in chord.pitch_classes
    ]
    if chord_tones:
        return chord_tones[0]
    return melody_midi + 4


def _shape_flute_span(
    phrase: Phrase,
    pitches: list[int],
    span_start: int,
    sounding_end: int,
    merged_flute_runs: list[Run],
    tie_first_in: bool,
    colours: dict[int, str],
    band_at: dict[int, str],
    ensemble: Ensemble,
    effective_level: str,
) -> tuple[list[WedgeEvent], list[DynamicEvent], list[int], str]:
    """Letters, hairpins, and velocities for one flute entrance.

    A glockenspiel of one run takes velocity = peak and never opens a wedge.
    A quiet span (peak 72) stays a flat mp. A loud span swells with a hairpin
    and does not print mf at the apex; mf is only the opening letter when the
    line is already at the top, or the single glockenspiel attack.
    """
    epb = active_meter().eighths_per_bar

    def overlaps_breakout(start: int, end: int) -> bool:
        return any(
            colours.get(run.start) == BREAKOUT and run.end > start and run.start < end
            for run in phrase.runs
        )

    span_apex = max(range(span_start, sounding_end), key=lambda eighth: (pitches[eighth], -eighth))
    has_breakout = overlaps_breakout(span_start, sounding_end)
    peak = 80 if has_breakout or band_at.get(span_apex // epb, "mp") in ("mf", "f") else 72
    first_attack = next(
        (run for index, run in enumerate(merged_flute_runs) if not (index == 0 and tie_first_in)),
        None,
    )
    if first_attack is None:
        return [], [], [64] * len(merged_flute_runs), effective_level

    arc_start = first_attack.start
    length = sounding_end - arc_start
    glock_one = ensemble == "brass" and len(merged_flute_runs) == 1
    branch_a = phrase.rise < MIN_RISE or peak == 72 or length < WEDGE_MIN
    eff_apex = span_apex
    wedges: list[WedgeEvent] = []
    start_marking = "mp"
    case = 1
    if branch_a:
        if glock_one and phrase.rise >= MIN_RISE and peak == 80:
            start_marking = "mf"
            case = 2
        if len(merged_flute_runs) == 1 and length >= 4:
            eff_apex = arc_start + length // 2
    elif glock_one:
        start_marking = "mf"
        case = 2
    elif len(merged_flute_runs) == 1 and length >= 4:
        eff_apex = arc_start + length // 2
        wedges = hairpins(arc_start, sounding_end, eff_apex)
        case = 3
    elif span_apex - arc_start >= WEDGE_MIN:
        eff_apex = span_apex
        wedges = hairpins(arc_start, sounding_end, eff_apex)
        case = 3 if sounding_end - eff_apex >= WEDGE_MIN else 4
    else:
        eff_apex = arc_start
        if ensemble != "brass":
            start_marking = "mf"
        wedges = [_wedge_at(arc_start, "diminuendo"), _wedge_at(sounding_end, "stop")]
        case = 4

    dynamics: list[DynamicEvent] = []
    level = effective_level
    if level != start_marking:
        dynamics.append(
            DynamicEvent(
                arc_start // epb,
                start_marking,
                SOUND[start_marking],
                (arc_start % epb) * 0.5,
            )
        )
        level = start_marking
    if case in (2, 4):
        level = "drifted"

    velocities: list[int] = []
    for run in merged_flute_runs:
        if phrase.rise < MIN_RISE:
            velocities.append(64)
            continue
        if glock_one:
            velocities.append(peak)
            continue
        if overlaps_breakout(run.start, run.end):
            velocities.append(peak)
            continue
        onset = max(arc_start, run.start)
        if onset <= eff_apex:
            span = 1.0 if eff_apex == arc_start else (onset - arc_start) / (eff_apex - arc_start)
        else:
            span = 1.0 - (onset - eff_apex) / max(1, sounding_end - eff_apex)
        velocities.append(round(64 + (peak - 64) * lift(phrase) * span))
    return wedges, dynamics, velocities, level


def _flute_and_violin_dovetail(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
    scale: tuple[int, ...],
    piece_eighths: int = TOTAL_EIGHTHS,
    mode: str = "major",
    ensemble: Ensemble = "classic",
) -> tuple[list[NoteEvent], list[tuple[int, int]], list[WedgeEvent], list[DynamicEvent]]:
    """Build Flute highlight notes and record spans where Violin yields.

    When a rising phrase reaches a high Apex (>= FLUTE_TRIGGER) or a BREAKOUT
    run, Flute enters softly (tenuto + legato slur) onto a chordal 3rd/5th
    above the melody. When Violin has already been playing a lead-in of at
    least 3 eighths inside the phrase and the entry note is within
    VIOLIN_CEILING, Violin and Flute play together for FLUTE_OVERLAP eighths
    (1 beat of dovetail layering) before Violin yields; otherwise (or when
    continuing from a previous Flute phrase) Violin yields immediately at
    span_start so it never flashes for a single beat and cuts out. Short
    isolated Violin fragments (< MIN_VIOLIN_SPAN eighths) before, between, or
    after Flute spans in a phrase are absorbed into Flute so the high solo
    line stays unbroken.
    """
    flute_notes: list[NoteEvent] = []
    yield_spans: list[tuple[int, int]] = []
    on_cello = False
    flute_active = False
    flute_tied_in = False
    violin_tied_in = False
    prev_flute_midi: int | None = None
    flute_wedges: list[WedgeEvent] = []
    flute_dynamics: list[DynamicEvent] = []
    effective_level = "mp"

    for phrase in phrases:
        colours = techniques(phrase, pitches, band_at)
        apex = phrase.apex
        breath = phrase.closes and phrase.end < piece_eighths
        crosses_ceiling = (
            max(r.midi for r in phrase.runs) > active_register().violin_ceiling
            and min(r.midi for r in phrase.runs) <= active_register().violin_ceiling
        )
        ended_on_flute = False

        run_is_violin: list[bool] = []
        for r in phrase.runs:
            on_cello = r.midi < active_register().cello_handback if on_cello else r.midi < active_register().violin_lowest
            run_is_violin.append(not on_cello)

        idx = 0
        while idx < len(phrase.runs):
            run = phrase.runs[idx]
            continued_flute = (
                flute_active
                and idx == 0
                and run.midi >= FLUTE_HANDBACK
            )
            is_breakout = (
                phrase.rise >= MIN_RISE
                and colours.get(run.start) == BREAKOUT
                and run.midi >= FLUTE_HANDBACK
            )
            is_high_apex = (
                phrase.rise >= MIN_RISE
                and run.start == apex.start
                and run.midi >= FLUTE_TRIGGER
            )
            above_ceiling = (
                phrase.rise > 0 or crosses_ceiling
            ) and run.midi > active_register().violin_ceiling
            if not (continued_flute or is_breakout or is_high_apex or above_ceiling):
                idx += 1
                continue

            # Absorb any short standalone Violin fragment (< MIN_VIOLIN_SPAN eighths
            # at >= FLUTE_DIP_FLOOR) immediately preceding this Flute entry so Violin
            # does not blip before Flute, without pulling low notes (< A4) into Flute.
            start_idx = idx
            if start_idx > 0:
                v_prefix_start = start_idx
                while (
                    v_prefix_start > 0
                    and run_is_violin[v_prefix_start - 1]
                    and phrase.runs[v_prefix_start - 1].midi >= FLUTE_DIP_FLOOR
                    and (
                        not yield_spans
                        or phrase.runs[v_prefix_start - 1].start >= yield_spans[-1][1]
                    )
                ):
                    v_prefix_start -= 1
                prefix_eighths = (
                    phrase.runs[start_idx].start - phrase.runs[v_prefix_start].start
                )
                has_unyielded_violin_before = (
                    v_prefix_start > 0
                    and run_is_violin[v_prefix_start - 1]
                    and (
                        not yield_spans
                        or phrase.runs[v_prefix_start - 1].start >= yield_spans[-1][1]
                    )
                )
                if (
                    0 < prefix_eighths < MIN_VIOLIN_SPAN
                    and not has_unyielded_violin_before
                    and not (v_prefix_start == 0 and violin_tied_in)
                ):
                    start_idx = v_prefix_start
                    if start_idx == 0 and flute_active:
                        continued_flute = True

            end_idx = idx + 1
            while end_idx < len(phrase.runs):
                if phrase.runs[end_idx].midi >= FLUTE_HANDBACK:
                    end_idx += 1
                    continue
                # Bridge short dips (< MIN_VIOLIN_SPAN eighths at >= FLUTE_DIP_FLOOR)
                # between high Flute runs or at the tail of a Flute phrase.
                dip_end = end_idx
                dip_eighths = 0
                while (
                    dip_end < len(phrase.runs)
                    and run_is_violin[dip_end]
                    and phrase.runs[dip_end].midi < FLUTE_HANDBACK
                    and phrase.runs[dip_end].midi >= FLUTE_DIP_FLOOR
                ):
                    dip_eighths += phrase.runs[dip_end].length
                    dip_end += 1
                if dip_end > end_idx:
                    eff_dip = dip_eighths - (
                        1 if breath and phrase.runs[dip_end - 1].end == phrase.end else 0
                    )
                    if eff_dip < MIN_VIOLIN_SPAN and (
                        dip_end == len(phrase.runs)
                        or (
                            dip_end < len(phrase.runs)
                            and phrase.runs[dip_end].midi >= FLUTE_HANDBACK
                        )
                    ):
                        end_idx = dip_end
                        continue
                break

            soar_runs = phrase.runs[start_idx:end_idx]
            span_start = soar_runs[0].start
            span_end = soar_runs[-1].end
            sounding_end = span_end - (1 if breath and span_end == phrase.end else 0)
            idx = end_idx
            if sounding_end <= span_start:
                continue

            # Skip isolated 1–2 eighth Flute blips that stay in the Violin register and do not
            # continue a Flute line; any peak above that register is kept on Flute so Violin
            # never has to fold it down an octave.
            if (
                not continued_flute
                and sounding_end - span_start <= FLUTE_OVERLAP
                and max(r.midi for r in soar_runs) <= active_register().violin_ceiling
            ):
                continue

            # Violin overlaps for FLUTE_OVERLAP eighths when it has already played a real
            # lead-in (>= MIN_VIOLIN_SPAN eighths) before span_start and the overlap notes
            # stay inside VIOLIN_CEILING, or at the very beginning of the piece (bar 0,
            # eighth 0) so Violin opens the session alongside Flute before handing off.
            v_lead_start = start_idx
            while (
                v_lead_start > 0
                and run_is_violin[v_lead_start - 1]
                and (
                    not yield_spans
                    or phrase.runs[v_lead_start - 1].start >= yield_spans[-1][1]
                )
            ):
                v_lead_start -= 1
            violin_lead = (
                (span_start - phrase.runs[v_lead_start].start)
                if v_lead_start < start_idx
                else (MIN_VIOLIN_SPAN if (start_idx == 0 and violin_tied_in) else 0)
            )
            can_overlap = (
                not continued_flute
                and (violin_lead >= MIN_VIOLIN_SPAN or span_start == 0)
                and all(
                    pitches[e] <= active_register().violin_ceiling
                    for e in range(span_start, min(sounding_end, span_start + FLUTE_OVERLAP))
                )
            )
            yield_start = span_start + FLUTE_OVERLAP if can_overlap else span_start

            # Keep Flute at or below E6 by folding any higher note down an octave
            # while preserving pitch class and step changes.
            flute_line: list[int] = []
            for eighth in range(span_start, sounding_end):
                flute_chord = chord_at[eighth // active_meter().eighths_per_bar]
                flute_scale = scale
                if mode == "minor" and flute_chord.name in ("G", "G7"):
                    from app.sonify.quantize import leading_scale

                    flute_scale = leading_scale(scale)
                f_pitch = flute_harmony_pitch(
                    pitches[eighth],
                    flute_chord,
                    flute_scale,
                )
                while f_pitch > active_register().flute_ceiling:
                    f_pitch -= 12
                flute_line.append(f_pitch)
            merged_flute_runs = [
                Run(span_start + r.start, r.length, r.midi)
                for r in runs_of(flute_line, 0, len(flute_line))
            ]
            has_slur = len(merged_flute_runs) > 1
            tie_first_in = (
                flute_tied_in
                and span_start == phrase.start
                and prev_flute_midi == merged_flute_runs[0].midi
            )
            # Only tie Flute across a held_over phrase boundary when the next phrase
            # will begin on the exact same Flute pitch (same chord at phrase.end).
            next_flute_midi: int | None = None
            if phrase.held_over and span_end == phrase.end and phrase.end < piece_eighths:
                next_chord = chord_at[phrase.end // active_meter().eighths_per_bar]
                next_scale = scale
                if mode == "minor" and next_chord.name in ("G", "G7"):
                    from app.sonify.quantize import leading_scale as _lead_scale

                    next_scale = _lead_scale(scale)
                nf_pitch = flute_harmony_pitch(
                    pitches[phrase.end],
                    next_chord,
                    next_scale,
                )
                while nf_pitch > active_register().flute_ceiling:
                    nf_pitch -= 12
                next_flute_midi = nf_pitch
            tie_last_out = (
                phrase.held_over
                and span_end == phrase.end
                and next_flute_midi == merged_flute_runs[-1].midi
            )
            span_wedges, span_dynamics, span_velocities, effective_level = _shape_flute_span(
                phrase,
                pitches,
                span_start,
                sounding_end,
                merged_flute_runs,
                tie_first_in,
                colours,
                band_at,
                ensemble,
                effective_level,
            )
            flute_wedges.extend(span_wedges)
            flute_dynamics.extend(span_dynamics)

            for r_i, f_run in enumerate(merged_flute_runs):
                is_first = r_i == 0
                is_last = r_i == len(merged_flute_runs) - 1
                flute_notes.extend(
                    written(
                        f_run.start,
                        f_run.length,
                        f_run.midi,
                        slur_start=has_slur and is_first,
                        slur_stop=has_slur and is_last,
                        velocity=span_velocities[r_i],
                        tenuto=is_first and not tie_first_in,
                        tie_in=is_first and tie_first_in,
                        tie_out=is_last and tie_last_out,
                    )
                )

            if yield_start < span_end:
                yield_spans.append((yield_start, span_end))
                if span_end == phrase.end:
                    ended_on_flute = True
            prev_flute_midi = merged_flute_runs[-1].midi

        flute_active = ended_on_flute
        flute_tied_in = phrase.held_over and ended_on_flute
        violin_tied_in = phrase.held_over and not ended_on_flute and run_is_violin[-1]

    return flute_notes, yield_spans, flute_wedges, flute_dynamics


def _fold_under_cello(midi: int, root: int) -> int:
    """Keep a cello-lead bar under C3. A fifth that already sits at C3–F#3 drops one octave."""
    if midi < 48:
        return midi
    folded = midi - 12
    return folded if folded >= 36 else root


def _bass_bar(
    chord: Chord, marking: str, bar: int, *, under_cello: bool = False
) -> list[NoteEvent]:
    degree = {
        ROOT: chord.bass_midi,
        FIFTH: fifth_above_bass(chord),
        OCTAVE: chord.bass_midi + OCTAVE,
    }
    events = [
        NoteEvent(
            bar=bar,
            beat=start * 0.5,
            midi=degree[interval],
            duration_beats=length * 0.5,
            voice=1,
        )
        for start, length, interval in _bass_pattern(marking, bar, under_cello=under_cello)
    ]
    if under_cello:
        events = [
            replace(event, midi=_fold_under_cello(event.midi, chord.bass_midi))
            if event.midi is not None
            else event
            for event in events
        ]
    from app.sonify.groove import groove_at, silence_second_half

    if groove_at(bar).caesura:
        return silence_second_half(events, bar)
    return events


def _right_hand(
    slots: tuple[ChordSlot, ...],
    cadence_fills: list[tuple[int, int, int]],
    piece_eighths: int = TOTAL_EIGHTHS,
    *,
    bed_velocity_at: dict[int, int] | None = None,
    bed_marking_at: dict[int, str] | None = None,
    phrases: tuple[Phrase, ...] | None = None,
) -> tuple[tuple[NoteEvent, ...], list[tuple[int, float, str, bool]], list[WedgeEvent]]:
    """Third and seventh on beat 1 for half a bar, cut short when a fill comes in.

    Without a bed map the fills stay at FILL_VELOCITY and no hairpin is written.
    Symphony passes the bed so each fill group swells or settles against it.
    """
    from app.sonify.groove import groove_at

    meter = active_meter()
    epb = meter.eighths_per_bar
    first_fill: dict[int, int] = {}
    for start, _length, _midi in cadence_fills:
        bar = start // epb
        first_fill[bar] = min(first_fill.get(bar, start), start)
    events: list[NoteEvent] = []
    for slot in slots:
        _root, guide = comp_pitches(slot.chord)
        for bar in slot.bars():
            if groove_at(bar).chamber:
                continue
            downbeat = bar * epb
            guide_eighths = 3 if (meter.beats, meter.beat_type) == (6, 8) else min(HALF_BAR, epb)
            length = min(guide_eighths, first_fill.get(bar, downbeat + guide_eighths) - downbeat)
            velocity = None if bed_velocity_at is None else bed_velocity_at.get(bar)
            events.extend(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=midi,
                    duration_beats=length * 0.5,
                    voice=1,
                    velocity=velocity,
                )
                for midi in guide
            )
    kept: list[tuple[int, int, int]] = []
    for start, length, midi in cadence_fills:
        bar = start // epb
        if groove_at(bar).caesura and (start % epb) * 0.5 >= meter.quarter_beats / 2:
            continue
        kept.append((start, length, midi))
    if bed_velocity_at is None or bed_marking_at is None:
        for start, length, midi in kept:
            events.extend(written(start, length, midi, velocity=FILL_VELOCITY))
        return with_rests(events, piece_eighths), [], []

    groups: list[tuple[Phrase | None, list[tuple[int, int, int]]]] = []
    current: list[tuple[int, int, int]] = []
    current_phrase: Phrase | None = None
    for start, length, midi in kept:
        phrase = next(
            (
                candidate
                for candidate in phrases or ()
                if candidate.closes and candidate.cadence.start <= start < candidate.cadence.end
            ),
            None,
        )
        if current and phrase is not current_phrase:
            groups.append((current_phrase, current))
            current = []
        current.append((start, length, midi))
        current_phrase = phrase
    if current:
        groups.append((current_phrase, current))

    fill_marks: list[tuple[int, float, str, bool]] = []
    comp_wedges: list[WedgeEvent] = []
    for phrase, group in groups:
        by_bar: dict[int, list[tuple[int, int, int]]] = {}
        for start, length, midi in group:
            by_bar.setdefault(start // epb, []).append((start, length, midi))
        for bar in sorted(by_bar):
            sub = by_bar[bar]
            groove = groove_at(bar)
            if groove.selloff:
                direction = "fall"
            elif groove.rally:
                direction = "rise"
            elif phrase is None or not phrase.runs:
                direction = "flat"
            elif phrase.cadence.midi > phrase.runs[0].midi:
                direction = "rise"
            elif phrase.cadence.midi < phrase.runs[0].midi:
                direction = "fall"
            else:
                direction = "flat"
            bed_mark = bed_marking_at[bar]
            fill_mark = "mp" if bed_mark == "p" else "mf"
            bed_vel = bed_velocity_at[bar]
            target = 64 if fill_mark == "mp" else 80
            sub_start = sub[0][0]
            sub_end = sub[-1][0] + sub[-1][1]
            long_enough = len(sub) >= 2 and sub_end - sub_start >= WEDGE_MIN
            if direction == "rise" and long_enough:
                letter, has_wedge = bed_mark, True
                start_vel, end_vel = bed_vel, target
                comp_wedges.extend((_wedge_at(sub_start, "crescendo"), _wedge_at(sub_end, "stop")))
            elif direction == "fall" and long_enough:
                letter, has_wedge = fill_mark, True
                start_vel, end_vel = target, 56 if fill_mark == "mp" else 72
                comp_wedges.extend((_wedge_at(sub_start, "diminuendo"), _wedge_at(sub_end, "stop")))
            else:
                letter, has_wedge = fill_mark, False
                start_vel = end_vel = target
            fill_marks.append((bar, (sub_start % epb) * 0.5, letter, has_wedge))
            last = len(sub) - 1
            for index, (start, length, midi) in enumerate(sub):
                velocity = start_vel if last == 0 else round(start_vel + (end_vel - start_vel) * index / last)
                events.extend(written(start, length, midi, velocity=velocity))
    return with_rests(events, piece_eighths), fill_marks, comp_wedges


def _comp_dynamics(
    notes: list[NoteEvent],
    fill_marks: list[tuple[int, float, str, bool]],
    bed_marking_at: dict[int, str],
    bars: int,
) -> list[DynamicEvent]:
    """Bed letter on a sounding downbeat, then the fill letter. A wedge drifts the level."""
    by_bar: dict[int, list[tuple[float, str, bool]]] = {}
    for bar, beat, marking, has_wedge in fill_marks:
        by_bar.setdefault(bar, []).append((beat, marking, has_wedge))
    sounding = {(note.bar, note.beat) for note in notes if note.midi is not None and note.beat == 0.0}
    current: str | None = None
    events: list[DynamicEvent] = []
    for bar in range(bars):
        bed = bed_marking_at[bar]
        if (bar, 0.0) in sounding and bed != current:
            events.append(DynamicEvent(bar, bed, SOUND[bed], 0.0))
            current = bed
        for beat, marking, has_wedge in by_bar.get(bar, []):
            if marking != current:
                events.append(DynamicEvent(bar, marking, SOUND[marking], beat))
            current = "drifted" if has_wedge else marking
    return events


def _section_rel_span(bars: list[Bar], groups: list[list[int]], start: int, end: int) -> float:
    closes = [bars[index].close for bar in range(start, end) for index in groups[bar]]
    if len(closes) < 2:
        return 0.0
    low = min(closes)
    high = max(closes)
    return (high - low) / max(abs(low), 1e-9)


def render(
    bars: list[Bar],
    *,
    title: str = "1-Day Recap",
    regimes: tuple[Regime, ...] | None = None,
    variant: Variant = "symphony",
    form: FormSpec | None = None,
    source_groups: list[list[int]] | None = None,
    price_low: float | None = None,
    price_high: float | None = None,
    volume_low: float | None = None,
    volume_high: float | None = None,
    key: KeySpec | None = None,
    character: MovementCharacter | None = None,
    outro_override: OutroOverride | None = None,
    framed: bool = True,
    mode: str = "major",
    home_pedal: bool = False,
    ensemble: Ensemble = "classic",
    character_at: Sequence[MovementCharacter | None] | None = None,
    gap_leads: Sequence[str | None] | None = None,
) -> Score:
    """Compose in C, with register bounds shifted for `key` before any note is placed.

    `framed` attaches the 1D warm-up and cool-down around the 30-bar price body.
    The daily recap turns it on. A caller that passes `form` keeps that form.
    """
    chosen_key = C_KEY if key is None else key
    tuned = tune_register(register_for(chosen_key), ensemble, chosen_key.semitones)
    with compose_register(chosen_key, tuned):
        score = _compose(
            bars,
            title=title,
            regimes=regimes,
            variant=variant,
            form=form,
            source_groups=source_groups,
            price_low=price_low,
            price_high=price_high,
            volume_low=volume_low,
            volume_high=volume_high,
            key=chosen_key,
            character=character,
            outro_override=outro_override,
            framed=framed,
            mode=mode,
            home_pedal=home_pedal,
            ensemble=ensemble,
            character_at=character_at,
            gap_leads=gap_leads,
        )
    return score


def _compose(
    bars: list[Bar],
    *,
    title: str,
    regimes: tuple[Regime, ...] | None,
    variant: Variant,
    form: FormSpec | None,
    source_groups: list[list[int]] | None,
    price_low: float | None,
    price_high: float | None,
    volume_low: float | None,
    volume_high: float | None,
    key: KeySpec,
    character: MovementCharacter | None,
    outro_override: OutroOverride | None,
    framed: bool = True,
    mode: str = "major",
    home_pedal: bool = False,
    ensemble: Ensemble = "classic",
    character_at: Sequence[MovementCharacter | None] | None = None,
    gap_leads: Sequence[str | None] | None = None,
) -> Score:
    """Turn one session of closes into a 30-bar score for `variant` ('symphony', 'jazz', 'minimalist').

    Each phrase regime is the average of the first few source bars at that
    phrase's downbeat, then held for the phrase. Intro uses phrase 1's regime;
    outro uses phrase 3's. The melody stays on the C major home scale, snapping
    notes on strong beats (beats 1 and 3) to chord tones of the active chord
    while keeping non-chord scale tones on weak beats as passing notes. Piano
    touches the third, seventh, and root, and answers each phrase that closes
    on a held note with a short arpeggio.
    The melody is cut into phrases where the price stalls; see phrasing.py.
    Liquidity is the average continuous volume of the slot, ranked p–f. The
    band sets how often the bass attacks: a held root at p, halves at mp,
    quarters at mf, a root–octave–fifth eighth-note drive at f. The bass is
    marked at that band but never above BASS_CEILING.
    """
    if not bars:
        raise ValueError("need at least one price bar")
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")

    spec = form
    daily = form is None and source_groups is None
    daily_ambient = daily and variant == "ambient"
    daily_ensemble = daily and framed and variant in ("symphony", "jazz", "minimalist")
    if daily_ambient:
        spec = DAILY_AMBIENT_SPEC
    elif daily_ensemble:
        spec = DAILY_ENSEMBLE_SPEC
    musical_bars = MUSICAL_BARS if spec is None else spec.bars
    warmup, body_end = _frame_edges(spec)
    meter = METER_44 if spec is None else spec.meter
    with compose_meter(meter):
        if source_groups is not None:
            groups = source_groups
        elif daily_ambient or daily_ensemble:
            groups = assign_daily_ambient_bars(len(bars))
        elif warmup or (spec is not None and body_end != spec.bars):
            groups = _assign_framed(len(bars), musical_bars, warmup, body_end)
        else:
            groups = assign_source_bars(len(bars), musical_bars)
        if len(groups) != musical_bars:
            raise ValueError(f"expected {musical_bars} source groups, got {len(groups)}")
        if regimes is None:
            if spec is None:
                phrase_starts = PHRASE_STARTS
            else:
                phrase_starts = tuple(
                    next(
                        section.start
                        for section in spec.sections
                        if section.regime_slot == slot and section.kind not in ("warmup", "cooldown")
                    )
                    for slot in range(spec.regime_slots)
                )
            samples = tuple(_phrase_regime(bars, groups, start) for start in phrase_starts)
            sample_indexes: tuple[int, ...] | None = tuple(index for index, _regime in samples)
            chosen = tuple(regime for _index, regime in samples)
        else:
            sample_indexes = None
            chosen = regimes
        for regime in chosen:
            progression(regime)

        scale = c_natural_minor_scale() if mode == "minor" else c_major_scale()
        session_low = min(bar.close for bar in bars) if price_low is None else price_low
        session_high = max(bar.close for bar in bars) if price_high is None else price_high
        held_close = bars[0].close
        raw_pitches: list[int] = []
        for group in groups:
            if group:
                closes = [bars[index].close for index in group]
                held_close = closes[-1]
            else:
                closes = [held_close]
            for close in resample(closes, active_meter().eighths_per_bar):
                raw_pitches.append(
                    scale[price_to_scale_index(close, session_low, session_high, len(scale))]
                )

        slots = plan_slots(
            chosen,
            raw_pitches,
            scale,
            spec,
            character=character,
            outro_override=None if home_pedal else outro_override,
            mode=mode,  # type: ignore[arg-type]
            home_pedal=home_pedal,
            harmonic_bridge=variant in ("jazz", "symphony"),
            character_at=character_at,
            gap_leads=gap_leads,
            dialect=dialect_for(ensemble),
        )

        windows = LIQUIDITY_WINDOWS if spec is None else liquidity_windows_for(spec)
        window_volumes = average_liquidity(
            [_window_candles(bars, groups, start, length) for start, length in windows]
        )
        traded = [volume for volume in window_volumes if volume > 0]
        low_volume = percentile(traded, 0.10) if volume_low is None else volume_low
        high_volume = percentile(traded, 0.90) if volume_high is None else volume_high
        bands = [marking_for_volume(volume, low_volume, high_volume) for volume in window_volumes]
        dynamics = tuple(
            DynamicEvent(bar=start, marking=bass_marking(band), sound=SOUND[bass_marking(band)])
            for (start, _length), band in zip(windows, bands)
        )
        harmonies = tuple(
            HarmonyEvent(slot.start, slot.chord)
            for index, slot in enumerate(slots)
            if index == 0 or slot.chord != slots[index - 1].chord
        )

        chord_at = {bar: slot.chord for slot in slots for bar in slot.bars()}
        pitches = quantize_strong_beats(raw_pitches, chord_at, scale, mode)
        section_starts = SECTION_STARTS if spec is None else spec.section_starts
        raw_phrases = plan_phrases(
            raw_pitches, tuple(start * active_meter().eighths_per_bar for start in section_starts)
        )
        phrases = tuple(
            Phrase(
                phrase.start,
                phrase.end,
                tuple(
                    part
                    for run in phrase.runs
                    for part in runs_of(pitches, run.start, run.end)
                ),
                phrase.held_over and pitches[phrase.end] == pitches[phrase.end - 1],
            )
            for phrase in raw_phrases
        )
        band_at = {
            bar: band
            for (start, length), band in zip(windows, bands)
            for bar in range(start, start + length)
        }
        for bar in range(musical_bars):
            band_at.setdefault(bar, "p")
        rel_span = (session_high - session_low) / max(abs(session_low), 1e-9)
        piece_eighths = TOTAL_EIGHTHS if spec is None else spec.eighths
        bell_caps = None
        if form is not None:
            from app.sonify.phrasing import bell_budget

            bell_caps = tuple(
                (
                    section.start * active_meter().eighths_per_bar,
                    section.end * active_meter().eighths_per_bar,
                    bell_budget(
                        _section_rel_span(bars, groups, section.start, section.end),
                        round(0.15 * (section.end - section.start) * active_meter().eighths_per_bar),
                    ),
                )
                for section in spec.sections
                if section.kind not in ("warmup", "cooldown")
            )
        def _finish(score: Score) -> Score:
            # The key has to be on the score before the fold. Drone and swell are
            # written in C; A and Bb then drop them, and the fold must see that.
            score = replace(
                score,
                ensemble=ensemble,
                key=key,
                mode=mode,  # type: ignore[arg-type]
                beats=meter.beats,
                beat_type=meter.beat_type,
                bar_beats=meter.quarter_beats,
                swing=swing_for(variant, meter),
            )
            score = fit_ensemble(score)
            if daily_ensemble:
                from app.sonify.daily_frame import apply_daily_frame

                score = apply_daily_frame(score)
            elif spec is not None and any(section.kind == "warmup" for section in spec.sections):
                from app.sonify.movement_frame import apply_span_frame

                score = apply_span_frame(score, spec, character)
            from app.sonify.groove import _GROOVE

            _GROOVE.set({})
            return score

        from app.sonify.groove import _GROOVE, build_groove

        _GROOVE.set(
            build_groove(spec, windows, bands, variant, character, character_at, chosen)
        )
        if variant == "jazz":
            from app.sonify.jazz import JAZZ_BPM

            return _finish(
                render_jazz_score(
                    title=title,
                    chosen=chosen,
                    sample_indexes=sample_indexes,
                    slots=slots,
                    pitches=pitches,
                    phrases=phrases,
                    dynamics=dynamics,
                    bands=bands,
                    band_at=band_at,
                    rel_span=rel_span,
                    musical_bars=musical_bars,
                    total_eighths=piece_eighths,
                    bpm=JAZZ_BPM if form is None else spec.bpm,
                    bell_caps=bell_caps,
                    mode=mode,
                )
            )
        if variant == "minimalist":
            from app.sonify.minimalist import MINIMALIST_BPM

            return _finish(
                render_minimalist_score(
                    title=title,
                    chosen=chosen,
                    sample_indexes=sample_indexes,
                    slots=slots,
                    raw_pitches=raw_pitches,
                    pitches=pitches,
                    phrases=phrases,
                    dynamics=dynamics,
                    harmonies=harmonies,
                    bands=bands,
                    chord_at=chord_at,
                    band_at=band_at,
                    rel_span=rel_span,
                    musical_bars=musical_bars,
                    total_eighths=piece_eighths,
                    bpm=MINIMALIST_BPM if form is None else spec.bpm,
                    bell_caps=bell_caps,
                )
            )
        if variant == "ambient":
            from app.sonify.ambient import AMBIENT_BPM, render_ambient_score

            return _finish(
                render_ambient_score(
                    title=title,
                    chosen=chosen,
                    sample_indexes=sample_indexes,
                    slots=slots,
                    pitches=pitches,
                    phrases=phrases,
                    bands=bands,
                    band_at=band_at,
                    windows=windows,
                    form=spec if spec is not None else DAILY_SPEC,
                    source_bars=bars,
                    source_groups=groups,
                    musical_bars=musical_bars,
                    total_eighths=piece_eighths,
                    bpm=AMBIENT_BPM if form is None else spec.bpm,
                    frame=daily_ambient,
                )
            )

        flute_notes, yield_spans, flute_wedges, flute_dynamics = _flute_and_violin_dovetail(
            phrases,
            pitches,
            band_at,
            chord_at,
            scale,
            piece_eighths=piece_eighths,
            mode=mode,
            ensemble=ensemble,
        )
        violin, cello, cadences = melody_parts(
            pitches, phrases, band_at, yield_spans, piece_eighths=piece_eighths
        )
        from app.sonify.groove import groove_at

        eff_bands = {
            bar: effective_comp_band(band_at[bar], bar) for bar in range(musical_bars)
        }
        bed_velocity_at = {bar: PIANO_VELOCITY[eff_bands[bar]] for bar in range(musical_bars)}
        bed_marking_at = {bar: piano_marking(eff_bands[bar]) for bar in range(musical_bars)}
        dense_left = frozenset(
            bar
            for bar in range(musical_bars)
            if eff_bands[bar] == "f" or groove_at(bar).rally
        )
        piano_notes, fill_marks, comp_wedges = _right_hand(
            slots,
            fills(cadences, chord_at),
            piece_eighths,
            bed_velocity_at=bed_velocity_at,
            bed_marking_at=bed_marking_at,
            phrases=phrases,
        )
        piano: list[NoteEvent] = list(piano_notes)
        for slot in slots:
            piano.extend(
                left_hand(slot, velocity_at=bed_velocity_at, every_bar_at=dense_left)
            )
        comp_dynamics = _comp_dynamics(piano, fill_marks, bed_marking_at, musical_bars)
        threshold = max(active_meter().quarter_beats / 2, 2.0) - 1e-6
        cello_beats: dict[int, float] = {}
        for note in cello.notes:
            if note.midi is None:
                continue
            cello_beats[note.bar] = cello_beats.get(note.bar, 0.0) + note.duration_beats
        cello_lead = {bar for bar, beats in cello_beats.items() if beats >= threshold}
        bass: list[NoteEvent] = []
        for bar in range(musical_bars):
            bass.extend(
                _bass_bar(chord_at[bar], band_at[bar], bar, under_cello=bar in cello_lead)
            )

        return _finish(Score(
            title=title,
            bpm=BPM if form is None else spec.bpm,
            bars=musical_bars,
            regimes=chosen,
            regime_samples=sample_indexes,
            slots=slots,
            high=with_rests(flute_notes, piece_eighths),
            lead=with_rests(violin.notes, piece_eighths),
            support=with_rests(cello.notes, piece_eighths),
            comp=tuple(piano),
            low=tuple(bass),
            dynamics=dynamics,
            harmonies=harmonies,
            liquidity=tuple(bands),
            phrases=phrases,
            lead_wedges=tuple(violin.wedges),
            support_wedges=tuple(cello.wedges),
            lead_dynamics=tuple(violin.dynamics),
            support_dynamics=tuple(cello.dynamics),
            high_wedges=tuple(flute_wedges),
            high_dynamics=tuple(flute_dynamics),
            comp_wedges=tuple(comp_wedges),
            comp_dynamics=tuple(comp_dynamics),
            variant="symphony",
            divisions=2,
            key=key,
            swing=False,
        ))
