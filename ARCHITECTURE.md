# Scheduled Agent MVP Architecture

This document captures the current repository architecture based on the implementation under `app/`, `jobs/`, and `skills/`.

<style scoped>
.arch-diagram{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#0f172a;background:linear-gradient(180deg,#f8fbff 0%,#f5f7fb 100%);border:1px solid #dbe4f0;border-radius:20px;padding:20px;box-shadow:0 10px 30px rgba(15,23,42,.08);overflow:hidden}
.arch-title{font-size:26px;font-weight:800;letter-spacing:-.02em;margin:0 0 6px 0;color:#0f172a}
.arch-subtitle{font-size:13px;color:#475569;margin:0 0 16px 0}
.arch-wrapper{display:flex;gap:16px;align-items:flex-start}
.arch-sidebar{width:240px;display:flex;flex-direction:column;gap:12px}
.arch-main{flex:1;display:flex;flex-direction:column;gap:12px}
.arch-sidebar-panel,.arch-layer{border-radius:16px;border:1px solid rgba(148,163,184,.28);background:rgba(255,255,255,.86);backdrop-filter:blur(8px);box-shadow:0 4px 14px rgba(148,163,184,.12)}
.arch-sidebar-panel{padding:12px}
.arch-sidebar-title{font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#334155;margin-bottom:10px}
.arch-sidebar-item{font-size:12px;line-height:1.45;padding:8px 10px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0;color:#334155;margin-bottom:8px}
.arch-sidebar-item.metric{background:#eaf4ff;border-color:#bfdbfe;color:#1d4ed8;font-weight:700}
.arch-layer{padding:14px}
.arch-layer-title{font-size:14px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px 0}
.arch-layer.user{background:linear-gradient(180deg,#eff6ff 0%,#dbeafe 100%);border-color:#bfdbfe}
.arch-layer.user .arch-layer-title{color:#1d4ed8}
.arch-layer.application{background:linear-gradient(180deg,#f5f3ff 0%,#ede9fe 100%);border-color:#d8b4fe}
.arch-layer.application .arch-layer-title{color:#6d28d9}
.arch-layer.ai{background:linear-gradient(180deg,#fff7ed 0%,#ffedd5 100%);border-color:#fdba74}
.arch-layer.ai .arch-layer-title{color:#c2410c}
.arch-layer.data{background:linear-gradient(180deg,#ecfeff 0%,#cffafe 100%);border-color:#67e8f9}
.arch-layer.data .arch-layer-title{color:#0f766e}
.arch-layer.infra{background:linear-gradient(180deg,#f8fafc 0%,#e2e8f0 100%);border-color:#cbd5e1}
.arch-layer.infra .arch-layer-title{color:#334155}
.arch-layer.external{background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);border:1.5px dashed #94a3b8}
.arch-layer.external .arch-layer-title{color:#475569}
.arch-grid{display:grid;gap:10px}
.arch-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.arch-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.arch-grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.arch-box{border-radius:12px;padding:10px 12px;background:rgba(255,255,255,.72);border:1px solid rgba(255,255,255,.9);font-size:13px;line-height:1.35;color:#0f172a;min-height:58px}
.arch-box small{display:block;margin-top:4px;color:#475569;font-size:11px;line-height:1.35}
.arch-box.highlight{box-shadow:inset 0 0 0 2px rgba(59,130,246,.25);background:#ffffff}
.arch-box.tech{min-height:auto;padding:8px 10px;font-size:12px}
.arch-subgroup{display:flex;gap:10px;margin-top:10px}
.arch-subgroup-box{flex:1;border-radius:12px;padding:10px;background:rgba(255,255,255,.46);border:1px solid rgba(148,163,184,.25)}
.arch-subgroup-title{font-size:11px;font-weight:800;color:#334155;text-transform:uppercase;letter-spacing:.06em;text-align:center;margin-bottom:8px}
.arch-user-types{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:8px}
.arch-user-tag{font-size:10px;padding:3px 8px;border-radius:999px;background:rgba(59,130,246,.12);color:#1d4ed8;font-weight:700}
@media (max-width:1100px){.arch-wrapper{flex-direction:column}.arch-sidebar{width:auto}.arch-grid-4{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:700px){.arch-grid-2,.arch-grid-3,.arch-grid-4{grid-template-columns:1fr}.arch-subgroup{flex-direction:column}}
</style>
<div class="arch-diagram">
<div class="arch-title">Scheduled Agent MVP</div>
<div class="arch-subtitle">Current architecture derived from <code>app/runner.py</code>, agent modules, fetchers, tools, job YAML, and skill files after removing the structured Slack template path.</div>
<div class="arch-wrapper">
<div class="arch-sidebar">
<div class="arch-sidebar-panel">
<div class="arch-sidebar-title">Triggers</div>
<div class="arch-sidebar-item">Manual CLI run<br><small><code>python -m app.runner --job daily_digest</code></small></div>
<div class="arch-sidebar-item">Cron scheduler<br><small>Periodic execution with <code>--trigger cron</code></small></div>
<div class="arch-sidebar-item">Dry run mode<br><small>Skips outbound Slack delivery</small></div>
</div>
<div class="arch-sidebar-panel">
<div class="arch-sidebar-title">Outputs</div>
<div class="arch-sidebar-item metric">Typed JSON Decision</div>
<div class="arch-sidebar-item">Summary, Slack decision, plain-text Slack message, follow-up actions</div>
<div class="arch-sidebar-item">Optional Slack webhook post after runner validation</div>
</div>
</div>
<div class="arch-main">
<div class="arch-layer user">
<div class="arch-layer-title">User Layer</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box highlight">Operators and Developers<br><small>Start jobs manually and inspect stdout results</small></div>
<div class="arch-box">Cron Runtime<br><small>Invokes the runner on a schedule</small></div>
<div class="arch-box">Slack Recipients<br><small>Receive actionable notifications when needed</small></div>
</div>
<div class="arch-user-types">
<span class="arch-user-tag">Operator</span>
<span class="arch-user-tag">Cron</span>
<span class="arch-user-tag">Slack Audience</span>
</div>
</div>
<div class="arch-layer application">
<div class="arch-layer-title">Application Layer</div>
<div class="arch-grid arch-grid-4">
<div class="arch-box highlight"><code>app.runner.run_job</code><br><small>Main orchestration entry point for settings, fetch, agent run, plain-text Slack validation, and notification</small></div>
<div class="arch-box"><code>load_settings()</code><br><small>Loads environment-backed application settings</small></div>
<div class="arch-box"><code>load_job_config()</code><br><small>Loads and validates <code>jobs/*.yaml</code></small></div>
<div class="arch-box"><code>fetch_data()</code><br><small>Dispatches to <code>http_api</code> or <code>gh_cli</code> fetchers</small></div>
</div>
<div class="arch-subgroup">
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">Outbound Actions</div>
<div class="arch-grid arch-grid-2">
<div class="arch-box tech"><code>send_slack_webhook()</code><br><small>Posts Slack payloads when requested</small></div>
<div class="arch-box tech"><code>finalize_agent_decision()</code><br><small>Requires <code>slack_message.text</code> when notifying and clears it otherwise</small></div>
</div>
</div>
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">Job Definition</div>
<div class="arch-grid arch-grid-2">
<div class="arch-box tech"><code>jobs/daily_digest.yaml</code><br><small>Fetch config, skill list, MCP config, notification settings</small></div>
<div class="arch-box tech"><code>skills/default.md</code> + task skill<br><small>Reusable base rules plus job-specific task contract</small></div>
</div>
</div>
</div>
</div>
<div class="arch-layer ai">
<div class="arch-layer-title">AI / Logic Layer</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box highlight"><code>create_agent()</code> and <code>run_agent()</code><br><small>PydanticAI agent loop with structured <code>AgentDecision</code> output</small></div>
<div class="arch-box">Model Routing<br><small>Supports <code>ollama</code>, <code>openai-compatible</code>, and <code>test</code></small></div>
<div class="arch-box">Context Injection<br><small>Combines base instructions, optional job prompt, loaded skill texts, and fetched data preview</small></div>
</div>
<div class="arch-subgroup">
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">Skill Loading</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box tech"><code>load_skill_texts()</code><br><small>Reads <code>skills/*.md</code> selected by the job</small></div>
<div class="arch-box tech"><code>default.md</code><br><small>Shared operating rules across jobs</small></div>
<div class="arch-box tech"><code>daily_digest_task.md</code><br><small>Task contract now lives in a skill instead of a Slack template</small></div>
</div>
</div>
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">Built-in Agent Tools</div>
<div class="arch-grid arch-grid-2">
<div class="arch-box tech"><code>format_slack_message</code><br><small>Builds readable plain-text Slack messages</small></div>
<div class="arch-box tech"><code>run_workspace_script</code><br><small>Runs helper scripts only under the allowed workspace directory</small></div>
</div>
</div>
</div>
<div class="arch-subgroup" style="margin-top:10px">
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">MCP Toolsets</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box tech"><code>build_mcp_servers()</code><br><small>Creates stdio or streamable HTTP MCP servers</small></div>
<div class="arch-box tech"><code>keyword_score</code><br><small>Deterministic urgency scoring from text</small></div>
<div class="arch-box tech"><code>suggest_audience</code><br><small>Maps urgency score to notification target</small></div>
</div>
</div>
</div>
</div>
<div class="arch-layer data">
<div class="arch-layer-title">Data Layer</div>
<div class="arch-subgroup">
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">Schemas</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box tech"><code>FetchedData</code><br><small>Normalized source, timestamp, payload, and summary hint</small></div>
<div class="arch-box tech"><code>RunRequest</code><br><small>Job name, trigger, fetched data, selected skills, and optional prompt</small></div>
<div class="arch-box tech"><code>AgentDecision</code><br><small>Summary, Slack decision, plain-text message, and follow-up actions</small></div>
</div>
</div>
<div class="arch-subgroup-box">
<div class="arch-subgroup-title">Configuration Assets</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box tech"><code>.env</code><br><small>Model provider, endpoint, API key, timeouts, webhook URL</small></div>
<div class="arch-box tech"><code>jobs/*.yaml</code><br><small>Fetch, MCP, notification, and ordered skill references</small></div>
<div class="arch-box tech"><code>skills/*.md</code><br><small>Base, formatting, and task-specific instruction fragments loaded into agent context</small></div>
</div>
</div>
</div>
</div>
<div class="arch-layer infra">
<div class="arch-layer-title">Infrastructure Layer</div>
<div class="arch-grid arch-grid-4">
<div class="arch-box">Python 3.11 Runtime<br><small>Async application execution</small></div>
<div class="arch-box">Pydantic and Settings<br><small>Validation and environment-backed configuration</small></div>
<div class="arch-box"><code>httpx</code> Async Networking<br><small>Used for both fetch and Slack webhook delivery</small></div>
<div class="arch-box">Workspace and Scripts<br><small>Controlled local execution boundary under <code>ALLOWED_SCRIPT_DIR</code></small></div>
</div>
</div>
<div class="arch-layer external">
<div class="arch-layer-title">External Services</div>
<div class="arch-grid arch-grid-3">
<div class="arch-box">LLM Provider Endpoint<br><small>Ollama or OpenAI-compatible API</small></div>
<div class="arch-box">Source HTTP API<br><small>Current demo job uses <code>jsonplaceholder.typicode.com</code></small></div>
<div class="arch-box">Slack Webhook API<br><small>Receives notifications only when the decision requires it</small></div>
</div>
</div>
</div>
<div class="arch-sidebar">
<div class="arch-sidebar-panel">
<div class="arch-sidebar-title">Controls</div>
<div class="arch-sidebar-item">Structured output still enforces a typed decision contract, but Slack content is now plain text</div>
<div class="arch-sidebar-item">Script execution is restricted to the configured allowed directory</div>
<div class="arch-sidebar-item">MCP transport can be local stdio or streamable HTTP</div>
</div>
<div class="arch-sidebar-panel">
<div class="arch-sidebar-title">Design Notes</div>
<div class="arch-sidebar-item metric">Conservative Slack Policy</div>
<div class="arch-sidebar-item">Task behavior is defined by ordered skills, not by a separate Slack template compiler</div>
<div class="arch-sidebar-item">MCP tools provide deterministic scoring to complement model judgment</div>
</div>
</div>
</div>
</div>
