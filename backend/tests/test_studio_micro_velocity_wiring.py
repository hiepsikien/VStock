"""Micro-velocity wiring into sentence, texture, compiler, and preview JSON.

The §6.9 model lives in ``app.studio.micro_velocity`` and owns its own parse,
validation, and serialization. These tests only prove the authoring schemas
carry it: slot/texture round-trip, bounded paths, the compiler bundle, and the
preview passthrough. Nothing here renders a contour or changes a ``NoteEvent``.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio as studio_router
from app.sonify.sentence_specs import SentenceSpec
from app.studio import compiler, preview
from app.studio.export import SPECS_DIR
from app.studio.micro_velocity import (
    MicroVelocity,
    VelocityOffset,
    parse_micro_velocity,
)
from app.studio.sentence_spec import parse_spec, spec_to_mapping
from app.studio.texture_spec import (
    MeterSpec,
    MeterVariant,
    TextureSpec,
    check_texture_spec,
    parse_texture_spec,
    texture_spec_to_mapping,
    validate_authored,
    validate_texture_spec,
)
from app.sonify.form import METER_44

CONTOUR = {
    "kind": "offsets",
    "notes": [{"bar": 0, "beat": 0.0, "voice": 1, "offset": -6}],
    "thumb": [],
}


def _castillo_payload() -> dict:
    return json.loads(
        (SPECS_DIR / "castillo-3-4.json").read_text(encoding="utf-8")
    )["specs"][0]


def _with_contour(payload: dict | None = None, contour: dict | None = None) -> dict:
    data = copy.deepcopy(payload if payload is not None else _castillo_payload())
    data["slots"][0]["microVelocity"] = copy.deepcopy(
        contour if contour is not None else CONTOUR
    )
    return data


def _spec_payload(filename: str, spec_id: str) -> dict:
    data = json.loads((SPECS_DIR / filename).read_text(encoding="utf-8"))
    for spec in data["specs"]:
        if spec["id"] == spec_id:
            return copy.deepcopy(spec)
    raise AssertionError(f"{filename} has no spec {spec_id!r}")


def _slot_spec() -> SentenceSpec:
    return parse_spec(_with_contour())


def _texture_mapping() -> dict:
    return {
        "id": "suite_mazurka",
        "composer": "villa",
        "kind": "pattern",
        "level": "topic",
        "runtime": "code",
        "status": "draft",
        "meter_variants": [
            {
                "meter": {
                    "id": "4/4",
                    "beats": 4,
                    "beat_type": 4,
                    "eighths_per_bar": 8,
                    "strong_eighths": [0],
                    "subbar_breaks": [4],
                    "extra_weights": [],
                },
                "materializer": "grid_4_4",
            }
        ],
        "authored": {
            "events": [
                {
                    "bar": 0,
                    "beat": 0.0,
                    "duration_beats": 1.0,
                    "voice": 1,
                    "pitch": {"kind": "chord_root"},
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# Sentence slot
# ---------------------------------------------------------------------------


def test_slot_contour_round_trips_and_is_typed() -> None:
    payload = _with_contour()
    spec = parse_spec(payload)

    contour = spec.slots[0].micro_velocity
    assert contour == parse_micro_velocity(CONTOUR)
    assert spec_to_mapping(spec)["slots"][0]["microVelocity"] == CONTOUR
    assert parse_spec(spec_to_mapping(spec)) == spec


def test_absent_slot_contour_parses_as_none_and_is_not_emitted() -> None:
    payload = _castillo_payload()
    spec = parse_spec(payload)

    assert spec.slots[0].micro_velocity is None
    assert "microVelocity" not in spec_to_mapping(spec)["slots"][0]
    assert spec_to_mapping(spec) == payload


def test_slot_contour_bar_bound_uses_slot_bars() -> None:
    payload = _with_contour()
    payload["slots"][0]["microVelocity"]["notes"][0]["bar"] = 9

    with pytest.raises(ValueError) as excinfo:
        parse_spec(payload)
    assert "slots[0].microVelocity.notes[0].bar" in str(excinfo.value)
    assert "outside figure length 9" in str(excinfo.value)


def test_slot_contour_beat_bound_uses_the_meter() -> None:
    payload = _with_contour()
    payload["slots"][0]["microVelocity"]["notes"][0]["beat"] = 3.0

    with pytest.raises(ValueError) as excinfo:
        parse_spec(payload)
    assert "slots[0].microVelocity.notes[0].beat" in str(excinfo.value)
    assert "outside bar length 3.0" in str(excinfo.value)


def test_slot_contour_duplicate_keeps_the_authored_slot_path() -> None:
    payload = _with_contour()
    payload["slots"][0]["microVelocity"]["notes"].append(
        {"bar": 0, "beat": 0.0, "voice": 1, "offset": -2}
    )

    with pytest.raises(ValueError) as excinfo:
        parse_spec(payload)
    assert "slots[0].microVelocity.notes[1]" in str(excinfo.value)
    assert "duplicate key" in str(excinfo.value)


def test_slot_contour_pinned_error_keeps_the_authored_slot_path() -> None:
    payload = _with_contour(
        contour={
            "kind": "offsets",
            "notes": [
                {
                    "bar": 0,
                    "beat": 0.0,
                    "voice": 1,
                    "offset": -6,
                    "pinned": True,
                    "velocity": 60,
                }
            ],
            "thumb": [],
        }
    )

    with pytest.raises(ValueError) as excinfo:
        parse_spec(payload)
    assert "slots[0].microVelocity.notes[0].offset" in str(excinfo.value)
    assert "not allowed when pinned" in str(excinfo.value)


def test_preview_validate_reports_the_slot_contour_path() -> None:
    spec = _slot_spec()
    bad = MicroVelocity(
        notes=(VelocityOffset(bar=99, beat=0.0, voice=1, offset=-3),)
    )
    broken = SentenceSpec(
        id=spec.id,
        pattern=spec.pattern,
        meter=spec.meter,
        select=spec.select,
        span=spec.span,
        slots=(replace(spec.slots[0], micro_velocity=bad),),
    )

    paths = [error.path for error in preview.validate_spec(broken)]
    assert "slots[0].microVelocity.notes[0].bar" in paths


# ---------------------------------------------------------------------------
# Texture spec
# ---------------------------------------------------------------------------


def test_texture_contour_round_trips_and_is_optional() -> None:
    mapping = _texture_mapping()
    mapping["microVelocity"] = copy.deepcopy(CONTOUR)

    spec = parse_texture_spec(mapping)
    assert spec.micro_velocity == parse_micro_velocity(CONTOUR)
    assert texture_spec_to_mapping(spec)["microVelocity"] == CONTOUR
    assert parse_texture_spec(texture_spec_to_mapping(spec)) == spec


def test_absent_texture_contour_is_none_and_not_emitted() -> None:
    spec = parse_texture_spec(_texture_mapping())
    assert spec.micro_velocity is None
    assert "microVelocity" not in texture_spec_to_mapping(spec)


def test_texture_contour_parse_error_uses_the_texture_path() -> None:
    mapping = _texture_mapping()
    mapping["microVelocity"] = copy.deepcopy(CONTOUR)
    mapping["microVelocity"]["notes"].append(
        {"bar": 0, "beat": 0.0, "voice": 1, "offset": -2}
    )

    errors = check_texture_spec(mapping)
    assert [error.path for error in errors] == ["spec.microVelocity.notes[1]"]
    assert "duplicate key" in errors[0].message


def test_texture_contour_validation_reuses_the_model_rules() -> None:
    mapping = _texture_mapping()
    spec = parse_texture_spec(mapping)
    broken = TextureSpec(
        id=spec.id,
        composer=spec.composer,
        kind=spec.kind,
        level=spec.level,
        runtime=spec.runtime,
        status=spec.status,
        meter_variants=spec.meter_variants,
        micro_velocity=MicroVelocity(kind="unknown"),
    )

    errors = validate_texture_spec(broken)
    assert [error.path for error in errors] == ["microVelocity.kind"]


def test_event_velocity_offset_round_trips_and_validates_range() -> None:
    mapping = _texture_mapping()
    mapping["authored"]["events"][0]["velocityOffset"] = -4

    spec = parse_texture_spec(mapping)
    event = spec.authored[0]
    assert event.velocity_offset == -4
    assert texture_spec_to_mapping(spec)["authored"]["events"][0][
        "velocityOffset"
    ] == -4
    assert validate_authored((event,), METER_44) == ()

    out_of_range = replace(event, velocity_offset=200)
    errors = validate_authored((out_of_range,), METER_44)
    assert [error.path for error in errors] == ["authored.events[0].velocityOffset"]
    assert "integer in -126..126" in errors[0].message

    not_an_integer = replace(event, velocity_offset=1.5)
    errors = validate_authored((not_an_integer,), METER_44)
    assert [error.path for error in errors] == ["authored.events[0].velocityOffset"]


def test_absent_event_velocity_offset_is_none_and_not_emitted() -> None:
    spec = parse_texture_spec(_texture_mapping())
    assert spec.authored[0].velocity_offset is None
    assert "velocityOffset" not in texture_spec_to_mapping(spec)["authored"]["events"][0]


def test_boolean_velocity_offset_is_rejected_by_parse() -> None:
    mapping = _texture_mapping()
    mapping["authored"]["events"][0]["velocityOffset"] = True

    with pytest.raises(ValueError) as excinfo:
        parse_texture_spec(mapping)
    assert "authored.events[0].velocityOffset" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Compiler bundle and preview
# ---------------------------------------------------------------------------


def test_compile_bundle_carries_the_slot_contour() -> None:
    spec = _slot_spec()
    bundle = compiler.compile_sentence(spec)

    assert bundle["spec"]["slots"][0]["microVelocity"] == CONTOUR

    plain = compiler.compile_sentence(parse_spec(_castillo_payload()))
    assert "microVelocity" not in plain["spec"]["slots"][0]


def test_preview_returns_slot_contours_without_changing_notes() -> None:
    plain = preview.preview_spec(parse_spec(_castillo_payload()))
    contoured = preview.preview_spec(_slot_spec())

    assert plain.ok and contoured.ok
    assert plain.micro_velocity == ()
    assert contoured.micro_velocity == (
        {
            "slot": 0,
            "start": 0,
            "bars": 9,
            "tile": 9,
            "exact": False,
            "cycle": False,
            "contour": CONTOUR,
        },
    )

    # The contour is authored data: the render itself stays identical, but the
    # hash (and therefore the audio cache key) must tell the two specs apart.
    assert contoured.notes == plain.notes
    assert contoured.render_hash != plain.render_hash

    assert "microVelocity" not in plain.as_response()
    assert contoured.as_response()["microVelocity"] == [
        {
            "slot": 0,
            "start": 0,
            "bars": 9,
            "tile": 9,
            "exact": False,
            "cycle": False,
            "contour": CONTOUR,
        }
    ]


def test_preview_reports_a_late_slot_origin() -> None:
    """A slot at `start=1` maps contour bar 0 to preview bar 1."""
    payload = _spec_payload("castillo-4-4.json", "castillo_44_pair_odd")
    payload["slots"][0]["microVelocity"] = copy.deepcopy(CONTOUR)

    result = preview.preview_spec(parse_spec(payload))

    assert result.ok, result.errors
    assert result.micro_velocity == (
        {
            "slot": 0,
            "start": 1,
            "bars": 2,
            "tile": None,
            "exact": True,
            "cycle": False,
            "contour": CONTOUR,
        },
    )


def test_preview_resolves_middle_and_end_slot_origins() -> None:
    """Middle/end anchors are length-relative, so the fixture resolves them."""
    middle = _spec_payload("fandanguillo-any.json", "fan_odd_open")
    middle["slots"][0]["microVelocity"] = copy.deepcopy(CONTOUR)
    middle_result = preview.preview_spec(parse_spec(middle), {"length": 4})
    assert middle_result.ok, middle_result.errors
    # anchor="middle", start=-1, bars=2 in a 4-bar phrase: 4//2 - 1 = 1.
    assert middle_result.micro_velocity[0]["start"] == 1
    assert middle_result.micro_velocity[0]["bars"] == 2

    end = _spec_payload("sonatina-any.json", "son_close_l4_5")
    end["slots"][0]["microVelocity"] = copy.deepcopy(CONTOUR)
    end_result = preview.preview_spec(parse_spec(end), {"length": 4})
    assert end_result.ok, end_result.errors
    # anchor="end", bars=3 in a 4-bar phrase: 4 - 3 = 1.
    assert end_result.micro_velocity[0]["start"] == 1
    assert end_result.micro_velocity[0]["bars"] == 3


def test_preview_reports_exact_and_repeating_sentence_semantics() -> None:
    """The lane needs the tile/exact pair to wrap only a real repeat."""
    exact_payload = _spec_payload("castillo-4-4.json", "castillo_44_pair_odd")
    exact_payload["slots"][0]["microVelocity"] = copy.deepcopy(CONTOUR)
    exact = preview.preview_spec(parse_spec(exact_payload), {"length": 3})
    assert exact.ok, exact.errors
    assert exact.micro_velocity[0]["exact"] is True
    assert exact.micro_velocity[0]["tile"] is None
    assert exact.micro_velocity[0]["cycle"] is False

    repeated_payload = _castillo_payload()
    repeated_payload["slots"][0]["microVelocity"] = copy.deepcopy(CONTOUR)
    repeated = preview.preview_spec(parse_spec(repeated_payload), {"length": 18})
    assert repeated.ok, repeated.errors
    assert repeated.micro_velocity[0]["exact"] is False
    assert repeated.micro_velocity[0]["tile"] == 9
    assert repeated.micro_velocity[0]["bars"] == 9
    assert repeated.micro_velocity[0]["cycle"] is False


def test_preview_reports_cycle_semantics_per_slot() -> None:
    payload = _spec_payload("galop-any.json", "galop_cycle")
    for slot in payload["slots"]:
        slot["microVelocity"] = copy.deepcopy(CONTOUR)

    result = preview.preview_spec(parse_spec(payload), {"run_length": 16})

    assert result.ok, result.errors
    assert [(item["slot"], item["start"], item["bars"]) for item in result.micro_velocity] == [
        (0, 0, 4),
        (1, 4, 4),
    ]
    assert all(item["exact"] is False for item in result.micro_velocity)
    assert all(item["cycle"] is True for item in result.micro_velocity)
    assert all(item["tile"] == 8 for item in result.micro_velocity)


def test_preview_reports_each_slot_origin_for_multiple_slots() -> None:
    payload = _spec_payload("castillo-4-4.json", "castillo_44_pairs_odd")
    for slot in payload["slots"]:
        slot["microVelocity"] = copy.deepcopy(CONTOUR)

    result = preview.preview_spec(parse_spec(payload), {"length": 5})

    assert result.ok, result.errors
    assert [(item["slot"], item["start"], item["bars"]) for item in result.micro_velocity] == [
        (0, 0, 2),
        (1, 3, 2),
    ]
    assert all(item["exact"] is True for item in result.micro_velocity)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_router.router)
    return TestClient(app)


def test_preview_api_adds_micro_velocity_only_when_authored() -> None:
    client = _client()
    plain = client.post(
        "/v1/studio/sentence/preview",
        json={"spec": _castillo_payload(), "fixture": {"bars": 2}},
    )
    assert plain.status_code == 200
    assert "microVelocity" not in plain.json()

    contoured = client.post(
        "/v1/studio/sentence/preview",
        json={"spec": _with_contour(), "fixture": {"bars": 2}},
    )
    assert contoured.status_code == 200
    body = contoured.json()
    assert body["microVelocity"] == [
        {
            "slot": 0,
            "start": 0,
            "bars": 9,
            "tile": 9,
            "exact": False,
            "cycle": False,
            "contour": CONTOUR,
        }
    ]
    assert body["notes"] == plain.json()["notes"]


def test_validate_api_preserves_the_contour_path() -> None:
    client = _client()
    payload = _with_contour()
    payload["slots"][0]["microVelocity"]["notes"][0]["bar"] = 9
    response = client.post("/v1/studio/sentence/validate", json=payload)
    assert response.status_code == 200
    paths = [error["path"] for error in response.json()["errors"]]
    assert "slots[0].microVelocity.notes[0].bar" in paths


def test_parse_error_ignores_a_spec_id_that_looks_like_a_path() -> None:
    from app.routers.studio import _parse_error

    error = _parse_error(
        ValueError(
            "my.spec.song: slots[0].microVelocity.notes[0].bar: outside"
        )
    )
    assert error.path == "slots[0].microVelocity.notes[0].bar"
    assert error.message == "outside"


def test_texture_contour_bounds_only_beats_offline() -> None:
    mapping = _texture_mapping()
    mapping["microVelocity"] = {
        "kind": "offsets",
        "notes": [{"bar": 0, "beat": 4.0, "voice": 1, "offset": -1}],
        "thumb": [],
    }
    errors = validate_texture_spec(parse_texture_spec(mapping))
    assert [error.path for error in errors] == ["microVelocity.notes[0].beat"]

    # `TextureSpec` has no declared bar length, so bar is deliberately
    # unbounded offline: a trailing/rest-only bar must not be rejected here.
    mapping["microVelocity"]["notes"][0] = {
        "bar": 999,
        "beat": 0.0,
        "voice": 1,
        "offset": -1,
    }
    assert validate_texture_spec(parse_texture_spec(mapping)) == ()


def test_texture_spec_helper_defaults_keep_old_mappings() -> None:
    """The optional contour must not change an authored spec that omits it."""
    spec = TextureSpec(
        id="bridge",
        composer="classic",
        kind="pattern",
        level="topic",
        runtime="code",
        status="draft",
        meter_variants=(
            MeterVariant(
                meter=MeterSpec.from_form_meter(METER_44), materializer="grid_4_4"
            ),
        ),
    )
    assert spec.micro_velocity is None
    assert "microVelocity" not in texture_spec_to_mapping(spec)
