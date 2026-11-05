"""Phase 0 tests for ``app.studio.meter_runtime``.

The resolver must reuse production's form-level transforms in production's
order and fail closed on meters the runtime cannot render. Nothing here
renders, registers, or calls ``active_meter()``; one test monkeypatches
``active_meter`` to raise to prove it is never consulted.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.sonify import sentence_specs
from app.sonify.form import (
    METER_34,
    METER_44,
    METER_54,
    METER_64,
    METER_68,
    METER_78,
    METER_128,
    FormSpec,
    Meter,
)
from app.sonify.span import _guitar_meter, retarget_torroba_meter
from app.studio.meter_runtime import (
    APPROVED_TRANSFORMS,
    SUPPORTED_METERS,
    TRIPLET_SUBDIVISION_METERS,
    MeterResolutionError,
    check_meter_variant_chain,
    resolve_meter_variant,
    resolve_runtime_meter,
)
from app.studio.texture_spec import (
    MeterSpec,
    MeterVariant,
    meter_key,
)


def _spec(meter: Meter = METER_34, *, id: str | None = None) -> MeterSpec:
    return MeterSpec.from_form_meter(meter, id=id)


def _variant(
    meter: Meter = METER_34,
    *,
    id: str | None = None,
    transform: str = "none",
    unsupported: bool = False,
    materializer: str | None = "grid",
) -> MeterVariant:
    return MeterVariant(
        meter=_spec(meter, id=id),
        materializer=materializer,
        transform=transform,
        unsupported=unsupported,
        reason="test" if unsupported else None,
    )


def _carrier(meter: Meter) -> FormSpec:
    return FormSpec(bars=1, bpm=1, sections=(), meter=meter)


def _assert_key(actual: MeterSpec, expected: Meter) -> None:
    assert meter_key(actual) == meter_key(expected)


# ---------------------------------------------------------------------------
# Guitar form transform: _guitar_meter
# ---------------------------------------------------------------------------


def test_guitar_swaps_three_four_and_six_eight() -> None:
    three = resolve_runtime_meter(METER_34, ensemble="torroba", variant="guitar")
    six = resolve_runtime_meter(METER_68, ensemble="torroba", variant="guitar")
    assert three.beats == 6 and three.beat_type == 8
    assert six.beats == 3 and six.beat_type == 4
    _assert_key(three, METER_68)
    _assert_key(six, METER_34)


def test_guitar_leaves_four_four_alone() -> None:
    resolved = resolve_runtime_meter(METER_44, ensemble="villa", variant="guitar")
    _assert_key(resolved, METER_44)


@pytest.mark.parametrize("ensemble", ["villa", "barrios", "brouwer", "bach", "torroba"])
def test_resolver_matches_the_real_guitar_transform(ensemble: str) -> None:
    for meter in SUPPORTED_METERS:
        resolved = resolve_runtime_meter(meter, ensemble=ensemble, variant="guitar")
        # `_guitar_meter` is production's real transform; compare its meter output.
        expected = _guitar_meter(_carrier(meter)).meter
        _assert_key(resolved, expected)


def test_resolver_reuses_the_real_torroba_transform() -> None:
    for character in (None, "calm", "selloff", "rally", "volatile"):
        resolved = resolve_runtime_meter(
            METER_44, ensemble="torroba", character=character, variant="guitar"
        )
        expected = retarget_torroba_meter(_guitar_meter(_carrier(METER_44)), character).meter
        _assert_key(resolved, expected)


# ---------------------------------------------------------------------------
# Torroba retarget: retarget_torroba_meter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("character", ["calm", "selloff"])
def test_torroba_four_four_calm_and_selloff_become_three_four(character: str) -> None:
    resolved = resolve_runtime_meter(
        METER_44, ensemble="torroba", character=character, variant="guitar"
    )
    assert (resolved.beats, resolved.beat_type) == (3, 4)
    _assert_key(resolved, METER_34)


@pytest.mark.parametrize("character", ["rally", "volatile", None])
def test_torroba_four_four_rally_volatile_and_none_stay(character: str | None) -> None:
    resolved = resolve_runtime_meter(
        METER_44, ensemble="torroba", character=character, variant="guitar"
    )
    _assert_key(resolved, METER_44)


@pytest.mark.parametrize("ensemble", ["classic", "villa", "barrios", "brouwer", "bach"])
def test_non_torroba_guitar_does_not_retarget(ensemble: str) -> None:
    resolved = resolve_runtime_meter(
        METER_44, ensemble=ensemble, character="calm", variant="guitar"
    )
    _assert_key(resolved, METER_44)


# ---------------------------------------------------------------------------
# Non-guitar is unaffected by _guitar_meter
# ---------------------------------------------------------------------------


def test_non_guitar_variant_is_not_swapped() -> None:
    resolved = resolve_runtime_meter(METER_34, ensemble="classic", variant="symphony")
    _assert_key(resolved, METER_34)
    # Production would swap this meter on the guitar path; the gate keeps it.
    assert meter_key(_guitar_meter(_carrier(METER_34)).meter) == meter_key(METER_68)

    six = resolve_runtime_meter(METER_68, ensemble="classic", variant="symphony")
    _assert_key(six, METER_68)


def test_minimalist_guitar_ensemble_is_not_the_guitar_variant() -> None:
    resolved = resolve_runtime_meter(METER_34, ensemble="guitar", variant="minimalist")
    _assert_key(resolved, METER_34)


def test_omitted_variant_infers_only_guitar_exclusive_ensembles() -> None:
    # villa/torroba/... only exist under the guitar variant in production.
    _assert_key(
        resolve_runtime_meter(METER_34, ensemble="villa"),
        METER_68,
    )
    # classic and guitar are shared with other variants, so no inference.
    _assert_key(
        resolve_runtime_meter(METER_34, ensemble="classic"),
        METER_34,
    )
    _assert_key(
        resolve_runtime_meter(METER_34, ensemble="guitar"),
        METER_34,
    )


# ---------------------------------------------------------------------------
# Canonical key, not id
# ---------------------------------------------------------------------------


def test_canonical_key_equality_ignores_id() -> None:
    a = _spec(METER_34, id="mazurka")
    b = _spec(METER_34, id="3/4")
    assert a != b  # the display id differs
    assert meter_key(a) == meter_key(b)


def test_variant_lookup_uses_key_and_ignores_mismatched_id() -> None:
    variant = _variant(METER_34, id="mazurka")
    requested = _spec(METER_34, id="3/4")
    assert resolve_meter_variant(requested, [variant]) is variant
    # Even a misleading id on the lookup meter cannot change the key match.
    mislabeled = _spec(METER_34, id="6/8")
    assert resolve_meter_variant(mislabeled, [variant]) is variant


def test_variant_lookup_unknown_key_raises() -> None:
    variant = _variant(METER_34)
    with pytest.raises(MeterResolutionError) as info:
        resolve_meter_variant(METER_68, [variant])
    assert info.value.code == "unknown_meter_variant"
    assert info.value.path == "meter"


def test_variant_lookup_duplicate_key_raises() -> None:
    first = _variant(METER_34, id="one")
    second = _variant(METER_34, id="two")
    with pytest.raises(MeterResolutionError) as info:
        resolve_meter_variant(METER_34, [first, second])
    assert info.value.code == "duplicate_variant_key"


def test_variant_lookup_accepts_meter_spec_or_form_meter() -> None:
    variant = _variant(METER_34)
    assert resolve_meter_variant(METER_34, [variant]) is variant
    assert resolve_meter_variant(_spec(METER_34), [variant]) is variant


# ---------------------------------------------------------------------------
# Variant chain: supported keys in the composer set, duplicate keys rejected
# ---------------------------------------------------------------------------


def test_chain_accepts_supported_variant_in_composer_set() -> None:
    variants = [_variant(METER_34), _variant(METER_44)]
    composers = [_spec(METER_34), _spec(METER_44), _spec(METER_68)]
    assert check_meter_variant_chain(variants, composers) == (
        meter_key(METER_34),
        meter_key(METER_44),
    )


def test_chain_rejects_duplicate_keys_even_when_unsupported() -> None:
    variants = [
        _variant(METER_34, id="a"),
        _variant(METER_34, id="b", unsupported=True, materializer=None),
    ]
    with pytest.raises(MeterResolutionError) as info:
        check_meter_variant_chain(variants, [_spec(METER_34)])
    assert info.value.code == "duplicate_variant_key"
    assert info.value.path == "pattern.meter_variants[1].meter"


def test_chain_rejects_supported_variant_absent_from_composer() -> None:
    variants = [_variant(METER_34), _variant(METER_68)]
    with pytest.raises(MeterResolutionError) as info:
        check_meter_variant_chain(variants, [_spec(METER_34)])
    assert info.value.code == "variant_not_in_composer"
    assert info.value.path == "pattern.meter_variants[1].meter"


def test_chain_skips_composer_check_for_unsupported_variant() -> None:
    variants = [
        _variant(METER_34),
        _variant(METER_68, unsupported=True, materializer=None),
    ]
    assert check_meter_variant_chain(variants, [_spec(METER_34)]) == (
        meter_key(METER_34),
    )


# ---------------------------------------------------------------------------
# Fail closed: 12/8, 5/4, 6/4, 7/8
# ---------------------------------------------------------------------------


def test_twelve_eight_without_approval_raises_and_never_becomes_four_four() -> None:
    with pytest.raises(MeterResolutionError) as info:
        resolve_runtime_meter(METER_128, ensemble="classic", variant="symphony")
    assert info.value.code == "triplet_subdivision_required"
    assert info.value.path == "meter"
    assert "12/8" in info.value.message
    assert "triplet_subdivision" in info.value.message


@pytest.mark.parametrize("transform", ["none", "unknown"])
def test_twelve_eight_needs_approved_triplet_subdivision(transform: str) -> None:
    unapproved = _variant(METER_128, transform=transform)
    with pytest.raises(MeterResolutionError) as info:
        resolve_runtime_meter(
            METER_128, ensemble="classic", variant="symphony", meter_variant=unapproved
        )
    assert info.value.code == "triplet_subdivision_required"


def test_twelve_eight_unsupported_variant_is_not_approval() -> None:
    unsupported = _variant(
        METER_128,
        transform="triplet_subdivision",
        unsupported=True,
        materializer=None,
    )
    with pytest.raises(MeterResolutionError) as info:
        resolve_runtime_meter(
            METER_128, ensemble="classic", variant="symphony", meter_variant=unsupported
        )
    assert info.value.code == "triplet_subdivision_required"


def test_twelve_eight_variant_for_another_meter_is_not_approval() -> None:
    wrong = _variant(METER_44, transform="triplet_subdivision")
    with pytest.raises(MeterResolutionError) as info:
        resolve_runtime_meter(
            METER_128, ensemble="classic", variant="symphony", meter_variant=wrong
        )
    assert info.value.code == "triplet_subdivision_required"


def test_twelve_eight_with_approved_variant_resolves() -> None:
    approved = _variant(
        METER_128, id="misleading-id", transform="triplet_subdivision", materializer="grid_12_8"
    )
    resolved = resolve_runtime_meter(
        METER_128, ensemble="classic", variant="symphony", meter_variant=approved
    )
    _assert_key(resolved, METER_128)
    assert "triplet_subdivision" in APPROVED_TRANSFORMS
    assert meter_key(METER_128) in {meter_key(m) for m in TRIPLET_SUBDIVISION_METERS}


def test_twelve_eight_can_be_approved_through_the_variant_argument() -> None:
    # `variant` also accepts the declared MeterVariant for callers that read
    # the doc's "explicit variant" literally.
    approved = _variant(METER_128, transform="triplet_subdivision")
    resolved = resolve_runtime_meter(METER_128, ensemble="classic", variant=approved)
    _assert_key(resolved, METER_128)


@pytest.mark.parametrize("meter", [METER_54, METER_64, METER_78])
def test_other_meters_fail_closed(meter: Meter) -> None:
    with pytest.raises(MeterResolutionError) as info:
        resolve_runtime_meter(meter, ensemble="classic", variant="symphony")
    assert info.value.code == "unsupported_meter"
    assert f"{meter.beats}/{meter.beat_type}" in info.value.message


@pytest.mark.parametrize("meter", [METER_54, METER_64, METER_78])
def test_a_triplet_variant_does_not_approve_other_meters(meter: Meter) -> None:
    variant = _variant(meter, transform="triplet_subdivision")
    with pytest.raises(MeterResolutionError) as info:
        resolve_runtime_meter(
            meter, ensemble="classic", variant="symphony", meter_variant=variant
        )
    assert info.value.code == "unsupported_meter"


def test_twelve_eight_stays_twelve_eight_on_the_guitar_path() -> None:
    # _guitar_meter does not touch 12/8; only the fail-closed check decides.
    approved = _variant(METER_128, transform="triplet_subdivision")
    resolved = resolve_runtime_meter(
        METER_128, ensemble="torroba", character="calm", variant="guitar", meter_variant=approved
    )
    _assert_key(resolved, METER_128)


# ---------------------------------------------------------------------------
# active_meter is never a source
# ---------------------------------------------------------------------------


def test_resolver_never_consults_active_meter(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.sonify.form as form

    def boom() -> Meter:
        raise AssertionError("active_meter() must not be read by the resolver")

    monkeypatch.setattr(form, "active_meter", boom)

    _assert_key(resolve_runtime_meter(METER_34, ensemble="torroba", variant="guitar"), METER_68)
    _assert_key(
        resolve_runtime_meter(
            METER_44, ensemble="torroba", character="calm", variant="guitar"
        ),
        METER_34,
    )


# ---------------------------------------------------------------------------
# Purity: no registration, no guitar_patterns import
# ---------------------------------------------------------------------------


def test_resolving_does_not_mutate_the_sentence_registry() -> None:
    before = dict(sentence_specs.SENTENCE_SPECS)
    for meter in (METER_34, METER_44, METER_68):
        for ensemble, variant in (
            ("torroba", "guitar"),
            ("villa", "guitar"),
            ("classic", "symphony"),
        ):
            resolve_runtime_meter(meter, ensemble=ensemble, variant=variant)
    assert dict(sentence_specs.SENTENCE_SPECS) == before


def test_import_and_resolve_do_not_load_guitar_patterns() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import sys\n"
        "from app.sonify.sentence_specs import SENTENCE_SPECS\n"
        "from app.sonify.form import METER_34, METER_44\n"
        "before = len(SENTENCE_SPECS)\n"
        "from app.studio.meter_runtime import resolve_runtime_meter\n"
        "resolve_runtime_meter(METER_34, ensemble='torroba', variant='guitar')\n"
        "resolve_runtime_meter(METER_44, ensemble='classic', variant='symphony')\n"
        "print(before, len(SENTENCE_SPECS), "
        "'app.sonify.guitar_patterns' in sys.modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    before, after, loaded = completed.stdout.split()
    assert before == after
    assert loaded == "False"


def test_supported_meter_constants_match_the_fail_closed_policy() -> None:
    assert {meter_key(meter) for meter in SUPPORTED_METERS} == {
        meter_key(METER_34),
        meter_key(METER_44),
        meter_key(METER_68),
    }
    assert {meter_key(meter) for meter in TRIPLET_SUBDIVISION_METERS} == {
        meter_key(METER_128)
    }
