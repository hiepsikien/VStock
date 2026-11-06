"""Bounded Phase 2 interpreter dispatch for authored textures.

This module is deliberately narrow. It resolves a published ``TextureSpec`` for
one pattern through :mod:`app.sonify.texture_registry` and turns its
``authored.events`` into ``NoteEvent`` values bar by bar. It is not a registry, a
compiler, or a generic pattern engine:

* The specs come from the fail-soft registry (``load_default``), not from a
  hardcoded file read. A bounded dispatch table is keyed by the authored
  ``source.render_context.pattern``, the meter signature the live render
  context exposes, and the spec's own excerpt digest. The ``chord_melody``
  renderer asks for its pattern; every other pattern, every missing/failed
  spec, and every context mismatch returns ``None`` so the caller keeps the
  existing code path.
* The digest is part of the dispatch key, so it is per excerpt. A two-bar
  context never borrows a spec authored for a one-bar render and vice versa,
  and two published excerpts with the same pattern and meter stay distinct.
* Pitch resolution goes through :func:`app.studio.texture_resolve.resolve_pitch`
  (via ``authored_to_events``). The spec does not contain absolute MIDI unless
  a tone is genuinely fixture data; the golden fixture records that reason.
* Velocity is *not* owned by the spec. ``velocity_at`` is a caller-supplied
  resolver because the spec contract puts realized velocity in ``derived``
  (see ``docs/sonify-texture-studio.md`` §6.1 and §6.5). When it is omitted the
  events keep ``velocity=None``, which is the authored shape before the host
  renderer derives it.

The flag :data:`INTERPRETER_FLAG` is read on every call and defaults off. The
module never imports ``guitar_patterns``, never registers a spec, and never
mutates ``SENTENCE_SPECS``. Importing it is inert: the registry reads no files
until the first flagged render. A missing, malformed, or registry-skipped spec
degrades to ``None``; it never raises into a render or boot path.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from app.sonify import texture_registry
from app.sonify.model import NoteEvent
from app.studio.texture_spec import (
    MeterSpec,
    TextureError,
    TextureSpec,
    TextureSpecError,
    parse_texture_spec,
    validate_texture_spec,
)
from app.studio.texture_resolve import (
    TextureResolveError,
    authored_to_events,
)

__all__ = [
    "INTERPRETER_FLAG",
    "INTERPRETER_PATTERN",
    "SPEC_ID",
    "SPEC_PATH",
    "SPEC_ROOT",
    "Interpretation",
    "TextureInterpreterError",
    "context_digest",
    "dispatch_key",
    "dispatch_spec",
    "excerpt_key",
    "interpreter_enabled",
    "load_spec",
    "render_chord_melody_bar",
    "reset_spec_cache",
    "use_texture_interpreter",
]

logger = logging.getLogger(__name__)

INTERPRETER_FLAG = "VSTOCK_TEXTURE_INTERPRETER"
INTERPRETER_PATTERN = "chord_melody"
#: The default file for the direct-file test seam (``load_spec``). Runtime
#: dispatch never compares against this id; it comes from the registry table.
SPEC_ID = "chord_melody_phase2"
# The committed file is only the direct-file test seam (``load_spec``); runtime
# resolution goes through the registry's scan of the published directory.
SPEC_PATH = Path(__file__).with_name("textures") / f"{SPEC_ID}.json"
#: Registry root. ``None`` means the registry's own committed ``TEXTURES_DIR``.
#: Tests override it to point at a temporary published directory.
SPEC_ROOT: Path | None = None
_TRUE = frozenset({"1", "true", "yes", "on"})

VelocityResolver = Callable[[NoteEvent, set[int]], int | None]

#: Meter fields the live render context exposes. ``strong_eighths`` keeps 3/4
#: and 6/8 apart even though both have six eighths and three quarter beats.
MeterKey = tuple[int, float, tuple[int, ...]]
#: ``(pattern, meter, excerpt digest)``. The digest is in the key so a spec
#: never applies outside the excerpt it was authored for.
DispatchKey = tuple[str, MeterKey, str]

_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "texture_interpreter_enabled", default=None
)


class TextureInterpreterError(ValueError):
    """The interpreter spec is missing, malformed, or does not fit the context."""


@dataclass(frozen=True)
class Interpretation:
    """One registry spec matched to a live render context."""

    spec: TextureSpec
    meter: MeterSpec
    pattern: str
    digest: str


def interpreter_enabled() -> bool:
    """The flag, with a ContextVar override for tests and auditions."""
    override = _OVERRIDE.get()
    if override is not None:
        return override
    raw = os.environ.get(INTERPRETER_FLAG)
    if raw is None:
        return False
    return raw.strip().lower() in _TRUE


@contextmanager
def use_texture_interpreter(enabled: bool = True) -> Iterator[None]:
    """Enable/disable the flag without touching the process environment."""
    token = _OVERRIDE.set(bool(enabled))
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------


def load_spec(
    path: Path | str | None = None,
    *,
    pattern: str | None = INTERPRETER_PATTERN,
) -> TextureSpec:
    """Parse and fully validate one spec file directly.

    This is the file-based test seam: it bypasses the registry so a test can
    point at a fixture on ``tmp_path`` and fail loudly. Runtime callers use
    :func:`dispatch_spec`, which goes through the fail-soft registry.
    """
    target = Path(path) if path is not None else SPEC_PATH
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TextureInterpreterError(f"cannot read {target}: {exc}") from exc
    except JSONDecodeError as exc:
        raise TextureInterpreterError(f"{target}: invalid JSON: {exc}") from exc

    try:
        spec = parse_texture_spec(raw)
    except TextureSpecError as exc:
        raise TextureInterpreterError(str(exc)) from exc

    return _validated_spec(spec, source=str(target), expected_pattern=pattern)


def _validated_spec(
    spec: TextureSpec,
    *,
    source: str,
    meter: MeterSpec | None = None,
    expected_pattern: str | None = None,
) -> TextureSpec:
    """The interpreter's own checks on an already-parsed spec.

    The registry applies the parse, version, and general offline validation
    gates. These checks are stricter and specific to this proof: it must be an
    ``interpreter`` spec, declare its excerpt pattern and digest, and validate
    every authored bar as a full bar in the meter being dispatched.
    """
    if spec.runtime != "interpreter":
        raise TextureInterpreterError(
            f"{spec.id}: runtime is {spec.runtime!r}, expected 'interpreter'"
        )
    declared = _declared_context(spec)
    if declared is None:
        raise TextureInterpreterError(
            f"{spec.id}: source.render_context must declare a pattern and digest"
        )
    if expected_pattern is not None and declared["pattern"] != expected_pattern:
        raise TextureInterpreterError(
            f"{source}: spec pattern is {declared['pattern']!r}, "
            f"expected {expected_pattern!r}"
        )
    if not spec.meter_variants:
        raise TextureInterpreterError(f"{spec.id}: missing meter variant")

    target = meter if meter is not None else spec.meter_variants[0].meter
    if not isinstance(target, MeterSpec):
        raise TextureInterpreterError(f"{spec.id}: meter is not a MeterSpec")

    errors = validate_texture_spec(spec, meter=target, require_full_bars=True)
    if errors:
        raise TextureInterpreterError(_format_errors(errors))
    return spec


def _published_specs() -> tuple[TextureSpec, ...]:
    """The registry's specs, from the default directory or a test override."""
    if SPEC_ROOT is None:
        return texture_registry.load_default()
    return texture_registry.load_specs(SPEC_ROOT)


