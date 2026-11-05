"""Preview-only Bach fugue exposition renderer.

The production planners and `render_guitar_score` do not know this module. It
answers one question for the Studio authoring loop: *what does this candidate
exposition plan sound like for one bounded fixture?*

The renderer is intentionally a skeleton, not a counterpoint engine:

* subject entries restate the fixed two-bar subject contour, transposed by
  whole octaves into the entry voice's register;
* the bass answer is produced by the real imitation renderer
  (`guitar_bach._compose_fuga_bass`), so it keeps the production 1:1 contour
  and tonal adaptation;
* the harmony is a hard-coded tonic/dominant plan (C for a subject entry, G
  for the answer entry), which is the one thing a real exposition must do that
  the bar renderer cannot infer;
* nothing else is written: there is no free counterpoint, countersubject, or
  episode. Those need a separate engine and are out of scope.

Two inputs share one entry plan:

* `preview_bach_exposition` takes an `ExpositionSpec` directly;
* `preview_bach_exposition_candidate` takes the v1 `SentenceSpec` wrapper from
  `app/studio/candidates/bach_exposition.json`. The sentence wrapper can only
  name the procedure, not spell out entries, so the named `EXPOSITIONS` spec
  owns the entry plan and the candidate points at it with
  `Slot.procedure="bach_exposition"`.

Nothing is registered in `SENTENCE_SPECS` and no production procedure table is
touched. `PreviewResult`, the fixture helpers, and the render hash are the
shared Studio shapes from `app.studio.preview`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from app.sonify import sentence_specs
from app.sonify.bach_exposition import (
    Entry,
    ExpositionSpec,
    resolve_exposition,
)
from app.sonify.chords import C, G
from app.sonify.form import METER_34, METER_44, METER_68, compose_meter
from app.sonify.guitar_bach import _compose_fuga_bass
from app.sonify.guitar_patterns import _eighth_event, _runs
from app.sonify.sentence_specs import SentenceSpec
from app.studio.preview import (
    MAX_RENDER_BARS,
    Error,
    PreviewResult,
    _ctx,
    _fixture_int,
    _notes,
    _render_hash,
    _voice,
)
from app.studio.preview_fixture import SpecParseError, allowed_fixture_keys

_METERS = {"3/4": METER_34, "4/4": METER_44, "6/8": METER_68}

# A two-bar subject in C major: an arch, then a higher arch. It is a fixture,
# not a quotation. The subject entry copies it; the bass answer re-derives its
# contour from the same eighths through `_compose_fuga_bass`.
_SUBJECT_CONTOUR = (
    67,
    69,
    71,
    72,
    74,
    72,
    71,
    69,
    67,
    71,
    74,
    76,
    77,
    76,
    74,
    71,
)

_VOICE_NUMBER = {"soprano": 1, "alto": 2, "bass": 3}
_VOICE_VELOCITY = {"soprano": 64, "alto": 52, "bass": 58}
# The entry writer is fixed in C major and a calm character; only the meter,
# the render window, and the tempo metadata are fixture inputs.
_FIXTURE_KEYS = frozenset({"meter", "bars", "bpm"})


def _strip_id(message: str, spec: SentenceSpec) -> str:
    prefix = f"{spec.id}: "
    return message[len(prefix):] if message.startswith(prefix) else message


def _error_path(message: str) -> str:
    if message.startswith("entries["):
        return "entries"
    for key in ("subject_bars", "imitation", "meter", "pattern", "id"):
        if message.startswith(key):
            return key
    return "spec"


# ---------------------------------------------------------------------------
# validation


def validate_exposition(spec: ExpositionSpec) -> list[Error]:
    """Schema and realization errors for one entry plan."""
    if not isinstance(spec, ExpositionSpec):
        return [Error("spec", "expected an ExpositionSpec")]
    errors: list[Error] = []
    try:
        spec.check_realized()
    except (ValueError, TypeError) as exc:
        errors.append(Error(_error_path(str(exc)), str(exc)))
    for index, entry in enumerate(spec.entries if isinstance(spec.entries, tuple) else ()):
        if isinstance(entry, Entry) and entry.countersubject:
            errors.append(
                Error(
                    "entries",
                    f"entries[{index}].countersubject is not realized by the "
                    "preview; leave it false",
                )
            )
    if not isinstance(spec.meter, str) or spec.meter not in _METERS:
        errors.append(
            Error(
                "meter",
                f"meter {spec.meter!r} is not renderable; "
                f"expected one of {sorted(_METERS)}",
            )
        )
    return errors


def validate_candidate(spec: SentenceSpec) -> list[Error]:
    """Validate the v1 sentence wrapper and the named exposition it points at."""
    if not isinstance(spec, SentenceSpec):
        return [Error("spec", "expected a SentenceSpec")]
    errors: list[Error] = []
    if not isinstance(spec.id, str) or not spec.id.strip():
        errors.append(Error("id", "id must be a non-empty string"))

    slots = spec.slots if isinstance(spec.slots, tuple) else ()
    if len(slots) != 1:
        errors.append(
            Error("slots", "a candidate exposition needs exactly one procedure slot")
        )
    else:
        slot = slots[0]
        if not isinstance(slot, sentence_specs.Slot):
            errors.append(Error("slots[0]", "expected a slot object"))
        elif slot.procedure is None:
            errors.append(
                Error(
                    "slots[0].procedure",
                    "a candidate exposition names a procedure",
                )
            )
        else:
            try:
                named = resolve_exposition(slot.procedure)
            except ValueError as exc:
                errors.append(Error("slots[0].procedure", str(exc)))
            else:
                if spec.pattern != named.pattern:
                    errors.append(
                        Error(
                            "pattern",
                            f"pattern {spec.pattern!r} does not match the "
                            f"{named.id!r} pattern {named.pattern!r}",
                        )
                    )
                if spec.meter != named.meter:
                    errors.append(
                        Error(
                            "meter",
                            f"meter {spec.meter!r} does not match the "
                            f"{named.id!r} meter {named.meter!r}",
                        )
                    )
                if slot.start != 0 or slot.bars != named.length:
                    errors.append(
                        Error(
                            "slots[0]",
                            f"the procedure slot must cover bars 0..{named.length}",
                        )
                    )
                if getattr(spec.span, "tile", None) != named.length:
                    errors.append(
                        Error(
                            "span.tile",
                            f"span.tile must equal the exposition length "
                            f"({named.length})",
                        )
                    )

    try:
        sentence_specs._validate(spec, spec.pattern, spec.meter)
    except (ValueError, AttributeError, TypeError) as exc:
        candidate = Error("spec", _strip_id(str(exc), spec))
        if candidate not in errors:
            errors.append(candidate)
    return errors


# ---------------------------------------------------------------------------
# fixture


def _resolve_fixture(
    spec: ExpositionSpec, fixture: Mapping[str, Any] | None
) -> dict[str, Any]:
    supplied = dict(fixture or {})
    allowed_fixture_keys(supplied, _FIXTURE_KEYS)

    meter = supplied.get("meter", spec.meter)
    if not isinstance(meter, str) or meter not in _METERS:
        raise SpecParseError(
            f"fixture.meter {meter!r} is not renderable; "
            f"expected {sorted(_METERS)}"
        )
    if meter != spec.meter:
        raise SpecParseError(
            f"fixture.meter {meter!r} does not match spec.meter {spec.meter!r}"
        )

    bars = _fixture_int(supplied.get("bars", spec.length), "fixture.bars", minimum=0)
    bars = min(bars, MAX_RENDER_BARS, spec.length)

    bpm = _fixture_int(
        supplied.get("bpm", 96), "fixture.bpm", minimum=1, maximum=400
    )
    return {
        "meter": meter,
        "bars": max(0, bars),
        "bpm": bpm,
    }


# ---------------------------------------------------------------------------
# render


def _harmony(spec: ExpositionSpec) -> dict[int, Any]:
    """Tonic for a subject, dominant for the answer. No other key plan."""
    chords: dict[int, Any] = {}
    for entry in spec.entries:
        chord = G if entry.role == "answer" else C
        for bar in range(entry.start_bar, entry.start_bar + entry.bars):
            chords[bar] = chord
    return chords


def _voice_range(ctx: Any, voice: str) -> tuple[int, int]:
    if voice == "soprano":
        return ctx.treble_floor, ctx.treble_top
    if voice == "alto":
        return ctx.mid_low, ctx.mid_high
    return ctx.bass_low, ctx.bass_high


def _octave_shift(pitches: list[int], low: int, high: int) -> int:
    """Whole-octave transposition that fits the voice; never alters intervals."""
    for shift in (0, -12, 12, -24, 24, -36, 36):
        if all(low <= pitch + shift <= high for pitch in pitches):
            return shift
    raise ValueError(
        f"the subject does not fit the voice register {low}..{high}; "
        "use a different starting contour or voice"
    )


def _subject_events(ctx: Any, spec: ExpositionSpec, entry: Any) -> list:
    """Restate the fixed subject contour in the entry's voice."""
    runs = _runs(ctx.melody, 0, spec.subject_bars * ctx.epb)
    pitches = [midi for _offset, _length, midi in runs]
    low, high = _voice_range(ctx, entry.voice)
    shift = _octave_shift(pitches, low, high)
    return [
        event
        for offset, length, midi in runs
        for event in _eighth_event(
            entry.start_bar * ctx.epb + offset,
            length,
            midi + shift,
            ctx.epb,
            _VOICE_NUMBER[entry.voice],
            _VOICE_VELOCITY[entry.voice],
        )
    ]


