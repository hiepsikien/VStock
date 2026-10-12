from __future__ import annotations

import html
import logging
import os

import httpx

logger = logging.getLogger(__name__)
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
WATCHED = {"Được vào", "Loại", "Khóa"}


def _escaped(value: object) -> str:
    """Text for an HTML message: only our own tags may survive the trip.

    A filing title with a stray ``<`` is enough to make sendMessage answer 400 and lose the
    whole session alert, position lines included.
    """
    return html.escape(str(value), quote=False)


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() and os.environ.get("TELEGRAM_CHAT_ID", "").strip())


async def send(text: str) -> bool:
    """Post one message. Missing credentials are not an error, the operator may not want alerts."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not configured():
        logger.info("Telegram skipped: token or chat id not set")
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                TELEGRAM_URL.format(token=token),
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # The exception message carries the request URL, and the URL carries the bot token:
        # keep the status code and drop the rest.
        logger.warning("Telegram send failed: HTTP %s", exc.response.status_code)
        return False
    except httpx.HTTPError as exc:
        logger.warning("Telegram send failed: %s", type(exc).__name__)
        return False
    return True


def transition_lines(previous: list[dict], current: list[dict]) -> list[str]:
    """One line per name whose status changed into or out of a decision state."""
    before = {item["symbol"]: item for item in previous}
    lines: list[str] = []
    for item in current:
        old = before.get(item["symbol"])
        if old is None or old["status"] == item["status"]:
            continue
        if item["status"] not in WATCHED and old["status"] != "Được vào":
            continue
        stop = f"{item['stop_price']:.2f}" if item.get("stop_price") else "—"
        if item["status"] == "Được vào":
            lines.append(
                f"<b>{_escaped(item['symbol'])}</b> Được vào — điểm {item['score']}/100, "
                f"dừng lỗ {stop}. {_escaped(item['summary'])}"
            )
        elif item["status"] in {"Loại", "Khóa"}:
            lines.append(
                f"<b>{_escaped(item['symbol'])}</b> {_escaped(item['status'])} — {_escaped(item['summary'])}"
            )
        else:
            lines.append(
                f"<b>{_escaped(item['symbol'])}</b> {_escaped(old['status'])} → {_escaped(item['status'])}"
            )
    return lines


def session_message(current: list[dict], previous: list[dict], as_of: str) -> str | None:
    """Message body for a session, or None when nothing needs an alert."""
    lines = transition_lines(previous, current)
    if not lines:
        return None
    header = f"VStock research {_escaped(as_of)}"
    return header + "\n" + "\n".join(lines)
