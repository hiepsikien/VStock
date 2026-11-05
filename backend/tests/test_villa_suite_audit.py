"""Phase 2 audit data for the Villa-Lobos *Suite Popular Brasileira*.

The audit is data only. Importing it must not register a sentence, mutate a
production table, or turn an audit movement into a Studio example.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

# Import both production owners so the registry snapshot is complete before
# the audit checks that it did not change.
import app.sonify.guitar_sor  # noqa: F401
import app.sonify.guitar_torroba  # noqa: F401
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_34, METER_44, Meter
from app.sonify.guitar_wave import PROFILES
from app.sonify.pattern_registry import PATTERN_META
from app.sonify.program import pattern_title
from app.studio.examples import examples
from app.studio.villa_suite_audit import (
    SENTENCE_VERDICTS,
    SUITE_MOVEMENTS,
    VILLA_PATTERN_IDS,
    SuiteMovement,
    coverage,
    first_movement,
    validate,
)

ORDER = (
    "suite_mazurka",
    "suite_schottish",
    "suite_valsa",
    "suite_gavotta",
    "suite_choros1",
)
TITLES = (
    "Mazurka-Choro",
    "Schottish-Choro",
    "Valsa-Choro",
    "Gavotta-Choro",
    "Choros No. 1",
)


def _known_titles() -> set[str]:
    ensembles = ("villa", "classic", "barrios", "bach", "brouwer", "torroba")
    return {
        title
        for pattern in PATTERN_META
        for ensemble in ensembles
        if (title := pattern_title(pattern, ensemble))
    }


def _with_first(**changes) -> tuple[SuiteMovement, ...]:
    return (replace(SUITE_MOVEMENTS[0], **changes),) + SUITE_MOVEMENTS[1:]


# ---------------------------------------------------------------------------
# shape and identity


def test_the_suite_has_five_movements_in_the_documented_order() -> None:
    assert len(SUITE_MOVEMENTS) == 5
    assert tuple(movement.id for movement in SUITE_MOVEMENTS) == ORDER
    assert tuple(movement.title for movement in SUITE_MOVEMENTS) == TITLES
    assert first_movement() is SUITE_MOVEMENTS[0]
    assert first_movement().id == "suite_mazurka"


def test_ids_and_titles_are_unique_and_do_not_collide_with_patterns() -> None:
    validate()
    ids = [movement.id for movement in SUITE_MOVEMENTS]
    titles = [movement.title for movement in SUITE_MOVEMENTS]

    assert len(set(ids)) == 5
    assert len(set(titles)) == 5
    assert not set(ids) & set(PATTERN_META)
    assert not set(titles) & _known_titles()


def test_validate_rejects_a_pattern_id_collision() -> None:
    with pytest.raises(ValueError, match="collides with an existing pattern id"):
        validate(_with_first(id="choro"))


def test_validate_rejects_a_pattern_title_collision() -> None:
    with pytest.raises(ValueError, match="collides with an existing pattern title"):
        validate(_with_first(title="Waltz"))


def test_validate_rejects_a_duplicate_movement_id() -> None:
    duplicate = replace(SUITE_MOVEMENTS[1], id=SUITE_MOVEMENTS[0].id)
    movements = (SUITE_MOVEMENTS[0], duplicate) + SUITE_MOVEMENTS[2:]
    with pytest.raises(ValueError, match="duplicate movement ids"):
        validate(movements)


# ---------------------------------------------------------------------------
# meter evidence


def test_every_meter_is_real_or_explicitly_flagged_unknown() -> None:
    for movement in SUITE_MOVEMENTS:
        if movement.meter is None:
            assert movement.meter_uncertain is True
        else:
            assert isinstance(movement.meter, Meter)
        assert movement.meter_source.strip()
        if movement.meter_uncertain:
            assert movement.meter_note.strip()


def test_meter_derivations_match_the_evidence() -> None:
    by_id = {movement.id: movement for movement in SUITE_MOVEMENTS}

    # Exact 3/4: no fold.
    assert by_id["suite_mazurka"].meter == METER_34
    assert by_id["suite_valsa"].meter == METER_34
    assert not by_id["suite_mazurka"].meter_uncertain
    assert not by_id["suite_valsa"].meter_uncertain

    # 2/4 sources must be marked as folded or provisional, never as exact 4/4.
    for movement_id in ("suite_schottish", "suite_gavotta", "suite_choros1"):
        movement = by_id[movement_id]
        assert movement.meter == METER_44
        assert movement.meter_uncertain is True
        assert movement.meter_note.strip()


def test_validate_rejects_a_missing_meter_that_is_not_flagged() -> None:
    with pytest.raises(ValueError, match="missing meter must be marked uncertain"):
        validate(_with_first(meter=None, meter_uncertain=False))


# ---------------------------------------------------------------------------
# existing-pattern overlap


def test_audit_patterns_are_exactly_the_real_villa_rows() -> None:
    villa_rows = {pattern for ensemble, pattern in PROFILES if ensemble == "villa"}
    assert VILLA_PATTERN_IDS == villa_rows
    for movement in SUITE_MOVEMENTS:
        assert set(movement.pattern_overlap) <= villa_rows


def test_coverage_keeps_empty_patterns_as_the_audit_finding() -> None:
    found = coverage()

    assert set(found) == VILLA_PATTERN_IDS
    assert found["villa_pattern"] == ORDER
    assert found["chord_melody"] == ORDER
    assert found["thumb_cantabile"] == ("suite_mazurka", "suite_valsa")
    assert found["etude1"] == ()
    assert found["etude11"] == ()


# ---------------------------------------------------------------------------
# sentence judgement and authoring gaps


def test_every_movement_has_a_sentence_verdict_rationale_and_gaps() -> None:
    for movement in SUITE_MOVEMENTS:
        assert movement.sentence_plausible in SENTENCE_VERDICTS
        assert movement.rationale.strip()
        assert movement.gaps
        assert all(gap.strip() for gap in movement.gaps)


def test_validate_rejects_an_empty_rationale() -> None:
    with pytest.raises(ValueError, match="rationale must not be empty"):
        validate(_with_first(rationale="  "))


# ---------------------------------------------------------------------------
# no production registration, no candidate auto-registration


def test_audit_calls_do_not_mutate_the_sentence_registry() -> None:
    before = dict(specs.SENTENCE_SPECS)

    validate()
    coverage()
    first_movement()

    assert dict(specs.SENTENCE_SPECS) == before
    assert not [key for key in specs.SENTENCE_SPECS if key[0].startswith("suite_")]


def test_audit_movement_ids_are_not_studio_examples() -> None:
    example_ids = {example.id for example in examples()}
    assert not {movement.id for movement in SUITE_MOVEMENTS} & example_ids


def test_import_is_inert() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import sys\n"
        "from app.sonify.sentence_specs import SENTENCE_SPECS\n"
        "before = len(SENTENCE_SPECS)\n"
        "import app.studio.villa_suite_audit\n"
        "suite = [key for key in SENTENCE_SPECS if key[0].startswith('suite_')]\n"
        "print(before, len(SENTENCE_SPECS), suite, "
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
    before, after, suite, loaded = completed.stdout.split()
    assert before == after
    assert suite == "[]"
    assert loaded == "False"
