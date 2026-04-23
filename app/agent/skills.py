from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LoadedSkill:
    skill_id: str
    name: str
    description: str | None
    content: str
    base_dir: Path
    scripts_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)


def _parse_skill_file(raw_text: str) -> tuple[dict[str, Any], str]:
    if not raw_text.startswith("---\n"):
        return {}, raw_text.strip()

    _, remainder = raw_text.split("---\n", 1)
    frontmatter_text, separator, body = remainder.partition("\n---\n")
    if not separator:
        return {}, raw_text.strip()

    metadata = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Skill frontmatter must be a YAML mapping.")

    return metadata, body.strip()


def load_skills(skill_ids: list[str], skills_dir: Path | None = None) -> list[LoadedSkill]:
    directory = skills_dir or Path("skills")
    loaded: list[LoadedSkill] = []
    for skill_id in skill_ids:
        skill_dir = directory / skill_id
        skill_path = skill_dir / "SKILL.md"
        raw_text = skill_path.read_text(encoding="utf-8")
        metadata, content = _parse_skill_file(raw_text)
        loaded.append(
            LoadedSkill(
                skill_id=skill_id,
                name=str(metadata.get("name") or skill_id),
                description=metadata.get("description"),
                content=content,
                base_dir=skill_dir,
                scripts_dir=skill_dir / "scripts",
                metadata=metadata,
            )
        )
    return loaded


def build_skill_prompt(skills: list[LoadedSkill]) -> str:
    if not skills:
        return "No extra skills loaded."

    parts: list[str] = []
    for skill in skills:
        available_scripts = []
        if skill.scripts_dir.is_dir():
            available_scripts = sorted(path.name for path in skill.scripts_dir.iterdir() if path.is_file())
        header = f"Skill: {skill.name} (id: {skill.skill_id})"
        description = f"Description: {skill.description}" if skill.description else None
        script_line = (
            f"Available scripts: {', '.join(available_scripts)}"
            if available_scripts
            else "Available scripts: none"
        )
        block_lines = [header]
        if description:
            block_lines.append(description)
        block_lines.append(script_line)
        block_lines.append(skill.content)
        parts.append("\n".join(block_lines))
    return "\n\n".join(parts)
