# Scheduled Agent MVP

Minimal Python agent runtime for this flow:

1. `cron` triggers a job
2. runner fetches data from a configured source such as an HTTP API or `gh`
3. data is normalized into Pydantic models
4. PydanticAI runs an agent loop with local tools and optional MCP tools
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

## MCP

The sample job enables a local stdio MCP server:

```bash
.venv/bin/python -m app.mcp_server
```

The runner starts that server automatically through PydanticAI when the job uses stdio transport.

## Fetch Sources

Jobs can fetch from either an HTTP API or the GitHub CLI.

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
- long strings are truncated
- large lists are capped to the first 20 items
- nested content is depth-limited

This keeps large GitHub payloads from overwhelming local model inference.

## Slack Templates

Each job can optionally provide a structured `slack_template`. When present, the agent must fill `slack_content` using the declared section keys, and the runner validates and renders the final `slack_message.text` deterministically.

Example:

```yaml
name: github_daily_activity
prompt: >-
  Summarize the most important GitHub activity for the requested day.
slack_template:
  title: GitHub Daily Report - ${GITHUB_ACTIVITY_DATE}
  tone: clear and actionable
  audience: team
  sections:
    - key: completed
      label: Today's Work
      type: bullet_list
      required: true
      min_items: 3
      max_items: 8
      instruction: Each bullet should include the action, the target, and the specific outcome. Keep the detail concrete instead of over-summarizing. When the source is GitHub activity, include the GitHub URL in each relevant bullet.
skills:
  - digest
fetch:
  type: gh_cli
  args:
    - api
    - users/${GITHUB_USERNAME}/events?per_page=20
```

Supported section types in the MVP are:

- `paragraph`: a single string value, optionally constrained by `min_chars`
- `bullet_list`: a list of strings, optionally constrained by `min_items` and `max_items`

If the agent returns invalid `slack_content`, the runner fails the job instead of sending a partial Slack message.

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
