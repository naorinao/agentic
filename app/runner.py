from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from app.agent.main import run_agent
from app.agent.mcp_tools import build_mcp_servers
from app.agent.slack_templates import finalize_slack_decision
from app.config import load_job_config, load_settings
from app.fetchers import fetch_data
from app.logging_config import configure_logging
from app.schemas import RunRequest
from app.tools.slack_webhook import send_slack_webhook


logger = logging.getLogger(__name__)


async def run_job(job_name: str, trigger: str, dry_run: bool, log_level: str | None = None) -> None:
    settings = load_settings()
    configure_logging(log_level or settings.log_level)
    workspace_dir = Path.cwd()
    logger.info("Starting job run job=%s trigger=%s dry_run=%s workspace=%s", job_name, trigger, dry_run, workspace_dir)
    job = load_job_config(job_name)
    logger.info("Loaded job configuration for %s", job.name)

    logger.info("Beginning fetch step")
    fetched_data = await fetch_data(
        job.fetch,
        timeout_seconds=settings.fetch_timeout_seconds,
        workspace_dir=workspace_dir,
    )
    logger.info("Fetch step completed source=%s", fetched_data.source)
    run_request = RunRequest(
        job_name=job.name,
        trigger=trigger,
        data=[fetched_data],
        skill_ids=job.skills,
        job_prompt=job.prompt,
        slack_template=job.slack_template,
    )

    logger.info("Building MCP tool configuration")
    mcp_servers = build_mcp_servers(job.mcp)
    logger.info("MCP configuration ready toolsets=%s", len(mcp_servers))
    logger.info("Starting agent step")
    decision = await run_agent(
        request=run_request,
        settings=settings,
        workspace_dir=workspace_dir,
        toolsets=mcp_servers,
    )
    decision = finalize_slack_decision(decision, job.slack_template)
    logger.info("Agent step completed")

    print(decision.model_dump_json(indent=2))

    webhook_url = settings.slack_webhook_url
    if decision.should_notify_slack and decision.slack_message and not dry_run:
        if not webhook_url:
            raise RuntimeError("Slack notification requested, but SLACK_WEBHOOK_URL is not set")
        logger.info("Starting Slack delivery")
        await send_slack_webhook(webhook_url, decision.slack_message)
    elif dry_run:
        logger.info("Skipping Slack delivery because dry_run=true")
    else:
        logger.info("Skipping Slack delivery because agent did not request it")
    logger.info("Job run finished job=%s", job.name)


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
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level for this run",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        configure_logging("INFO")
        asyncio.run(
            run_job(
                job_name=args.job,
                trigger=args.trigger,
                dry_run=args.dry_run,
                log_level=args.log_level,
            )
        )
    except Exception:
        logger.exception("Job run failed")
        raise


if __name__ == "__main__":
    main()