def reset_spec_cache() -> None:
    """Forget cached registry results. Tests call this after changing files."""
    texture_registry.clear_cache()


def _format_errors(errors: Sequence[TextureError]) -> str:
    return "; ".join(str(error) for error in errors)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def excerpt_key(spec: TextureSpec) -> tuple[str, str] | None:
    """The per-excerpt identity of one published spec.

    A spec is addressed by its own id and its authored context digest. There is
    no single module-wide excerpt constant: two specs may share a pattern and
    meter while applying to different excerpts.
    """
    declared = _declared_context(spec)
    if declared is None:
        return None
    return (spec.id, declared["digest"])


def _meter_key(meter: MeterSpec) -> MeterKey:
    return (
        int(meter.eighths_per_bar),
        round(float(meter.quarter_beats), 6),
        tuple(int(value) for value in meter.strong_eighths),
    )


def _context_meter_key(ctx: Any) -> MeterKey:
    return (
        int(getattr(ctx, "epb", 0) or 0),
        round(float(getattr(ctx, "bar_beats", 0.0) or 0.0), 6),
        tuple(int(value) for value in tuple(getattr(ctx, "strong", ()) or ())),
    )


def dispatch_key(pattern: str, ctx: Any) -> DispatchKey:
    """The bounded dispatch key: pattern + meter signature + excerpt digest."""
    return (str(pattern), _context_meter_key(ctx), context_digest(ctx))


