"""Galop migration: run-cycle plan, boundary resets, variant bit, integration.

Galop is the first run-based archetype: its cycle index counts bars inside a
maximal galop run, so `plan_run` takes a run length instead of a phrase length.
The pre-registry chooser stays as `_galop_cell_legacy` and is the parity oracle.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from types import SimpleNamespace

import app.sonify.guitar_sor as sor
from app.sonify.chords import C
from app.sonify.form import METER_44, ChordSlot, FormSection, compose_meter
from app.sonify.guitar import render_guitar_score
from app.sonify.model import Phrase, Run
from app.sonify.sentence_specs import plan_run, plan_sentence

FRAME = 2
EPB = 8


def _held(start: int, eighths: int, midi: int) -> Phrase:
    return Phrase(start, start + eighths, (Run(start, eighths, midi),), False)


def _joined(start: int, pitches: list[int]) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs), False)


def _galop_score(body: int, body_pitches: list[int] | None = None):
    """Intro/outro frames around a single galop body phrase of `body` bars."""
    total = FRAME + body + FRAME
    body_pitches = body_pitches or [67] * (body * EPB)
    assert len(body_pitches) == body * EPB
    phrases = (
        _held(0, FRAME * EPB, 67),
        _joined(FRAME * EPB, body_pitches),
        _held((FRAME + body) * EPB, FRAME * EPB, 67),
    )
    pitches = (
        [67] * (FRAME * EPB)
        + list(body_pitches)
        + [67] * (FRAME * EPB)
    )
    kinds = {
        bar: (
            "intro" if bar < FRAME else "outro" if bar >= FRAME + body else "phrase"
        )
        for bar in range(total)
    }
    sections = (
        FormSection(0, FRAME, "intro", 0),
        FormSection(FRAME, FRAME + body, "phrase", 0),
        FormSection(FRAME + body, total, "outro", 0),
    )
    slots = tuple(
        ChordSlot(bar, 1, C, "sideway", kinds[bar]) for bar in range(total)
    )
    with compose_meter(METER_44):
        return render_guitar_score(
            title="Guitar",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=pitches,
            phrases=phrases,
            dynamics=(),
            bands=["mf"] * total,
            band_at={bar: "mf" for bar in range(total)},
            musical_bars=total,
            total_eighths=total * EPB,
            bpm=88,
            ensemble="classic",
            harmonies=(),
            mode="major",
            character="rally",
            sections=sections,
        )


def _run_ctx(bars: int, kinds: dict[int, str] | None = None) -> SimpleNamespace:
    kinds = kinds or {}
    ctx = SimpleNamespace(kind="4/4", bars=bars)
    ctx.kind_at = {bar: kinds.get(bar, "phrase") for bar in range(bars)}
    ctx._pattern_source = None
    ctx._pattern_signature = None
    ctx._pattern_cache = {}
    ctx.epb = EPB
    ctx.phrases = [
        SimpleNamespace(start=bar * EPB, end=(bar + 1) * EPB) for bar in range(bars)
    ]
    return ctx


def _legacy_cells(run_length: int) -> list[str]:
    return [sor._galop_cell_legacy(index) for index in range(run_length)]


def test_galop_plan_matches_legacy_cells_for_every_run_length() -> None:
    for meter in ("3/4", "4/4", "6/8"):
        for run_length in range(1, 31):
            assert plan_run("galop", meter, run_length) == _legacy_cells(
                run_length
            ), (meter, run_length)


def test_plan_run_contract() -> None:
    assert plan_run("galop", "4/4", 0) == []
    assert plan_run("galop", "4/4", 1) == ["galop1"]
    # A pair with no entry stays on the code path, like `plan_sentence`.
    assert plan_run("unit_absent", "4/4", 8) is None
    # A phrase family has no run plan.
    assert plan_run("castillo", "3/4", 9) == []


def test_galop_cells_are_not_figure_spans() -> None:
    # Registered for the pair, but `plan_sentence` only emits figures.
    for length in range(1, 13):
        assert plan_sentence("galop", "4/4", length, 0) == []


def test_a_study_bar_resets_the_run() -> None:
    bars = 12
    patterns = ["galop"] * bars
    patterns[5] = "study"
    ctx = _run_ctx(bars)

    assert sor._galop_run_length(ctx, 0, patterns) == 5
    first = [sor._galop_run_cell(ctx, bar, patterns) for bar in range(5)]
    assert first == [(index, _legacy_cells(5)[index]) for index in range(5)]
    # The study bar is not a galop bar; the next run restarts at cell 1 / index 0.
    assert sor._galop_run_length(ctx, 6, patterns) == 6
    second = [sor._galop_run_cell(ctx, bar, patterns) for bar in range(6, 12)]
    assert second == [(index, _legacy_cells(6)[index]) for index in range(6)]


def test_a_pedal_bar_resets_the_run() -> None:
    bars = 10
    patterns = ["galop"] * bars
    # A door region (`_PEDAL`) is what the run index treats as a break.
    ctx = _run_ctx(bars, {4: "warmup"})

    assert sor._galop_run_length(ctx, 0, patterns) == 4
    assert sor._galop_run_length(ctx, 5, patterns) == 5
    second = [sor._galop_run_cell(ctx, bar, patterns) for bar in range(5, 10)]
    assert second == [(index, _legacy_cells(5)[index]) for index in range(5)]


def test_every_run_length_renders_the_planned_cell(monkeypatch) -> None:
    seen: list[tuple[int, str]] = []
    original = sor._galop_run_cell

    def record(ctx, bar, patterns):
        index, cell = original(ctx, bar, patterns)
        seen.append((index, cell))
        return index, cell

    monkeypatch.setattr(sor, "_galop_run_cell", record)
    for run_length in range(1, 31):
        seen.clear()
        _galop_score(run_length)
        assert seen == list(enumerate(plan_run("galop", "4/4", run_length))), run_length


def test_the_variant_bit_lives_on_the_first_bar_of_a_run_only() -> None:
    # Long enough that bar 10 is not the run's last (boundary) bar.
    body = 13
    # Only the first bar's second half differs, so rhythm alone cannot fake it.
    first = [67, 67, 67, 67, 67, 67, 72, 74]
    score = _galop_score(body, first + [67] * ((body - 1) * EPB))

    def at(bar: int) -> list:
        return [note for note in score.lead if note.bar == bar and note.midi is not None]

    start = at(FRAME)
    second = next(note for note in start if abs(note.beat - 3.0) < 1e-9)
    third = next(note for note in start if abs(note.beat - 3.5) < 1e-9)
    assert second.staccato and second.midi == 72
    assert not third.staccato and third.midi == 74

    # One cycle later the cell is cell 1 again, but this is not the run's first
    # bar, so the variant must stay off.
    later = at(FRAME + 8)
    later_second = next(note for note in later if abs(note.beat - 3.0) < 1e-9)
    later_third = next(note for note in later if abs(note.beat - 3.5) < 1e-9)
    assert later_second.staccato and later_second.midi == 67
    assert later_third.midi != 74


def test_galop_renders_without_the_legacy_cell_chooser(monkeypatch) -> None:
    seen: list[tuple[int, str]] = []
    original = sor._galop_run_cell

    def record(ctx, bar, patterns):
        index, cell = original(ctx, bar, patterns)
        seen.append((index, cell))
        return index, cell

    def boom(*_args, **_kwargs):
        raise AssertionError("galop used the legacy cell chooser")

    monkeypatch.setattr(sor, "_galop_run_cell", record)
    monkeypatch.setattr(sor, "_galop_cell_legacy", boom)

    score = _galop_score(9)
    assert seen == list(enumerate(plan_run("galop", "4/4", 9)))
    assert any(note.midi is not None for note in score.lead if note.bar == FRAME)


def test_plan_run_loads_the_owner_module() -> None:
    """A caller that imports only sentence_specs still plans the galop run."""
    backend = pathlib.Path(__file__).resolve().parents[1]
    code = (
        "from app.sonify.sentence_specs import plan_run;"
        "print(plan_run('galop', '4/4', 9))"
    )
    env = {**os.environ, "PYTHONPATH": str(backend)}
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == repr(_legacy_cells(9))
