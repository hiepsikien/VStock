"""One nylon guitar, three voices.

Sor keeps a study texture: the price is the top voice, chord tones fill the
weak eighths, and the root sits on the strong beats. Villa-Lobos rolls a
chord-tone pattern under that line. Barrios repeats the melody as a tremolo
and puts the thumb on the beat. All three read the written guitar bounds from
the active register, so a transposed key stays inside the same sounding range.
"""

from __future__ import annotations

from dataclasses import replace

from app.sonify.chords import Chord
from app.sonify.form import active_meter
from app.sonify.keys import active_register
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import Phrase, with_rests, written

GUITAR_BPM = {"classic": 88, "villa": 100, "barrios": 76}
_PEDAL = frozenset({"intro", "outro", "warmup", "cooldown"})
_MELODY = 74
_INNER = 56
_BASS = 68


def render_guitar_score(
    *,
    title: str,
    chosen: tuple,
    sample_indexes: tuple[int, ...] | None,
    slots: tuple,
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    dynamics: tuple[DynamicEvent, ...],
    bands: list[str],
    band_at: dict[int, str],
    musical_bars: int,
    total_eighths: int,
    bpm: int,
    ensemble: str,
    harmonies: tuple[HarmonyEvent, ...],
) -> Score:
    meter = active_meter()
    register = active_register()
    melody = _place_melody(pitches, phrases, register.guitar_treble_floor, register.guitar_treble_top)
    chord_at = {bar: slot.chord for slot in slots for bar in slot.bars()}
    kind_at = {bar: slot.section for slot in slots for bar in slot.bars()}
    if ensemble == "barrios":
        lead, support, low = _tremolo(
            melody,
            chord_at,
            kind_at,
            musical_bars,
            bpm,
            register.guitar_floor,
            register.guitar_mid_low,
            register.guitar_mid_high,
            phrases,
        )
        divisions = 4
    else:
        lead = _melody_line(melody, phrases, musical_bars)
        support, low = _arpeggio(
            melody,
            chord_at,
            kind_at,
            band_at,
            musical_bars,
            rolling=ensemble == "villa",
            bass_low=register.guitar_floor,
            bass_high=register.guitar_floor + 11,
            mid_low=register.guitar_mid_low,
            mid_high=register.guitar_mid_high,
        )
        lead = with_rests(lead, total_eighths)
        support = with_rests(list(support), total_eighths)
        low = with_rests(list(low), total_eighths)
        divisions = 2
    return Score(
        title=title,
        bpm=bpm,
        bars=musical_bars,
        regimes=chosen,  # type: ignore[arg-type]
        regime_samples=sample_indexes if sample_indexes is None else tuple(sample_indexes[:3]),  # type: ignore[arg-type]
        slots=slots,
        high=(),
        lead=_voice(lead, 1),
        support=_voice(support, 2),
        comp=(),
        low=_voice(low, 3),
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble=ensemble,  # type: ignore[arg-type]
        divisions=divisions,
        beats=meter.beats,
        beat_type=meter.beat_type,
        bar_beats=meter.quarter_beats,
    )


def _place_melody(pitches: list[int], phrases: tuple[Phrase, ...], floor: int, top: int) -> list[int]:
    placed = list(pitches)
    covered = set()
    for phrase in phrases:
        window = pitches[phrase.start : phrase.end]
        if not window:
            continue
        shift = min(
            (12, 0, -12, -24),
            key=lambda amount: sum(1 for note in window if not floor <= note + amount <= top),
        )
        for index in range(phrase.start, phrase.end):
            placed[index] = _clamp(pitches[index] + shift, floor, top)
            covered.add(index)
    for index, note in enumerate(placed):
        if index not in covered:
            placed[index] = _clamp(note, floor, top)
    return placed


def _melody_line(pitches: list[int], phrases: tuple[Phrase, ...], bars: int) -> list[NoteEvent]:
    epb = active_meter().eighths_per_bar
    events: list[NoteEvent] = []
    for bar in range(bars):
        start = bar * epb
        index = start
        end = start + epb
        while index < end:
            nxt = index + 1
            while nxt < end and pitches[nxt] == pitches[index]:
                nxt += 1
            events.extend(written(index, nxt - index, pitches[index], velocity=_MELODY))
            index = nxt
    return _slur(events, phrases)


