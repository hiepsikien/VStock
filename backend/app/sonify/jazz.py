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

from itertools import combinations

from app.sonify.chords import Chord, Regime, jazz_chord
from app.sonify.form import (
    HALF_BAR,
    active_meter,
    MUSICAL_BARS,
    TOTAL_EIGHTHS,
    ChordSlot,
)
from app.sonify.keys import C_REGISTER, active_register
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import (
    BELL_MAX_EIGHTHS,
    BREAKOUT,
    CELLO_OVERLAP,
    FILL_VELOCITY,
    MIN_RISE,
    PERIOD,
    Phrase,
    Run,
    bell_budget,
    comp_pitches,
    fills,
    left_hand,
    melody_parts,
    quantize_strong_beats,
    runs_of,
    techniques,
    with_rests,
    written,
)
from app.sonify.quantize import c_major_scale

JAZZ_BPM = 82
SAX_LOW = 48  # C3: bottom of Tenor Saxophone register
SAX_CEILING = C_REGISTER.sax_ceiling  # Ab5 (G5 = 79 in C major): top of realistic Alto Saxophone range
VIBRAPHONE_APEX_TRIGGER = 79  # G5: minimum pitch for a phrase apex to trigger Vibraphone
VIBRAPHONE_LOW = 84  # C6 when the score is still in C. The live ceiling is active_register().
VIBRAPHONE_VEL_SINGLE = 58  # mp
VIBRAPHONE_VEL_CHORD = 64  # mp-mf
# Cap high-end Vibraphone accents at 15% of 240 eighths (36 eighths max across 30 bars)
VIBRAPHONE_MAX_EIGHTHS = BELL_MAX_EIGHTHS

# Dynamic-programming weights for cross-phrase Saxophone octave/register selection.
# Hierarchy:
#   DP_LARGE_LEAP_PENALTY (100_000)
#     >> DP_FIT_ALTO_COMPRESS_PENALTY (30_000)
#     >> DP_NARROW_COMPRESS_PENALTY (15_000)
#     >> DP_FIT_ALTO_SHIFT_PENALTY (5_000)
#     >> DP_ALTO_FLOOR_PENALTY (2_000)
#     >> DP_COMPRESS_PENALTY (1_000)
#     >> DP_EXTRA_OCTAVE_SHIFT_COST (150)
#     >> DP_SMALL_REVERSAL_PENALTY (10)
#     >> DP_SHIFT_CHANGE_COST (2)
# Small reversals (< 9 semitones) cost less than compressing a phrase, and phrases
# that already fit in the Alto Saxophone register (<= Ab5 = 80) stay at their exact
# 1:1 pitch (shift = 0) unless keeping them there would cause a large boundary leap
# (>= 9 semitones) against price.
SAX_LARGE_LEAP_SEMITONES = 9
DP_LARGE_LEAP_PENALTY = 100_000
DP_FIT_ALTO_COMPRESS_PENALTY = 30_000
DP_NARROW_COMPRESS_PENALTY = 15_000
DP_FIT_ALTO_SHIFT_PENALTY = 5_000
DP_ALTO_FLOOR_PENALTY = 2_000
DP_COMPRESS_PENALTY = 1_000
DP_EXTRA_OCTAVE_SHIFT_COST = 150
DP_SMALL_REVERSAL_PENALTY = 10
DP_SHIFT_CHANGE_COST = 2

SaxCandidateKey = tuple[int, int, bool]  # (octave_shift_semitones, floor_scale_idx, preserve_span)
SaxDPState = tuple[SaxCandidateKey, bool, tuple[int, int] | None]


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


def _vibraphone_window() -> tuple[int, int]:
    """C-space bell span. Positive keys shift it down so the sounding notes stay in C6–F6."""
    high = active_register().vibraphone_high
    up = C_REGISTER.vibraphone_high - high
    return VIBRAPHONE_LOW - up, high


def _bell_pitch(melody_midi: int, chord: Chord, scale_high: tuple[int, ...]) -> int:
    """Select a Vibraphone chord tone inside `scale_high`, tracking the price contour."""
    chord_tones = [m for m in scale_high if m % 12 in chord.pitch_classes]
    pool = chord_tones if chord_tones else list(scale_high)
    norm = min(1.0, max(0.0, (melody_midi - 76) / (95 - 76)))
    low, high = scale_high[0], scale_high[-1]
    target = low + norm * (high - low)
    return min(pool, key=lambda m: (abs(m - target), m))


