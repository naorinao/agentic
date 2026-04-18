from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import FetchedData, GhCLIFetchConfig


async def fetch_gh_cli(config: GhCLIFetchConfig, workspace_dir: Path) -> FetchedData:
    try:
        process = await asyncio.create_subprocess_exec(
            "gh",
            *config.args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_dir),
        )
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI `gh` is not installed or not available in PATH") from exc

    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        error_message = stderr or stdout.strip() or "unknown gh error"
        raise RuntimeError(f"gh command failed with exit code {process.returncode}: {error_message}")

    payload: dict[str, Any]
    trimmed_stdout = stdout.strip()
    if not trimmed_stdout:
        payload = {}
    else:
        try:
            json_payload = json.loads(trimmed_stdout)
        except json.JSONDecodeError:
            payload = {"text": stdout}
        else:
            payload = json_payload if isinstance(json_payload, dict) else {"items": json_payload}

    return FetchedData(
        source=f"gh {' '.join(config.args)}".strip(),
        fetched_at=datetime.now(timezone.utc),
        payload=payload,
        text_summary=config.summary_hint,
    )
