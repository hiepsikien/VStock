"""Resolve authored pitches and placement into render-context events.

This module is the bridge between the declarative Phase 0 layer in
``app.studio.texture_spec`` and one render context. It deliberately does three
things and nothing else:

* ``resolve_pitch`` reads a ``PitchRef`` against the *same* context the
  renderer uses. ``melody_eighth`` indexes ``ctx.melody``, the chord kinds read
  the actual ``Chord`` object, and ``scale_step`` walks the runtime mode scale
  inside the context's lead register. It never rebuilds a price-to-melody
  transform.
* ``authored_to_events`` copies authored placement and notation into
  ``NoteEvent`` values. Only the pitch is derived; bar/beat/duration/voice/
  staff/tie/slur/accent are preserved.
* ``check_authored_playable`` reports the render-context half of
  ``assert_authored_playable`` (see ``docs/sonify-texture-studio.md`` §6.6).

The module is read-only with respect to the renderer. Importing it does not
import ``guitar_patterns``, register a sentence, or render a note; the fret
table below mirrors the runtime table without loading the pattern module. It
does not own a runtime interpreter and it never mutates ``SENTENCE_SPECS``.

Errors that prevent a single value from resolving are ``TextureResolveError``
(a ``ValueError``) carrying the authored path, for example
``authored.events[0].pitch.eighth``. Playability problems are returned as
``TextureError`` records from ``texture_spec``; ``PlayableReport`` also names
the checks that could not run because the authored data does not carry them.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.sonify.chords import C
from app.sonify.guitar import _melody_scale
from app.sonify.model import NoteEvent
from app.studio.texture_spec import (
    PITCH_KINDS,
    AuthoredEvent,
    PitchRef,
    TextureError,
    TextureSpec,
)

__all__ = [
    "HAND_SPAN_LIMIT",
    "PlayableReport",
    "TextureResolveError",
    "authored_to_events",
    "check_authored_playable",
    "resolve_pitch",
]

# Sounding limits from the runtime guitar profiles. A context may narrow them
# with its own ``bass_low``/``ceiling`` fields.
GUITAR_LOW = 40
GUITAR_HIGH = 83
HAND_SPAN_LIMIT = 5

_TIE_START = frozenset({"start", "continue", "next_bar"})
_TIE_STOP = frozenset({"stop", "continue"})
_SLUR_START = frozenset({"start", "continue"})
_SLUR_STOP = frozenset({"stop", "continue"})

_EPSILON = 1e-9
_MAX_FRET = (12, 12, 12, 17, 19, 19)  # string 6 → 1, mirrors guitar_patterns

# Scientific pitch notation, including the flat/sharp spellings Gemini uses.
_PITCH_NAME = re.compile(r"^\s*([A-Ga-g])([#b♯♭]?)(-?\d+)\s*$")
_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACCIDENTAL = {"#": 1, "♯": 1, "b": -1, "♭": -1, "": 0}

SKIPPED_PROFILE = "profile"
SKIPPED_STRING_FRET = "string/fret"
SKIPPED_WRITTEN_SOUNDING = "written/sounding"
SKIPPED_HAND_SPAN = "hand span"


class TextureResolveError(ValueError):
    """A pitch or authored event cannot be resolved in this render context."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


class PlayableReport(list):
    """The playability problems, plus the checks the data could not support.

    It is a real ``list`` of ``TextureError`` records, so ``report == []`` is
    the pass condition. ``skipped`` names checks that genuinely need data the
    authored event does not carry (tab metadata, a renderer profile, or both
    pitch spellings). ``partial`` mirrors the Studio validation contract.
    """

    def __init__(
        self,
        problems: Sequence[TextureError] = (),
        *,
        skipped: Sequence[str] = (),
    ) -> None:
        super().__init__(problems)
        self.skipped: tuple[str, ...] = tuple(skipped)

    @property
    def partial(self) -> bool:
        return bool(self.skipped)


# ---------------------------------------------------------------------------
# Pitch
# ---------------------------------------------------------------------------