def _high_bell_voicing(
    melody_midi: int,
    chord: Chord,
    scale_high: tuple[int, ...],
) -> tuple[int, ...]:
    """Pick bell notes in `scale_high` with no minor second, preferring chord tones.

    Three notes when the window has a clash-free triple. In C that is `(84, 86, 88)`
    or `(84, 86, 89)`, so E and F are not struck together. D's window (82–87) only
    holds B–C–D, and B–C is a minor second, so that key rings two notes instead of
    dipping below C6.
    """
    tones = tuple(sorted(scale_high))
    if len(tones) <= 1:
        return tones
    pcs = chord.pitch_classes
    lead = _bell_pitch(melody_midi, chord, tones)
    for size in (3, 2):
        choices = [
            combo
            for combo in combinations(tones, size)
            if all(b - a != 1 for a, b in zip(combo, combo[1:]))
        ]
        if not choices:
            continue
        return min(
            choices,
            key=lambda combo: (
                -sum(note % 12 in pcs for note in combo),
                sum(abs(note - lead) for note in combo),
                -sum(combo),
            ),
        )
    return (tones[-1],)


def _vibraphone_accent_part(
    phrases: tuple[Phrase, ...],
    pitches: list[int],
    band_at: dict[int, str],
    chord_at: dict[int, Chord],
    *,
    rel_span: float = 1.0,
    total_eighths: int = TOTAL_EIGHTHS,
    bell_caps: tuple[tuple[int, int, int], ...] | None = None,
) -> tuple[tuple[NoteEvent, ...], list[tuple[int, int, bool, Run]]]:
    """Build the high-end Vibraphone part (P5) strictly on Breakouts and High Apexes.

    Controlled rules:
    - Register: strictly in C6–F6 (84..89), matching the standard 3-octave Vibraphone ceiling.
    - Duty cycle: capped at <= 15% of total piece duration (<= 36 eighths) and scaled
      smoothly by relative session span (`bell_budget(rel_span)`): completely silent
      when `rel_span <= 0.5%` (flat / 1–2 tick sideway sessions), ramping linearly up to
      36 eighths at `rel_span >= 2.0%`.
    - Breakouts trigger a ringing chord in the bell window (velocity 64), two or three notes and never a minor second.
    - High phrase apexes / peaks (>= G5 = 79) trigger melodic bell notes in the bell window (velocity 58)
      that follow the price contour rather than repeating a static ceiling pitch.
    """
    max_eighths = bell_budget(rel_span, VIBRAPHONE_MAX_EIGHTHS)
    if bell_caps is None and max_eighths < 2:
        return tuple(written(0, total_eighths, None)), []

    candidates: list[tuple[int, int, int, bool, Run]] = []
    for phrase in phrases:
        colours = techniques(phrase, pitches, band_at)
        apex = phrase.apex
        for run in phrase.runs:
            is_breakout = colours.get(run.start) == BREAKOUT
            is_apex = (
                run.start == apex.start
                and phrase.rise >= MIN_RISE
                and run.midi >= VIBRAPHONE_APEX_TRIGGER
            )
            if is_breakout or is_apex or run.midi >= VIBRAPHONE_LOW:
                bar = run.start // active_meter().eighths_per_bar
                bar_end = (bar + 1) * active_meter().eighths_per_bar
                target_len = PERIOD if is_breakout else min(max(2, run.length), PERIOD)
                avail = min(bar_end - run.start, target_len)
                if avail < 2 and not (avail == 1 and run.midi >= VIBRAPHONE_LOW):
                    continue
                priority = (
                    3 if is_breakout else (2 if is_apex else 1)
                )
                candidates.append((priority, run.start, avail, is_breakout, run))

    ranked = sorted(
        candidates,
        key=lambda item: (-item[0], -item[4].midi, item[1]),
    )

    chosen_spans: list[tuple[int, int, bool, Run]] = []
    used_bars: set[int] = set()
    spent = 0
    spent_by_section: dict[tuple[int, int], int] = {}

    for _prio, start, length, is_breakout, run in ranked:
        bar = start // active_meter().eighths_per_bar
        if bar in used_bars:
            continue
        if bell_caps is None:
            room = max_eighths - spent
        else:
            cap = next((item for item in bell_caps if item[0] <= start < item[1]), None)
            if cap is None:
                continue
            room = cap[2] - spent_by_section.get((cap[0], cap[1]), 0)
        if room < 2 and not (room == 1 and run.midi >= VIBRAPHONE_LOW):
            continue
        if length > room:
            length = room
        chosen_spans.append((start, length, is_breakout, run))
        used_bars.add(bar)
        spent += length
        if bell_caps is not None:
            cap = next(item for item in bell_caps if item[0] <= start < item[1])
            key = (cap[0], cap[1])
            spent_by_section[key] = spent_by_section.get(key, 0) + length
        elif spent >= max_eighths:
            break

    chosen_spans.sort(key=lambda item: item[0])

    scale_high = c_major_scale(*_vibraphone_window())
    events: list[NoteEvent] = []
    cursor = 0
    for start, length, is_breakout, run in chosen_spans:
        if start > cursor:
            events.extend(written(cursor, start - cursor, None))
        bar = start // active_meter().eighths_per_bar
        chord = chord_at[bar]
        if is_breakout:
            pieces = written(
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
                _bell_pitch(pitches[eighth], chord_at[eighth // active_meter().eighths_per_bar], scale_high)
                for eighth in range(start, start + length)
            ]
            bell_runs = [
                Run(start + r.start, r.length, r.midi)
                for r in runs_of(bell_line, 0, len(bell_line))
            ]
            has_slur = len(bell_runs) > 1
            for r_idx, b_run in enumerate(bell_runs):
                events.extend(
                    written(
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

    if cursor < total_eighths:
        events.extend(written(cursor, total_eighths - cursor, None))
    return tuple(events), chosen_spans


def _compress_phrase_to_bounds(
    pitches: list[int],
    phrase: Phrase,
    chord_at: dict[int, Chord] | None,
    scale: tuple[int, ...],
    ceiling_idx: int,
    target_bot_idx: int,
    target_top_idx: int,
) -> list[int]:
    """Monotonically compress one phrase onto scale[target_bot_idx..target_top_idx] and snap strong beats."""
    top = max(r.midi for r in phrase.runs)
    bot = min(r.midi for r in phrase.runs)
    top_idx = scale.index(top)
    bot_idx = scale.index(bot)
    span_idx = max(1, top_idx - bot_idx)
    out: list[int] = []
    for eighth in range(phrase.start, phrase.end):
        idx = scale.index(pitches[eighth])
        rel = (idx - bot_idx) / span_idx
        mapped_idx = round(target_bot_idx + rel * (target_top_idx - target_bot_idx))
        mapped_idx = max(0, min(ceiling_idx, mapped_idx))
        out.append(scale[mapped_idx])
    if chord_at:
        bar_start = phrase.start // active_meter().eighths_per_bar
        pad_len = phrase.start % active_meter().eighths_per_bar
        padded = [out[0]] * pad_len + out
        rel_chords = {b - bar_start: c for b, c in chord_at.items()}
        out = quantize_strong_beats(
            padded, rel_chords, scale[: ceiling_idx + 1]
        )[pad_len:]

    # Preserve 1-step pitch changes on non-strong-beat runs that flattened into the preceding run.
    for r_idx in range(1, len(phrase.runs)):
        prev_r = phrase.runs[r_idx - 1]
        curr_r = phrase.runs[r_idx]
        if curr_r.midi == prev_r.midi:
            continue
        s_off = curr_r.start - phrase.start
        e_off = curr_r.end - phrase.start
        prev_m = out[s_off - 1]
        if all(out[o] == prev_m for o in range(s_off, e_off)) and all(
            (curr_r.start + o) % active_meter().eighths_per_bar not in active_meter().strong_eighths
            for o in range(curr_r.length)
        ):
            step = 1 if curr_r.midi > prev_r.midi else -1
            cand_idx = scale.index(prev_m) + step
            if target_bot_idx <= cand_idx <= target_top_idx:
                cand_m = scale[cand_idx]
                if r_idx + 1 < len(phrase.runs):
                    next_r = phrase.runs[r_idx + 1]
                    next_m = out[next_r.start - phrase.start]
                    if (next_r.midi - curr_r.midi) * (next_m - cand_m) < 0:
                        continue
                for o in range(s_off, e_off):
                    out[o] = cand_m
    return out


def _phrase_vibe_spans(
    phrase: Phrase,
    chosen_spans: list[tuple[int, int, bool, Run]],
) -> tuple[list[tuple[int, int]], int, int]:
    """Return normalized Vibraphone yield spans, minimum required octave shift, and max exact shift."""
    p_vibe = [
        (st, st + ln)
        for st, ln, is_b, r in chosen_spans
        if not is_b
        and st >= phrase.start
        and st + ln <= phrase.end
        and r.midi > active_register().sax_ceiling
    ]
    norm_vibe = [
        (ys, phrase.end if ye == phrase.end - 1 else ye)
        for ys, ye in p_vibe
    ]
    rem_high = [
        r.midi
        for r in phrase.runs
        if r.midi > active_register().sax_ceiling
        and not any(ys <= r.start and r.end <= ye for ys, ye in norm_vibe)
    ]
    top = max(r.midi for r in phrase.runs)
    bot = min(r.midi for r in phrase.runs)
    if not rem_high:
        req_shift = 0
    elif top - 12 <= active_register().sax_ceiling:
        req_shift = 12
    else:
        req_shift = 24
    max_exact_shift = 24 if bot - 24 >= SAX_LOW else (12 if bot - 12 >= SAX_LOW else 0)
    return norm_vibe, req_shift, max_exact_shift


def _realize_sax_phrase(
    pitches: list[int],
    phrase: Phrase,
    chord_at: dict[int, Chord] | None,
    scale: tuple[int, ...],
    ceiling_idx: int,
    req_shift: int,
    max_exact_shift: int,
    shift: int,
    floor_idx: int,
    preserve_span: bool,
) -> tuple[list[int], bool]:
    """Realize one phrase at `shift` semitones down, returning `(phrase_pitches, is_exact)`."""
    top = max(r.midi for r in phrase.runs)
    bot = min(r.midi for r in phrase.runs)
    floor_midi = scale[floor_idx]
    can_exact = top - shift <= active_register().sax_ceiling or (shift == 0 and req_shift == 0)
    if can_exact and shift <= max_exact_shift and bot - shift >= floor_midi:
        return [pitches[e] - shift for e in range(phrase.start, phrase.end)], True
    t_top = min(ceiling_idx, scale.index(max(floor_midi, top - shift)))
    span = scale.index(top) - scale.index(bot)
    t_bot = max(floor_idx, min(t_top, t_top - span))
    if preserve_span:
        t_top = min(ceiling_idx, max(t_top, t_bot + span))
    return (
        _compress_phrase_to_bounds(
            pitches, phrase, chord_at, scale, ceiling_idx, t_bot, t_top
        ),
        False,
    )


def _build_phrase_candidates(
    pitches: list[int],
    phrase: Phrase,
    chord_at: dict[int, Chord] | None,
    scale: tuple[int, ...],
    ceiling_idx: int,
    alto_low_idx: int,
    req_shift: int,
    max_exact_shift: int,
    *,
    include_extra_floors: bool = False,
) -> dict[SaxCandidateKey, tuple[list[int], bool]]:
    """Build deduplicated exact and compressed octave-shift candidates for a phrase."""
    cands: dict[SaxCandidateKey, tuple[list[int], bool]] = {}
    seen: set[tuple[object, ...]] = set()
    top = max(r.midi for r in phrase.runs)
    bot = min(r.midi for r in phrase.runs)
    span = scale.index(top) - scale.index(bot)

    keys: list[SaxCandidateKey] = []
    for shift in (0, 12, 24):
        if shift < req_shift:
            continue
        keys.append((shift, 0, True))
        if shift > 0:
            keys.append((shift, alto_low_idx, True))
        if shift > req_shift:
            keys.append((shift, 0, False))
            if shift > 0:
                keys.append((shift, alto_low_idx, False))
    if include_extra_floors:
        for f_extra in range(alto_low_idx + 1, ceiling_idx):
            keys.append((req_shift, f_extra, True))

    for key in keys:
        shift, floor_idx, preserve_span = key
        floor_midi = scale[floor_idx]
        can_exact = top - shift <= active_register().sax_ceiling or (shift == 0 and req_shift == 0)
        if can_exact and shift <= max_exact_shift and bot - shift >= floor_midi:
            sig: tuple[object, ...] = ("exact", shift)
        else:
            t_top = min(ceiling_idx, scale.index(max(floor_midi, top - shift)))
            t_bot = max(floor_idx, min(t_top, t_top - span))
            if preserve_span:
                t_top = min(ceiling_idx, max(t_top, t_bot + span))
            sig = ("comp", t_bot, t_top)
        if sig in seen:
            continue
        seen.add(sig)
        cands[key] = _realize_sax_phrase(
            pitches,
            phrase,
            chord_at,
            scale,
            ceiling_idx,
            req_shift,
            max_exact_shift,
            shift,
            floor_idx,
            preserve_span,
        )
    return cands


def _candidate_base_cost(
    key: SaxCandidateKey,
    is_exact: bool,
    req_shift: int,
) -> int:
    """Compute the intrinsic DP cost of selecting `key` for a phrase."""
    shift, floor_idx, preserve_span = key
    extra_octaves = (shift - req_shift) // 12
    compress_cost = (
        0
        if is_exact
        else (DP_FIT_ALTO_COMPRESS_PENALTY if req_shift == 0 else DP_COMPRESS_PENALTY)
    )
    shift_cost = (
        extra_octaves * DP_FIT_ALTO_SHIFT_PENALTY
        if req_shift == 0
        else extra_octaves * DP_EXTRA_OCTAVE_SHIFT_COST
    )
    narrow_cost = 0 if preserve_span else DP_NARROW_COMPRESS_PENALTY
    floor_cost = DP_ALTO_FLOOR_PENALTY + floor_idx * 10 if floor_idx > 0 else 0
    return compress_cost + narrow_cost + shift_cost + floor_cost


def _simulate_alto_handoff(
    phrase: Phrase,
    phrase_pitches: list[int],
    vibe_spans: list[tuple[int, int]],
    on_tenor_in: bool,
) -> tuple[bool, tuple[int, int] | None, tuple[int, int] | None]:
    """Simulate Alto/Tenor Saxophone handoff (matching `_instrument_segments`) for one phrase."""
    on_tenor = on_tenor_in
    alto_pts: list[tuple[int, int]] = []
    phrase_runs = runs_of(phrase_pitches, 0, len(phrase_pitches))
    for r_idx, run in enumerate(phrase_runs):
        next_on_tenor = (
            run.midi < active_register().cello_handback
            if on_tenor
            else run.midi < active_register().violin_lowest
        )
        if on_tenor and not next_on_tenor and r_idx > 0:
            prev_r = phrase_runs[r_idx - 1]
            if prev_r.midi >= active_register().violin_lowest and prev_r.length >= 2:
                lead = min(CELLO_OVERLAP, prev_r.length // 2)
                for off in range(prev_r.end - lead, prev_r.end):
                    eighth = phrase.start + off
                    if not any(ys <= eighth < ye for ys, ye in vibe_spans):
                        alto_pts.append((eighth, prev_r.midi))
        on_tenor = next_on_tenor
        if not on_tenor:
            for off in range(run.start, run.end):
                eighth = phrase.start + off
                if not any(ys <= eighth < ye for ys, ye in vibe_spans):
                    alto_pts.append((eighth, run.midi))
    return (
        on_tenor,
        alto_pts[0] if alto_pts else None,
        alto_pts[-1] if alto_pts else None,
    )


def _boundary_transition_penalty(
    pitches: list[int],
    prev_phrase: Phrase,
    curr_phrase: Phrase,
    prev_pitches: list[int],
    curr_pitches: list[int],
    prev_shift: int,
    curr_shift: int,
    last_alto_prev: tuple[int, int] | None,
    first_alto_curr: tuple[int, int] | None,
) -> int:
    """Compute the DP transition penalty across a phrase boundary."""
    dp_dir = pitches[curr_phrase.start] - pitches[prev_phrase.end - 1]
    ds_dir = curr_pitches[0] - prev_pitches[-1]
    rev_dir = (
        (dp_dir > 0 and ds_dir < 0)
        or (dp_dir < 0 and ds_dir > 0)
        or (dp_dir == 0 and ds_dir != 0)
    )
    big_dir = rev_dir and abs(ds_dir) >= SAX_LARGE_LEAP_SEMITONES

    rev_alto = False
    big_alto = False
    if last_alto_prev is not None and first_alto_curr is not None:
        e0, m0 = last_alto_prev
        e1, m1 = first_alto_curr
        dp_a = pitches[e1] - pitches[e0]
        ds_a = m1 - m0
        rev_alto = (
            (dp_a > 0 and ds_a < 0)
            or (dp_a < 0 and ds_a > 0)
            or (dp_a == 0 and ds_a != 0)
        )
        big_alto = rev_alto and abs(ds_a) >= SAX_LARGE_LEAP_SEMITONES

    if big_alto or big_dir:
        return DP_LARGE_LEAP_PENALTY
    if rev_alto or rev_dir:
        return DP_SMALL_REVERSAL_PENALTY
    return abs(curr_shift - prev_shift) * DP_SHIFT_CHANGE_COST


def _solve_sax_dp(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    phrase_vibes: list[list[tuple[int, int]]],
    min_shift: list[int],
    candidates: list[dict[SaxCandidateKey, tuple[list[int], bool]]],
) -> tuple[list[SaxCandidateKey], int]:
    """Run DP over phrase octave/register candidates and return `(chosen_keys, min_cost)`."""
    n = len(phrases)
    dp: list[dict[SaxDPState, int]] = [{} for _ in range(n)]
    parent: list[dict[SaxDPState, SaxDPState | None]] = [{} for _ in range(n)]

    for key, (sl, is_exact) in candidates[0].items():
        s_val = key[0]
        vibes = phrase_vibes[0] if (s_val == 0 and is_exact) else []
        on_tenor_out, _, last_a = _simulate_alto_handoff(phrases[0], sl, vibes, False)
        st: SaxDPState = (key, on_tenor_out, last_a)
        cost = _candidate_base_cost(key, is_exact, min_shift[0])
        if st not in dp[0] or cost < dp[0][st]:
            dp[0][st] = cost
            parent[0][st] = None

    for i in range(1, n):
        for k_curr, (sl_curr, exact_curr) in candidates[i].items():
            s_curr = k_curr[0]
            base_c = _candidate_base_cost(k_curr, exact_curr, min_shift[i])
            vibes = phrase_vibes[i] if (s_curr == 0 and exact_curr) else []
            sim_by_tenor = {
                False: _simulate_alto_handoff(phrases[i], sl_curr, vibes, False),
                True: _simulate_alto_handoff(phrases[i], sl_curr, vibes, True),
            }
            for st_prev, prev_c in dp[i - 1].items():
                k_prev, on_tenor_prev, last_a_prev = st_prev
                s_prev = k_prev[0]
                sl_prev, _ = candidates[i - 1][k_prev]
                on_tenor_out, first_a_curr, last_a_curr = sim_by_tenor[on_tenor_prev]
                new_last_a = last_a_curr if last_a_curr is not None else last_a_prev
                st_curr: SaxDPState = (k_curr, on_tenor_out, new_last_a)
                pen = _boundary_transition_penalty(
                    pitches,
                    phrases[i - 1],
                    phrases[i],
                    sl_prev,
                    sl_curr,
                    s_prev,
                    s_curr,
                    last_a_prev,
                    first_a_curr,
                )
                tot = prev_c + base_c + pen
                if st_curr not in dp[i] or tot < dp[i][st_curr]:
                    dp[i][st_curr] = tot
                    parent[i][st_curr] = st_prev

    best_st = min(dp[-1], key=lambda st_key: dp[-1][st_key])
    best_cost = dp[-1][best_st]
    chosen_k: list[SaxCandidateKey] = [(0, 0, True)] * n
    curr_st: SaxDPState | None = best_st
    for i in range(n - 1, -1, -1):
        assert curr_st is not None
        chosen_k[i] = curr_st[0]
        curr_st = parent[i][curr_st]
    return chosen_k, best_cost


def _sax_melody_curve(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    chosen_spans: list[tuple[int, int, bool, Run]],
    chord_at: dict[int, Chord] | None = None,
    total_eighths: int = TOTAL_EIGHTHS,
    melody_scale: tuple[int, ...] | None = None,
) -> tuple[list[int], tuple[Phrase, ...], list[tuple[int, int]]]:
    """Keep phrases within the Saxophone register (<= Ab5 = 80) at full 1:1 resolution.

    Phrases that already fit within <= Ab5 (80), or whose only notes above Ab5 are
    covered by a non-breakout Vibraphone yield span, stay at their exact 1:1 pitches
    unless keeping them at 1:1 would create a large contrary leap (>= 9 semitones)
    at a phrase boundary. Dynamic programming across phrases selects the octave shift
    (0, 12, or 24 semitones) and register bounds for each phrase while re-quantizing
    any compressed phrase on strong beats via `quantize_strong_beats`.
    """
    if not phrases:
        return list(pitches), phrases, []

    scale = melody_scale if melody_scale is not None else c_major_scale(SAX_LOW, 96)
    ceiling = active_register().sax_ceiling
    floor = active_register().violin_lowest
    ceiling_idx = max(index for index, midi in enumerate(scale) if midi <= ceiling)
    alto_low_idx = min(index for index, midi in enumerate(scale) if midi >= floor)

    phrase_vibes: list[list[tuple[int, int]]] = []
    min_shift: list[int] = []
    max_exact: list[int] = []
    candidates: list[dict[SaxCandidateKey, tuple[list[int], bool]]] = []
    for phrase in phrases:
        norm_vibe, req_shift, max_exact_shift = _phrase_vibe_spans(phrase, chosen_spans)
        phrase_vibes.append(norm_vibe)
        min_shift.append(req_shift)
        max_exact.append(max_exact_shift)
        candidates.append(
            _build_phrase_candidates(
                pitches,
                phrase,
                chord_at,
                scale,
                ceiling_idx,
                alto_low_idx,
                req_shift,
                max_exact_shift,
            )
        )

    chosen_k, best_cost = _solve_sax_dp(
        pitches, phrases, phrase_vibes, min_shift, candidates
    )
    if best_cost >= DP_FIT_ALTO_SHIFT_PENALTY:
        candidates = [
            _build_phrase_candidates(
                pitches,
                phrase,
                chord_at,
                scale,
                ceiling_idx,
                alto_low_idx,
                min_shift[i],
                max_exact[i],
                include_extra_floors=True,
            )
            for i, phrase in enumerate(phrases)
        ]
        chosen_k, _ = _solve_sax_dp(
            pitches, phrases, phrase_vibes, min_shift, candidates
        )

    yield_spans: list[tuple[int, int]] = []
    sax_pitches = list(pitches)
    temp_phrases: list[Phrase] = []
    for i, phrase in enumerate(phrases):
        k = chosen_k[i]
        s_val = k[0]
        sl, is_exact = candidates[i][k]
        sax_pitches[phrase.start : phrase.end] = sl
        if s_val == 0 and is_exact:
            if phrase_vibes[i]:
                yield_spans.extend(phrase_vibes[i])
            temp_phrases.append(phrase)
        elif is_exact:
            runs = [Run(r.start, r.length, r.midi - s_val) for r in phrase.runs]
            temp_phrases.append(Phrase(phrase.start, phrase.end, tuple(runs), False))
        else:
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
            and p.end < total_eighths
            and sax_pitches[p.end] == sax_pitches[p.end - 1],
        )
        for i, p in enumerate(temp_phrases)
    )
    return sax_pitches, sax_phrases, yield_spans


RHODES_RIGHT_LOW = 53  # F3: lowest right-hand note, strictly above left-hand F2–E3 (41–52)
RHODES_RIGHT_HIGH = 76  # E5: ceiling when lifting a clashing 9th above a low 3rd


def _rhodes_voicing(chord: Chord) -> tuple[int, tuple[int, ...]]:
    """Return left-hand root (F2–E3) and right-hand guide+9th tones in F3–E5 without semitone clashes."""
    root, guide = comp_pitches(chord)
    if len(chord.pitches) >= 5:
        third_pc = chord.pitches[1] % 12
        third_midi = next((m for m in guide if m % 12 == third_pc), guide[0])
        other_guide = tuple(m for m in guide if m != third_midi)
        ninth_pc = chord.pitches[4] % 12
        ninth_midi = 60 + ninth_pc  # C4–B4
        if ninth_midi < min(guide):
            ninth_midi += 12
        if ninth_midi <= 72 and ninth_midi not in guide:
            voiced = sorted((*guide, ninth_midi))
            if any(b - a < 2 for a, b in zip(voiced, voiced[1:])):
                # When the 3rd clashes by 1 semitone with the 9th (e.g. E4–F4 on Dm9),
                # open the 3rd down an octave if it stays >= F3 (53); otherwise lift the 9th.
                if abs(third_midi - ninth_midi) == 1 and third_midi - 12 >= RHODES_RIGHT_LOW:
                    voiced = sorted((*other_guide, third_midi - 12, ninth_midi))
                elif ninth_midi + 12 <= RHODES_RIGHT_HIGH:
                    voiced = sorted((*guide, ninth_midi + 12))
            if (
                voiced[0] >= RHODES_RIGHT_LOW
                and voiced[-1] <= RHODES_RIGHT_HIGH
                and all(b - a >= 2 for a, b in zip(voiced, voiced[1:]))
            ):
                return root, tuple(voiced)
    return root, guide


def _rhodes_comping_part(
    slots: tuple[ChordSlot, ...],
    cadences: list[tuple[Run, str]],
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
    total_eighths: int = TOTAL_EIGHTHS,
) -> list[NoteEvent]:
    """Build Fender Rhodes Piano (P3) with Charleston syncopation and Jazz fills.

    On active phrase bars where no cadence fill starts in the first half-bar, Rhodes
    plays a classic Jazz Charleston comping figure on beats 1.0 (dotted quarter, 1.5 beats)
    and 1.5 ("and of 2", eighth note, 0.5 beats). On intro/outro or quiet bars ('p'),
    it plays a warm half-note chord cushion on beat 1.0.
    """
    cadence_fills = fills(cadences, chord_at)
    first_fill: dict[int, int] = {}
    for start, _length, _midi in cadence_fills:
        bar = start // active_meter().eighths_per_bar
        first_fill[bar] = min(first_fill.get(bar, start), start)

    right_events: list[NoteEvent] = []
    for slot in slots:
        _root, voicing = _rhodes_voicing(slot.chord)
        for bar in slot.bars():
            meter = active_meter()
            signature = (meter.beats, meter.beat_type)
            if signature == (12, 8):
                for beat in (1.5, 4.5):
                    for midi in voicing:
                        right_events.append(
                            NoteEvent(bar=bar, beat=beat, midi=midi, duration_beats=1.5, voice=1)
                        )
                continue
            if signature == (3, 4) and (slot.section in ("phrase", "warmup") or band_at[bar] != "p"):
                if bar % 2 == 0:
                    for midi in voicing:
                        right_events.append(
                            NoteEvent(bar=bar, beat=0.0, midi=midi, duration_beats=1.5, voice=1)
                        )
                        right_events.append(
                            NoteEvent(
                                bar=bar, beat=1.5, midi=midi, duration_beats=0.5, voice=1, tenuto=True
                            )
                        )
                else:
                    for beat in (0.0, 2.0):
                        for midi in voicing:
                            right_events.append(
                                NoteEvent(bar=bar, beat=beat, midi=midi, duration_beats=1.0, voice=1)
                            )
                continue
            downbeat = bar * meter.eighths_per_bar
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

    for start, length, midi in cadence_fills:
        right_events.extend(written(start, length, midi, velocity=FILL_VELOCITY))

    piano: list[NoteEvent] = list(with_rests(right_events, total_eighths))
    for slot in slots:
        piano.extend(left_hand(slot))
    return piano


def _approach_note(
    next_chord: Chord, from_pitch: int, scale_bass: tuple[int, ...], fallback: int
) -> int:
    next_root = next_chord.bass_midi
    if next_root not in scale_bass:
        return fallback
    index = scale_bass.index(next_root)
    above = scale_bass[min(len(scale_bass) - 1, index + 1)]
    below = scale_bass[max(0, index - 1)]
    chosen = above if abs(above - from_pitch) <= abs(below - from_pitch) else below
    if chosen == next_root:
        return fallback
    return chosen


def _walk_waltz(
    chord: Chord,
    next_chord: Chord,
    band: str,
    bar: int,
    section: str,
    scale_bass: tuple[int, ...],
    root: int,
    fifth: int,
) -> list[NoteEvent]:
    third = root + ((chord.pitches[1] % 12 - chord.pitches[0] % 12) % 12)
    lead = _approach_note(next_chord, fifth, scale_bass, fifth)
    if band in ("p",) or section in ("intro", "warmup", "outro", "cooldown"):
        return [
            NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=2.0, voice=1),
            NoteEvent(bar=bar, beat=2.0, midi=lead, duration_beats=1.0, voice=1),
        ]
    middle = third if bar % 2 == 0 else fifth
    return [
        NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=1.0, midi=middle, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=2.0, midi=lead, duration_beats=1.0, voice=1),
    ]


def _walk_ballad(
    chord: Chord,
    next_chord: Chord,
    band: str,
    bar: int,
    section: str,
    scale_bass: tuple[int, ...],
    root: int,
    fifth: int,
) -> list[NoteEvent]:
    if band == "p" or section in ("intro", "warmup", "outro", "cooldown"):
        return [
            NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=3.0, voice=1),
            NoteEvent(bar=bar, beat=3.0, midi=fifth, duration_beats=3.0, voice=1),
        ]
    third = root + ((chord.pitches[1] % 12 - chord.pitches[0] % 12) % 12)
    into_next = _approach_note(next_chord, fifth, scale_bass, fifth)
    into_bar = _approach_note(chord, root, scale_bass, fifth)
    return [
        NoteEvent(bar=bar, beat=0.0, midi=root, duration_beats=1.5, voice=1),
        NoteEvent(bar=bar, beat=1.5, midi=third, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=2.5, midi=into_bar, duration_beats=0.5, voice=1),
        NoteEvent(bar=bar, beat=3.0, midi=fifth, duration_beats=1.5, voice=1),
        NoteEvent(bar=bar, beat=4.5, midi=third, duration_beats=1.0, voice=1),
        NoteEvent(bar=bar, beat=5.5, midi=into_next, duration_beats=0.5, voice=1),
    ]


