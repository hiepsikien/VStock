"""`bar_plan_cells` coverage: a cell owns a bar just like a figure."""

from __future__ import annotations

import pytest

from app.sonify.sentence_production import bar_plan, bar_plan_cells
from app.sonify.sentence_specs import PlannedSlot


def _slot(
    *,
    start: int,
    bars: tuple[int, ...],
    figure: int | None = None,
    cell: str | None = None,
    micro_velocity=None,
) -> PlannedSlot:
    return PlannedSlot(
        slot_index=0,
        slot_start=start,
        bars=bars,
        figure=figure,
        cell=cell,
        micro_velocity=micro_velocity,
    )


def test_cells_count_as_coverage() -> None:
    planned = [
        _slot(start=0, bars=(0, 1), figure=1),
        _slot(start=2, bars=(2, 3), cell="key_a"),
    ]
    figures, cells, contours = bar_plan_cells(planned, 4)  # type: ignore[misc]
    assert figures == {0: 1, 1: 1}
    assert cells == {2: "key_a", 3: "key_a"}
    assert contours == {}


def test_figure_only_bar_plan_ignores_cells() -> None:
    planned = [
        _slot(start=0, bars=(0, 1), figure=1),
        _slot(start=2, bars=(2, 3), cell="key_a"),
    ]
    # The historical helper keeps its figure-only contract and cannot cover
    # the movement once a cell takes two bars.
    assert bar_plan(planned, 4) is None
    assert bar_plan(planned, 2) == ({0: 1, 1: 1}, {})


def test_require_full_counts_the_union_of_figures_and_cells() -> None:
    planned = [_slot(start=0, bars=(0, 1), cell="key_a")]
    assert bar_plan_cells(planned, 4) is None
    partial = bar_plan_cells(planned, 4, require_full=False)
    assert partial is not None
    figures, cells, _contours = partial
    assert figures == {}
    assert cells == {0: "key_a", 1: "key_a"}


def test_empty_plan_falls_back() -> None:
    assert bar_plan_cells(None, 4) is None
    assert bar_plan_cells([], 4) is None


def test_out_of_range_bars_are_ignored() -> None:
    planned = [_slot(start=2, bars=(2, 3, 4), cell="key_a")]
    found = bar_plan_cells(planned, 4, require_full=False)
    assert found is not None
    _figures, cells, _contours = found
    assert cells == {2: "key_a", 3: "key_a"}


def test_slot_contours_survive_a_cell_plan() -> None:
    from app.studio.micro_velocity import parse_micro_velocity

    contour = parse_micro_velocity(
        {
            "kind": "offsets",
            "notes": [
                {"bar": 0, "beat": 0.0, "voice": 1, "offset": 4},
            ],
            "thumb": [],
        }
    )
    planned = [_slot(start=0, bars=(0,), cell="key_a", micro_velocity=contour)]
    found = bar_plan_cells(planned, 1)
    assert found is not None
    _figures, _cells, contours = found
    assert contours == {0: contour}


def test_both_realizers_cannot_own_the_same_bar() -> None:
    # A hand-built overlap keeps the cell rule after the figure rule only if
    # both are present; the planner never produces this, so the helper must
    # not crash and should keep the figure as the authoritative realizer.
    planned = [
        _slot(start=0, bars=(0,), figure=1),
        _slot(start=0, bars=(0,), cell="key_a"),
    ]
    found = bar_plan_cells(planned, 1)
    assert found is not None
    figures, cells, _contours = found
    assert figures == {0: 1}
    assert cells == {0: "key_a"}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
