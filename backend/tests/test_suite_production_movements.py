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
import app.sonify.guitar_suite_gavotta as suite_gavotta
import app.sonify.guitar_suite_schottish as suite_schottish
import app.sonify.guitar_suite_valsa as suite_valsa
from app.sonify import production_flags as flags
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_34, METER_44, FormSection, FormSpec
from app.sonify.guitar_villa_figures import (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
)
from app.sonify.guitar_wave import PROFILES
from app.sonify.model import Bar
from app.sonify.params import compose_params
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


def _render(ensemble: str, meter, bars: int):
    with compose_params({}):
        return render(
            _bars(bars),
            variant="guitar",
            ensemble=ensemble,
            form=_form(bars, meter),
            framed=True,
        )


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


def _patterns_context(meter_label: str, bars: int):
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
    off = _digest(_render("villa", case.meter, case.bars))
    calls = _spy_figure(monkeypatch, case.module)
    on = _render("villa", case.meter, case.bars)
    assert calls == []
    assert _digest(on) == off
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_falls_back_below_min_bars(monkeypatch, case: Case) -> None:
    short = case.min_bars - 1
    off = _digest(_render("villa", case.meter, short))
    calls = _spy_figure(monkeypatch, case.module)
    with case.context(True):
        on = _render("villa", case.meter, short)
    assert calls == []
    assert _digest(on) == off
    assert case.key not in specs.SENTENCE_SPECS


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_falls_back_in_the_other_meter(monkeypatch, case: Case) -> None:
    other = METER_44 if case.meter is METER_34 else METER_34
    off = _digest(_render("villa", other, case.bars))
    calls = _spy_figure(monkeypatch, case.module)
    with case.context(True):
        on = _render("villa", other, case.bars)
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
            )
    assert calls == []
    assert _digest(on) == _digest(off)
    assert case.key not in specs.SENTENCE_SPECS


# ---------------------------------------------------------------------------
# on: registration, selection, render


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_on_registers_selects_and_renders_the_tile(monkeypatch, case: Case) -> None:
    off = _digest(_render("villa", case.meter, case.bars))
    calls = _spy_figure(monkeypatch, case.module)

    with case.context(True):
        assert specs.SENTENCE_SPECS.get(case.key) == (case.spec,)
        tiled = (case.figures * (case.bars // len(case.figures) + 1))[: case.bars]
        assert specs.plan_sentence(
            case.pattern, case.meter_label, case.bars, 0
        ) == [(figure, (bar,)) for bar, figure in enumerate(tiled)]

        on = _render("villa", case.meter, case.bars)

        assert calls == list(enumerate(tiled))
        assert on.divisions == 2
        assert {event.bar for event in on.lead} == set(range(case.bars))
        assert _digest(on) != off

    assert case.key not in specs.SENTENCE_SPECS
    assert specs.plan_sentence(case.pattern, case.meter_label, case.bars, 0) is None
    assert _digest(_render("villa", case.meter, case.bars)) == off


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_selection_is_the_same_predicate_as_render(case: Case) -> None:
    with compose_params({}):
        with case.context(True):
            ctx = _patterns_context(case.meter_label, case.bars)
            assert patterns._patterns(ctx) == [case.pattern]

            short = _patterns_context(case.meter_label, case.min_bars - 1)
            assert case.pattern not in patterns._patterns(short)

            other_label = "4/4" if case.meter is METER_34 else "3/4"
            other_ctx = _patterns_context(other_label, case.bars)
            assert case.pattern not in patterns._patterns(other_ctx)


@pytest.mark.parametrize("case", CASES_WITH_IDS)
def test_env_auditions_without_the_context(monkeypatch, case: Case) -> None:
    monkeypatch.setenv(case.env, "on")
    calls = _spy_figure(monkeypatch, case.module)
    try:
        score = _render("villa", case.meter, case.bars)
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
