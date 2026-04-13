from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any

import feedparser
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


ParsedItem = dict[str, Any]


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return date_parser.parse(value).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def _item_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()


def fetch_feed(feed: dict[str, Any], max_items: int) -> list[ParsedItem]:
    """Fetch a single RSS feed and normalize items."""
    name = feed.get("name", "unknown")
    url = feed.get("url", "")
    weight = float(feed.get("weight", 1.0))

    parsed = feedparser.parse(url)
    if getattr(parsed, "bozo", False):
        logger.warning("Feed parse warning for %s (%s): %s", name, url, getattr(parsed, "bozo_exception", "unknown"))

    items: list[ParsedItem] = []
    for entry in parsed.entries[:max_items]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "")
        published = _parse_date(entry.get("published") or entry.get("updated"))

        if not title or not link:
            continue

        items.append(
            {
                "id": _item_id(link, title),
                "title": title,
                "url": link,
                "summary": summary,
                "source": name,
                "feed_weight": weight,
                "published_at": published,
                "raw_published": entry.get("published") or entry.get("updated"),
            }
        )

    logger.info("Fetched %d items from %s", len(items), name)
    return items


def fetch_all(feeds: list[dict[str, Any]], max_items_per_feed: int) -> list[ParsedItem]:
    all_items: list[ParsedItem] = []
    for feed in feeds:
        try:
            all_items.extend(fetch_feed(feed, max_items_per_feed))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Feed fetch failed for %s: %s", feed.get("name", "unknown"), exc)
    return all_items