def _dispatch_table(
    specs: Sequence[TextureSpec],
) -> dict[DispatchKey, tuple[Interpretation, ...]]:
    """Index interpreter specs by pattern, meter, and authored digest.

    Later duplicate entries with the same key stay in registration order; the
    registry already sorts by id and drops duplicate ids.
    """
    table: dict[DispatchKey, list[Interpretation]] = {}
    for spec in specs:
        if spec.runtime != "interpreter":
            continue
        declared = _declared_context(spec)
        if declared is None:
            continue
        pattern = declared["pattern"]
        digest = declared["digest"]
        for variant in spec.meter_variants:
            meter = variant.meter
            if not isinstance(meter, MeterSpec):
                continue
            key = (pattern, _meter_key(meter), digest)
            table.setdefault(key, []).append(
                Interpretation(
                    spec=spec,
                    meter=meter,
                    pattern=pattern,
                    digest=digest,
                )
            )
    return {key: tuple(candidates) for key, candidates in table.items()}


def dispatch_spec(pattern: str, ctx: Any) -> Interpretation | None:
    """The first valid registry spec for ``pattern`` and this exact excerpt.

    Fail-soft mirrors the registry contract in ``docs/sonify-texture-studio.md``
    §7.2: a broken, skipped, or invalid spec must not stop a render or boot.
    Unknown patterns, an unavailable registry, and a context mismatch all
    return ``None`` so the caller keeps the code renderer.
    """
    if not isinstance(pattern, str) or not pattern:
        return None
    try:
        specs = _published_specs()
    except Exception:  # noqa: BLE001 - the render boundary must never raise
        logger.warning("texture interpreter: registry unavailable", exc_info=True)
        return None

    try:
        key = dispatch_key(pattern, ctx)
        candidates = _dispatch_table(specs).get(key, ())
    except Exception:  # noqa: BLE001 - the render boundary must never raise
        logger.warning(
            "texture interpreter: cannot build the dispatch table", exc_info=True
        )
        return None

    for candidate in candidates:
        try:
            _validated_spec(
                candidate.spec,
                source="texture registry",
                meter=candidate.meter,
            )
        except Exception:  # noqa: BLE001 - the render boundary must never raise
            logger.warning(
                "texture interpreter: ignoring spec %s",
                candidate.spec.id,
                exc_info=True,
            )
            continue
        return candidate
    return None


# ---------------------------------------------------------------------------
# Render-context digest
# ---------------------------------------------------------------------------


def context_digest(ctx: Any) -> str:
    """A stable digest of the fields this pattern actually reads.

    The proof spec is authored for one deterministic excerpt, so it must not be
    applied to a different melody, chord, phrase, band, or meter. The digest is
    the explicit context contract from §6.8: ``melody_eighth`` needs the same
    pipeline context, not a standalone spec. Fields the chord-melody bar writer
    never reads (registers, key, price) stay out so a preview built with the
    same bar data still matches.
    """
    payload = {
        "epb": int(getattr(ctx, "epb", 0) or 0),
        "kind": str(getattr(ctx, "kind", "") or ""),
        "bars": int(getattr(ctx, "bars", 0) or 0),
        "bar_beats": float(getattr(ctx, "bar_beats", 0) or 0),
        "strong": [int(value) for value in tuple(getattr(ctx, "strong", ()) or ())],
        "melody": [int(value) for value in list(getattr(ctx, "melody", ()) or ())],
        "raw": [int(value) for value in list(getattr(ctx, "raw", ()) or ())],
        "bpm": int(getattr(ctx, "bpm", 0) or 0),
        "ensemble": str(getattr(ctx, "ensemble", "") or ""),
        "mode": str(getattr(ctx, "mode", "") or ""),
        "character": getattr(ctx, "character", None),
        "rel_span": float(getattr(ctx, "rel_span", 0.0) or 0.0),
        "phrases": [_phrase_snapshot(phrase) for phrase in tuple(getattr(ctx, "phrases", ()) or ())],
        "bands": _sorted_mapping(getattr(ctx, "band_at", None)),
        "kinds": _sorted_mapping(getattr(ctx, "kind_at", None)),
        "characters": _sorted_mapping(getattr(ctx, "character_at", None)),
        "chords": _chord_snapshot(ctx),
        "sections": [_section_snapshot(section) for section in tuple(getattr(ctx, "sections", ()) or ())],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _phrase_snapshot(phrase: Any) -> dict[str, Any]:
    runs = []
    for run in tuple(getattr(phrase, "runs", ()) or ()):
        runs.append(
            [
                int(getattr(run, "start", 0)),
                int(getattr(run, "length", 0)),
                int(getattr(run, "midi", 0)),
            ]
        )
    return {
        "start": int(getattr(phrase, "start", 0)),
        "end": int(getattr(phrase, "end", 0)),
        "runs": runs,
        "closes": bool(getattr(phrase, "closes", False)),
        "held_over": bool(getattr(phrase, "held_over", False)),
    }


def _section_snapshot(section: Any) -> dict[str, Any]:
    return {
        "start": int(getattr(section, "start", 0)),
        "end": int(getattr(section, "end", 0)),
        "kind": str(getattr(section, "kind", "") or ""),
        "index": int(getattr(section, "index", 0) or 0),
    }


def _sorted_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): value[key] for key in sorted(value, key=lambda item: str(item))}


