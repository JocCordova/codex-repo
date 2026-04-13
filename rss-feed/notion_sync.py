from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import requests
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"


def _date_obj(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return {"start": dt.isoformat()}
    except ValueError:
        return None


def _build_properties(item: dict[str, Any], cluster: dict[str, Any], notion_cfg: dict[str, Any], digest_date: str) -> dict[str, Any]:
    props = notion_cfg["properties"]
    properties: dict[str, Any] = {
        props["title"]: {"title": [{"text": {"content": item["title"][:2000]}}]},
        props["source"]: {"rich_text": [{"text": {"content": item.get("source", "")[:2000]}}]},
        props["url"]: {"url": item.get("url")},
        props["score"]: {"number": float(item.get("score", 0.0))},
        props["topics"]: {"multi_select": [{"name": t[:100]} for t in item.get("matched_topics", [])[:20]]},
        props["cluster_size"]: {"number": int(cluster.get("size", 1))},
        props["digest_date"]: {"date": {"start": digest_date}},
    }

    parsed = _date_obj(item.get("published_at"))
    if parsed:
        properties[props["published_at"]] = {"date": parsed}
    return properties


def sync_to_notion(clusters: list[dict[str, Any]], notion_cfg: dict[str, Any], timezone_name: str) -> None:
    if not notion_cfg.get("enabled", False):
        logger.info("Notion sync disabled")
        return

    token = os.getenv(notion_cfg.get("token_env", ""))
    database_id = os.getenv(notion_cfg.get("database_id_env", ""))
    if not token or not database_id:
        logger.warning("Notion sync enabled but credentials are missing")
        return

    digest_date = datetime.now(ZoneInfo(timezone_name)).date().isoformat()
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    for cluster in clusters:
        for item in cluster.get("items", []):
            payload = {
                "parent": {"database_id": database_id},
                "properties": _build_properties(item, cluster, notion_cfg, digest_date),
            }
            try:
                response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=20)
                if response.status_code >= 300:
                    logger.error("Notion sync failed (%s): %s", response.status_code, response.text)
                else:
                    logger.info("Synced to Notion: %s", item["title"])
            except requests.RequestException as exc:
                logger.error("Notion request failed for '%s': %s", item["title"], exc)
