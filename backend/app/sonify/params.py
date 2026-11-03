"""Parameter profiles for the sonify pipeline.

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

SCHEMA_VERSION = 3
LINK_SCHEMA_VERSION = 2
P_MAX_LENGTH = 2048
HUMANIZE_SOFT_WARNING = 1.1
BREATH_SOFT_WARNING = 1.2

TIERS = ("A", "B", "C")
# Production starts with tier A. Local development sets
# VSTOCK_SONIFY_PARAMS_TIER=A,B,C to expose the new knobs.
DEFAULT_TIERS = ("A",)


@dataclass(frozen=True)
class ParamChoice:
    value: str
    label: str


@dataclass(frozen=True)
class ParamField:
    key: str
    label: str
    group: str
    minimum: float
    maximum: float
    step: float
    default: float | str | bool
    unit: str = ""
    description: str = ""
    # Display a leading "+" for positive integers. The client uses this
    # explicitly instead of inferring signedness from the step.
    signed: bool = False
    kind: str = "number"
    choices: tuple[ParamChoice, ...] = ()
    auto: bool = False
    applies_to: tuple[str, ...] = ()
    tier: str = "A"


PERFORMANCE = "performance"
TEXTURE = "texture"
GUITAR = "guitar"
HARMONY = "harmony"
SPACE = "space"
FORM = "form"

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
        "Tăng giảm tốc độ của bản thu so với nhịp gốc.",
    ),
    ParamField(
        "humanize",
        "Người",
        PERFORMANCE,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "Độ lệch velocity giữa các nốt để bớt đều máy móc.",
    ),
    ParamField(
        "breath",
        "Hơi thở",
        PERFORMANCE,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "Độ cong tốc độ ở đầu và cuối mỗi câu.",
    ),
    ParamField(
        "color",
        "Màu",
        PERFORMANCE,
        0.0,
        2.0,
        0.01,
        1.0,
        "",
        "Lượng hiệu ứng màu (EQ, echo, soft-clip); 0 là khô, 2 là đậm gấp đôi.",
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
        "Độ chênh lực bấm giữa các sắc thái, quanh velocity 64.",
    ),
    ParamField(
        "noise",
        "Nhiễu",
        TEXTURE,
        0.0,
        0.5,
        0.05,
        0.1,
        "%",
        "Nhiễu nền cộng vào bản thu, tính bằng % toàn thang.",
    ),
    ParamField(
        "density",
        "Mật độ",
        TEXTURE,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "Lượng fill và bell chèn vào giữa các câu.",
    ),
    ParamField(
        "guitar_high",
        "Bè cao",
        GUITAR,
        -12.0,
        12.0,
        1.0,
        0.0,
        "",
        "Độ lệch velocity của bè cao (giai điệu). 0 là bản hiện tại.",
        signed=True,
    ),
    ParamField(
        "guitar_mid",
        "Bè trung",
        GUITAR,
        -12.0,
        12.0,
        1.0,
        0.0,
        "",
        "Độ lệch velocity của bè trung (voice 2 và 4). 0 là bản hiện tại.",
        signed=True,
    ),
    ParamField(
        "guitar_bass",
        "Bè bass",
        GUITAR,
        -12.0,
        12.0,
        1.0,
        0.0,
        "",
        "Độ lệch velocity của bè bass (ngón cái). 0 là bản hiện tại.",
        signed=True,
    ),
    ParamField(
        "harmony",
        "Màu hòa âm",
        HARMONY,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "0 là tối giản trong vocabulary của variant; 1 là hiện tại; 2 là nhiều màu hơn.",
        tier="B",
    ),
    ParamField(
        "register",
        "Vùng âm",
        SPACE,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "0 thấp/ấm, 1 hiện tại, 2 cao/sáng. Dịch biên độ, không đổi giọng.",
        tier="B",
    ),
    ParamField(
        "technique",
        "Kỹ thuật",
        GUITAR,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "0 dễ, 1 hiện tại, 2 điêu luyện. Hiện chỉ áp dụng cho Bach và Torroba.",
        applies_to=("bach", "torroba"),
        tier="C",
    ),
    ParamField(
        "motion",
        "Nhịp hòa âm",
        HARMONY,
        0.0,
        2.0,
        0.05,
        1.0,
        "",
        "0 giữ hợp âm lâu, 1 hiện tại, 2 đổi hợp âm dồn dập.",
        tier="C",
    ),
    ParamField(
        "frame",
        "Khung",
        FORM,
        0.0,
        0.0,
        0.0,
        "auto",
        "",
        "Độ dài warm-up/cool-down cho span dài. Auto giữ hiện tại.",
        kind="choice",
        choices=(
            ParamChoice("auto", "Tự động"),
            ParamChoice("none", "Không khung"),
            ParamChoice("short", "Ngắn"),
            ParamChoice("long", "Dài"),
        ),
        auto=True,
        applies_to=("1M", "3M", "1Y"),
        tier="B",
    ),
    ParamField(
        "meter",
        "Tiết nhịp",
        FORM,
        0.0,
        0.0,
        0.0,
        "auto",
        "",
        "Chỉ mở nơi đã có retarget. Auto giữ hiện tại.",
        kind="choice",
        choices=(
            ParamChoice("auto", "Tự động"),
            ParamChoice("4/4", "4/4"),
            ParamChoice("3/4", "3/4"),
            ParamChoice("6/8", "6/8"),
            ParamChoice("12/8", "12/8"),
        ),
        auto=True,
        applies_to=("torroba",),
        tier="B",
    ),
)

FIELD_BY_KEY: dict[str, ParamField] = {field.key: field for field in FIELDS}
DEFAULT_PARAMS: dict[str, float | str | bool] = {field.key: field.default for field in FIELDS}
GROUPS: tuple[tuple[str, str], ...] = (
    (PERFORMANCE, "Trình diễn"),
    (TEXTURE, "Sâu hơn"),
    (GUITAR, "Guitar"),
    (HARMONY, "Hòa âm"),
    (SPACE, "Không gian"),
    (FORM, "Dáng"),
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


Params = dict[str, float | str | bool]


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


def enabled_tiers() -> tuple[str, ...]:
    raw = os.environ.get("VSTOCK_SONIFY_PARAMS_TIER")
    if raw is None:
        return DEFAULT_TIERS
    tokens = tuple(token.strip().upper() for token in raw.split(",") if token.strip())
    found = tuple(token for token in TIERS if token in tokens)
    return found or ("A",)


def apply_tiers(
    params: Mapping[str, Any],
    tiers: tuple[str, ...] | None = None,
) -> Params:
    active_tiers = enabled_tiers() if tiers is None else tiers
    shaped = dict(params)
    for field in FIELDS:
        if field.tier not in active_tiers:
            shaped[field.key] = field.default
    return shaped


def _normalize_value(field: ParamField, value: Any) -> tuple[float | str | bool, str | None]:
    if field.kind == "toggle":
        if isinstance(value, bool):
            return value, None
        return field.default, "unknown_choice"
    if field.kind == "choice":
        if isinstance(value, str):
            allowed = {choice.value for choice in field.choices}
            if value in allowed:
                return value, None
            return field.default, "unknown_choice"
        return field.default, "unknown_choice"
    number = _coerce_number(field.key, value)
    shaped = min(field.maximum, max(field.minimum, _round_step(number, field.step)))
    shaped = min(field.maximum, max(field.minimum, _round_step(shaped, field.step)))
    return shaped, None


def normalize_with_warnings(
    raw: Mapping[str, Any] | None,
    *,
    tiers: tuple[str, ...] | None = None,
) -> tuple[Params, list[dict[str, Any]]]:
    """Return canonical params and warnings. Unknown keys are skipped."""
    source: Mapping[str, Any] = raw or {}
    if not isinstance(source, Mapping):
        raise ValueError("params must be an object")
    active_tiers = enabled_tiers() if tiers is None else tiers
    params: Params = {}
    warnings: list[dict[str, Any]] = []
    for key, field in FIELD_BY_KEY.items():
        if key not in source:
            params[key] = field.default
        else:
            value, warning = _normalize_value(field, source[key])
            params[key] = value
            if warning == "unknown_choice":
                warnings.append(
                    {"code": "unknown_choice", "key": key, "value": source[key]}
                )
            elif field.kind == "number":
                number = _coerce_number(key, source[key])
                if value != _round_step(number, field.step):
                    warnings.append({"code": "clamped", "key": key, "value": number})
        if field.tier not in active_tiers:
            params[key] = field.default
            if key in source:
                warnings.append({"code": "tier_disabled", "key": key})
    for key in source:
        if key not in FIELD_BY_KEY:
            warnings.append({"code": "unknown_key", "key": str(key)})
    humanize = params["humanize"]
    breath = params["breath"]
    if isinstance(humanize, float) and humanize > HUMANIZE_SOFT_WARNING:
        warnings.append(
            {"code": "high_humanize", "key": "humanize", "value": humanize}
        )
    if isinstance(breath, float) and breath > BREATH_SOFT_WARNING:
        warnings.append({"code": "high_breath", "key": "breath", "value": breath})
    return params, warnings


_SPAN_TOKENS = frozenset({"1D", "1W", "1M", "3M", "1Y"})


def _applies_to(field: ParamField, variant: str | None, ensemble: str | None, span: str | None) -> bool:
    if not field.applies_to:
        return True
    spans = tuple(item for item in field.applies_to if item in _SPAN_TOKENS)
    targets = tuple(item for item in field.applies_to if item not in _SPAN_TOKENS)
    if spans and span and span in spans:
        return True
    if targets and variant and variant in targets:
        return True
    if targets and ensemble and ensemble in targets:
        return True
    return False


def inapplicable_warnings(
    raw: Mapping[str, Any] | None,
    *,
    variant: str | None = None,
    ensemble: str | None = None,
    span: str | None = None,
) -> list[dict[str, Any]]:
    """Warn about fields that do not apply to this room. Does not touch the hash."""
    source = raw or {}
    if not isinstance(source, Mapping):
        return []
    warnings: list[dict[str, Any]] = []
    for key, field in FIELD_BY_KEY.items():
        if key not in source:
            continue
        if field.tier not in enabled_tiers():
            continue
        if not _applies_to(field, variant, ensemble, span):
            warnings.append({"code": "inapplicable", "key": key})
    return warnings


def normalize_params(
    raw: Mapping[str, Any] | None,
    *,
    tiers: tuple[str, ...] | None = None,
) -> Params:
    params, _warnings = normalize_with_warnings(raw, tiers=tiers)
    return params


def params_key(
    params: Mapping[str, Any] | None,
    *,
    schema: int = SCHEMA_VERSION,
    tiers: tuple[str, ...] | None = None,
) -> str:
    """Canonical JSON string, used by the client as a React key."""
    canonical = {
        "schema": schema,
        "params": normalize_params(params, tiers=tiers),
    }
    return json.dumps(canonical, separators=(",", ":"), sort_keys=True)


def params_hash(
    params: Mapping[str, Any] | None,
    *,
    schema: int = SCHEMA_VERSION,
    tiers: tuple[str, ...] | None = None,
) -> str:
    return hashlib.sha256(
        params_key(params, schema=schema, tiers=tiers).encode("utf-8")
    ).hexdigest()[:12]


DEFAULT_HASH = params_hash(DEFAULT_PARAMS, tiers=TIERS)


def encode_params(
    params: Mapping[str, Any] | None,
    *,
    schema: int = SCHEMA_VERSION,
    tiers: tuple[str, ...] | None = None,
) -> str:
    payload = params_key(params, schema=schema, tiers=tiers).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_params(text: str, *, tiers: tuple[str, ...] | None = None) -> Params:
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
    version = payload.get("schema", SCHEMA_VERSION)
    if version not in (2, SCHEMA_VERSION):
        raise ValueError("unsupported params schema")
    body = payload.get("params", payload)
    if not isinstance(body, dict):
        raise ValueError("p params must be an object")
    return normalize_params(body, tiers=tiers)


def params_from_flags(humanize: bool = True, color: bool = True) -> Params:
    """Map the legacy boolean query onto the new params."""
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
    return f"&p={encode_params(normalized, schema=LINK_SCHEMA_VERSION)}"


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


def schema_payload(
    *,
    enabled: bool | None = None,
    tiers: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    active_tiers = enabled_tiers() if tiers is None else tiers
    groups: list[dict[str, Any]] = []
    for group_id, label in GROUPS:
        fields = [
            {
                "key": field.key,
                "label": field.label,
                "type": field.kind,
                "min": field.minimum,
                "max": field.maximum,
                "step": field.step,
                "default": field.default,
                "unit": field.unit,
                "description": field.description,
                "signed": field.signed,
                "choices": [
                    {"value": choice.value, "label": choice.label}
                    for choice in field.choices
                ],
                "auto": field.auto,
                "appliesTo": list(field.applies_to),
                "tier": field.tier,
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
        "enabledTiers": list(active_tiers),
        "allTiers": list(TIERS),
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
            "params": {**DEFAULT_PARAMS, "tempo": 0.96, "noise": 0.2},
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
    value = _ACTIVE.get().get(key, DEFAULT_PARAMS[key])
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float(
        DEFAULT_PARAMS[key]
    )


def active_choice(key: str) -> str:
    value = _ACTIVE.get().get(key, DEFAULT_PARAMS[key])
    return value if isinstance(value, str) else str(DEFAULT_PARAMS[key])


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
