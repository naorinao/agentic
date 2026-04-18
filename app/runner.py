from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.agent.main import run_agent
from app.agent.mcp_tools import build_mcp_servers
from app.config import load_job_config, load_settings
from app.fetchers import fetch_data
from app.schemas import RunRequest
from app.tools.slack_webhook import send_slack_webhook


async def run_job(job_name: str, trigger: str, dry_run: bool) -> None:
    settings = load_settings()
    workspace_dir = Path.cwd()
    job = load_job_config(job_name)

    fetched_data = await fetch_data(
        job.fetch,
        timeout_seconds=settings.fetch_timeout_seconds,
        workspace_dir=workspace_dir,
    )
    run_request = RunRequest(
        job_name=job.name,
        trigger=trigger,
        data=[fetched_data],
        skill_ids=job.skills,
        job_prompt=job.prompt,
    )

    mcp_servers = build_mcp_servers(job.mcp)
    decision = await run_agent(
        request=run_request,
        settings=settings,
        workspace_dir=workspace_dir,
        toolsets=mcp_servers,
    )

    print(decision.model_dump_json(indent=2))

    webhook_url = settings.slack_webhook_url
    if decision.should_notify_slack and decision.slack_message and not dry_run:
        if not webhook_url:
            raise RuntimeError("Slack notification requested, but SLACK_WEBHOOK_URL is not set")
        await send_slack_webhook(webhook_url, decision.slack_message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a scheduled agent job")
    parser.add_argument("--job", required=True, help="Job name matching jobs/<job>.yaml")
    parser.add_argument(
        "--trigger",
        default="manual",
        choices=["manual", "cron"],
        help="Trigger type for the current run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the agent but skip outbound Slack delivery",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run_job(job_name=args.job, trigger=args.trigger, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