def resolve_pitch(
    ref: PitchRef,
    ctx: Any,
    *,
    bar: int = 0,
    melody_length: int | None = None,
) -> int:
    """Resolve one declarative pitch reference to a MIDI number.

    ``melody_eighth`` uses ``ctx.melody[eighth + offset]``. Unlike the runtime
    ``_melody_at`` (which clamps to the last note), an out-of-range reference
    raises: a late phrase note must not silently become the final melody note.

    ``chord_degree``/``chord_root`` read the chord at ``bar`` through
    ``ctx.chord(bar)`` (or a plain ``ctx.chord_at`` mapping). Degree 1 is the
    chord's actual root; higher degrees follow the chord's written pitches and
    continue by octaves when they run past the seventh/ninth.

    ``scale_step`` walks ``_melody_scale(ctx.mode)`` inside the context's lead
    register (``ctx.treble_floor .. ctx.treble_top``). The anchor is the scale
    tone nearest the middle of that register; steps are then diatonic and clamp
    at the register edges. This mirrors the runtime ``_walk`` helper without
    importing the pattern module.
    """
    if not isinstance(ref, PitchRef):
        raise TextureResolveError("pitch", "expected a PitchRef")
    if ref.kind not in PITCH_KINDS:
        raise TextureResolveError("pitch.kind", f"unknown pitch kind {ref.kind!r}")

    if ref.kind == "melody_eighth":
        return _resolve_melody(ctx, ref, melody_length=melody_length)
    if ref.kind == "chord_root":
        return _resolve_chord(ctx, bar, 1)
    if ref.kind == "chord_bass":
        return _resolve_chord_bass(ctx, bar)
    if ref.kind == "chord_degree":
        degree = _integer(ref.degree, "pitch.degree", "degree")
        if degree < 1:
            raise TextureResolveError("pitch.degree", "must be >= 1")
        return _resolve_chord(ctx, bar, degree)
    if ref.kind == "chord_mid":
        degree = _integer(ref.degree, "pitch.degree", "degree")
        if degree < 1:
            raise TextureResolveError("pitch.degree", "must be >= 1")
        return _resolve_chord_mid(ctx, bar, degree)
    if ref.kind == "scale_step":
        steps = _integer(ref.steps, "pitch.steps", "steps")
        return _resolve_scale_step(ctx, steps)
    return _resolve_literal(ref)


def _resolve_melody(
    ctx: Any,
    ref: PitchRef,
    *,
    melody_length: int | None,
) -> int:
    melody = getattr(ctx, "melody", None)
    if not isinstance(melody, Sequence) or isinstance(melody, (str, bytes)):
        raise TextureResolveError("pitch", "render context has no melody array")

    eighth = _integer(ref.eighth, "pitch.eighth", "eighth")
    offset = 0 if ref.offset is None else _integer(ref.offset, "pitch.offset", "offset")
    if eighth < 0:
        raise TextureResolveError("pitch.eighth", "must be >= 0")
    if offset < 0:
        raise TextureResolveError("pitch.offset", "must be >= 0")

    length = len(melody)
    if melody_length is not None:
        declared = _integer(melody_length, "melody_length", "melody_length")
        if declared < 0:
            raise TextureResolveError("melody_length", "must be >= 0")
        length = min(length, declared)

    if eighth >= length:
        raise TextureResolveError(
            "pitch.eighth",
            f"eighth {eighth} is outside melody length {length}",
        )
    if eighth + offset >= length:
        raise TextureResolveError(
            "pitch.offset",
            f"eighth + offset {eighth + offset} is outside melody length {length}",
        )
    return int(melody[eighth + offset])


def _resolve_chord(ctx: Any, bar: int, degree: int) -> int:
    if not isinstance(bar, int) or isinstance(bar, bool):
        raise TextureResolveError("bar", "bar must be an integer")
    chord = _chord_at(ctx, bar)
    pitches = getattr(chord, "pitches", None)
    if not isinstance(pitches, Sequence) or isinstance(pitches, (str, bytes)) or not pitches:
        raise TextureResolveError("pitch", "render context chord has no pitches")
    index = (degree - 1) % len(pitches)
    octave = (degree - 1) // len(pitches)
    return int(pitches[index]) + 12 * octave


def _fold_into_band(midi: int, low: int, high: int) -> int:
    """Move a pitch by octaves into ``low..high`` without changing pitch class."""
    if low > high:
        low, high = high, low
    while midi > high:
        midi -= 12
    while midi < low:
        midi += 12
    return midi


