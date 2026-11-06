"""The pattern registry: `level` and `name_source` cover `_FAMILY` exactly.

Metadata only. These tests pin the split the model doc section 12 decided: five
texture ids, thirty-eight topics, and a printed title for every topic.

The second half is the codegen gate: the generated TypeScript must match the
Python registries, every row must carry a title plus its `level`/`name_source`,
and uniqueness is per ensemble rather than global. The TS `PATTERN_NAMES` set
is the 35 distinct topic titles; `Pedal` is a texture and never enters it.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from app.sonify.guitar_patterns import _FAMILY
from app.sonify.guitar_wave import PROFILES
from app.sonify.pattern_registry import (
    LEVELS,
    NAME_SOURCES,
    PATTERN_META,
    PatternMeta,
    meta,
    validate,
)
from app.sonify.program import _PATTERN_TITLE, pattern_title

# The five texture ids. `thumb_cantabile` is one id for two ensembles.
_TEXTURE = {
    "villa_pattern",
    "chord_melody",
    "tremolo",
    "thumb_cantabile",
    "pedal",
}
_TOPIC = set(_FAMILY) - _TEXTURE


def test_registry_covers_family() -> None:
    assert set(PATTERN_META) == set(_FAMILY)
    assert len(PATTERN_META) == 43


def test_registry_key_matches_id() -> None:
    for pattern, found in PATTERN_META.items():
        assert isinstance(found, PatternMeta)
        assert found.id == pattern


def test_level_sets_are_exact() -> None:
    topic = {
        pattern for pattern, found in PATTERN_META.items() if found.level == "topic"
    }
    texture = {
        pattern for pattern, found in PATTERN_META.items() if found.level == "texture"
    }
    assert topic == _TOPIC
    assert texture == _TEXTURE
    assert len(topic) == 38
    assert len(texture) == 5


def test_every_topic_prints_a_title() -> None:
    for ensemble, pattern in PROFILES:
        if PATTERN_META[pattern].level == "topic":
            assert pattern_title(pattern, ensemble), (ensemble, pattern)


def test_name_source_rules() -> None:
    for pattern, found in PATTERN_META.items():
        assert found.level in LEVELS
        if found.level == "texture":
            assert found.name_source is None, pattern
        else:
            assert found.name_source in NAME_SOURCES, pattern


@pytest.mark.parametrize("pattern", sorted(_TEXTURE))
def test_texture_needs_no_title(monkeypatch: pytest.MonkeyPatch, pattern: str) -> None:
    """A texture owns no name, so validate() must pass with every texture title gone."""
    monkeypatch.delitem(_PATTERN_TITLE, pattern)
    assert validate() is None


def test_validate_rejects_a_topic_without_a_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(_PATTERN_TITLE, "study")
    with pytest.raises(ValueError, match="no printed title"):
        validate()


def test_unknown_pattern_raises() -> None:
    with pytest.raises(KeyError):
        meta("not-a-pattern")


def test_validate_passes_on_the_real_module() -> None:
    assert validate() is None


# --- Codegen gate -----------------------------------------------------------
#
# `scripts/gen_pattern_registry.py` builds rows from `PROFILES` ∪ `_FAMILY`.
# These tests are the real gate (the repo has no CI): they check title
# coverage, per-ensemble uniqueness, and that the committed generated file is
# reproducible and fresh.

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gen_pattern_registry.py"
GENERATED = ROOT / "src" / "sonify" / "patternRegistry.generated.ts"

# Global repeats are intentional: one title can name a topic in two ensembles.
# Per-ensemble uniqueness is the real rule (§12.3).
_KNOWN_GLOBAL_DUPLICATES = {"Cantabile", "Etude", "Prelude", "Sarabande"}


def _codegen():
    """Load the script as a module so tests read the same rows it writes."""
    spec = importlib.util.spec_from_file_location("gen_pattern_registry", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolves string annotations through sys.modules, so register
    # the module before executing it. Keep the repo free of scripts/__pycache__.
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _owners() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    for ensemble, pattern in PROFILES:
        owners[pattern].add(ensemble)
    return owners


def test_every_profile_row_has_a_title() -> None:
    """The wave registry is the printed surface; every row must be named."""
    missing = [
        (ensemble, pattern)
        for ensemble, pattern in sorted(PROFILES)
        if not pattern_title(pattern, ensemble)
    ]
    assert not missing, missing


def test_every_family_pattern_has_a_title() -> None:
    """Probe the owning ensemble; fall back to `classic` only when none exists.

    Assumption: `_PATTERN_TITLE` is keyed by id and does not vary by ensemble,
    except `thumb_cantabile` (Barrios "Cantabile", Villa "Prelude"). A
    family-only id has no `PROFILES` row, so there is no owner to probe; the
    docs name `classic` as the neutral fallback. If a title ever becomes
    ensemble-dependent for another id, this probe must be revisited.
    """
    owners = _owners()
    missing = [
        pattern
        for pattern in sorted(_FAMILY)
        if not any(
            pattern_title(pattern, ensemble)
            for ensemble in (owners.get(pattern) or {"classic"})
        )
    ]
    assert not missing, missing


def test_titles_are_unique_within_each_ensemble() -> None:
    """A listener inside one ensemble must not hear two different topics alike."""
    by_ensemble: dict[str, list[str]] = defaultdict(list)
    for ensemble, pattern in sorted(PROFILES):
        title = pattern_title(pattern, ensemble)
        if title:
            by_ensemble[ensemble].append(title)
    for ensemble, titles in by_ensemble.items():
        duplicates = sorted({title for title in titles if titles.count(title) > 1})
        assert not duplicates, (ensemble, duplicates)


def test_the_four_known_global_duplicates_are_allowed() -> None:
    """Global repeats cross ensembles, so they are not a collision."""
    by_title: dict[str, set[str]] = defaultdict(set)
    for ensemble, pattern in sorted(PROFILES):
        title = pattern_title(pattern, ensemble)
        if title:
            by_title[title].add(ensemble)

    repeated = {
        title for title, ensembles in by_title.items() if len(ensembles) > 1
    }
    assert repeated == _KNOWN_GLOBAL_DUPLICATES
    for title in sorted(repeated):
        assert len(by_title[title]) >= 2, title


def test_generated_rows_cover_the_python_registries() -> None:
    module = _codegen()
    rows = module.build_rows()

    profiled = {pattern for _ensemble, pattern in PROFILES}
    family_only = set(_FAMILY) - profiled

    assert len(rows) == len(PROFILES) + len(family_only)
    assert len(PROFILES) == 43
    assert family_only == {"pedal"}

    wave_rows = {(row.ensemble, row.pattern) for row in rows if row.wave_profile}
    assert wave_rows == set(PROFILES)

    standalone = {row.pattern for row in rows if row.ensemble is None}
    assert standalone == family_only

    for row in rows:
        assert row.pattern in _FAMILY
        assert row.family == _FAMILY[row.pattern]
        assert row.title, (row.ensemble, row.pattern)
        assert row.wave_profile is (row.ensemble is not None)
        expected = PATTERN_META[row.pattern]
        assert row.level == expected.level, (row.ensemble, row.pattern)
        assert row.name_source == expected.name_source, (row.ensemble, row.pattern)


def test_generated_rows_split_topics_from_textures() -> None:
    """38 topic rows and 6 texture rows, with `pedal` never a printed topic."""
    rows = _codegen().build_rows()

    topic_rows = [row for row in rows if row.level == "topic"]
    texture_rows = [row for row in rows if row.level == "texture"]
    assert len(topic_rows) == 38
    assert len(texture_rows) == 6
    assert {row.pattern for row in texture_rows} == _TEXTURE

    pedal_rows = [row for row in rows if row.pattern == "pedal"]
    assert len(pedal_rows) == 1
    assert pedal_rows[0].level == "texture"
    assert pedal_rows[0].name_source is None


def test_generated_topic_titles_are_the_frontend_set() -> None:
    """The TS set is the 35 distinct topic titles, with no texture title.

    38 topic rows collapse to 35 titles because `Etude`, `Prelude`, and
    `Sarabande` each name a topic in two ensembles. `PATTERN_NAMES` is a Set,
    so the count is 35. `Pedal` is a texture, so it never enters.
    """
    rows = _codegen().build_rows()

    topic_titles = {row.title for row in rows if row.level == "topic"}
    assert len(topic_titles) == 35
    assert "Pedal" not in topic_titles
    assert topic_titles.isdisjoint({"Arpeggio", "Chord Melody", "Tremolo"})

    # The full row set keeps the four known global repeats (§12.3).
    all_titles = [row.title for row in rows]
    repeated = {
        title for title in set(all_titles) if all_titles.count(title) > 1
    }
    assert repeated == _KNOWN_GLOBAL_DUPLICATES
    # 39 distinct titles over all 44 rows; 38 over the printed rows, because
    # `Pedal` is the only non-printed row and it owns a title of its own.
    assert len(set(all_titles)) == 39
    printed_titles = {row.title for row in rows if row.wave_profile}
    assert len(printed_titles) == 38
    assert "Pedal" not in printed_titles


def test_committed_registry_is_fresh() -> None:
    assert GENERATED.is_file()
    completed = _run("--check")
    assert completed.returncode == 0, completed.stderr


def test_check_detects_drift(tmp_path: Path) -> None:
    drifted = tmp_path / "patternRegistry.generated.ts"
    drifted.write_text(
        GENERATED.read_text(encoding="utf-8") + "// drift\n", encoding="utf-8"
    )

    completed = _run("--check", "--out", str(drifted))
    assert completed.returncode == 1
    assert "out of date" in completed.stderr


def test_check_rejects_a_missing_file(tmp_path: Path) -> None:
    completed = _run("--check", "--out", str(tmp_path / "absent.ts"))
    assert completed.returncode == 1
    assert "out of date" in completed.stderr


def test_generated_file_is_deterministic_across_two_builds(tmp_path: Path) -> None:
    first = tmp_path / "first.ts"
    second = tmp_path / "second.ts"

    for path in (first, second):
        completed = _run("--write", "--out", str(path))
        assert completed.returncode == 0, completed.stderr

    committed = GENERATED.read_text(encoding="utf-8")
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert first.read_text(encoding="utf-8") == committed
