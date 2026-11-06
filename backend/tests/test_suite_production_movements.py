"""Feature-gated production paths for the remaining Suite movements.

Valsa-Choro, Gavotta-Choro, Schottish-Choro, and Choros No. 1 follow the
Mazurka pattern: a default-off flag, a lazy `SentenceSpec` registration under a
new production pattern id, the existing Villa figures, and the shared gated
tail. Off must leave the historical render and registry untouched; on must
select and render the candidate tile and clean up afterward.

The Schottish and Choros rows carry their audit caveats: both use the 4/4
engine as a stand-in, and Choros No. 1 is provisional. Gavotta keeps the bar-0
warning. No 2/4 `Meter` or new figure is invented here.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest

import app.sonify.guitar_frame as guitar_frame
import app.sonify.guitar_patterns as patterns
import app.sonify.guitar_suite_choros1 as suite_choros1
import app.sonify.guitar_suite_gate as suite_gate
import app.sonify.guitar_suite_gavotta as suite_gavotta
import app.sonify.guitar_suite_schottish as suite_schottish
import app.sonify.guitar_suite_valsa as suite_valsa
from app.sonify import production_flags as flags
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_24, METER_34, METER_44, FormSection, FormSpec
from app.sonify.form import compose_meter
from app.sonify.guitar import _PEDAL
from app.sonify.guitar_villa_figures import (
    VILLA_ARPEGGIO,
    VILLA_CADENCE,
    VILLA_CHORD_MELODY,
    VILLA_FIGURES,
    render_villa_figure,
)
from app.sonify.guitar_wave import PROFILES
from app.sonify.model import Bar, Phrase, Run
from app.sonify.params import compose_params
from app.sonify.sentence_plan import AutoAABA, PhraseView, build_plan
from app.sonify.span import (
    attach_frame,
    plan_month,
    plan_quarter,
    plan_week,
    week_spec,
)
from app.sonify.pattern_registry import PATTERN_META, PatternMeta, meta
from app.sonify.program import pattern_title
from app.sonify.render import render
from app.sonify.sentence_specs import SentenceSpec
from app.studio.candidates.suite_choros1 import (
    METER_CAVEAT as CHOROS1_CAVEAT,
    suite_choros1_spec,
)
from app.studio.candidates.suite_gavotta import (
    BAR_ZERO_CAVEAT,
    suite_gavotta_spec,
)
from app.studio.candidates.suite_schottish import (
    METER_CAVEAT as SCHOTTISH_CAVEAT,
    suite_schottish_spec,
)
from app.studio.candidates.suite_valsa import suite_valsa_spec


@dataclass(frozen=True)
class Case:
    module: Any
    spec: SentenceSpec
    key: tuple[str, str]
    context: Callable[..., AbstractContextManager[None]]
    candidate: Callable[[], SentenceSpec]
    candidate_caveat: str | None
    caveat: str
    meta: PatternMeta
    pattern: str
    meter: Any
    meter_label: str
    bars: int
    min_bars: int
    figures: tuple[int, ...]
    title: str
    env: str
    movement_span: str | None = None
    movement_index: int | None = None
    specs: tuple[SentenceSpec, ...] | None = None


VALSA_FIGURES = (
    VILLA_ARPEGGIO,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
    VILLA_ARPEGGIO,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_CHORD_MELODY,
)
GAVOTTA_FIGURES = (
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
)
SCHOTTISH_FIGURES = (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
)
SCHOTTISH_B_FIGURES = (
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
)
SCHOTTISH_CLOSE_FIGURES = (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
    VILLA_CADENCE,
)
CHOROS1_FIGURES = (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
)

CASES = (
    Case(
        module=suite_valsa,
        spec=suite_valsa.SUITE_VALSA_PERIOD,
        key=suite_valsa.SUITE_VALSA_KEY,
        context=suite_valsa.use_suite_valsa_period,
        candidate=suite_valsa_spec,
        candidate_caveat=None,
        caveat=suite_valsa.SUITE_VALSA_CAVEAT,
        meta=suite_valsa.SUITE_VALSA_META,
        pattern=suite_valsa.SUITE_VALSA_PATTERN,
        meter=METER_34,
        meter_label=suite_valsa.SUITE_VALSA_METER,
        bars=8,
        min_bars=suite_valsa.SUITE_VALSA_MIN_BARS,
        figures=VALSA_FIGURES,
        title=suite_valsa.SUITE_VALSA_TITLE,
        env=flags.SUITE_VALSA_ENV,
    ),
    Case(
        module=suite_gavotta,
        spec=suite_gavotta.SUITE_GAVOTTA_BAAB,
        key=suite_gavotta.SUITE_GAVOTTA_KEY,
        context=suite_gavotta.use_suite_gavotta_baab,
        candidate=suite_gavotta_spec,
        candidate_caveat=BAR_ZERO_CAVEAT,
        caveat=suite_gavotta.SUITE_GAVOTTA_CAVEAT,
        meta=suite_gavotta.SUITE_GAVOTTA_META,
        pattern=suite_gavotta.SUITE_GAVOTTA_PATTERN,
        meter=METER_44,
        meter_label=suite_gavotta.SUITE_GAVOTTA_METER,
        bars=8,
        min_bars=suite_gavotta.SUITE_GAVOTTA_MIN_BARS,
        figures=GAVOTTA_FIGURES,
        title=suite_gavotta.SUITE_GAVOTTA_TITLE,
        env=flags.SUITE_GAVOTTA_ENV,
    ),
    Case(
        module=suite_schottish,
        spec=suite_schottish.SUITE_SCHOTTISH_ABAB,
        key=suite_schottish.SUITE_SCHOTTISH_KEY,
        context=suite_schottish.use_suite_schottish_abab,
        candidate=suite_schottish_spec,
        candidate_caveat=SCHOTTISH_CAVEAT,
        caveat=suite_schottish.SUITE_SCHOTTISH_CAVEAT,
        meta=suite_schottish.SUITE_SCHOTTISH_META,
        pattern=suite_schottish.SUITE_SCHOTTISH_PATTERN,
        meter=METER_44,
        meter_label=suite_schottish.SUITE_SCHOTTISH_METER,
        bars=8,
        min_bars=suite_schottish.SUITE_SCHOTTISH_MIN_BARS,
        figures=SCHOTTISH_FIGURES,
        title=suite_schottish.SUITE_SCHOTTISH_TITLE,
        env=flags.SUITE_SCHOTTISH_ENV,
        movement_span="1M",
        movement_index=2,
        specs=suite_schottish.GATE_44.specs,
    ),
    Case(
        module=suite_choros1,
        spec=suite_choros1.SUITE_CHOROS1_ABBA,
        key=suite_choros1.SUITE_CHOROS1_KEY,
        context=suite_choros1.use_suite_choros1_abba,
        candidate=suite_choros1_spec,
        candidate_caveat=CHOROS1_CAVEAT,
        caveat=suite_choros1.SUITE_CHOROS1_CAVEAT,
        meta=suite_choros1.SUITE_CHOROS1_META,
        pattern=suite_choros1.SUITE_CHOROS1_PATTERN,
        meter=METER_44,
        meter_label=suite_choros1.SUITE_CHOROS1_METER,
        bars=8,
        min_bars=suite_choros1.SUITE_CHOROS1_MIN_BARS,
        figures=CHOROS1_FIGURES,
        title=suite_choros1.SUITE_CHOROS1_TITLE,
        env=flags.SUITE_CHOROS1_ENV,
    ),
)
CASE_IDS = ("valsa", "gavotta", "schottish", "choros1")
CASES_WITH_IDS = tuple(
    pytest.param(case, id=case_id)
    for case, case_id in zip(CASES, CASE_IDS, strict=True)
)


@pytest.fixture(autouse=True)
def _registry_does_not_leak():
    before = dict(specs.SENTENCE_SPECS)
    yield
    assert dict(specs.SENTENCE_SPECS) == before


def _bars(count: int) -> list[Bar]:
    return [Bar(100.0 + (index % 4) * 40, 250.0) for index in range(count * 4)]


def _form(bars: int, meter) -> FormSpec:
    return FormSpec(
        bars,
        120,
        (FormSection(0, bars, "phrase", 0),),
        meter=meter,
    )


def _scope(case: Case) -> dict:
    """The movement scope a case needs; non-scoped movements get nothing."""
    if case.movement_span is None:
        return {}
    return {
        "movement_span": case.movement_span,
        "movement_index": case.movement_index,
    }


def _render_case(case: Case):
    """Render one case with the movement scope it needs."""
    return _render(
        "villa", case.meter, case.bars, **_scope(case)
    )


def _render(
    ensemble: str,
    meter,
    bars: int,
    *,
    movement_span: str | None = None,
    movement_index: int | None = None,
):
    with compose_params({}):
        return render(
            _bars(bars),
            variant="guitar",
            ensemble=ensemble,
            form=_form(bars, meter),
            framed=True,
            movement_span=movement_span,
            movement_index=movement_index,
        )


def _render_form(
    form: FormSpec,
    *,
    movement_span: str | None = None,
    movement_index: int | None = None,
):
    with compose_params({}):
        return render(
            _bars(form.bars),
            variant="guitar",
            ensemble="villa",
            form=form,
            framed=True,
            movement_span=movement_span,
            movement_index=movement_index,
        )


def _body_bars(form: FormSpec) -> set[int]:
    return {
        bar
        for section in form.sections
        for bar in range(section.start, section.end)
        if section.kind not in _PEDAL
    }


def _digest(score) -> str:
    payload = [
        (
            event.voice,
            event.bar,
            round(event.beat, 6),
            round(event.duration_beats, 6),
            event.midi,
            event.velocity,
            event.tie_start,
            event.tie_stop,
        )
        for voice in (score.lead, score.comp, score.bass)
        for event in voice
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _spy_figure(monkeypatch, module) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []
    original = module.render_villa_figure

    def spy(ctx, bar, phrase, figure):
        calls.append((bar, figure))
        return original(ctx, bar, phrase, figure)

    monkeypatch.setattr(module, "render_villa_figure", spy)
    return calls


def _patterns_context(
    meter_label: str,
    bars: int,
    *,
    movement_span: str | None = None,
    movement_index: int | None = None,
):
    from tests.guitar_fixture import meter_named, pattern_case

    section = FormSection(0, bars, "phrase", 0)
    return pattern_case(
        "probe",
        meter_named(meter_label),
        ensemble="villa",
        mood="calm",
        band="mf",
        bpm=96,
        bars=bars,
        first_body=True,
        previous=[],
        section=section,
        movement_span=movement_span,
        movement_index=movement_index,
    )[0]


# ---------------------------------------------------------------------------
# authored source and taxonomy


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_production_spec_matches_the_authored_candidate(case: Case) -> None:
    authored = case.candidate()
    assert authored.pattern == "villa_pattern"
    assert case.spec == dataclasses.replace(authored, pattern=case.pattern)
    assert case.spec.select.length_min == case.min_bars
    assert tuple(slot.figure for slot in case.spec.slots) == case.figures


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_taxonomy_and_title_are_consistent(case: Case) -> None:
    found = PATTERN_META[case.pattern]
    assert found == case.meta
    assert found == meta(case.pattern)
    assert found.id == case.pattern
    assert found.level == "topic"
    assert found.name_source in {"dance", "genre"}
    assert pattern_title(case.pattern, "villa") == case.title


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_profile_and_door_are_shared_with_the_villa_roll(case: Case) -> None:
    assert PROFILES[("villa", case.pattern)] == PROFILES[("villa", "villa_pattern")]
    assert (
        guitar_frame._RETAINED_DOORS[("villa", case.pattern)]
        is guitar_frame._villa_pattern_door
    )


# ---------------------------------------------------------------------------
# off parity and fallback


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_off_is_the_historical_render(monkeypatch, case: Case) -> None:
    monkeypatch.delenv(case.env, raising=False)
    off = _digest(_render_case(case))
    calls = _spy_figure(monkeypatch, case.module)
    on = _render_case(case)
    assert calls == []
    assert _digest(on) == off
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_falls_back_below_min_bars(monkeypatch, case: Case) -> None:
    short = case.min_bars - 1
    off = _digest(
        _render("villa", case.meter, short, **_scope(case))
    )
    calls = _spy_figure(monkeypatch, case.module)
    with case.context(True):
        on = _render("villa", case.meter, short, **_scope(case))
    assert calls == []
    assert _digest(on) == off
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_falls_back_in_the_other_meter(monkeypatch, case: Case) -> None:
    other = METER_44 if case.meter is METER_34 else METER_34
    off = _digest(_render("villa", other, case.bars, **_scope(case)))
    calls = _spy_figure(monkeypatch, case.module)
    with case.context(True):
        on = _render("villa", other, case.bars, **_scope(case))
    assert calls == []
    assert _digest(on) == off
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_falls_back_with_a_pedal_frame(monkeypatch, case: Case) -> None:
    framed = FormSpec(
        case.bars,
        120,
        (
            FormSection(0, 1, "intro", 0),
            FormSection(1, case.bars, "phrase", 0),
        ),
        meter=case.meter,
    )
    with compose_params({}):
        off = render(
            _bars(case.bars),
            variant="guitar",
            ensemble="villa",
            form=framed,
            framed=True,
            **_scope(case),
        )
    calls = _spy_figure(monkeypatch, case.module)
    with case.context(True):
        with compose_params({}):
            on = render(
                _bars(case.bars),
                variant="guitar",
                ensemble="villa",
                form=framed,
                framed=True,
                **_scope(case),
            )
    if case.module is suite_schottish:
        # Schottish opts into the body/door seam: a pedal frame is allowed, so
        # the body renders and the movement does not fall back wholesale.
        assert calls
        assert {bar for bar, _figure in calls} == set(range(1, case.bars))
        assert _digest(on) != _digest(off)
    else:
        assert calls == []
        assert _digest(on) == _digest(off)
    assert case.key not in specs.SENTENCE_SPECS


def test_schottish_partial_merge_on_a_real_framed_week(monkeypatch) -> None:
    """A real week + frame selects Schottish and renders only its body bars."""
    form = attach_frame(week_spec(1), "1M")
    body = _body_bars(form)
    assert body and len(body) >= suite_schottish.SUITE_SCHOTTISH_MIN_BARS

    monkeypatch.delenv(flags.SUITE_SCHOTTISH_ENV, raising=False)
    off = _digest(_render_form(form, movement_span="1M", movement_index=2))
    calls = _spy_figure(monkeypatch, suite_schottish)
    with suite_schottish.use_suite_schottish_abab(True):
        on = _render_form(form, movement_span="1M", movement_index=2)
        assert calls
        assert {bar for bar, _figure in calls} == body
        assert _digest(on) != off
    assert suite_schottish.SUITE_SCHOTTISH_KEY not in specs.SENTENCE_SPECS
    assert (
        _digest(_render_form(form, movement_span="1M", movement_index=2))
        == off
    )


def test_schottish_flag_off_is_identical_on_a_real_frame(monkeypatch) -> None:
    form = attach_frame(week_spec(1), "1M")
    monkeypatch.delenv(flags.SUITE_SCHOTTISH_ENV, raising=False)
    calls = _spy_figure(monkeypatch, suite_schottish)
    assert _digest(_render_form(form)) == _digest(_render_form(form))
    assert calls == []
    assert suite_schottish.SUITE_SCHOTTISH_KEY not in specs.SENTENCE_SPECS


def test_schottish_selection_differs_between_flag_off_and_on() -> None:
    form = attach_frame(week_spec(1), "1M")
    from tests.guitar_fixture import meter_named, pattern_case

    def patterns_for(enabled: bool) -> list[str]:
        with compose_params({}):
            with suite_schottish.use_suite_schottish_abab(enabled):
                ctx, _phrases = pattern_case(
                    "probe",
                    meter_named("4/4"),
                    ensemble="villa",
                    mood="calm",
                    band="mf",
                    bpm=96,
                    bars=form.bars,
                    first_body=True,
                    previous=[],
                    sections=list(form.sections),
                    movement_span="1M",
                    movement_index=2,
                )
                return patterns._patterns(ctx)

    assert "suite_schottish" not in patterns_for(False)
    assert "suite_schottish" in patterns_for(True)


# ---------------------------------------------------------------------------
# on: registration, selection, render


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_registers_selects_and_renders_the_tile(monkeypatch, case: Case) -> None:
    off = _digest(_render_case(case))
    calls = _spy_figure(monkeypatch, case.module)

    with case.context(True):
        expected = case.specs or (case.spec,)
        assert specs.SENTENCE_SPECS.get(case.key) == expected
        tiled = (case.figures * (case.bars // len(case.figures) + 1))[: case.bars]
        assert specs.plan_sentence(
            case.pattern, case.meter_label, case.bars, 0
        ) == [(figure, (bar,)) for bar, figure in enumerate(tiled)]

        on = _render_case(case)

        if case.specs:
            # A multi-spec gate plans A/B/close; the final body bar is the
            # cadence figure, not the historical ABAB repeat.
            assert [bar for bar, _figure in calls] == list(range(case.bars))
            assert calls[-1][1] == VILLA_CADENCE
        else:
            assert calls == list(enumerate(tiled))
        assert on.divisions == 2
        assert {event.bar for event in on.lead} == set(range(case.bars))
        assert _digest(on) != off

    assert case.key not in specs.SENTENCE_SPECS
    assert specs.plan_sentence(case.pattern, case.meter_label, case.bars, 0) is None
    assert _digest(_render_case(case)) == off


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_selection_is_the_same_predicate_as_render(case: Case) -> None:
    with compose_params({}):
        with case.context(True):
            ctx = _patterns_context(case.meter_label, case.bars, **_scope(case))
            assert patterns._patterns(ctx) == [case.pattern]

            short = _patterns_context(
                case.meter_label, case.min_bars - 1, **_scope(case)
            )
            assert case.pattern not in patterns._patterns(short)

            other_label = "4/4" if case.meter is METER_34 else "3/4"
            other_ctx = _patterns_context(other_label, case.bars, **_scope(case))
            assert case.pattern not in patterns._patterns(other_ctx)


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_env_auditions_without_the_context(monkeypatch, case: Case) -> None:
    monkeypatch.setenv(case.env, "on")
    calls = _spy_figure(monkeypatch, case.module)
    try:
        score = _render_case(case)
        assert len(calls) == case.bars
        assert case.key in specs.SENTENCE_SPECS
        assert score.divisions == 2
    finally:
        case.module.unregister()
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_ensure_registered_refuses_to_replace_a_different_spec(case: Case) -> None:
    other = dataclasses.replace(case.spec, id="future_archetype")
    specs.SENTENCE_SPECS[case.key] = (other,)
    try:
        with pytest.raises(ValueError, match="would replace it"):
            case.module.ensure_registered()
    finally:
        del specs.SENTENCE_SPECS[case.key]
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_context_cleans_up_after_an_exception(case: Case) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        with case.context(True):
            assert case.key in specs.SENTENCE_SPECS
            raise RuntimeError("boom")
    assert case.key not in specs.SENTENCE_SPECS


# ---------------------------------------------------------------------------
# caveats and precedence


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_caveat_is_carried_from_the_audit(case: Case) -> None:
    if case.candidate_caveat is not None:
        assert case.caveat == case.candidate_caveat
    else:
        # Valsa is the exact 3/4 case: the caveat is about phrase evidence,
        # not a meter fold.
        assert "3/4" in case.caveat
        assert "fold" in case.caveat


def test_four_shared_meter_gates_use_the_documented_precedence() -> None:
    """Valsa -> Gavotta -> Schottish -> Choros; first eligible wins."""
    from app.sonify.guitar_suite_movements import selectable_pattern

    with compose_params({}):
        with (
            suite_gavotta.use_suite_gavotta_baab(True),
            suite_schottish.use_suite_schottish_abab(True),
        ):
            ctx = _patterns_context("4/4", 8)
            assert patterns._patterns(ctx) == ["suite_gavotta"]
            assert selectable_pattern(ctx) == "suite_gavotta"

        with suite_valsa.use_suite_valsa_period(True):
            ctx = _patterns_context("3/4", 8)
            assert patterns._patterns(ctx) == ["suite_valsa"]
    assert suite_gavotta.SUITE_GAVOTTA_KEY not in specs.SENTENCE_SPECS
    assert suite_schottish.SUITE_SCHOTTISH_KEY not in specs.SENTENCE_SPECS
    assert suite_valsa.SUITE_VALSA_KEY not in specs.SENTENCE_SPECS


def test_choros1_claims_a_genre_not_a_dance() -> None:
    assert PATTERN_META["suite_choros1"].name_source == "genre"
    assert pattern_title("suite_choros1", "villa") == "Choros No. 1"


def test_importing_the_movement_modules_registers_no_suite_sentence() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "from app.sonify import sentence_specs as specs\n"
        "import app.sonify.guitar_suite_movements\n"
        "import app.sonify.guitar_suite_valsa\n"
        "import app.sonify.guitar_suite_gavotta\n"
        "import app.sonify.guitar_suite_schottish\n"
        "import app.sonify.guitar_suite_choros1\n"
        "suite = sorted(key for key in specs.SENTENCE_SPECS "
        "if key[0].startswith('suite_'))\n"
        "print(suite)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "[]"


# ---------------------------------------------------------------------------
# Phase 3: native 2/4 for the Schottish scope


def test_schottish_gates_share_the_scope_and_expose_both_meters() -> None:
    assert suite_schottish.SCHOTTISH_SCOPES == frozenset(
        {("1W", 0), ("1M", 2), ("3M", 2)}
    )
    assert suite_schottish.GATES == (
        suite_schottish.GATE_44,
        suite_schottish.GATE_24,
    )
    assert {gate.key for gate in suite_schottish.GATES} == {
        suite_schottish.SUITE_SCHOTTISH_KEY,
        suite_schottish.SUITE_SCHOTTISH_KEY_24,
    }
    assert all(
        gate.movement_scopes == suite_schottish.SCHOTTISH_SCOPES
        and gate.partial
        for gate in suite_schottish.GATES
    )


def test_direct_context_without_scope_never_selects_schottish() -> None:
    with compose_params({}):
        with suite_schottish.use_suite_schottish_abab(True):
            bare = _patterns_context("4/4", 8)
            assert not suite_schottish.eligible(bare)
            assert not suite_schottish.selectable(bare)
            assert "suite_schottish" not in patterns._patterns(bare)

            # One half of the pair is not enough.
            assert not suite_schottish.selectable(
                dataclasses.replace(bare, movement_span="1M")
            )
            assert not suite_schottish.selectable(
                dataclasses.replace(bare, movement_index=2)
            )

            scoped = dataclasses.replace(
                bare, movement_span="1M", movement_index=2
            )
            assert suite_schottish.selectable(scoped)
            assert patterns._patterns(scoped) == ["suite_schottish"]


def test_year_movement_three_does_not_select_schottish() -> None:
    with compose_params({}):
        with suite_schottish.use_suite_schottish_abab(True):
            ctx = _patterns_context(
                "4/4", 8, movement_span="1Y", movement_index=2
            )
            assert not suite_schottish.eligible(ctx)
            assert not suite_schottish.selectable(ctx)
            assert "suite_schottish" not in patterns._patterns(ctx)


def test_month_and_quarter_movement_three_use_native_2_4(monkeypatch) -> None:
    with compose_params({}):
        with suite_schottish.use_suite_schottish_abab(True):
            plans = {
                "1M": plan_month([8, 8, 8, 8], "guitar", "villa")[2],
                "3M": plan_quarter([8, 8, 8], "guitar", "villa")[2],
            }
            for span, movement in plans.items():
                assert movement.spec.meter is METER_24
                ctx = _patterns_context(
                    "2/4", 8, movement_span=span, movement_index=2
                )
                assert patterns._patterns(ctx) == ["suite_schottish"]

                calls = _spy_figure(monkeypatch, suite_schottish)
                score = _render_form(
                    movement.spec,
                    movement_span=span,
                    movement_index=2,
                )
                assert calls
                assert {bar for bar, _figure in calls} == _body_bars(
                    movement.spec
                )
                assert {event.bar for event in score.lead} <= set(
                    range(movement.spec.bars)
                )
                assert (score.bars, score.beats, score.beat_type) == (
                    movement.spec.bars,
                    2,
                    4,
                )


def test_week_uses_native_2_4_for_the_whole_movement(monkeypatch) -> None:
    with compose_params({}):
        with suite_schottish.use_suite_schottish_abab(True):
            movement = plan_week(2, "guitar", "villa")[0]
            assert movement.spec.meter is METER_24

            ctx = _patterns_context(
                "2/4", 8, movement_span="1W", movement_index=0
            )
            assert patterns._patterns(ctx) == ["suite_schottish"]

            calls = _spy_figure(monkeypatch, suite_schottish)
            score = _render_form(
                movement.spec,
                movement_span="1W",
                movement_index=0,
            )
            assert calls
            assert {bar for bar, _figure in calls} == _body_bars(
                movement.spec
            )
            assert (score.beats, score.beat_type) == (2, 4)


def test_month_movements_one_two_and_four_do_not_select_schottish() -> None:
    with compose_params({}):
        with suite_schottish.use_suite_schottish_abab(True):
            movements = plan_month([8, 8, 8, 8], "guitar", "villa")
            for index in (0, 1, 3):
                spec = movements[index].spec
                label = f"{spec.meter.beats}/{spec.meter.beat_type}"
                assert spec.meter is not METER_24
                ctx = _patterns_context(
                    label, 8, movement_span="1M", movement_index=index
                )
                assert not suite_schottish.selectable(ctx)
                assert "suite_schottish" not in patterns._patterns(ctx)


def test_flag_off_keeps_the_historical_meter_and_render(monkeypatch) -> None:
    from app.sonify.span import month_specs, quarter_specs

    monkeypatch.delenv(flags.SUITE_SCHOTTISH_ENV, raising=False)
    with compose_params({}):
        assert plan_week(2, "guitar", "villa")[0].spec == week_spec(2)
        assert plan_month(
            [8, 8, 8, 8], "guitar", "villa"
        )[2].spec == attach_frame(month_specs("guitar")[2], "1M")
        assert plan_quarter(
            [8, 8, 8], "guitar", "villa"
        )[2].spec == attach_frame(quarter_specs("guitar")[2], "3M")

        form = attach_frame(week_spec(1), "1M")
        scoped = _digest(
            _render_form(form, movement_span="1M", movement_index=2)
        )
        bare = _digest(_render_form(form))
        assert scoped == bare


def test_every_villa_figure_fits_a_2_4_bar() -> None:
    from tests.guitar_fixture import meter_named, pattern_case

    meter = meter_named("2/4")
    ctx, _phrases = pattern_case(
        "probe",
        meter,
        ensemble="villa",
        mood="calm",
        band="mf",
        bpm=96,
        bars=4,
    )
    bar_beats = meter.quarter_beats
    with compose_meter(meter):
        for figure in sorted(VILLA_FIGURES):
            for bar in range(ctx.bars):
                voices = render_villa_figure(
                    ctx, bar, ctx.phrases[0], figure
                )
                for events in voices:
                    for event in events:
                        assert event.beat >= 0
                        assert (
                            event.beat + event.duration_beats
                            <= bar_beats + 1e-9
                        ), (figure, bar, event)


# ---------------------------------------------------------------------------
# Phase 2: phrase roles, cadence, and the multi-spec gate


def _sentence_views(
    count: int,
    *,
    start: int = 0,
    bars: int = 4,
    rises: list[int] | None = None,
) -> tuple[PhraseView, ...]:
    rises = rises or [0] * count
    return tuple(
        PhraseView(
            index=index,
            count=count,
            start_bar=start + index * bars,
            bars=bars,
            closes=index == count - 1,
            rise=rises[index],
            kind="phrase",
        )
        for index in range(count)
    )


@pytest.mark.parametrize("gate", suite_schottish.GATES, ids=("44", "24"))
def test_schottish_three_phrase_plan_uses_b_and_cadence(gate) -> None:
    plan = build_plan(
        gate.pattern,
        gate.meter,
        _sentence_views(3, start=2),
        policy=AutoAABA(),
        registry={gate.key: gate.specs},
    )
    assert [phrase.role.role for phrase in plan.phrases] == [
        "A",
        "B",
        "close",
    ]
    assert [slot.figure for slot in plan.phrases[0].slots] == list(
        SCHOTTISH_FIGURES
    )
    assert [slot.figure for slot in plan.phrases[1].slots] == list(
        SCHOTTISH_B_FIGURES
    )
    assert [slot.figure for slot in plan.phrases[2].slots] == list(
        SCHOTTISH_CLOSE_FIGURES
    )
    # The close phrase's final bar, at its absolute offset, is the cadence.
    assert plan.slots[-1].figure == VILLA_CADENCE
    assert plan.slots[-1].bars == (13,)
    assert [
        slot.figure for slot in plan.slots if slot.figure == VILLA_CADENCE
    ] == [VILLA_CADENCE]


@pytest.mark.parametrize("gate", suite_schottish.GATES, ids=("44", "24"))
def test_schottish_four_phrase_plan_has_exactly_one_b(gate) -> None:
    # A rise on the A phrases must not promote one of them to B.
    plan = build_plan(
        gate.pattern,
        gate.meter,
        _sentence_views(4, start=2, rises=[5, 5, 5, 0]),
        policy=AutoAABA(),
        registry={gate.key: gate.specs},
    )
    roles = [phrase.role.role for phrase in plan.phrases]
    assert roles == ["A", "A", "B", "close"]
    assert roles.count("B") == 1
    assert [slot.figure for slot in plan.phrases[0].slots] == list(
        SCHOTTISH_FIGURES
    )
    assert [slot.figure for slot in plan.phrases[1].slots] == list(
        SCHOTTISH_FIGURES
    )
    assert [slot.figure for slot in plan.phrases[2].slots] == list(
        SCHOTTISH_B_FIGURES
    )
    assert [slot.figure for slot in plan.phrases[3].slots] == list(
        SCHOTTISH_CLOSE_FIGURES
    )


@pytest.mark.parametrize("gate", suite_schottish.GATES, ids=("44", "24"))
def test_gate_specs_are_stable_sorted_and_unregister_cleanly(
    gate,
) -> None:
    expected = tuple(
        sorted(
            (gate.spec, *gate.extra_specs),
            key=lambda spec: (spec.select.length_min, spec.id),
        )
    )
    assert isinstance(gate.specs, tuple)
    assert gate.specs == gate.specs == expected
    assert [spec.role for spec in gate.specs] == ["A", "close", "B"]

    with suite_schottish.use_suite_schottish_abab(True):
        assert specs.SENTENCE_SPECS[gate.key] == expected
        assert suite_gate.unregister(gate) is True
        assert gate.key not in specs.SENTENCE_SPECS
        assert suite_gate.unregister(gate) is False
    assert gate.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("gate", suite_schottish.GATES, ids=("44", "24"))
def test_phrase_plan_keeps_body_offset_and_door_bars(gate) -> None:
    """The partial multi-spec plan writes body phrases at their offset."""
    from tests.guitar_fixture import meter_named, pattern_case

    sections = [
        FormSection(0, 2, "warmup", 0),
        FormSection(2, 14, "phrase", 0),
        FormSection(14, 16, "outro", 0),
    ]
    with compose_params({}):
        with suite_schottish.use_suite_schottish_abab(True):
            ctx, _phrases = pattern_case(
                "probe",
                meter_named(gate.meter),
                ensemble="villa",
                mood="calm",
                band="mf",
                bpm=96,
                bars=16,
                first_body=True,
                previous=[],
                sections=sections,
                movement_span="1W",
                movement_index=0,
            )
            epb = ctx.epb

            def phrase(start: int, end: int) -> Phrase:
                return Phrase(
                    start * epb,
                    end * epb,
                    (Run(start * epb, (end - start) * epb, 64),),
                    False,
                )

            ctx = dataclasses.replace(
                ctx,
                phrases=(phrase(2, 6), phrase(6, 10), phrase(10, 14)),
            )
            views = suite_gate._phrase_views(ctx)
            role_plan = build_plan(
                gate.pattern,
                gate.meter,
                views,
                policy=AutoAABA(),
                registry={gate.key: gate.specs},
            )
            plan = suite_gate._phrase_plan(gate, ctx)

    # Every body phrase survives, and only the middle one is B.
    assert [phrase.role.role for phrase in role_plan.phrases] == [
        "A",
        "B",
        "close",
    ]
    for planned in role_plan.phrases:
        covered = {
            bar for slot in planned.slots for bar in slot.bars
        }
        assert covered == set(
            range(
                planned.phrase.start_bar,
                planned.phrase.start_bar + planned.phrase.bars,
            )
        )

    assert plan is not None
    figures, cells, contours, covered = plan
    body = frozenset(range(2, 14))
    assert covered == body
    assert set(figures) == set(body)
    assert not cells and not contours
    # The warmup/outro door bars stay out of the sentence plan.
    assert set(figures).isdisjoint({0, 1, 14, 15})
    assert [figures[bar] for bar in range(2, 6)] == list(SCHOTTISH_FIGURES)
    assert [figures[bar] for bar in range(6, 10)] == list(
        SCHOTTISH_B_FIGURES
    )
    assert [figures[bar] for bar in range(10, 14)] == list(
        SCHOTTISH_CLOSE_FIGURES
    )
    assert [
        bar for bar in sorted(figures) if figures[bar] == VILLA_CADENCE
    ] == [13]
