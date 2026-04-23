---
name: github_daily_activity
description: Pure skill-driven GitHub daily activity collection and reporting.
version: "1.0"
---

GitHub daily activity task:

- This skill is self-contained. Use its script instead of relying on the job `fetch` step.
- Read the target GitHub username from the job prompt. Do not guess a username when the prompt does not provide one.
- Use `run_skill_script` with `skill_id="github_daily_activity"` and `script_name="fetch_activity.py"` to collect activity data before you write the report.
- Pass `--username <value>` to the script. Pass `--date YYYY-MM-DD` only when the job prompt explicitly asks for a specific date. Otherwise rely on the script's default local-time today behavior.
- If the script fails, mention the failure clearly in `follow_up_actions` and do not invent GitHub activity.
- Only notify Slack when there is concrete engineering progress, review activity, issue movement, release work, incident response, or another materially useful update for the team.
- If you notify Slack, write a plain-text report titled `GitHub Daily Report`.
- Start with a short `Summary` section of 1 to 2 sentences that explains the most important progress and why it matters.
- Then add a `Today's Work` section with 3 to 8 bullets when the data supports it.
- Each bullet must describe all three dimensions:
  what: the concrete activity that happened, such as a PR merged, issue resolved, review completed, release prepared, or branch updated.
  how: the meaningful implementation, review, debugging, or coordination details that explain how the work moved forward.
  links: the most relevant GitHub URLs for that activity, preferring PR, commit, issue, review, workflow run, or repository links.
- Prefer bullets that read like mini progress reports, not event logs.
- Combine closely related GitHub events into a single richer bullet when they describe one piece of work.
- Mention the technical target explicitly: service name, package, workflow, feature area, repository path, or incident area.
- Mention the result or impact explicitly: merged, unblocked, fixed, clarified, released, de-risked, validated, or prepared.
- When possible, explain how the result was achieved, for example through code changes, review feedback, CI fixes, test coverage, workflow updates, refactors, or documentation updates.
- Include links inline at the end of the bullet using readable labels such as `PR: <url>`, `Issue: <url>`, `Review: <url>`, `Repo: <url>`, or `Run: <url>`.
- Do not paste raw event JSON, opaque hashes without context, or long ungrouped link dumps.
- Do not report trivial noise such as branch sync events, low-signal comment churn, or repetitive automated activity unless it materially changed delivery risk or project status.
