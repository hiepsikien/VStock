from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_QUOTE_PROVIDERS: list[dict[str, Any]] = [
    {"name": "vps", "priority": 1, "type": "realtime", "batch": True},
    {"name": "ssi_iboard", "priority": 2, "type": "realtime", "batch": False},
    {"name": "entrade_stale", "priority": 3, "type": "stale", "batch": True},
    {"name": "kbs_stale", "priority": 4, "type": "stale", "batch": False},
]


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "providers.yaml"


def load_quote_providers() -> list[dict[str, Any]]:
    path = _config_path()
    if not path.exists():
        return DEFAULT_QUOTE_PROVIDERS

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return DEFAULT_QUOTE_PROVIDERS

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    providers = raw.get("quotes", {}).get("providers")
    if not isinstance(providers, list) or not providers:
        return DEFAULT_QUOTE_PROVIDERS

    cleaned: list[dict[str, Any]] = []
    for item in providers:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        cleaned.append(item)

    return cleaned or DEFAULT_QUOTE_PROVIDERS
