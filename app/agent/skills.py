from __future__ import annotations

from pathlib import Path


def load_skill_texts(skill_ids: list[str], skills_dir: Path | None = None) -> list[str]:
    directory = skills_dir or Path("skills")
    texts: list[str] = []
    for skill_id in skill_ids:
        skill_path = directory / f"{skill_id}.md"
        texts.append(skill_path.read_text(encoding="utf-8").strip())
    return texts
