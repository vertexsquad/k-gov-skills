from __future__ import annotations

import json
import unittest
from pathlib import Path

from kgov_runtime.capabilities import local_ordinance_draft_review as adapter
from tests.capabilities.review_admission_contract import ReviewAdmissionContractMixin

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "kgov_runtime" / "capabilities" / "local_ordinance_draft_review.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "capabilities" / "local-ordinance-draft-review.json"


class AdapterTest(ReviewAdmissionContractMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = adapter
        cls.adapter_path = ADAPTER_PATH
        cls.valid = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
