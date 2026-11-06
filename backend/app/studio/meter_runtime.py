"""Runtime meter resolution for Texture Studio (Phase 0/1).

The Studio stores a meter as a :class:`~app.studio.texture_spec.MeterSpec`.
A pattern, sentence, or compiler bundle must be authored at the meter the
runtime will actually use, which is *after* the two form-level retargets in
``app.sonify.span``:

    requested Meter
        -> _guitar_meter                # guitar: 3/4 <-> 6/8
        -> retarget_torroba_meter       # Torroba: 4/4 calm/selloff -> 3/4
        -> resolved MeterSpec

This module is the single read-only gate for that order. It calls the real
production transforms on a one-bar carrier :class:`~app.sonify.form.FormSpec`
and keeps only the resolved ``meter`` field, so the rule is never duplicated.

Policy:

* Identity is :func:`~app.studio.texture_spec.meter_key` (the canonical tuple),
  never ``MeterSpec.id`` or its display string.
* 3/4, 4/4, and 6/8 resolve directly.
* 12/8 resolves only when an explicit ``MeterVariant`` whose canonical key is
  12/8 declares ``transform == "triplet_subdivision"`` and is supported. It is
  never silently treated as 4/4.
* Every other meter (5/4, 6/4, 7/8, 2/4, ...) fails closed.

Importing this module imports ``app.sonify.form`` and ``app.studio.texture_spec``
only; ``app.sonify.span`` is imported lazily inside the resolver. It never
imports ``guitar_patterns``, registers a spec, reads the active meter context,
or touches a database.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.sonify.form import (
    METER_34,
    METER_44,
    METER_68,
    METER_128,
    FormSpec,
    Meter,
)
from app.studio.texture_spec import MeterSpec, MeterVariant, meter_key

__all__ = [
    "APPROVED_TRANSFORMS",
    "SUPPORTED_METERS",
    "TRIPLET_SUBDIVISION_METERS",
    "MeterResolutionError",
    "check_meter_variant_chain",
    "resolve_meter_variant",
    "resolve_runtime_meter",
]

#: Transforms this gate recognises. ``triplet_subdivision`` is the only
#: non-identity transform approved for a runtime meter (4/4 bars heard as 12/8).
APPROVED_TRANSFORMS = ("none", "triplet_subdivision")

#: Meters the runtime renders without an explicit transform.
SUPPORTED_METERS = (METER_34, METER_44, METER_68)

#: Meters that need an explicit, approved ``triplet_subdivision`` variant.
TRIPLET_SUBDIVISION_METERS = (METER_128,)

_SUPPORTED_KEYS = frozenset(meter_key(meter) for meter in SUPPORTED_METERS)
_TRIPLET_KEYS = frozenset(meter_key(meter) for meter in TRIPLET_SUBDIVISION_METERS)

# Ensembles that only occur under the guitar variant (``ensemble._ALLOWED``).
# ``classic`` and ``guitar`` are shared with other variants, so a caller that
# uses them must say ``variant="guitar"`` explicitly.
_GUITAR_ONLY_ENSEMBLES = frozenset({"villa", "barrios", "brouwer", "bach", "torroba"})


class MeterResolutionError(ValueError):
    """A meter could not be resolved under the Studio fail-closed policy.

    ``path`` is the authored location (for example ``meter_variants[0].meter``)
    and ``code`` is a stable machine-readable reason. ``message`` is the human
    explanation. ``str(exc)`` is ``"<path>: <code>: <message>"``.
    """

    def __init__(self, path: str, code: str, message: str) -> None:
        self.path = path
        self.code = code
        self.message = message
        super().__init__(f"{path}: {code}: {message}" if path else f"{code}: {message}")


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------


def _key_of(meter: Meter | MeterSpec, path: str) -> tuple[Any, ...]:
    if not isinstance(meter, (Meter, MeterSpec)):
        raise MeterResolutionError(
            path, "unknown_meter", "expected an app.sonify.form.Meter or a MeterSpec"
        )
    return meter_key(meter)


def _as_meter(meter: Meter | MeterSpec, path: str) -> Meter:
    if isinstance(meter, MeterSpec):
        return meter.to_form_meter()
    if isinstance(meter, Meter):
        return meter
    raise MeterResolutionError(
        path, "unknown_meter", "expected an app.sonify.form.Meter or a MeterSpec"
    )


def _label(meter: Meter) -> str:
    return f"{meter.beats}/{meter.beat_type}"


def _carrier(meter: Meter) -> FormSpec:
    """A one-bar FormSpec that exists only to carry ``meter`` through span."""
    return FormSpec(bars=1, bpm=1, sections=(), meter=meter)


def _split_variant_argument(
    variant: str | MeterVariant | Sequence[MeterVariant] | None,
    meter_variant: MeterVariant | Sequence[MeterVariant] | None,
) -> tuple[str | None, MeterVariant | Sequence[MeterVariant] | None]:
    """Separate the production variant name from declared meter variants.

    ``variant`` is the production variant (``"guitar"``, ``"symphony"``, ...).
    For convenience it also accepts a ``MeterVariant`` or a sequence of them;
    that form is read as the approval argument, exactly like ``meter_variant``.
    """
    if variant is None or isinstance(variant, str):
        return variant, meter_variant
    if meter_variant is not None:
        raise MeterResolutionError(
            "variant",
            "ambiguous_variant",
            "pass the declared MeterVariant(s) in one of variant/meter_variant, not both",
        )
    return None, variant


def _declared_variants(
    declared: MeterVariant | Sequence[MeterVariant] | None, path: str
) -> tuple[MeterVariant, ...]:
    if declared is None:
        return ()
    if isinstance(declared, MeterVariant):
        return (declared,)
    if isinstance(declared, (str, bytes)) or not isinstance(declared, Sequence):
        raise MeterResolutionError(
            path,
            "invalid_variant",
            "expected a MeterVariant or a sequence of MeterVariants",
        )
    items: list[MeterVariant] = []
    for index, item in enumerate(declared):
        if not isinstance(item, MeterVariant):
            raise MeterResolutionError(
                f"{path}[{index}]", "invalid_variant", "expected a MeterVariant"
            )
        items.append(item)
    return tuple(items)


def _matching_declared(
    meter: Meter,
    declared: MeterVariant | Sequence[MeterVariant] | None,
    path: str,
) -> MeterVariant | None:
    key = meter_key(meter)
    matches = [
        variant
        for variant in _declared_variants(declared, path)
        if meter_key(variant.meter) == key
    ]
    if len(matches) > 1:
        raise MeterResolutionError(
            path,
            "duplicate_variant_key",
            f"more than one declared variant has canonical key {key!r}",
        )
    return matches[0] if matches else None


def _is_guitar_variant(
    variant: str | None, ensemble: str
) -> bool:
    """Whether production would run ``_guitar_meter`` for this movement.

    ``*_specs("guitar")`` is the only caller of ``_guitar_meter``, so the
    transform is gated by the variant, not by the ensemble alone. When the
    caller omits the variant, only ensembles that exist exclusively under the
    guitar variant are treated as guitar.
    """
    if variant is None:
        return ensemble in _GUITAR_ONLY_ENSEMBLES
    return variant == "guitar"


def _check_fail_closed(
    meter: Meter,
    declared: MeterVariant | Sequence[MeterVariant] | None,
    *,
    path: str,
) -> None:
    """Raise unless ``meter`` is renderable without an unapproved fallback."""
    key = meter_key(meter)
    if key in _SUPPORTED_KEYS:
        return
    if key in _TRIPLET_KEYS:
        approval = _matching_declared(meter, declared, f"{path}.variant")
        if (
            approval is None
            or approval.unsupported
            or approval.transform != "triplet_subdivision"
        ):
            raise MeterResolutionError(
                path,
                "triplet_subdivision_required",
                f"{_label(meter)} needs an explicit supported MeterVariant with "
                "transform 'triplet_subdivision'; it is never mapped to 4/4",
            )
        return
    raise MeterResolutionError(
        path,
        "unsupported_meter",
        f"{_label(meter)} has no approved materializer; supported meters are "
        "3/4, 4/4, 6/8 (and 12/8 only with an approved triplet_subdivision variant)",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_runtime_meter(
    meter: Meter | MeterSpec,
    *,
    ensemble: str,
    character: str | None = None,
    variant: str | MeterVariant | Sequence[MeterVariant] | None = None,
    meter_variant: MeterVariant | Sequence[MeterVariant] | None = None,
) -> MeterSpec:
    """Resolve the meter the runtime will use for one movement.

    The transformations are exactly production's, in production's order:

    1. ``_guitar_meter`` runs when the production variant is ``"guitar"`` and
       swaps 3/4 and 6/8.
    2. ``retarget_torroba_meter`` runs for ``ensemble == "torroba"`` on the
       guitar path and moves a 4/4 calm or selloff to 3/4.

    ``meter`` may be a :class:`~app.sonify.form.Meter` or a
    :class:`~app.studio.texture_spec.MeterSpec`; ``MeterSpec.id`` is ignored.
    ``character`` is the movement character (``"calm"``, ``"selloff"``,
    ``"rally"``, ``"volatile"``, or ``None``).

    ``variant`` is normally the production variant string. A ``MeterVariant``
    (or sequence) is also accepted there and is read as ``meter_variant``; see
    :func:`_split_variant_argument`.

    ``meter_variant`` is the declared variant (or variants) used only to
    approve 12/8. It does not select the transform.

    Raises :class:`MeterResolutionError` for 12/8 without an approved
    ``triplet_subdivision`` variant and for every other unsupported meter.
    This function never reads ``active_meter()``.
    """
    # Imported lazily: module import stays free of span's render stack and of
    # guitar_patterns.
    from app.sonify.span import _guitar_meter, retarget_torroba_meter

    production_variant, declared = _split_variant_argument(variant, meter_variant)
    requested = _as_meter(meter, "meter")

    spec = _carrier(requested)
    if _is_guitar_variant(production_variant, ensemble):
        spec = _guitar_meter(spec)
        if ensemble == "torroba":
            spec = retarget_torroba_meter(spec, character)

    resolved = spec.meter
    _check_fail_closed(resolved, declared, path="meter")
    return MeterSpec.from_form_meter(resolved)


def resolve_meter_variant(
    meter: Meter | MeterSpec,
    variants: Sequence[MeterVariant],
    *,
    path: str = "meter",
) -> MeterVariant:
    """Return the variant whose canonical meter key matches ``meter``.

    Matching uses :func:`meter_key` only, so a variant's ``MeterSpec.id`` (or a
    display string such as ``"6/8"`` on 3/4 fields) cannot change the answer.
    An unknown key, a duplicate key, or a non-``MeterVariant`` item raises
    :class:`MeterResolutionError`.
    """
    key = _key_of(meter, path)
    if isinstance(variants, (str, bytes)) or not isinstance(variants, Sequence):
        raise MeterResolutionError(
            path, "invalid_variants", "expected a sequence of MeterVariants"
        )
    matches: list[MeterVariant] = []
    for index, variant in enumerate(variants):
        if not isinstance(variant, MeterVariant):
            raise MeterResolutionError(
                f"{path}[{index}]", "invalid_variant", "expected a MeterVariant"
            )
        if meter_key(variant.meter) == key:
            matches.append(variant)
    if not matches:
        raise MeterResolutionError(
            path, "unknown_meter_variant", f"no MeterVariant matches canonical key {key!r}"
        )
    if len(matches) > 1:
        raise MeterResolutionError(
            path,
            "duplicate_variant_key",
            f"more than one MeterVariant matches canonical key {key!r}",
        )
    return matches[0]


def check_meter_variant_chain(
    pattern_variants: Sequence[MeterVariant],
    composer_meters: Sequence[Meter | MeterSpec],
    *,
    path: str = "pattern.meter_variants",
) -> tuple[tuple[Any, ...], ...]:
    """Validate a pattern's variants against its composer's meter list.

    Rules (doc section 4.5):

    * two pattern variants may not share a canonical meter key, even when one
      is marked unsupported;
    * every supported variant's key must appear in ``composer_meters``;
    * unsupported variants are exempt from the composer membership check.

    Returns the supported canonical keys in declaration order. Raises
    :class:`MeterResolutionError` on the first violation, with a path such as
    ``pattern.meter_variants[1].meter``.
    """
    if isinstance(composer_meters, (str, bytes)) or not isinstance(
        composer_meters, Sequence
    ):
        raise MeterResolutionError(
            "composer.meters", "invalid_meters", "expected a sequence of meters"
        )
    composer_keys = {
        _key_of(meter, f"composer.meters[{index}]")
        for index, meter in enumerate(composer_meters)
    }

    if isinstance(pattern_variants, (str, bytes)) or not isinstance(
        pattern_variants, Sequence
    ):
        raise MeterResolutionError(
            path, "invalid_variants", "expected a sequence of MeterVariants"
        )

    seen: dict[tuple[Any, ...], int] = {}
    supported: list[tuple[Any, ...]] = []
    for index, variant in enumerate(pattern_variants):
        item = f"{path}[{index}]"
        if not isinstance(variant, MeterVariant):
            raise MeterResolutionError(
                item, "invalid_variant", "expected a MeterVariant"
            )
        key = _key_of(variant.meter, f"{item}.meter")
        if key in seen:
            raise MeterResolutionError(
                f"{item}.meter",
                "duplicate_variant_key",
                f"duplicate canonical key {key!r} (also at {path}[{seen[key]}])",
            )
        seen[key] = index
        if variant.unsupported:
            continue
        if key not in composer_keys:
            raise MeterResolutionError(
                f"{item}.meter",
                "variant_not_in_composer",
                f"supported variant key {key!r} is not declared by the composer",
            )
        supported.append(key)
    return tuple(supported)
