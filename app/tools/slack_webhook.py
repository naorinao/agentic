from __future__ import annotations

import logging

import httpx

from app.schemas import SlackMessage


logger = logging.getLogger(__name__)


async def send_slack_webhook(webhook_url: str, message: SlackMessage) -> None:
    logger.info("Sending Slack webhook message")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=message.model_dump())
        response.raise_for_status()
    logger.info("Slack webhook delivered successfully with status=%s", response.status_code)
