from __future__ import annotations

import json
import unittest
from datetime import datetime, UTC

from app.agent.main import build_data_preview
from app.schemas import FetchedData


class AgentDataPreviewTests(unittest.TestCase):
    def test_build_data_preview_keeps_valid_json_for_large_payloads(self) -> None:
        data = [
            FetchedData(
                source="github/issues",
                fetched_at=datetime(2026, 4, 23, tzinfo=UTC),
                text_summary="A" * 9000,
                payload={
                    "items": [
                        {
                            "title": f"Issue {index}",
                            "body": "B" * 2000,
                            "url": f"https://github.com/example/repo/issues/{index}",
                        }
                        for index in range(40)
                    ]
                },
            ),
            FetchedData(
                source="github/pulls",
                fetched_at=datetime(2026, 4, 23, 1, tzinfo=UTC),
                text_summary="C" * 9000,
                payload={
                    "items": [
                        {
                            "title": f"PR {index}",
                            "body": "D" * 2000,
                            "url": f"https://github.com/example/repo/pull/{index}",
                        }
                        for index in range(40)
                    ]
                },
            ),
        ]

        preview = build_data_preview(data)
        parsed = json.loads(preview)

        self.assertEqual([item["source"] for item in parsed], ["github/issues", "github/pulls"])

    def test_build_data_preview_preserves_top_level_shape_when_tightened(self) -> None:
        data = [
            FetchedData(
                source="github/events",
                fetched_at=datetime(2026, 4, 23, tzinfo=UTC),
                text_summary="summary" * 3000,
                payload={
                    "events": [
                        {
                            "type": "PushEvent",
                            "description": "details" * 1000,
                        }
                        for _ in range(100)
                    ]
                },
            )
        ]

        parsed = json.loads(build_data_preview(data))

        self.assertEqual(parsed[0]["source"], "github/events")
        self.assertIn("payload", parsed[0])
        self.assertIn("text_summary", parsed[0])


if __name__ == "__main__":
    unittest.main()
