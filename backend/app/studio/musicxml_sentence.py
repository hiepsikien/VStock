"""Build one previewable sentence draft from a MusicXML passage.

The endpoint this module backs does **not** invent a new renderer. It copies a
committed template's ``select``/``span``/``slots`` into a new ``SentenceSpec``,
re-keys the pattern when the caller is creating a new pattern, and sends the
result through the existing preview and audio seams:

* ``existing`` mode only accepts the generic ``PILOT_PATTERNS`` set.  A
  ``suite_*`` id is a deliberate error: suite gates own exactly one sentence,
  so adding a second sentence there could not be promoted.
* ``new`` mode in the router now previews the selected passage itself (see
  ``prepare_new_metadata``): the rhythm, durations, and reference pitch are the
  source, and no template is required. ``render_draft`` still keeps the legacy
  template path for ``new`` drafts built directly by callers/tests.  No
  registry is mutated and the result is never production-ready.

Templates come from ``app.studio.examples`` (the committed JSON payloads),
parsed with ``sentence_spec.parse_spec``.  Nothing here hardcodes a template.

The draft covers whole bars.  A passage with beat offsets still drafts the
whole selected bars and returns a warning, because sentence slots are
bar-based.  The fixture is resolved with only ``length``/``run_length``; ``n``,
``closes``, and ``rise`` keep the spec's defaults rather than being invented
from the MusicXML.

No preview renderer lives here: ``render_draft`` calls
``dispatch.preview_sentence`` (existing) or ``villa_preview`` (new), then
``studio_audio.preview_audio`` with the draft family override.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from app.sonify.pattern_registry import PATTERN_META
from app.sonify.guitar_villa_figures import VILLA_ARPEGGIO
from app.sonify.sentence_specs import (
    METER_ANY,
    SENTENCE_SPECS,
    Select,
    SentenceSpec,
    Slot,
    Span,
    quarter_beats,
)
from app.studio import audio as studio_audio
from app.studio import dispatch, examples, villa_preview
from app.studio.export import PILOT_PATTERNS
from app.studio.preview import Error
from app.studio.preview_fixture import MAX_PLAN_BARS, MAX_RENDER_BARS
from app.studio.sentence_spec import parse_spec, spec_to_mapping

_MODES = frozenset({"existing", "new"})
_VILLA_RENDERER = "villa"
_VILLA_METERS = frozenset(villa_preview.VILLA_METERS)


@dataclass(frozen=True)
class Template:
    """One committed example spec, parsed for drafting."""

    id: str
    pattern: str
    meter: str
    spec: SentenceSpec


@dataclass(frozen=True)
class Draft:
    """One prepared draft, before preview/audio rendering.

    Keeping preparation separate lets the router spend quota only after the
    request has passed its structural checks (pattern, template, meter, id).
    """

    ok: bool
    mode: str | None = None
    spec: SentenceSpec | None = None
    fixture: dict[str, Any] | None = None
    template_id: str | None = None
    family: str | None = None
    warnings: tuple[str, ...] = ()
    production_ready: bool = False
    errors: tuple[Error, ...] = ()

    def as_error(self) -> dict[str, Any]:
        return {
            "ok": False,
            "errors": [
                {"path": error.path, "message": error.message}
                for error in self.errors
            ],
        }


# ---------------------------------------------------------------------------
# Templates


def templates() -> tuple[Template, ...]:
    """Every committed example, parsed into a draft template.

    ``examples`` already de-duplicates and sorts deterministically.  Parsing its
    payload here (instead of reading JSON again) keeps the example contract as
    the single source.
    """
    found: list[Template] = []
    for example in examples.examples():
        spec = parse_spec(example.payload, path=f"examples[{example.id}]")
        found.append(
            Template(
                id=example.id,
                pattern=example.pattern,
                meter=example.meter,
                spec=spec,
            )
        )
    return tuple(found)


def _meter_matches(template_meter: str, meter: str) -> bool:
    return template_meter == meter or template_meter == METER_ANY


def _template_bars(spec: SentenceSpec) -> int:
    """The bar span a template naturally covers."""
    if spec.span.exact or spec.span.remainder == "exact":
        return max(1, spec.select.length_min)
    if spec.span.tile is not None:
        return max(1, spec.span.tile)
    return max(1, spec.select.length_min)


def _score(template: Template, bars: int) -> tuple[int, int, int, str]:
    """Closest bar span, then a simple density/onset tie-break, then id.

    The last element makes the result deterministic when two committed
    templates describe the same geometry (the castillo 3/4 pair does).
    """
    slots = template.spec.slots
    return (
        abs(_template_bars(template.spec) - bars),
        len(slots),
        sum(slot.start for slot in slots),
        template.id,
    )


def _blank_to_none(value: str | None) -> str | None:
    """Normalise a blank/whitespace template id to the Auto default."""
    if not isinstance(value, str):
        return value
    return value.strip() or None


def choose_template(
    pattern: str,
    meter: str,
    bars: int,
    *,
    template_id: str | None = None,
) -> tuple[Template | None, list[Error]]:
    """Pick one committed template for an existing pattern/meter pair.

    A blank or whitespace `template_id` is the UI's Auto option: it is treated
    as omitted and the deterministic score picks the template.
    """
    template_id = _blank_to_none(template_id)
    available = [
        template
        for template in templates()
        if template.pattern == pattern and _meter_matches(template.meter, meter)
    ]
    if template_id is not None:
        if not isinstance(template_id, str):
            return None, [Error("templateId", "templateId must be a non-empty string")]
        chosen = next(
            (template for template in templates() if template.id == template_id),
            None,
        )
        if chosen is None:
            return None, [
                Error("templateId", f"unknown template {template_id!r}")
            ]
        if chosen.pattern != pattern:
            return None, [
                Error(
                    "templateId",
                    f"template {template_id!r} belongs to pattern "
                    f"{chosen.pattern!r}, not {pattern!r}",
                )
            ]
        if not _meter_matches(chosen.meter, meter):
            return None, [
                Error(
                    "templateId",
                    f"template {template_id!r} is {chosen.meter}; the passage is "
                    f"{meter}",
                )
            ]
        return chosen, []

    if not available:
        return None, [
            Error(
                "pattern",
                f"no committed template for pattern {pattern!r} in meter {meter}",
            )
        ]
    return min(available, key=lambda template: _score(template, bars)), []


def _default_villa_template(meter: str) -> Template:
    """A one-bar Villa arpeggio sentence for meters without a committed example.

    The figure is bar-level and already supports 2/4 in the preview adapter; the
    template exists only for the draft and is never registered.
    """
    spec = SentenceSpec(
        id=f"villa_{meter.replace('/', '_')}_arpeggio",
        pattern="villa_pattern",
        meter=meter,
        select=Select(length_min=1),
        span=Span(tile=1, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),),
    )
    return Template(
        id=spec.id,
        pattern=spec.pattern,
        meter=meter,
        spec=spec,
    )


def choose_villa_template(
    meter: str,
    bars: int,
    *,
    template_id: str | None = None,
) -> tuple[Template | None, list[Error]]:
    """Pick a Villa template for a new pattern.

    A blank/whitespace `template_id` means the UI's Auto option: filter the
    committed Villa examples by the passage meter and let the same `_score`
    helper choose. An explicit id must still be a Villa template in that meter.
    """
    template_id = _blank_to_none(template_id)
    available = [
        template
        for template in templates()
        if template.pattern in villa_preview.VILLA_PATTERNS
        and _meter_matches(template.meter, meter)
    ]
    if template_id is not None:
        if not isinstance(template_id, str):
            return None, [
                Error("newPattern.templateId", "templateId must be a non-empty string")
            ]
        chosen = next(
            (template for template in templates() if template.id == template_id),
            None,
        )
        if chosen is None:
            return None, [
                Error("newPattern.templateId", f"unknown template {template_id!r}")
            ]
        if chosen.pattern not in villa_preview.VILLA_PATTERNS:
            return None, [
                Error(
                    "newPattern.templateId",
                    f"template {template_id!r} is not a Villa template",
                )
            ]
        if not _meter_matches(chosen.meter, meter):
            return None, [
                Error(
                    "newPattern.templateId",
                    f"template {template_id!r} is {chosen.meter}; the passage is "
                    f"{meter}",
                )
            ]
        return chosen, []

    if not available:
        if meter in _VILLA_METERS:
            return _default_villa_template(meter), []
        return None, [
            Error(
                "newPattern.templateId",
                f"no committed Villa template for meter {meter}",
            )
        ]
    return min(available, key=lambda template: _score(template, bars)), []


# ---------------------------------------------------------------------------
# ids and collision rules


def _reserved_pattern_ids() -> set[str]:
    reserved = set(PILOT_PATTERNS)
    reserved.update(PATTERN_META)
    reserved.update(villa_preview.VILLA_PATTERNS)
    reserved.update(pattern for pattern, _meter in SENTENCE_SPECS)
    reserved.update(template.pattern for template in templates())
    return reserved


def _collision_error(pattern_id: str) -> Error | None:
    if pattern_id.startswith("suite_"):
        return Error(
            "newPattern.id",
            f"{pattern_id} is a single-sentence suite gate; create a new "
            "pattern id instead",
        )
    if pattern_id in _reserved_pattern_ids():
        return Error(
            "newPattern.id",
            f"pattern id {pattern_id!r} is already in the pattern registry; "
            "choose a new id",
        )
    return None


def _draft_id(
    *,
    import_id: str,
    bar_start: int,
    bar_end: int,
    meter: str,
    mode: str,
    pattern: str,
    template_id: str,
) -> str:
    seed = {
        "importId": import_id,
        "barStart": bar_start,
        "barEnd": bar_end,
        "meter": meter,
        "mode": mode,
        "pattern": pattern,
        "templateId": template_id,
    }
    payload = json.dumps(seed, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
    return f"musicxml_{import_id}_{bar_start}_{bar_end}_{digest}"


# ---------------------------------------------------------------------------
# request validation helpers


def _text(value: object, path: str) -> tuple[str | None, Error | None]:
    if not isinstance(value, str) or not value.strip():
        return None, Error(path, f"{path} must be a non-empty string")
    return value.strip(), None


def _fixture_input(spec: SentenceSpec, bars: int) -> dict[str, int]:
    """Only the passage length; n/closes/rise stay at the spec defaults."""
    if spec.span.cycle:
        return {"run_length": bars}
    return {"length": bars}


def _beat_warning(
    meter: str, beat_start: float | None, beat_end: float | None
) -> str | None:
    bar_length = quarter_beats(meter)
    partial_start = abs(float(beat_start or 0.0)) > 1e-9
    partial_end = (
        beat_end is not None
        and bar_length is not None
        and abs(float(beat_end) - float(bar_length)) > 1e-9
    )
    if not (partial_start or partial_end):
        return None
    return (
        "sentence slots are bar-based; the draft uses whole bars and ignores "
        "the beat offsets"
    )


def _bars(bar_start: int, bar_end: int) -> tuple[int | None, Error | None]:
    bars = bar_end - bar_start + 1
    if bars < 1:
        return None, Error("barEnd", "barEnd must be >= barStart")
    if bars > MAX_PLAN_BARS:
        return None, Error(
            "barEnd",
            f"the passage is {bars} bars; a draft preview supports at most "
            f"{MAX_PLAN_BARS}",
        )
    return bars, None


def _select_length_error(spec: SentenceSpec, bars: int) -> Error | None:
    """A clear error when the passage cannot fit the copied template."""
    if spec.span.cycle:
        return None
    if bars < spec.select.length_min:
        return Error(
            "barEnd",
            f"the chosen template needs at least {spec.select.length_min} "
            f"bars; the passage has {bars}",
        )
    if spec.select.length_max is not None and bars > spec.select.length_max:
        return Error(
            "barEnd",
            f"the chosen template covers at most {spec.select.length_max} "
            f"bars; the passage has {bars}",
        )
    return None


def _warning_for_length(bars: int) -> str | None:
    if bars <= MAX_RENDER_BARS:
        return None
    return (
        f"the passage is {bars} bars; the preview renders the first "
        f"{MAX_RENDER_BARS}"
    )


# ---------------------------------------------------------------------------
# preparation


def _prepare_existing(
    *,
    import_id: str,
    meter: str,
    bar_start: int,
    bar_end: int,
    bars: int,
    pattern: object,
    template_id: str | None,
    warnings: list[str],
) -> Draft:
    pattern_id, error = _text(pattern, "pattern")
    if error is not None:
        return Draft(ok=False, mode="existing", errors=(error,))
    assert pattern_id is not None

    if pattern_id.startswith("suite_"):
        return Draft(
            ok=False,
            mode="existing",
            errors=(
                Error(
                    "pattern",
                    f"{pattern_id} is a single-sentence suite gate; create a "
                    "new pattern instead",
                ),
            ),
        )
    if pattern_id not in PILOT_PATTERNS:
        return Draft(
            ok=False,
            mode="existing",
            errors=(
                Error(
                    "pattern",
                    f"{pattern_id!r} is not an existing generic pattern "
                    f"({', '.join(PILOT_PATTERNS)}); create a new pattern instead",
                ),
            ),
        )

    template, errors = choose_template(
        pattern_id, meter, bars, template_id=template_id
    )
    if template is None:
        return Draft(ok=False, mode="existing", errors=tuple(errors))
    assert template is not None

    family = dispatch.family_for(pattern_id)
    if family is None:  # defensive: PILOT_PATTERNS is the Torroba/Sor set
        return Draft(
            ok=False,
            mode="existing",
            errors=(Error("pattern", f"unknown pattern {pattern_id!r}"),),
        )

    spec = replace(
        template.spec,
        id=_draft_id(
            import_id=import_id,
            bar_start=bar_start,
            bar_end=bar_end,
            meter=meter,
            mode="existing",
            pattern=pattern_id,
            template_id=template.id,
        ),
        pattern=pattern_id,
        meter=meter,
    )
    validation = dispatch.validate(spec, family=family)
    if validation:
        return Draft(ok=False, mode="existing", errors=tuple(validation))
    length_error = _select_length_error(spec, bars)
    if length_error is not None:
        return Draft(ok=False, mode="existing", errors=(length_error,))

    try:
        fixture = dispatch.resolve_fixture(
            spec, _fixture_input(spec, bars), family=family
        )
    except (TypeError, ValueError) as exc:
        return Draft(ok=False, mode="existing", errors=(Error("fixture", str(exc)),))

    warning = _warning_for_length(bars)
    if warning is not None:
        warnings.append(warning)
    template_bars = _template_bars(template.spec)
    if template_bars != bars:
        warnings.append(
            f"template {template.id} spans {template_bars} bars; the passage "
            f"has {bars}"
        )
    return Draft(
        ok=True,
        mode="existing",
        spec=spec,
        fixture=fixture,
        template_id=template.id,
        family=family,
        warnings=tuple(warnings),
        production_ready=True,
    )


def _new_pattern_meta(
    *,
    new_pattern: Mapping[str, Any] | None,
    template_id: str | None,
    meter: str,
) -> tuple[str | None, str | None, tuple[Error, ...]]:
    """Validate only the new-pattern metadata shared by every new draft.

    The template is optional here: ``new`` mode now previews the source rhythm,
    so metadata validation must not depend on a committed template existing.
    Returns ``(pattern_id, chosen_template_id, errors)``.
    """
    if not isinstance(new_pattern, Mapping):
        return None, None, (Error("newPattern", "newPattern is required"),)

    new = dict(new_pattern)
    pattern_id, error = _text(new.get("id"), "newPattern.id")
    if error is not None:
        return None, None, (error,)
    assert pattern_id is not None

    for field in ("label", "composer"):
        _value, field_error = _text(new.get(field), f"newPattern.{field}")
        if field_error is not None:
            return None, None, (field_error,)

    renderer, error = _text(new.get("renderer"), "newPattern.renderer")
    if error is not None:
        return None, None, (error,)
    if renderer != _VILLA_RENDERER:
        return None, None, (
            Error(
                "newPattern.renderer",
                f"MVP supports renderer {_VILLA_RENDERER!r} only, got "
                f"{renderer!r}",
            ),
        )

    requested_meter = new.get("meter")
    if requested_meter is not None:
        if not isinstance(requested_meter, str) or requested_meter.strip() != meter:
            return None, None, (
                Error(
                    "newPattern.meter",
                    f"newPattern.meter must match the passage meter {meter}",
                ),
            )

    # Either templateId location may be the UI's blank Auto value. A non-blank
    # newPattern.templateId wins; otherwise the top-level field is used.
    chosen_template_id = (
        _blank_to_none(new.get("templateId"))
        or _blank_to_none(template_id)
    )

    collision = _collision_error(pattern_id)
    if collision is not None:
        return None, None, (collision,)

    return pattern_id, chosen_template_id, ()


def _prepare_new(
    *,
    import_id: str,
    meter: str,
    bar_start: int,
    bar_end: int,
    bars: int,
    new_pattern: Mapping[str, Any] | None,
    template_id: str | None,
    warnings: list[str],
) -> Draft:
    pattern_id, chosen_template_id, errors = _new_pattern_meta(
        new_pattern=new_pattern,
        template_id=template_id,
        meter=meter,
    )
    if errors:
        return Draft(ok=False, mode="new", errors=errors)
    assert pattern_id is not None

    if meter not in _VILLA_METERS:
        supported = ", ".join(sorted(_VILLA_METERS))
        return Draft(
            ok=False,
            mode="new",
            errors=(
                Error(
                    "newPattern.templateId",
                    f"no Villa template for meter {meter}; Villa drafts "
                    f"support {supported}",
                ),
            ),
        )

    template, template_errors = choose_villa_template(
        meter, bars, template_id=chosen_template_id
    )
    if template is None:
        return Draft(ok=False, mode="new", errors=tuple(template_errors))

    spec = replace(
        template.spec,
        id=_draft_id(
            import_id=import_id,
            bar_start=bar_start,
            bar_end=bar_end,
            meter=meter,
            mode="new",
            pattern=pattern_id,
            template_id=template.id,
        ),
        pattern=pattern_id,
        meter=meter,
    )
    allowed = {pattern_id}
    validation = villa_preview.validate_villa_spec(
        spec, allowed_patterns=allowed
    )
    if validation:
        return Draft(ok=False, mode="new", errors=tuple(validation))
    length_error = _select_length_error(spec, bars)
    if length_error is not None:
        return Draft(ok=False, mode="new", errors=(length_error,))

    try:
        fixture = villa_preview.resolve_fixture(spec, _fixture_input(spec, bars))
    except (TypeError, ValueError) as exc:
        return Draft(ok=False, mode="new", errors=(Error("fixture", str(exc)),))

    warning = _warning_for_length(bars)
    if warning is not None:
        warnings.append(warning)
    template_bars = _template_bars(template.spec)
    if template_bars != bars:
        warnings.append(
            f"template {template.id} spans {template_bars} bars; the passage "
            f"has {bars}"
        )
    return Draft(
        ok=True,
        mode="new",
        spec=spec,
        fixture=fixture,
        template_id=template.id,
        family=dispatch.VILLA,
        warnings=tuple(warnings),
        production_ready=False,
    )


def prepare_new_metadata(
    *,
    meter: str,
    bar_start: int,
    bar_end: int,
    new_pattern: Mapping[str, Any] | None,
    template_id: str | None = None,
) -> Draft:
    """Validate a ``new`` request without selecting or requiring a template.

    The rhythm-faithful preview is built from the passage itself, so the only
    draft checks that matter are the new-pattern id/label/composer/renderer,
    the meter match, the bar span, and the registry collision. A template id is
    accepted for compatibility but is not needed to preview the passage.
    """
    _bar_count, error = _bars(bar_start, bar_end)
    if error is not None:
        return Draft(ok=False, mode="new", errors=(error,))

    _pattern_id, _template_id, errors = _new_pattern_meta(
        new_pattern=new_pattern,
        template_id=template_id,
        meter=meter,
    )
    if errors:
        return Draft(ok=False, mode="new", errors=errors)

    # Beat offsets and long passages are handled by the passage payload itself,
    # so this metadata check returns no sentence/template warnings.
    return Draft(
        ok=True,
        mode="new",
        family=dispatch.VILLA,
        production_ready=False,
    )


def prepare_draft(
    *,
    import_id: str,
    meter: str,
    bar_start: int,
    bar_end: int,
    mode: str,
    pattern: object = None,
    template_id: str | None = None,
    new_pattern: Mapping[str, Any] | None = None,
    beat_start: float | None = 0.0,
    beat_end: float | None = None,
) -> Draft:
    """Validate the request and build the draft spec/fixture.

    The returned `Draft` is not rendered yet.  The router can therefore spend
    its quota only when this function succeeds, and a malformed request does
    not consume a draft.
    """
    if mode not in _MODES:
        return Draft(
            ok=False,
            errors=(
                Error("mode", f"mode must be one of {sorted(_MODES)}"),
            ),
        )

    bars, error = _bars(bar_start, bar_end)
    if error is not None:
        return Draft(ok=False, mode=mode, errors=(error,))
    assert bars is not None

    warnings: list[str] = []
    beat_warning = _beat_warning(meter, beat_start, beat_end)
    if beat_warning is not None:
        warnings.append(beat_warning)

    if mode == "existing":
        return _prepare_existing(
            import_id=import_id,
            meter=meter,
            bar_start=bar_start,
            bar_end=bar_end,
            bars=bars,
            pattern=pattern,
            template_id=template_id,
            warnings=warnings,
        )
    return _prepare_new(
        import_id=import_id,
        meter=meter,
        bar_start=bar_start,
        bar_end=bar_end,
        bars=bars,
        new_pattern=new_pattern,
        template_id=template_id,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# render


def render_draft(draft: Draft) -> dict[str, Any]:
    """Preview and synthesize one prepared draft."""
    if not draft.ok:
        return draft.as_error()
    if draft.spec is None or draft.fixture is None or draft.family is None:
        return Draft(
            ok=False, errors=(Error("spec", "draft is incomplete"),)
        ).as_error()

    spec = draft.spec
    fixture = draft.fixture
    if draft.mode == "new":
        preview = villa_preview.preview_villa_sentence(
            spec, fixture, allowed_patterns={spec.pattern}
        )
    else:
        preview = dispatch.preview_sentence(spec, fixture, family=draft.family)
    if not preview.ok:
        return Draft(ok=False, errors=preview.errors).as_error()

    audio = studio_audio.preview_audio(spec, fixture, family=draft.family)
    if not audio.ok or audio.asset is None:
        errors = tuple(
            Error(path, message) for path, message in audio.errors
        ) or (Error("audio", "preview audio failed"),)
        return Draft(ok=False, errors=errors).as_error()

    return {
        "ok": True,
        "mode": draft.mode,
        "spec": spec_to_mapping(spec),
        "fixture": dict(fixture),
        "preview": {
            "renderHash": audio.render_hash,
            "audioUrl": audio.asset.audio_url,
            "durationSec": audio.asset.duration_sec,
            "notes": len(preview.notes),
        },
        "warnings": list(draft.warnings),
        "productionReady": draft.production_ready,
        "templateId": draft.template_id,
    }


def draft_sentence(**kwargs: Any) -> dict[str, Any]:
    """Prepare and render in one call (tests and simple callers)."""
    return render_draft(prepare_draft(**kwargs))
