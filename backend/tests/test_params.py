"""The params contract: canonical JSON, URL text, and the cache mark."""

from __future__ import annotations

import json

import pytest

from app.sonify.params import (
    DEFAULT_HASH,
    DEFAULT_PARAMS,
    active,
    cache_mark,
    compose_params,
    decode_params,
    encode_params,
    legacy_layer_mark,
    normalize_params,
    normalize_with_warnings,
    params_from_flags,
    params_from_query,
    params_hash,
    params_key,
    schema_payload,
)


def test_default_hash_is_pinned() -> None:
    assert DEFAULT_HASH == "35d9a160e9a3"
    assert params_hash(DEFAULT_PARAMS) == DEFAULT_HASH


def test_hash_rounds_to_the_step_before_hashing() -> None:
    assert params_hash({**DEFAULT_PARAMS, "tempo": 0.9600000000000001}) == params_hash(
        {**DEFAULT_PARAMS, "tempo": 0.96}
    )


def test_missing_keys_take_the_default_and_unknown_keys_warn() -> None:
    params, warnings = normalize_with_warnings({"tempo": 0.96, "nope": 1})
    assert params["tempo"] == 0.96
    assert params["breath"] == 1.0
    assert {warning["code"] for warning in warnings} == {"unknown_key"}


def test_out_of_range_is_clamped_and_warned() -> None:
    params, warnings = normalize_with_warnings({"tempo": 1.4, "humanize": 99})
    assert params["tempo"] == 1.25
    assert params["humanize"] == 1.5
    codes = {(warning["code"], warning["key"]) for warning in warnings}
    assert ("clamped", "tempo") in codes
    assert ("clamped", "humanize") in codes
    assert ("high_humanize", "humanize") in codes


def test_wrong_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_params({"tempo": "fast"})
    with pytest.raises(ValueError):
        normalize_params({"tempo": True})


def test_url_round_trip_and_canonical_text() -> None:
    params = {**DEFAULT_PARAMS, "tempo": 0.96}
    text = encode_params(params)
    assert decode_params(text) == params
    assert params_key(decode_params(text)) == params_key(params)
    assert "=" not in text


def test_default_url_has_no_p() -> None:
    assert params_from_query(None) == DEFAULT_PARAMS
    assert params_from_query(encode_params(DEFAULT_PARAMS)) == DEFAULT_PARAMS


def test_bad_p_is_an_error() -> None:
    import base64

    with pytest.raises(ValueError):
        decode_params("not-base64!")
    assert decode_params("e30") == DEFAULT_PARAMS
    wrong_schema = base64.urlsafe_b64encode(
        json.dumps({"schema": 2, "params": DEFAULT_PARAMS}).encode()
    ).decode()
    with pytest.raises(ValueError):
        decode_params(wrong_schema.rstrip("="))


def test_p_wins_when_present() -> None:
    text = encode_params({**DEFAULT_PARAMS, "tempo": 0.96})
    params = params_from_query(text, humanize=False, color=False)
    assert params["tempo"] == 0.96
    assert params["humanize"] == 1.0
    assert params["color"] == 1.0


def test_legacy_flags_map_to_params() -> None:
    assert params_from_flags(False, True) == {**DEFAULT_PARAMS, "humanize": 0.0, "breath": 0.0}
    assert params_from_flags(True, False) == {**DEFAULT_PARAMS, "color": 0.0}
    assert params_from_flags(False, False) == {
        **DEFAULT_PARAMS,
        "humanize": 0.0,
        "breath": 0.0,
        "color": 0.0,
    }


def test_cache_mark_only_uses_the_old_suffixes_for_the_old_combinations() -> None:
    assert cache_mark(DEFAULT_PARAMS) == ""
    assert cache_mark(params_from_flags(False, True)) == "_nh"
    assert cache_mark(params_from_flags(True, False)) == "_nc"
    assert cache_mark(params_from_flags(False, False)) == "_nh_nc"
    assert cache_mark({**DEFAULT_PARAMS, "humanize": 0.0}) == "_p" + params_hash(
        {**DEFAULT_PARAMS, "humanize": 0.0}
    )
    assert cache_mark({**DEFAULT_PARAMS, "tempo": 0.96}).startswith("_p")
    assert legacy_layer_mark({**DEFAULT_PARAMS, "tempo": 0.96}) == ""


def test_compose_params_scopes_active_values() -> None:
    assert active("tempo") == 1.0
    params = {**DEFAULT_PARAMS, "tempo": 0.9}
    with compose_params(params):
        assert active("tempo") == 0.9
    assert active("tempo") == 1.0


def test_schema_and_default_hash_are_consistent() -> None:
    payload = schema_payload(enabled=True)
    assert payload["schema"] == 1
    assert payload["defaultHash"] == DEFAULT_HASH
    assert payload["enabled"] is True
    by_key = {
        field["key"]: field
        for group in payload["groups"]
        for field in group["fields"]
    }
    assert set(by_key) == set(DEFAULT_PARAMS)
    assert by_key["tempo"]["min"] == 0.75
    assert by_key["tempo"]["max"] == 1.25
    assert by_key["humanize"]["max"] == 1.5
    json.dumps(payload)
