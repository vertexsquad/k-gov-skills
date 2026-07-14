from __future__ import annotations

import copy
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_catalog import render_catalog  # noqa: E402
from scripts.validate_catalog import validate  # noqa: E402


class CatalogContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((ROOT / "catalog" / "domain-skills.json").read_text(encoding="utf-8"))

    def test_live_catalog_is_valid(self) -> None:
        self.assertEqual([], validate(self.data, ROOT))

    def test_evidence_distribution_matches_review(self) -> None:
        counts = Counter(item["evidence"] for item in self.data["domains"])
        self.assertEqual(
            {"direct": 35, "adjacent": 16, "new": 8, "sensitive": 1},
            dict(counts),
        )

    def test_capability_runtime_manifest_is_complete(self) -> None:
        self.assertIn("shared_capabilities", self.data)
        capabilities = self.data["shared_capabilities"]
        self.assertEqual(8, len(capabilities))
        required = {
            "slug",
            "locale",
            "jurisdiction",
            "service",
            "credential_class",
            "proxy_mode",
            "side_effect_class",
            "manual_handoff_gate",
            "source_provenance",
            "execution_status",
            "live_smoke",
        }
        for capability in capabilities:
            self.assertTrue(required.issubset(capability))
            self.assertEqual("ko-KR", capability["locale"])
            self.assertEqual("KR", capability["jurisdiction"])

    def test_duplicate_domain_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][1]["domain"] = changed["domains"][0]["domain"]
        errors = validate(changed, ROOT)
        self.assertTrue(any(error.startswith("duplicate domain:") for error in errors))

    def test_live_status_requires_matching_smoke_evidence(self) -> None:
        changed = copy.deepcopy(self.data)
        capability = next(item for item in changed["shared_capabilities"] if item["slug"] == "official-source-research")
        capability["live_smoke"] = "not-run"
        errors = validate(changed, ROOT)
        self.assertIn("official-source-research: live-verified requires live_smoke=passed", errors)

    def test_generated_document_matches_catalog(self) -> None:
        rendered = render_catalog(self.data)
        current = (ROOT / "docs" / "domain-skill-candidates.md").read_text(encoding="utf-8")
        self.assertEqual(rendered, current)
        self.assertIn("전체 domain: **60개**", current)


if __name__ == "__main__":
    unittest.main()
