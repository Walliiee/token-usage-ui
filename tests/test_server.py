"""Unit tests for the Token Usage UI server logic.

These tests use only the Python standard library and point OPENCLAW_DIR at a
non-existent path so the mock-data fallbacks are exercised deterministically,
regardless of the machine they run on.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402


class PricingTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(server.get_pricing("claude-sonnet-4-6"), (3.0, 15.0))

    def test_prefix_match(self):
        # A dated/suffixed model id should match its family prefix.
        self.assertEqual(server.get_pricing("claude-3-opus-20240229"), (15.0, 75.0))

    def test_unknown_model_is_free(self):
        self.assertEqual(server.get_pricing("some-unknown-model"), (0.0, 0.0))

    def test_cloud_models_are_free(self):
        self.assertEqual(server.get_pricing("glm-5.1:cloud"), (0.0, 0.0))

    def test_calc_cost(self):
        # 1M input + 1M output on sonnet pricing = 3 + 15 = 18 USD.
        self.assertEqual(server.calc_cost(1_000_000, 1_000_000, "claude-sonnet-4-6"), 18.0)
        self.assertEqual(server.calc_cost(0, 0, "claude-sonnet-4-6"), 0.0)


class FallbackDataTests(unittest.TestCase):
    """With no sessions file present, the API returns mock data."""

    def setUp(self):
        self._orig = server.OPENCLAW_DIR
        server.OPENCLAW_DIR = Path(tempfile.gettempdir()) / "does-not-exist-token-ui"

    def tearDown(self):
        server.OPENCLAW_DIR = self._orig

    def test_usage_mock(self):
        data = server.get_usage_data()
        self.assertEqual(data["totalSessions"], 10)
        self.assertEqual(len(data["models"]), 3)
        self.assertIn("fetchedAt", data)

    def test_timeline_mock_has_seven_days(self):
        data = server.get_timeline_data()
        self.assertEqual(len(data["timeline"]), 7)
        self.assertTrue(all("date" in d for d in data["timeline"]))


class RealDataTests(unittest.TestCase):
    """With a sessions file present, usage is aggregated per model."""

    def setUp(self):
        self._orig = server.OPENCLAW_DIR
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        sessions_dir = root / "agents" / "main" / "sessions"
        sessions_dir.mkdir(parents=True)
        sessions = [
            {"model": "claude-sonnet-4-6", "inputTokens": 1_000_000, "outputTokens": 0,
             "startedAt": 1_700_000_000_000},
            {"model": "claude-sonnet-4-6", "inputTokens": 0, "outputTokens": 1_000_000,
             "startedAt": 1_700_000_000_000},
        ]
        (sessions_dir / "sessions.json").write_text(json.dumps(sessions))
        server.OPENCLAW_DIR = root

    def tearDown(self):
        server.OPENCLAW_DIR = self._orig
        self._tmp.cleanup()

    def test_aggregates_models_and_cost(self):
        data = server.get_usage_data()
        self.assertEqual(data["totalSessions"], 2)
        self.assertEqual(len(data["models"]), 1)
        model = data["models"]["claude-sonnet-4-6"]
        self.assertEqual(model["inputTokens"], 1_000_000)
        self.assertEqual(model["outputTokens"], 1_000_000)
        self.assertEqual(model["sessions"], 2)
        self.assertEqual(data["totalCost"], 18.0)

    def test_timeline_groups_by_day(self):
        data = server.get_timeline_data()
        self.assertEqual(len(data["timeline"]), 1)
        day = data["timeline"][0]
        self.assertEqual(day["sessions"], 2)
        self.assertIn("claude-sonnet-4-6", day["models"])


if __name__ == "__main__":
    unittest.main()
