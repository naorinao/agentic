from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas import JobConfig


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_provider: str = Field(default="openai-compatible", alias="MODEL_PROVIDER")
    model_name: str = Field(default="qwen3", alias="MODEL_NAME")
    model_base_url: str = Field(default="http://localhost:11434/v1", alias="MODEL_BASE_URL")
    model_api_key: str = Field(default="ollama", alias="MODEL_API_KEY")
    fetch_timeout_seconds: int = Field(default=30, alias="FETCH_TIMEOUT_SECONDS")
    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    allowed_script_dir: Path = Field(default=Path("scripts"), alias="ALLOWED_SCRIPT_DIR")


def load_settings() -> AppSettings:
    return AppSettings()


def load_job_config(job_name: str, jobs_dir: Path | None = None) -> JobConfig:
    jobs_path = jobs_dir or Path("jobs")
    job_path = jobs_path / f"{job_name}.yaml"
    raw_text = os.path.expandvars(job_path.read_text(encoding="utf-8"))
    raw_data = yaml.safe_load(raw_text)
    return JobConfig.model_validate(raw_data)
