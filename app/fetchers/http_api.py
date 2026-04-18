from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.schemas import FetchedData, HttpAPIFetchConfig


async def fetch_http_api(config: HttpAPIFetchConfig, timeout_seconds: int) -> FetchedData:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.request(
            config.method,
            str(config.url),
            headers=config.headers,
            params=config.params,
            json=config.json_body,
        )
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    payload: dict[str, Any]
    if "application/json" in content_type:
        json_payload = response.json()
        payload = json_payload if isinstance(json_payload, dict) else {"items": json_payload}
    else:
        payload = {"text": response.text}

    return FetchedData(
        source=str(config.url),
        fetched_at=datetime.now(timezone.utc),
        payload=payload,
        text_summary=config.summary_hint,
    )
