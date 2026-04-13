from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _build_message(clusters: list[dict[str, Any]], max_items: int, max_chars: int) -> str:
    lines = ["Daily RSS Digest"]
    count = 0
    for cluster in clusters:
        for item in cluster.get("items", []):
            if count >= max_items:
                break
            lines.append(f"- {item['title']} ({item['source']})")
            count += 1
        if count >= max_items:
            break
    message = "\n".join(lines)
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


def send_digest(clusters: list[dict[str, Any]], whatsapp_cfg: dict[str, Any]) -> None:
    if not whatsapp_cfg.get("enabled", False):
        logger.info("WhatsApp sync disabled")
        return

    message = _build_message(
        clusters,
        max_items=int(whatsapp_cfg.get("max_items", 5)),
        max_chars=int(whatsapp_cfg.get("max_message_chars", 1500)),
    )

    provider = whatsapp_cfg.get("provider", "twilio").lower()
    if provider == "twilio":
        _send_twilio(message, whatsapp_cfg)
    elif provider == "meta":
        logger.warning("Meta WhatsApp provider scaffold not implemented yet")
    else:
        logger.error("Unsupported WhatsApp provider: %s", provider)
