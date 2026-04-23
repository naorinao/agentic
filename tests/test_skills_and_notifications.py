from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from app.agent.skills import load_skills
from app.runner import finalize_agent_decision
from app.schemas import AgentDecision, JobConfig


class SkillsAndNotificationsTests(unittest.TestCase):
    def test_finalize_agent_decision_requires_plain_text_when_notifying(self) -> None:
        decision = AgentDecision.model_validate(
            {
                "summary": "This should notify Slack.",
                "should_notify_slack": True,
                "follow_up_actions": [],
            }
        )

        with self.assertRaisesRegex(ValueError, "slack_message.text"):
            finalize_agent_decision(decision)

    def test_finalize_agent_decision_clears_message_when_not_notifying(self) -> None:
        decision = AgentDecision.model_validate(
            {
                "summary": "Nothing important happened.",
                "should_notify_slack": False,
                "slack_message": {"text": "Should be cleared."},
                "follow_up_actions": [],
            }
        )

        finalized = finalize_agent_decision(decision)

        self.assertIsNone(finalized.slack_message)

    def test_load_skills_reads_package_skills(self) -> None:
        skills_dir = Path(__file__).resolve().parents[1] / "skills"

        skills = load_skills(["default", "daily_digest_task"], skills_dir=skills_dir)

        self.assertEqual(len(skills), 2)
        self.assertEqual(skills[0].skill_id, "default")
        self.assertIn("Base operating rules", skills[0].content)
        self.assertTrue(skills[0].scripts_dir.name.endswith("scripts"))
        self.assertIn("Team Daily Report", skills[1].content)

    def test_daily_digest_job_is_defined_by_skills(self) -> None:
        job_path = Path(__file__).resolve().parents[1] / "jobs" / "daily_digest.yaml"
        job = JobConfig.model_validate(yaml.safe_load(job_path.read_text()))

        self.assertEqual(job.skills, ["default", "digest", "daily_digest_task"])
        self.assertIsNotNone(job.fetch)

    def test_github_daily_activity_job_can_be_skill_only(self) -> None:
        job_path = Path(__file__).resolve().parents[1] / "jobs" / "github_daily_activity.yaml"
        job = JobConfig.model_validate(yaml.safe_load(job_path.read_text()))

        self.assertIsNone(job.fetch)
        self.assertEqual(job.skills, ["default", "digest", "github_daily_activity"])


if __name__ == "__main__":
    unittest.main()