def _resolve_chord_bass(ctx: Any, bar: int) -> int:
    """Resolve the chord root in the guitar bass register (E2..F3)."""
    chord = _chord_at(ctx, bar)
    pitches = getattr(chord, "pitches", None)
    if not isinstance(pitches, Sequence) or isinstance(pitches, (str, bytes)) or not pitches:
        raise TextureResolveError("pitch", "render context chord has no pitches")
    root = getattr(chord, "bass_midi", None)
    midi = int(root) if isinstance(root, int) else int(pitches[0])
    low = _context_int(ctx, "bass_low", GUITAR_LOW)
    high = _context_int(ctx, "bass_high", 53)
    return _fold_into_band(midi, low, high)


def _resolve_chord_mid(ctx: Any, bar: int, degree: int) -> int:
    """Resolve a chord degree inside the guitar mid register (D3..F4)."""
    midi = _resolve_chord(ctx, bar, degree)
    low = _context_int(ctx, "mid_low", 50)
    high = _context_int(ctx, "mid_high", 65)
    return _fold_into_band(midi, low, high)


def _chord_at(ctx: Any, bar: int) -> Any:
    method = getattr(ctx, "chord", None)
    if callable(method):
        return method(bar)
    chord_at = getattr(ctx, "chord_at", None)
    if not isinstance(chord_at, Mapping):
        raise TextureResolveError("bar", "render context has no chord_at mapping")
    if bar in chord_at:
        return chord_at[bar]
    earlier = [key for key in chord_at if isinstance(key, int) and key <= bar]
    # `_Ctx.chord()` itself falls back to C when the table has no earlier bar;
    # mirror that production default instead of inventing a different policy.
    return chord_at[max(earlier)] if earlier else C


def _resolve_scale_step(ctx: Any, steps: int) -> int:
    mode = getattr(ctx, "mode", None)
    if mode not in ("major", "minor"):
        raise TextureResolveError("pitch.steps", f"unknown context mode {mode!r}")

    scale = _melody_scale(mode)
    low = _integer(
        getattr(ctx, "treble_floor", scale[0]), "pitch.steps", "treble_floor"
    )
    high = _integer(
        getattr(ctx, "treble_top", scale[-1]), "pitch.steps", "treble_top"
    )
    if low > high:
        low, high = high, low

    window = [note for note in scale if low <= note <= high]
    if not window:  # A narrow register can miss every scale tone.
        window = list(scale)
    center = (low + high) // 2
    anchor = min(window, key=lambda note: (abs(note - center), note))
    index = max(0, min(len(window) - 1, window.index(anchor) + steps))
    return int(window[index])


def _resolve_literal(ref: PitchRef) -> int:
    value = _integer(ref.value, "pitch.value", "value")
    if not 0 <= value <= 127:
        raise TextureResolveError("pitch.value", "must be in 0..127")
    return value


# ---------------------------------------------------------------------------
# Authored events → NoteEvent
# ---------------------------------------------------------------------------


def authored_to_events(
    spec_or_events: TextureSpec | Sequence[AuthoredEvent] | AuthoredEvent,
    ctx: Any,
    meter: Any,
    *,
    bar_offset: int = 0,
) -> list[NoteEvent]:
    """Copy authored placement and notation into ``NoteEvent`` values.

    Only ``pitch`` is resolved. ``bar`` is shifted by ``bar_offset`` (for a
    phrase placed later in a form); every other authored field keeps its value.
    Placement is checked against ``meter`` and is never clamped or rounded.
    """
    events = _authored_events(spec_or_events)
    quarter = _quarter_beats(meter)
    offset = _integer(bar_offset, "bar_offset", "bar_offset")
    if offset < 0:
        raise TextureResolveError("bar_offset", "must be >= 0")

    notes: list[NoteEvent] = []
    for index, event in enumerate(events):
        notes.append(_note_for_event(event, ctx, quarter, index=index, bar_offset=offset))
    return notes


