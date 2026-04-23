from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.skills import LoadedSkill, build_skill_prompt, load_skills
from app.config import AppSettings
from app.schemas import AgentDecision, FetchedData, RunRequest
from app.tools.local_script import run_local_script
from app.tools.skill_script import run_skill_script_dir


logger = logging.getLogger(__name__)

MAX_PREVIEW_CHARS = 24000
MAX_LIST_ITEMS = 20
MAX_STRING_CHARS = 500
MAX_NESTED_DEPTH = 6
PREVIEW_LIMIT_PROFILES = (
    (20, 500, 6),
    (12, 350, 5),
    (8, 240, 4),
    (5, 160, 3),
    (3, 96, 2),
    (2, 64, 2),
    (1, 48, 1),
)


BASE_INSTRUCTIONS = """
You are a scheduled operations agent.

Your job is to inspect fetched data, optionally use tools, and return a structured decision.
Use tools when they can improve correctness.
If the job loads skill scripts that can fetch or enrich data, use them when needed.
Only request a Slack notification when the information is actionable or materially important.
If you set should_notify_slack to false, leave slack_message as null.
Keep summaries concise and factual.
If you choose to notify Slack, populate slack_message.text directly as readable plain text.
Do not invent fields that are not supported by the fetched data.
""".strip()


@dataclass
class AgentDependencies:
    request: RunRequest
    workspace_dir: Path
    allowed_script_dir: Path
    loaded_skills: list[LoadedSkill]


def _shrink_for_prompt(
    value: Any,
    *,
    max_list_items: int,
    max_string_chars: int,
    max_nested_depth: int,
    depth: int = 0,
) -> Any:
    if depth >= max_nested_depth:
        return "<truncated nested content>"

    if isinstance(value, dict):
        return {
            key: _shrink_for_prompt(
                item,
                max_list_items=max_list_items,
                max_string_chars=max_string_chars,
                max_nested_depth=max_nested_depth,
                depth=depth + 1,
            )
            for key, item in value.items()
        }

    if isinstance(value, list):
        kept_items = [
            _shrink_for_prompt(
                item,
                max_list_items=max_list_items,
                max_string_chars=max_string_chars,
                max_nested_depth=max_nested_depth,
                depth=depth + 1,
            )
            for item in value[:max_list_items]
        ]
        remaining_items = len(value) - len(kept_items)
        if remaining_items > 0:
            kept_items.append(f"<truncated {remaining_items} more items>")
        return kept_items

    if isinstance(value, str) and len(value) > max_string_chars:
        return f"{value[:max_string_chars]}<truncated {len(value) - max_string_chars} chars>"

    return value


def _build_compact_items(
    data: list[FetchedData],
    *,
    max_list_items: int,
    max_string_chars: int,
    max_nested_depth: int,
) -> list[dict[str, Any]]:
    compact_items = []
    for item in data:
        compact_items.append(
            {
                "source": item.source,
                "fetched_at": item.fetched_at.isoformat(),
                "text_summary": _shrink_for_prompt(
                    item.text_summary,
                    max_list_items=max_list_items,
                    max_string_chars=max_string_chars,
                    max_nested_depth=max_nested_depth,
                ),
                "payload": _shrink_for_prompt(
                    item.payload,
                    max_list_items=max_list_items,
                    max_string_chars=max_string_chars,
                    max_nested_depth=max_nested_depth,
                ),
            }
        )
    return compact_items


def _build_minimal_preview(data: list[FetchedData]) -> str:
    compact_items = []
    for item in data:
        compact_items.append(
            {
                "source": item.source,
                "fetched_at": item.fetched_at.isoformat(),
                "text_summary": _shrink_for_prompt(
                    item.text_summary,
                    max_list_items=1,
                    max_string_chars=48,
                    max_nested_depth=1,
                ),
                "payload": "<payload omitted after preview budget>",
            }
        )

    return json.dumps(compact_items, ensure_ascii=True, separators=(",", ":")) if compact_items else "[]"


def build_data_preview(data: list[FetchedData]) -> str:
    last_preview = "[]"
    for max_list_items, max_string_chars, max_nested_depth in PREVIEW_LIMIT_PROFILES:
        compact_items = _build_compact_items(
            data,
            max_list_items=max_list_items,
            max_string_chars=max_string_chars,
            max_nested_depth=max_nested_depth,
        )
        preview = json.dumps(compact_items, ensure_ascii=True, separators=(",", ":")) if compact_items else "[]"
        last_preview = preview
        if len(preview) <= MAX_PREVIEW_CHARS:
            if (max_list_items, max_string_chars, max_nested_depth) != PREVIEW_LIMIT_PROFILES[0]:
                logger.info(
                    "Compressed agent data preview to chars=%s using list_items=%s string_chars=%s nested_depth=%s",
                    len(preview),
                    max_list_items,
                    max_string_chars,
                    max_nested_depth,
                )
            else:
                logger.info("Prepared agent data preview chars=%s", len(preview))
            return preview

    preview = _build_minimal_preview(data)
    if len(preview) <= MAX_PREVIEW_CHARS:
        logger.info("Fell back to minimal agent data preview chars=%s", len(preview))
        return preview

    logger.info(
        "Minimal agent data preview still exceeded budget chars=%s limit=%s; returning smallest valid preview",
        len(preview),
        MAX_PREVIEW_CHARS,
    )
    return preview if len(preview) <= len(last_preview) else last_preview


