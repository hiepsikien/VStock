"""Shared fixture parsing for the Studio preview pilots."""

from __future__ import annotations

import pytest

from app.studio.preview_fixture import (
    MAX_PLAN_BARS,
    MAX_RENDER_BARS,
    SpecParseError,
    allowed_fixture_keys,
    fixture_bool,
    fixture_int,
    matrix_axes,
)

_DEFAULTS = {
    "lengths": [1, 2],
    "n": [0, 1],
    "closes": [False, True],
    "rise": [0],
}


def test_bounds_are_shared_constants() -> None:
    assert MAX_PLAN_BARS == 64
    assert MAX_RENDER_BARS == 16


def test_fixture_int_returns_a_bounded_integer() -> None:
    assert fixture_int(3, "fixture.n") == 3
    assert fixture_int(1, "fixture.length", minimum=1, maximum=1) == 1


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None])
def test_fixture_int_rejects_non_integers(value: object) -> None:
    with pytest.raises(SpecParseError, match=r"fixture\.n must be an integer"):
        fixture_int(value, "fixture.n")


@pytest.mark.parametrize(
    ("value", "message"),
    [(0, r"fixture\.n must be >= 1"), (5, r"fixture\.n must be <= 4")],
)
def test_fixture_int_rejects_out_of_bounds(value: int, message: str) -> None:
    with pytest.raises(SpecParseError, match=message):
        fixture_int(value, "fixture.n", minimum=1, maximum=4)


def test_fixture_bool_accepts_only_booleans() -> None:
    assert fixture_bool(True, "fixture.closes") is True
    assert fixture_bool(False, "fixture.closes") is False
    for value in (0, 1, "true", None):
        with pytest.raises(
            SpecParseError, match=r"fixture\.closes must be a boolean"
        ):
            fixture_bool(value, "fixture.closes")


def test_spec_parse_error_is_a_value_error() -> None:
    # Callers catch ValueError (villa) or SpecParseError (preview/barrios).
    assert issubclass(SpecParseError, ValueError)


def test_allowed_fixture_keys_accepts_known_keys() -> None:
    allowed_fixture_keys({"length": 3, "n": 0}, {"length", "n"})


def test_allowed_fixture_keys_rejects_unknown_keys_sorted() -> None:
    with pytest.raises(
        SpecParseError,
        match=r"fixture: unknown field\(s\) \['nope', 'run_length'\]",
    ):
        allowed_fixture_keys(
            {"length": 3, "nope": 1, "run_length": 2}, {"length"}
        )


def test_allowed_fixture_keys_uses_the_supplied_path() -> None:
    with pytest.raises(SpecParseError, match=r"candidate: unknown field"):
        allowed_fixture_keys({"nope": 1}, set(), path="candidate")


def test_matrix_axes_uses_defaults_for_missing_axes() -> None:
    axes = matrix_axes(
        None,
        defaults=_DEFAULTS,
        max_rows=4096,
        max_length=8,
    )
    assert axes == {
        "lengths": [1, 2],
        "n": [0, 1],
        "closes": [False, True],
        "rise": [0],
    }
    assert all(isinstance(value, list) for value in axes.values())


def test_matrix_axes_overrides_only_the_supplied_axes() -> None:
    axes = matrix_axes(
        {"lengths": [3, 2, 3], "n": [2]},
        defaults=_DEFAULTS,
        max_rows=4096,
        max_length=8,
    )
    assert axes == {
        "lengths": [2, 3],
        "n": [2],
        "closes": [False, True],
        "rise": [0],
    }


def test_matrix_axes_slices_each_axis_before_converting() -> None:
    # Invalid values past each accepted slice must not be converted.
    axes = matrix_axes(
        {
            "lengths": [1, 2, 3] + [1] * 3 + ["bad"] * 100,
            "n": [0, 1] + [0] * 6 + ["bad"] * 100,
            "closes": [True, False] + ["bad"] * 100,
            "rise": [0, 1] + [0] * 6 + ["bad"] * 100,
        },
        defaults=_DEFAULTS,
        max_rows=4096,
        max_length=3,
    )
    assert axes["lengths"] == [1, 2, 3]
    assert axes["n"] == [0, 1] + [0] * 6
    assert axes["closes"] == [True, False]
    assert axes["rise"] == [0, 1] + [0] * 6


@pytest.mark.parametrize(
    ("matrix", "message"),
    [
        ({"lengths": [0]}, r"fixture\.matrix\.lengths must be >= 1"),
        ({"lengths": [9]}, r"fixture\.matrix\.lengths must be <= 8"),
        ({"lengths": []}, r"fixture\.matrix axes must be non-empty"),
        ({"n": []}, r"fixture\.matrix axes must be non-empty"),
        ({"n": ["one"]}, r"fixture\.matrix\.n must be an integer"),
        ({"closes": [1]}, r"fixture\.matrix\.closes must be a boolean"),
        ({"rise": [-1]}, r"fixture\.matrix\.rise must be >= 0"),
        ({"lengths": 3}, r"fixture\.matrix\.lengths must be a list"),
        ({"n": None}, r"fixture\.matrix\.n must be a list"),
    ],
)
def test_matrix_axes_rejects_bad_axes(matrix: object, message: str) -> None:
    with pytest.raises(SpecParseError, match=message):
        matrix_axes(
            matrix,  # type: ignore[arg-type]
            defaults=_DEFAULTS,
            max_rows=4096,
            max_length=8,
        )


def test_matrix_axes_rejects_a_non_mapping() -> None:
    with pytest.raises(SpecParseError, match=r"fixture\.matrix must be a mapping"):
        matrix_axes(
            [1],
            defaults=_DEFAULTS,
            max_rows=4096,
            max_length=8,
        )  # type: ignore[arg-type]


def test_matrix_axes_respects_the_row_cap() -> None:
    with pytest.raises(SpecParseError, match=r"fixture\.matrix is capped at 4 rows"):
        matrix_axes(
            None,
            defaults={"lengths": [1, 2, 3], "n": [0, 1], "closes": [False], "rise": [0]},
            max_rows=4,
            max_length=8,
        )


def test_matrix_axes_uses_the_callers_length_bound() -> None:
    axes = matrix_axes(
        {"lengths": [3]},
        defaults=_DEFAULTS,
        max_rows=4096,
        max_length=3,
    )
    assert axes["lengths"] == [3]
    with pytest.raises(SpecParseError, match=r"must be <= 3"):
        matrix_axes(
            {"lengths": [4]},
            defaults=_DEFAULTS,
            max_rows=4096,
            max_length=3,
        )


def test_matrix_axes_can_whitelist_lengths() -> None:
    axes = matrix_axes(
        {"lengths": [2, 4]},
        defaults=_DEFAULTS,
        max_rows=4096,
        max_length=8,
        allowed_lengths={2, 4},
    )
    assert axes["lengths"] == [2, 4]

    with pytest.raises(
        SpecParseError, match=r"fixture\.matrix\.lengths 3 is not an allowed length"
    ):
        matrix_axes(
            {"lengths": [2, 3]},
            defaults=_DEFAULTS,
            max_rows=4096,
            max_length=8,
            allowed_lengths={2, 4},
        )