def _answer_events(ctx: Any, spec: ExpositionSpec, entry: Any) -> list:
    """The production imitation renderer supplies the bass answer."""
    events: list = []
    for bar in range(entry.start_bar, entry.start_bar + entry.bars):
        events.extend(_compose_fuga_bass(ctx, bar, [], spec.imitation))
    return events


def _row(spec: ExpositionSpec) -> list[str]:
    row = [spec.pattern] * spec.length
    for entry in spec.entries:
        for bar in range(entry.start_bar, entry.start_bar + entry.bars):
            row[bar] = f"{entry.voice}:{entry.role}"
    return row


def _plan(spec: ExpositionSpec) -> dict[str, Any]:
    return {
        "kind": "procedure",
        "procedure": spec.id,
        "pattern": spec.pattern,
        "meter": spec.meter,
        "length": spec.length,
        "subject_bars": spec.subject_bars,
        "selected": True,
        "imitation": {
            "lag": spec.imitation.lag,
            "contour": spec.imitation.contour,
            "retrograde": spec.imitation.retrograde,
            "inversion": spec.imitation.inversion,
        },
        "entries": [
            {
                "index": index,
                "voice": entry.voice,
                "start_bar": entry.start_bar,
                "bars": entry.bars,
                "role": entry.role,
                "countersubject": entry.countersubject,
            }
            for index, entry in enumerate(spec.entries)
        ],
    }


