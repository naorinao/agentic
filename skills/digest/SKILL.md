---
name: digest
description: Shared digest formatting heuristics for status and daily report jobs.
version: "1.0"
---

Digest formatting rules:

- Focus on the single most important observation first.
- For daily reports, prefer a single detailed list of what was completed today instead of splitting the update into many sections.
- Prefer concrete facts over generic status language like "in progress" or "ongoing" unless no stronger signal exists.
- Write bullets as action plus target plus outcome whenever possible.
- Do not add next steps, asks, or blockers unless the task skill explicitly asks for them.
- When the source data comes from GitHub, include PR, commit, issue, or review URLs in the relevant bullets whenever available.
- Mention urgency only when the data clearly supports it.
- Use MCP scoring tools if you need a deterministic tie-breaker for urgency.