def _note_for_event(
    event: AuthoredEvent,
    ctx: Any,
    quarter: float,
    *,
    index: int,
    bar_offset: int,
) -> NoteEvent:
    path = f"authored.events[{index}]"
    if not isinstance(event, AuthoredEvent):
        raise TextureResolveError(path, "expected an AuthoredEvent")

    _check_placement(event, quarter, path)
    bar = event.bar + bar_offset
    try:
        midi = resolve_pitch(event.pitch, ctx, bar=bar)
    except TextureResolveError as exc:
        raise TextureResolveError(_join(path, exc.path), exc.message) from None

    return NoteEvent(
        bar=bar,
        beat=float(event.beat),
        midi=midi,
        duration_beats=float(event.duration_beats),
        voice=event.voice,
        staff=event.staff,
        tie_start=event.tie in _TIE_START,
        tie_stop=event.tie in _TIE_STOP,
        slur_start=event.slur in _SLUR_START,
        slur_stop=event.slur in _SLUR_STOP,
        accent=event.accent,
        # Derived at render time; authored does not own these.
        velocity=None,
        tenuto=event.tenuto,
        staccato=event.staccato,
        hairpin=False,
        pinned=False,
    )


def _check_placement(event: AuthoredEvent, quarter: float, path: str) -> None:
    if not _is_int(event.bar) or event.bar < 0:
        raise TextureResolveError(f"{path}.bar", "must be an integer >= 0")
    if not _is_number(event.beat) or float(event.beat) < 0:
        raise TextureResolveError(f"{path}.beat", "must be a finite number >= 0")
    if not _is_number(event.duration_beats) or float(event.duration_beats) <= 0:
        raise TextureResolveError(f"{path}.duration_beats", "must be a finite number > 0")

    beat = float(event.beat)
    duration = float(event.duration_beats)
    if beat >= quarter:
        raise TextureResolveError(
            f"{path}.beat",
            f"beat {beat} is outside bar length {quarter}",
        )
    if beat + duration > quarter + _EPSILON:
        raise TextureResolveError(
            f"{path}.duration_beats",
            f"note overflows the bar: {beat} + {duration} > {quarter}",
        )


# ---------------------------------------------------------------------------
# Render-context playability
# ---------------------------------------------------------------------------


def check_authored_playable(
    events: TextureSpec | Sequence[AuthoredEvent] | AuthoredEvent,
    ctx: Any,
    meter: Any,
) -> PlayableReport:
    """Return render-context playability problems for authored events.

    Checked (when the data exists):

    * every resolved MIDI is inside the context's guitar range;
    * simultaneous voices stay ordered bass < mid < lead (voice 4 is the upper
      middle, between 2 and 1);
    * ``string`` is 1..6 and ``fret`` is inside the runtime table;
    * ``written_pitch`` and ``sounding_pitch`` differ by 12 semitones;
    * simultaneous tab notes span no more than five frets.

    Not checked, and reported in ``skipped``: renderer-profile exceptions
    (``thumb_cantabile``, tremolo double bass), any string/fret vs pitch
    comparison (the schema does not say whether tab pitch is written or
    sounding), the written/sounding relation when a pair is absent, and hand
    span when fewer than two simultaneous notes carry string/fret. Voice
    inversions are not skipped: authored has no field that documents one, so
    the ordinary order is enforced.
    """
    items = _authored_events(events)
    try:
        quarter = _quarter_beats(meter)
    except TextureResolveError as exc:
        return PlayableReport(
            [TextureError(exc.path, exc.message)],
            skipped=(SKIPPED_PROFILE,),
        )

    report = PlayableReport()
    notes: list[NoteEvent | None] = []
    for index, event in enumerate(items):
        try:
            notes.append(
                _note_for_event(event, ctx, quarter, index=index, bar_offset=0)
            )
        except TextureResolveError as exc:
            report.append(TextureError(exc.path, exc.message))
            notes.append(None)

    low = _context_int(ctx, "bass_low", GUITAR_LOW)
    high = _context_int(ctx, "ceiling", GUITAR_HIGH)
    if low > high:
        low, high = high, low
    for index, note in enumerate(notes):
        if note is not None and not low <= note.midi <= high:
            report.append(
                TextureError(
                    f"authored.events[{index}].pitch",
                    f"resolved midi {note.midi} is outside guitar range {low}..{high}",
                )
            )

    report.extend(_voice_order_problems(items, notes))
    report.extend(_string_fret_problems(items))
    report.extend(_written_sounding_problems(items))
    report.extend(_hand_span_problems(items, notes))

    if not any(
        item.string is not None and item.fret is not None
        for item in items
        if isinstance(item, AuthoredEvent)
    ):
        report.skipped = (*report.skipped, SKIPPED_STRING_FRET)
    if not any(
        item.written_pitch is not None and item.sounding_pitch is not None
        for item in items
        if isinstance(item, AuthoredEvent)
    ):
        report.skipped = (*report.skipped, SKIPPED_WRITTEN_SOUNDING)
    if not _tab_pair_overlap(items):
        report.skipped = (*report.skipped, SKIPPED_HAND_SPAN)
    # The profile is a renderer input, not an authored field. Profile-specific
    # floors (thumb_cantabile, tremolo bass) stay with assert_playable.
    report.skipped = (*report.skipped, SKIPPED_PROFILE)
    return report


