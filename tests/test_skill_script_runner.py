from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.tools.skill_script import run_skill_script_dir


class SkillScriptRunnerTests(unittest.TestCase):
    def test_run_skill_script_dir_executes_python_script_and_parses_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scripts_dir = Path(tmp_dir) / "scripts"
            scripts_dir.mkdir()
            script_path = scripts_dir / "emit.py"
            script_path.write_text(
                "import json\n"
                "import sys\n"
                "print(json.dumps({'message': 'ok', 'args': sys.argv[1:]}))\n",
                encoding="utf-8",
            )

            result = asyncio.run(run_skill_script_dir(scripts_dir, "emit.py", args=["alice", "2026-04-23"]))

            self.assertTrue(result["ok"])
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["payload"], {"message": "ok", "args": ["alice", "2026-04-23"]})

    def test_run_skill_script_dir_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            scripts_dir = Path(tmp_dir) / "scripts"
            scripts_dir.mkdir()
            outside_script = Path(tmp_dir) / "outside.py"
            outside_script.write_text("print('nope')\n", encoding="utf-8")

            result = asyncio.run(run_skill_script_dir(scripts_dir, "../outside.py"))

            self.assertFalse(result["ok"])
            self.assertIn("must live under", result["stderr"])


if __name__ == "__main__":
    unittest.main()
