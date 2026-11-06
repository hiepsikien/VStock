"""Compile one authored sentence spec into a deterministic publish bundle.

Phase 0/1 treats a `SentenceSpec` as **authoring source plus fixture**: the
runtime still renders through `guitar_torroba` / `guitar_sor`, and nothing in
this module registers a spec. The compiler answers one question for the Studio
and for the PR author:

    what exactly would land in the repo if this spec were published?

The answer is one bundle:

    {"schemaVersion": 1,
     "spec": {...},                 # the v1 JSON mapping
     "fixture": {...},              # resolved, bounded preview input
     "rendered": {plan, row, notes, renderHash, matrix},
     "registration": {pattern, meter, id, family, ownerModule,
                      alreadyRegistered, validFigures, checklist}}

`compile_sentence` is pure (apart from reading the committed example files to
name the spec's source): it validates through `dispatch.validate`, previews
through `dispatch.preview_sentence`, and never writes. `compile_bundle` is the
same function under its artifact name. `export_bundle` writes the four fixed
files of §11.2:

    spec.json  fixture.json  rendered.json  registration.md

`preview.wav` is deliberately absent: the compiler does not call MuseScore or
the synth cache. `registration.md` is a checklist, not a registry patch, and
contains no timestamps, user ids, or absolute paths, so two exports of the same
spec are byte-identical.

The HTTP router never calls `export_bundle`: the server does not write into the
repo. It returns the bundle JSON and the caller (UI, test, or agent) decides
where the artifact lives.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.sonify import sentence_specs
from app.sonify.guitar_barrios_figures import BARRIOS_FIGURES
from app.sonify.guitar_barrios_period import (
    BARRIOS_CATHEDRAL_PERIOD_ID,
    BARRIOS_PERIOD_ENV,
)
from app.sonify.guitar_brouwer_figures import BROUWER_FIGURES
from app.sonify.guitar_sor import GALOP_CELL_1, GALOP_CELL_2
from app.sonify.guitar_torroba import _FIGURES
from app.sonify.guitar_villa_figures import VILLA_FIGURES
from app.sonify.sentence_specs import SentenceSpec
from app.studio import dispatch
from app.studio.candidates import CANDIDATES_DIR
from app.studio.export import SPECS_DIR
from app.studio.preview import Error
from app.studio.sentence_spec import spec_to_mapping

SCHEMA_VERSION = 1

BUNDLE_FILES = ("spec.json", "fixture.json", "rendered.json", "registration.md")

# The renderer that owns each family's bar writers. The preview module is the
# read-only authoring path, not the runtime.
_OWNER_MODULES = {
    dispatch.TORROBA_SOR: "backend/app/sonify/guitar_torroba.py",
    dispatch.VILLA: "backend/app/sonify/guitar_villa.py",
    dispatch.BARRIOS: "backend/app/sonify/guitar_barrios.py",
    dispatch.BROUWER: "backend/app/sonify/guitar_brouwer.py",
}
_PREVIEW_MODULES = {
    dispatch.TORROBA_SOR: "backend/app/studio/preview.py",
    dispatch.VILLA: "backend/app/studio/villa_preview.py",
    dispatch.BARRIOS: "backend/app/studio/barrios_preview.py",
    dispatch.BROUWER: "backend/app/studio/brouwer_preview.py",
}
_FAMILY_TESTS = {
    dispatch.TORROBA_SOR: (
        "backend/tests/test_studio_preview.py",
        "backend/tests/test_studio_sentence_spec.py",
    ),
    dispatch.VILLA: ("backend/tests/test_studio_villa_sentence.py",),
    dispatch.BARRIOS: ("backend/tests/test_studio_barrios_period.py",),
    dispatch.BROUWER: ("backend/tests/test_studio_brouwer_sentence.py",),
}
_BUNDLE_TEST = "backend/tests/test_studio_export.py"

# The committed authored sources. `backend/` is the repo-relative prefix, so
# the checklist never leaks the absolute checkout path.
_SOURCE_DIRS = (
    (SPECS_DIR, "backend/app/studio/specs"),
    (CANDIDATES_DIR, "backend/app/studio/candidates"),
)


class CompileError(Exception):
    """One failed compile. `errors` keeps the preview's JSON paths."""

    def __init__(self, errors: tuple[Error, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(f"{e.path}: {e.message}" for e in self.errors))


# ---------------------------------------------------------------------------
# registration metadata


def _registered_specs(pattern: str, meter: str) -> tuple[SentenceSpec, ...]:
    """Registry membership for one key, exact key before the `"*"` wildcard.

    This reads `SENTENCE_SPECS` through the same lookup the planners use. It
    never calls `register()`; a compiled candidate stays invisible to runtime.
    """
    return sentence_specs._lookup(pattern, meter) or ()


def _already_registered(spec: SentenceSpec) -> bool:
    return any(existing == spec for existing in _registered_specs(spec.pattern, spec.meter))


def _uses_cells(spec: SentenceSpec) -> bool:
    """True when the sentence is realized by cell ids (Sor's galop), not figures."""
    return any(slot.cell is not None for slot in spec.slots)


def _valid_figures(spec: SentenceSpec, family: str) -> list[Any]:
    if family == dispatch.TORROBA_SOR:
        if _uses_cells(spec):
            return sorted((GALOP_CELL_1, GALOP_CELL_2))
        return sorted(_FIGURES)
    if family == dispatch.VILLA:
        return sorted(VILLA_FIGURES)
    if family == dispatch.BARRIOS:
        return sorted(BARRIOS_FIGURES)
    return sorted(BROUWER_FIGURES)


def _owner_module(spec: SentenceSpec, family: str) -> str:
    if family == dispatch.TORROBA_SOR and _uses_cells(spec):
        # A cell cycle is realized by Sor's galop writer, not Torroba's figures.
        return "backend/app/sonify/guitar_sor.py"
    return _OWNER_MODULES[family]


def _committed_source(spec: SentenceSpec) -> str | None:
    """The repo-relative authored JSON for this exact spec, when one is committed."""
    for directory, prefix in _SOURCE_DIRS:
        for path in sorted(Path(directory).glob("*.json")):
            try:
                wrapper = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for raw in wrapper.get("specs", ()):
                if not isinstance(raw, Mapping):
                    continue
                if (
                    raw.get("id") == spec.id
                    and raw.get("pattern") == spec.pattern
                    and raw.get("meter") == spec.meter
                ):
                    return f"{prefix}/{path.name}"
    return None


def _figures_entry(spec: SentenceSpec, family: str, figures: list[Any]) -> str:
    joined = ", ".join(str(figure) for figure in figures)
    if family == dispatch.TORROBA_SOR and _uses_cells(spec):
        return f"figures: {joined} (cell realizers, not figure ids)"
    return f"figures: {joined}"


def _checklist(
    spec: SentenceSpec,
    family: str,
    *,
    registered: bool,
    source: str | None,
) -> list[str]:
    """The PR checklist derived from the spec, its family, and the registry.

    Every line names a file or a registry fact. None of it proposes a runtime
    change: in Phase 0/1 the spec is authoring data, and the renderer stays
    code-backed.
    """
    owner = _owner_module(spec, family)
    key = f"({spec.pattern!r}, {spec.meter!r})"
    state = "registered" if registered else "not registered"
    entries = [
        f"renderer: {owner}",
        f"preview: {_PREVIEW_MODULES[family]}",
        f"registry: backend/app/sonify/sentence_specs.py "
        f"SENTENCE_SPECS[{key}] ({state})",
        _figures_entry(spec, family, _valid_figures(spec, family)),
        (
            f"sentence JSON: {source}"
            if source is not None
            else "sentence JSON: not committed; add the exported spec.json in the PR"
        ),
        "tests: " + ", ".join((*_FAMILY_TESTS[family], _BUNDLE_TEST)),
    ]
    if not registered:
        entries.append(
            f"still preview-only: {spec.id!r} is not in SENTENCE_SPECS; "
            "the runtime stays code-backed and no planner reads this JSON"
        )
    if family == dispatch.BARRIOS and spec.id == BARRIOS_CATHEDRAL_PERIOD_ID:
        entries.append(
            "candidate status: preview-only in Studio; a feature-gated production "
            f"path exists behind {BARRIOS_PERIOD_ENV} (default off)"
        )
    elif family != dispatch.TORROBA_SOR:
        entries.append(
            "candidate status: preview-only pilot; no production planner selects it"
        )
    return entries


def _registration(spec: SentenceSpec, family: str) -> dict[str, Any]:
    registered = _already_registered(spec)
    source = _committed_source(spec)
    return {
        "pattern": spec.pattern,
        "meter": spec.meter,
        "id": spec.id,
        "family": family,
        "ownerModule": _owner_module(spec, family),
        "alreadyRegistered": registered,
        "validFigures": _valid_figures(spec, family),
        "checklist": _checklist(spec, family, registered=registered, source=source),
    }


# ---------------------------------------------------------------------------
# compile / export


def compile_sentence(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None = None,
    family: str | None = None,
) -> dict[str, Any]:
    """Validate and preview one spec, returning its bundle.

    Raises `CompileError` (with the family's JSON-path errors) instead of
    returning a partial bundle. Reads the registry and the committed examples;
    writes nothing and registers nothing. `family` is the draft-only override
    used for a new pattern; production callers omit it.
    """
    if family is not None and family not in dispatch.FAMILIES:
        raise CompileError((Error("family", f"unknown family {family!r}"),))
    owner = family if family is not None else dispatch.family_for(spec.pattern)
    errors = dispatch.validate(spec, family=owner)
    if errors or owner is None:
        raise CompileError(tuple(errors) or (Error("pattern", "unknown pattern"),))

    result = dispatch.preview_sentence(spec, fixture, family=owner)
    if not result.ok:
        raise CompileError(result.errors or (Error("spec", "preview failed"),))

    try:
        resolved = dispatch.resolve_fixture(spec, fixture, family=owner)
    except (ValueError, TypeError) as exc:
        raise CompileError((Error("fixture", str(exc)),)) from None

    return {
        "schemaVersion": SCHEMA_VERSION,
        "spec": spec_to_mapping(spec),
        "fixture": resolved,
        "rendered": {
            "plan": result.plan,
            "row": result.row,
            "notes": list(result.notes),
            "renderHash": result.render_hash,
            "matrix": list(result.matrix),
        },
        "registration": _registration(spec, owner),
    }


def compile_bundle(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None = None,
    family: str | None = None,
) -> dict[str, Any]:
    """`compile_sentence` under its artifact name: the bundle, with no writes.

    Kept as the counterpart to `export_bundle` so callers can say "compile" vs
    "compile and write". It raises `CompileError` exactly like `compile_sentence`.
    """
    return compile_sentence(spec, fixture, family=family)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def render_registration(registration: Mapping[str, Any]) -> str:
    """The deterministic `registration.md` body for one bundle."""
    figures = ", ".join(str(figure) for figure in registration["validFigures"])
    lines = [
        f"# Registration: {registration['id']}",
        "",
        f"- pattern: `{registration['pattern']}`",
        f"- meter: `{registration['meter']}`",
        f"- family: `{registration['family']}`",
        f"- owner: `{registration['ownerModule']}`",
        f"- registered: {'yes' if registration['alreadyRegistered'] else 'no'}",
        f"- valid figures: {figures}",
        "",
        "## Checklist",
        "",
    ]
    lines.extend(f"- [ ] {entry}" for entry in registration["checklist"])
    lines.append("")
    return "\n".join(lines)


def export_bundle(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None,
    out_dir: str | Path,
) -> list[Path]:
    """Write the four bundle files into `out_dir` and return their paths.

    Names are fixed, so nothing derived from the spec id can escape `out_dir`.
    The directory is created when missing; no other file is touched.
    """
    bundle = compile_sentence(spec, fixture)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    payloads = {
        "spec.json": bundle["spec"],
        "fixture.json": bundle["fixture"],
        "rendered.json": bundle["rendered"],
    }
    written: list[Path] = []
    for name, payload in payloads.items():
        path = target / name
        path.write_text(_json(payload), encoding="utf-8")
        written.append(path)

    registration_path = target / "registration.md"
    registration_path.write_text(
        render_registration(bundle["registration"]), encoding="utf-8"
    )
    written.append(registration_path)
    return written