def _chord_snapshot(ctx: Any) -> dict[str, Any]:
    """Only the bars the pattern can touch: every bar in the context."""
    bars = int(getattr(ctx, "bars", 0) or 0)
    found: dict[str, Any] = {}
    for bar in range(bars):
        chord = None
        method = getattr(ctx, "chord", None)
        if callable(method):
            try:
                chord = method(bar)
            except (KeyError, IndexError, TypeError, ValueError):
                chord = None
        if chord is None:
            mapping = getattr(ctx, "chord_at", None)
            if isinstance(mapping, Mapping):
                chord = mapping.get(bar)
        if chord is None:
            continue
        found[str(bar)] = {
            "name": str(getattr(chord, "name", "") or ""),
            "pitches": [int(pitch) for pitch in tuple(getattr(chord, "pitches", ()) or ())],
        }
    return found


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------


def _declared_context(spec: TextureSpec) -> Mapping[str, Any] | None:
    """The authored render-context mapping, when it declares pattern + digest."""
    source = spec.source
    if not isinstance(source, Mapping):
        return None
    declared = source.get("render_context")
    if not isinstance(declared, Mapping):
        return None
    pattern = declared.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return None
    digest = declared.get("digest")
    if not isinstance(digest, str) or not digest:
        return None
    return declared


def _events_for_bar(spec: TextureSpec, bar: int) -> tuple[Any, ...]:
    return tuple(event for event in spec.authored if event.bar == bar)


def render_chord_melody_bar(
    ctx: Any,
    bar: int,
    phrase: Any = None,
    *,
    velocity_at: VelocityResolver | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]] | None:
    """Interpret one ``chord_melody`` bar from a matching published spec.

    Bars are resolved independently from the same authored excerpt. Returns
    ``(lead, support, low)`` exactly when the flag is on, a spec for the
    ``chord_melody`` pattern at this meter and excerpt resolves, and its
    authored events validate. Any other case returns ``None``; the caller must
    keep the code renderer.
    """
    if not interpreter_enabled():
        return None
    match = dispatch_spec(INTERPRETER_PATTERN, ctx)
    if match is None:
        return None

    events = _events_for_bar(match.spec, bar)
    if not events:
        return None
    if any(event.voice not in (1, 2, 3) for event in events):
        return None

    try:
        notes = authored_to_events(events, ctx, match.meter)
    except TextureResolveError:
        return None

    epb = int(getattr(ctx, "epb", 0) or 0)
    breaks = {
        bar * epb + int(round(float(event.beat) * 2))
        for event in events
        if event.voice in (2, 3)
    }
    if velocity_at is not None:
        notes = [
            replace(note, velocity=velocity_at(note, breaks))
            for note in notes
        ]

    lead = [note for note in notes if note.voice == 1]
    support = [note for note in notes if note.voice == 2]
    low = [note for note in notes if note.voice == 3]
    return lead, support, low
