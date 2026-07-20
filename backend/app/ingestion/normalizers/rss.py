from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from app.domain.news import NewsArticle

_IMG_SRC_RE = re.compile(r'src=["\']([^"\']+)["\']', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SYMBOL_RE = re.compile(r"\b([A-Z]{3}(?:[0-9]{1,2})?)\b")


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def _parse_pub_date(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError, OverflowError):
        pass

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue

    return raw[:19] if len(raw) >= 19 else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _extract_summary(description: str) -> str:
    if not description:
        return ""

    text = _TAG_RE.sub(" ", description)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:220]


def _extract_image(description: str, enclosure_url: str | None) -> str | None:
    if enclosure_url:
        return enclosure_url

    match = _IMG_SRC_RE.search(description)
    if match:
        return match.group(1).strip()
    return None


def _extract_symbols(title: str, summary: str) -> tuple[str, ...]:
    found: list[str] = []
    for text in (title, summary):
        for match in _SYMBOL_RE.findall(text):
            sym = match.upper()
            if sym not in found:
                found.append(sym)
    return tuple(found)


def parse_rss_feed(
    xml_text: str,
    *,
    source: str,
    default_category: str,
    provider_prefix: str,
) -> list[NewsArticle]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    channel = root
    if _local_name(root.tag) != "channel":
        channel = root.find("channel") or root.find("{*}channel") or root

    items: list[NewsArticle] = []
    for item in channel.findall(".//item") + channel.findall(".//{*}item"):
        title = html.unescape(_text(item.find("title")) or _text(item.find("{*}title")))
        if not title:
            continue

        link = html.unescape(_text(item.find("link")) or _text(item.find("{*}link")))
        guid = html.unescape(_text(item.find("guid")) or _text(item.find("{*}guid")))
        description = _text(item.find("description")) or _text(item.find("{*}description"))
        pub_date = _text(item.find("pubDate")) or _text(item.find("{*}pubDate"))

        enclosure_url: str | None = None
        enclosure = item.find("enclosure") or item.find("{*}enclosure")
        if enclosure is not None:
            enclosure_url = (enclosure.attrib.get("url") or "").strip() or None

        url = link or guid
        key = url or title
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        summary = _extract_summary(description)

        items.append(
            NewsArticle(
                id=f"{provider_prefix}:{digest}",
                title=title,
                summary=summary,
                source=source,
                published_at=_parse_pub_date(pub_date),
                url=url,
                image_url=_extract_image(description, enclosure_url),
                symbols=_extract_symbols(title, summary),
                category=default_category,
            )
        )

    return items
