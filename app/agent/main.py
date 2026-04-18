from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.agent.skills import load_skill_texts
from app.config import AppSettings
from app.schemas import AgentDecision, RunRequest
from app.tools.local_script import run_local_script


logger = logging.getLogger(__name__)


BASE_INSTRUCTIONS = """
You are a scheduled operations agent.

Your job is to inspect fetched data, optionally use tools, and return a structured decision.
Use tools when they can improve correctness.
Only request a Slack notification when the information is actionable or materially important.
If you set should_notify_slack to false, leave slack_message as null.
Keep summaries concise and factual.
""".strip()


@dataclass
class AgentDependencies:
    request: RunRequest
    workspace_dir: Path
    allowed_script_dir: Path
    skill_texts: list[str]


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
        skill_block = "\n\n".join(ctx.deps.skill_texts) if ctx.deps.skill_texts else "No extra skills loaded."
        data_preview = request.data[0].model_dump_json(indent=2) if request.data else "{}"
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
