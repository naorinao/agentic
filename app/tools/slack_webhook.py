from __future__ import annotations

import httpx

from app.schemas import SlackMessage


async def send_slack_webhook(webhook_url: str, message: SlackMessage) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=message.model_dump())
        response.raise_for_status()
