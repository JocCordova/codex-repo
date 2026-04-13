from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _format_score(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _notion_database_url(notion_cfg: dict[str, Any] | None) -> str | None:
    if not notion_cfg:
        return None

    database_id_env = notion_cfg.get("database_id_env", "")
    if not database_id_env:
        return None

    database_id = os.getenv(database_id_env, "").strip()
    if not database_id:
        return None

    normalized = database_id.replace("-", "")
    return f"https://www.notion.so/{normalized}"


def _build_message(
    clusters: list[dict[str, Any]], max_items: int, max_chars: int, notion_db_url: str | None = None
) -> str:
    lines = ["Daily RSS Digest"]
    count = 0
    footer_lines = ["Notion DB", notion_db_url] if notion_db_url else []

    def _compose(candidate_lines: list[str], include_footer: bool) -> str:
        full_lines = list(candidate_lines)
        if include_footer and footer_lines:
            full_lines.extend([""] + footer_lines)
        return "\n".join(full_lines)

    def append_block(block_lines: list[str]) -> bool:
        candidate_lines = lines + [""] + block_lines
        candidate = _compose(candidate_lines, include_footer=True)
        if len(candidate) > max_chars:
            return False
        lines[:] = candidate_lines
        return True

    for cluster in clusters:
        for item in cluster.get("items", []):
            if count >= max_items:
                break

            block_lines = [
                f"{count + 1}. {item['title']}",
                f"Source: {item['source']} | Score: {_format_score(item.get('score'))}",
                item.get("url", ""),
            ]
            if not append_block(block_lines):
                logger.warning("WhatsApp message hit max chars after %d items", count)
                return _compose(lines, include_footer=True)[:max_chars]
            count += 1
        if count >= max_items:
            break

    message = _compose(lines, include_footer=True)
    if len(message) > max_chars and footer_lines:
        logger.warning("WhatsApp message exceeded max chars even after reserving Notion DB link")
        return _compose(["Daily RSS Digest"], include_footer=True)[:max_chars]
    return message[:max_chars]


def _send_twilio(message: str, cfg: dict[str, Any]) -> None:
    sid = os.getenv(cfg.get("sid_env", ""))
    token = os.getenv(cfg.get("token_env", ""))
    to_num = os.getenv(cfg.get("to_env", ""))
    from_num = os.getenv(cfg.get("from_env", ""))

    if not all([sid, token, to_num, from_num]):
        logger.warning("Twilio WhatsApp enabled but required env vars are missing")
        return

    try:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": f"whatsapp:{to_num}", "From": f"whatsapp:{from_num}", "Body": message},
            auth=(sid, token),
            timeout=20,
        )
        if response.status_code >= 300:
            logger.error("Twilio send failed (%s): %s", response.status_code, response.text)
        else:
            logger.info("WhatsApp digest sent")
    except requests.RequestException as exc:
        logger.error("WhatsApp request failed: %s", exc)


def send_digest(clusters: list[dict[str, Any]], whatsapp_cfg: dict[str, Any], notion_cfg: dict[str, Any] | None = None) -> None:
    if not whatsapp_cfg.get("enabled", False):
        logger.info("WhatsApp sync disabled")
        return

    notion_db_url = _notion_database_url(notion_cfg)
    message = _build_message(
        clusters,
        max_items=int(whatsapp_cfg.get("max_items", 5)),
        max_chars=int(whatsapp_cfg.get("max_message_chars", 1500)),
        notion_db_url=notion_db_url,
    )

    provider = whatsapp_cfg.get("provider", "twilio").lower()
    if provider == "twilio":
        _send_twilio(message, whatsapp_cfg)
    elif provider == "meta":
        logger.warning("Meta WhatsApp provider scaffold not implemented yet")
    else:
        logger.error("Unsupported WhatsApp provider: %s", provider)