def _arpeggio(
    melody: list[int],
    chord_at: dict[int, Chord],
    kind_at: dict[int, str],
    band_at: dict[int, str],
    bars: int,
    *,
    rolling: bool,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    strong = set(meter.strong_eighths)
    inner: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    for bar in range(bars):
        chord = chord_at[bar]
        root = _fit(chord.pitches[0] % 12, bass_low, bass_high)
        start = bar * epb
        if kind_at.get(bar) in _PEDAL:
            bass.extend(written(start, epb, root, velocity=_BASS))
            continue
        points = [point for point in meter.strong_eighths if point < epb]
        edges = [*points, epb]
        for left, right in zip(edges, edges[1:]):
            bass.extend(written(start + left, right - left, root, velocity=_BASS))
        pool = _pool(chord)
        for eighth in range(epb):
            if not rolling and eighth in strong:
                continue
            tone = _fit(pool[eighth % len(pool)], mid_low, mid_high)
            while tone >= melody[start + eighth] and tone - 12 >= mid_low:
                tone -= 12
            if tone >= melody[start + eighth] or tone <= root:
                continue
            accent = rolling and band_at.get(bar) == "f" and eighth in {0, 3, 6}
            inner.extend(
                written(
                    start + eighth,
                    1,
                    tone,
                    velocity=_INNER + (8 if accent else 0),
                    accent=accent,
                )
            )
    return inner, bass


def _tremolo(
    melody: list[int],
    chord_at: dict[int, Chord],
    kind_at: dict[int, str],
    bars: int,
    bpm: int,
    bass_low: int,
    mid_low: int,
    mid_high: int,
    phrases: tuple[Phrase, ...],
) -> tuple[tuple[NoteEvent, ...], tuple[NoteEvent, ...], tuple[NoteEvent, ...]]:
    """Thumb on the beat, the melody repeated through the rest of the beat."""
    meter = active_meter()
    epb = meter.eighths_per_bar
    grain = 1 if bpm > 100 else 2
    duration = 0.5 / grain
    line: list[NoteEvent] = []
    inner: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    for bar in range(bars):
        chord = chord_at[bar]
        root = _fit(chord.pitches[0] % 12, bass_low, bass_low + 11)
        changed = bar == 0 or chord_at.get(bar - 1) != chord
        if kind_at.get(bar) in _PEDAL:
            start = bar * epb
            index = start
            end = start + epb
            while index < end:
                nxt = index + 1
                while nxt < end and melody[nxt] == melody[index]:
                    nxt += 1
                line.extend(written(index, nxt - index, melody[index], velocity=_MELODY))
                index = nxt
            bass.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=root,
                    duration_beats=meter.quarter_beats,
                    voice=3,
                    velocity=_BASS,
                )
            )
            inner.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=None,
                    duration_beats=meter.quarter_beats,
                    voice=2,
                )
            )
            continue
        attacks = {point for point in meter.strong_eighths if point < epb}
        for slot in range(epb * grain):
            eighth = slot // grain
            beat = slot * duration
            on_thumb = eighth in attacks and slot % grain == 0
            sung = melody[bar * epb + eighth]
            if on_thumb and eighth == 0 and changed:
                color = _fit(_pool(chord)[min(1, len(_pool(chord)) - 1)], mid_low, mid_high)
                inner.append(_hit(bar, beat, duration, color if color < sung else None, 2, _INNER))
                bass.append(_hit(bar, beat, duration, None, 3, _BASS))
                line.append(_hit(bar, beat, duration, None, 1, _MELODY))
            elif on_thumb:
                inner.append(_hit(bar, beat, duration, None, 2, _INNER))
                bass.append(_hit(bar, beat, duration, root, 3, _BASS))
                line.append(_hit(bar, beat, duration, None, 1, _MELODY))
            else:
                inner.append(_hit(bar, beat, duration, None, 2, _INNER))
                bass.append(_hit(bar, beat, duration, None, 3, _BASS))
                line.append(_hit(bar, beat, duration, sung, 1, _MELODY))
    return tuple(_slur(line, phrases)), tuple(inner), tuple(bass)


def _hit(bar: int, beat: float, duration: float, midi: int | None, voice: int, velocity: int) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=voice,
        velocity=None if midi is None else velocity,
    )


def _pool(chord: Chord) -> list[int]:
    pitches = list(chord.pitches)
    if len(pitches) >= 4:
        del pitches[2]
    found: list[int] = []
    for pitch in pitches:
        pc = pitch % 12
        if pc not in found:
            found.append(pc)
    return found or [chord.pitches[0] % 12]


def _fit(pitch_class: int, low: int, high: int) -> int:
    note = low + (pitch_class - low) % 12
    while note > high:
        note -= 12
    while note < low:
        note += 12
    return note


def _clamp(note: int, low: int, high: int) -> int:
    while note > high:
        note -= 12
    while note < low:
        note += 12
    return note


def _voice(notes: tuple[NoteEvent, ...] | list[NoteEvent], voice: int) -> tuple[NoteEvent, ...]:
    return tuple(replace(note, voice=voice) for note in notes)


def _slur(events: list[NoteEvent], phrases: tuple[Phrase, ...]) -> list[NoteEvent]:
    epb = active_meter().eighths_per_bar
    result = list(events)

    def eighth(event: NoteEvent) -> int:
        return event.bar * epb + int(round(event.beat * 2))

    for phrase in phrases:
        sounding = [
            index
            for index, event in enumerate(result)
            if event.midi is not None and phrase.start <= eighth(event) < phrase.end
        ]
        if len(sounding) < 2:
            continue
        result[sounding[0]] = replace(result[sounding[0]], slur_start=True)
        result[sounding[-1]] = replace(result[sounding[-1]], slur_stop=True)
    return result
