from __future__ import annotations

import asyncio
from pathlib import Path


async def run_local_script(
    workspace_dir: Path,
    allowed_script_dir: Path,
    script_path: str,
    args: list[str] | None = None,
) -> dict[str, str | int | bool]:
    resolved_allowed_dir = (workspace_dir / allowed_script_dir).resolve()
    resolved_script = (workspace_dir / script_path).resolve()

    if not resolved_script.is_file():
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"Script not found: {script_path}"}

    if not str(resolved_script).startswith(str(resolved_allowed_dir)):
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Script must live under {resolved_allowed_dir}",
        }

    process = await asyncio.create_subprocess_exec(
        str(resolved_script),
        *(args or []),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(workspace_dir),
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    return {
        "ok": process.returncode == 0,
        "exit_code": int(process.returncode or 0),
        "stdout": stdout_bytes.decode("utf-8", errors="replace"),
        "stderr": stderr_bytes.decode("utf-8", errors="replace"),
    }
