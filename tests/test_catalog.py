from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.render_catalog import render_catalog  # noqa: E402
from scripts.render_domain_skills import expected_domain_skills  # noqa: E402
from scripts.validate_catalog import validate  # noqa: E402


class CatalogContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((ROOT / "catalog/domain-skills.json").read_text(encoding="utf-8"))

    def copied_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        shutil.copytree(
            ROOT,
            Path(temp.name) / "repo",
            ignore=shutil.ignore_patterns(".git", ".ruff_cache", "__pycache__", "*.pyc"),
            dirs_exist_ok=True,
        )
        return temp

    def test_live_catalog_is_valid(self) -> None:
        self.assertEqual([], validate(self.data, ROOT))

    def test_public_skills_are_owned_by_domains(self) -> None:
        self.assertFalse((ROOT / "skills").exists())
        entrypoints = sorted(ROOT.glob("domains/*/skills/*/SKILL.md"))
        self.assertEqual(66, len(entrypoints))
        self.assertEqual(66, len({path.parent.name for path in entrypoints}))
        self.assertFalse(list(ROOT.glob("domains/*/.gitkeep")))

    def test_evidence_distribution_matches_review(self) -> None:
        counts = Counter(item["evidence"] for item in self.data["domains"])
        self.assertEqual({"direct": 35, "adjacent": 16, "new": 8, "sensitive": 1}, dict(counts))

    def test_capability_runtime_manifest_is_complete(self) -> None:
        self.assertEqual(4, self.data["schema_version"])
        capabilities = self.data["shared_capabilities"]
        self.assertEqual(11, len(capabilities))
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

    def test_each_domain_has_one_primary_and_unique_skill_names(self) -> None:
        names: list[str] = []
        for domain in self.data["domains"]:
            self.assertEqual(1, sum(skill["role"] == "primary" for skill in domain["skills"]))
            names.extend(skill["name"] for skill in domain["skills"])
        self.assertEqual(66, len(names))
        self.assertEqual(len(names), len(set(names)))

    def test_additional_capabilities_are_domain_owned(self) -> None:
        expected = {
            "civil-complaint-triage-draft",
            "administrative-document-draft-review",
            "public-policy-evidence-pack",
        }
        for domain_name in ("행정", "지방자치"):
            domain = next(item for item in self.data["domains"] if item["domain"] == domain_name)
            additions = {skill["capability"] for skill in domain["skills"] if skill["role"] == "additional"}
            self.assertEqual(expected, additions)

    def test_unknown_capability_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][0]["skills"][0]["capability"] = "unknown-capability"
        errors = validate(changed, ROOT)
        self.assertTrue(any("unknown capability unknown-capability" in error for error in errors))

    def test_invalid_skill_container_is_rejected_without_crashing(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][0]["skills"] = None
        errors = validate(changed, ROOT)
        self.assertTrue(any("skills must be a non-empty list" in error for error in errors))

    def test_duplicate_domain_skill_name_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][1]["skills"][0]["name"] = changed["domains"][0]["skills"][0]["name"]
        errors = validate(changed, ROOT)
        self.assertTrue(any(error.startswith("duplicate domain Skill name:") for error in errors))

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

    def test_internal_capability_artifacts_are_complete(self) -> None:
        for capability in self.data["shared_capabilities"]:
            slug = capability["slug"]
            module = slug.replace("-", "_")
            self.assertTrue((ROOT / "kgov_runtime/capabilities" / f"{module}.py").is_file())
            self.assertTrue((ROOT / "tests/capabilities" / f"test_{module}.py").is_file())
            self.assertTrue((ROOT / "tests/fixtures/capabilities" / f"{slug}.json").is_file())
            self.assertTrue((ROOT / "docs/capabilities" / slug / "procedure.md").is_file())
            self.assertTrue((ROOT / "docs/capabilities" / slug / "runtime-contract.md").is_file())

    def test_generated_documents_match_catalog(self) -> None:
        current = (ROOT / "docs/domain-skill-candidates.md").read_text(encoding="utf-8")
        self.assertEqual(render_catalog(self.data), current)
        self.assertIn("전체 domain: **60개**", current)
        self.assertIn("domain-owned Skill: **66개**", current)

    def test_generated_domain_skills_match_catalog(self) -> None:
        expected = expected_domain_skills(self.data, ROOT)
        self.assertEqual(66, len(expected))
        for path, content in expected.items():
            self.assertEqual(content, path.read_text(encoding="utf-8"))

    def test_top_level_skill_mutation_fails_closed(self) -> None:
        temp = self.copied_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "repo"
        rogue = root / "skills/rogue/SKILL.md"
        rogue.parent.mkdir(parents=True)
        rogue.write_text("---\nname: rogue\ndescription: rogue\n---\n", encoding="utf-8")
        errors = validate(self.data, root)
        self.assertIn("top-level skills/ is forbidden; public Skills must be owned by domains", errors)

    def test_misplaced_domain_skill_mutation_fails_closed(self) -> None:
        temp = self.copied_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "repo"
        source = next(root.glob("domains/*/skills/*/SKILL.md"))
        target = source.parents[1] / "rogue" / "SKILL.md"
        target.parent.mkdir(parents=True)
        source.replace(target)
        errors = validate(self.data, root)
        self.assertTrue(any(error.startswith("domain Skill/catalog mismatch") for error in errors))

    def test_validator_cli_reports_owned_topology(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_catalog.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("domains=60 domain_skills=66 capabilities=11 top_level_skills=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
