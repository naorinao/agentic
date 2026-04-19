from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field, HttpUrl, model_validator


class FetchedData(BaseModel):
    source: str
    fetched_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    text_summary: str | None = None


class SlackSectionTemplate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    type: Literal["paragraph", "bullet_list"]
    required: bool = True
    instruction: str | None = None
    min_chars: int | None = Field(default=None, ge=1)
    min_items: int | None = Field(default=None, ge=1)
    max_items: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_section_rules(self) -> "SlackSectionTemplate":
        if self.type == "paragraph":
            if self.min_items is not None or self.max_items is not None:
                raise ValueError("paragraph sections cannot define min_items or max_items")
            return self

        if self.min_chars is not None:
            raise ValueError("bullet_list sections cannot define min_chars")
        if self.min_items is not None and self.max_items is not None and self.min_items > self.max_items:
            raise ValueError("min_items cannot be greater than max_items")
        return self


class SlackTemplate(BaseModel):
    title: str
    tone: str | None = None
    audience: str | None = None
    sections: list[SlackSectionTemplate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "SlackTemplate":
        keys = [section.key for section in self.sections]
        duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
        if duplicate_keys:
            duplicates = ", ".join(duplicate_keys)
            raise ValueError(f"slack template section keys must be unique: {duplicates}")
        return self


SlackContentValue: TypeAlias = str | list[str]


class RunRequest(BaseModel):
    job_name: str
    trigger: Literal["manual", "cron"]
    data: list[FetchedData]
    skill_ids: list[str] = Field(default_factory=list)
    job_prompt: str | None = None
    slack_template: SlackTemplate | None = None


class SlackMessage(BaseModel):
    text: str


class AgentDecision(BaseModel):
    summary: str = Field(description="Short summary of the fetched information.")
    should_notify_slack: bool = Field(description="Whether the runner should post to Slack.")
    slack_content: dict[str, SlackContentValue] | None = Field(
        default=None,
        description="Structured Slack content that matches the configured template when one is provided.",
    )
    slack_message: SlackMessage | None = Field(
        default=None,
        description="Plain-text Slack webhook payload to send when no structured template is configured.",
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
    slack_template: SlackTemplate | None = None
    skills: list[str] = Field(default_factory=list)
    fetch: FetchConfig
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
