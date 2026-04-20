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

from app.agent.skills import load_skill_texts
from app.agent.slack_templates import build_slack_template_prompt
from app.config import AppSettings
from app.schemas import AgentDecision, FetchedData, RunRequest
from app.tools.local_script import run_local_script


logger = logging.getLogger(__name__)

MAX_PREVIEW_CHARS = 12000
MAX_LIST_ITEMS = 20
MAX_STRING_CHARS = 500
MAX_NESTED_DEPTH = 6


BASE_INSTRUCTIONS = """
You are a scheduled operations agent.

Your job is to inspect fetched data, optionally use tools, and return a structured decision.
Use tools when they can improve correctness.
Only request a Slack notification when the information is actionable or materially important.
If you set should_notify_slack to false, leave slack_message and slack_sections as null.
Keep summaries concise and factual.
When a structured Slack template is provided, populate slack_sections using the exact section keys and follow every section rule.
When no structured Slack template is provided, populate slack_message.text directly if you choose to notify Slack.
Do not invent fields or sections that are not supported by the fetched data.
""".strip()


@dataclass
class AgentDependencies:
    request: RunRequest
    workspace_dir: Path
    allowed_script_dir: Path
    skill_texts: list[str]


def _shrink_for_prompt(value: Any, depth: int = 0) -> Any:
    if depth >= MAX_NESTED_DEPTH:
        return "<truncated nested content>"

    if isinstance(value, dict):
        return {key: _shrink_for_prompt(item, depth + 1) for key, item in value.items()}

    if isinstance(value, list):
        kept_items = [_shrink_for_prompt(item, depth + 1) for item in value[:MAX_LIST_ITEMS]]
        remaining_items = len(value) - len(kept_items)
        if remaining_items > 0:
            kept_items.append(f"<truncated {remaining_items} more items>")
        return kept_items

    if isinstance(value, str) and len(value) > MAX_STRING_CHARS:
        return f"{value[:MAX_STRING_CHARS]}<truncated {len(value) - MAX_STRING_CHARS} chars>"

    return value


def build_data_preview(data: list[FetchedData]) -> str:
    compact_items = []
    for item in data:
        compact_items.append(
            {
                "source": item.source,
                "fetched_at": item.fetched_at.isoformat(),
                "text_summary": item.text_summary,
                "payload": _shrink_for_prompt(item.payload),
            }
        )

    preview = json.dumps(compact_items, ensure_ascii=True, separators=(",", ":")) if compact_items else "[]"
    if len(preview) > MAX_PREVIEW_CHARS:
        logger.info(
            "Trimmed agent data preview from chars=%s to chars=%s",
            len(preview),
            MAX_PREVIEW_CHARS,
        )
        return f"{preview[:MAX_PREVIEW_CHARS]}...<truncated {len(preview) - MAX_PREVIEW_CHARS} chars>"

    logger.info("Prepared agent data preview chars=%s", len(preview))
    return preview


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
                "slack_sections": None,
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
        skill_block = "\n\n".join(ctx.deps.skill_texts) if ctx.deps.skill_texts else "No extra skills loaded."
        data_preview = build_data_preview(request.data)
        slack_template_block = build_slack_template_prompt(request.slack_template)
        return (
            f"Job name: {request.job_name}\n"
            f"Trigger: {request.trigger}\n"
            f"Job prompt: {request.job_prompt or 'None'}\n"
            f"Slack output contract:\n{slack_template_block}\n\n"
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

    return agent


async def run_agent(
    request: RunRequest,
    settings: AppSettings,
    workspace_dir: Path,
    toolsets: list[object] | None = None,
) -> AgentDecision:
    selected_toolsets = toolsets or []
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
        skill_texts=load_skill_texts(request.skill_ids),
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
