from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class FetchedData(BaseModel):
    source: str
    fetched_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    text_summary: str | None = None


class RunRequest(BaseModel):
    job_name: str
    trigger: Literal["manual", "cron"]
    data: list[FetchedData]
    skill_ids: list[str] = Field(default_factory=list)
    job_prompt: str | None = None


class SlackMessage(BaseModel):
    text: str


class AgentDecision(BaseModel):
    summary: str = Field(description="Short summary of the fetched information.")
    should_notify_slack: bool = Field(description="Whether the runner should post to Slack.")
    slack_message: SlackMessage | None = Field(
        default=None,
        description="Slack webhook payload to send when a notification is needed.",
    )
    follow_up_actions: list[str] = Field(default_factory=list)


class HttpAPIFetchConfig(BaseModel):
    type: Literal["http_api"] = "http_api"
    url: HttpUrl
    method: Literal["GET", "POST"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    summary_hint: str | None = None


class GhCLIFetchConfig(BaseModel):
    type: Literal["gh_cli"] = "gh_cli"
    args: list[str] = Field(default_factory=list)
    summary_hint: str | None = None


FetchConfig = Annotated[HttpAPIFetchConfig | GhCLIFetchConfig, Field(discriminator="type")]


class MCPConfig(BaseModel):
    enabled: bool = False
    transport: Literal["stdio", "streamable-http"] = "stdio"
    command: str = "python"
    args: list[str] = Field(default_factory=lambda: ["-m", "app.mcp_server"])
    url: str | None = None
    tool_prefix: str | None = None
    include_instructions: bool = True


class NotifyConfig(BaseModel):
    slack_webhook_env: str = "SLACK_WEBHOOK_URL"


class JobConfig(BaseModel):
    name: str
    prompt: str | None = None
    skills: list[str] = Field(default_factory=list)
    fetch: FetchConfig
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
