"""Phase 2 texture registry: version gate and fail-soft loading.

These tests use ``tmp_path`` for every scan; none of them depend on the repo's
``app/sonify/textures`` directory existing. They also prove the loader never
mutates the runtime registries and that importing the module reads no files.
"""

from __future__ import annotations

import copy
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.sonify.form import METER_44
from app.sonify.sentence_specs import SENTENCE_SPECS
from app.sonify.texture_registry import (
    CURRENT_SCHEMA_VERSION,
    load_report,
    load_specs,
    load_textures,
)
from app.sonify.guitar_wave import PROFILES
from app.studio.texture_spec import (
    MeterSpec,
    MeterVariant,
    TextureSpec,
    parse_texture_spec,
    texture_spec_to_mapping,
    validate_texture_spec,
)

_DEFAULT = object()
DEFAULT_PROVENANCE = {
    "schema_version": CURRENT_SCHEMA_VERSION,
    "renderer_version": "guitar-render-76",
}


def _payload(
    spec_id: str = "villa_arpeggio_aba",
    *,
    runtime: str = "code",
    composer: str = "villa",
    provenance: Any = _DEFAULT,
) -> dict[str, Any]:
    spec = TextureSpec(
        id=spec_id,
        composer=composer,
        kind="pattern",
        level="texture",
        runtime=runtime,
        status="published",
        meter_variants=(
            MeterVariant(
                meter=MeterSpec.from_form_meter(METER_44),
                materializer="grid_4_4",
            ),
        ),
        provenance=(
            copy.deepcopy(DEFAULT_PROVENANCE)
            if provenance is _DEFAULT
            else provenance
        ),
    )
    mapping = texture_spec_to_mapping(spec)
    # Keep the fixture itself honest: a valid loading test must start from a
    # spec the offline validator accepts.
    assert validate_texture_spec(spec) == ()
    return mapping


def _write(root: Path, name: str, payload: Any) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="app.sonify.texture_registry")


def test_missing_directory_is_an_empty_registry(tmp_path: Path) -> None:
    result = load_report(tmp_path / "does-not-exist")
    assert result.specs == ()
    assert result.issues == ()
    assert result.ids == ()


def test_empty_directory_is_an_empty_registry(tmp_path: Path) -> None:
    (tmp_path / "textures").mkdir()
    assert load_textures(tmp_path / "textures") == ()
    assert load_specs(tmp_path / "textures") == ()


def test_valid_spec_loads(tmp_path: Path) -> None:
    _write(tmp_path, "textures/villa_arpeggio_aba/spec.json", _payload())

    specs = load_specs(tmp_path)
    assert len(specs) == 1
    spec = specs[0]
    assert spec.id == "villa_arpeggio_aba"
    assert spec.runtime == "code"
    assert spec.provenance == DEFAULT_PROVENANCE
    # The loader is the only consumer: parsing the same JSON again is equal.
    assert parse_texture_spec(_payload()) == spec


def test_malformed_json_is_logged_and_skipped(tmp_path: Path, caplog) -> None:
    _log(caplog)
    _write(tmp_path, "bad.json", "{not json")
    _write(tmp_path, "good.json", _payload("good"))

    result = load_report(tmp_path)

    assert result.ids == ("good",)
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.code == "json"
    assert issue.path == "bad.json"
    assert "bad.json" in caplog.text
    assert "invalid JSON" in caplog.text


def test_one_bad_spec_does_not_block_the_others(tmp_path: Path) -> None:
    # Unknown top-level key is a structural parse failure, not a crash.
    broken = _payload("broken")
    broken["unexpected_field"] = True
    _write(tmp_path, "a-broken.json", broken)
    _write(tmp_path, "b-good.json", _payload("good"))

    result = load_report(tmp_path)
    assert result.ids == ("good",)
    assert [issue.code for issue in result.issues] == ["parse"]


def test_wrong_schema_version_is_logged_and_skipped(tmp_path: Path, caplog) -> None:
    _log(caplog)
    _write(
        tmp_path,
        "future.json",
        _payload(provenance={"schema_version": "texture-spec-2"}),
    )

    result = load_report(tmp_path)

    assert result.specs == ()
    assert [issue.code for issue in result.issues] == ["schema_version"]
    assert "texture-spec-2" in caplog.text
    assert str(CURRENT_SCHEMA_VERSION) in caplog.text


