"""Render one Studio Piece from tagged figures, a plan, and a 1D bar series.

This is Phase C1/C2 (``docs/studio-render-piece-plan.md`` §4, §13 W1/W4/W5/W9):
MusicXML is stored by content hash and the result reports whether a production
WAV already exists. The async export itself lives in
:mod:`app.studio.render_jobs`; the service never blocks on MuseScore.

The service layer is pure with respect to the registries. It validates the
figure pool through :func:`app.sonify.pattern_promote.promote_figures` (the
same five-tag gate as an explicit promote) but never calls ``apply_promotion``.
The render itself goes through the Phase A ``studio_piece`` seam, so
``TEXTURE_CELLS``, ``SENTENCE_SPECS`` and ``STUDIO_DOORS`` stay untouched.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import Any

from app.sonify.form import (
    METER_14,
    METER_24,
    METER_34,
    METER_44,
    METER_54,
    METER_64,
    METER_68,
    METER_78,
    METER_128,
    FormSection,
    FormSpec,
    Meter,
)
from app.sonify.model import Bar, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.params import active_params, params_hash
from app.sonify.pattern_figures import PatternFigure
from app.sonify.pattern_promote import PromotionPlan, promote_figures
from app.sonify.render import render
from app.sonify.span import plan_month, plan_week
from app.sonify.studio_arrangement import ArrangementResult, build_arrangement
from app.studio import render_audio, render_store
from app.studio.texture_resolve import check_authored_playable
from app.studio.texture_spec import (
    AuthoredEvent,
    PitchRef,
    TextureSpec,
    texture_spec_to_mapping,
    validate_texture_spec,
)

__all__ = [
    "STUDIO_RENDER_REVISION",
    "RenderError",
    "RenderPieceError",
    "RenderPieceRequest",
    "RenderPieceResult",
    "SUPPORTED_RENDER_SPANS",
    "SUPPORTED_METERS",
    "meter_from_name",
    "render_piece",
]

#: Bump when rendered notes or the hash payload change. W4 requires it in the
#: content hash so old cache entries cannot survive a renderer change.
STUDIO_RENDER_REVISION = 4

SUPPORTED_RENDER_SPANS = ("1W", "1M")
SUPPORTED_PLAN_IDS = ("auto_aaba", "trio")

_METERS: dict[str, Meter] = {
    "1/4": METER_14,
    "2/4": METER_24,
    "3/4": METER_34,
    "4/4": METER_44,
    "5/4": METER_54,
    "6/4": METER_64,
    "6/8": METER_68,
    "7/8": METER_78,
    "12/8": METER_128,
}
SUPPORTED_METERS = tuple(_METERS)

_MAX_SERIES_BARS = 4096
_MAX_FIGURES = 128


@dataclass(frozen=True)
class RenderError:
    path: str
    message: str


class RenderPieceError(ValueError):
    """A structural Render Piece request error with path-shaped records."""

    def __init__(self, errors: Sequence[RenderError]) -> None:
        self.errors = tuple(errors)
        message = "; ".join(
            f"{error.path}: {error.message}" if error.path else error.message
            for error in self.errors
        )
        super().__init__(message or "invalid render request")


@dataclass(frozen=True)
class RenderPieceRequest:
    """Everything one Render Piece call needs.

    ``figures`` pairs each tagged figure with the authored texture the caller
    wants rendered. The pairs are mandatory here: the service never reads
    ``TEXTURE_CELLS``. ``bars`` is the already-resolved 1D series; symbol/date
    loading is a transport concern and happens before this request is built.
    """

    pattern: str
    meter: str
    figures: tuple[tuple[PatternFigure, TextureSpec], ...]
    plan: str = "auto_aaba"
    bars: tuple[Bar, ...] = field(default_factory=tuple)
    span: str = "1W"
    movement_index: int | None = None
    title: str | None = None
    include_doors: bool = True
    # Optional namespace metadata only; it never changes the content hash.
    session: str = "anonymous"


@dataclass(frozen=True)
class RenderPieceResult:
    render_hash: str
    musicxml: str
    meter: str
    bars: int
    notes: int
    plan: str
    warnings: tuple[str, ...]
    audio_status: str = "unavailable"
    audio_hash: str | None = None
    audio_job_id: str | None = None
    audio_errors: tuple[RenderError, ...] = ()
    title: str = ""
    span: str = "1W"
    movement_index: int | None = None
    cached: bool = False

    @property
    def musicxml_url(self) -> str:
        digest = render_store.normalize_hash(self.render_hash) or self.render_hash
        return f"/v1/studio/figure/render/{digest}.musicxml"

    @property
    def audio_url(self) -> str | None:
        digest = render_store.normalize_hash(self.audio_hash or "")
        return f"/v1/studio/figure/render/{digest}.wav" if digest else None


def meter_from_name(name: str) -> Meter:
    """Resolve a display meter such as ``"2/4"`` to the runtime ``Meter``."""
    if not isinstance(name, str) or not name.strip():
        raise RenderPieceError(
            [RenderError("meter", "meter must be a non-empty string")]
        )
    meter = _METERS.get(name.strip())
    if meter is None:
        raise RenderPieceError(
            [
                RenderError(
                    "meter",
                    f"unsupported meter {name!r}; expected one of "
                    f"{', '.join(SUPPORTED_METERS)}",
                )
            ]
        )
    return meter


def _non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RenderPieceError(
            [RenderError(path, "must be a non-empty string")]
        )
    return value.strip()


def _resolve_form(
    span: str,
    meter: Meter,
    movement_index: int | None,
) -> tuple[FormSpec, int]:
    """Return the MVP form for a span and the resolved movement index."""
    if span == "1W":
        spec = plan_week(1, variant="guitar", ensemble="villa")[0].spec
        index = 0
    elif span == "1M":
        index = 2 if movement_index is None else movement_index
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 4:
            raise RenderPieceError(
                [
                    RenderError(
                        "form.movementIndex",
                        "movementIndex must be an integer in 0..3 for span 1M",
                    )
                ]
            )
        # ``plan_month`` already applies ``attach_frame("1M")`` to body specs.
        spec = plan_month(
            [1, 1, 1, 1], variant="guitar", ensemble="villa"
        )[index].spec
    elif span == "3M":
        raise RenderPieceError(
            [
                RenderError(
                    "form.span",
                    "span '3M' is not implemented for Studio Piece; use '1W' or '1M'",
                )
            ]
        )
    else:
        raise RenderPieceError(
            [
                RenderError(
                    "form.span",
                    f"unknown form span {span!r}; expected '1W' or '1M'",
                )
            ]
        )
    # A Studio Piece owns its meter. Never depend on the Schottish flag or on
    # which movement the suite planner happened to choose.
    return FormSpec(
        bars=spec.bars,
        bpm=spec.bpm,
        sections=spec.sections,
        chunks=spec.chunks,
        borrowed=spec.borrowed,
        meter=meter,
    ), index


def _body_only(form: FormSpec) -> FormSpec:
    """Drop the frame doors and rebase the remaining phrases to bar 0."""
    body = [
        section
        for section in form.sections
        if section.kind not in ("intro", "warmup", "outro", "cooldown")
    ]
    if not body:
        raise RenderPieceError(
            [RenderError("form", "the selected form has no body sections")]
        )
    shift = int(body[0].start)
    sections = tuple(
        FormSection(
            int(section.start) - shift,
            int(section.end) - shift,
            section.kind,
            section.regime_slot,
            section.bridge,
            section.trio,
        )
        for section in body
    )
    return FormSpec(
        bars=sections[-1].end,
        bpm=form.bpm,
        sections=sections,
        chunks=(),
        borrowed=form.borrowed,
        meter=form.meter,
    )


def _validate_series(bars: Sequence[Bar], form: FormSpec) -> None:
    if not isinstance(bars, Sequence) or isinstance(bars, (str, bytes)):
        raise RenderPieceError([RenderError("series.bars", "must be a list")])
    if not bars:
        raise RenderPieceError(
            [RenderError("series.bars", "series must contain at least one bar")]
        )
    if len(bars) > _MAX_SERIES_BARS:
        raise RenderPieceError(
            [
                RenderError(
                    "series.bars",
                    f"too many bars: {len(bars)} > {_MAX_SERIES_BARS}",
                )
            ]
        )
    errors: list[RenderError] = []
    for index, bar in enumerate(bars):
        close = getattr(bar, "close", None)
        volume = getattr(bar, "volume", 0.0)
        if (
            isinstance(close, bool)
            or not isinstance(close, (int, float))
            or not math.isfinite(float(close))
        ):
            errors.append(
                RenderError(
                    f"series.bars[{index}].close",
                    "close must be a finite number",
                )
            )
        if (
            isinstance(volume, bool)
            or not isinstance(volume, (int, float))
            or not math.isfinite(float(volume))
            or float(volume) < 0
        ):
            errors.append(
                RenderError(
                    f"series.bars[{index}].volume",
                    "volume must be a finite number >= 0",
                )
            )
    if errors:
        raise RenderPieceError(errors)
    if len(bars) < form.bars:
        raise RenderPieceError(
            [
                RenderError(
                    "series.bars",
                    f"series has {len(bars)} bars; form {form.bars} needs at least "
                    f"{form.bars} (no repeat/truncate)",
                )
            ]
        )


def _playability_context(meter: Meter) -> Any:
    """A neutral guitar register for offline playability.

    The authored pitch kinds are resolved exactly like the renderer's default
    C-major chord. ``melody_eighth`` cannot be exact without the real price
    melody, but the range/voice/tab checks still use this deterministic context
    and the actual render remains the final authority.
    """
    return SimpleNamespace(
        melody=tuple([60] * 8192),
        raw=tuple([60] * 8192),
        chord_at={},
        mode="major",
        treble_floor=59,
        treble_top=81,
        bass_low=40,
        bass_high=53,
        mid_low=50,
        mid_high=65,
        ceiling=83,
        epb=meter.eighths_per_bar,
        bar_beats=meter.quarter_beats,
    )


def _production_roles(
    texture: TextureSpec,
) -> dict[int, tuple[str, int]]:
    """Assign lead/bass/mid by pitch at each onset, not by source voice.

    MusicXML voice numbers are not role ids: in the Villa passage the actual
    bass is voice 2 and the middle line is voice 3. Mirror the UI's
    ``buildRoleLanes`` instead: voice 1 is lead, the lowest non-lead note is
    bass, and the remaining non-lead notes are mid from low to high.
    """
    groups: dict[tuple[int, float], list[int]] = {}
    for index, event in enumerate(texture.authored):
        if event.pitch.kind != "literal_midi":
            continue
        key = (event.bar, round(float(event.beat), 9))
        groups.setdefault(key, []).append(index)

    roles: dict[int, tuple[str, int]] = {}
    for indices in groups.values():
        lead = [
            index
            for index in indices
            if int(texture.authored[index].voice) == 1
        ]
        non_lead = [index for index in indices if index not in lead]
        if not lead and non_lead:
            # No voice 1 in this source: the highest note still carries the
            # line, matching the matrix's lead row.
            highest = max(
                non_lead,
                key=lambda index: int(texture.authored[index].pitch.value or 0),
            )
            lead = [highest]
            non_lead = [index for index in non_lead if index != highest]
        for index in lead:
            roles[index] = ("lead", 0)
        ordered = sorted(
            non_lead,
            key=lambda index: (
                int(texture.authored[index].pitch.value or 0),
                int(texture.authored[index].voice),
            ),
        )
        if ordered:
            roles[ordered[0]] = ("bass", 0)
        for rank, index in enumerate(ordered[1:]):
            roles[index] = ("mid", rank)
    return roles


def _bind_production_pitches(
    pairs: Sequence[tuple[PatternFigure, TextureSpec]],
    epb: int,
) -> tuple[tuple[tuple[PatternFigure, TextureSpec], ...], tuple[str, ...]]:
    """Replace MusicXML literal pitches with production references.

    Lead follows the target price melody. The lowest non-lead note becomes the
    bass root, and the remaining non-lead notes become middle chord tones.
    Role is decided by pitch order at each onset, because the source voice
    number is not a role id. The rhythm/duration/notation metadata is kept;
    only pitch is rewritten, and the renderer assigns the final role by pitch.
    """
    bound: list[tuple[PatternFigure, TextureSpec]] = []
    changed = False
    for figure, texture in pairs:
        roles = _production_roles(texture)
        events: list[AuthoredEvent] = []
        texture_changed = False
        for index, event in enumerate(texture.authored):
            role = roles.get(index)
            if event.pitch.kind != "literal_midi" or role is None:
                events.append(event)
                continue
            kind, rank = role
            if kind == "lead":
                # render_texture_bar reindexes the selected cell bar to 0 and
                # adds target_bar * epb in bind_texture. Include only the
                # beat offset here; adding event.bar would double-count the
                # cell bar and overflow the target melody.
                pitch = PitchRef.melody_eighth(int(round(event.beat * 2)), 0)
            elif kind == "bass":
                pitch = PitchRef.chord_bass()
            else:
                pitch = PitchRef.chord_mid(2 + rank)
            # Keep the source voice number. Rewriting it can make two
            # different source voices collide in one role voice and trip the
            # monophonic authored validator. ``render_texture_bar`` assigns
            # the final role by pitch at render time.
            events.append(replace(event, pitch=pitch))
            texture_changed = True
        if texture_changed:
            changed = True
            texture = replace(texture, authored=tuple(events))
        bound.append((figure, texture))
    warnings: tuple[str, ...] = ()
    if changed:
        warnings = (
            "MusicXML literal pitches were rebound to the price/chord context "
            "and role voices by pitch order for production preview",
        )
    return tuple(bound), warnings


def _fold_literal_pitches(
    pairs: Sequence[tuple[PatternFigure, TextureSpec]],
) -> tuple[tuple[tuple[PatternFigure, TextureSpec], ...], tuple[str, ...]]:
    """Fold absolute MIDI outside the neutral guitar range by octaves.

    Render Piece normally rebinds every literal before this runs, so this is a
    defensive fallback for a literal that was not rebound (for example a future
    pitch kind that deliberately preserves authored MIDI). Preview/export must
    accept the passages Studio itself imports; production promotion keeps the
    strict 40..83 check.
    """
    folded: list[tuple[PatternFigure, TextureSpec]] = []
    changed_cells: list[str] = []
    for figure, texture in pairs:
        events = []
        changed = False
        for event in texture.authored:
            value = event.pitch.value
            if event.pitch.kind == "literal_midi" and isinstance(value, int):
                target = value
                while target > 83:
                    target -= 12
                while target < 40:
                    target += 12
                if target != value:
                    event = replace(
                        event,
                        pitch=replace(event.pitch, value=target),
                    )
                    changed = True
            events.append(event)
        if changed:
            changed_cells.append(figure.cell_id)
            texture = replace(texture, authored=tuple(events))
        folded.append((figure, texture))
    warnings = ()
    if changed_cells:
        warnings = (
            "out-of-range literal MIDI was folded into guitar range 40..83 "
            f"for preview ({', '.join(sorted(set(changed_cells)))})",
        )
    return tuple(folded), warnings


def _validate_figures(
    request: RenderPieceRequest,
    meter: Meter,
) -> tuple[PromotionPlan, tuple[str, ...]]:
    if not isinstance(request.figures, Sequence) or isinstance(
        request.figures, (str, bytes)
    ):
        raise RenderPieceError(
            [RenderError("figures", "figures must be a list")]
        )
    if not request.figures:
        raise RenderPieceError(
            [RenderError("figures", "figures must contain at least one figure")]
        )
    if len(request.figures) > _MAX_FIGURES:
        raise RenderPieceError(
            [
                RenderError(
                    "figures",
                    f"too many figures: {len(request.figures)} > {_MAX_FIGURES}",
                )
            ]
        )

    errors: list[RenderError] = []
    pairs: list[tuple[PatternFigure, TextureSpec]] = []
    index_by_cell: dict[str, int] = {}
    for index, pair in enumerate(request.figures):
        if (
            not isinstance(pair, (tuple, list))
            or len(pair) != 2
            or not isinstance(pair[0], PatternFigure)
            or not isinstance(pair[1], TextureSpec)
        ):
            errors.append(
                RenderError(
                    f"figures[{index}]",
                    "expected a (PatternFigure, TextureSpec) pair",
                )
            )
            continue
        figure, texture = pair
        index_by_cell.setdefault(figure.cell_id, index)
        pairs.append((figure, texture))
    if errors:
        raise RenderPieceError(errors)

    pairs, folded_warnings = _fold_literal_pitches(pairs)
    plan: PromotionPlan | None = None
    try:
        plan = promote_figures(
            request.pattern,
            request.meter,
            pairs,
            allow_literal=True,
        )
    except ValueError as exc:
        errors.append(RenderError("figures", str(exc)))

    # Validate every distinct authored cell once. The meter comes from the
    # request, not from a texture's declared variant list.
    seen_cells: set[str] = set()
    playability_ctx = _playability_context(meter)
    warnings: list[str] = list(folded_warnings)
    if any(
        event.pitch.kind == "literal_midi"
        for _figure, texture in pairs
        for event in texture.authored
    ):
        warnings.append(
            "literal_midi is preview-only; production promote still requires "
            "a relative PitchRef"
        )
    for index, (figure, texture) in enumerate(pairs):
        if figure.cell_id in seen_cells:
            continue
        seen_cells.add(figure.cell_id)
        prefix = f"figures[{index_by_cell.get(figure.cell_id, index)}].spec"
        for problem in validate_texture_spec(texture, meter=meter):
            errors.append(
                RenderError(f"{prefix}.{problem.path}" if problem.path else prefix, problem.message)
            )
        for problem in check_authored_playable(texture, playability_ctx, meter):
            if (
                problem.path.endswith(".voice")
                and "is not below voice" in problem.message
            ):
                # MusicXML imports may assign overlapping voice labels by
                # splitting chords rather than by pitch order. Preview/export
                # can still render literal-authored material; production
                # promote keeps the strict validation.
                note = "voice order was relaxed for Studio preview"
                if note not in warnings:
                    warnings.append(note)
                continue
            errors.append(
                RenderError(f"{prefix}.{problem.path}" if problem.path else prefix, problem.message)
            )

    if errors or plan is None:
        raise RenderPieceError(errors)
    return plan, tuple(warnings)


def _canonical_figures(
    figures: Sequence[tuple[PatternFigure, TextureSpec]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": figure.id,
            "cellId": figure.cell_id,
            "bars": figure.bars,
            "tags": list(figure.tags),
            "spec": texture_spec_to_mapping(texture),
        }
        for figure, texture in figures
    ]


def _render_hash(
    request: RenderPieceRequest,
    *,
    form: FormSpec,
    span: str,
    movement_index: int,
    title: str,
) -> str:
    payload = {
        "revision": STUDIO_RENDER_REVISION,
        "pattern": request.pattern,
        "meter": request.meter,
        "plan": request.plan,
        "figures": _canonical_figures(request.figures),
        "series": [
            {"close": float(bar.close), "volume": float(bar.volume)}
            for bar in request.bars
            if hasattr(bar, "close")
        ],
        "form": {
            "span": span,
            "movementIndex": movement_index,
            "bars": form.bars,
            "meter": request.meter,
            "includeDoors": request.include_doors,
        },
        "title": title,
        "paramsHash": params_hash(active_params()),
    }
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _score_notes(score: Score) -> int:
    return sum(
        1
        for voice in (
            getattr(score, "high", ()),
            score.lead,
            score.support,
            getattr(score, "comp", ()),
            score.low,
        )
        for note in voice
        if getattr(note, "midi", None) is not None
    )


def _audio_state(
    render_hash: str,
    params: Mapping[str, Any] | str | None = None,
) -> tuple[str, str | None]:
    """Report a cached production WAV without enqueueing work.

    The router owns the async job. The service only reports ``ready`` when a
    WAV already exists so a cache hit is visible without touching MuseScore.
    """
    try:
        asset = render_audio.cached_for_render(render_hash, params)
    except (OSError, ValueError):
        return "unavailable", None
    if asset is None:
        return "unavailable", None
    return "ready", asset.audio_hash


def _with_door_stubs(
    request: RenderPieceRequest,
) -> RenderPieceRequest:
    """Satisfy the five-tag validator for a body-only render.

    The stub doors are never used: ``_body_only`` removes the frame sections
    before the arrangement is built. They only let the shared promote validator
    prove the body figure is usable.
    """
    key_pair = next(
        (
            pair
            for pair in request.figures
            if "key" in pair[0].tags
        ),
        None,
    )
    if key_pair is None:
        return request
    key_figure, key_texture = key_pair
    existing = {
        tag
        for figure, _texture in request.figures
        for tag in figure.tags
    }
    missing = tuple(
        (tag, bars)
        for tag, bars in (
            ("intro.short", 2),
            ("intro.long", 4),
            ("outro.short", 2),
            ("outro.long", 4),
        )
        if tag not in existing
    )
    if not missing:
        return request
    stubs = tuple(
        (
            PatternFigure(
                id=f"__studio_door_{tag}",
                cell_id=key_figure.cell_id,
                bars=bars,
                tags=(tag,),
            ),
            key_texture,
        )
        for tag, bars in missing
    )
    return replace(
        request,
        figures=tuple(request.figures) + stubs,
    )


def _build_piece(
    request: RenderPieceRequest,
    form: FormSpec,
    cells: Mapping[str, TextureSpec],
) -> ArrangementResult:
    try:
        return build_arrangement(
            pattern=request.pattern,
            meter=request.meter,
            figures=[figure for figure, _texture in request.figures],
            form=form,
            policy=request.plan,
            textures=cells,
            require_doors=request.include_doors,
        )
    except ValueError as exc:
        message = str(exc)
        path = "plan" if "policy" in message else "form"
        raise RenderPieceError([RenderError(path, message)]) from exc


def render_piece(request: RenderPieceRequest) -> RenderPieceResult:
    """Validate, arrange, render, and cache one Studio Piece MusicXML score."""
    if not isinstance(request, RenderPieceRequest):
        raise TypeError("request must be a RenderPieceRequest")

    pattern = _non_empty_string(request.pattern, "pattern")
    meter_name = _non_empty_string(request.meter, "meter")
    meter = meter_from_name(meter_name)

    plan_id = request.plan
    if isinstance(plan_id, Mapping):
        plan_id = plan_id.get("id")
    if not isinstance(plan_id, str) or plan_id not in SUPPORTED_PLAN_IDS:
        raise RenderPieceError(
            [
                RenderError(
                    "plan",
                    f"unknown plan {plan_id!r}; expected one of "
                    f"{', '.join(SUPPORTED_PLAN_IDS)}",
                )
            ]
        )

    span = request.span
    if not isinstance(span, str) or not span:
        raise RenderPieceError(
            [RenderError("form.span", "span must be a non-empty string")]
        )
    form, movement_index = _resolve_form(
        span, meter, request.movement_index
    )
    if not request.include_doors:
        form = _body_only(form)

    figures, pitch_warnings = _bind_production_pitches(
        request.figures, meter.eighths_per_bar
    )
    normalized = RenderPieceRequest(
        pattern=pattern,
        meter=meter_name,
        figures=figures,
        plan=plan_id,
        bars=request.bars,
        span=span,
        movement_index=request.movement_index,
        title=request.title,
        include_doors=request.include_doors,
        session=request.session,
    )

    validation_request = (
        normalized if normalized.include_doors else _with_door_stubs(normalized)
    )
    plan, validation_warnings = _validate_figures(validation_request, meter)
    _validate_series(normalized.bars, form)

    requested_title = normalized.title
    title = (
        requested_title.strip()
        if isinstance(requested_title, str) and requested_title.strip()
        else f"{pattern} Studio Piece"
    )

    arrangement = _build_piece(normalized, form, plan.cells)
    warnings = [*pitch_warnings, *validation_warnings, *arrangement.warnings]

    render_hash = _render_hash(
        normalized,
        form=form,
        span=span,
        movement_index=movement_index,
        title=title,
    )
    cached = render_store.load_render(render_hash)
    if cached is not None:
        meta = cached.meta
        cached_warnings = meta.get("warnings")
        audio_status, audio_hash = _audio_state(
            cached.render_hash, str(meta.get("paramsHash") or "") or None
        )
        return RenderPieceResult(
            render_hash=cached.render_hash,
            musicxml=cached.musicxml.decode("utf-8"),
            meter=str(meta.get("meter") or meter_name),
            bars=int(meta.get("bars") or form.bars),
            notes=int(meta.get("notes") or 0),
            plan=str(meta.get("plan") or plan_id),
            warnings=(
                tuple(str(item) for item in cached_warnings)
                if isinstance(cached_warnings, list)
                else tuple(warnings)
            ),
            audio_status=audio_status,
            audio_hash=audio_hash,
            title=str(meta.get("title") or title),
            span=span,
            movement_index=movement_index,
            cached=True,
        )

    bar_values = [Bar(close=float(bar.close), volume=float(bar.volume)) for bar in normalized.bars]
    score = render(
        bar_values,
        variant="guitar",
        ensemble="villa",
        form=form,
        framed=False,
        movement_span=span,
        movement_index=movement_index,
        studio_piece=arrangement.piece,
        title=title,
    )
    musicxml = score_to_musicxml(score)
    notes = _score_notes(score)

    render_store.write_render(
        render_hash,
        musicxml,
        {
            "meter": meter_name,
            "bars": form.bars,
            "bpm": form.bpm,
            "title": title,
            "notes": notes,
            "plan": plan_id,
            "span": span,
            "movementIndex": movement_index,
            "warnings": warnings,
            "session": normalized.session,
            "revision": STUDIO_RENDER_REVISION,
            "paramsHash": params_hash(active_params()),
        },
    )

    audio_status, audio_hash = _audio_state(
        render_hash, params_hash(active_params())
    )
    return RenderPieceResult(
        render_hash=render_hash,
        musicxml=musicxml,
        meter=meter_name,
        bars=form.bars,
        notes=notes,
        plan=plan_id,
        warnings=tuple(warnings),
        audio_status=audio_status,
        audio_hash=audio_hash,
        title=title,
        span=span,
        movement_index=movement_index,
    )
