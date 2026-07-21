from __future__ import annotations

from app.ingestion.providers.registry import get_quote_registry
from app.repositories.quotes_repo import QuotesRepository
from app.services.cache import QUOTE_TTL, cache

_repo = QuotesRepository()


def _is_thin_payload(payload: dict) -> bool:
    return (
        float(payload.get("open") or 0) <= 0
        and float(payload.get("high") or 0) <= 0
        and float(payload.get("low") or 0) <= 0
        and int(payload.get("volume") or 0) <= 0
    )


def _sanitize_payload(payload: dict) -> dict:
    """Fix legacy bad change values (raw VND / flipped sign) using ref or %."""
    price = float(payload.get("price") or 0)
    change = float(payload.get("change") or 0)
    change_pct = float(payload.get("changePercent") or 0)
    ref = float(payload.get("ref") or 0)

    sign_mismatch = (change > 0 and change_pct < 0) or (change < 0 and change_pct > 0)
    absurd = price > 0 and abs(change) > max(price * 0.35, 5.0)

    if not sign_mismatch and not absurd:
        return payload

    fixed = dict(payload)
    if ref > 0 and price > 0:
        fixed["change"] = round(price - ref, 2)
    elif price > 0 and change_pct != 0:
        inferred_ref = price / (1 + change_pct / 100)
        fixed["change"] = round(price - inferred_ref, 2)
        fixed["ref"] = round(inferred_ref, 2)
    return fixed


def _is_bad_change(payload: dict) -> bool:
    price = float(payload.get("price") or 0)
    change = float(payload.get("change") or 0)
    change_pct = float(payload.get("changePercent") or 0)
    sign_mismatch = (change > 0 and change_pct < 0) or (change < 0 and change_pct > 0)
    absurd = price > 0 and abs(change) > max(price * 0.35, 5.0)
    return sign_mismatch or absurd


async def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Serve quotes from SQLite store; bootstrap missing symbols via providers."""
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    if not cleaned:
        return {}

    result: dict[str, dict] = {}
    missing: list[str] = []

    for sym in cleaned:
        cached = cache.get(f"quote:{sym}")
        if cached is not None and not _is_thin_payload(cached) and not _is_bad_change(cached):
            result[sym] = _sanitize_payload(cached)
            continue
        missing.append(sym)

    if missing:
        from_db = await _repo.get_latest(missing)
        still_missing: list[str] = []
        for sym in missing:
            payload = from_db.get(sym)
            if payload and not _is_thin_payload(payload) and not _is_bad_change(payload):
                payload = _sanitize_payload(payload)
                cache.set(f"quote:{sym}", payload, QUOTE_TTL)
                result[sym] = payload
            elif payload and not _is_thin_payload(payload) and _is_bad_change(payload):
                # Repair in place so UI is correct even before provider refresh.
                fixed = _sanitize_payload(payload)
                cache.set(f"quote:{sym}", fixed, QUOTE_TTL)
                result[sym] = fixed
                still_missing.append(sym)  # also refresh from providers
            else:
                still_missing.append(sym)
        missing = still_missing

    if missing:
        registry = get_quote_registry()
        fetched = await registry.fetch_quotes(missing)
        if fetched:
            await _repo.upsert_many(list(fetched.values()))
        for sym in missing:
            quote = fetched.get(sym)
            if not quote:
                continue
            payload = _sanitize_payload(quote.to_dict())
            cache.set(f"quote:{sym}", payload, QUOTE_TTL)
            result[sym] = payload

    return result


async def fetch_quote(symbol: str) -> dict | None:
    quotes = await fetch_quotes([symbol])
    return quotes.get(symbol.upper())
