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