def _events(spec: ExpositionSpec, fixture: Mapping[str, Any]) -> tuple[list, list[str]]:
    meter = _METERS[str(fixture["meter"])]
    length = spec.length
    melody = [
        _SUBJECT_CONTOUR[index % len(_SUBJECT_CONTOUR)]
        for index in range(length * meter.eighths_per_bar)
    ]
    collect = min(int(fixture["bars"]), length)
    buckets: dict[str, list] = {"soprano": [], "alto": [], "bass": []}
    with compose_meter(meter):
        ctx = _ctx(
            meter=meter,
            length=length,
            character="calm",
            mode="major",
            bpm=int(fixture["bpm"]),
            ensemble="bach",
            melody=melody,
        )
        # `_ctx` fills one chord for every bar; an exposition needs the answer
        # to sit on the dominant, so replace the chord table before rendering.
        ctx = replace(ctx, chord_at=_harmony(spec))
        for entry in spec.entries:
            if entry.start_bar >= collect:
                continue
            if entry.role == "answer":
                found = _answer_events(ctx, spec, entry)
            else:
                found = _subject_events(ctx, spec, entry)
            buckets[entry.voice].extend(
                event for event in found if event.bar < collect
            )
    events = (
        _voice(buckets["soprano"], 1)
        + _voice(buckets["alto"], 2)
        + _voice(buckets["bass"], 3)
    )
    return events, _row(spec)


def _matrix(
    spec: ExpositionSpec,
    fixture: Mapping[str, Any],
    render_hash: str | None,
) -> tuple[dict[str, Any], ...]:
    bars = int(fixture["bars"])
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(spec.entries):
        rendered = entry.start_bar < bars
        rows.append(
            {
                "index": index,
                "voice": entry.voice,
                "start_bar": entry.start_bar,
                "bars": entry.bars,
                "role": entry.role,
                "selected": True,
                "render": rendered,
                "renderHash": render_hash if rendered else None,
            }
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# public entry points


def preview_bach_exposition(
    spec: ExpositionSpec, fixture: Mapping[str, Any] | None = None
) -> PreviewResult:
    """Validate one entry plan and render one bounded, deterministic fixture."""
    errors = validate_exposition(spec)
    if errors:
        return PreviewResult(ok=False, errors=tuple(errors))

    try:
        resolved = _resolve_fixture(spec, fixture)
    except (SpecParseError, TypeError, ValueError) as exc:
        return PreviewResult(ok=False, errors=(Error("fixture", str(exc)),))

    try:
        events, row = _events(spec, resolved)
    except ValueError as exc:
        return PreviewResult(ok=False, errors=(Error("entries", str(exc)),))

    plan = _plan(spec)
    notes = _notes(events)
    render_hash = _render_hash(plan, row, notes)
    return PreviewResult(
        ok=True,
        plan=plan,
        row=row,
        notes=notes,
        render_hash=render_hash,
        matrix=_matrix(spec, resolved, render_hash),
    )


def preview_bach_exposition_candidate(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None = None
) -> PreviewResult:
    """Preview a v1 sentence candidate that names a registered exposition."""
    errors = validate_candidate(spec)
    if errors:
        return PreviewResult(ok=False, errors=tuple(errors))
    named = resolve_exposition(spec.slots[0].procedure)  # type: ignore[arg-type]
    return preview_bach_exposition(named, fixture)
