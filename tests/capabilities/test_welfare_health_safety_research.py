from __future__ import annotations

import subprocess
import sys
import unittest

from kgov_runtime.capabilities import welfare_health_safety_research as adapter


class AdapterTest(unittest.TestCase):
    def test_exact_profile_is_absent_and_fixture_reports_block(self) -> None:
        self.assertIsNone(adapter.OPERATION)
        self.assertEqual(
            {
                "contract_id": "kgov/welfare-health-safety-research/v1",
                "execution_mode": "synthetic-fixture",
                "status": "live-operation-blocked",
                "count": 0,
                "records": [],
                "source_receipt": {
                    "operation_id": "kgov/welfare-health-safety-research/blocked-dataset-query/v1",
                    "policy_id": None,
                    "endpoint": None,
                },
                "manual_review_required": True,
            },
            adapter.fixture_result(),
        )

    def test_live_query_is_blocked_before_network(self) -> None:
        calls = []
        with self.assertRaisesRegex(RuntimeError, "exact dataset profile"):
            adapter.query(opener=lambda *_a, **_k: calls.append(True))
        self.assertEqual([], calls)

    def test_cli_fixture_succeeds_and_live_is_policy_blocked(self) -> None:
        fixture = subprocess.run([sys.executable, "-m", "kgov_runtime.capabilities.welfare_health_safety_research", "--fixture"], text=True, capture_output=True, check=False)
        blocked = subprocess.run([sys.executable, "-m", "kgov_runtime.capabilities.welfare_health_safety_research"], text=True, capture_output=True, check=False)
        self.assertEqual(0, fixture.returncode)
        self.assertEqual(3, blocked.returncode)
        self.assertNotIn("Traceback", blocked.stderr)


if __name__ == "__main__":
    unittest.main()