def build_model(settings: AppSettings):
    provider_name = settings.model_provider.lower()
    logger.info("Building model provider=%s model=%s", provider_name, settings.model_name)
    if provider_name == "ollama":
        return OllamaModel(
            settings.model_name,
            provider=OllamaProvider(base_url=settings.model_base_url),
        )

    if provider_name == "openai-compatible":
        return OpenAIChatModel(
            settings.model_name,
            provider=OpenAIProvider(
                base_url=settings.model_base_url,
                api_key=settings.model_api_key,
            ),
            profile=OpenAIModelProfile(openai_supports_strict_tool_definition=False),
        )

    if provider_name == "test":
        return TestModel(
            custom_output_args={
                "summary": "Test provider smoke test completed successfully.",
                "should_notify_slack": False,
                "slack_message": None,
                "follow_up_actions": ["Install and start Ollama for live model runs."],
            }
        )

    raise ValueError(f"Unsupported MODEL_PROVIDER: {settings.model_provider}")


def create_agent(settings: AppSettings, toolsets: list[object]) -> Agent[AgentDependencies, AgentDecision]:
    model = build_model(settings)
    agent: Agent[AgentDependencies, AgentDecision] = Agent(
        model,
        deps_type=AgentDependencies,
        output_type=AgentDecision,
        instructions=BASE_INSTRUCTIONS,
        toolsets=toolsets,
    )

    @agent.instructions
    def inject_context(ctx: RunContext[AgentDependencies]) -> str:
        request = ctx.deps.request
        skill_block = build_skill_prompt(ctx.deps.loaded_skills)
        data_preview = build_data_preview(request.data)
        return (
            f"Job name: {request.job_name}\n"
            f"Trigger: {request.trigger}\n"
            f"Job prompt: {request.job_prompt or 'None'}\n"
            f"Loaded skills:\n{skill_block}\n\n"
            f"Fetched data preview:\n{data_preview}"
        )

    @agent.tool
    async def format_slack_message(
        ctx: RunContext[AgentDependencies],
        headline: str,
        details: list[str],
    ) -> str:
        """Format a plain-text Slack message from a headline and detail lines."""
        lines = [f"*{headline.strip()}*"]
        lines.extend(f"- {detail.strip()}" for detail in details if detail.strip())
        return "\n".join(lines)

    @agent.tool
    async def run_workspace_script(
        ctx: RunContext[AgentDependencies],
        script_path: str,
        args: list[str] | None = None,
    ) -> dict[str, str | int | bool]:
        """Run a helper script from the workspace scripts directory and return stdout and stderr."""
        return await run_local_script(
            workspace_dir=ctx.deps.workspace_dir,
            allowed_script_dir=ctx.deps.allowed_script_dir,
            script_path=script_path,
            args=args,
        )

    @agent.tool
    async def run_skill_script(
        ctx: RunContext[AgentDependencies],
        skill_id: str,
        script_name: str,
        args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a script from one of the loaded skill packages and return parsed stdout when it is JSON."""
        skill_map = {skill.skill_id: skill for skill in ctx.deps.loaded_skills}
        skill = skill_map.get(skill_id)
        if skill is None:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Skill not loaded: {skill_id}",
                "payload": None,
            }
        return await run_skill_script_dir(skill.scripts_dir, script_name=script_name, args=args)

    return agent


async def run_agent(
    request: RunRequest,
    settings: AppSettings,
    workspace_dir: Path,
    toolsets: list[object] | None = None,
) -> AgentDecision:
    selected_toolsets = toolsets or []
    loaded_skills = load_skills(request.skill_ids)
    logger.info(
        "Starting agent run for job=%s trigger=%s toolsets=%s skills=%s",
        request.job_name,
        request.trigger,
        len(selected_toolsets),
        request.skill_ids,
    )
    deps = AgentDependencies(
        request=request,
        workspace_dir=workspace_dir,
        allowed_script_dir=settings.allowed_script_dir,
        loaded_skills=loaded_skills,
    )
    agent = create_agent(settings=settings, toolsets=selected_toolsets)
    async with agent:
        result = await agent.run("Analyze the fetched data and decide whether to notify Slack.", deps=deps)
    logger.info(
        "Agent run completed for job=%s should_notify_slack=%s follow_up_actions=%s",
        request.job_name,
        result.output.should_notify_slack,
        len(result.output.follow_up_actions),
    )
    return result.output