def test_missing_schema_version_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "no-provenance.json", _payload(provenance=None))
    _write(tmp_path, "empty-provenance.json", _payload(provenance={}))

    result = load_report(tmp_path)

    assert result.specs == ()
    assert [issue.code for issue in result.issues] == [
        "schema_version",
        "schema_version",
    ]


def test_interpreter_without_renderer_version_is_skipped(
    tmp_path: Path, caplog
) -> None:
    _log(caplog)
    _write(
        tmp_path,
        "interpreter.json",
        _payload(runtime="interpreter", provenance={"schema_version": CURRENT_SCHEMA_VERSION}),
    )

    result = load_report(tmp_path)

    assert result.specs == ()
    assert [issue.code for issue in result.issues] == ["renderer_version"]
    assert "interpreter" in caplog.text
    assert "renderer_version" in caplog.text


def test_interpreter_with_renderer_version_loads(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "interpreter.json",
        _payload(
            runtime="interpreter",
            provenance={
                "schema_version": CURRENT_SCHEMA_VERSION,
                "renderer_version": "guitar-render-76",
            },
        ),
    )

    specs = load_textures(tmp_path)
    assert [spec.id for spec in specs] == ["villa_arpeggio_aba"]
    assert specs[0].runtime == "interpreter"


def test_duplicate_ids_keep_the_first_path_and_report_the_rest(
    tmp_path: Path, caplog
) -> None:
    _log(caplog)
    _write(tmp_path, "a.json", _payload("same", composer="first"))
    _write(tmp_path, "nested/b.json", _payload("same", composer="second"))

    result = load_report(tmp_path)

    assert len(result.specs) == 1
    assert result.specs[0].composer == "first"
    assert [issue.code for issue in result.issues] == ["duplicate"]
    assert result.issues[0].path == "nested/b.json"
    assert "already loaded from a.json" in caplog.text


def test_order_is_deterministic_and_sorted_by_id(tmp_path: Path) -> None:
    _write(tmp_path, "z.json", _payload("gamma"))
    _write(tmp_path, "nested/m.json", _payload("beta"))
    _write(tmp_path, "a.json", _payload("alpha"))

    first = load_specs(tmp_path)
    second = load_specs(tmp_path)

    assert [spec.id for spec in first] == ["alpha", "beta", "gamma"]
    assert first == second
    assert load_report(tmp_path).ids == ("alpha", "beta", "gamma")


def test_invalid_spec_is_skipped(tmp_path: Path) -> None:
    # A supported variant with no materializer fails ``validate_texture_spec``,
    # not parsing. The registry reports it as a validation skip.
    broken = _payload("broken")
    broken["meter_variants"][0]["materializer"] = None
    _write(tmp_path, "broken.json", broken)

    result = load_report(tmp_path)

    assert result.specs == ()
    assert [issue.code for issue in result.issues] == ["validate"]
    assert "materializer" in result.issues[0].message


def test_loading_does_not_mutate_runtime_registries(tmp_path: Path) -> None:
    before_sentences = dict(SENTENCE_SPECS)
    before_profiles = copy.deepcopy(PROFILES)
    _write(tmp_path, "textures/villa_arpeggio_aba/spec.json", _payload())

    specs = load_specs(tmp_path)

    assert len(specs) == 1
    assert dict(SENTENCE_SPECS) == before_sentences
    assert PROFILES == before_profiles


def test_import_reads_no_files_and_registers_nothing() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import pathlib\n"
        "def _boom(*args, **kwargs):\n"
        "    raise AssertionError('importing texture_registry read a file')\n"
        "pathlib.Path.read_text = _boom\n"
        "from app.sonify.sentence_specs import SENTENCE_SPECS\n"
        "before = len(SENTENCE_SPECS)\n"
        "import app.sonify.texture_registry\n"
        "print(before, len(SENTENCE_SPECS), "
        "'app.sonify.guitar_patterns' in __import__('sys').modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    before, after, loaded = completed.stdout.split()
    assert before == after
    assert loaded == "False"


def test_load_default_is_lazy_and_cached(tmp_path: Path, monkeypatch) -> None:
    import app.sonify.texture_registry as registry

    calls: list[Path | None] = []

    def fake_load_specs(root=None):
        calls.append(root)
        return ()

    monkeypatch.setattr(registry, "load_specs", fake_load_specs)
    registry.clear_cache()
    try:
        assert calls == []
        assert registry.load_default() == ()
        assert registry.load_default() == ()
        assert calls == [registry.TEXTURES_DIR]
    finally:
        registry.clear_cache()
