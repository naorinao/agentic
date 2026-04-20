from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from app.schemas import AgentDecision, JobConfig, SlackTemplate
from app.agent.slack_templates import finalize_slack_decision, validate_slack_content


class SlackTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = SlackTemplate.model_validate(
            {
                "title": "GitHub Daily Activity",
                "tone": "concise",
                "audience": "team",
                "sections": [
                    {
                        "key": "overview",
                        "label": "Overview",
                        "type": "paragraph",
                        "required": True,
                        "min_chars": 20,
                        "instruction": "Summarize the most important progress in 2-3 sentences.",
                    },
                    {
                        "key": "highlights",
                        "label": "Highlights",
                        "type": "bullet_list",
                        "required": True,
                        "min_items": 2,
                        "max_items": 4,
                        "instruction": "List the most important PRs, commits, or reviews.",
                    },
                    {
                        "key": "next_steps",
                        "label": "Next Steps",
                        "type": "bullet_list",
                        "required": True,
                        "min_items": 1,
                        "max_items": 2,
                        "instruction": "List the next actions worth sharing.",
                    },
                ],
            }
        )

    def test_validate_slack_content_reports_template_violations(self) -> None:
        errors = validate_slack_content(
            self.template,
            {
                "overview": "Too short",
                "highlights": ["Only one item"],
                "unexpected": "extra section",
            },
        )

        self.assertEqual(
            errors,
            [
                "Section 'overview' must be at least 20 characters.",
                "Section 'highlights' must contain at least 2 items.",
                "Missing required section 'next_steps'.",
                "Unknown slack_content sections: unexpected.",
            ],
        )

    def test_finalize_slack_decision_renders_template_in_order(self) -> None:
        decision = AgentDecision.model_validate(
            {
                "summary": "GitHub activity is worth notifying the team about.",
                "should_notify_slack": True,
                "slack_content": {
                    "overview": "Completed the release prep, merged two reviews, and cleared the flaky CI blocker.",
                    "highlights": [
                        "Merged the deployment checklist cleanup PR.",
                        "Closed the flaky CI issue after updating the retry logic.",
                    ],
                    "next_steps": ["Prepare the release notes draft before tomorrow morning."],
                },
                "follow_up_actions": [],
            }
        )

        finalized = finalize_slack_decision(decision, self.template)

        self.assertIsNotNone(finalized.slack_message)
        self.assertEqual(
            finalized.slack_message.text,
            "*GitHub Daily Activity*\n\n"
            "Overview\n"
            "Completed the release prep, merged two reviews, and cleared the flaky CI blocker.\n\n"
            "Highlights\n"
            "- Merged the deployment checklist cleanup PR.\n"
            "- Closed the flaky CI issue after updating the retry logic.\n\n"
            "Next Steps\n"
            "- Prepare the release notes draft before tomorrow morning.",
        )

    def test_finalize_slack_decision_requires_plain_text_without_template(self) -> None:
        decision = AgentDecision.model_validate(
            {
                "summary": "This should notify Slack.",
                "should_notify_slack": True,
                "follow_up_actions": [],
            }
        )

        with self.assertRaisesRegex(ValueError, "slack_message.text"):
            finalize_slack_decision(decision, None)

    def test_validate_slack_content_allows_empty_optional_bullet_list_sections(self) -> None:
        template = SlackTemplate.model_validate(
            {
                "title": "Team Daily Report",
                "sections": [
                    {
                        "key": "summary",
                        "label": "Summary",
                        "type": "paragraph",
                        "required": True,
                        "min_chars": 20,
                    },
                    {
                        "key": "blockers",
                        "label": "Risks / Blockers",
                        "type": "bullet_list",
                        "required": False,
                        "min_items": 1,
                        "max_items": 3,
                    },
                ],
            }
        )

        errors = validate_slack_content(
            template,
            {
                "summary": "Completed the release checklist and unblocked the deployment.",
                "blockers": [],
            },
        )

        self.assertEqual(errors, [])

    def test_finalize_slack_decision_skips_empty_optional_bullet_list_sections(self) -> None:
        template = SlackTemplate.model_validate(
            {
                "title": "Team Daily Report",
                "sections": [
                    {
                        "key": "summary",
                        "label": "Summary",
                        "type": "paragraph",
                        "required": True,
                        "min_chars": 20,
                    },
                    {
                        "key": "blockers",
                        "label": "Risks / Blockers",
                        "type": "bullet_list",
                        "required": False,
                        "min_items": 1,
                        "max_items": 3,
                    },
                ],
            }
        )
        decision = AgentDecision.model_validate(
            {
                "summary": "This should notify Slack.",
                "should_notify_slack": True,
                "slack_content": {
                    "summary": "Completed the release checklist and unblocked the deployment.",
                    "blockers": [],
                },
                "follow_up_actions": [],
            }
        )

        finalized = finalize_slack_decision(decision, template)

        self.assertEqual(
            finalized.slack_message.text,
            "*Team Daily Report*\n\n"
            "Summary\n"
            "Completed the release checklist and unblocked the deployment.",
        )

    def test_job_config_accepts_structured_slack_template(self) -> None:
        job = JobConfig.model_validate(
            {
                "name": "github_daily_activity",
                "prompt": "Summarize the most important GitHub activity for the requested day.",
                "slack_template": self.template.model_dump(mode="json"),
                "skills": ["digest"],
                "fetch": {
                    "type": "gh_cli",
                    "args": ["api", "users/octocat/events?per_page=20"],
                },
            }
        )

        self.assertEqual(job.slack_template.title, "GitHub Daily Activity")
        self.assertEqual([section.key for section in job.slack_template.sections], ["overview", "highlights", "next_steps"])

    def test_daily_digest_job_uses_richer_daily_report_template(self) -> None:
        job_path = Path(__file__).resolve().parents[1] / "jobs" / "daily_digest.yaml"
        job = JobConfig.model_validate(yaml.safe_load(job_path.read_text()))

        self.assertIsNotNone(job.slack_template)
        self.assertEqual(
            [section.key for section in job.slack_template.sections],
            ["today_summary", "completed", "impact", "blockers", "next_focus", "asks"],
        )
        self.assertEqual(job.slack_template.tone, "clear and actionable")
        self.assertEqual(job.slack_template.audience, "team")
        self.assertEqual(job.slack_template.sections[1].min_items, 3)
        self.assertEqual(job.slack_template.sections[1].max_items, 5)
        self.assertTrue(any(skill_id == "digest" for skill_id in job.skills))


if __name__ == "__main__":
    unittest.main()
