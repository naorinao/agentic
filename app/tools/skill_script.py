from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any


async def run_skill_script_dir(
    scripts_dir: Path,
    script_name: str,
    args: list[str] | None = None,
) -> dict[str, Any]:
    resolved_scripts_dir = scripts_dir.resolve()
    resolved_script = (scripts_dir / script_name).resolve()

    if not resolved_script.is_relative_to(resolved_scripts_dir):
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Script must live under {resolved_scripts_dir}",
            "payload": None,
        }

    if not resolved_script.is_file():
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Script not found: {script_name}",
            "payload": None,
        }

    command = [str(resolved_script), *(args or [])]
    if resolved_script.suffix == ".py":
        command = [sys.executable, str(resolved_script), *(args or [])]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(resolved_scripts_dir.parent),
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    payload: Any = None
    stripped_stdout = stdout.strip()
    if stripped_stdout:
        try:
            payload = json.loads(stripped_stdout)
        except json.JSONDecodeError:
            payload = None

    return {
        "ok": process.returncode == 0,
        "exit_code": int(process.returncode or 0),
        "stdout": stdout,
        "stderr": stderr,
        "payload": payload,
    }