def _voice_order_problems(
    events: Sequence[AuthoredEvent],
    notes: Sequence[NoteEvent | None],
) -> list[TextureError]:
    problems: list[TextureError] = []
    for left in range(len(notes)):
        first = notes[left]
        if first is None or not isinstance(events[left], AuthoredEvent):
            continue
        for right in range(left + 1, len(notes)):
            second = notes[right]
            if second is None or not isinstance(events[right], AuthoredEvent):
                continue
            if not _overlaps(first, second):
                continue
            first_rank = _voice_rank(first.voice)
            second_rank = _voice_rank(second.voice)
            if first_rank is None or second_rank is None or first_rank == second_rank:
                continue
            if first_rank > second_rank:
                lower, upper = second, first
                lower_index, lower_voice, upper_voice = right, second.voice, first.voice
            else:
                lower, upper = first, second
                lower_index, lower_voice, upper_voice = left, first.voice, second.voice
            if lower.midi >= upper.midi:
                problems.append(
                    TextureError(
                        f"authored.events[{lower_index}].voice",
                        f"voice {lower_voice} ({lower.midi}) is not below "
                        f"voice {upper_voice} ({upper.midi})",
                    )
                )
    return problems


def _string_fret_problems(events: Sequence[AuthoredEvent]) -> list[TextureError]:
    problems: list[TextureError] = []
    for index, event in enumerate(events):
        if not isinstance(event, AuthoredEvent):
            continue
        path = f"authored.events[{index}]"
        string = event.string
        fret = event.fret
        if string is None:
            if fret is not None:
                problems.append(
                    TextureError(f"{path}.fret", "fret requires string")
                )
            continue
        if not _is_int(string) or not 1 <= string <= 6:
            problems.append(TextureError(f"{path}.string", "must be 1..6"))
            continue
        if fret is None:
            continue
        if not _is_int(fret) or fret < 0:
            problems.append(TextureError(f"{path}.fret", "must be an integer >= 0"))
            continue
        maximum = _MAX_FRET[6 - string]
        if fret > maximum:
            problems.append(
                TextureError(
                    f"{path}.fret",
                    f"fret {fret} is above string {string}'s limit {maximum}",
                )
            )
    return problems


def _written_sounding_problems(events: Sequence[AuthoredEvent]) -> list[TextureError]:
    problems: list[TextureError] = []
    for index, event in enumerate(events):
        if not isinstance(event, AuthoredEvent):
            continue
        written = event.written_pitch
        sounding = event.sounding_pitch
        if written is None or sounding is None:
            continue
        path = f"authored.events[{index}]"
        written_midi = _pitch_name_midi(written)
        sounding_midi = _pitch_name_midi(sounding)
        if written_midi is None:
            problems.append(
                TextureError(
                    f"{path}.written_pitch",
                    f"cannot read {written!r} as scientific pitch notation",
                )
            )
        if sounding_midi is None:
            problems.append(
                TextureError(
                    f"{path}.sounding_pitch",
                    f"cannot read {sounding!r} as scientific pitch notation",
                )
            )
        if written_midi is None or sounding_midi is None:
            continue
        if written_midi - sounding_midi != 12:
            problems.append(
                TextureError(
                    f"{path}.sounding_pitch",
                    f"written {written} sounds as {sounding}, a difference of "
                    f"{written_midi - sounding_midi} semitones; guitar is 12",
                )
            )
    return problems


