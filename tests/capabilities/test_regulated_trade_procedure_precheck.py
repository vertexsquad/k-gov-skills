from __future__ import annotations

import json
import unittest
from pathlib import Path

from kgov_runtime.capabilities import regulated_trade_procedure_precheck as adapter
from tests.capabilities.review_admission_contract import ReviewAdmissionContractMixin

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "kgov_runtime" / "capabilities" / "regulated_trade_procedure_precheck.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "capabilities" / "regulated-trade-procedure-precheck.json"


class AdapterTest(ReviewAdmissionContractMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = adapter
        cls.adapter_path = ADAPTER_PATH
        cls.valid = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_contract_is_narrow_and_exact(self) -> None:
        self.assertEqual(
            frozenset({"www.customs.go.kr", "unipass.customs.go.kr"}),
            adapter.CONTRACT.allowed_hosts,
        )
        self.assertEqual(
            frozenset({"customs-origin-document-precheck", "trade-procedure-document-precheck"}),
            adapter.CONTRACT.review_types,
        )
        self.assertEqual(
            (
                "origin-determination",
                "customs-declaration-or-submission",
                "clearance-or-enforcement-action",
            ),
            adapter.CONTRACT.prohibited_decisions,
        )
        self.assertEqual("regulated-trade-review-draft-only", adapter.CONTRACT.permitted_output)


if __name__ == "__main__":
    unittest.main()
