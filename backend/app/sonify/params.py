"""Tier A parameter profiles for the sonify pipeline.

One schema lives here. The API serves it, the cache mark is a pure function of
the normalized values, and the render pipeline reads the active values through
a ContextVar. A missing or default value must reproduce the previous behaviour
byte for byte.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1
P_MAX_LENGTH = 2048
HUMANIZE_SOFT_WARNING = 1.1
BREATH_SOFT_WARNING = 1.2


@dataclass(frozen=True)
class ParamField:
    key: str
    label: str
    group: str
    minimum: float
    maximum: float
    step: float
    default: float
    unit: str
    description: str


PERFORMANCE = "performance"
TEXTURE = "texture"

FIELDS: tuple[ParamField, ...] = (
    ParamField(
        "tempo",
        "Nhịp",
        PERFORMANCE,
        0.75,
        1.25,
        0.01,
        1.0,
        "×",
        "Nhân BPM gốc của dòng nhạc.",
    ),
    ParamField(
        "humanize",
        "Người",
        PERFORMANCE,
        0.0,
        1.5,
        0.05,
        1.0,
        "",
        "Độ lệch velocity.",
    ),
    ParamField(
        "breath",
        "Hơi thở",
        PERFORMANCE,
        0.0,
        1.5,
        0.05,
        1.0,
        "",
        "Độ cong tempo trong câu.",
    ),
    ParamField(
        "color",
        "Màu",
        PERFORMANCE,
        0.0,
        1.0,
        0.05,
        1.0,
        "",
        "Lượng wet của preset.",
    ),
    ParamField(
        "dynamics",
        "Tương phản",
        TEXTURE,
        0.5,
        1.5,
        0.05,
        1.0,
        "",
        "Co giãn velocity quanh mốc 64.",
    ),
    ParamField(
        "noise",
        "Nhiễu",
        TEXTURE,
        0.0,
        1.0,
        0.05,
        1.0,
        "",
        "Nhân nền nhiễu của preset.",
    ),
    ParamField(
        "density",
        "Mật độ",
        TEXTURE,
        0.0,
        1.5,
        0.05,
        1.0,
        "",
        "Nhân độ dài và số lượng fill, bell.",
    ),
)

FIELD_BY_KEY: dict[str, ParamField] = {field.key: field for field in FIELDS}
DEFAULT_PARAMS: dict[str, float] = {field.key: field.default for field in FIELDS}
GROUPS: tuple[tuple[str, str], ...] = (
    (PERFORMANCE, "Trình diễn"),
    (TEXTURE, "Sâu hơn"),
)

# The unmodified tempo of each line. The schema carries this so the drawer can
# show the derived BPM without a hand-kept copy in the client.
GUITAR_BPM: dict[str, int] = {
    "bach": 96,
    "classic": 88,
    "villa": 100,
    "barrios": 120,
    "brouwer": 108,
    "torroba": 96,
}
BASE_BPM: dict[str, int | dict[str, int]] = {
    "symphony": 90,
    "jazz": 82,
    "minimalist": 118,
    "ambient": 60,
    "guitar": GUITAR_BPM,
}


def base_bpm(variant: str, ensemble: str = "classic") -> int:
    value = BASE_BPM.get(variant, BASE_BPM["symphony"])
    if isinstance(value, dict):
        return value.get(ensemble, value["classic"])
    return value

Params = dict[str, float]


def _round_step(value: float, step: float) -> float:
    """Round to the schema grid before anything reads the number."""
    if step <= 0:
        return round(float(value), 2)
    return round(round(float(value) / step) * step, 2)


def _coerce_number(key: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{key} must be a finite number")
    return number


def normalize_with_warnings(raw: Mapping[str, Any] | None) -> tuple[Params, list[dict[str, Any]]]:
    """Return canonical params and warnings. Unknown keys are skipped."""
    source: Mapping[str, Any] = raw or {}
    if not isinstance(source, Mapping):
        raise ValueError("params must be an object")
    params: Params = {}
    warnings: list[dict[str, Any]] = []
    for key, field in FIELD_BY_KEY.items():
        if key not in source:
            params[key] = field.default
            continue
        number = _coerce_number(key, source[key])
        value = min(field.maximum, max(field.minimum, _round_step(number, field.step)))
        value = min(field.maximum, max(field.minimum, _round_step(value, field.step)))
        if value != _round_step(number, field.step):
            warnings.append({"code": "clamped", "key": key, "value": number})
        params[key] = value
    for key in source:
        if key not in FIELD_BY_KEY:
            warnings.append({"code": "unknown_key", "key": str(key)})
    if params["humanize"] > HUMANIZE_SOFT_WARNING:
        warnings.append(
            {"code": "high_humanize", "key": "humanize", "value": params["humanize"]}
        )
    if params["breath"] > BREATH_SOFT_WARNING:
        warnings.append({"code": "high_breath", "key": "breath", "value": params["breath"]})
    return params, warnings


def normalize_params(raw: Mapping[str, Any] | None) -> Params:
    params, _warnings = normalize_with_warnings(raw)
    return params


def params_key(params: Mapping[str, Any] | None) -> str:
    """Canonical JSON string, used by the client as a React key."""
    canonical = {"schema": SCHEMA_VERSION, "params": normalize_params(params)}
    return json.dumps(canonical, separators=(",", ":"), sort_keys=True)


def params_hash(params: Mapping[str, Any] | None) -> str:
    return hashlib.sha256(params_key(params).encode("utf-8")).hexdigest()[:12]


DEFAULT_HASH = params_hash(DEFAULT_PARAMS)


def encode_params(params: Mapping[str, Any] | None) -> str:
    payload = params_key(params).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_params(text: str) -> Params:
    if not isinstance(text, str) or not text:
        raise ValueError("p is empty")
    if len(text) > P_MAX_LENGTH:
        raise ValueError("p is too long")
    padded = text + "=" * (-len(text) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("p is not base64url") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("p is not JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("p must decode to an object")
    if payload.get("schema", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("unsupported params schema")
    body = payload.get("params", payload)
    if not isinstance(body, dict):
        raise ValueError("p params must be an object")
    return normalize_params(body)


def params_from_flags(humanize: bool = True, color: bool = True) -> Params:
    """Map the legacy boolean query onto the new params.

    `humanize=false` turned off the whole post-compose layer, tempo clock
    included, so it also pins breath to zero. That is what keeps the old `_nh`
    cache valid.
    """
    params = dict(DEFAULT_PARAMS)
    if not humanize:
        params["humanize"] = 0.0
        params["breath"] = 0.0
    if not color:
        params["color"] = 0.0
    return params


def legacy_layer_mark(params: Mapping[str, Any]) -> str:
    """The old suffixes, only for the exact combinations that produced them."""
    normalized = normalize_params(params)
    rest = {
        key: value
        for key, value in normalized.items()
        if key not in {"humanize", "breath", "color"}
    }
    if any(value != DEFAULT_PARAMS[key] for key, value in rest.items()):
        return ""
    humanize = normalized["humanize"]
    breath = normalized["breath"]
    color = normalized["color"]
    if humanize == 0.0 and breath == 0.0:
        if color == 1.0:
            return "_nh"
        if color == 0.0:
            return "_nh_nc"
        return ""
    if humanize == 1.0 and breath == 1.0 and color == 0.0:
        return "_nc"
    return ""


def cache_mark(params: Mapping[str, Any] | None) -> str:
    """Stem suffix. Empty keeps the old file name, so old cache still serves."""
    normalized = normalize_params(params)
    if normalized == DEFAULT_PARAMS:
        return ""
    return legacy_layer_mark(normalized) or f"_p{params_hash(normalized)}"


def is_default(params: Mapping[str, Any] | None) -> bool:
    return normalize_params(params) == DEFAULT_PARAMS


def params_query(params: Mapping[str, Any] | None) -> str:
    """Query suffix for audio and peaks URLs."""
    normalized = normalize_params(params)
    if normalized == DEFAULT_PARAMS:
        return ""
    return f"&p={encode_params(normalized)}"


def params_layers(params: Mapping[str, Any] | None) -> tuple[bool, bool]:
    """(humanize layer on, color layer on) for one params object."""
    normalized = normalize_params(params)
    humanize = normalized["humanize"] != 0.0 or normalized["breath"] != 0.0
    return humanize, normalized["color"] != 0.0


def params_enabled() -> bool:
    return os.environ.get("VSTOCK_SONIFY_PARAMS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def params_from_query(
    p: str | None,
    humanize: bool = True,
    color: bool = True,
) -> Params:
    """Read `p`, falling back to the legacy booleans. Raises on a bad `p`."""
    if p and params_enabled():
        return decode_params(p)
    return params_from_flags(humanize=humanize, color=color)


def schema_payload(*, enabled: bool | None = None) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    for group_id, label in GROUPS:
        fields = [
            {
                "key": field.key,
                "label": field.label,
                "type": "number",
                "min": field.minimum,
                "max": field.maximum,
                "step": field.step,
                "default": field.default,
                "unit": field.unit,
                "description": field.description,
            }
            for field in FIELDS
            if field.group == group_id
        ]
        groups.append({"id": group_id, "label": label, "fields": fields})
    payload: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "groups": groups,
        "defaultHash": DEFAULT_HASH,
        "baseBpm": BASE_BPM,
        "enabled": params_enabled() if enabled is None else enabled,
    }
    return payload


def presets_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": "default",
            "name": "Default",
            "params": dict(DEFAULT_PARAMS),
        },
        {
            "id": "close",
            "name": "Gần",
            "params": {**DEFAULT_PARAMS, "color": 0.45, "noise": 0.0},
        },
        {
            "id": "warm",
            "name": "Ấm",
            "params": {**DEFAULT_PARAMS, "tempo": 0.96, "noise": 0.8},
        },
        {
            "id": "alive",
            "name": "Sống",
            "params": {**DEFAULT_PARAMS, "humanize": 1.1, "breath": 1.15},
        },
        {
            "id": "dense",
            "name": "Dày",
            "params": {**DEFAULT_PARAMS, "density": 1.25},
        },
    ]


_ACTIVE: ContextVar[Params] = ContextVar("sonify_params", default=DEFAULT_PARAMS)


def active_params() -> Params:
    return _ACTIVE.get()


def active(key: str) -> float:
    return _ACTIVE.get().get(key, DEFAULT_PARAMS[key])


@contextmanager
def compose_params(params: Mapping[str, Any] | None):
    token = _ACTIVE.set(normalize_params(params))
    try:
        yield _ACTIVE.get()
    finally:
        _ACTIVE.reset(token)


def tempo_bpm(bpm: int | float, tempo: float | None = None) -> int:
    """Effective BPM. Half-up, so `.5` is monotone as `tempo` rises."""
    factor = active("tempo") if tempo is None else tempo
    return int(float(bpm) * factor + 0.5)
