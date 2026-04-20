from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from app.agent.slack_templates import build_slack_template_prompt, compile_slack_template, finalize_slack_decision
from app.schemas import AgentDecision, GeneratedSlackSection, JobConfig, SlackTemplate


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
                        "required_level": "hard",
                        "min_chars": 20,
                        "instruction": "Summarize the most important progress in 2-3 sentences.",
                    },
                    {
                        "key": "highlights",
                        "label": "Highlights",
                        "type": "bullet_list",
                        "required_level": "hard",
                        "min_items": 2,
                        "max_items": 4,
                        "instruction": "List the most important PRs, commits, or reviews.",
                    },
                    {
                        "key": "next_steps",
                        "label": "Next Steps",
                        "type": "bullet_list",
                        "required_level": "soft",
                        "min_items": 1,
                        "max_items": 2,
                        "instruction": "List the next actions worth sharing.",
                    },
                ],
            }
        )
        self.compiled_template = compile_slack_template(self.template)

    def test_compile_slack_template_exposes_contract_and_prompt_hints(self) -> None:
        self.assertEqual(self.compiled_template.title, "GitHub Daily Activity")
        self.assertEqual([section.key for section in self.compiled_template.sections], ["overview", "highlights", "next_steps"])
        self.assertEqual(self.compiled_template.required_keys, ["overview", "highlights"])
        self.assertEqual(self.compiled_template.sections[2].required_level, "soft")
        self.assertIn("Tone: concise", self.compiled_template.prompt_hints)
        self.assertIn("Audience: team", self.compiled_template.prompt_hints)

    def test_finalize_slack_decision_renders_template_in_order(self) -> None:
        decision = AgentDecision.model_validate(
            {
                "summary": "GitHub activity is worth notifying the team about.",
                "should_notify_slack": True,
                "slack_sections": [
                    {
                        "key": "overview",
                        "content": "Completed the release prep, merged two reviews, and cleared the flaky CI blocker.",
                    },
                    {
                        "key": "highlights",
                        "content": [
                            "Merged the deployment checklist cleanup PR.",
                            "Closed the flaky CI issue after updating the retry logic.",
                        ],
                    },
                    {
                        "key": "next_steps",
                        "content": ["Prepare the release notes draft before tomorrow morning."],
                    },
                ],
                "follow_up_actions": [],
            }
        )

        finalized = finalize_slack_decision(decision, self.compiled_template)

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

    def test_finalize_slack_decision_skips_missing_optional_sections(self) -> None:
        template = SlackTemplate.model_validate(
            {
                "title": "Team Daily Report",
                "sections": [
                    {
                        "key": "summary",
                        "label": "Summary",
                        "type": "paragraph",
                        "required_level": "hard",
                        "min_chars": 20,
                    },
                    {
                        "key": "blockers",
                        "label": "Risks / Blockers",
                        "type": "bullet_list",
                        "required_level": "soft",
                        "min_items": 1,
                        "max_items": 3,
                    },
                ],
            }
        )
        compiled_template = compile_slack_template(template)
        decision = AgentDecision.model_validate(
            {
                "summary": "This should notify Slack.",
                "should_notify_slack": True,
                "slack_sections": [
                    {
                        "key": "summary",
                        "content": "Completed the release checklist and unblocked the deployment.",
                    }
                ],
                "follow_up_actions": [],
            }
        )

        finalized = finalize_slack_decision(decision, compiled_template)

        self.assertEqual(
            finalized.slack_message.text,
            "*Team Daily Report*\n\n"
            "Summary\n"
            "Completed the release checklist and unblocked the deployment.",
        )

    def test_finalize_slack_decision_requires_hard_sections_from_contract(self) -> None:
        decision = AgentDecision.model_validate(
            {
                "summary": "This should notify Slack.",
                "should_notify_slack": True,
                "slack_sections": [
                    {
                        "key": "overview",
                        "content": "Completed the release prep, merged two reviews, and cleared the flaky CI blocker.",
                    }
                ],
                "follow_up_actions": [],
            }
        )

        with self.assertRaisesRegex(ValueError, "Missing required section 'highlights'"):
            finalize_slack_decision(decision, self.compiled_template)

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

    def test_daily_digest_job_uses_single_detailed_work_log_section(self) -> None:
        job_path = Path(__file__).resolve().parents[1] / "jobs" / "daily_digest.yaml"
        job = JobConfig.model_validate(yaml.safe_load(job_path.read_text()))

        self.assertIsNotNone(job.slack_template)
        self.assertEqual([section.key for section in job.slack_template.sections], ["completed"])
        self.assertEqual(job.slack_template.tone, "clear and actionable")
        self.assertEqual(job.slack_template.audience, "team")
        self.assertEqual(job.slack_template.sections[0].min_items, 3)
        self.assertEqual(job.slack_template.sections[0].max_items, 8)
        self.assertEqual(job.slack_template.sections[0].required_level, "hard")
        self.assertIn("GitHub URL", job.slack_template.sections[0].instruction)
        self.assertTrue(any(skill_id == "digest" for skill_id in job.skills))

    def test_build_slack_template_prompt_warns_against_template_metadata_in_output(self) -> None:
        prompt = build_slack_template_prompt(self.compiled_template)

        self.assertIn("Return slack_sections as a JSON array", prompt)
        self.assertIn("Do not include template metadata fields like title, tone, audience, sections, or required_keys", prompt)
        self.assertIn('Allowed keys: ["overview", "highlights", "next_steps"]', prompt)
        self.assertIn('Required keys: ["overview", "highlights"]', prompt)
        self.assertIn('Example shape: [{"key":"overview","content":"..."}', prompt)


if __name__ == "__main__":
    unittest.main()
