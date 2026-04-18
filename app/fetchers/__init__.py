"""Data fetchers used by scheduled jobs."""

from __future__ import annotations

from pathlib import Path

from app.fetchers.gh_cli import fetch_gh_cli
from app.fetchers.http_api import fetch_http_api
from app.schemas import FetchConfig, FetchedData, GhCLIFetchConfig, HttpAPIFetchConfig


async def fetch_data(config: FetchConfig, timeout_seconds: int, workspace_dir: Path) -> FetchedData:
    if isinstance(config, HttpAPIFetchConfig):
        return await fetch_http_api(config, timeout_seconds=timeout_seconds)

    if isinstance(config, GhCLIFetchConfig):
        return await fetch_gh_cli(config, workspace_dir=workspace_dir)

    raise ValueError(f"Unsupported fetch config type: {type(config).__name__}")