def _hand_span_problems(
    events: Sequence[AuthoredEvent],
    notes: Sequence[NoteEvent | None],
) -> list[TextureError]:
    problems: list[TextureError] = []
    for left in range(len(notes)):
        first = notes[left]
        if first is None or not isinstance(events[left], AuthoredEvent):
            continue
        left_fret = _valid_fret(events[left])
        if left_fret is None:
            continue
        for right in range(left + 1, len(notes)):
            second = notes[right]
            if second is None or not isinstance(events[right], AuthoredEvent):
                continue
            right_fret = _valid_fret(events[right])
            if right_fret is None:
                continue
            if not _overlaps(first, second):
                continue
            span = abs(left_fret - right_fret)
            if span > HAND_SPAN_LIMIT:
                problems.append(
                    TextureError(
                        f"authored.events[{left}].fret",
                        f"hand span {span} frets with events[{left}] and "
                        f"events[{right}] exceeds {HAND_SPAN_LIMIT}",
                    )
                )
    return problems


def _tab_pair_overlap(events: Sequence[AuthoredEvent]) -> bool:
    for left in range(len(events)):
        if _valid_fret(events[left]) is None:
            continue
        for right in range(left + 1, len(events)):
            if _valid_fret(events[right]) is None:
                continue
            if _overlaps_event(events[left], events[right]):
                return True
    return False


def _valid_fret(event: Any) -> int | None:
    if not isinstance(event, AuthoredEvent):
        return None
    if event.string is None or event.fret is None:
        return None
    if not _is_int(event.string) or not 1 <= event.string <= 6:
        return None
    if not _is_int(event.fret) or event.fret < 0:
        return None
    if event.fret > _MAX_FRET[6 - event.string]:
        return None
    return event.fret


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _authored_events(
    source: TextureSpec | Sequence[AuthoredEvent] | AuthoredEvent,
) -> tuple[AuthoredEvent, ...]:
    if isinstance(source, TextureSpec):
        return tuple(source.authored)
    if isinstance(source, AuthoredEvent):
        return (source,)
    if isinstance(source, Sequence) and not isinstance(source, (str, bytes)):
        return tuple(source)
    raise TextureResolveError(
        "authored.events",
        "expected a TextureSpec, an AuthoredEvent, or a sequence of them",
    )


def _quarter_beats(meter: Any) -> float:
    try:
        quarter = float(meter.quarter_beats)
    except (AttributeError, TypeError, ValueError):
        raise TextureResolveError(
            "meter", "expected a Meter or MeterSpec with quarter_beats"
        ) from None
    if not math.isfinite(quarter) or quarter <= 0:
        raise TextureResolveError("meter", "quarter_beats must be finite and > 0")
    return quarter


def _overlaps(first: NoteEvent, second: NoteEvent) -> bool:
    if first.bar != second.bar:
        return False
    return (
        first.beat < second.beat + second.duration_beats - _EPSILON
        and second.beat < first.beat + first.duration_beats - _EPSILON
    )


def _overlaps_event(first: AuthoredEvent, second: AuthoredEvent) -> bool:
    if first.bar != second.bar:
        return False
    return (
        float(first.beat) < float(second.beat) + float(second.duration_beats) - _EPSILON
        and float(second.beat) < float(first.beat) + float(first.duration_beats) - _EPSILON
    )


def _voice_rank(voice: int) -> int | None:
    return {3: 0, 2: 1, 4: 2, 1: 3}.get(voice)


def _pitch_name_midi(name: str) -> int | None:
    match = _PITCH_NAME.match(name)
    if match is None:
        return None
    letter, accidental, octave = match.groups()
    pitch_class = _PITCH_CLASS[letter.upper()] + _ACCIDENTAL[accidental]
    return 12 * (int(octave) + 1) + pitch_class


def _context_int(ctx: Any, name: str, default: int) -> int:
    value = getattr(ctx, name, default)
    return value if _is_int(value) else default


def _integer(value: Any, path: str, name: str) -> int:
    if not _is_int(value):
        raise TextureResolveError(path, f"{name} must be an integer")
    return value


def _join(path: str, suffix: str) -> str:
    if not suffix:
        return path
    return f"{path}.{suffix}"


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
