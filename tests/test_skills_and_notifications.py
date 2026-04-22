from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from app.agent.skills import load_skill_texts
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

    def test_load_skill_texts_reads_task_skill(self) -> None:
        skills_dir = Path(__file__).resolve().parents[1] / "skills"

        texts = load_skill_texts(["default", "daily_digest_task"], skills_dir=skills_dir)

        self.assertEqual(len(texts), 2)
        self.assertIn("Base operating rules", texts[0])
        self.assertIn("Team Daily Report", texts[1])

    def test_daily_digest_job_is_defined_by_skills(self) -> None:
        job_path = Path(__file__).resolve().parents[1] / "jobs" / "daily_digest.yaml"
        job = JobConfig.model_validate(yaml.safe_load(job_path.read_text()))

        self.assertIsNone(job.prompt)
        self.assertEqual(job.skills, ["default", "digest", "daily_digest_task"])


if __name__ == "__main__":
    unittest.main()