def _walking_bass_bar(
    chord: Chord,
    next_chord: Chord,
    band: str,
    bar: int,
    section: str,
    scale_bass: tuple[int, ...],
    mode: str = "major",
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
    from app.sonify.chords import fifth_above_bass

    fifth = fifth_above_bass(chord)
    if mode == "minor" and (
        chord.name in ("G", "G7") or next_chord.name in ("G", "G7")
    ):
        from app.sonify.quantize import leading_scale

        scale_bass = leading_scale(scale_bass)
    meter = active_meter()
    signature = (meter.beats, meter.beat_type)
    if signature == (3, 4):
        return _walk_waltz(chord, next_chord, band, bar, section, scale_bass, root, fifth)
    if signature == (12, 8):
        return _walk_ballad(chord, next_chord, band, bar, section, scale_bass, root, fifth)
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
    chosen: tuple[Regime, ...],
    sample_indexes: tuple[int, ...] | None,
    slots: tuple[ChordSlot, ...],
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    dynamics: tuple[DynamicEvent, ...],
    bands: list[str],
    band_at: dict[int, str],
    rel_span: float = 1.0,
    musical_bars: int = MUSICAL_BARS,
    total_eighths: int = TOTAL_EIGHTHS,
    bpm: int = JAZZ_BPM,
    bell_caps: tuple[tuple[int, int, int], ...] | None = None,
    mode: str = "major",
) -> Score:
    """Assemble the 30-bar Lo-Fi / Cool Jazz score."""
    jazz_slots, harmonies, chord_at = _promote_jazz_slots(slots)
    section_at = {bar: slot.section for slot in jazz_slots for bar in slot.bars()}

    vibraphone, chosen_spans = _vibraphone_accent_part(
        phrases,
        pitches,
        band_at,
        chord_at,
        rel_span=rel_span,
        total_eighths=total_eighths,
        bell_caps=bell_caps,
    )
    from app.sonify.quantize import C_NATURAL_MINOR_PCS, scale_from_classes

    if mode == "minor":
        classes = C_NATURAL_MINOR_PCS | frozenset({11})
        melody_scale = scale_from_classes(SAX_LOW, 96, classes)
        scale_bass = scale_from_classes(33, 60, classes)
    else:
        melody_scale = None
        scale_bass = c_major_scale(33, 60)
    sax_pitches, sax_phrases, yield_spans = _sax_melody_curve(
        pitches, phrases, chosen_spans, chord_at, total_eighths, melody_scale
    )
    alto_sax, tenor_sax, cadences = melody_parts(
        sax_pitches, sax_phrases, band_at, yield_spans=yield_spans, piece_eighths=total_eighths
    )

    rhodes = _rhodes_comping_part(jazz_slots, cadences, chord_at, band_at, total_eighths)

    bass: list[NoteEvent] = []
    for bar in range(musical_bars):
        next_chord = chord_at[min(musical_bars - 1, bar + 1)]
        bass.extend(
            _walking_bass_bar(
                chord_at[bar],
                next_chord,
                band_at[bar],
                bar,
                section_at[bar],
                scale_bass,
                mode,
            )
        )

    return Score(
        title=title,
        bpm=bpm,
        bars=musical_bars,
        regimes=chosen,
        regime_samples=sample_indexes,
        slots=jazz_slots,
        high=vibraphone,
        lead=with_rests(alto_sax.notes, total_eighths),
        support=with_rests(tenor_sax.notes, total_eighths),
        comp=tuple(rhodes),
        low=tuple(bass),
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=sax_phrases,
        lead_wedges=tuple(alto_sax.wedges),
        support_wedges=tuple(tenor_sax.wedges),
        lead_dynamics=tuple(alto_sax.dynamics),
        support_dynamics=tuple(tenor_sax.dynamics),
        variant="jazz",
        divisions=2,
        swing=True,
    )
