from __future__ import annotations

import subprocess
import sys
import unittest

from kgov_runtime.capabilities import land_housing_geospatial_research as adapter


class AdapterTest(unittest.TestCase):
    def test_exact_profile_is_absent_and_fixture_reports_block(self) -> None:
        self.assertIsNone(adapter.OPERATION)
        self.assertEqual("kgov/land-housing-geospatial-research/v1", adapter.fixture_result()["contract_id"])
        self.assertEqual("live-operation-blocked", adapter.fixture_result()["status"])
        self.assertEqual([], adapter.fixture_result()["records"])
        self.assertEqual(None, adapter.fixture_result()["source_receipt"]["endpoint"])

    def test_live_query_is_blocked_before_network(self) -> None:
        calls = []
        with self.assertRaisesRegex(RuntimeError, "exact dataset profile"):
            adapter.query(opener=lambda *_a, **_k: calls.append(True))
        self.assertEqual([], calls)

    def test_cli_fixture_succeeds_and_live_is_policy_blocked(self) -> None:
        fixture = subprocess.run([sys.executable, "-m", "kgov_runtime.capabilities.land_housing_geospatial_research", "--fixture"], text=True, capture_output=True, check=False)
        blocked = subprocess.run([sys.executable, "-m", "kgov_runtime.capabilities.land_housing_geospatial_research"], text=True, capture_output=True, check=False)
        self.assertEqual(0, fixture.returncode)
        self.assertEqual(3, blocked.returncode)
        self.assertNotIn("Traceback", blocked.stderr)


if __name__ == "__main__":
    unittest.main()
