"""Preview-only Barrios period: validate an authored sentence and render it.

A Barrios figure has no production registry yet (see
`docs/sonify-guitar-model.md` §13.6). This module is the pilot: it validates a
candidate `SentenceSpec` against `guitar_barrios_figures.BARRIOS_FIGURES`,
builds one bounded deterministic `_Ctx`, and renders the period through the
real Barrios per-bar renderers.

It deliberately does not use `app.studio.preview.preview_spec`: that path only
knows the Torroba/Sor owners, and its fixture table would reject `preludio`.
It shares only renderer-agnostic helpers (`preview_fixture`, note/hash shapes,
`_Ctx`) with the other pilots. This module reads the same result, note, and
hash shapes so the Studio UI can consume either result.

Nothing here registers a spec. `SENTENCE_SPECS` is only read by
`sentence_specs._validate` / `_matches`; the candidate never enters it.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.sonify import sentence_specs
from app.sonify.form import FormSection, compose_meter
from app.sonify.chords import C, CM
from app.sonify.guitar_patterns import _Ctx, _meter_kind
from app.sonify.guitar_barrios_figures import (
    BARRIOS_FIGURES,
    BARRIOS_PATTERNS,
    BarriosFigurePen,
    BarriosFigureState,
    figure_band,
    figure_pattern,
    render_barrios_figure,
)
from app.sonify.keys import active_register
from app.sonify.model import Phrase, Run
from app.sonify.sentence_specs import SentenceSpec
from app.studio.preview import (
    Error,
    PreviewResult,
    _CHARACTERS,
    _METERS,
    _MODES,
    _notes,
    _render_hash,
    _shape_ok,
    _voice,
)
from app.studio.preview_fixture import (
    MAX_PLAN_BARS,
    MAX_RENDER_BARS,
    SpecParseError,
    allowed_fixture_keys,
    fixture_bool as _fixture_bool,
    fixture_int as _fixture_int,
    matrix_axes,
)

MAX_BARRIOS_MATRIX_ROWS = 64
_BARRIOS_CONTOUR = (67, 65, 64, 62, 60, 62, 64, 65)
_DEFAULT_BPM = 96  # match the Studio audio preview tempo
_DEFAULT_MODE = "minor"
_DEFAULT_CHARACTER = "calm"


def _exact_length(spec: SentenceSpec) -> int | None:
    """The one period length an exact candidate can select."""
    if not isinstance(spec.span, sentence_specs.Span):
        return None
    length = spec.span.tile
    if length is None:
        length = spec.select.length_min
    return length


def _errors(spec: SentenceSpec) -> list[Error]:
    errors: list[Error] = []
    if not isinstance(spec.id, str) or not spec.id.strip():
        errors.append(Error("id", "id must be a non-empty string"))
    if not isinstance(spec.pattern, str) or spec.pattern not in BARRIOS_PATTERNS:
        errors.append(
            Error(
                "pattern",
                f"unknown Barrios pattern {spec.pattern!r}; "
                f"expected one of {sorted(BARRIOS_PATTERNS)}",
            )
        )
    if not isinstance(spec.meter, str) or spec.meter not in _METERS:
        errors.append(
            Error(
                "meter",
                f"unknown meter {spec.meter!r}; expected one of {sorted(_METERS)}",
            )
        )
    if not _shape_ok(spec):
        if not errors:
            errors.append(Error("spec", "spec fields do not have the expected types"))
        return errors

    if spec.span.cycle:
        errors.append(Error("span", "a Barrios period cannot be a cell/cycle span"))
    length = _exact_length(spec)
    if length is None or length < 1:
        errors.append(Error("span", "a Barrios period needs an exact positive length"))
        length = None
    elif spec.select.length_min != length or (
        spec.select.length_max is not None and spec.select.length_max != length
    ):
        errors.append(
            Error(
                "span",
                "an exact period must select exactly its tile "
                f"({length}); got length_min={spec.select.length_min}, "
                f"length_max={spec.select.length_max}",
            )
        )

    slots_ok = isinstance(spec.slots, tuple) and all(
        isinstance(slot, sentence_specs.Slot) for slot in spec.slots
    )
    if not slots_ok:
        errors.append(Error("slots", "slots must be a tuple of slot objects"))
        return errors

    for index, slot in enumerate(spec.slots):
        path = f"slots[{index}]"
        if slot.anchor != "start":
            errors.append(
                Error(f"{path}.anchor", "a Barrios period slot must be start-anchored")
            )
        if slot.figure is None:
            errors.append(Error(path, "a Barrios period slot needs a figure"))
        elif slot.figure not in BARRIOS_FIGURES:
            errors.append(
                Error(
                    f"{path}.figure",
                    f"figure {slot.figure!r} is not in BARRIOS_FIGURES",
                )
            )
        if slot.cell is not None:
            errors.append(Error(f"{path}.cell", "a Barrios period does not use cell ids"))

    if length is not None:
        covered: set[int] = set()
        for slot in spec.slots:
            if slot.anchor != "start":
                continue
            covered.update(range(slot.start, slot.start + slot.bars))
        if covered != set(range(length)):
            errors.append(
                Error(
                    "slots",
                    f"slots must tile the {length}-bar period exactly",
                )
            )

    try:
        sentence_specs._validate(spec, spec.pattern, spec.meter)
    except (ValueError, AttributeError, TypeError) as exc:
        message = str(exc)
        prefix = f"{spec.id}: "
        if message.startswith(prefix):
            message = message[len(prefix):]
        if not any(error.message == message for error in errors):
            errors.append(Error("spec", message))
    return errors


def validate_barrios_period(spec: SentenceSpec) -> list[Error]:
    """Schema, registry, and coverage errors for one candidate period."""
    return _errors(spec)


# ---------------------------------------------------------------------------
# fixture


def _default_n(spec: SentenceSpec) -> int:
    select = spec.select
    if select.n_mod is not None:
        return select.n_mod[1]
    return 1 if select.n_parity == "odd" else 0


def _resolve_fixture(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None
) -> dict[str, Any]:
    supplied = dict(fixture or {})
    allowed = {
        "pattern",
        "meter",
        "length",
        "bars",
        "n",
        "closes",
        "rise",
        "mode",
        "character",
        "bpm",
        "matrix",
    }
    allowed_fixture_keys(supplied, allowed)

    pattern = supplied.get("pattern", spec.pattern)
    if pattern != spec.pattern:
        raise SpecParseError(
            f"fixture.pattern {pattern!r} does not match spec.pattern {spec.pattern!r}"
        )
    meter = supplied.get("meter", spec.meter)
    if meter not in _METERS:
        raise SpecParseError(
            f"fixture.meter {meter!r} is not renderable; expected {sorted(_METERS)}"
        )
    if meter != spec.meter:
        raise SpecParseError(
            f"fixture.meter {meter!r} does not match spec.meter {spec.meter!r}"
        )
    length = _exact_length(spec)
    if length is None:
        raise SpecParseError("the candidate period has no exact length")
    requested = _fixture_int(
        supplied.get("length", length),
        "fixture.length",
        minimum=1,
        maximum=MAX_PLAN_BARS,
    )
    if requested != length:
        raise SpecParseError(
            f"fixture.length {requested} does not match the exact period length {length}"
        )
    bars = _fixture_int(supplied.get("bars", length), "fixture.bars", minimum=0)
    bars = min(bars, MAX_RENDER_BARS, length)
    n = _fixture_int(supplied.get("n", _default_n(spec)), "fixture.n", minimum=0)
    closes = _fixture_bool(
        supplied.get("closes", spec.select.closes == "close"), "fixture.closes"
    )
    rise = _fixture_int(
        supplied.get("rise", spec.select.rise_min), "fixture.rise", minimum=0
    )
    mode = supplied.get("mode", _DEFAULT_MODE)
    if mode not in _MODES:
        raise SpecParseError("fixture.mode must be major or minor")
    character = supplied.get("character")
    if character is None:
        character = _DEFAULT_CHARACTER
    if character not in _CHARACTERS:
        raise SpecParseError("fixture.character is not a known character")
    bpm = _fixture_int(
        supplied.get("bpm", _DEFAULT_BPM), "fixture.bpm", minimum=1, maximum=400
    )
    return {
        "pattern": pattern,
        "meter": meter,
        "length": length,
        "bars": bars,
        "n": n,
        "closes": closes,
        "rise": rise,
        "mode": mode,
        "character": character,
        "bpm": bpm,
        "matrix": matrix_axes(
            supplied.get("matrix"),
            defaults={
                "lengths": [length],
                "n": [n],
                "closes": [closes],
                "rise": [rise],
            },
            max_rows=MAX_BARRIOS_MATRIX_ROWS,
            max_length=MAX_PLAN_BARS,
        ),
    }


# ---------------------------------------------------------------------------
# bounded context / render


def _joined(start: int, pitches: list[int]) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs), False)


def _melody(length: int, epb: int) -> list[int]:
    return [
        _BARRIOS_CONTOUR[index % len(_BARRIOS_CONTOUR)]
        for index in range(length * epb)
    ]


def _sections(length: int) -> tuple[FormSection, ...]:
    if length <= 1:
        return (FormSection(0, length, "intro", 0),)
    return (
        FormSection(0, 1, "intro", 0),
        FormSection(1, length, "phrase", 0),
    )


def _barrios_ctx(
    fixture: Mapping[str, Any],
    *,
    slots: list,
):
    meter = _METERS[fixture["meter"]]
    length = int(fixture["length"])
    epb = meter.eighths_per_bar
    melody = _melody(length, epb)
    phrases = tuple(
        _joined(
            slot.start * epb,
            melody[slot.start * epb : (slot.start + slot.bars) * epb],
        )
        for slot in slots
    )
    figure_by_bar = {
        bar: slot.figure
        for slot in slots
        for bar in range(slot.start, slot.start + slot.bars)
    }
    band_at = {
        bar: figure_band(figure_by_bar[bar]) for bar in range(length)
    }
    register = active_register()
    return _Ctx(
        melody=list(melody),
        raw=list(melody),
        chord_at={bar: CM if fixture["mode"] == "minor" else C for bar in range(length)},
        kind_at={bar: "phrase" for bar in range(length)},
        band_at=band_at,
        phrases=phrases,
        bars=length,
        bpm=int(fixture["bpm"]),
        ensemble="barrios",
        mode=str(fixture["mode"]),
        character=str(fixture["character"]),
        character_at=None,
        sections=_sections(length),
        rel_span=0.02,
        semitones=40 - register.guitar_floor,
        bass_low=register.guitar_floor,
        bass_high=register.guitar_bass_top,
        mid_low=register.guitar_mid_low,
        mid_high=register.guitar_mid_high,
        treble_floor=register.guitar_treble_floor,
        treble_top=register.guitar_treble_top,
        ceiling=register.guitar_ceiling,
        epb=epb,
        kind=_meter_kind(meter),
        strong=tuple(meter.strong_eighths),
        bar_beats=meter.quarter_beats,
        regime_at={bar: "sideway" for bar in range(length)},
    )


def _period_spans(spec: SentenceSpec) -> list[dict[str, Any]]:
    ordered = sorted(spec.slots, key=lambda slot: slot.start)
    spans: list[dict[str, Any]] = []
    for slot in ordered:
        if slot.figure is None:
            continue
        spans.append(
            {
                "figure": slot.figure,
                "pattern": figure_pattern(slot.figure),
                "bars": list(range(slot.start, slot.start + slot.bars)),
            }
        )
    return spans


def _render_period(
    spec: SentenceSpec, fixture: Mapping[str, Any]
) -> tuple[list, list[str]]:
    meter = _METERS[fixture["meter"]]
    length = int(fixture["length"])
    slots = sorted(spec.slots, key=lambda slot: slot.start)
    patterns = [figure_pattern(slot.figure) for slot in slots]
    bar_slot = {
        bar: (index, slot)
        for index, slot in enumerate(slots)
        for bar in range(slot.start, slot.start + slot.bars)
    }
    collect = min(int(fixture["bars"]), length)
    with compose_meter(meter):
        ctx = _barrios_ctx(fixture, slots=slots)
        state = BarriosFigureState.build(ctx, patterns)
        lead: list = []
        support: list = []
        low: list = []
        for bar in range(collect):
            index, slot = bar_slot[bar]
            pen = BarriosFigurePen(
                state=state,
                bar=bar,
                phrase=ctx.phrases[index],
                index=bar - slot.start,
                count=slot.bars,
            )
            part_lead, part_support, part_low = render_barrios_figure(
                pen, slot.figure
            )
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
    row = [figure_pattern(bar_slot[bar][1].figure) for bar in range(length)]
    return _voice(lead, 1) + _voice(support, 2) + _voice(low, 3), row


# ---------------------------------------------------------------------------
# matrix / entry point


def _matrix(
    spec: SentenceSpec,
    fixture: Mapping[str, Any],
    render_hash: str | None,
) -> tuple[dict[str, Any], ...]:
    axes = fixture["matrix"]
    spans = _period_spans(spec)
    rows: list[dict[str, Any]] = []
    for length in axes["lengths"]:
        for n in axes["n"]:
            for closes in axes["closes"]:
                for rise in axes["rise"]:
                    selected = bool(
                        sentence_specs._matches(spec, length, n, closes, rise)
                    )
                    rendered = (
                        selected
                        and render_hash is not None
                        and length == int(fixture["length"])
                        and n == int(fixture["n"])
                        and closes == bool(fixture["closes"])
                        and rise == int(fixture["rise"])
                    )
                    rows.append(
                        {
                            "length": length,
                            "n": n,
                            "closes": closes,
                            "rise": rise,
                            "selected": selected,
                            "spans": spans if selected else [],
                            "render": rendered,
                            "renderHash": render_hash if rendered else None,
                        }
                    )
    return tuple(rows)


def preview_barrios_period(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None = None
) -> PreviewResult:
    """Validate one candidate period and render one bounded deterministic body."""
    errors = validate_barrios_period(spec)
    if errors:
        return PreviewResult(ok=False, errors=tuple(errors))

    try:
        resolved = _resolve_fixture(spec, fixture)
    except (SpecParseError, TypeError, ValueError) as exc:
        return PreviewResult(ok=False, errors=(Error("fixture", str(exc)),))

    events, row = _render_period(spec, resolved)
    notes = _notes(events)
    plan = {
        "kind": "barrios_period",
        "pattern": spec.pattern,
        "meter": resolved["meter"],
        "length": resolved["length"],
        "selected": True,
        "spans": _period_spans(spec),
    }
    render_hash = _render_hash(plan, row, notes)
    matrix = _matrix(spec, resolved, render_hash)
    return PreviewResult(
        ok=True,
        plan=plan,
        row=row,
        notes=notes,
        render_hash=render_hash,
        matrix=matrix,
    )
