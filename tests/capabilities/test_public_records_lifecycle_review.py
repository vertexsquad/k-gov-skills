from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from kgov_runtime.capabilities import public_records_lifecycle_review as adapter
from tests.capabilities.review_admission_contract import ReviewAdmissionContractMixin

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "kgov_runtime" / "capabilities" / "public_records_lifecycle_review.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "capabilities" / "public-records-lifecycle-review.json"


class AdapterTest(ReviewAdmissionContractMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = adapter
        cls.adapter_path = ADAPTER_PATH
        cls.valid = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_contract_preserves_lifecycle_decision_boundary(self) -> None:
        self.assertEqual(
            (
                "records-series-and-business-function",
                "retention-basis-and-trigger",
                "transfer-disposal-and-approval-gate",
            ),
            adapter.CONTRACT.required_checks,
        )
        self.assertEqual(
            (
                "final-retention-period",
                "source-record-mutation",
                "automatic-transfer-or-disposal",
            ),
            adapter.CONTRACT.prohibited_decisions,
        )
        self.assertEqual("records-lifecycle-review-draft-only", adapter.CONTRACT.permitted_output)

    def test_source_host_allowlist_matches_catalog_provenance(self) -> None:
        catalog = json.loads((REPO_ROOT / "catalog/domain-skills.json").read_text(encoding="utf-8"))
        manifest = next(
            item
            for item in catalog["shared_capabilities"]
            if item["slug"] == "public-records-lifecycle-review"
        )
        provenance_hosts = {urlsplit(url).hostname for url in manifest["source_provenance"]}
        self.assertEqual(adapter.CONTRACT.allowed_hosts, provenance_hosts)
        self.assertEqual("draft-only", manifest["side_effect_class"])
        self.assertEqual(
            "보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인",
            manifest["manual_handoff_gate"],
        )


if __name__ == "__main__":
    unittest.main()
