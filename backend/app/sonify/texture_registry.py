"""Fail-soft loader for published ``TextureSpec`` JSON files.

This is the Phase 2 reader from ``docs/sonify-texture-studio.md`` §7.2. It is
deliberately a reader and nothing else:

* It scans ``app/sonify/textures/**/*.json`` (one spec per file), parses each
  file with :func:`app.studio.texture_spec.parse_texture_spec`, and checks the
  version gate (``provenance.schema_version`` allowlist plus
  ``provenance.renderer_version`` for ``runtime: "interpreter"``).
* JSON that is broken, a spec that does not parse, a spec that fails the
  offline validator, an unsupported schema version, or a duplicate id is
  **skipped and logged**, never raised. One bad published file cannot stop the
  app from booting or block ``/health``.
* It never registers into ``SENTENCE_SPECS``, ``PROFILES``, or a planner, and
  it never imports a renderer. Loading a spec does not make it a runtime
  consumer; that wiring belongs to a later phase.
* It only reads files in the repo. There is no network, cache directory, or
  environment lookup.

Importing this module is inert: no directory is read until ``load_specs`` (or
``load_report``/``load_default``) is called. ``load_default`` is the lazy
convenience entry point for the committed texture directory.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.studio.texture_spec import (
    TextureSpec,
    TextureSpecError,
    parse_texture_spec,
    validate_texture_spec,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "SCHEMA_VERSIONS",
    "TEXTURES_DIR",
    "TextureIssue",
    "TextureLoadResult",
    "clear_cache",
    "load_default",
    "load_report",
    "load_specs",
    "load_textures",
]

# The schema string carried by ``provenance.schema_version``. Only versions in
# this allowlist are accepted; a new authored shape needs a new constant and a
# deliberate review, not a silent parse of whatever a published file says.
CURRENT_SCHEMA_VERSION = "texture-spec-1"
SCHEMA_VERSIONS = frozenset({CURRENT_SCHEMA_VERSION})

#: Directory containing published specs. It may not exist yet; an absent or
#: empty directory is a normal empty registry, not an error.
TEXTURES_DIR = Path(__file__).with_name("textures")


@dataclass(frozen=True)
class TextureIssue:
    """One skipped file, addressed by its path relative to the scan root."""

    path: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass(frozen=True)
class TextureLoadResult:
    """Loaded specs plus every skip, in deterministic order.

    ``specs`` is sorted by id, which is unique after duplicate rejection.
    ``issues`` follows the sorted file path order; a duplicate is recorded at
    the path that lost.
    """

    specs: tuple[TextureSpec, ...]
    issues: tuple[TextureIssue, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(spec.id for spec in self.specs)

    @property
    def by_id(self) -> dict[str, TextureSpec]:
        return {spec.id: spec for spec in self.specs}

    def get(self, spec_id: str) -> TextureSpec | None:
        return self.by_id.get(spec_id)


def _relative(path: Path, root: Path) -> str:
    """Path shown in logs/issues; never an absolute checkout path."""
    if root.is_file():
        return path.name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _json_paths(root: Path) -> tuple[Path, ...]:
    """Every ``*.json`` below ``root``, sorted by relative POSIX path."""
    if root.is_file():
        return (root,) if root.suffix == ".json" else ()
    if not root.is_dir():
        # The textures directory is optional: absence is an empty registry.
        return ()
    paths = [path for path in root.rglob("*.json") if path.is_file()]
    return tuple(sorted(paths, key=lambda path: _relative(path, root)))


def _issue(path: Path, root: Path, code: str, message: str) -> TextureIssue:
    return TextureIssue(path=_relative(path, root), code=code, message=message)


def _version_issue(spec: TextureSpec) -> tuple[str, str] | None:
    """Apply the registry version gate. Returns ``(code, message)`` or None."""
    provenance = spec.provenance
    if not isinstance(provenance, Mapping):
        return (
            "schema_version",
            f"missing provenance.schema_version (allowed: {sorted(SCHEMA_VERSIONS)})",
        )

    version = provenance.get("schema_version")
    if not isinstance(version, str) or version not in SCHEMA_VERSIONS:
        if version is None:
            detail = "missing"
        else:
            detail = repr(version)
        return (
            "schema_version",
            f"unsupported provenance.schema_version {detail} "
            f"(allowed: {sorted(SCHEMA_VERSIONS)})",
        )

    renderer_version = provenance.get("renderer_version")
    if spec.runtime == "interpreter":
        if not isinstance(renderer_version, str) or not renderer_version.strip():
            return (
                "renderer_version",
                "runtime 'interpreter' requires a non-empty "
                "provenance.renderer_version",
            )
    elif renderer_version is not None and (
        not isinstance(renderer_version, str) or not renderer_version.strip()
    ):
        return (
            "renderer_version",
            "provenance.renderer_version must be a non-empty string when present",
        )
    return None


def _load_one(path: Path, root: Path) -> tuple[TextureSpec | None, TextureIssue | None]:
    """Read, parse, gate, and validate one file without raising."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, _issue(path, root, "read", f"cannot read file: {exc}")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, _issue(path, root, "json", f"invalid JSON: {exc}")

    try:
        spec = parse_texture_spec(payload)
    except TextureSpecError as exc:
        return None, _issue(path, root, "parse", str(exc))

    gate = _version_issue(spec)
    if gate is not None:
        code, message = gate
        return None, _issue(path, root, code, message)

    errors = validate_texture_spec(spec)
    if errors:
        return None, _issue(
            path,
            root,
            "validate",
            "; ".join(str(error) for error in errors),
        )
    return spec, None


