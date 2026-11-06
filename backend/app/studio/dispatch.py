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
chooses the owner and normalizes the answer. `resolve_fixture` exposes the same
per-family fixture resolution, so the compiler can write the resolved preview
input into an export bundle without a second copy of the defaults.
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

# The four families a draft may name explicitly. Production requests never pass
# `family`, so `family_for` stays the only production authority.
FAMILIES = (TORROBA_SOR, VILLA, BARRIOS, BROUWER)
_FAMILIES = frozenset(FAMILIES)

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
        "pattern",
        f"unknown pattern {pattern!r}; expected a Torroba/Sor, Villa, "
        "Barrios, or Brouwer pattern",
    )


def _unknown_family(family: object) -> preview.Error:
    return preview.Error(
        "family",
        f"unknown family {family!r}; expected one of {', '.join(FAMILIES)}",
    )


def _owner(pattern: object, family: str | None) -> str | None:
    """The family to use, honouring an explicit draft-only override."""
    if family is not None:
        return family if family in _FAMILIES else None
    return family_for(pattern)


def _villa_patterns(spec: SentenceSpec, family: str | None) -> set[str] | None:
    # A draft pattern is created by the server, so an explicit family call is
    # the only place Villa's whitelist is widened. Production calls pass no
    # family and keep the immutable `VILLA_PATTERNS` check.
    if family is None:
        return None
    pattern = getattr(spec, "pattern", None)
    return {pattern} if isinstance(pattern, str) and pattern else None


def validate(
    spec: SentenceSpec, family: str | None = None
) -> list[preview.Error]:
    """Validate one spec with its own family's rules.

    `family` is the draft-only override: when set, it selects the renderer even
    if `family_for(spec.pattern)` is `None`. Production callers omit it.
    """
    if family is not None and family not in _FAMILIES:
        return [_unknown_family(family)]
    owner = _owner(getattr(spec, "pattern", None), family)
    if owner is None:
        return [_unknown(getattr(spec, "pattern", None))]
    if owner == TORROBA_SOR:
        return preview.validate_spec(spec)
    if owner == VILLA:
        return villa_preview.validate_villa_spec(
            spec, allowed_patterns=_villa_patterns(spec, family)
        )
    if owner == BARRIOS:
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
        micro_velocity=tuple(getattr(result, "micro_velocity", ())),
    )


def preview_sentence(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None = None,
    family: str | None = None,
) -> preview.PreviewResult:
    """Validate and render one bounded fixture through the owning family.

    `family` is the draft-only override; see `validate`.
    """
    if family is not None and family not in _FAMILIES:
        return preview.PreviewResult(ok=False, errors=(_unknown_family(family),))
    owner = _owner(getattr(spec, "pattern", None), family)
    if owner is None:
        return preview.PreviewResult(
            ok=False, errors=(_unknown(getattr(spec, "pattern", None)),)
        )
    if owner == TORROBA_SOR:
        result = preview.preview_spec(spec, fixture)
    elif owner == VILLA:
        result = villa_preview.preview_villa_sentence(
            spec, fixture, allowed_patterns=_villa_patterns(spec, family)
        )
    elif owner == BARRIOS:
        result = barrios_preview.preview_barrios_period(spec, fixture)
    else:
        result = brouwer_preview.preview_brouwer_sentence(spec, fixture)
    return _normalize(result)


_RESOLVERS = {
    TORROBA_SOR: preview._resolve_fixture,
    VILLA: villa_preview._resolve_fixture,
    BARRIOS: barrios_preview._resolve_fixture,
    BROUWER: brouwer_preview._resolve_fixture,
}


def resolve_fixture(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None = None,
    family: str | None = None,
) -> dict[str, Any]:
    """The bounded fixture `preview_sentence` would render for one spec.

    The previews already apply family defaults (length, bars, profile, matrix
    axes); the compiler needs the resolved values to write `fixture.json`, so
    this exposes the same pure resolution step. It raises `ValueError` (or the
    family's `SpecParseError`) on a bad fixture; callers that already previewed
    successfully will not see one. `family` is the draft-only override.
    """
    if family is not None and family not in _FAMILIES:
        raise ValueError(f"unknown family {family!r}")
    owner = _owner(getattr(spec, "pattern", None), family)
    if owner is None:
        raise ValueError(f"unknown pattern {getattr(spec, 'pattern', None)!r}")
    return _RESOLVERS[owner](spec, fixture)
