# Scheduled Agent MVP

Minimal Python agent runtime for this flow:

1. `cron` triggers a job
2. runner optionally fetches data from a configured source such as an HTTP API or `gh`
3. data is normalized into Pydantic models when a fetch step is configured
4. PydanticAI runs an agent loop with local tools, skill-scoped scripts, and optional MCP tools
5. runner validates the structured result
6. runner sends a Slack webhook when requested

## Stack

- Python 3.11+
- PydanticAI
- Ollama via native provider or OpenAI-compatible endpoint
- MCP Python SDK / FastMCP
- httpx
- cron

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Ollama

Start Ollama and make sure your model is available:

```bash
ollama serve
ollama pull qwen3
```

Default `.env` settings assume the OpenAI-compatible endpoint:

```env
MODEL_PROVIDER=openai-compatible
MODEL_NAME=qwen3
MODEL_BASE_URL=http://localhost:11434/v1
MODEL_API_KEY=ollama
LOG_LEVEL=INFO
```

If you want the dedicated Ollama provider instead:

```env
MODEL_PROVIDER=ollama
MODEL_NAME=qwen3
MODEL_BASE_URL=http://localhost:11434/v1
```

If you want a no-LLM smoke test for local development:

```bash
MODEL_PROVIDER=test .venv/bin/python -m app.runner --job daily_digest --dry-run
```

## Run

Copy `.env.example` to `.env` and update your webhook if you want live Slack delivery.

Dry run:

```bash
.venv/bin/python -m app.runner --job daily_digest --dry-run
```

Debug run with verbose logs:

```bash
.venv/bin/python -m app.runner --job daily_digest --dry-run --log-level DEBUG
```

Live run:

```bash
.venv/bin/python -m app.runner --job daily_digest
```

Pure skill-driven GitHub daily run:

```bash
.venv/bin/python -m app.runner --job github_daily_activity --dry-run
```

## MCP

The sample job enables a local stdio MCP server:

```bash
.venv/bin/python -m app.mcp_server
```

The runner starts that server automatically through PydanticAI when the job uses stdio transport.

## Fetch Sources

Jobs can fetch from either an HTTP API or the GitHub CLI, or skip the fetch step entirely and let the agent call skill scripts.

HTTP API example:

```yaml
fetch:
  type: http_api
  url: https://jsonplaceholder.typicode.com/todos/1
  method: GET
  summary_hint: Example API payload for validating the MVP pipeline.
```

GitHub CLI example:

```yaml
fetch:
  type: gh_cli
  args:
    - api
    - repos/owner/repo/issues
    - --method
    - GET
  summary_hint: Open issues fetched from GitHub via gh.
```

For `gh_cli`, the runner executes `gh` from the workspace directory and tries to parse stdout as JSON. If stdout is not JSON, it is stored as plain text instead.

Before fetched data is sent to the model, the runner compacts it for prompt efficiency:

- pretty-printed JSON is removed
- long strings are progressively truncated when needed
- large lists are progressively capped when needed
- nested content is progressively depth-limited when needed
- the preview stays as valid JSON instead of being cut mid-string

This keeps large GitHub payloads from overwhelming local model inference.

## Skills

This repo uses skill packages under `skills/<skill_id>/SKILL.md`. Each skill can also ship local resources such as `scripts/` or `reference/`. This keeps job YAML small and lets a skill bundle its own controlled automation.

Example:

```yaml
name: github_daily_activity
prompt: >-
  Target GitHub username: octocat.
  Use local-time today unless a different date is explicitly requested.
skills:
  - default
  - digest
  - github_daily_activity
```

When the agent decides to notify Slack, it should populate `slack_message.text` directly. The runner validates that plain-text message exists before delivery.

Skill packages can expose scripts. The agent can call them through the built-in `run_skill_script(skill_id, script_name, args)` tool, but only for skills loaded by the current job.

Typical pattern:

- `skills/default/SKILL.md`: shared operating rules
- `skills/digest/SKILL.md`: reusable formatting heuristics
- `skills/<task>/SKILL.md`: the task contract for one concrete job
- `skills/<task>/scripts/*`: controlled automation owned by that skill

Example package layout:

```text
skills/
  github_daily_activity/
    SKILL.md
    scripts/
      fetch_activity.py
```

The sample `github_daily_activity` job is pure skill-driven: it does not define a `fetch:` block, and the agent uses the skill script to collect GitHub activity for the configured user.

## Cron

Example cron entry:

```cron
*/30 * * * * /home/woshahua/Work/agentic/.venv/bin/python -m app.runner --job daily_digest --trigger cron >> /tmp/scheduled-agent.log 2>&1
```

## Project Layout

```text
app/
  agent/
  fetchers/
  tools/
  config.py
  mcp_server.py
  runner.py
  schemas.py
jobs/
skills/
```
