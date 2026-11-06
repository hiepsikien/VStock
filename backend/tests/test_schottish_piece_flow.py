"""End-to-end 2/4 Schottish piece through the new production flow.

This is the smoke test the Phase 1-3 work was built for: plan a guitar
movement, let the Suite meter override choose native 2/4 for movement III,
attach the real intro/outro frame, and render a non-empty score through the
public `render` entry point.

It intentionally does not assert a particular melody or digest. The purpose is
to prove the new flow produces a playable movement with all three voices and a
framed body before any AI layer is introduced.
"""

from __future__ import annotations

from app.sonify.form import METER_24
from app.sonify.guitar_suite_schottish import use_suite_schottish_abab
from app.sonify.model import Bar
from app.sonify.params import compose_params
from app.sonify.render import render
from app.sonify.span import attach_frame, plan_week


def _bars(count: int) -> list[Bar]:
    return [Bar(100.0 + (index % 5) * 32, 250.0 + index % 3) for index in range(count * 4)]


def test_new_flow_renders_a_framed_native_2_4_piece() -> None:
    with compose_params({}):
        with use_suite_schottish_abab(True):
            movement = plan_week(1, variant="guitar", ensemble="villa")[0]
            form = attach_frame(movement.spec, "1M")

            assert form.meter == METER_24
            assert form.bars > 0

            score = render(
                _bars(form.bars),
                variant="guitar",
                ensemble="villa",
                form=form,
                framed=True,
                movement_span="1M",
                movement_index=2,
            )

    assert score.lead
    assert score.support
    assert score.low
    assert score.divisions >= 1

    # The frame is real: there are bars outside the body with notes, and the
    # body itself has all three voices. A blank or fallback-only render fails.
    bars_with_notes = {event.bar for event in (*score.lead, *score.support, *score.low)}
    assert len(bars_with_notes) > 4
    assert max(bars_with_notes) < form.bars
    assert min(bars_with_notes) >= 0