def load_report(root: str | Path | None = None) -> TextureLoadResult:
    """Load every published spec under ``root`` and return specs plus skips.

    ``root`` defaults to :data:`TEXTURES_DIR`. A missing directory is an empty
    result, not an error. Each skipped file is logged once at warning level;
    the loaded specs are sorted by id and later duplicate ids are dropped.
    """
    directory = TEXTURES_DIR if root is None else Path(root)
    loaded: list[TextureSpec] = []
    loaded_from: dict[str, str] = {}
    issues: list[TextureIssue] = []

    for path in _json_paths(directory):
        spec, issue = _load_one(path, directory)
        if issue is not None:
            issues.append(issue)
            logger.warning("texture registry: skipping %s", issue)
            continue
        if spec is None:
            # Defensive: fail-soft even if a future reader forgets a return.
            issue = _issue(path, directory, "internal", "loader returned no spec")
            issues.append(issue)
            logger.warning("texture registry: skipping %s", issue)
            continue

        previous = loaded_from.get(spec.id)
        if previous is not None:
            duplicate = _issue(
                path,
                directory,
                "duplicate",
                f"duplicate id {spec.id!r} (already loaded from {previous})",
            )
            issues.append(duplicate)
            logger.warning("texture registry: skipping %s", duplicate)
            continue

        loaded_from[spec.id] = _relative(path, directory)
        loaded.append(spec)

    return TextureLoadResult(
        specs=tuple(sorted(loaded, key=lambda spec: spec.id)),
        issues=tuple(issues),
    )


def load_specs(root: str | Path | None = None) -> tuple[TextureSpec, ...]:
    """Load the published specs under ``root`` (default :data:`TEXTURES_DIR`).

    Fail-soft: malformed JSON, a bad spec, a version-gate failure, or a
    duplicate id is skipped and logged. The returned tuple is sorted by id.
    """
    return load_report(root).specs


def load_textures(root: str | Path | None = None) -> tuple[TextureSpec, ...]:
    """Alias for :func:`load_specs`; the registry's texture-shaped name."""
    return load_specs(root)


@lru_cache(maxsize=1)
def load_default() -> tuple[TextureSpec, ...]:
    """Lazily load the committed :data:`TEXTURES_DIR` once, on first use."""
    return load_specs(TEXTURES_DIR)


def clear_cache() -> None:
    """Forget the cached :func:`load_default` result (tests and dev reloads)."""
    load_default.cache_clear()
