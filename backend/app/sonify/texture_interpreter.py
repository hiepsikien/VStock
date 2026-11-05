"""Bounded Phase 2 interpreter proof for one authored bar texture.

This module is deliberately narrow. It reads one committed ``TextureSpec`` for
``chord_melody`` and turns its ``authored.events`` into ``NoteEvent`` values for
the same bar. It is not a registry, a compiler, or a generic pattern engine:

* Only the spec whose id is :data:`SPEC_ID`, whose ``runtime`` is
  ``"interpreter"``, and whose authored render-context digest matches the live
  ``_Ctx`` is used. Everything else returns ``None`` so the caller keeps the
  existing code path.
* Pitch resolution goes through :func:`app.studio.texture_resolve.resolve_pitch`
  (via ``authored_to_events``). The spec does not contain absolute MIDI unless
  a tone is genuinely fixture data; the golden fixture records that reason.
* Velocity is *not* owned by the spec. ``velocity_at`` is a caller-supplied
  resolver because the spec contract puts realized velocity in ``derived``
  (see ``docs/sonify-texture-studio.md`` §6.1 and §6.5). When it is omitted the
  events keep ``velocity=None``, which is the authored shape before the host
  renderer derives it.

The flag :data:`INTERPRETER_FLAG` is read on every call and defaults off. The
module never imports ``guitar_patterns`` and never mutates ``SENTENCE_SPECS``.
Importing it is inert: the spec is loaded lazily from a file.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from json import JSONDecodeError
from pathlib import Path
from typing import Any

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
    "TextureInterpreterError",
    "context_digest",
    "interpreter_enabled",
    "load_spec",
    "render_chord_melody_bar",
    "reset_spec_cache",
    "runtime_spec",
    "use_texture_interpreter",
]

INTERPRETER_FLAG = "VSTOCK_TEXTURE_INTERPRETER"
INTERPRETER_PATTERN = "chord_melody"
SPEC_ID = "chord_melody_phase2"
SPEC_PATH = Path(__file__).with_name("textures") / f"{SPEC_ID}.json"
_TRUE = frozenset({"1", "true", "yes", "on"})

VelocityResolver = Callable[[NoteEvent, set[int]], int | None]

_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "texture_interpreter_enabled", default=None
)
_SPEC_CACHE: TextureSpec | None = None
_SPEC_LOADED = False


class TextureInterpreterError(ValueError):
    """The interpreter spec is missing, malformed, or does not fit the context."""


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


def load_spec(path: Path | str | None = None) -> TextureSpec:
    """Parse and fully validate the committed proof spec.

    Raises :class:`TextureInterpreterError` so tests can fail loudly. Runtime
    callers use :func:`runtime_spec`, which is fail-soft.
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

    if spec.runtime != "interpreter":
        raise TextureInterpreterError(
            f"{spec.id}: runtime is {spec.runtime!r}, expected 'interpreter'"
        )
    if spec.id != SPEC_ID:
        raise TextureInterpreterError(f"{target}: spec id is {spec.id!r}")
    if not spec.meter_variants:
        raise TextureInterpreterError(f"{spec.id}: missing meter variant")

    errors = validate_texture_spec(
        spec,
        meter=spec.meter_variants[0].meter,
        require_full_bars=True,
    )
    if errors:
        raise TextureInterpreterError(_format_errors(errors))
    return spec


def runtime_spec() -> TextureSpec | None:
    """The cached spec, or ``None`` when it is missing/invalid.

    Fail-soft mirrors the registry contract in ``docs/sonify-texture-studio.md``
    §7.2: a broken proof spec must not stop a render. The caller falls back to
    the code renderer.
    """
    global _SPEC_CACHE, _SPEC_LOADED
    if not _SPEC_LOADED:
        _SPEC_LOADED = True
        try:
            _SPEC_CACHE = load_spec()
        except TextureInterpreterError:
            _SPEC_CACHE = None
    return _SPEC_CACHE


def reset_spec_cache() -> None:
    """Drop the cache. Tests use this after changing the committed file."""
    global _SPEC_CACHE, _SPEC_LOADED
    _SPEC_CACHE = None
    _SPEC_LOADED = False


def _format_errors(errors: Sequence[TextureError]) -> str:
    return "; ".join(str(error) for error in errors)


# ---------------------------------------------------------------------------
# Render-context digest
# ---------------------------------------------------------------------------


def context_digest(ctx: Any) -> str:
    """A stable digest of the fields this one pattern actually reads.

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


def _spec_matches(spec: TextureSpec, ctx: Any) -> bool:
    if spec.runtime != "interpreter" or spec.id != SPEC_ID:
        return False
    if not spec.meter_variants:
        return False
    meter = spec.meter_variants[0].meter
    if not isinstance(meter, MeterSpec):
        return False
    if meter.eighths_per_bar != int(getattr(ctx, "epb", 0) or 0):
        return False
    if meter.quarter_beats != float(getattr(ctx, "bar_beats", 0) or 0):
        return False
    source = spec.source
    if not isinstance(source, Mapping):
        return False
    declared = source.get("render_context")
    if not isinstance(declared, Mapping):
        return False
    return declared.get("digest") == context_digest(ctx)


def _events_for_bar(spec: TextureSpec, bar: int) -> tuple[Any, ...]:
    return tuple(event for event in spec.authored if event.bar == bar)


def render_chord_melody_bar(
    ctx: Any,
    bar: int,
    phrase: Any = None,
    *,
    velocity_at: VelocityResolver | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]] | None:
    """Interpret one ``chord_melody`` bar from the committed spec.

    Returns ``(lead, support, low)`` exactly when the flag is on, the spec is
    valid, and its authored render-context digest matches ``ctx``. Any other
    case returns ``None``; the caller must keep the code renderer.
    """
    if not interpreter_enabled():
        return None
    spec = runtime_spec()
    if spec is None:
        return None
    if not _spec_matches(spec, ctx):
        return None

    events = _events_for_bar(spec, bar)
    if not events:
        return None
    if any(event.voice not in (1, 2, 3) for event in events):
        return None

    meter = spec.meter_variants[0].meter
    try:
        notes = authored_to_events(events, ctx, meter)
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
