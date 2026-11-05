"""Dispatch an authored Studio spec to the preview family that owns it.

The Studio UI posts every spec to the same endpoints, but a pattern belongs to
exactly one family, and each family has its own validator and renderer:

================  =====================  ==================================
family            patterns               module
================  =====================  ==================================
`torroba_sor`     the five registered    `app.studio.preview`
                  Torroba/Sor pilots
`villa`           `villa_pattern`,       `app.studio.villa_preview`
                  `chord_melody`,
                  `etude1`, `etude11`
`barrios`         the Barrios figure     `app.studio.barrios_preview`
                  patterns (the pilot
                  is `preludio`)
`brouwer`         the Brouwer figure     `app.studio.brouwer_preview`
                  patterns (the pilot
                  is `brouwer_etude`)
================  =====================  ==================================

The candidate modules already return `preview.PreviewResult`, so the API keeps
one response shape (`ok, errors, plan, row, notes, renderHash, matrix`) no
matter which family answered. `_normalize` re-checks that contract instead of
trusting it: a family that grows its own result type still answers in the
shared spelling.

Nothing here registers a spec or touches the global `SENTENCE_SPECS`. The
family modules keep owning their validation and rendering; this module only
chooses the owner and normalizes the answer.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.sonify.guitar_barrios_figures import BARRIOS_PATTERNS
from app.sonify.guitar_brouwer_figures import BROUWER_PATTERNS
from app.sonify.sentence_specs import SentenceSpec
from app.studio import barrios_preview, brouwer_preview, preview, villa_preview
from app.studio.export import PILOT_PATTERNS

TORROBA_SOR = "torroba_sor"
VILLA = "villa"
BARRIOS = "barrios"
BROUWER = "brouwer"

# `PILOT_PATTERNS` is exactly the registered Torroba/Sor set today; it is the
# public order-stable list that the exporter already owns.
_TORROBA_SOR_PATTERNS = frozenset(PILOT_PATTERNS)
_VILLA_PATTERNS = villa_preview.VILLA_PATTERNS
_BARRIOS_PATTERNS = frozenset(BARRIOS_PATTERNS)
_BROUWER_PATTERNS = frozenset(BROUWER_PATTERNS)


def family_for(pattern: object) -> str | None:
    """The family that owns `pattern`, or `None` when nobody does."""
    if not isinstance(pattern, str):
        return None
    if pattern in _TORROBA_SOR_PATTERNS:
        return TORROBA_SOR
    if pattern in _VILLA_PATTERNS:
        return VILLA
    if pattern in _BARRIOS_PATTERNS:
        return BARRIOS
    if pattern in _BROUWER_PATTERNS:
        return BROUWER
    return None


def _unknown(pattern: object) -> preview.Error:
    return preview.Error(
        "spec.pattern",
        f"unknown pattern {pattern!r}; expected a Torroba/Sor, Villa, "
        "Barrios, or Brouwer pattern",
    )


def validate(spec: SentenceSpec) -> list[preview.Error]:
    """Validate one spec with its own family's rules."""
    family = family_for(getattr(spec, "pattern", None))
    if family is None:
        return [_unknown(getattr(spec, "pattern", None))]
    if family == TORROBA_SOR:
        return preview.validate_spec(spec)
    if family == VILLA:
        return villa_preview.validate_villa_spec(spec)
    if family == BARRIOS:
        return barrios_preview.validate_barrios_period(spec)
    return brouwer_preview.validate_brouwer_spec(spec)


def _normalize(result: Any) -> preview.PreviewResult:
    """The shared preview record, whichever family produced it."""
    if isinstance(result, preview.PreviewResult):
        return result
    return preview.PreviewResult(
        ok=bool(result.ok),
        errors=tuple(
            preview.Error(path=str(error.path), message=str(error.message))
            for error in result.errors
        ),
        plan=result.plan,
        row=result.row,
        notes=tuple(result.notes),
        render_hash=result.render_hash,
        matrix=tuple(result.matrix),
    )


def preview_sentence(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None = None
) -> preview.PreviewResult:
    """Validate and render one bounded fixture through the owning family."""
    family = family_for(getattr(spec, "pattern", None))
    if family is None:
        return preview.PreviewResult(
            ok=False, errors=(_unknown(getattr(spec, "pattern", None)),)
        )
    if family == TORROBA_SOR:
        result = preview.preview_spec(spec, fixture)
    elif family == VILLA:
        result = villa_preview.preview_villa_sentence(spec, fixture)
    elif family == BARRIOS:
        result = barrios_preview.preview_barrios_period(spec, fixture)
    else:
        result = brouwer_preview.preview_brouwer_sentence(spec, fixture)
    return _normalize(result)
