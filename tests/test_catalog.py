"""Catalog regression suite.

# noqa: SIZE_OK -- Issue #33 confines catalog regressions to this existing suite;
# extracting its legacy test classes would violate isolated file ownership.
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import check  # noqa: E402
from scripts.render_catalog import render_catalog  # noqa: E402
from scripts.render_domain_skills import expected_domain_skills  # noqa: E402
from scripts.validate_catalog import validate  # noqa: E402

validate_catalog = importlib.import_module("scripts.validate_catalog")

STRICT_CLI_OWNED_PATHS = (
    "catalog/domain-skills.json",
    "scripts/validate_catalog.py",
    "tests/test_catalog.py",
)


def copy_repository_inputs(destination: Path) -> None:
    """Copy indexed input paths using working-tree bytes, never ambient files."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "AGENTS.md", "CLAUDE.md", "README.md",
         "catalog", "docs", "domains", "kgov_runtime", "scripts", "tests"],
        cwd=ROOT, check=True, capture_output=True,
    )
    for raw in listed.stdout.split(b"\0")[:-1]:
        relative = Path(os.fsdecode(raw))
        source = ROOT / relative
        if any((ROOT / part).is_symlink() for part in (relative, *relative.parents)):
            raise ValueError(f"symlink repository input: {relative}")
        if not source.is_file():
            raise ValueError(f"non-regular repository input: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class RepositoryCheckTest(unittest.TestCase):
    def test_scan_detects_patterns_but_prunes_existing_exclusions(self) -> None:
        patterns = (
            b"ghp_" + b"A" * 20, b"github_pat_" + b"B" * 20,
            b"AKIA" + b"C" * 16, b"-----BEGIN " + b"PRIVATE KEY-----",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in (".git", ".ruff_cache", "__pycache__"):
                directory = root / name
                directory.mkdir()
                (directory / "ignored").write_bytes(patterns[0])
                (directory / "dangling").symlink_to("missing")
            with patch.object(check, "ROOT", root):
                self.assertIsNone(check.scan_secrets())
                for body in patterns:
                    with self.subTest(body=body[:4]):
                        (root / "input").write_bytes(body)
                        with self.assertRaises(SystemExit) as caught:
                            check.scan_secrets()
                        self.assertIn("input", str(caught.exception))
                        self.assertNotIn(body.decode(), str(caught.exception))
                        self.assertNotIn(str(root), str(caught.exception))

    def test_scan_rejects_nonregular_files_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.mkfifo(root / "pipe")
            with patch.object(check, "ROOT", root), patch.object(Path, "read_bytes") as read:
                with self.assertRaises(SystemExit):
                    check.scan_secrets()
                read.assert_not_called()

    def test_scan_read_failure_is_not_a_clean_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "nested/input.txt"
            path.parent.mkdir()
            path.write_bytes(b"clean")
            with patch.object(check, "ROOT", root):
                self.assertIsNone(check.scan_secrets())
                with patch.object(
                    Path, "read_bytes",
                    side_effect=PermissionError(13, "PRIVATE_ERROR_DETAIL", str(path)),
                ) as read:
                    with self.assertRaises(SystemExit) as caught:
                        check.scan_secrets()
                read.assert_called_once()
                self.assertIn("nested/input.txt", str(caught.exception))
                self.assertNotIn(str(root), str(caught.exception))
                self.assertNotIn("PRIVATE_ERROR_DETAIL", str(caught.exception))

    def test_scan_rejects_symlinks_without_reading_targets(self) -> None:
        for target in ("inside.txt", "../outside.txt", "../outside", "../missing", "link"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                parent = Path(temp)
                root = parent / "repo"
                root.mkdir()
                (root / "inside.txt").write_bytes(b"clean")
                (parent / "outside.txt").write_bytes(b"outside")
                (parent / "outside").mkdir()
                (root / "link").symlink_to(target)
                read_bytes = Path.read_bytes

                def guarded_read(path: Path) -> bytes:
                    self.assertFalse(path.is_symlink(), "symlink target was read")
                    self.assertTrue(path.is_relative_to(root))
                    return read_bytes(path)

                with patch.object(check, "ROOT", root), patch.object(Path, "read_bytes", guarded_read):
                    with self.assertRaises(SystemExit) as caught:
                        check.scan_secrets()
                self.assertIn("link", str(caught.exception))
                self.assertNotIn(str(parent), str(caught.exception))
                self.assertNotIn("outside", str(caught.exception))

    def test_scan_directory_read_failure_is_not_a_clean_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            blocked = root / "nested"
            blocked.mkdir()
            scandir = os.scandir

            def guarded_scandir(path):
                if Path(path) == blocked:
                    raise PermissionError(13, "PRIVATE_ERROR_DETAIL", str(path))
                return scandir(path)

            with patch.object(check, "ROOT", root), patch.object(os, "scandir", guarded_scandir):
                with self.assertRaises(SystemExit) as caught:
                    check.scan_secrets()
            self.assertIn("nested", str(caught.exception))
            self.assertNotIn(str(root), str(caught.exception))
            self.assertNotIn("PRIVATE_ERROR_DETAIL", str(caught.exception))


class RepositoryCopyTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "source"
        self.root.mkdir()
        self.source = self.root / "docs/owned.md"
        self.source.parent.mkdir()
        self.source.write_bytes(b"indexed bytes")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        subprocess.run(["git", "add", "docs/owned.md"], cwd=self.root, check=True, capture_output=True)
        self.helper = CatalogContractTest()
        self.addCleanup(self.helper.doCleanups)
        self.enterContext(patch(__name__ + ".ROOT", self.root))

    def test_copy_uses_current_input_bytes_and_excludes_ambient_files(self) -> None:
        current = b"working tree\r\n\xff\x00"
        self.source.write_bytes(current)
        for name in (".env", "docs/ambient.md", ".omo/evidence.md", "tests/fixtures/ambient.json"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ambient")
        subprocess.run(
            ["git", "add", ".env", ".omo/evidence.md"],
            cwd=self.root, check=True, capture_output=True,
        )
        temp = self.helper.copied_repo()
        self.addCleanup(temp.cleanup)
        destination = Path(temp.name) / "repo"
        self.assertEqual(current, (destination / "docs/owned.md").read_bytes())
        self.assertEqual(
            ["docs/owned.md"],
            sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()),
        )

    def test_copy_excludes_ambient_symlinks(self) -> None:
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "input").write_bytes(b"outside")
        for target in ("docs/owned.md", "../outside", "../outside/input", "../missing"):
            with self.subTest(target=target):
                link = self.root / "ambient"
                link.symlink_to(target)
                try:
                    temp = self.helper.copied_repo()
                    self.addCleanup(temp.cleanup)
                    self.assertFalse(os.path.lexists(Path(temp.name) / "repo/ambient"))
                finally:
                    link.unlink()

    def test_copy_rejects_selected_symlinks_and_symlink_parents(self) -> None:
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "owned.md").write_bytes(b"outside")
        (self.root / "inside.md").write_bytes(b"inside")
        self.source.unlink()
        for target in ("../inside.md", "../../outside/owned.md", "missing", "owned.md"):
            with self.subTest(target=target):
                self.source.symlink_to(target)
                try:
                    with self.assertRaises(ValueError):
                        self.helper.copied_repo()
                finally:
                    self.source.unlink()
        self.source.parent.rmdir()
        self.source.parent.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.helper.copied_repo()

    def test_copy_rejects_missing_or_nonregular_selected_inputs(self) -> None:
        self.source.unlink()
        with self.assertRaises(ValueError):
            self.helper.copied_repo()
        os.mkfifo(self.source)
        with self.assertRaises(ValueError):
            self.helper.copied_repo()


class CatalogContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((ROOT / "catalog/domain-skills.json").read_text(encoding="utf-8"))

    def copied_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        copy_repository_inputs(Path(temp.name) / "repo")
        return temp

    def assert_cross_domain_move_errors(
        self,
        changed,
        source_domain: str,
        destination_domain: str,
        errors: list[str],
    ) -> None:
        domain_indexes = {domain["domain"]: index for index, domain in enumerate(changed["domains"])}
        source_index = domain_indexes[source_domain]
        destination_index = domain_indexes[destination_domain]
        moved_index = len(changed["domains"][destination_index]["skills"]) - 1
        expected = sorted(
            (
                f'V6_INVALID_VALUE "/domains/{source_index}/skills"',
                f'V6_INVALID_VALUE "/domains/{destination_index}/skills"',
                f'V6_INVALID_VALUE "/domains/{destination_index}/skills/{moved_index}/name"',
            )
        )
        self.assertEqual(expected, errors)

    @staticmethod
    def contract_field_for_mutation(mutation: str) -> str:
        return {
            "title": "title",
            "capability": "capability",
            "references": "reference_skills",
            "boundary": "boundary",
        }.get(mutation, "task_checks")

    def assert_skill_contract_field_error(
        self,
        domain_name: str,
        skill_name: str,
        field: str,
        errors: list[str],
    ) -> None:
        domain_index = next(
            index for index, domain in enumerate(self.data["domains"])
            if domain["domain"] == domain_name
        )
        skill_index = next(
            index for index, skill in enumerate(self.data["domains"][domain_index]["skills"])
            if skill["name"] == skill_name
        )
        expected = [
            f'V6_CONTRACT_INVARIANT "/domains/{domain_index}/skills/{skill_index}/{field}"'
        ]
        if field == "capability":
            expected = [
                f'V6_BINDING_MISMATCH "/domains/{domain_index}/skills/{skill_index}/runtime_binding/contract_id"'
            ]
        self.assertEqual(expected, errors)

    def assert_capability_contract_field_error(
        self,
        slug: str,
        field: str,
        errors: list[str],
    ) -> None:
        capability_index = next(
            index for index, capability in enumerate(self.data["shared_capabilities"])
            if capability["slug"] == slug
        )
        self.assertEqual(
            [f'V6_CONTRACT_INVARIANT "/shared_capabilities/{capability_index}/{field}"'],
            errors,
        )

    def test_live_catalog_is_valid(self) -> None:
        self.assertEqual([], validate(self.data, ROOT))

    def test_public_skills_are_owned_by_domains(self) -> None:
        self.assertFalse((ROOT / "skills").exists())
        entrypoints = sorted(ROOT.glob("domains/*/skills/*/SKILL.md"))
        self.assertEqual(308, len(entrypoints))
        self.assertEqual(308, len({path.parent.name for path in entrypoints}))
        self.assertFalse(list(ROOT.glob("domains/*/.gitkeep")))

    def test_evidence_distribution_matches_review(self) -> None:
        counts = Counter(item["evidence"] for item in self.data["domains"])
        self.assertEqual({"direct": 35, "adjacent": 16, "new": 8, "sensitive": 1}, dict(counts))

    def test_capability_runtime_manifest_is_complete(self) -> None:
        self.assertEqual(6, self.data["schema_version"])
        capabilities = self.data["shared_capabilities"]
        self.assertEqual(22, len(capabilities))
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
            "source_policy_ids",
            "runtime_contract_id",
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
        self.assertEqual(308, len(names))
        self.assertEqual(len(names), len(set(names)))

    def test_minimum_skill_rollout_contract(self) -> None:
        target = self.data["target_skills_per_domain"]
        minimums = self.data["enforced_minimum_skills_by_domain"]
        domain_names = {domain["domain"] for domain in self.data["domains"]}
        self.assertEqual(5, target)
        self.assertEqual(domain_names, set(minimums))
        self.assertTrue(all(value == 5 for value in minimums.values()))
        for domain in self.data["domains"]:
            self.assertGreaterEqual(len(domain["skills"]), minimums[domain["domain"]])

    def test_minimum_skill_rollout_mutations_fail_closed(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["enforced_minimum_skills_by_domain"].pop("교육")
        self.assertEqual(
            ['V6_REQUIRED_FIELD "/enforced_minimum_skills_by_domain/교육"'],
            validate(changed, ROOT),
        )

        changed = copy.deepcopy(self.data)
        changed["enforced_minimum_skills_by_domain"]["secret-query-credential"] = 5
        self.assertEqual(
            ['V6_UNKNOWN_FIELD "/enforced_minimum_skills_by_domain/secret-query-credential"'],
            validate(changed, ROOT),
        )

        for invalid_target in (4, "5", None):
            with self.subTest(target=invalid_target):
                changed = copy.deepcopy(self.data)
                changed["target_skills_per_domain"] = invalid_target
                self.assertEqual(
                    ['V6_INVALID_VALUE "/target_skills_per_domain"'],
                    validate(changed, ROOT),
                )

        for invalid_minimum, code in (
            (0, "V6_INVALID_VALUE"),
            (6, "V6_INVALID_VALUE"),
            ("5", "V6_INVALID_TYPE"),
            (True, "V6_INVALID_TYPE"),
        ):
            with self.subTest(minimum=invalid_minimum):
                changed = copy.deepcopy(self.data)
                changed["enforced_minimum_skills_by_domain"]["교육"] = invalid_minimum
                self.assertEqual(
                    [f'{code} "/enforced_minimum_skills_by_domain/교육"'],
                    validate(changed, ROOT),
                )

        changed = copy.deepcopy(self.data)
        domain = next(item for item in changed["domains"] if item["domain"] == "경호")
        draft = next(skill for skill in domain["skills"] if skill["role"] == "additional")
        draft["boundary"] = "draft-only"
        domain_index = changed["domains"].index(domain)
        skill_index = domain["skills"].index(draft)
        self.assertEqual(
            [f'V6_INVALID_VALUE "/domains/{domain_index}/skills/{skill_index}/boundary"'],
            validate(changed, ROOT),
        )

    def test_additional_capabilities_are_domain_owned(self) -> None:

        shared_expected = {
            "civil-complaint-triage-draft",
            "administrative-document-draft-review",
            "public-policy-evidence-pack",
        }
        for domain_name in ("행정", "지방자치"):
            domain = next(item for item in self.data["domains"] if item["domain"] == domain_name)
            additions = {skill["capability"] for skill in domain["skills"] if skill["role"] == "additional"}
            expected = set(shared_expected)
            if domain_name == "행정":
                expected.update(
                    {
                        "korean-legal-citation-verification",
                        "public-ai-governance-review",
                        "official-notice-multilingual-translation-review",
                    }
                )
            else:
                expected.add("local-ordinance-draft-review")
            self.assertEqual(expected, additions)

    def test_skill_expansion_19_plus_patent_merge_contract(self) -> None:
        expected_additions = {
            "public-ai-impact-assessment-draft-review",
            "public-ai-risk-management-plan-review",
            "ai-product-procurement-readiness-check",
            "public-it-project-procedure-check",
            "local-finance-evidence-pack",
            "audit-finding-response-draft-review",
            "public-record-disclosure-redaction-review",
            "local-council-agenda-draft-review",
            "local-ordinance-draft-review",
            "procurement-specification-hwpx-review",
            "education-administrative-document-draft-review",
            "immigration-civil-complaint-triage-draft",
            "police-civil-complaint-triage-draft",
            "welfare-civil-complaint-triage-draft",
            "labor-civil-complaint-triage-draft",
            "disaster-public-message-draft-review",
            "construction-standard-bim-compliance-precheck",
            "building-permit-document-precheck",
            "official-notice-multilingual-translation-review",
        }
        skills = [skill for domain in self.data["domains"] for skill in domain["skills"]]
        by_name = {skill["name"]: skill for skill in skills}
        self.assertTrue(expected_additions.issubset(by_name))
        self.assertTrue(all(len(by_name[name]["task_checks"]) == 3 for name in expected_additions))
        self.assertEqual(
            "patent-prior-art-evidence-pack",
            by_name["korean-patent-lookup"]["capability"],
        )

    def test_domain_minimum_three_wave_one_contract(self) -> None:
        expected = {
            "재정": (
                "national-subsidy-project-evidence-review",
                "public-policy-evidence-pack",
                "지원대상 확정·교부결정·정책평가는 담당기관 승인으로 이관",
            ),
            "감사": (
                "audit-action-plan-evidence-review",
                "administrative-document-draft-review",
                "이행완료 판단·제출·수용 여부는 감사 담당자 승인",
            ),
            "출입국": (
                "immigration-statistics-policy-brief",
                "public-policy-evidence-pack",
                "체류자격·입국 허가·정책 해석은 담당기관 검토로 이관",
            ),
            "경찰": (
                "police-crime-statistics-brief",
                "kosis-official-statistics",
                "치안 수준·수사·개별 위험도 판단은 경찰 담당 검토로 이관",
            ),
            "재난안전": (
                "disaster-response-plan-evidence-review",
                "administrative-document-draft-review",
                "경보발령·대피·출동 판단은 공식기관 승인으로 이관",
            ),
            "교육행정": (
                "school-facility-safety-plan-review",
                "administrative-document-draft-review",
                "시설 안전판단·긴급조치·계획 승인은 학교 담당자에게 이관",
            ),
            "사회복지": (
                "welfare-eligibility-evidence-check",
                "public-policy-evidence-pack",
                "수급자격·지급액·신청 가능 여부는 담당기관 판단으로 이관",
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, (skill_name, capability, safety_handoff) in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                self.assertEqual("additional", skill["role"])
                self.assertEqual(capability, skill["capability"])
                self.assertEqual("draft-only", skill["boundary"])
                self.assertEqual(3, len(skill["task_checks"]))
                self.assertEqual(safety_handoff, skill["task_checks"][-1])

    def test_wave_one_minimum_three_mutation_fails_closed(self) -> None:
        protected_domains = (
            "재정",
            "감사",
            "출입국",
            "경찰",
            "재난안전",
            "교육행정",
            "사회복지",
        )
        for domain_name in protected_domains:
            with self.subTest(domain=domain_name):
                changed = copy.deepcopy(self.data)
                by_domain = {item["domain"]: item for item in changed["domains"]}
                moved = by_domain[domain_name]["skills"].pop()
                by_domain["세무"]["skills"].append(moved)
                errors = validate(changed, ROOT)
                self.assert_cross_domain_move_errors(
                    changed, domain_name, "세무", errors,
                )

    def test_wave_one_safety_task_checks_mutation_fails_closed(self) -> None:
        protected_skills = {
            "재정": "national-subsidy-project-evidence-review",
            "감사": "audit-action-plan-evidence-review",
            "출입국": "immigration-statistics-policy-brief",
            "경찰": "police-crime-statistics-brief",
            "재난안전": "disaster-response-plan-evidence-review",
            "교육행정": "school-facility-safety-plan-review",
            "사회복지": "welfare-eligibility-evidence-check",
        }
        for domain_name, skill_name in protected_skills.items():
            with self.subTest(domain=domain_name):
                changed = copy.deepcopy(self.data)
                by_domain = {item["domain"]: item for item in changed["domains"]}
                skill = next(
                    item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                )
                skill["task_checks"][-1] = "고위험 판단을 자동 수행"
                errors = validate(changed, ROOT)
                self.assert_skill_contract_field_error(
                    domain_name, skill_name, "task_checks", errors,
                )

    def test_domain_minimum_three_wave_two_contract(self) -> None:
        expected = {
            "고용노동": (
                "industrial-accident-statistics-brief",
                "산업재해 통계 근거 브리프",
                "kosis-official-statistics",
                (
                    "산업재해 지표의 기준기간·업종·재해유형·집계단위를 분리",
                    "공식 고용노동·KOSIS 통계표 코드·조회일·통계 기준을 보존",
                    "산재 인정·사업장 위험도·제재 판단은 담당기관 검토로 이관",
                ),
            ),
            "토목시설": (
                "infrastructure-maintenance-evidence-review",
                "기반시설 유지관리 근거 검토",
                "administrative-document-draft-review",
                (
                    "시설·구간·점검일·손상유형·조치상태·증빙을 분리",
                    "공식 기준·점검보고서·사진·도면 참조와 증빙 공백을 구분",
                    "시설 안전등급·통제·보수 우선순위는 기술자·관리기관 승인으로 이관",
                ),
            ),
            "건축": (
                "building-code-citation-check",
                "건축기준 조문 인용 점검",
                "korean-legal-citation-verification",
                (
                    "용도·규모·지역·행위별 적용 법령 후보와 기준시점을 분리",
                    "국가법령정보센터의 조문·시행일·인용문과 공식 URL을 보존",
                    "설계 적합성·허가 가능 여부·법적 해석은 건축사·허가권자 검토로 이관",
                ),
            ),
            "전산": (
                "public-it-security-checklist-review",
                "공공 정보시스템 보안 체크리스트 검토",
                "public-it-project-procedure-review",
                (
                    "시스템·데이터등급·위협·통제·검증증빙을 항목별로 분리",
                    "공식 보안·개인정보·정보화 지침의 버전·URL·조회일을 보존",
                    "보안 적합성·취약점 수용·운영 승인은 보안책임자 검토로 이관",
                ),
            ),
            "기록관리": (
                "records-retention-schedule-review",
                "기록물 보존기간표 검토",
                "public-records-lifecycle-review",
                (
                    "기록물계열·업무기능·보존기산점·보존기간 후보를 분리",
                    "공식 기록관리기준·법령 URL과 조회일 및 근거 공백을 보존",
                    "보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인으로 이관",
                ),
            ),
            "지방의회": (
                "local-council-budget-bill-comparison",
                "지방의회 예산안 비교 브리프",
                "public-policy-evidence-pack",
                (
                    "예산안·수정안·심사보고서의 회계연도·사업·금액·근거를 분리",
                    "공식 의안·회의록·예산서 URL과 조회일 및 문서 버전을 보존",
                    "증감 적정성·재정 영향·의결 판단은 지방의회 담당자 검토로 이관",
                ),
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, (skill_name, title, capability, task_checks) in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                self.assertEqual(title, skill["title"])
                self.assertEqual(capability, skill["capability"])
                self.assertEqual("additional", skill["role"])
                self.assertEqual("draft-only", skill["boundary"])
                self.assertEqual(task_checks, tuple(skill["task_checks"]))

    def test_wave_two_minimum_three_mutation_fails_closed(self) -> None:
        for domain_name in ("고용노동", "토목시설", "건축", "전산", "기록관리", "지방의회"):
            with self.subTest(domain=domain_name):
                changed = copy.deepcopy(self.data)
                by_domain = {item["domain"]: item for item in changed["domains"]}
                moved = by_domain[domain_name]["skills"].pop()
                by_domain["세무"]["skills"].append(moved)
                errors = validate(changed, ROOT)
                self.assert_cross_domain_move_errors(
                    changed, domain_name, "세무", errors,
                )

    def test_wave_two_contract_mutations_fail_closed(self) -> None:
        protected = {
            "고용노동": "industrial-accident-statistics-brief",
            "토목시설": "infrastructure-maintenance-evidence-review",
            "건축": "building-code-citation-check",
            "전산": "public-it-security-checklist-review",
            "기록관리": "records-retention-schedule-review",
            "지방의회": "local-council-budget-bill-comparison",
        }
        for domain_name, skill_name in protected.items():
            for mutation, field, value in (
                ("title", "title", "다른 제목"),
                ("capability", "capability", "official-source-research"),
                ("role", "role", "primary"),
                ("references", "reference_skills", ["korean-law-search"]),
                ("boundary", "boundary", "manual-review-only"),
                ("unsafe-handoff", "task_checks", ["고위험 판단을 자동 수행"]),
                ("reordered-checks", "task_checks", None),
            ):
                with self.subTest(domain=domain_name, mutation=mutation):
                    changed = copy.deepcopy(self.data)
                    by_domain = {item["domain"]: item for item in changed["domains"]}
                    skill = next(
                        item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                    )
                    skill[field] = list(reversed(skill[field])) if value is None else value
                    errors = validate(changed, ROOT)
                    if mutation == "role":
                        domain_index = list(by_domain).index(domain_name)
                        self.assertEqual(
                            [f'V6_INVALID_VALUE "/domains/{domain_index}/skills"'],
                            errors,
                        )
                    else:
                        self.assert_skill_contract_field_error(
                            domain_name, skill_name, self.contract_field_for_mutation(mutation), errors,
                        )

    def test_wave_two_capability_contract_mutations_fail_closed(self) -> None:
        for mutation, field, value in (
            ("service", "service", "일반 기록물 검색"),
            ("side-effect", "side_effect_class", "read-only"),
            ("handoff", "manual_handoff_gate", "자동 폐기 가능"),
            ("provenance-order", "source_provenance", None),
            ("execution-status", "execution_status", "blocked"),
        ):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.data)
                capability = next(
                    item
                    for item in changed["shared_capabilities"]
                    if item["slug"] == "public-records-lifecycle-review"
                )
                capability[field] = list(reversed(capability[field])) if value is None else value
                errors = validate(changed, ROOT)
                self.assert_capability_contract_field_error(
                    "public-records-lifecycle-review", field, errors,
                )

    def test_domain_minimum_three_wave_three_contract(self) -> None:
        expected = {
            "입법": (
                (
                    "bill-comparison-impact-brief",
                    "법안 비교·영향 근거 브리프",
                    "korean-law-bill-research",
                    (
                        "법안·대안·수정안별 의안번호·기준일·처리단계·조문 차이를 분리",
                        "국가법령정보·국회 공개정보의 공식 URL·조회일·문서 버전을 보존",
                        "법적 효력·정책 영향·채택 여부 판단은 입법·법무 담당자 검토로 이관",
                    ),
                ),
                (
                    "committee-minutes-evidence-pack",
                    "상임위원회 회의록 근거 팩",
                    "korean-law-bill-research",
                    (
                        "위원회·회기·안건·회의일·의결 결과를 문서 단위로 분리",
                        "공식 회의록·심사보고서·의안정보 URL·공개일·조회일을 보존",
                        "발언 취지·정치적 평가·의결 해석은 입법 담당자 검토로 이관",
                    ),
                ),
            ),
            "교육": (
                (
                    "education-statistics-brief",
                    "교육통계 근거 브리프",
                    "kosis-official-statistics",
                    (
                        "지표명·학제·지역·학년도·분모·단위를 분리",
                        "KOSIS 통계표 코드·작성기관·수록기간·조회일·개정 상태를 보존",
                        "학교·학생 평가·정책 효과·자원배분 판단은 교육 담당기관 검토로 이관",
                    ),
                ),
                (
                    "school-policy-document-review",
                    "학교 정책문서 검토",
                    "administrative-document-draft-review",
                    (
                        "정책 대상·적용기관·시행일·의무·권고·근거 문서를 분리",
                        "교육부·법령 공식 URL·조회일·문서 버전과 근거 공백을 보존",
                        "법적 해석·학교별 적용·공문 확정·발송은 교육 담당자 승인으로 이관",
                    ),
                ),
            ),
            "국토교통": (
                (
                    "transport-policy-project-evidence-pack",
                    "교통정책·사업 근거 팩",
                    "public-policy-evidence-pack",
                    (
                        "사업·노선·구간·단계·예산·일정 주장을 항목별로 분리",
                        "공식 1차 자료로 입력된 URL·조회일·문서 버전과 상충·미수집 근거를 구분",
                        "사업 타당성·우선순위·예산 승인·노선 결정은 담당기관 검토로 이관",
                    ),
                ),
                (
                    "traffic-safety-statistics-brief",
                    "교통안전 통계 근거 브리프",
                    "kosis-official-statistics",
                    (
                        "기준기간·지역·도로유형·사고유형·지표·분모·단위를 분리",
                        "KOSIS 통계표 코드·작성기관·조회일·통계 기준·개정 상태를 보존",
                        "위험도 순위·단속·시설 개선 우선순위는 교통안전 담당기관 검토로 이관",
                    ),
                ),
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, contracts in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                for skill_name, title, capability, task_checks in contracts:
                    skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                    self.assertEqual(title, skill["title"])
                    self.assertEqual(capability, skill["capability"])
                    self.assertEqual("additional", skill["role"])
                    self.assertEqual([], skill["reference_skills"])
                    self.assertEqual("draft-only", skill["boundary"])
                    self.assertEqual(task_checks, tuple(skill["task_checks"]))

    def test_wave_three_contract_mutations_fail_closed(self) -> None:
        protected = {
            "입법": ("bill-comparison-impact-brief", "committee-minutes-evidence-pack"),
            "교육": ("education-statistics-brief", "school-policy-document-review"),
            "국토교통": (
                "transport-policy-project-evidence-pack",
                "traffic-safety-statistics-brief",
            ),
        }
        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                for mutation in (
                    "title",
                    "capability",
                    "role",
                    "references",
                    "boundary",
                    "task-check-replacement",
                    "task-check-delete",
                    "task-check-append",
                    "task-check-reorder",
                    "task-check-empty",
                ):
                    with self.subTest(domain=domain_name, skill=skill_name, mutation=mutation):
                        changed = copy.deepcopy(self.data)
                        by_domain = {item["domain"]: item for item in changed["domains"]}
                        skill = next(
                            item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                        )
                        if mutation == "title":
                            skill["title"] = "다른 제목"
                        elif mutation == "capability":
                            skill["capability"] = "official-source-research"
                        elif mutation == "role":
                            skill["role"] = "primary"
                        elif mutation == "references":
                            skill["reference_skills"] = ["korean-law-search"]
                        elif mutation == "boundary":
                            skill["boundary"] = "manual-review-only"
                        elif mutation == "task-check-replacement":
                            skill["task_checks"][0] = "자동 판단을 허용"
                        elif mutation == "task-check-delete":
                            skill["task_checks"].pop(0)
                        elif mutation == "task-check-append":
                            skill["task_checks"].append("자동 제출")
                        elif mutation == "task-check-reorder":
                            skill["task_checks"].reverse()
                        else:
                            skill["task_checks"] = []
                        errors = validate(changed, ROOT)
                        if mutation == "task-check-empty":
                            skill_index = by_domain[domain_name]["skills"].index(skill)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{list(by_domain).index(domain_name)}/skills/{skill_index}/task_checks"'],
                                errors,
                            )
                        elif mutation == "role":
                            domain_index = list(by_domain).index(domain_name)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{domain_index}/skills"'],
                                errors,
                            )
                        else:
                            self.assert_skill_contract_field_error(
                                domain_name, skill_name, self.contract_field_for_mutation(mutation), errors,
                            )

        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                with self.subTest(domain=domain_name, skill=skill_name, mutation="cross-domain"):
                    changed = copy.deepcopy(self.data)
                    by_domain = {item["domain"]: item for item in changed["domains"]}
                    index = next(
                        index
                        for index, item in enumerate(by_domain[domain_name]["skills"])
                        if item["name"] == skill_name
                    )
                    moved = by_domain[domain_name]["skills"].pop(index)
                    by_domain["세무"]["skills"].append(moved)
                    errors = validate(changed, ROOT)
                    self.assert_cross_domain_move_errors(
                        changed, domain_name, "세무", errors,
                    )

    def test_domain_minimum_three_wave_four_contract(self) -> None:
        expected = {
            "사법": (
                (
                    "judgment-citation-evidence-pack",
                    "판결 인용 근거 팩",
                    "korean-legal-citation-verification",
                    (
                        "법원·사건번호·선고일·판례 원문 식별자와 정확한 인용 위치를 분리",
                        "국가법령정보 공식 원문 URL·조회일·적용 법령 버전과 불일치·복수 후보를 보존",
                        "법률적 효력·사안 적용·소송 제출 여부는 법무 담당자 최종 검토로 이관",
                    ),
                ),
                (
                    "court-statistics-evidence-brief",
                    "법원 통계 근거 브리프",
                    "public-policy-evidence-pack",
                    (
                        "작성기관·통계표 또는 보고서 식별자·기준기간·분모·단위·절차 단계를 분리",
                        "공식 자료로 입력된 URL·공표일·조회일·문서 버전과 상충·미수집 근거를 구분",
                        "사건 결과 예측·법원 또는 재판부 평가·정책 판단은 사법 담당자 검토로 이관",
                    ),
                ),
            ),
            "보건의료": (
                (
                    "healthcare-policy-statistics-brief",
                    "보건의료 정책통계 브리프",
                    "kosis-official-statistics",
                    (
                        "지표명·지역·기간·기관 또는 질환 범주·분모·단위·집계 기준을 분리",
                        "KOSIS 통계표 코드·작성기관·수록기간·조회일·개정 상태와 결측을 보존",
                        "진단·치료·기관 서열화·정책 효과 판단은 보건의료 담당기관 검토로 이관",
                    ),
                ),
                (
                    "medical-benefit-criteria-evidence-pack",
                    "급여기준 근거 팩",
                    "public-policy-evidence-pack",
                    (
                        "급여기준 주장을 대상·조건·예외·시행일·적용 시점 단위로 분리",
                        "공식 자료로 입력된 URL·조회일·문서 버전·개정 상태와 상충·미수집 근거를 구분",
                        "환자별 급여 여부·진료·처방·청구 판단은 의료전문가와 담당기관 검토로 이관",
                    ),
                ),
            ),
            "식품의약": (
                (
                    "food-drug-recall-evidence-brief",
                    "식품·의약품 회수 근거 브리프",
                    "welfare-health-safety-research",
                    (
                        "제품명·업체·품목 식별자·회수 등급·대상 제조번호·유통기한을 분리",
                        "식약처·공공데이터 응답의 공식 endpoint·조회일·공표일·정정 상태와 미확인 항목을 보존",
                        "복약·섭취 중단·행정처분·현장 회수 집행은 식약처·전문가·담당자 확인으로 이관",
                    ),
                ),
                (
                    "regulatory-notice-comparison-review",
                    "식품의약 규제고시 비교 검토",
                    "public-policy-evidence-pack",
                    (
                        "고시·공고·행정예고별 발행기관·문서번호·공포일·시행일·적용 대상을 분리",
                        "공식 자료로 입력된 URL·조회일·문서 버전과 변경 전후·경과조치·상충·미수집 근거를 구분",
                        "법적 효력·개별 사안 적용·기관 대응·발송·집행은 식품의약 담당자 검토로 이관",
                    ),
                ),
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, contracts in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                for skill_name, title, capability, task_checks in contracts:
                    skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                    self.assertEqual(title, skill["title"])
                    self.assertEqual(capability, skill["capability"])
                    self.assertEqual("additional", skill["role"])
                    self.assertEqual([], skill["reference_skills"])
                    self.assertEqual("draft-only", skill["boundary"])
                    self.assertEqual(task_checks, tuple(skill["task_checks"]))

    def test_wave_four_contract_mutations_fail_closed(self) -> None:
        protected = {
            "사법": ("judgment-citation-evidence-pack", "court-statistics-evidence-brief"),
            "보건의료": (
                "healthcare-policy-statistics-brief",
                "medical-benefit-criteria-evidence-pack",
            ),
            "식품의약": (
                "food-drug-recall-evidence-brief",
                "regulatory-notice-comparison-review",
            ),
        }
        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                for mutation in (
                    "title",
                    "capability",
                    "role",
                    "references",
                    "boundary",
                    "task-check-replacement",
                    "task-check-delete",
                    "task-check-append",
                    "task-check-reorder",
                    "task-check-empty",
                ):
                    with self.subTest(domain=domain_name, skill=skill_name, mutation=mutation):
                        changed = copy.deepcopy(self.data)
                        by_domain = {item["domain"]: item for item in changed["domains"]}
                        skill = next(
                            item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                        )
                        if mutation == "title":
                            skill["title"] = "다른 제목"
                        elif mutation == "capability":
                            skill["capability"] = "official-source-research"
                        elif mutation == "role":
                            skill["role"] = "primary"
                        elif mutation == "references":
                            skill["reference_skills"] = ["korean-law-search"]
                        elif mutation == "boundary":
                            skill["boundary"] = "manual-review-only"
                        elif mutation == "task-check-replacement":
                            skill["task_checks"][0] = "자동 판단을 허용"
                        elif mutation == "task-check-delete":
                            skill["task_checks"].pop(0)
                        elif mutation == "task-check-append":
                            skill["task_checks"].append("자동 제출")
                        elif mutation == "task-check-reorder":
                            skill["task_checks"].reverse()
                        else:
                            skill["task_checks"] = []
                        errors = validate(changed, ROOT)
                        if mutation == "task-check-empty":
                            skill_index = by_domain[domain_name]["skills"].index(skill)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{list(by_domain).index(domain_name)}/skills/{skill_index}/task_checks"'],
                                errors,
                            )
                        elif mutation == "role":
                            domain_index = list(by_domain).index(domain_name)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{domain_index}/skills"'],
                                errors,
                            )
                        else:
                            self.assert_skill_contract_field_error(
                                domain_name, skill_name, self.contract_field_for_mutation(mutation), errors,
                            )

        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                with self.subTest(domain=domain_name, skill=skill_name, mutation="cross-domain"):
                    changed = copy.deepcopy(self.data)
                    by_domain = {item["domain"]: item for item in changed["domains"]}
                    index = next(
                        index
                        for index, item in enumerate(by_domain[domain_name]["skills"])
                        if item["name"] == skill_name
                    )
                    moved = by_domain[domain_name]["skills"].pop(index)
                    by_domain["세무"]["skills"].append(moved)
                    errors = validate(changed, ROOT)
                    self.assert_cross_domain_move_errors(
                        changed, domain_name, "세무", errors,
                    )

    def test_domain_minimum_three_wave_five_contract(self) -> None:
        expected = {
            "통계": (
                (
                    "official-statistics-methodology-evidence-review",
                    "공식통계 방법론 근거 검토",
                    "public-policy-evidence-pack",
                    (
                        "통계명·통계표 코드·작성기관·작성목적·작성주기·조사대상·모집단·표본·가중치를 분리",
                        "공식 자료로 입력된 URL·공표일·조회일·방법론 버전·개정 이력과 상충·미수집 근거를 구분",
                        "방법론 적합성·통계 품질등급·정책 적용 판단은 통계 담당자 최종 검토로 이관",
                    ),
                ),
                (
                    "statistical-release-evidence-brief",
                    "통계 공표 근거 브리프",
                    "kosis-official-statistics",
                    (
                        "통계표 코드·지표·분류·기준기간·분모·단위·잠정 또는 확정 상태를 분리",
                        "KOSIS 통계표 코드·작성기관·수록기간·공표일·조회일·개정 상태·결측·시계열 단절을 보존",
                        "추세 해석·인과관계·정책효과·공식 입장 판단은 통계 담당자 검토로 이관",
                    ),
                ),
            ),
            "소방": (
                (
                    "fire-safety-standard-evidence-pack",
                    "소방안전 기준 근거 팩",
                    "public-policy-evidence-pack",
                    (
                        "시설유형·점검대상·적용 법령·고시·안전기준·시행일을 분리",
                        "공식 자료로 입력된 URL·문서번호·공표일·조회일·개정 상태와 상충·미수집 근거를 구분",
                        "적합·부적합 판정·시정명령·과태료·현장 점검·안전조치는 소방 담당기관과 전문가에게 이관",
                    ),
                ),
                (
                    "fire-response-statistics-brief",
                    "소방 대응통계 브리프",
                    "kosis-official-statistics",
                    (
                        "화재유형·지역·기준기간·출동 또는 진압 단계·지표·분모·단위를 분리",
                        "KOSIS 통계표 코드·작성기관·공표일·조회일·개정 상태·결측을 보존",
                        "위험도 순위·인력 또는 장비 배치·현장 대응·예방정책 우선순위는 소방 담당기관에 이관",
                    ),
                ),
            ),
            "과학기술": (
                (
                    "national-rd-program-evidence-brief",
                    "국가 R&D 사업 근거 브리프",
                    "public-policy-evidence-pack",
                    (
                        "사업명·사업 또는 과제 식별자·주관기관·공고번호·기간·예산·추진상태를 분리",
                        "공식 자료로 입력된 NTIS·부처 URL·공표일·조회일·문서 버전과 상충·미수집 근거를 구분",
                        "지원자격·선정·평가·예산배분·과제 수행 판단은 연구개발 담당기관에 이관",
                    ),
                ),
                (
                    "technology-impact-evidence-pack",
                    "과학기술 영향 근거 팩",
                    "public-policy-evidence-pack",
                    (
                        "기술·정책 주장별 기준선·지표·기간·대상·단위와 상관 또는 인과 표현을 분리",
                        "공식 자료로 입력된 URL·발행기관·공표일·조회일·방법론·문서 버전과 상충·미수집 근거를 구분",
                        "인과효과·기술성숙도·투자·규제·사업 우선순위 판단은 과학기술 담당자와 전문가 검토로 이관",
                    ),
                ),
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, contracts in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                for skill_name, title, capability, task_checks in contracts:
                    skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                    self.assertEqual(title, skill["title"])
                    self.assertEqual(capability, skill["capability"])
                    self.assertEqual("additional", skill["role"])
                    self.assertEqual([], skill["reference_skills"])
                    self.assertEqual("draft-only", skill["boundary"])
                    self.assertEqual(task_checks, tuple(skill["task_checks"]))

    def test_wave_five_contract_mutations_fail_closed(self) -> None:
        protected = {
            "통계": (
                "official-statistics-methodology-evidence-review",
                "statistical-release-evidence-brief",
            ),
            "소방": ("fire-safety-standard-evidence-pack", "fire-response-statistics-brief"),
            "과학기술": ("national-rd-program-evidence-brief", "technology-impact-evidence-pack"),
        }
        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                for mutation in (
                    "title",
                    "capability",
                    "role",
                    "references",
                    "boundary",
                    "task-check-replacement",
                    "task-check-delete",
                    "task-check-append",
                    "task-check-reorder",
                    "task-check-empty",
                ):
                    with self.subTest(domain=domain_name, skill=skill_name, mutation=mutation):
                        changed = copy.deepcopy(self.data)
                        by_domain = {item["domain"]: item for item in changed["domains"]}
                        skill = next(
                            item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                        )
                        if mutation == "title":
                            skill["title"] = "다른 제목"
                        elif mutation == "capability":
                            skill["capability"] = "official-source-research"
                        elif mutation == "role":
                            skill["role"] = "primary"
                        elif mutation == "references":
                            skill["reference_skills"] = ["korean-law-search"]
                        elif mutation == "boundary":
                            skill["boundary"] = "manual-review-only"
                        elif mutation == "task-check-replacement":
                            skill["task_checks"][0] = "자동 판단을 허용"
                        elif mutation == "task-check-delete":
                            skill["task_checks"].pop(0)
                        elif mutation == "task-check-append":
                            skill["task_checks"].append("자동 제출")
                        elif mutation == "task-check-reorder":
                            skill["task_checks"].reverse()
                        else:
                            skill["task_checks"] = []
                        errors = validate(changed, ROOT)
                        if mutation == "task-check-empty":
                            skill_index = by_domain[domain_name]["skills"].index(skill)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{list(by_domain).index(domain_name)}/skills/{skill_index}/task_checks"'],
                                errors,
                            )
                        elif mutation == "role":
                            domain_index = list(by_domain).index(domain_name)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{domain_index}/skills"'],
                                errors,
                            )
                        else:
                            self.assert_skill_contract_field_error(
                                domain_name, skill_name, self.contract_field_for_mutation(mutation), errors,
                            )

        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                with self.subTest(domain=domain_name, skill=skill_name, mutation="cross-domain"):
                    changed = copy.deepcopy(self.data)
                    by_domain = {item["domain"]: item for item in changed["domains"]}
                    index = next(
                        index
                        for index, item in enumerate(by_domain[domain_name]["skills"])
                        if item["name"] == skill_name
                    )
                    moved = by_domain[domain_name]["skills"].pop(index)
                    by_domain["세무"]["skills"].append(moved)
                    errors = validate(changed, ROOT)
                    self.assert_cross_domain_move_errors(
                        changed, domain_name, "세무", errors,
                    )

    def test_domain_minimum_three_wave_six_contract(self) -> None:
        expected = {
            "선거관리": (
                (
                    "election-law-procedure-evidence-review",
                    "선거법·절차 근거 검토",
                    "public-policy-evidence-pack",
                    (
                        "선거유형·선거일·절차단계·행위주체·적용 법령·조문·기준시점을 분리",
                        "공식 자료로 입력된 선관위·국가법령정보 URL·문서 식별자·조회일·시행일·개정 상태와 상충·미수집 근거를 구분",
                        "위법성·후보자격·등록수리·제재·이의처리 판단은 선거관리위원회와 법무 담당자 검토로 이관",
                    ),
                ),
                (
                    "election-result-statistics-evidence-brief",
                    "선거결과 통계 근거 브리프",
                    "public-policy-evidence-pack",
                    (
                        "선거종류·회차·선거구·후보 또는 정당·기준일·득표수·득표율·투표율·분모·무효표를 분리",
                        "공식 자료로 입력된 선거통계 URL·공표일·조회일·정정 상태와 상충·미수집 근거를 구분",
                        "당락·재검표·선거무효·정치적 평가·인과관계 판단은 선거관리위원회와 담당자 검토로 이관",
                    ),
                ),
            ),
            "특허": (
                (
                    "patent-claim-citation-evidence-review",
                    "특허 청구항 인용 근거 검토",
                    "patent-prior-art-evidence-pack",
                    (
                        "출원번호·공개번호·등록번호·청구항 버전·청구항 요소·인용 문헌번호·인용 위치를 분리",
                        "KIPRIS·지식재산처 공식 URL·공개일·조회일·공개 또는 등록 상태와 미확인·복수 후보를 보존",
                        "신규성·진보성·침해·유효성·출원전략 판단은 변리사와 특허 담당자 검토로 이관",
                    ),
                ),
                (
                    "ip-policy-statistics-evidence-brief",
                    "지식재산 정책통계 근거 브리프",
                    "public-policy-evidence-pack",
                    (
                        "권리유형·정책 또는 사업·기준기간·출원인 범주·지역·건수·분모·단위를 분리",
                        "공식 자료로 입력된 지식재산처·KIPRIS URL·보고서 또는 통계표 식별자·공표일·조회일·개정 상태와 결측을 구분",
                        "인과관계·정책효과·산업경쟁력·지원 또는 규제 우선순위 판단은 지식재산 담당자 검토로 이관",
                    ),
                ),
            ),
            "사이버보안": (
                (
                    "privacy-impact-evidence-review",
                    "개인정보 영향평가 근거 검토",
                    "public-policy-evidence-pack",
                    (
                        "시스템·처리업무·개인정보 유형·처리목적·정보주체·법적근거·처리흐름·보유기간·제3자 제공을 분리",
                        "공식 자료로 입력된 개인정보위·국가법령정보 URL·가이드 또는 법령 버전·조회일과 상충·미수집 근거를 구분",
                        "영향평가 실시대상·적합성·법적준수·승인 판단은 개인정보 보호책임자와 전문기관 검토로 이관",
                    ),
                ),
                (
                    "cyber-incident-response-plan-evidence-review",
                    "사이버 침해사고 대응계획 근거 검토",
                    "public-policy-evidence-pack",
                    (
                        "사고유형·시스템경계·자산·담당역할·보고경로·격리·복구·로그보존 항목을 분리",
                        "공식 자료로 입력된 KISA·국가 또는 기관 보안기준 URL·문서버전·시행일·조회일과 상충·미수집 근거를 구분",
                        "사고등급·차단·격리·포렌식·외부신고·현장대응 실행은 보안책임자와 관할기관 검토로 이관",
                    ),
                ),
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, contracts in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                for skill_name, title, capability, task_checks in contracts:
                    skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                    self.assertEqual(title, skill["title"])
                    self.assertEqual(capability, skill["capability"])
                    self.assertEqual("additional", skill["role"])
                    self.assertEqual([], skill["reference_skills"])
                    self.assertEqual("draft-only", skill["boundary"])
                    self.assertEqual(task_checks, tuple(skill["task_checks"]))

    def test_wave_six_contract_mutations_fail_closed(self) -> None:
        protected = {
            "선거관리": (
                "election-law-procedure-evidence-review",
                "election-result-statistics-evidence-brief",
            ),
            "특허": (
                "patent-claim-citation-evidence-review",
                "ip-policy-statistics-evidence-brief",
            ),
            "사이버보안": (
                "privacy-impact-evidence-review",
                "cyber-incident-response-plan-evidence-review",
            ),
        }
        mutation_count = 0
        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                for mutation in (
                    "title",
                    "capability",
                    "role",
                    "references",
                    "boundary",
                    "task-check-replacement",
                    "task-check-delete",
                    "task-check-append",
                    "task-check-reorder",
                    "task-check-empty",
                ):
                    mutation_count += 1
                    with self.subTest(domain=domain_name, skill=skill_name, mutation=mutation):
                        changed = copy.deepcopy(self.data)
                        by_domain = {item["domain"]: item for item in changed["domains"]}
                        skill = next(
                            item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                        )
                        if mutation == "title":
                            skill["title"] = "다른 제목"
                        elif mutation == "capability":
                            skill["capability"] = "official-source-research"
                        elif mutation == "role":
                            skill["role"] = "primary"
                        elif mutation == "references":
                            skill["reference_skills"] = ["korean-law-search"]
                        elif mutation == "boundary":
                            skill["boundary"] = "manual-review-only"
                        elif mutation == "task-check-replacement":
                            skill["task_checks"][0] = "자동 판단을 허용"
                        elif mutation == "task-check-delete":
                            skill["task_checks"].pop(0)
                        elif mutation == "task-check-append":
                            skill["task_checks"].append("자동 제출")
                        elif mutation == "task-check-reorder":
                            skill["task_checks"].reverse()
                        else:
                            skill["task_checks"] = []
                        errors = validate(changed, ROOT)
                        if mutation == "task-check-empty":
                            skill_index = by_domain[domain_name]["skills"].index(skill)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{list(by_domain).index(domain_name)}/skills/{skill_index}/task_checks"'],
                                errors,
                            )
                        elif mutation == "role":
                            domain_index = list(by_domain).index(domain_name)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{domain_index}/skills"'],
                                errors,
                            )
                        else:
                            self.assert_skill_contract_field_error(
                                domain_name, skill_name, self.contract_field_for_mutation(mutation), errors,
                            )

        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                mutation_count += 1
                with self.subTest(domain=domain_name, skill=skill_name, mutation="cross-domain"):
                    changed = copy.deepcopy(self.data)
                    by_domain = {item["domain"]: item for item in changed["domains"]}
                    index = next(
                        index
                        for index, item in enumerate(by_domain[domain_name]["skills"])
                        if item["name"] == skill_name
                    )
                    moved = by_domain[domain_name]["skills"].pop(index)
                    by_domain["세무"]["skills"].append(moved)
                    errors = validate(changed, ROOT)
                    self.assert_cross_domain_move_errors(
                        changed, domain_name, "세무", errors,
                    )
        self.assertEqual(66, mutation_count)

    def test_domain_minimum_three_wave_seven_contract(self) -> None:
        expected = {
            "관세": (
                (
                    "customs-origin-document-precheck",
                    "원산지 증빙서류 사전점검",
                    "regulated-trade-procedure-precheck",
                    (
                        "거래·품목·HS 코드·협정·원산지 기준·증빙서류·기준시점을 분리",
                        "관세청·UNI-PASS·FTA 포털 공식 URL·문서 식별자·발급 또는 조회일·유효기간과 누락·상충 근거를 구분",
                        "원산지 판정·특혜관세 적용·신고·제출·통관·제재 판단은 관세사와 세관 담당자 검토로 이관",
                    ),
                ),
                (
                    "customs-trade-statistics-brief",
                    "관세 무역통계 브리프",
                    "public-policy-evidence-pack",
                    (
                        "기준기간·수출입 구분·상대국·HS 코드·수량·금액·단위·정정 상태를 분리",
                        "관세청 무역통계 공식 URL·통계표 또는 품목 식별자·공표일·조회일·잠정 또는 확정 상태와 결측·개정을 구분",
                        "추세·인과관계·정책효과·세율 또는 통관 판단은 관세 통계 담당자 검토로 이관",
                    ),
                ),
            ),
            "외교": (
                (
                    "treaty-diplomatic-document-source-check",
                    "조약·외교문서 출처 점검",
                    "public-policy-evidence-pack",
                    (
                        "조약명·조약번호·당사국·서명일·비준일·발효일·언어·문서 버전을 분리",
                        "외교부 조약정보 안내(https://www.mofa.go.kr/www/wpge/m_24251/contents.do)와 조약정보시스템(https://treatyweb.mofa.go.kr/) 공식 URL·문서 식별자·공표일·조회일·개정 또는 종료 상태와 상충·미수집 근거를 구분",
                        "조약의 효력·법적 해석·외교적 입장·국제법 판단은 외교부와 법무 담당자 검토로 이관",
                    ),
                ),
                (
                    "overseas-safety-country-brief",
                    "해외안전 국가 브리프",
                    "public-policy-evidence-pack",
                    (
                        "국가·지역·여행경보 단계·안전공지 유형·기준일·긴급 연락처를 분리",
                        "외교부 해외안전여행 공식 URL·공표일·조회일·갱신 상태와 상충·미수집 근거를 구분",
                        "여행·철수·대피·영사조력·현장 긴급대응 판단은 외교부와 관할 공관으로 이관",
                    ),
                ),
            ),
            "통일": (
                (
                    "inter-korean-policy-timeline-evidence-pack",
                    "남북관계 정책연표 근거 팩",
                    "public-policy-evidence-pack",
                    (
                        "사건·정책·행위주체·공식문서·발생일·공표일·진행 상태를 연표 항목별 분리",
                        "통일부 공식 URL·문서 식별자·공표일·조회일·문서 버전과 상충·미수집 근거를 구분",
                        "정부 공식입장·법적 또는 정치적 평가·관계 전망 판단은 통일부와 담당 연구자 검토로 이관",
                    ),
                ),
                (
                    "dmz-policy-source-brief",
                    "DMZ 정책 출처 브리프",
                    "public-policy-evidence-pack",
                    (
                        "지역·시설·사업·적용 규정·출입 조건·기준일·운영 상태를 분리",
                        "통일부와 관계기관 공식 URL·문서 식별자·공표일·조회일·개정 상태와 근거 공백을 구분",
                        "출입 승인·군사보안·현장 운영·환경 또는 법적 판단은 관할 기관과 담당자 검토로 이관",
                    ),
                ),
            ),
        }
        by_domain = {item["domain"]: item for item in self.data["domains"]}
        for domain_name, contracts in expected.items():
            with self.subTest(domain=domain_name):
                domain = by_domain[domain_name]
                self.assertGreaterEqual(len(domain["skills"]), 5)
                for skill_name, title, capability, task_checks in contracts:
                    skill = next(item for item in domain["skills"] if item["name"] == skill_name)
                    self.assertEqual(title, skill["title"])
                    self.assertEqual(capability, skill["capability"])
                    self.assertEqual("additional", skill["role"])
                    self.assertEqual([], skill["reference_skills"])
                    self.assertEqual("draft-only", skill["boundary"])
                    self.assertEqual(task_checks, tuple(skill["task_checks"]))

    def test_wave_seven_contract_mutations_fail_closed(self) -> None:
        protected = {
            "관세": (
                "customs-origin-document-precheck",
                "customs-trade-statistics-brief",
            ),
            "외교": (
                "treaty-diplomatic-document-source-check",
                "overseas-safety-country-brief",
            ),
            "통일": (
                "inter-korean-policy-timeline-evidence-pack",
                "dmz-policy-source-brief",
            ),
        }
        mutation_count = 0
        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                for mutation in (
                    "title",
                    "capability",
                    "role",
                    "references",
                    "boundary",
                    "task-check-replacement",
                    "task-check-delete",
                    "task-check-append",
                    "task-check-reorder",
                    "task-check-empty",
                ):
                    mutation_count += 1
                    with self.subTest(domain=domain_name, skill=skill_name, mutation=mutation):
                        changed = copy.deepcopy(self.data)
                        by_domain = {item["domain"]: item for item in changed["domains"]}
                        skill = next(
                            item for item in by_domain[domain_name]["skills"] if item["name"] == skill_name
                        )
                        if mutation == "title":
                            skill["title"] = "다른 제목"
                        elif mutation == "capability":
                            skill["capability"] = "official-source-research"
                        elif mutation == "role":
                            skill["role"] = "primary"
                        elif mutation == "references":
                            skill["reference_skills"] = ["korean-law-search"]
                        elif mutation == "boundary":
                            skill["boundary"] = "manual-review-only"
                        elif mutation == "task-check-replacement":
                            skill["task_checks"][0] = "자동 판단을 허용"
                        elif mutation == "task-check-delete":
                            skill["task_checks"].pop(0)
                        elif mutation == "task-check-append":
                            skill["task_checks"].append("자동 제출")
                        elif mutation == "task-check-reorder":
                            skill["task_checks"].reverse()
                        else:
                            skill["task_checks"] = []
                        errors = validate(changed, ROOT)
                        if mutation == "task-check-empty":
                            skill_index = by_domain[domain_name]["skills"].index(skill)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{list(by_domain).index(domain_name)}/skills/{skill_index}/task_checks"'],
                                errors,
                            )
                        elif mutation == "role":
                            domain_index = list(by_domain).index(domain_name)
                            self.assertEqual(
                                [f'V6_INVALID_VALUE "/domains/{domain_index}/skills"'],
                                errors,
                            )
                        else:
                            self.assert_skill_contract_field_error(
                                domain_name, skill_name, self.contract_field_for_mutation(mutation), errors,
                            )

        for domain_name, skill_names in protected.items():
            for skill_name in skill_names:
                mutation_count += 1
                with self.subTest(domain=domain_name, skill=skill_name, mutation="cross-domain"):
                    changed = copy.deepcopy(self.data)
                    by_domain = {item["domain"]: item for item in changed["domains"]}
                    index = next(
                        index
                        for index, item in enumerate(by_domain[domain_name]["skills"])
                        if item["name"] == skill_name
                    )
                    moved = by_domain[domain_name]["skills"].pop(index)
                    by_domain["세무"]["skills"].append(moved)
                    errors = validate(changed, ROOT)
                    self.assert_cross_domain_move_errors(
                        changed, domain_name, "세무", errors,
                    )
        for mutation in (
            "service",
            "credential_class",
            "proxy_mode",
            "side_effect_class",
            "manual_handoff_gate",
            "source_provenance",
            "execution_status",
            "live_smoke",
        ):
            mutation_count += 1
            with self.subTest(capability="regulated-trade-procedure-precheck", mutation=mutation):
                changed = copy.deepcopy(self.data)
                capability = next(
                    item
                    for item in changed["shared_capabilities"]
                    if item["slug"] == "regulated-trade-procedure-precheck"
                )
                replacements = {
                    "service": "다른 서비스",
                    "credential_class": "operator-held",
                    "proxy_mode": "required",
                    "side_effect_class": "read-only",
                    "manual_handoff_gate": "자동 승인",
                    "source_provenance": ["https://example.org/"],
                    "execution_status": "planned",
                    "live_smoke": "blocked",
                }
                capability[mutation] = replacements[mutation]
                errors = validate(changed, ROOT)
                self.assert_capability_contract_field_error(
                    "regulated-trade-procedure-precheck", mutation, errors,
                )
        self.assertEqual(74, mutation_count)

    def test_unknown_capability_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][0]["skills"][0]["capability"] = "secret-query-credential"
        errors = validate(changed, ROOT)
        self.assertEqual(
            ['V6_UNKNOWN_REFERENCE "/domains/0/skills/0/capability"'],
            errors,
        )
        self.assertNotIn("secret-query-credential", "\n".join(errors))

    def test_read_only_skill_cannot_route_to_draft_only_capability(self) -> None:
        changed = copy.deepcopy(self.data)
        skill = next(
            skill
            for domain in changed["domains"]
            for skill in domain["skills"]
            if skill["name"] == "audit-finding-response-draft-review"
        )
        skill["boundary"] = "read-only"
        errors = validate(changed, ROOT)
        domain_index = next(
            index for index, domain in enumerate(changed["domains"])
            if skill in domain["skills"]
        )
        skill_index = changed["domains"][domain_index]["skills"].index(skill)
        self.assertEqual(
            [f'V6_BINDING_MISMATCH "/domains/{domain_index}/skills/{skill_index}/boundary"'],
            errors,
        )

    def test_invalid_skill_container_is_rejected_without_crashing(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][0]["skills"] = None
        errors = validate(changed, ROOT)
        self.assertEqual(['V6_INVALID_TYPE "/domains/0/skills"'], errors)

    def test_non_object_catalog_root_is_rejected_without_crashing(self) -> None:
        for bad in (None, 123, "x", ["domains"]):
            with self.subTest(bad=type(bad).__name__):
                errors = validate(bad, ROOT)
                self.assertEqual(['V6_INVALID_TYPE ""'], errors)

    def test_duplicate_domain_skill_name_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][1]["skills"][0]["name"] = changed["domains"][0]["skills"][0]["name"]
        errors = validate(changed, ROOT)
        self.assertEqual(
            ['V6_DUPLICATE_ID "/domains/1/skills/0/name"'],
            errors,
        )

    def test_duplicate_domain_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][1]["domain"] = changed["domains"][0]["domain"]
        errors = validate(changed, ROOT)
        self.assertEqual(['V6_DUPLICATE_ID "/domains/1/domain"'], errors)

    def test_live_status_requires_matching_smoke_evidence(self) -> None:
        changed = copy.deepcopy(self.data)
        capability = next(item for item in changed["shared_capabilities"] if item["slug"] == "official-source-research")
        capability["execution_status"] = "live-verified"
        errors = validate(changed, ROOT)
        self.assertEqual(
            ['V6_INVALID_VALUE "/shared_capabilities/7/live_smoke"'],
            errors,
        )

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
        self.assertIn("domain-owned Skill: **308개**", current)

    def test_generated_domain_skills_match_catalog(self) -> None:
        expected = expected_domain_skills(self.data, ROOT)
        self.assertEqual(308, len(expected))
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
        self.assertEqual(['V6_CONTRACT_INVARIANT ""'], errors)

    def test_misplaced_domain_skill_mutation_fails_closed(self) -> None:
        temp = self.copied_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "repo"
        source = next(root.glob("domains/*/skills/*/SKILL.md"))
        target = source.parents[1] / "rogue" / "SKILL.md"
        target.parent.mkdir(parents=True)
        source.replace(target)
        errors = validate(self.data, root)
        self.assertEqual(['V6_CONTRACT_INVARIANT "/domains"'], errors)

    def test_instruction_contract_mutation_fails_closed(self) -> None:
        temp = self.copied_repo()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "repo"
        claude = root / "CLAUDE.md"
        claude.write_text(
            claude.read_text(encoding="utf-8").replace("top-level `skills/`", "root capability surface"),
            encoding="utf-8",
        )
        errors = validate(self.data, root)
        self.assertEqual(['V6_CONTRACT_INVARIANT ""'], errors)

    def test_validator_cli_reports_owned_topology(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_catalog.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            "PASS schema=6 domains=60 domain_skills=308 capabilities=22 source_policies=7 "
            "runtime_contracts=22 operations=23 active_operations=22 bindings=308 top_level_skills=0 "
            "direct=35 adjacent=16 new=8 sensitive=1\n",
            result.stdout,
        )
        self.assertEqual("", result.stderr)


class SchemaV6PrimitiveTest(unittest.TestCase):
    @staticmethod
    def validate_node(schema, value, pointer: str = "") -> list[str]:
        helper = getattr(validate_catalog, "_validate_schema_node", None)
        if helper is None:
            return ['V6_TEST_HELPER_MISSING ""']
        errors: list[str] = []
        helper(schema, value, pointer, errors)
        return errors

    def test_valid_recursive_schema_accepts_scalar_nullable_object_and_array_values(self) -> None:
        schema = {
            "type": "object",
            "required": ["name", "count", "when", "items"],
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 3},
                "count": {"type": ["integer", "null"], "minimum": 0, "maximum": 2},
                "when": {"type": "string", "format": "date-time"},
                "items": {
                    "type": "array",
                    "items": {"type": "number", "minimum": -1.5, "maximum": 2},
                    "minItems": 1,
                    "maxItems": 2,
                },
            },
            "additionalProperties": False,
        }
        value = {
            "name": "한글",
            "count": None,
            "when": "2026-09-05T18:30:01.25+09:00",
            "items": [-1.5, 2],
        }

        self.assertEqual([], self.validate_node(schema, value))

    def test_schema_definition_errors_are_complete_and_sorted(self) -> None:
        schema = {
            "type": "object",
            "required": ["second", "first", "second", "missing"],
            "properties": {
                "first": {"type": "string", "minItems": 1, "pattern": "secret"},
                "second": {"type": ["string", "integer"]},
            },
            "additionalProperties": True,
        }

        self.assertEqual(
            [
                'V6_INVALID_SCHEMA_DEFINITION "/additionalProperties"',
                'V6_INVALID_SCHEMA_DEFINITION "/properties/first/minItems"',
                'V6_UNSUPPORTED_SCHEMA_KEYWORD "/properties/first/pattern"',
                'V6_INVALID_SCHEMA_DEFINITION "/properties/second/type"',
                'V6_INVALID_SCHEMA_DEFINITION "/required"',
            ],
            self.validate_node(schema, {}),
        )

    def test_every_node_requires_a_type_and_closed_object_or_array_shape(self) -> None:
        cases = (
            ({"enum": [1]}, 'V6_INVALID_SCHEMA_DEFINITION "/type"'),
            (
                {"type": "object", "required": [], "properties": {}},
                'V6_INVALID_SCHEMA_DEFINITION "/additionalProperties"',
            ),
            (
                {"type": "array", "minItems": 0},
                'V6_INVALID_SCHEMA_DEFINITION "/items"',
            ),
        )
        for schema, expected in cases:
            with self.subTest(schema=schema):
                self.assertEqual([expected], self.validate_node(schema, None))

    def test_enum_const_and_bounds_are_type_sensitive_and_finite(self) -> None:
        valid_number_enum = {"type": "number", "enum": [1, 1.0]}
        self.assertEqual([], self.validate_node(valid_number_enum, 1.0))
        cases = (
            (
                {"type": "integer", "enum": [1, 1]},
                1,
                ['V6_INVALID_SCHEMA_DEFINITION "/enum/1"'],
            ),
            (
                {"type": "integer", "const": 1, "enum": [1]},
                1,
                ['V6_INVALID_SCHEMA_DEFINITION ""'],
            ),
            (
                {"type": "number", "minimum": 2, "maximum": 1},
                1,
                ['V6_INVALID_SCHEMA_DEFINITION "/maximum"'],
            ),
            (
                {"type": "array", "items": {"type": "null"}, "minItems": True},
                [],
                ['V6_INVALID_SCHEMA_DEFINITION "/minItems"'],
            ),
            (
                {"type": "number", "minimum": float("inf")},
                1,
                ['V6_INVALID_SCHEMA_DEFINITION "/minimum"'],
            ),
            (
                {"type": "integer"},
                True,
                ['V6_INVALID_TYPE ""'],
            ),
            (
                {"type": "number"},
                float("nan"),
                ['V6_INVALID_TYPE ""'],
            ),
            (
                {"type": "string", "minLength": 2, "maxLength": 1},
                "x",
                ['V6_INVALID_SCHEMA_DEFINITION "/maxLength"'],
            ),
        )
        for schema, value, expected in cases:
            with self.subTest(schema=schema, value=value):
                self.assertEqual(expected, self.validate_node(schema, value))

    def test_value_errors_use_escaped_rfc6901_pointers_and_stable_order(self) -> None:
        schema = {
            "type": "object",
            "required": ["missing", "a/b", "til~de"],
            "properties": {
                "missing": {"type": "boolean"},
                "a/b": {"type": "integer"},
                "til~de": {"type": "array", "items": {"type": "null"}, "maxItems": 1},
            },
            "additionalProperties": False,
        }
        value = {"z": 1, "a/b": False, "til~de": [None, None], "a": 2}

        self.assertEqual(
            [
                'V6_UNKNOWN_FIELD "/a"',
                'V6_INVALID_TYPE "/a~1b"',
                'V6_REQUIRED_FIELD "/missing"',
                'V6_INVALID_VALUE "/til~0de"',
                'V6_UNKNOWN_FIELD "/z"',
            ],
            self.validate_node(schema, value),
        )

    def test_enum_const_and_inclusive_value_bounds_are_enforced(self) -> None:
        cases = (
            ({"type": "string", "enum": ["a", "b"]}, "c"),
            ({"type": "number", "const": 1}, 1.0),
            ({"type": "number", "minimum": 1, "maximum": 2}, 0.5),
            ({"type": "string", "minLength": 2, "maxLength": 3}, "a"),
            ({"type": "array", "items": {"type": "boolean"}, "minItems": 1}, []),
        )
        for schema, value in cases:
            with self.subTest(schema=schema, value=value):
                self.assertEqual(['V6_INVALID_VALUE ""'], self.validate_node(schema, value))
        self.assertEqual([], self.validate_node({"type": "number", "minimum": 1, "maximum": 2}, 2))

    def test_exact_formats_accept_only_contract_values(self) -> None:
        accepted = {
            "date": "2024-02-29",
            "date-time": "2026-09-05T09:08:07Z",
            "https-url": "https://example.go.kr/path?q=allowed",
            "sha256": "0123456789abcdef" * 4,
        }
        rejected = {
            "date": ("2023-02-29", "2026-9-05", "2026-09-05T00:00:00Z"),
            "date-time": (
                "2026-09-05 09:08:07Z",
                "2026-09-05T09:08:07",
                "2026-09-05T09:08:60Z",
                "2026-09-05T09:08:07+24:00",
            ),
            "https-url": (
                "HTTPS://example.go.kr/",
                "https://Example.go.kr/",
                "https://user@example.go.kr/",
                "https://example.go.kr#",
                "https://example.go.kr/#fragment",
                "https://example.go.kr.:443/",
                "https://127.0.0.1/",
                "https://example.go.kr:444/",
                "https://exam\tple.go.kr/",
                "https://exam\nple.go.kr/",
                "https://exam\rple.go.kr/",
            ),
            "sha256": ("A" * 64, "a" * 63),
        }
        for format_name, value in accepted.items():
            with self.subTest(format=format_name, value=value):
                self.assertEqual([], self.validate_node({"type": "string", "format": format_name}, value))
        for format_name, values in rejected.items():
            for value in values:
                with self.subTest(format=format_name, value=value):
                    self.assertEqual(
                        ['V6_INVALID_FORMAT ""'],
                        self.validate_node({"type": "string", "format": format_name}, value),
                    )

    def test_https_url_rejects_every_ascii_control_character(self) -> None:
        for codepoint in (*range(0x20), 0x7F):
            with self.subTest(codepoint=codepoint):
                value = f"https://example.go.kr/safe{chr(codepoint)}suffix"
                self.assertEqual(
                    ['V6_INVALID_FORMAT ""'],
                    self.validate_node({"type": "string", "format": "https-url"}, value),
                )

    def test_https_url_rejects_whitespace_malformed_escapes_and_surrogates(self) -> None:
        unsafe_values = (
            *(f"https://example.go.kr/safe{character}suffix" for character in (
                " ", "\u00a0", "\u1680", "\u2000", "\u2028", "\u2029", "\u202f", "\u205f", "\u3000",
            )),
            *(f"https://example.go.kr/bad{escape}" for escape in ("%", "%0", "%zz", "%0z", "%z0")),
            "https://example.go.kr/bad\ud800",
            "https://example.go.kr/bad\udfff",
        )
        for index, value in enumerate(unsafe_values):
            with self.subTest(index=index):
                errors = self.validate_node({"type": "string", "format": "https-url"}, value)
                self.assertEqual(['V6_INVALID_FORMAT ""'], errors)
                self.assertEqual(
                    b'["V6_INVALID_FORMAT \\\"\\\""]',
                    json.dumps(errors).encode("utf-8"),
                )

    def test_error_array_is_hash_seed_independent(self) -> None:
        driver = """
import json
from scripts import validate_catalog
schema = {
    "type": "object",
    "required": [],
    "properties": {key: {"type": "integer"} for key in {"z", "a/b", "til~de"}},
    "additionalProperties": False,
}
errors = []
helper = getattr(validate_catalog, "_validate_schema_node", None)
if helper is None:
    errors = ['V6_TEST_HELPER_MISSING ""']
else:
    helper(schema, {key: False for key in {"z", "a/b", "til~de"}}, "", errors)
print(json.dumps(errors))
"""
        outputs = []
        for seed in ("1", "2"):
            environment = dict(os.environ)
            environment["PYTHONHASHSEED"] = seed
            result = subprocess.run(
                [sys.executable, "-c", driver],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            outputs.append(json.loads(result.stdout))
        expected = [
            'V6_INVALID_TYPE "/a~1b"',
            'V6_INVALID_TYPE "/til~0de"',
            'V6_INVALID_TYPE "/z"',
        ]
        self.assertEqual([expected, expected], outputs)


class StrictCatalogJsonLoaderTest(unittest.TestCase):
    @staticmethod
    def copy_strict_cli_candidate(
        repo: Path,
        relative_paths: tuple[str, ...] = STRICT_CLI_OWNED_PATHS,
    ) -> tuple[str, ...]:
        if relative_paths != STRICT_CLI_OWNED_PATHS:
            raise AssertionError("strict CLI candidate path set changed")
        copied = []
        for relative_path in relative_paths:
            source = ROOT / relative_path
            destination = repo / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(relative_path)
        return tuple(copied)

    @classmethod
    def run_copied_repo_cli(
        cls,
        raw: bytes,
    ) -> tuple[subprocess.CompletedProcess[bytes], Path, tuple[str, ...]]:
        temp = tempfile.TemporaryDirectory()
        temp_root = Path(temp.name)
        repo = temp_root / "repo"
        copied_paths = cls.copy_strict_cli_candidate(repo)
        (repo / "catalog/domain-skills.json").write_bytes(raw)
        result = subprocess.run(
            ["python3", "scripts/validate_catalog.py"],
            cwd=repo,
            check=False,
            capture_output=True,
        )
        temp.cleanup()
        return result, temp_root, copied_paths

    def assert_cli_rejection(self, raw: bytes, expected_code: str) -> None:
        result, temp_root, copied_paths = self.run_copied_repo_cli(raw)
        self.assertEqual(STRICT_CLI_OWNED_PATHS, copied_paths)
        self.assertEqual(1, result.returncode)
        self.assertEqual(f'ERROR {expected_code} ""\n'.encode(), result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertNotIn(b"Traceback", result.stdout + result.stderr)
        self.assertFalse(temp_root.exists())

    @staticmethod
    def load(raw: bytes):
        helper = getattr(validate_catalog, "_load_json_strict", None)
        if helper is None:
            return "V6_TEST_HELPER_MISSING"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "catalog.json"
            path.write_bytes(raw)
            try:
                return helper(path)
            except validate_catalog.StrictJsonError as error:
                return error.code

    def test_valid_json_is_loaded(self) -> None:
        self.assertEqual({"schema_version": 5}, self.load(b'{"schema_version":5}'))

    def test_strict_cli_copy_contract_rejects_omission_and_extra_product_path(self) -> None:
        cases = (
            (
                ("catalog/domain-skills.json", "scripts/validate_catalog.py"),
                "tests/test_catalog.py",
            ),
            (
                (*STRICT_CLI_OWNED_PATHS, "scripts/render_catalog.py"),
                "scripts/render_catalog.py",
            ),
        )
        for relative_paths, forbidden_path in cases:
            with self.subTest(relative_paths=relative_paths):
                with tempfile.TemporaryDirectory() as temp:
                    repo = Path(temp) / "repo"
                    with self.assertRaisesRegex(
                        AssertionError,
                        "strict CLI candidate path set changed",
                    ):
                        self.copy_strict_cli_candidate(repo, relative_paths)
                    self.assertFalse((repo / forbidden_path).exists())

        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            copied_paths = self.copy_strict_cli_candidate(repo)
            actual_files = tuple(
                path.relative_to(repo).as_posix()
                for path in sorted(repo.rglob("*"))
                if path.is_file()
            )
            self.assertEqual(STRICT_CLI_OWNED_PATHS, copied_paths)
            self.assertEqual(
                (
                    "catalog/domain-skills.json",
                    "scripts/validate_catalog.py",
                    "tests/test_catalog.py",
                ),
                actual_files,
            )

    def test_malformed_utf8_and_json_are_invalid_json(self) -> None:
        for raw in (b'\xff', b'{"schema_version":'):
            with self.subTest(raw=raw):
                self.assertEqual("V6_INVALID_JSON", self.load(raw))

    def test_nested_duplicate_key_is_rejected(self) -> None:
        self.assertEqual("V6_DUPLICATE_JSON_KEY", self.load(b'{"outer":{"same":1,"same":2}}'))

    def test_nonfinite_constants_are_rejected(self) -> None:
        for constant in (b"NaN", b"Infinity", b"-Infinity"):
            with self.subTest(constant=constant):
                self.assertEqual("V6_NON_FINITE_NUMBER", self.load(b'{"value":' + constant + b"}"))

    def test_cli_rejects_malformed_utf8_and_json_without_traceback(self) -> None:
        for raw in (b"\xff", b'{"schema_version":'):
            with self.subTest(raw=raw):
                self.assert_cli_rejection(raw, "V6_INVALID_JSON")

    def test_cli_rejects_nested_duplicate_key_without_traceback(self) -> None:
        self.assert_cli_rejection(
            b'{"outer":{"same":1,"same":2}}',
            "V6_DUPLICATE_JSON_KEY",
        )

    def test_cli_rejects_each_nonfinite_constant_without_traceback(self) -> None:
        for constant in (b"NaN", b"Infinity", b"-Infinity"):
            with self.subTest(constant=constant):
                self.assert_cli_rejection(
                    b'{"value":' + constant + b"}",
                    "V6_NON_FINITE_NUMBER",
                )

    def test_cli_rejects_overflowed_finite_number_without_traceback(self) -> None:
        self.assert_cli_rejection(b"1e9999", "V6_NON_FINITE_NUMBER")

    def test_cli_reports_escaped_lone_surrogate_member_without_traceback(self) -> None:
        raw = (ROOT / "catalog/domain-skills.json").read_bytes()
        raw = raw.replace(b"{", b'{"alien\\ud800":null,', 1)

        result, temp_root, copied_paths = self.run_copied_repo_cli(raw)

        self.assertEqual(STRICT_CLI_OWNED_PATHS, copied_paths)
        self.assertEqual(1, result.returncode)
        self.assertEqual(b'ERROR V6_UNKNOWN_FIELD "/alien\\ud800"\n', result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertNotIn(b"Traceback", result.stdout + result.stderr)
        self.assertFalse(temp_root.exists())


class SourcePolicyV6Test(unittest.TestCase):
    ON_DATE = date(2026, 9, 5)

    @staticmethod
    def candidate():
        policy_specs = (
            (
                "law-go-kr-drf-api",
                "국가법령정보센터",
                "api",
                "https://www.law.go.kr",
                (("exact", "/DRF/lawSearch.do"), ("exact", "/DRF/lawService.do")),
            ),
            (
                "kosis-statistics-api",
                "KOSIS",
                "api",
                "https://kosis.kr",
                (("exact", "/openapi/Param/statisticsParameterData.do"),),
            ),
            (
                "data-go-kr-order-plan-api",
                "조달청",
                "api",
                "https://apis.data.go.kr",
                (("exact", "/1230000/ao/OrderPlanSttusService"),),
            ),
            (
                "data-go-kr-village-forecast-api",
                "기상청",
                "api",
                "https://apis.data.go.kr",
                (("exact", "/1360000/VilageFcstInfoService_2.0/getVilageFcst"),),
            ),
            ("gov-kr-web", "정부24", "web", "https://www.gov.kr", (("prefix", "/"),)),
            ("kipris-web", "KIPRIS", "web", "https://www.kipris.or.kr", (("prefix", "/"),)),
            ("kipo-web", "지식재산처", "web", "https://www.kipo.go.kr", (("prefix", "/"),)),
        )
        policies = [
            {
                "id": policy_id,
                "revision": 2 if policy_id == "kipo-web" else 1,
                "enabled": False,
                "institution": institution,
                "channel": channel,
                "scope": {
                    "origins": [origin],
                    "path_rules": [
                        {"match": match_type, "path": path}
                        for match_type, path in path_rules
                    ],
                    "methods": ["GET"],
                },
                "robots": {"status": "unreviewed"},
                "terms": {"status": "unreviewed"},
                "rate_limit": {"status": "unreviewed"},
                "response": {"status": "unreviewed"},
                "license": {"status": "unreviewed"},
                "retention": {"raw_content": "none", "receipts": "metadata-only"},
            }
            for policy_id, institution, channel, origin, path_rules in policy_specs
        ]
        capability_map = (
            ("public-document-hwpx", ()),
            ("korean-law-bill-research", ("law-go-kr-drf-api",)),
            ("kosis-official-statistics", ("kosis-statistics-api",)),
            ("public-procurement-research", ("data-go-kr-order-plan-api",)),
            ("disaster-geospatial-brief", ("data-go-kr-village-forecast-api",)),
            ("welfare-health-safety-research", ()),
            ("land-housing-geospatial-research", ()),
            ("official-source-research", ("gov-kr-web",)),
            ("civil-complaint-triage-draft", ()),
            ("administrative-document-draft-review", ()),
            ("public-policy-evidence-pack", ()),
            ("korean-legal-citation-verification", ("law-go-kr-drf-api",)),
            ("public-ai-governance-review", ()),
            ("public-it-project-procedure-review", ()),
            ("public-record-disclosure-redaction-review", ()),
            ("local-ordinance-draft-review", ()),
            ("construction-standard-bim-compliance-precheck", ()),
            ("building-permit-document-precheck", ()),
            ("official-notice-multilingual-translation-review", ()),
            ("patent-prior-art-evidence-pack", ("kipris-web", "kipo-web")),
            ("public-records-lifecycle-review", ()),
            ("regulated-trade-procedure-precheck", ()),
        )
        capabilities = [
            {
                "slug": slug,
                "source_policy_ids": list(policy_ids),
                "source_provenance": ["https://www.law.go.kr/"],
            }
            for slug, policy_ids in capability_map
        ]
        return {"source_policies": policies, "shared_capabilities": capabilities}

    @staticmethod
    def validate_policies(candidate, *, on_date: date = ON_DATE) -> list[str]:
        helper = getattr(validate_catalog, "_validate_source_policies", None)
        if helper is None:
            return ['V6_TEST_HELPER_MISSING ""']
        errors: list[str] = []
        helper(candidate, on_date=on_date, errors=errors)
        return errors

    @staticmethod
    def match_path(path_rules, request_path: str):
        helper = getattr(validate_catalog, "_match_source_policy_path", None)
        if helper is None:
            return "V6_TEST_HELPER_MISSING"
        return helper(path_rules, request_path)

    def test_exact_seven_policy_registry_and_capability_map_are_valid(self) -> None:
        candidate = self.candidate()
        expected_policies = (
            ("law-go-kr-drf-api", "국가법령정보센터", "api", "https://www.law.go.kr", (("exact", "/DRF/lawSearch.do"), ("exact", "/DRF/lawService.do"))),
            ("kosis-statistics-api", "KOSIS", "api", "https://kosis.kr", (("exact", "/openapi/Param/statisticsParameterData.do"),)),
            ("data-go-kr-order-plan-api", "조달청", "api", "https://apis.data.go.kr", (("exact", "/1230000/ao/OrderPlanSttusService"),)),
            ("data-go-kr-village-forecast-api", "기상청", "api", "https://apis.data.go.kr", (("exact", "/1360000/VilageFcstInfoService_2.0/getVilageFcst"),)),
            ("gov-kr-web", "정부24", "web", "https://www.gov.kr", (("prefix", "/"),)),
            ("kipris-web", "KIPRIS", "web", "https://www.kipris.or.kr", (("prefix", "/"),)),
            ("kipo-web", "지식재산처", "web", "https://www.kipo.go.kr", (("prefix", "/"),)),
        )
        actual_policies = tuple(
            (
                policy["id"],
                policy["institution"],
                policy["channel"],
                policy["scope"]["origins"][0],
                tuple((rule["match"], rule["path"]) for rule in policy["scope"]["path_rules"]),
            )
            for policy in candidate["source_policies"]
        )
        expected_map = {
            "korean-law-bill-research": ["law-go-kr-drf-api"],
            "kosis-official-statistics": ["kosis-statistics-api"],
            "public-procurement-research": ["data-go-kr-order-plan-api"],
            "disaster-geospatial-brief": ["data-go-kr-village-forecast-api"],
            "official-source-research": ["gov-kr-web"],
            "korean-legal-citation-verification": ["law-go-kr-drf-api"],
            "patent-prior-art-evidence-pack": ["kipris-web", "kipo-web"],
        }
        actual_map = {
            capability["slug"]: capability["source_policy_ids"]
            for capability in candidate["shared_capabilities"]
            if capability["source_policy_ids"]
        }

        self.assertEqual(expected_policies, actual_policies)
        self.assertEqual(expected_map, actual_map)
        self.assertEqual([], self.validate_policies(candidate))

    def test_duplicate_id_and_registry_order_fail_deterministically(self) -> None:
        duplicate = self.candidate()
        original_id = duplicate["source_policies"][1]["id"]
        duplicate["source_policies"][1]["id"] = "law-go-kr-drf-api"
        self.assertNotEqual(original_id, duplicate["source_policies"][1]["id"])
        self.assertEqual(
            ['V6_DUPLICATE_ID "/source_policies/1/id"'],
            self.validate_policies(duplicate),
        )

        reordered = self.candidate()
        original_order = tuple(policy["id"] for policy in reordered["source_policies"])
        reordered["source_policies"][0], reordered["source_policies"][1] = (
            reordered["source_policies"][1],
            reordered["source_policies"][0],
        )
        self.assertNotEqual(
            original_order,
            tuple(policy["id"] for policy in reordered["source_policies"]),
        )
        self.assertEqual(
            [
                'V6_INVALID_VALUE "/source_policies/0/id"',
                'V6_INVALID_VALUE "/source_policies/1/id"',
            ],
            self.validate_policies(reordered),
        )

    def test_capability_references_are_unique_known_ordered_and_not_inferred(self) -> None:
        unknown = self.candidate()
        original_refs = copy.deepcopy(unknown["shared_capabilities"][0]["source_policy_ids"])
        unknown["shared_capabilities"][0]["source_policy_ids"] = ["unknown-policy"]
        self.assertNotEqual(original_refs, unknown["shared_capabilities"][0]["source_policy_ids"])
        self.assertEqual(
            ['V6_UNKNOWN_REFERENCE "/shared_capabilities/0/source_policy_ids/0"'],
            self.validate_policies(unknown),
        )

        duplicate = self.candidate()
        original_refs = copy.deepcopy(duplicate["shared_capabilities"][1]["source_policy_ids"])
        duplicate["shared_capabilities"][1]["source_policy_ids"].append("law-go-kr-drf-api")
        self.assertNotEqual(original_refs, duplicate["shared_capabilities"][1]["source_policy_ids"])
        self.assertEqual(
            ['V6_DUPLICATE_VALUE "/shared_capabilities/1/source_policy_ids/1"'],
            self.validate_policies(duplicate),
        )

        wrong_order = self.candidate()
        original_refs = copy.deepcopy(wrong_order["shared_capabilities"][19]["source_policy_ids"])
        wrong_order["shared_capabilities"][19]["source_policy_ids"].reverse()
        self.assertNotEqual(original_refs, wrong_order["shared_capabilities"][19]["source_policy_ids"])
        self.assertEqual(
            ['V6_INVALID_VALUE "/shared_capabilities/19/source_policy_ids"'],
            self.validate_policies(wrong_order),
        )

        provenance_only = self.candidate()
        original_provenance = copy.deepcopy(
            provenance_only["shared_capabilities"][10]["source_provenance"]
        )
        provenance_only["shared_capabilities"][10]["source_provenance"] = [
            "https://www.law.go.kr/",
            "https://www.gov.kr/",
        ]
        self.assertNotEqual(
            original_provenance,
            provenance_only["shared_capabilities"][10]["source_provenance"],
        )
        self.assertEqual([], self.validate_policies(provenance_only))

    def test_enabled_policy_requires_every_reviewed_prerequisite(self) -> None:
        candidate = self.candidate()
        original_enabled = candidate["source_policies"][0]["enabled"]
        candidate["source_policies"][0]["enabled"] = True
        self.assertNotEqual(original_enabled, candidate["source_policies"][0]["enabled"])

        self.assertEqual(
            ['V6_POLICY_NOT_ENABLEABLE "/source_policies/0/enabled"'],
            self.validate_policies(candidate),
        )

    def test_review_freshness_includes_expiry_day_and_stales_after_it(self) -> None:
        fresh = self.candidate()
        original_policy = copy.deepcopy(fresh["source_policies"][0])
        fresh["source_policies"][0]["review"] = {
            "reviewed_on": "2026-09-01",
            "expires_on": "2026-09-05",
            "evidence_urls": ["https://www.law.go.kr/review?q=internal"],
        }
        self.assertNotEqual(original_policy, fresh["source_policies"][0])
        self.assertEqual([], self.validate_policies(fresh, on_date=date(2026, 9, 5)))

        stale = copy.deepcopy(fresh)
        fresh_on_date = date(2026, 9, 5)
        stale_on_date = date(2026, 9, 6)
        self.assertNotEqual(fresh_on_date, stale_on_date)
        self.assertEqual(
            ['V6_POLICY_STALE "/source_policies/0/review/expires_on"'],
            self.validate_policies(stale, on_date=stale_on_date),
        )

        future = copy.deepcopy(fresh)
        original_reviewed_on = future["source_policies"][0]["review"]["reviewed_on"]
        future["source_policies"][0]["review"]["reviewed_on"] = "2026-09-06"
        self.assertNotEqual(
            original_reviewed_on,
            future["source_policies"][0]["review"]["reviewed_on"],
        )
        self.assertEqual(
            ['V6_INVALID_VALUE "/source_policies/0/review/reviewed_on"'],
            self.validate_policies(future, on_date=date(2026, 9, 5)),
        )

    def test_all_reviewed_variants_can_enable_a_fresh_policy(self) -> None:
        candidate = self.candidate()
        policy = candidate["source_policies"][0]
        original_policy = copy.deepcopy(policy)
        policy["enabled"] = True
        policy["review"] = {
            "reviewed_on": "2026-09-01",
            "expires_on": "2026-10-01",
            "evidence_urls": ["https://www.law.go.kr/review"],
        }
        policy["robots"] = {"status": "documented-api-exemption", "evidence_url": "https://www.law.go.kr/robots"}
        policy["terms"] = {"status": "allowed", "url": "https://www.law.go.kr/terms"}
        policy["rate_limit"] = {
            "status": "reviewed",
            "requests": 10,
            "per_seconds": 1,
            "burst": 2,
            "max_wait_seconds": 0.5,
        }
        policy["response"] = {
            "status": "reviewed",
            "max_bytes": 1000,
            "media_types": ["application/json"],
        }
        policy["license"] = {
            "status": "reviewed",
            "url": "https://www.law.go.kr/license",
            "allowed_output_modes": ["link-only", "projected-records"],
            "redistribution": "link-only",
        }
        self.assertNotEqual(original_policy, policy)

        self.assertEqual([], self.validate_policies(candidate))

    def test_other_valid_policy_variants_remain_closed(self) -> None:
        variants = (
            ("robots", {"status": "required"}),
            ("terms", {"status": "manual-review", "url": "https://example.org/terms"}),
            ("terms", {"status": "prohibited", "url": "https://example.org/terms"}),
            ("license", {"status": "manual-review", "url": "https://example.org/license"}),
        )
        for key, variant in variants:
            with self.subTest(key=key, status=variant["status"]):
                candidate = self.candidate()
                original_variant = copy.deepcopy(candidate["source_policies"][0][key])
                candidate["source_policies"][0][key] = variant
                self.assertNotEqual(original_variant, candidate["source_policies"][0][key])
                self.assertEqual([], self.validate_policies(candidate))

    def test_every_nested_object_requires_its_variant_fields(self) -> None:
        mutations = (
            (("source_policies", 0, "scope", "path_rules", 0), None, "match", '/source_policies/0/scope/path_rules/0/match'),
            (("source_policies", 0, "review"), {"reviewed_on": "2026-09-01", "expires_on": "2026-10-01", "evidence_urls": ["https://example.org/review"]}, "reviewed_on", '/source_policies/0/review/reviewed_on'),
            (("source_policies", 0, "robots"), {"status": "documented-api-exemption", "evidence_url": "https://example.org/robots"}, "evidence_url", '/source_policies/0/robots/evidence_url'),
            (("source_policies", 0, "terms"), {"status": "allowed", "url": "https://example.org/terms"}, "url", '/source_policies/0/terms/url'),
            (("source_policies", 0, "rate_limit"), {"status": "reviewed", "requests": 1, "per_seconds": 1, "burst": 1, "max_wait_seconds": 0}, "burst", '/source_policies/0/rate_limit/burst'),
            (("source_policies", 0, "response"), {"status": "reviewed", "max_bytes": 1, "media_types": ["application/json"]}, "max_bytes", '/source_policies/0/response/max_bytes'),
            (("source_policies", 0, "license"), {"status": "manual-review", "url": "https://example.org/license"}, "url", '/source_policies/0/license/url'),
            (("source_policies", 0, "retention"), None, "raw_content", '/source_policies/0/retention/raw_content'),
        )
        for location, replacement, field, pointer in mutations:
            with self.subTest(pointer=pointer):
                candidate = self.candidate()
                parent = candidate
                for member in location[:-1]:
                    parent = parent[member]
                if replacement is not None:
                    parent[location[-1]] = copy.deepcopy(replacement)
                node = candidate
                for member in location:
                    node = node[member]
                original_node = copy.deepcopy(node)
                del node[field]
                self.assertNotEqual(original_node, node)
                self.assertEqual(
                    [f'V6_REQUIRED_FIELD "{pointer}"'],
                    self.validate_policies(candidate),
                )

    def test_origins_and_paths_reject_noncanonical_values_without_leaking_them(self) -> None:
        origin_cases = (
            "http://www.law.go.kr",
            "https://www.law.go.kr/",
            "https://www.law.go.kr?",
            "https://www.law.go.kr#",
            "https://WWW.law.go.kr",
            "https://127.0.0.1",
            "https://www.law.go.kr:443",
        )
        for origin in origin_cases:
            with self.subTest(origin=origin):
                candidate = self.candidate()
                original_origin = candidate["source_policies"][0]["scope"]["origins"][0]
                candidate["source_policies"][0]["scope"]["origins"][0] = origin
                self.assertNotEqual(original_origin, candidate["source_policies"][0]["scope"]["origins"][0])
                self.assertEqual(
                    ['V6_INVALID_FORMAT "/source_policies/0/scope/origins/0"'],
                    self.validate_policies(candidate),
                )
        path_cases = (
            "relative",
            "/has?query",
            "/has#fragment",
            "/back\\slash",
            "/repeated//slash",
            "/dot/../segment",
            "/encoded%2Fslash",
            "/encoded%5cslash",
            "/encoded%00nul",
            "/exact-trailing/",
        )
        for path in path_cases:
            with self.subTest(path=path):
                candidate = self.candidate()
                original_path = candidate["source_policies"][0]["scope"]["path_rules"][0]["path"]
                candidate["source_policies"][0]["scope"]["path_rules"][0]["path"] = path
                self.assertNotEqual(
                    original_path,
                    candidate["source_policies"][0]["scope"]["path_rules"][0]["path"],
                )
                self.assertEqual(
                    ['V6_INVALID_FORMAT "/source_policies/0/scope/path_rules/0/path"'],
                    self.validate_policies(candidate),
                )

    def test_policy_paths_reject_whitespace_malformed_escapes_and_surrogates(self) -> None:
        path_cases = (
            *(f"/safe{character}suffix" for character in (
                " ", "\u00a0", "\u1680", "\u2000", "\u2028", "\u2029", "\u202f", "\u205f", "\u3000",
            )),
            *(f"/bad{escape}" for escape in ("%", "%0", "%zz", "%0z", "%z0")),
            "/bad\ud800",
            "/bad\udfff",
        )
        for index, path in enumerate(path_cases):
            with self.subTest(index=index):
                candidate = self.candidate()
                original = candidate["source_policies"][0]["scope"]["path_rules"][0]["path"]
                candidate["source_policies"][0]["scope"]["path_rules"][0]["path"] = path
                self.assertNotEqual(original, path)
                errors = self.validate_policies(candidate)
                self.assertEqual(
                    ['V6_INVALID_FORMAT "/source_policies/0/scope/path_rules/0/path"'],
                    errors,
                )
                json.dumps(errors, ensure_ascii=False).encode("utf-8")

    def test_duplicate_and_equal_specificity_path_rules_are_ambiguous(self) -> None:
        duplicate = self.candidate()
        original_rules = copy.deepcopy(duplicate["source_policies"][0]["scope"]["path_rules"])
        duplicate["source_policies"][0]["scope"]["path_rules"].append(
            {"match": "exact", "path": "/DRF/lawSearch.do"}
        )
        self.assertNotEqual(original_rules, duplicate["source_policies"][0]["scope"]["path_rules"])
        self.assertEqual(
            ['V6_DUPLICATE_VALUE "/source_policies/0/scope/path_rules/2"'],
            self.validate_policies(duplicate),
        )

        ambiguous = self.candidate()
        original_rules = copy.deepcopy(ambiguous["source_policies"][0]["scope"]["path_rules"])
        ambiguous["source_policies"][0]["scope"]["path_rules"].append(
            {"match": "prefix", "path": "/DRF/lawSearch.do"}
        )
        self.assertNotEqual(original_rules, ambiguous["source_policies"][0]["scope"]["path_rules"])
        self.assertEqual(
            ['V6_INVALID_VALUE "/source_policies/0/scope/path_rules/2"'],
            self.validate_policies(ambiguous),
        )

    def test_guessed_fields_and_nested_shape_mutations_fail_closed(self) -> None:
        mutations = (
            (("source_policies", 0), "quota", 10, '/source_policies/0/quota'),
            (("source_policies", 0), "review_date", "2026-09-05", '/source_policies/0/review_date'),
            (("source_policies", 0, "license"), "spdx", "UNKNOWN", '/source_policies/0/license/spdx'),
            (("source_policies", 0, "robots"), "note", "secret", '/source_policies/0/robots/note'),
        )
        for location, key, value, pointer in mutations:
            with self.subTest(pointer=pointer):
                candidate = self.candidate()
                node = candidate
                for member in location:
                    node = node[member]
                original_node = copy.deepcopy(node)
                node[key] = value
                self.assertNotEqual(original_node, node)
                self.assertEqual(
                    [f'V6_UNKNOWN_FIELD "{pointer}"'],
                    self.validate_policies(candidate),
                )

        candidate = self.candidate()
        original_candidate = copy.deepcopy(candidate)
        del candidate["source_policies"][0]["scope"]["methods"]
        candidate["source_policies"][0]["retention"]["extra"] = "secret"
        self.assertNotEqual(original_candidate, candidate)
        self.assertEqual(
            [
                'V6_UNKNOWN_FIELD "/source_policies/0/retention/extra"',
                'V6_REQUIRED_FIELD "/source_policies/0/scope/methods"',
            ],
            self.validate_policies(candidate),
        )

    def test_disabled_policies_still_validate_all_nested_variants(self) -> None:
        cases = (
            ("revision", 0, '/source_policies/0/revision'),
            ("institution", "", '/source_policies/0/institution'),
            ("channel", "ftp", '/source_policies/0/channel'),
        )
        for key, value, pointer in cases:
            with self.subTest(key=key):
                candidate = self.candidate()
                original_value = candidate["source_policies"][0][key]
                candidate["source_policies"][0][key] = value
                self.assertNotEqual(original_value, candidate["source_policies"][0][key])
                self.assertEqual(
                    [f'V6_INVALID_VALUE "{pointer}"'],
                    self.validate_policies(candidate),
                )

        candidate = self.candidate()
        original_policy = copy.deepcopy(candidate["source_policies"][0])
        candidate["source_policies"][0]["rate_limit"] = {
            "status": "reviewed",
            "requests": True,
            "per_seconds": 0,
            "burst": 1,
            "max_wait_seconds": -1,
        }
        candidate["source_policies"][0]["response"] = {
            "status": "reviewed",
            "max_bytes": 0,
            "media_types": ["Application/JSON", "Application/JSON"],
        }
        candidate["source_policies"][0]["license"] = {
            "status": "reviewed",
            "url": "http://example.org",
            "allowed_output_modes": ["raw"],
            "redistribution": "unknown",
        }
        self.assertNotEqual(original_policy, candidate["source_policies"][0])
        self.assertEqual(
            [
                'V6_INVALID_VALUE "/source_policies/0/license/allowed_output_modes/0"',
                'V6_INVALID_VALUE "/source_policies/0/license/redistribution"',
                'V6_INVALID_FORMAT "/source_policies/0/license/url"',
                'V6_INVALID_VALUE "/source_policies/0/rate_limit/max_wait_seconds"',
                'V6_INVALID_VALUE "/source_policies/0/rate_limit/per_seconds"',
                'V6_INVALID_VALUE "/source_policies/0/rate_limit/requests"',
                'V6_INVALID_VALUE "/source_policies/0/response/max_bytes"',
                'V6_INVALID_VALUE "/source_policies/0/response/media_types/0"',
                'V6_DUPLICATE_VALUE "/source_policies/0/response/media_types/1"',
                'V6_INVALID_VALUE "/source_policies/0/response/media_types/1"',
            ],
            self.validate_policies(candidate),
        )

    def test_path_matcher_observes_exact_segment_boundary_and_longest_prefix(self) -> None:
        prefix_rules = [
            {"match": "prefix", "path": "/foo"},
            {"match": "prefix", "path": "/foo/bar"},
        ]
        exact_rules = [
            {"match": "prefix", "path": "/"},
            {"match": "exact", "path": "/health"},
        ]

        self.assertEqual(1, self.match_path(prefix_rules, "/foo/bar/baz"))
        self.assertIsNone(self.match_path(prefix_rules, "/foobar"))
        self.assertEqual(1, self.match_path(exact_rules, "/health"))
        self.assertEqual(0, self.match_path(exact_rules, "/other/path"))


class RuntimeContractV6Test(unittest.TestCase):
    CONTRACT_SPECS = (
        ("public-document-hwpx", "local-document", "none", "inspect-document", (), "none"),
        ("korean-law-bill-research", "retrieval", "optional-live", "search-laws", ("law-go-kr-drf-api",), "projected-records"),
        ("kosis-official-statistics", "retrieval", "optional-live", "query-statistics", ("kosis-statistics-api",), "projected-records"),
        ("public-procurement-research", "retrieval", "optional-live", "query-order-plans", ("data-go-kr-order-plan-api",), "projected-records"),
        ("disaster-geospatial-brief", "retrieval", "optional-live", "query-village-forecast", ("data-go-kr-village-forecast-api",), "projected-records"),
        ("welfare-health-safety-research", "retrieval", "blocked", "blocked-dataset-query", (), "none"),
        ("land-housing-geospatial-research", "retrieval", "blocked", "blocked-dataset-query", (), "none"),
        ("official-source-research", "retrieval", "optional-live", "inspect-page", ("gov-kr-web",), "link-only"),
        ("civil-complaint-triage-draft", "admission", "none", "admit-draft", (), "none"),
        ("administrative-document-draft-review", "admission", "none", "review-draft", (), "none"),
        ("public-policy-evidence-pack", "admission", "none", "build-pack", (), "none"),
        ("korean-legal-citation-verification", "verification", "optional-live", "verify-citations", ("law-go-kr-drf-api",), "link-only"),
        ("public-ai-governance-review", "admission", "none", "review-case", (), "none"),
        ("public-it-project-procedure-review", "admission", "none", "review-case", (), "none"),
        ("public-record-disclosure-redaction-review", "admission", "none", "review-case", (), "none"),
        ("local-ordinance-draft-review", "admission", "none", "review-case", (), "none"),
        ("construction-standard-bim-compliance-precheck", "admission", "none", "review-case", (), "none"),
        ("building-permit-document-precheck", "admission", "none", "review-case", (), "none"),
        ("official-notice-multilingual-translation-review", "admission", "none", "review-case", (), "none"),
        ("patent-prior-art-evidence-pack", "hybrid", "mixed", "review-case", (), "none"),
        ("public-records-lifecycle-review", "admission", "none", "review-case", (), "none"),
        ("regulated-trade-procedure-precheck", "admission", "none", "review-case", (), "none"),
    )
    CAPABILITY_POLICIES = (
        ("public-document-hwpx", ()),
        ("korean-law-bill-research", ("law-go-kr-drf-api",)),
        ("kosis-official-statistics", ("kosis-statistics-api",)),
        ("public-procurement-research", ("data-go-kr-order-plan-api",)),
        ("disaster-geospatial-brief", ("data-go-kr-village-forecast-api",)),
        ("welfare-health-safety-research", ()),
        ("land-housing-geospatial-research", ()),
        ("official-source-research", ("gov-kr-web",)),
        ("civil-complaint-triage-draft", ()),
        ("administrative-document-draft-review", ()),
        ("public-policy-evidence-pack", ()),
        ("korean-legal-citation-verification", ("law-go-kr-drf-api",)),
        ("public-ai-governance-review", ()),
        ("public-it-project-procedure-review", ()),
        ("public-record-disclosure-redaction-review", ()),
        ("local-ordinance-draft-review", ()),
        ("construction-standard-bim-compliance-precheck", ()),
        ("building-permit-document-precheck", ()),
        ("official-notice-multilingual-translation-review", ()),
        ("patent-prior-art-evidence-pack", ("kipris-web", "kipo-web")),
        ("public-records-lifecycle-review", ()),
        ("regulated-trade-procedure-precheck", ()),
    )
    EXIT_CODES = {
        "success": 0,
        "review_blocked": 1,
        "input_error": 2,
        "policy_blocked": 3,
        "upstream_error": 4,
    }
    FORBIDDEN_KEYS = ["authorization", "body", "cookie", "credential", "headers", "raw", "text"]

    @classmethod
    def candidate(cls):
        contracts = []
        for capability, kind, network, operation, policies, output_mode in cls.CONTRACT_SPECS:
            operation_id = f"kgov/{capability}/{operation}/v1"
            operations = [
                {
                    "id": operation_id,
                    "schema_status": "declared",
                    "source_policy_ids": list(policies),
                    "source_output_mode": output_mode,
                    "fixture_argv": ["--fixture"],
                }
            ]
            if capability == "patent-prior-art-evidence-pack":
                operations.append(
                    {
                        "id": "kgov/patent-prior-art-evidence-pack/inspect-source/v1",
                        "schema_status": "declared",
                        "source_policy_ids": ["kipris-web", "kipo-web"],
                        "source_output_mode": "link-only",
                    }
                )
            contracts.append(
                {
                    "id": f"kgov/{capability}/v1",
                    "capability_slug": capability,
                    "module": f"kgov_runtime.capabilities.{capability.replace('-', '_')}",
                    "kind": kind,
                    "network_mode": network,
                    "default_operation_id": operation_id,
                    "operations": operations,
                    "exit_codes": copy.deepcopy(cls.EXIT_CODES),
                    "forbidden_output_keys": copy.deepcopy(cls.FORBIDDEN_KEYS),
                }
            )
        capabilities = [
            {
                "slug": capability,
                "source_policy_ids": list(policies),
                "runtime_contract_id": f"kgov/{capability}/v1",
            }
            for capability, policies in cls.CAPABILITY_POLICIES
        ]
        return {"runtime_contracts": contracts, "shared_capabilities": capabilities}

    @staticmethod
    def validate_contracts(candidate) -> list[str]:
        helper = getattr(validate_catalog, "_validate_runtime_contracts", None)
        if helper is None:
            return ['V6_TEST_HELPER_MISSING ""']
        errors: list[str] = []
        helper(candidate, errors=errors)
        return errors

    @staticmethod
    def validate_binding(binding, *, capability_slug: str, contracts_by_id, pointer: str) -> list[str]:
        helper = getattr(validate_catalog, "_validate_runtime_binding", None)
        if helper is None:
            return ['V6_TEST_HELPER_MISSING ""']
        errors: list[str] = []
        helper(
            binding,
            capability_slug=capability_slug,
            contracts_by_id=contracts_by_id,
            pointer=pointer,
            errors=errors,
        )
        return errors

    @classmethod
    def active_candidate(cls):
        candidate = cls.candidate()
        operation = candidate["runtime_contracts"][0]["operations"][0]
        operation["schema_status"] = "active"
        operation["input_schema"] = {
            "type": "object",
            "required": ["query", "options"],
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "options": {
                    "type": "object",
                    "required": ["limit"],
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1},
                        "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }
        operation["output_schema"] = {
            "type": "object",
            "required": ["result"],
            "properties": {
                "result": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {"title": {"type": "string"}},
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
        }
        return candidate

    def test_exact_22_contract_and_23_operation_manifest_is_valid(self) -> None:
        candidate = self.candidate()
        expected_contract_ids = (
            "kgov/public-document-hwpx/v1",
            "kgov/korean-law-bill-research/v1",
            "kgov/kosis-official-statistics/v1",
            "kgov/public-procurement-research/v1",
            "kgov/disaster-geospatial-brief/v1",
            "kgov/welfare-health-safety-research/v1",
            "kgov/land-housing-geospatial-research/v1",
            "kgov/official-source-research/v1",
            "kgov/civil-complaint-triage-draft/v1",
            "kgov/administrative-document-draft-review/v1",
            "kgov/public-policy-evidence-pack/v1",
            "kgov/korean-legal-citation-verification/v1",
            "kgov/public-ai-governance-review/v1",
            "kgov/public-it-project-procedure-review/v1",
            "kgov/public-record-disclosure-redaction-review/v1",
            "kgov/local-ordinance-draft-review/v1",
            "kgov/construction-standard-bim-compliance-precheck/v1",
            "kgov/building-permit-document-precheck/v1",
            "kgov/official-notice-multilingual-translation-review/v1",
            "kgov/patent-prior-art-evidence-pack/v1",
            "kgov/public-records-lifecycle-review/v1",
            "kgov/regulated-trade-procedure-precheck/v1",
        )
        expected_operations = (
            ("kgov/public-document-hwpx/inspect-document/v1", "local-document", "none", (), "none", ("--fixture",)),
            ("kgov/korean-law-bill-research/search-laws/v1", "retrieval", "optional-live", ("law-go-kr-drf-api",), "projected-records", ("--fixture",)),
            ("kgov/kosis-official-statistics/query-statistics/v1", "retrieval", "optional-live", ("kosis-statistics-api",), "projected-records", ("--fixture",)),
            ("kgov/public-procurement-research/query-order-plans/v1", "retrieval", "optional-live", ("data-go-kr-order-plan-api",), "projected-records", ("--fixture",)),
            ("kgov/disaster-geospatial-brief/query-village-forecast/v1", "retrieval", "optional-live", ("data-go-kr-village-forecast-api",), "projected-records", ("--fixture",)),
            ("kgov/welfare-health-safety-research/blocked-dataset-query/v1", "retrieval", "blocked", (), "none", ("--fixture",)),
            ("kgov/land-housing-geospatial-research/blocked-dataset-query/v1", "retrieval", "blocked", (), "none", ("--fixture",)),
            ("kgov/official-source-research/inspect-page/v1", "retrieval", "optional-live", ("gov-kr-web",), "link-only", ("--fixture",)),
            ("kgov/civil-complaint-triage-draft/admit-draft/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/administrative-document-draft-review/review-draft/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/public-policy-evidence-pack/build-pack/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/korean-legal-citation-verification/verify-citations/v1", "verification", "optional-live", ("law-go-kr-drf-api",), "link-only", ("--fixture",)),
            ("kgov/public-ai-governance-review/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/public-it-project-procedure-review/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/public-record-disclosure-redaction-review/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/local-ordinance-draft-review/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/construction-standard-bim-compliance-precheck/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/building-permit-document-precheck/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/official-notice-multilingual-translation-review/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/patent-prior-art-evidence-pack/review-case/v1", "hybrid", "mixed", (), "none", ("--fixture",)),
            ("kgov/patent-prior-art-evidence-pack/inspect-source/v1", "hybrid", "mixed", ("kipris-web", "kipo-web"), "link-only", ()),
            ("kgov/public-records-lifecycle-review/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
            ("kgov/regulated-trade-procedure-precheck/review-case/v1", "admission", "none", (), "none", ("--fixture",)),
        )
        expected_defaults = (
            "kgov/public-document-hwpx/inspect-document/v1",
            "kgov/korean-law-bill-research/search-laws/v1",
            "kgov/kosis-official-statistics/query-statistics/v1",
            "kgov/public-procurement-research/query-order-plans/v1",
            "kgov/disaster-geospatial-brief/query-village-forecast/v1",
            "kgov/welfare-health-safety-research/blocked-dataset-query/v1",
            "kgov/land-housing-geospatial-research/blocked-dataset-query/v1",
            "kgov/official-source-research/inspect-page/v1",
            "kgov/civil-complaint-triage-draft/admit-draft/v1",
            "kgov/administrative-document-draft-review/review-draft/v1",
            "kgov/public-policy-evidence-pack/build-pack/v1",
            "kgov/korean-legal-citation-verification/verify-citations/v1",
            "kgov/public-ai-governance-review/review-case/v1",
            "kgov/public-it-project-procedure-review/review-case/v1",
            "kgov/public-record-disclosure-redaction-review/review-case/v1",
            "kgov/local-ordinance-draft-review/review-case/v1",
            "kgov/construction-standard-bim-compliance-precheck/review-case/v1",
            "kgov/building-permit-document-precheck/review-case/v1",
            "kgov/official-notice-multilingual-translation-review/review-case/v1",
            "kgov/patent-prior-art-evidence-pack/review-case/v1",
            "kgov/public-records-lifecycle-review/review-case/v1",
            "kgov/regulated-trade-procedure-precheck/review-case/v1",
        )
        actual_contract_ids = tuple(contract["id"] for contract in candidate["runtime_contracts"])
        actual_defaults = tuple(contract["default_operation_id"] for contract in candidate["runtime_contracts"])
        actual_operations = tuple(
            (
                operation["id"],
                contract["kind"],
                contract["network_mode"],
                tuple(operation["source_policy_ids"]),
                operation["source_output_mode"],
                tuple(operation.get("fixture_argv", ())),
            )
            for contract in candidate["runtime_contracts"]
            for operation in contract["operations"]
        )

        self.assertEqual(expected_contract_ids, actual_contract_ids)
        self.assertEqual(expected_defaults, actual_defaults)
        self.assertEqual(expected_operations, actual_operations)
        self.assertEqual(
            {"success": 0, "review_blocked": 1, "input_error": 2, "policy_blocked": 3, "upstream_error": 4},
            candidate["runtime_contracts"][0]["exit_codes"],
        )
        self.assertEqual(
            ["authorization", "body", "cookie", "credential", "headers", "raw", "text"],
            candidate["runtime_contracts"][0]["forbidden_output_keys"],
        )
        self.assertEqual(23, sum(len(contract["operations"]) for contract in candidate["runtime_contracts"]))
        self.assertEqual(
            0,
            sum(
                operation["schema_status"] == "active"
                for contract in candidate["runtime_contracts"]
                for operation in contract["operations"]
            ),
        )
        self.assertEqual([], self.validate_contracts(candidate))

    def test_duplicate_contract_and_operation_ids_point_to_second_declaration(self) -> None:
        duplicate_contract = self.candidate()
        original_id = duplicate_contract["runtime_contracts"][1]["id"]
        duplicate_contract["runtime_contracts"][1]["id"] = duplicate_contract["runtime_contracts"][0]["id"]
        self.assertNotEqual(original_id, duplicate_contract["runtime_contracts"][1]["id"])
        self.assertEqual(
            ['V6_DUPLICATE_ID "/runtime_contracts/1/id"'],
            self.validate_contracts(duplicate_contract),
        )

        duplicate_operation = self.candidate()
        original_id = duplicate_operation["runtime_contracts"][19]["operations"][1]["id"]
        duplicate_operation["runtime_contracts"][19]["operations"][1]["id"] = duplicate_operation["runtime_contracts"][19]["operations"][0]["id"]
        self.assertNotEqual(original_id, duplicate_operation["runtime_contracts"][19]["operations"][1]["id"])
        self.assertEqual(
            ['V6_DUPLICATE_ID "/runtime_contracts/19/operations/1/id"'],
            self.validate_contracts(duplicate_operation),
        )

    def test_contract_derivations_order_defaults_and_links_are_enforced(self) -> None:
        mutations = (
            (0, "module", "kgov_runtime.capabilities.wrong", '/runtime_contracts/0/module'),
            (0, "default_operation_id", "kgov/public-document-hwpx/wrong/v1", '/runtime_contracts/0/default_operation_id'),
        )
        for index, key, value, pointer in mutations:
            with self.subTest(key=key):
                candidate = self.candidate()
                original = candidate["runtime_contracts"][index][key]
                candidate["runtime_contracts"][index][key] = value
                self.assertNotEqual(original, candidate["runtime_contracts"][index][key])
                self.assertEqual(
                    [f'V6_CONTRACT_INVARIANT "{pointer}"'],
                    self.validate_contracts(candidate),
                )

        reordered = self.candidate()
        original_order = tuple(contract["capability_slug"] for contract in reordered["runtime_contracts"])
        reordered["runtime_contracts"][0], reordered["runtime_contracts"][1] = reordered["runtime_contracts"][1], reordered["runtime_contracts"][0]
        self.assertNotEqual(original_order, tuple(contract["capability_slug"] for contract in reordered["runtime_contracts"]))
        self.assertEqual(
            [
                'V6_CONTRACT_INVARIANT "/runtime_contracts/0/capability_slug"',
                'V6_CONTRACT_INVARIANT "/runtime_contracts/1/capability_slug"',
            ],
            self.validate_contracts(reordered),
        )

        wrong_link = self.candidate()
        original_link = wrong_link["shared_capabilities"][0]["runtime_contract_id"]
        wrong_link["shared_capabilities"][0]["runtime_contract_id"] = "kgov/korean-law-bill-research/v1"
        self.assertNotEqual(original_link, wrong_link["shared_capabilities"][0]["runtime_contract_id"])
        self.assertEqual(
            ['V6_CONTRACT_INVARIANT "/shared_capabilities/0/runtime_contract_id"'],
            self.validate_contracts(wrong_link),
        )

    def test_policy_union_order_and_network_invariants_fail_closed(self) -> None:
        wrong_union = self.candidate()
        original = copy.deepcopy(wrong_union["runtime_contracts"][1]["operations"][0]["source_policy_ids"])
        wrong_union["runtime_contracts"][1]["operations"][0]["source_policy_ids"] = []
        self.assertNotEqual(original, wrong_union["runtime_contracts"][1]["operations"][0]["source_policy_ids"])
        self.assertEqual(
            [
                'V6_CONTRACT_INVARIANT "/runtime_contracts/1/network_mode"',
                'V6_CONTRACT_INVARIANT "/runtime_contracts/1/operations"',
            ],
            self.validate_contracts(wrong_union),
        )

        wrong_network = self.candidate()
        original = wrong_network["runtime_contracts"][0]["network_mode"]
        wrong_network["runtime_contracts"][0]["network_mode"] = "optional-live"
        self.assertNotEqual(original, wrong_network["runtime_contracts"][0]["network_mode"])
        self.assertEqual(
            ['V6_CONTRACT_INVARIANT "/runtime_contracts/0/network_mode"'],
            self.validate_contracts(wrong_network),
        )

        wrong_order = self.candidate()
        refs = wrong_order["runtime_contracts"][19]["operations"][1]["source_policy_ids"]
        original = copy.deepcopy(refs)
        refs.reverse()
        self.assertNotEqual(original, refs)
        self.assertEqual(
            [
                'V6_CONTRACT_INVARIANT "/runtime_contracts/19/operations"',
                'V6_INVALID_VALUE "/runtime_contracts/19/operations/1/source_policy_ids"',
            ],
            self.validate_contracts(wrong_order),
        )

        unlisted = self.candidate()
        original = copy.deepcopy(unlisted["runtime_contracts"][0]["operations"][0]["source_policy_ids"])
        unlisted["runtime_contracts"][0]["operations"][0]["source_policy_ids"] = ["law-go-kr-drf-api"]
        self.assertNotEqual(original, unlisted["runtime_contracts"][0]["operations"][0]["source_policy_ids"])
        self.assertEqual(
            [
                'V6_CONTRACT_INVARIANT "/runtime_contracts/0/network_mode"',
                'V6_CONTRACT_INVARIANT "/runtime_contracts/0/operations"',
                'V6_UNKNOWN_REFERENCE "/runtime_contracts/0/operations/0/source_policy_ids/0"',
            ],
            self.validate_contracts(unlisted),
        )

    def test_network_status_policy_output_cross_product_fails_closed(self) -> None:
        network_error = 'V6_CONTRACT_INVARIANT "/runtime_contracts/0/network_mode"'
        output_error = (
            'V6_CONTRACT_INVARIANT '
            '"/runtime_contracts/0/operations/0/source_output_mode"'
        )
        policy_error = (
            'V6_CONTRACT_INVARIANT '
            '"/runtime_contracts/0/operations/0/source_policy_ids"'
        )
        matrix = (
            ("none", "declared", False, "none", ()),
            ("none", "declared", False, "link-only", (output_error,)),
            ("none", "declared", False, "projected-records", (output_error,)),
            ("none", "declared", True, "none", (network_error,)),
            ("none", "declared", True, "link-only", (network_error, output_error)),
            ("none", "declared", True, "projected-records", (network_error, output_error)),
            ("none", "active", False, "none", ()),
            ("none", "active", False, "link-only", (output_error, policy_error)),
            ("none", "active", False, "projected-records", (output_error, policy_error)),
            ("none", "active", True, "none", (network_error,)),
            ("none", "active", True, "link-only", (network_error, output_error)),
            ("none", "active", True, "projected-records", (network_error, output_error)),
            ("blocked", "declared", False, "none", ()),
            ("blocked", "declared", False, "link-only", ()),
            ("blocked", "declared", False, "projected-records", ()),
            ("blocked", "declared", True, "none", (network_error,)),
            ("blocked", "declared", True, "link-only", (network_error,)),
            ("blocked", "declared", True, "projected-records", (network_error,)),
            ("blocked", "active", False, "none", ()),
            ("blocked", "active", False, "link-only", (policy_error,)),
            ("blocked", "active", False, "projected-records", (policy_error,)),
            ("blocked", "active", True, "none", (network_error,)),
            ("blocked", "active", True, "link-only", (network_error,)),
            ("blocked", "active", True, "projected-records", (network_error,)),
            ("optional-live", "declared", False, "none", ()),
            ("optional-live", "declared", False, "link-only", ()),
            ("optional-live", "declared", False, "projected-records", ()),
            ("optional-live", "declared", True, "none", ()),
            ("optional-live", "declared", True, "link-only", ()),
            ("optional-live", "declared", True, "projected-records", ()),
            ("optional-live", "active", False, "none", ()),
            ("optional-live", "active", False, "link-only", (policy_error,)),
            ("optional-live", "active", False, "projected-records", (policy_error,)),
            ("optional-live", "active", True, "none", ()),
            ("optional-live", "active", True, "link-only", ()),
            ("optional-live", "active", True, "projected-records", ()),
            ("mixed", "declared", False, "none", ()),
            ("mixed", "declared", False, "link-only", ()),
            ("mixed", "declared", False, "projected-records", ()),
            ("mixed", "declared", True, "none", ()),
            ("mixed", "declared", True, "link-only", ()),
            ("mixed", "declared", True, "projected-records", ()),
            ("mixed", "active", False, "none", ()),
            ("mixed", "active", False, "link-only", (policy_error,)),
            ("mixed", "active", False, "projected-records", (policy_error,)),
            ("mixed", "active", True, "none", ()),
            ("mixed", "active", True, "link-only", ()),
            ("mixed", "active", True, "projected-records", ()),
        )
        object_schema = {
            "type": "object",
            "required": [],
            "properties": {},
            "additionalProperties": False,
        }
        helper = getattr(validate_catalog, "_validate_contract_semantics", None)
        self.assertIsNotNone(helper)

        for network, status, has_policy, output_mode, expected in matrix:
            with self.subTest(
                network=network,
                status=status,
                has_policy=has_policy,
                output_mode=output_mode,
            ):
                operation = {
                    "id": "kgov/matrix-capability/default/v1",
                    "schema_status": "declared",
                    "source_policy_ids": [],
                    "source_output_mode": "none",
                    "fixture_argv": ["--fixture"],
                }
                before = (
                    "none",
                    operation["schema_status"],
                    bool(operation["source_policy_ids"]),
                    operation["source_output_mode"],
                )
                operation["schema_status"] = status
                operation["source_policy_ids"] = ["law-go-kr-drf-api"] if has_policy else []
                operation["source_output_mode"] = output_mode
                if status == "active":
                    operation["input_schema"] = copy.deepcopy(object_schema)
                    operation["output_schema"] = copy.deepcopy(object_schema)
                operations = [operation]
                if network == "optional-live" and not has_policy:
                    operations.append(
                        {
                            "id": "kgov/matrix-capability/linked/v1",
                            "schema_status": "declared",
                            "source_policy_ids": ["law-go-kr-drf-api"],
                            "source_output_mode": "link-only",
                        }
                    )
                if network == "mixed":
                    operations.append(
                        {
                            "id": "kgov/matrix-capability/adjacent/v1",
                            "schema_status": "declared",
                            "source_policy_ids": [] if has_policy else ["law-go-kr-drf-api"],
                            "source_output_mode": "none" if has_policy else "link-only",
                        }
                    )
                capability = {
                    "slug": "matrix-capability",
                    "source_policy_ids": ["law-go-kr-drf-api"] if any(
                        item["source_policy_ids"] for item in operations
                    ) else [],
                }
                contract = {
                    "id": "kgov/matrix-capability/v1",
                    "capability_slug": "matrix-capability",
                    "module": "kgov_runtime.capabilities.matrix_capability",
                    "kind": "hybrid",
                    "network_mode": network,
                    "default_operation_id": "kgov/matrix-capability/default/v1",
                    "operations": operations,
                    "exit_codes": copy.deepcopy(self.EXIT_CODES),
                    "forbidden_output_keys": copy.deepcopy(self.FORBIDDEN_KEYS),
                }
                after = (
                    contract["network_mode"],
                    operation["schema_status"],
                    bool(operation["source_policy_ids"]),
                    operation["source_output_mode"],
                )
                self.assertEqual((network, status, has_policy, output_mode), after)
                for original, mutated in zip(before, after, strict=True):
                    if original == mutated:
                        self.assertEqual(original, mutated)
                    else:
                        self.assertNotEqual(original, mutated)

                errors: list[str] = []
                helper(contract, 0, capability, "/runtime_contracts/0", errors)
                self.assertEqual(list(expected), errors)

    def test_active_schema_and_partial_nested_binding_are_valid(self) -> None:
        candidate = self.active_candidate()
        self.assertNotEqual("declared", candidate["runtime_contracts"][0]["operations"][0]["schema_status"])
        self.assertEqual([], self.validate_contracts(candidate))
        contract = candidate["runtime_contracts"][0]
        binding = {
            "contract_id": "kgov/public-document-hwpx/v1",
            "operation": "kgov/public-document-hwpx/inspect-document/v1",
            "fixed_input": {"options": {"limit": 2, "tags": ["alpha"]}},
        }
        self.assertEqual(
            [],
            self.validate_binding(
                binding,
                capability_slug="public-document-hwpx",
                contracts_by_id={contract["id"]: contract},
                pointer="/domains/0/skills/0/runtime_binding",
            ),
        )

    def test_binding_rejects_declared_unknown_mismatched_and_invalid_inputs(self) -> None:
        pointer = "/domains/0/skills/0/runtime_binding"
        declared_candidate = self.candidate()
        declared_contract = declared_candidate["runtime_contracts"][0]
        declared_binding = {
            "contract_id": declared_contract["id"],
            "operation": declared_contract["operations"][0]["id"],
            "fixed_input": {},
        }
        self.assertEqual(
            [f'V6_OPERATION_NOT_ACTIVE "{pointer}/operation"'],
            self.validate_binding(
                declared_binding,
                capability_slug="public-document-hwpx",
                contracts_by_id={declared_contract["id"]: declared_contract},
                pointer=pointer,
            ),
        )

        active = self.active_candidate()
        contract = active["runtime_contracts"][0]
        base_binding = {
            "contract_id": contract["id"],
            "operation": contract["operations"][0]["id"],
            "fixed_input": {"options": {"limit": 2}},
        }
        cases = (
            ("unknown-contract", "contract_id", "kgov/unknown/v1", "public-document-hwpx", [f'V6_UNKNOWN_REFERENCE "{pointer}/contract_id"']),
            ("unknown-operation", "operation", "kgov/public-document-hwpx/unknown/v1", "public-document-hwpx", [f'V6_UNKNOWN_REFERENCE "{pointer}/operation"']),
            ("capability-mismatch", None, None, "other-capability", [f'V6_BINDING_MISMATCH "{pointer}/contract_id"']),
            ("unknown-fixed-key", "fixed_input", {"unknown": "SECRET"}, "public-document-hwpx", [f'V6_INVALID_VALUE "{pointer}/fixed_input/unknown"']),
            ("invalid-nested", "fixed_input", {"options": {"limit": 0}}, "public-document-hwpx", [f'V6_INVALID_VALUE "{pointer}/fixed_input/options/limit"']),
        )
        for mutation, key, value, capability, expected in cases:
            with self.subTest(mutation=mutation):
                binding = copy.deepcopy(base_binding)
                original_inputs = (copy.deepcopy(binding), "public-document-hwpx")
                if key is not None:
                    binding[key] = value
                self.assertNotEqual(original_inputs, (binding, capability))
                self.assertEqual(
                    expected,
                    self.validate_binding(
                        binding,
                        capability_slug=capability,
                        contracts_by_id={contract["id"]: contract},
                        pointer=pointer,
                    ),
                )

    def test_active_output_schema_rejects_forbidden_and_nonclosed_nested_objects(self) -> None:
        forbidden = self.active_candidate()
        properties = forbidden["runtime_contracts"][0]["operations"][0]["output_schema"]["properties"]["result"]["properties"]
        original = copy.deepcopy(properties)
        properties["raw"] = {"type": "string"}
        self.assertNotEqual(original, properties)
        self.assertEqual(
            ['V6_CONTRACT_INVARIANT "/runtime_contracts/0/operations/0/output_schema/properties/result/properties/raw"'],
            self.validate_contracts(forbidden),
        )

        nonclosed = self.active_candidate()
        result_schema = nonclosed["runtime_contracts"][0]["operations"][0]["output_schema"]["properties"]["result"]
        original = result_schema["additionalProperties"]
        result_schema["additionalProperties"] = True
        self.assertNotEqual(original, result_schema["additionalProperties"])
        self.assertEqual(
            ['V6_INVALID_SCHEMA_DEFINITION "/runtime_contracts/0/operations/0/output_schema/properties/result/additionalProperties"'],
            self.validate_contracts(nonclosed),
        )

    def test_declared_active_fixture_exit_and_shape_rules_are_enforced(self) -> None:
        declared_schema = self.candidate()
        operation = declared_schema["runtime_contracts"][0]["operations"][0]
        original = copy.deepcopy(operation)
        operation["input_schema"] = {"type": "null"}
        self.assertNotEqual(original, operation)
        self.assertEqual(
            ['V6_CONTRACT_INVARIANT "/runtime_contracts/0/operations/0/input_schema"'],
            self.validate_contracts(declared_schema),
        )

        missing_active_schema = self.active_candidate()
        operation = missing_active_schema["runtime_contracts"][0]["operations"][0]
        original = operation.pop("output_schema")
        self.assertNotEqual(original, operation.get("output_schema"))
        self.assertEqual(
            ['V6_REQUIRED_FIELD "/runtime_contracts/0/operations/0/output_schema"'],
            self.validate_contracts(missing_active_schema),
        )

        fixture = self.candidate()
        operation = fixture["runtime_contracts"][19]["operations"][1]
        original = copy.deepcopy(operation)
        operation["fixture_argv"] = ["--fixture"]
        self.assertNotEqual(original, operation)
        self.assertEqual(
            ['V6_CONTRACT_INVARIANT "/runtime_contracts/19/operations/1/fixture_argv"'],
            self.validate_contracts(fixture),
        )

        contract_mutations = (
            (
                "exit_codes",
                {
                    "success": 1,
                    "review_blocked": 1,
                    "input_error": 2,
                    "policy_blocked": 3,
                    "upstream_error": 4,
                },
                "/runtime_contracts/0/exit_codes/success",
            ),
            ("forbidden_output_keys", list(reversed(self.FORBIDDEN_KEYS)), '/runtime_contracts/0/forbidden_output_keys'),
        )
        for key, value, pointer in contract_mutations:
            with self.subTest(key=key):
                candidate = self.candidate()
                original = copy.deepcopy(candidate["runtime_contracts"][0][key])
                candidate["runtime_contracts"][0][key] = value
                self.assertNotEqual(original, candidate["runtime_contracts"][0][key])
                self.assertEqual(
                    [f'V6_CONTRACT_INVARIANT "{pointer}"'],
                    self.validate_contracts(candidate),
                )

        unknown_contract_field = self.candidate()
        contract = unknown_contract_field["runtime_contracts"][0]
        original = copy.deepcopy(contract)
        contract["guessed"] = "SECRET"
        self.assertNotEqual(original, contract)
        self.assertEqual(
            ['V6_UNKNOWN_FIELD "/runtime_contracts/0/guessed"'],
            self.validate_contracts(unknown_contract_field),
        )

        missing_operation_field = self.candidate()
        operation = missing_operation_field["runtime_contracts"][0]["operations"][0]
        original = operation.pop("source_output_mode")
        self.assertNotEqual(original, operation.get("source_output_mode"))
        self.assertEqual(
            ['V6_REQUIRED_FIELD "/runtime_contracts/0/operations/0/source_output_mode"'],
            self.validate_contracts(missing_operation_field),
        )

    def test_exit_codes_reject_boolean_and_integral_float_aliases_on_every_field(self) -> None:
        cases = (
            ("success", False, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/success"'),
            ("success", True, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/success"'),
            ("success", 0.0, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/success"'),
            ("review_blocked", False, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/review_blocked"'),
            ("review_blocked", True, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/review_blocked"'),
            ("review_blocked", 1.0, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/review_blocked"'),
            ("input_error", False, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/input_error"'),
            ("input_error", True, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/input_error"'),
            ("input_error", 2.0, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/input_error"'),
            ("policy_blocked", False, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/policy_blocked"'),
            ("policy_blocked", True, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/policy_blocked"'),
            ("policy_blocked", 3.0, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/policy_blocked"'),
            ("upstream_error", False, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/upstream_error"'),
            ("upstream_error", True, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/upstream_error"'),
            ("upstream_error", 4.0, 'V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/upstream_error"'),
        )
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                candidate = self.candidate()
                exit_codes = candidate["runtime_contracts"][0]["exit_codes"]
                original = exit_codes[field]
                exit_codes[field] = value
                self.assertNotEqual(type(original), type(value))
                self.assertEqual([expected], self.validate_contracts(candidate))

    def test_exit_codes_reject_wrong_integers_at_exact_member_pointers(self) -> None:
        cases = (
            ("success", 5, 'V6_CONTRACT_INVARIANT "/runtime_contracts/0/exit_codes/success"'),
            ("review_blocked", 0, 'V6_CONTRACT_INVARIANT "/runtime_contracts/0/exit_codes/review_blocked"'),
            ("input_error", -2, 'V6_CONTRACT_INVARIANT "/runtime_contracts/0/exit_codes/input_error"'),
            ("policy_blocked", 4, 'V6_CONTRACT_INVARIANT "/runtime_contracts/0/exit_codes/policy_blocked"'),
            ("upstream_error", 3, 'V6_CONTRACT_INVARIANT "/runtime_contracts/0/exit_codes/upstream_error"'),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                candidate = self.candidate()
                exit_codes = candidate["runtime_contracts"][0]["exit_codes"]
                original = exit_codes[field]
                exit_codes[field] = value
                self.assertNotEqual(original, value)
                self.assertEqual([expected], self.validate_contracts(candidate))

    def test_exit_codes_is_an_explicit_closed_required_object(self) -> None:
        required_cases = (
            ("success", 'V6_REQUIRED_FIELD "/runtime_contracts/0/exit_codes/success"'),
            ("review_blocked", 'V6_REQUIRED_FIELD "/runtime_contracts/0/exit_codes/review_blocked"'),
            ("input_error", 'V6_REQUIRED_FIELD "/runtime_contracts/0/exit_codes/input_error"'),
            ("policy_blocked", 'V6_REQUIRED_FIELD "/runtime_contracts/0/exit_codes/policy_blocked"'),
            ("upstream_error", 'V6_REQUIRED_FIELD "/runtime_contracts/0/exit_codes/upstream_error"'),
        )
        for field, expected in required_cases:
            with self.subTest(missing=field):
                candidate = self.candidate()
                exit_codes = candidate["runtime_contracts"][0]["exit_codes"]
                original = copy.deepcopy(exit_codes)
                del exit_codes[field]
                self.assertNotEqual(original, exit_codes)
                self.assertEqual([expected], self.validate_contracts(candidate))

        unknown_cases = (
            ("ordinary", 'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/ordinary"'),
            ("slash/key", 'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/slash~1key"'),
            ("tilde~key", 'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/tilde~0key"'),
            (json.loads(r'"alien\ud800"'), r'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/alien\ud800"'),
            (json.loads(r'"alien\udfff"'), r'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/alien\udfff"'),
            (json.loads(r'"alien\ud800\udc00"'), 'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/alien\U00010000"'),
            (json.loads(r'"alien\udbff\udfff"'), 'V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/alien\U0010ffff"'),
        )
        for field, expected in unknown_cases:
            with self.subTest(unknown=ascii(field)):
                candidate = self.candidate()
                exit_codes = candidate["runtime_contracts"][0]["exit_codes"]
                original = copy.deepcopy(exit_codes)
                exit_codes[field] = 5
                self.assertNotEqual(original, exit_codes)
                errors = self.validate_contracts(candidate)
                self.assertEqual([expected], errors)
                json.dumps(errors, ensure_ascii=False).encode("utf-8")

        for value in (None, [], "0/1/2/3/4"):
            with self.subTest(container=value):
                candidate = self.candidate()
                original = candidate["runtime_contracts"][0]["exit_codes"]
                candidate["runtime_contracts"][0]["exit_codes"] = value
                self.assertNotEqual(original, value)
                self.assertEqual(
                    ['V6_INVALID_TYPE "/runtime_contracts/0/exit_codes"'],
                    self.validate_contracts(candidate),
                )

    def test_copied_repository_cli_rejects_boolean_and_float_exit_codes(self) -> None:
        cases = (
            (
                "success",
                False,
                b'ERROR V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/success"\n',
            ),
            (
                "input_error",
                2.0,
                b'ERROR V6_INVALID_TYPE "/runtime_contracts/0/exit_codes/input_error"\n',
            ),
        )
        for field, value, expected_stdout in cases:
            with self.subTest(field=field):
                candidate = json.loads(
                    (ROOT / "catalog/domain-skills.json").read_text(encoding="utf-8")
                )
                exit_codes = candidate["runtime_contracts"][0]["exit_codes"]
                original = exit_codes[field]
                exit_codes[field] = value
                self.assertNotEqual(type(original), type(value))
                raw = json.dumps(candidate, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"

                result, temp_root, copied_paths = StrictCatalogJsonLoaderTest.run_copied_repo_cli(raw)

                self.assertEqual(STRICT_CLI_OWNED_PATHS, copied_paths)
                self.assertEqual(1, result.returncode)
                self.assertEqual(expected_stdout, result.stdout)
                self.assertEqual(b"", result.stderr)
                self.assertNotIn(b"Traceback", result.stdout + result.stderr)
                self.assertFalse(temp_root.exists())


class CatalogV6IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((ROOT / "catalog/domain-skills.json").read_text(encoding="utf-8"))

    def v6_candidate(self):
        candidate = copy.deepcopy(self.data)
        self.assertEqual(6, candidate.get("schema_version"))
        return candidate

    def validate_candidate(self, candidate) -> list[str]:
        try:
            return validate(candidate, ROOT, on_date=date(2026, 9, 5))
        except (KeyError, TypeError, ValueError) as error:
            self.fail(f"validator raised {type(error).__name__}")

    def test_live_catalog_is_schema_v6_and_valid(self) -> None:
        candidate = self.v6_candidate()

        self.assertEqual([], self.validate_candidate(candidate))

    def test_unknown_surrogate_member_names_have_exact_total_sorted_pointers(self) -> None:
        escaped_keys = (
            json.loads(r'"alien\ud800"'),
            json.loads(r'"alien\udfff"'),
            json.loads(r'"alien\ud800\udc00"'),
            json.loads(r'"alien\udbff\udfff"'),
        )
        candidate = self.v6_candidate()
        candidate["alien/a"] = None
        candidate["alien~a"] = None
        for key in escaped_keys:
            candidate[key] = None
        candidate["research_source"]["nested/a"] = None
        candidate["research_source"]["nested~a"] = None
        for key in escaped_keys:
            candidate["research_source"][key] = None

        errors = self.validate_candidate(candidate)

        self.assertEqual(
            [
                'V6_UNKNOWN_FIELD "/alien~0a"',
                'V6_UNKNOWN_FIELD "/alien~1a"',
                'V6_UNKNOWN_FIELD "/alien\\ud800"',
                'V6_UNKNOWN_FIELD "/alien\\udfff"',
                'V6_UNKNOWN_FIELD "/alien\U00010000"',
                'V6_UNKNOWN_FIELD "/alien\U0010ffff"',
                'V6_UNKNOWN_FIELD "/research_source/alien\\ud800"',
                'V6_UNKNOWN_FIELD "/research_source/alien\\udfff"',
                'V6_UNKNOWN_FIELD "/research_source/alien\U00010000"',
                'V6_UNKNOWN_FIELD "/research_source/alien\U0010ffff"',
                'V6_UNKNOWN_FIELD "/research_source/nested~0a"',
                'V6_UNKNOWN_FIELD "/research_source/nested~1a"',
            ],
            errors,
        )
        serialized = json.dumps(errors, ensure_ascii=False).encode("utf-8")
        self.assertNotIn(b"alien\xed\xa0\x80", serialized)
        self.assertNotIn(b"alien\xed\xbf\xbf", serialized)

    def test_empty_domain_evidence_returns_exact_type_diagnostic(self) -> None:
        candidate = self.v6_candidate()
        candidate["domains"][0]["evidence"] = []

        self.assertEqual(
            ['V6_INVALID_TYPE "/domains/0/evidence"'],
            self.validate_candidate(candidate),
        )

    def test_invalid_domain_group_returns_exact_non_leaking_diagnostic(self) -> None:
        supplied = "SECRET_QUERY_CREDENTIAL"
        candidate = self.v6_candidate()
        candidate["domains"][0]["group"] = supplied

        errors = self.validate_candidate(candidate)

        self.assertEqual(['V6_INVALID_VALUE "/domains/0/group"'], errors)
        self.assertNotIn(supplied, "\n".join(errors))

    def test_domain_and_skill_fields_fail_closed_before_legacy_validation(self) -> None:
        supplied = "SECRET_QUERY_CREDENTIAL"
        cases = (
            (("domains", 0, "domain"), [], 'V6_INVALID_TYPE "/domains/0/domain"'),
            (("domains", 0, "domain"), "", 'V6_INVALID_VALUE "/domains/0/domain"'),
            (("domains", 0, "group"), [], 'V6_INVALID_TYPE "/domains/0/group"'),
            (("domains", 0, "evidence"), supplied, 'V6_INVALID_VALUE "/domains/0/evidence"'),
            (("domains", 0, "skills"), {}, 'V6_INVALID_TYPE "/domains/0/skills"'),
            (("domains", 0, "skills"), [], 'V6_INVALID_VALUE "/domains/0/skills"'),
            (("domains", 0, "skills", 0), [], 'V6_INVALID_TYPE "/domains/0/skills/0"'),
            (("domains", 0, "skills", 0, "name"), [], 'V6_INVALID_TYPE "/domains/0/skills/0/name"'),
            (("domains", 0, "skills", 0, "name"), supplied, 'V6_INVALID_FORMAT "/domains/0/skills/0/name"'),
            (("domains", 0, "skills", 0, "title"), [], 'V6_INVALID_TYPE "/domains/0/skills/0/title"'),
            (("domains", 0, "skills", 0, "title"), "", 'V6_INVALID_VALUE "/domains/0/skills/0/title"'),
            (("domains", 0, "skills", 0, "capability"), [], 'V6_INVALID_TYPE "/domains/0/skills/0/capability"'),
            (("domains", 0, "skills", 0, "capability"), supplied, 'V6_INVALID_FORMAT "/domains/0/skills/0/capability"'),
            (("domains", 0, "skills", 0, "role"), [], 'V6_INVALID_TYPE "/domains/0/skills/0/role"'),
            (("domains", 0, "skills", 0, "role"), supplied, 'V6_INVALID_VALUE "/domains/0/skills/0/role"'),
            (("domains", 0, "skills", 0, "reference_skills"), {}, 'V6_INVALID_TYPE "/domains/0/skills/0/reference_skills"'),
            (("domains", 0, "skills", 0, "reference_skills"), [supplied], 'V6_INVALID_FORMAT "/domains/0/skills/0/reference_skills/0"'),
            (("domains", 0, "skills", 0, "boundary"), [], 'V6_INVALID_TYPE "/domains/0/skills/0/boundary"'),
            (("domains", 0, "skills", 0, "boundary"), supplied, 'V6_INVALID_VALUE "/domains/0/skills/0/boundary"'),
            (("domains", 0, "skills", 0, "task_checks"), {}, 'V6_INVALID_TYPE "/domains/0/skills/0/task_checks"'),
            (("domains", 0, "skills", 0, "task_checks"), [], 'V6_INVALID_VALUE "/domains/0/skills/0/task_checks"'),
            (("domains", 0, "skills", 0, "task_checks"), [1], 'V6_INVALID_TYPE "/domains/0/skills/0/task_checks/0"'),
            (("domains", 0, "skills", 0, "runtime_binding"), [], 'V6_INVALID_TYPE "/domains/0/skills/0/runtime_binding"'),
        )
        for path, value, expected in cases:
            with self.subTest(path=path, value=value):
                candidate = self.v6_candidate()
                target = candidate
                for segment in path[:-1]:
                    target = target[segment]
                target[path[-1]] = value

                errors = self.validate_candidate(candidate)

                self.assertEqual([expected], errors)
                self.assertNotIn(supplied, "\n".join(errors))

    def test_valid_looking_identity_and_cardinality_mutations_are_exact_and_non_leaking(self) -> None:
        supplied = "secret-query-credential"
        cases = (
            (lambda candidate: candidate["domains"][0].__setitem__("domain", supplied), ['V6_INVALID_VALUE "/domains/0/domain"']),
            (lambda candidate: candidate["domains"][0]["skills"][0].__setitem__("name", supplied), ['V6_INVALID_VALUE "/domains/0/skills/0/name"']),
            (lambda candidate: candidate["domains"][0]["skills"][0].__setitem__("capability", supplied), ['V6_UNKNOWN_REFERENCE "/domains/0/skills/0/capability"']),
            (lambda candidate: candidate["domains"].pop(), ['V6_INVALID_VALUE "/domains"']),
            (lambda candidate: candidate["domains"][0]["skills"].pop(), ['V6_INVALID_VALUE "/domains/0/skills"']),
            (lambda candidate: candidate["shared_capabilities"].pop(), ['V6_INVALID_VALUE "/shared_capabilities"']),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                candidate = self.v6_candidate()
                mutate(candidate)
                errors = self.validate_candidate(candidate)
                self.assertEqual(expected, errors)
                self.assertNotIn(supplied, "\n".join(errors))

    def test_minimum_map_matrix_is_exact_total_and_non_leaking(self) -> None:
        supplied = "secret-query-credential"
        cases = (
            (lambda minimums: minimums.__setitem__(supplied, 5), ['V6_UNKNOWN_FIELD "/enforced_minimum_skills_by_domain/secret-query-credential"']),
            (lambda minimums: minimums.pop("행정"), ['V6_REQUIRED_FIELD "/enforced_minimum_skills_by_domain/행정"']),
            (lambda minimums: minimums.__setitem__("행정", supplied), ['V6_INVALID_TYPE "/enforced_minimum_skills_by_domain/행정"']),
            (lambda minimums: minimums.__setitem__("행정", True), ['V6_INVALID_TYPE "/enforced_minimum_skills_by_domain/행정"']),
            (lambda minimums: minimums.__setitem__("행정", 0), ['V6_INVALID_VALUE "/enforced_minimum_skills_by_domain/행정"']),
            (lambda minimums: minimums.__setitem__("행정", 6), ['V6_INVALID_VALUE "/enforced_minimum_skills_by_domain/행정"']),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                candidate = self.v6_candidate()
                mutate(candidate["enforced_minimum_skills_by_domain"])
                errors = self.validate_candidate(candidate)
                self.assertEqual(expected, errors)
                if supplied not in expected[0]:
                    self.assertNotIn(supplied, "\n".join(errors))

    def test_every_normative_object_kind_has_required_and_unknown_mutation_vectors(self) -> None:
        def at(candidate, location):
            node = candidate
            for member in location:
                node = node[member]
            return node

        def policy_candidate(member=None, value=None):
            candidate = SourcePolicyV6Test.candidate()
            if member is not None:
                candidate["source_policies"][0][member] = copy.deepcopy(value)
            return candidate

        def runtime_candidate(*, active=False):
            return (
                RuntimeContractV6Test.active_candidate()
                if active
                else RuntimeContractV6Test.candidate()
            )

        def catalog_errors(candidate):
            return self.validate_candidate(candidate)

        def policy_errors(candidate):
            return SourcePolicyV6Test.validate_policies(candidate)

        def runtime_errors(candidate):
            return RuntimeContractV6Test.validate_contracts(candidate)

        def schema_errors(candidate):
            declared = candidate.get("type")
            value = {
                "object": {},
                "array": [],
                "string": "",
                "integer": 0,
                "number": 0,
                "boolean": False,
                "null": None,
            }.get(declared[0] if isinstance(declared, list) else declared)
            return SchemaV6PrimitiveTest.validate_node(candidate, value)

        def binding_fixture():
            candidate = runtime_candidate(active=True)
            contract = candidate["runtime_contracts"][0]
            binding = {
                "contract_id": "kgov/public-document-hwpx/v1",
                "operation": "kgov/public-document-hwpx/inspect-document/v1",
                "fixed_input": {"query": "valid"},
            }

            def binding_errors(value):
                return RuntimeContractV6Test.validate_binding(
                    value,
                    capability_slug="public-document-hwpx",
                    contracts_by_id={"kgov/public-document-hwpx/v1": contract},
                    pointer="/domains/0/skills/0/runtime_binding",
                )

            return binding, binding_errors

        required_cases = (
            ("root", self.v6_candidate(), catalog_errors, (), "research_source", ['V6_REQUIRED_FIELD "/research_source"']),
            ("research_source", self.v6_candidate(), catalog_errors, ("research_source",), "wiki_authority", ['V6_REQUIRED_FIELD "/research_source/wiki_authority"']),
            ("enforced_minimum_map", self.v6_candidate(), catalog_errors, ("enforced_minimum_skills_by_domain",), "행정", ['V6_REQUIRED_FIELD "/enforced_minimum_skills_by_domain/행정"']),
            ("domain", self.v6_candidate(), catalog_errors, ("domains", 0), "group", ['V6_REQUIRED_FIELD "/domains/0/group"']),
            ("Skill", self.v6_candidate(), catalog_errors, ("domains", 0, "skills", 0), "title", ['V6_REQUIRED_FIELD "/domains/0/skills/0/title"']),
            ("capability", self.v6_candidate(), catalog_errors, ("shared_capabilities", 0), "manual_handoff_gate", ['V6_REQUIRED_FIELD "/shared_capabilities/0/manual_handoff_gate"']),
            ("source_policy", policy_candidate(), policy_errors, ("source_policies", 0), "institution", ['V6_REQUIRED_FIELD "/source_policies/0/institution"']),
            ("scope", policy_candidate(), policy_errors, ("source_policies", 0, "scope"), "methods", ['V6_REQUIRED_FIELD "/source_policies/0/scope/methods"']),
            ("path_rule", policy_candidate(), policy_errors, ("source_policies", 0, "scope", "path_rules", 0), "match", ['V6_REQUIRED_FIELD "/source_policies/0/scope/path_rules/0/match"']),
            ("review", policy_candidate("review", {"reviewed_on": "2026-09-01", "expires_on": "2026-10-01", "evidence_urls": ["https://example.org/review"]}), policy_errors, ("source_policies", 0, "review"), "reviewed_on", ['V6_REQUIRED_FIELD "/source_policies/0/review/reviewed_on"']),
            ("robots_unreviewed", policy_candidate("robots", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "robots"), "status", ['V6_REQUIRED_FIELD "/source_policies/0/robots/status"']),
            ("robots_required", policy_candidate("robots", {"status": "required"}), policy_errors, ("source_policies", 0, "robots"), "status", ['V6_REQUIRED_FIELD "/source_policies/0/robots/status"']),
            ("robots_exemption", policy_candidate("robots", {"status": "documented-api-exemption", "evidence_url": "https://example.org/robots"}), policy_errors, ("source_policies", 0, "robots"), "evidence_url", ['V6_REQUIRED_FIELD "/source_policies/0/robots/evidence_url"']),
            ("terms_unreviewed", policy_candidate("terms", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "terms"), "status", ['V6_REQUIRED_FIELD "/source_policies/0/terms/status"']),
            ("terms_manual_review", policy_candidate("terms", {"status": "manual-review", "url": "https://example.org/terms"}), policy_errors, ("source_policies", 0, "terms"), "url", ['V6_REQUIRED_FIELD "/source_policies/0/terms/url"']),
            ("terms_allowed", policy_candidate("terms", {"status": "allowed", "url": "https://example.org/terms"}), policy_errors, ("source_policies", 0, "terms"), "url", ['V6_REQUIRED_FIELD "/source_policies/0/terms/url"']),
            ("terms_prohibited", policy_candidate("terms", {"status": "prohibited", "url": "https://example.org/terms"}), policy_errors, ("source_policies", 0, "terms"), "url", ['V6_REQUIRED_FIELD "/source_policies/0/terms/url"']),
            ("rate_unreviewed", policy_candidate("rate_limit", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "rate_limit"), "status", ['V6_REQUIRED_FIELD "/source_policies/0/rate_limit/status"']),
            ("rate_reviewed", policy_candidate("rate_limit", {"status": "reviewed", "requests": 1, "per_seconds": 1, "burst": 1, "max_wait_seconds": 0}), policy_errors, ("source_policies", 0, "rate_limit"), "burst", ['V6_REQUIRED_FIELD "/source_policies/0/rate_limit/burst"']),
            ("response_unreviewed", policy_candidate("response", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "response"), "status", ['V6_REQUIRED_FIELD "/source_policies/0/response/status"']),
            ("response_reviewed", policy_candidate("response", {"status": "reviewed", "max_bytes": 1, "media_types": ["application/json"]}), policy_errors, ("source_policies", 0, "response"), "max_bytes", ['V6_REQUIRED_FIELD "/source_policies/0/response/max_bytes"']),
            ("license_unreviewed", policy_candidate("license", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "license"), "status", ['V6_REQUIRED_FIELD "/source_policies/0/license/status"']),
            ("license_manual_review", policy_candidate("license", {"status": "manual-review", "url": "https://example.org/license"}), policy_errors, ("source_policies", 0, "license"), "url", ['V6_REQUIRED_FIELD "/source_policies/0/license/url"']),
            ("license_reviewed", policy_candidate("license", {"status": "reviewed", "url": "https://example.org/license", "allowed_output_modes": ["link-only"], "redistribution": "link-only"}), policy_errors, ("source_policies", 0, "license"), "redistribution", ['V6_REQUIRED_FIELD "/source_policies/0/license/redistribution"']),
            ("retention", policy_candidate(), policy_errors, ("source_policies", 0, "retention"), "raw_content", ['V6_REQUIRED_FIELD "/source_policies/0/retention/raw_content"']),
            ("runtime_contract", runtime_candidate(), runtime_errors, ("runtime_contracts", 0), "kind", ['V6_REQUIRED_FIELD "/runtime_contracts/0/kind"']),
            ("operation_declared", runtime_candidate(), runtime_errors, ("runtime_contracts", 0, "operations", 0), "source_output_mode", ['V6_REQUIRED_FIELD "/runtime_contracts/0/operations/0/source_output_mode"']),
            ("operation_active", runtime_candidate(active=True), runtime_errors, ("runtime_contracts", 0, "operations", 0), "input_schema", ['V6_REQUIRED_FIELD "/runtime_contracts/0/operations/0/input_schema"']),
            ("exit_codes", runtime_candidate(), runtime_errors, ("runtime_contracts", 0, "exit_codes"), "input_error", ['V6_REQUIRED_FIELD "/runtime_contracts/0/exit_codes/input_error"']),
            ("schema_object", {"type": "object", "required": [], "properties": {}, "additionalProperties": False}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_closed_object_required", {"type": "object", "required": [], "properties": {}, "additionalProperties": False}, schema_errors, (), "required", ['V6_INVALID_SCHEMA_DEFINITION "/required"']),
            ("schema_closed_object_properties", {"type": "object", "required": [], "properties": {}, "additionalProperties": False}, schema_errors, (), "properties", ['V6_INVALID_SCHEMA_DEFINITION "/properties"']),
            ("schema_closed_object_additionalProperties", {"type": "object", "required": [], "properties": {}, "additionalProperties": False}, schema_errors, (), "additionalProperties", ['V6_INVALID_SCHEMA_DEFINITION "/additionalProperties"']),
            ("schema_array", {"type": "array", "items": {"type": "null"}}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_array_items", {"type": "array", "items": {"type": "null"}}, schema_errors, (), "items", ['V6_INVALID_SCHEMA_DEFINITION "/items"']),
            ("schema_string", {"type": "string"}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_integer", {"type": "integer"}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_number", {"type": "number"}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_boolean", {"type": "boolean"}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_null", {"type": "null"}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
            ("schema_nullable", {"type": ["string", "null"]}, schema_errors, (), "type", ['V6_INVALID_SCHEMA_DEFINITION "/type"']),
        )
        binding, binding_errors = binding_fixture()
        required_cases += (
            ("runtime_binding", binding, binding_errors, (), "fixed_input", ['V6_REQUIRED_FIELD "/domains/0/skills/0/runtime_binding/fixed_input"']),
        )
        required_labels = (
            "root", "research_source", "enforced_minimum_map", "domain", "Skill", "capability",
            "source_policy", "scope", "path_rule", "review", "robots_unreviewed",
            "robots_required", "robots_exemption", "terms_unreviewed", "terms_manual_review",
            "terms_allowed", "terms_prohibited", "rate_unreviewed", "rate_reviewed",
            "response_unreviewed", "response_reviewed", "license_unreviewed",
            "license_manual_review", "license_reviewed", "retention", "runtime_contract",
            "operation_declared", "operation_active", "exit_codes", "schema_object",
            "schema_closed_object_required", "schema_closed_object_properties",
            "schema_closed_object_additionalProperties", "schema_array", "schema_array_items",
            "schema_string", "schema_integer", "schema_number", "schema_boolean", "schema_null",
            "schema_nullable", "runtime_binding",
        )
        self.assertEqual(required_labels, tuple(case[0] for case in required_cases))
        for label, candidate, validator, location, field, expected in required_cases:
            with self.subTest(mutation="required", object_kind=label):
                self.assertEqual([], validator(candidate))
                node = at(candidate, location)
                original = copy.deepcopy(node)
                del node[field]
                self.assertNotEqual(original, node)
                self.assertEqual(expected, validator(candidate))

        unknown_cases = (
            ("root", self.v6_candidate(), catalog_errors, (), ['V6_UNKNOWN_FIELD "/ordinary"']),
            ("research_source", self.v6_candidate(), catalog_errors, ("research_source",), ['V6_UNKNOWN_FIELD "/research_source/ordinary"']),
            ("enforced_minimum_map", self.v6_candidate(), catalog_errors, ("enforced_minimum_skills_by_domain",), ['V6_UNKNOWN_FIELD "/enforced_minimum_skills_by_domain/ordinary"']),
            ("domain", self.v6_candidate(), catalog_errors, ("domains", 0), ['V6_UNKNOWN_FIELD "/domains/0/ordinary"']),
            ("Skill", self.v6_candidate(), catalog_errors, ("domains", 0, "skills", 0), ['V6_UNKNOWN_FIELD "/domains/0/skills/0/ordinary"']),
            ("capability", self.v6_candidate(), catalog_errors, ("shared_capabilities", 0), ['V6_UNKNOWN_FIELD "/shared_capabilities/0/ordinary"']),
            ("source_policy", policy_candidate(), policy_errors, ("source_policies", 0), ['V6_UNKNOWN_FIELD "/source_policies/0/ordinary"']),
            ("scope", policy_candidate(), policy_errors, ("source_policies", 0, "scope"), ['V6_UNKNOWN_FIELD "/source_policies/0/scope/ordinary"']),
            ("path_rule", policy_candidate(), policy_errors, ("source_policies", 0, "scope", "path_rules", 0), ['V6_UNKNOWN_FIELD "/source_policies/0/scope/path_rules/0/ordinary"']),
            ("review", policy_candidate("review", {"reviewed_on": "2026-09-01", "expires_on": "2026-10-01", "evidence_urls": ["https://example.org/review"]}), policy_errors, ("source_policies", 0, "review"), ['V6_UNKNOWN_FIELD "/source_policies/0/review/ordinary"']),
            ("robots_unreviewed", policy_candidate("robots", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "robots"), ['V6_UNKNOWN_FIELD "/source_policies/0/robots/ordinary"']),
            ("robots_required", policy_candidate("robots", {"status": "required"}), policy_errors, ("source_policies", 0, "robots"), ['V6_UNKNOWN_FIELD "/source_policies/0/robots/ordinary"']),
            ("robots_exemption", policy_candidate("robots", {"status": "documented-api-exemption", "evidence_url": "https://example.org/robots"}), policy_errors, ("source_policies", 0, "robots"), ['V6_UNKNOWN_FIELD "/source_policies/0/robots/ordinary"']),
            ("terms_unreviewed", policy_candidate("terms", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "terms"), ['V6_UNKNOWN_FIELD "/source_policies/0/terms/ordinary"']),
            ("terms_manual_review", policy_candidate("terms", {"status": "manual-review", "url": "https://example.org/terms"}), policy_errors, ("source_policies", 0, "terms"), ['V6_UNKNOWN_FIELD "/source_policies/0/terms/ordinary"']),
            ("terms_allowed", policy_candidate("terms", {"status": "allowed", "url": "https://example.org/terms"}), policy_errors, ("source_policies", 0, "terms"), ['V6_UNKNOWN_FIELD "/source_policies/0/terms/ordinary"']),
            ("terms_prohibited", policy_candidate("terms", {"status": "prohibited", "url": "https://example.org/terms"}), policy_errors, ("source_policies", 0, "terms"), ['V6_UNKNOWN_FIELD "/source_policies/0/terms/ordinary"']),
            ("rate_unreviewed", policy_candidate("rate_limit", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "rate_limit"), ['V6_UNKNOWN_FIELD "/source_policies/0/rate_limit/ordinary"']),
            ("rate_reviewed", policy_candidate("rate_limit", {"status": "reviewed", "requests": 1, "per_seconds": 1, "burst": 1, "max_wait_seconds": 0}), policy_errors, ("source_policies", 0, "rate_limit"), ['V6_UNKNOWN_FIELD "/source_policies/0/rate_limit/ordinary"']),
            ("response_unreviewed", policy_candidate("response", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "response"), ['V6_UNKNOWN_FIELD "/source_policies/0/response/ordinary"']),
            ("response_reviewed", policy_candidate("response", {"status": "reviewed", "max_bytes": 1, "media_types": ["application/json"]}), policy_errors, ("source_policies", 0, "response"), ['V6_UNKNOWN_FIELD "/source_policies/0/response/ordinary"']),
            ("license_unreviewed", policy_candidate("license", {"status": "unreviewed"}), policy_errors, ("source_policies", 0, "license"), ['V6_UNKNOWN_FIELD "/source_policies/0/license/ordinary"']),
            ("license_manual_review", policy_candidate("license", {"status": "manual-review", "url": "https://example.org/license"}), policy_errors, ("source_policies", 0, "license"), ['V6_UNKNOWN_FIELD "/source_policies/0/license/ordinary"']),
            ("license_reviewed", policy_candidate("license", {"status": "reviewed", "url": "https://example.org/license", "allowed_output_modes": ["link-only"], "redistribution": "link-only"}), policy_errors, ("source_policies", 0, "license"), ['V6_UNKNOWN_FIELD "/source_policies/0/license/ordinary"']),
            ("retention", policy_candidate(), policy_errors, ("source_policies", 0, "retention"), ['V6_UNKNOWN_FIELD "/source_policies/0/retention/ordinary"']),
            ("runtime_contract", runtime_candidate(), runtime_errors, ("runtime_contracts", 0), ['V6_UNKNOWN_FIELD "/runtime_contracts/0/ordinary"']),
            ("operation_declared", runtime_candidate(), runtime_errors, ("runtime_contracts", 0, "operations", 0), ['V6_UNKNOWN_FIELD "/runtime_contracts/0/operations/0/ordinary"']),
            ("operation_active", runtime_candidate(active=True), runtime_errors, ("runtime_contracts", 0, "operations", 0), ['V6_UNKNOWN_FIELD "/runtime_contracts/0/operations/0/ordinary"']),
            ("exit_codes", runtime_candidate(), runtime_errors, ("runtime_contracts", 0, "exit_codes"), ['V6_UNKNOWN_FIELD "/runtime_contracts/0/exit_codes/ordinary"']),
            ("schema_object", {"type": "object", "required": [], "properties": {}, "additionalProperties": False}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_array", {"type": "array", "items": {"type": "null"}}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_string", {"type": "string"}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_integer", {"type": "integer"}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_number", {"type": "number"}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_boolean", {"type": "boolean"}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_null", {"type": "null"}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
            ("schema_nullable", {"type": ["string", "null"]}, schema_errors, (), ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/ordinary"']),
        )
        binding, binding_errors = binding_fixture()
        unknown_cases += (
            ("runtime_binding", binding, binding_errors, (), ['V6_UNKNOWN_FIELD "/domains/0/skills/0/runtime_binding/ordinary"']),
        )
        unknown_labels = (
            "root", "research_source", "enforced_minimum_map", "domain", "Skill", "capability",
            "source_policy", "scope", "path_rule", "review", "robots_unreviewed",
            "robots_required", "robots_exemption", "terms_unreviewed", "terms_manual_review",
            "terms_allowed", "terms_prohibited", "rate_unreviewed", "rate_reviewed",
            "response_unreviewed", "response_reviewed", "license_unreviewed",
            "license_manual_review", "license_reviewed", "retention", "runtime_contract",
            "operation_declared", "operation_active", "exit_codes", "schema_object", "schema_array",
            "schema_string", "schema_integer", "schema_number", "schema_boolean", "schema_null",
            "schema_nullable", "runtime_binding",
        )
        self.assertEqual(unknown_labels, tuple(case[0] for case in unknown_cases))
        for label, candidate, validator, location, expected in unknown_cases:
            with self.subTest(mutation="unknown", object_kind=label):
                self.assertEqual([], validator(candidate))
                node = at(candidate, location)
                original = copy.deepcopy(node)
                node["ordinary"] = "not echoed"
                self.assertNotEqual(original, node)
                self.assertEqual(expected, validator(candidate))

        shape_helper = getattr(validate_catalog, "_validate_object_shape")
        special_keys = (
            ("slash/key", ['V6_UNKNOWN_FIELD "/matrix/slash~1key"']),
            ("tilde~key", ['V6_UNKNOWN_FIELD "/matrix/tilde~0key"']),
            (json.loads(r'"alien\ud800"'), [r'V6_UNKNOWN_FIELD "/matrix/alien\ud800"']),
            (json.loads(r'"alien\udfff"'), [r'V6_UNKNOWN_FIELD "/matrix/alien\udfff"']),
            (json.loads(r'"alien\ud800\udc00"'), ['V6_UNKNOWN_FIELD "/matrix/alien\U00010000"']),
            (json.loads(r'"alien\udbff\udfff"'), ['V6_UNKNOWN_FIELD "/matrix/alien\U0010ffff"']),
        )
        for key, expected in special_keys:
            with self.subTest(mutation="shared-shape-special-key", key=ascii(key)):
                node = {"required": True}
                baseline_errors = []
                shape_helper(node, "/matrix", (("required",), frozenset()), baseline_errors)
                self.assertEqual([], baseline_errors)
                original = copy.deepcopy(node)
                node[key] = "not echoed"
                self.assertNotEqual(original, node)
                errors = []
                shape_helper(node, "/matrix", (("required",), frozenset()), errors)
                self.assertEqual(expected, errors)
                json.dumps(errors, ensure_ascii=False).encode("utf-8")

    def test_skill_reference_duplicates_fail_at_each_subsequent_pointer(self) -> None:
        candidate = self.v6_candidate()
        references = candidate["domains"][0]["skills"][0]["reference_skills"]
        self.assertGreaterEqual(len(references), 1)
        references[:] = [references[0], references[0], references[0]]

        self.assertEqual(
            [
                'V6_DUPLICATE_VALUE "/domains/0/skills/0/reference_skills/1"',
                'V6_DUPLICATE_VALUE "/domains/0/skills/0/reference_skills/2"',
            ],
            self.validate_candidate(candidate),
        )

    def test_approved_runtime_manifest_rejects_valid_looking_extra_operation(self) -> None:
        supplied = "secret-query-credential"
        candidate = self.v6_candidate()
        candidate["runtime_contracts"][0]["operations"].append(
            {
                "id": f"kgov/public-document-hwpx/{supplied}/v1",
                "schema_status": "declared",
                "source_policy_ids": [],
                "source_output_mode": "none",
            }
        )

        errors = self.validate_candidate(candidate)
        self.assertEqual(
            ['V6_CONTRACT_INVARIANT "/runtime_contracts/0/operations"'],
            errors,
        )
        self.assertNotIn(supplied, "\n".join(errors))

    def test_research_source_and_skill_topology_semantics_fail_closed(self) -> None:
        supplied = "secret-query-credential"
        research_cases = (
            ("wiki_authority", supplied),
            ("wiki_source_map", supplied),
            ("reference_repository", "https://example.go.kr/"),
            ("reference_head", "a" * 40),
        )
        for field, value in research_cases:
            with self.subTest(field=field):
                candidate = self.v6_candidate()
                candidate["research_source"][field] = value
                errors = self.validate_candidate(candidate)
                self.assertEqual([f'V6_INVALID_VALUE "/research_source/{field}"'], errors)
                self.assertNotIn(supplied, "\n".join(errors))

        topology_cases = (
            (lambda skill: skill.__setitem__("role", "additional"), ['V6_INVALID_VALUE "/domains/0/skills"']),
            (lambda skill: skill.__setitem__("reference_skills", []), ['V6_INVALID_VALUE "/domains/0/skills/0/reference_skills"']),
        )
        for mutate, expected in topology_cases:
            with self.subTest(expected=expected):
                candidate = self.v6_candidate()
                mutate(candidate["domains"][0]["skills"][0])
                self.assertEqual(expected, self.validate_candidate(candidate))

        candidate = self.v6_candidate()
        sensitive_index = next(
            index for index, domain in enumerate(candidate["domains"])
            if domain["evidence"] == "sensitive"
        )
        skill_index = next(
            index for index, skill in enumerate(candidate["domains"][sensitive_index]["skills"])
            if skill["role"] == "additional"
        )
        candidate["domains"][sensitive_index]["skills"][skill_index]["boundary"] = "draft-only"
        self.assertEqual(
            [f'V6_INVALID_VALUE "/domains/{sensitive_index}/skills/{skill_index}/boundary"'],
            self.validate_candidate(candidate),
        )

    def test_every_approved_contract_rejects_an_extra_valid_operation(self) -> None:
        supplied = "secret-query-credential"
        for contract_index in range(22):
            with self.subTest(contract_index=contract_index):
                candidate = self.v6_candidate()
                contract = candidate["runtime_contracts"][contract_index]
                contract["operations"].append(
                    {
                        "id": f'{contract["id"][:-3]}/{supplied}/v1',
                        "schema_status": "declared",
                        "source_policy_ids": [],
                        "source_output_mode": "none",
                    }
                )
                errors = self.validate_candidate(candidate)
                self.assertEqual(
                    [f'V6_CONTRACT_INVARIANT "/runtime_contracts/{contract_index}/operations"'],
                    errors,
                )
                self.assertNotIn(supplied, "\n".join(errors))

    def test_contract_capability_cardinality_and_exact_table_are_enforced(self) -> None:
        cases = (
            (lambda candidate: candidate["runtime_contracts"].pop(), ['V6_INVALID_VALUE "/runtime_contracts"']),
            (lambda candidate: candidate["shared_capabilities"].pop(), ['V6_INVALID_VALUE "/shared_capabilities"']),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                candidate = self.v6_candidate()
                mutate(candidate)
                self.assertEqual(expected, self.validate_candidate(candidate))

        for contract_index in range(22):
            with self.subTest(contract_index=contract_index):
                candidate = self.v6_candidate()
                contract = candidate["runtime_contracts"][contract_index]
                contract["kind"] = "verification" if contract["kind"] != "verification" else "admission"
                self.assertEqual(
                    [f'V6_CONTRACT_INVARIANT "/runtime_contracts/{contract_index}/kind"'],
                    self.validate_candidate(candidate),
                )

    def test_every_domain_and_skill_container_type_is_total_and_exact(self) -> None:
        non_strings = (None, False, 0, 1.5, [], {})
        non_lists = (None, False, 0, 1.5, "SECRET_QUERY_CREDENTIAL", {})
        non_objects = (None, False, 0, 1.5, "SECRET_QUERY_CREDENTIAL", [])
        cases = []
        for path in (
            ("domains", 0, "domain"),
            ("domains", 0, "group"),
            ("domains", 0, "evidence"),
            ("domains", 0, "skills", 0, "name"),
            ("domains", 0, "skills", 0, "title"),
            ("domains", 0, "skills", 0, "capability"),
            ("domains", 0, "skills", 0, "role"),
            ("domains", 0, "skills", 0, "boundary"),
        ):
            pointer = "/" + "/".join(str(segment) for segment in path)
            cases.extend((path, value, f'V6_INVALID_TYPE "{pointer}"') for value in non_strings)
        for path in (
            ("domains", 0, "skills"),
            ("domains", 0, "skills", 0, "reference_skills"),
            ("domains", 0, "skills", 0, "task_checks"),
        ):
            pointer = "/" + "/".join(str(segment) for segment in path)
            cases.extend((path, value, f'V6_INVALID_TYPE "{pointer}"') for value in non_lists)
        for path in (
            ("domains", 0, "skills", 0),
            ("domains", 0, "skills", 0, "runtime_binding"),
        ):
            pointer = "/" + "/".join(str(segment) for segment in path)
            cases.extend((path, value, f'V6_INVALID_TYPE "{pointer}"') for value in non_objects)
        for field in ("reference_skills", "task_checks"):
            path = ("domains", 0, "skills", 0, field, 0)
            pointer = "/" + "/".join(str(segment) for segment in path)
            cases.extend((path, value, f'V6_INVALID_TYPE "{pointer}"') for value in non_strings)

        for path, value, expected in cases:
            with self.subTest(path=path, value=value):
                candidate = self.v6_candidate()
                if len(path) > 1 and path[-2] == "task_checks":
                    candidate["domains"][0]["skills"][0]["task_checks"] = ["valid check"]
                target = candidate
                for segment in path[:-1]:
                    target = target[segment]
                target[path[-1]] = value

                errors = self.validate_candidate(candidate)

                self.assertEqual([expected], errors)
                self.assertNotIn("SECRET_QUERY_CREDENTIAL", "\n".join(errors))

    def test_every_capability_field_fails_closed_for_invalid_json_categories(self) -> None:
        supplied = "SECRET_QUERY_CREDENTIAL"
        type_errors = {
            "slug": 'V6_INVALID_TYPE "/shared_capabilities/0/slug"',
            "locale": 'V6_INVALID_TYPE "/shared_capabilities/0/locale"',
            "jurisdiction": 'V6_INVALID_TYPE "/shared_capabilities/0/jurisdiction"',
            "service": 'V6_INVALID_TYPE "/shared_capabilities/0/service"',
            "credential_class": 'V6_INVALID_TYPE "/shared_capabilities/0/credential_class"',
            "proxy_mode": 'V6_INVALID_TYPE "/shared_capabilities/0/proxy_mode"',
            "side_effect_class": 'V6_INVALID_TYPE "/shared_capabilities/0/side_effect_class"',
            "manual_handoff_gate": 'V6_INVALID_TYPE "/shared_capabilities/0/manual_handoff_gate"',
            "source_provenance": 'V6_INVALID_TYPE "/shared_capabilities/0/source_provenance"',
            "execution_status": 'V6_INVALID_TYPE "/shared_capabilities/0/execution_status"',
            "live_smoke": 'V6_INVALID_TYPE "/shared_capabilities/0/live_smoke"',
            "source_policy_ids": 'V6_INVALID_TYPE "/shared_capabilities/0/source_policy_ids"',
            "runtime_contract_id": 'V6_INVALID_TYPE "/shared_capabilities/0/runtime_contract_id"',
        }
        string_errors = {
            "slug": 'V6_INVALID_FORMAT "/shared_capabilities/0/slug"',
            "locale": 'V6_INVALID_VALUE "/shared_capabilities/0/locale"',
            "jurisdiction": 'V6_INVALID_VALUE "/shared_capabilities/0/jurisdiction"',
            "service": 'V6_INVALID_VALUE "/shared_capabilities/0/service"',
            "credential_class": 'V6_INVALID_VALUE "/shared_capabilities/0/credential_class"',
            "proxy_mode": 'V6_INVALID_VALUE "/shared_capabilities/0/proxy_mode"',
            "side_effect_class": 'V6_INVALID_VALUE "/shared_capabilities/0/side_effect_class"',
            "manual_handoff_gate": 'V6_INVALID_VALUE "/shared_capabilities/0/manual_handoff_gate"',
            "source_provenance": 'V6_INVALID_TYPE "/shared_capabilities/0/source_provenance"',
            "execution_status": 'V6_INVALID_VALUE "/shared_capabilities/0/execution_status"',
            "live_smoke": 'V6_INVALID_VALUE "/shared_capabilities/0/live_smoke"',
            "source_policy_ids": 'V6_INVALID_TYPE "/shared_capabilities/0/source_policy_ids"',
            "runtime_contract_id": 'V6_INVALID_FORMAT "/shared_capabilities/0/runtime_contract_id"',
        }
        array_errors = {
            "slug": 'V6_INVALID_TYPE "/shared_capabilities/0/slug"',
            "locale": 'V6_INVALID_TYPE "/shared_capabilities/0/locale"',
            "jurisdiction": 'V6_INVALID_TYPE "/shared_capabilities/0/jurisdiction"',
            "service": 'V6_INVALID_TYPE "/shared_capabilities/0/service"',
            "credential_class": 'V6_INVALID_TYPE "/shared_capabilities/0/credential_class"',
            "proxy_mode": 'V6_INVALID_TYPE "/shared_capabilities/0/proxy_mode"',
            "side_effect_class": 'V6_INVALID_TYPE "/shared_capabilities/0/side_effect_class"',
            "manual_handoff_gate": 'V6_INVALID_TYPE "/shared_capabilities/0/manual_handoff_gate"',
            "source_provenance": 'V6_INVALID_VALUE "/shared_capabilities/0/source_provenance"',
            "execution_status": 'V6_INVALID_TYPE "/shared_capabilities/0/execution_status"',
            "live_smoke": 'V6_INVALID_TYPE "/shared_capabilities/0/live_smoke"',
            "source_policy_ids": 'V6_INVALID_TYPE "/shared_capabilities/0/source_policy_ids/0"',
            "runtime_contract_id": 'V6_INVALID_TYPE "/shared_capabilities/0/runtime_contract_id"',
        }
        invalid_strings = {
            "service": "",
            "manual_handoff_gate": "",
        }
        cases = {
            field: (
                (None, type_errors[field]),
                (False, type_errors[field]),
                (0, type_errors[field]),
                (invalid_strings.get(field, supplied), string_errors[field]),
                ([False] if field == "source_policy_ids" else [], array_errors[field]),
                ({}, type_errors[field]),
            )
            for field in type_errors
        }

        self.assertEqual(
            {
                "slug", "locale", "jurisdiction", "service", "credential_class",
                "proxy_mode", "side_effect_class", "manual_handoff_gate",
                "source_provenance", "execution_status", "live_smoke",
                "source_policy_ids", "runtime_contract_id",
            },
            set(cases),
        )
        for field, vectors in cases.items():
            self.assertEqual(6, len(vectors))
            for value, expected in vectors:
                with self.subTest(field=field, value=value):
                    candidate = self.v6_candidate()
                    candidate["shared_capabilities"][0][field] = value

                    errors = self.validate_candidate(candidate)

                    self.assertEqual([expected], errors)
                    self.assertNotIn(supplied, "\n".join(errors))

        for field, value, expected in (
            ("source_provenance", [False], 'V6_INVALID_TYPE "/shared_capabilities/0/source_provenance/0"'),
            ("source_provenance", [supplied], 'V6_INVALID_FORMAT "/shared_capabilities/0/source_provenance/0"'),
            ("source_policy_ids", [supplied], 'V6_INVALID_FORMAT "/shared_capabilities/0/source_policy_ids/0"'),
        ):
            with self.subTest(field=field, value=value):
                candidate = self.v6_candidate()
                candidate["shared_capabilities"][0][field] = value
                errors = self.validate_candidate(candidate)
                self.assertEqual([expected], errors)
                self.assertNotIn(supplied, "\n".join(errors))

    def test_capability_field_valid_controls_and_status_pairs_are_accepted(self) -> None:
        controls = {
            "slug": "public-document-hwpx",
            "locale": "ko-KR",
            "jurisdiction": "KR",
            "service": "local HWPX documents",
            "credential_class": "none",
            "proxy_mode": "none",
            "side_effect_class": "document-read",
            "manual_handoff_gate": "원본 변경·제출·결재는 별도 승인",
            "source_provenance": ["https://www.hancom.com/"],
            "execution_status": "fixture-verified",
            "live_smoke": "not-run",
            "source_policy_ids": [],
            "runtime_contract_id": "kgov/public-document-hwpx/v1",
        }
        for field, value in controls.items():
            with self.subTest(field=field):
                candidate = self.v6_candidate()
                candidate["shared_capabilities"][0][field] = copy.deepcopy(value)
                self.assertEqual([], self.validate_candidate(candidate))

        for execution_status, live_smoke in (
            ("live-verified", "not-run"),
            ("fixture-verified", "passed"),
        ):
            with self.subTest(execution_status=execution_status, live_smoke=live_smoke):
                candidate = self.v6_candidate()
                capability = candidate["shared_capabilities"][0]
                capability["execution_status"] = execution_status
                capability["live_smoke"] = live_smoke
                self.assertEqual(
                    ['V6_INVALID_VALUE "/shared_capabilities/0/live_smoke"'],
                    self.validate_candidate(candidate),
                )

    def test_root_order_and_independent_v6_inventories_are_exact(self) -> None:
        candidate = self.v6_candidate()
        expected_root_keys = (
            "schema_version",
            "target_skills_per_domain",
            "enforced_minimum_skills_by_domain",
            "research_source",
            "source_policies",
            "runtime_contracts",
            "shared_capabilities",
            "domains",
        )
        expected_policy_ids = (
            "law-go-kr-drf-api",
            "kosis-statistics-api",
            "data-go-kr-order-plan-api",
            "data-go-kr-village-forecast-api",
            "gov-kr-web",
            "kipris-web",
            "kipo-web",
        )
        expected_contract_ids = (
            "kgov/public-document-hwpx/v1",
            "kgov/korean-law-bill-research/v1",
            "kgov/kosis-official-statistics/v1",
            "kgov/public-procurement-research/v1",
            "kgov/disaster-geospatial-brief/v1",
            "kgov/welfare-health-safety-research/v1",
            "kgov/land-housing-geospatial-research/v1",
            "kgov/official-source-research/v1",
            "kgov/civil-complaint-triage-draft/v1",
            "kgov/administrative-document-draft-review/v1",
            "kgov/public-policy-evidence-pack/v1",
            "kgov/korean-legal-citation-verification/v1",
            "kgov/public-ai-governance-review/v1",
            "kgov/public-it-project-procedure-review/v1",
            "kgov/public-record-disclosure-redaction-review/v1",
            "kgov/local-ordinance-draft-review/v1",
            "kgov/construction-standard-bim-compliance-precheck/v1",
            "kgov/building-permit-document-precheck/v1",
            "kgov/official-notice-multilingual-translation-review/v1",
            "kgov/patent-prior-art-evidence-pack/v1",
            "kgov/public-records-lifecycle-review/v1",
            "kgov/regulated-trade-procedure-precheck/v1",
        )
        expected_operation_ids = (
            "kgov/public-document-hwpx/inspect-document/v1",
            "kgov/korean-law-bill-research/search-laws/v1",
            "kgov/kosis-official-statistics/query-statistics/v1",
            "kgov/public-procurement-research/query-order-plans/v1",
            "kgov/disaster-geospatial-brief/query-village-forecast/v1",
            "kgov/welfare-health-safety-research/blocked-dataset-query/v1",
            "kgov/land-housing-geospatial-research/blocked-dataset-query/v1",
            "kgov/official-source-research/inspect-page/v1",
            "kgov/civil-complaint-triage-draft/admit-draft/v1",
            "kgov/administrative-document-draft-review/review-draft/v1",
            "kgov/public-policy-evidence-pack/build-pack/v1",
            "kgov/korean-legal-citation-verification/verify-citations/v1",
            "kgov/public-ai-governance-review/review-case/v1",
            "kgov/public-it-project-procedure-review/review-case/v1",
            "kgov/public-record-disclosure-redaction-review/review-case/v1",
            "kgov/local-ordinance-draft-review/review-case/v1",
            "kgov/construction-standard-bim-compliance-precheck/review-case/v1",
            "kgov/building-permit-document-precheck/review-case/v1",
            "kgov/official-notice-multilingual-translation-review/review-case/v1",
            "kgov/patent-prior-art-evidence-pack/review-case/v1",
            "kgov/patent-prior-art-evidence-pack/inspect-source/v1",
            "kgov/public-records-lifecycle-review/review-case/v1",
            "kgov/regulated-trade-procedure-precheck/review-case/v1",
        )

        expected_policy_manifest = SourcePolicyV6Test.candidate()["source_policies"]
        operations = [
            operation
            for contract in candidate["runtime_contracts"]
            for operation in contract["operations"]
        ]

        self.assertEqual(expected_root_keys, tuple(candidate))
        self.assertEqual(expected_policy_ids, tuple(policy["id"] for policy in candidate["source_policies"]))
        self.assertEqual(expected_policy_manifest, candidate["source_policies"])
        self.assertEqual(expected_contract_ids, tuple(contract["id"] for contract in candidate["runtime_contracts"]))
        self.assertEqual(22, sum(operation["schema_status"] == "active" for operation in operations))
        self.assertEqual(1, sum(operation["schema_status"] == "declared" for operation in operations))
        self.assertEqual(
            expected_operation_ids,
            tuple(operation["id"] for operation in operations),
        )

    def test_capability_policy_and_contract_links_are_exact(self) -> None:
        candidate = self.v6_candidate()
        expected_nonempty_policies = {
            "korean-law-bill-research": ["law-go-kr-drf-api"],
            "kosis-official-statistics": ["kosis-statistics-api"],
            "public-procurement-research": ["data-go-kr-order-plan-api"],
            "disaster-geospatial-brief": ["data-go-kr-village-forecast-api"],
            "official-source-research": ["gov-kr-web"],
            "korean-legal-citation-verification": ["law-go-kr-drf-api"],
            "patent-prior-art-evidence-pack": ["kipris-web", "kipo-web"],
        }
        actual_nonempty_policies = {
            capability["slug"]: capability["source_policy_ids"]
            for capability in candidate["shared_capabilities"]
            if capability["source_policy_ids"]
        }
        expected_links = {
            capability: f"kgov/{capability}/v1"
            for capability in (
                "public-document-hwpx",
                "korean-law-bill-research",
                "kosis-official-statistics",
                "public-procurement-research",
                "disaster-geospatial-brief",
                "welfare-health-safety-research",
                "land-housing-geospatial-research",
                "official-source-research",
                "civil-complaint-triage-draft",
                "administrative-document-draft-review",
                "public-policy-evidence-pack",
                "korean-legal-citation-verification",
                "public-ai-governance-review",
                "public-it-project-procedure-review",
                "public-record-disclosure-redaction-review",
                "local-ordinance-draft-review",
                "construction-standard-bim-compliance-precheck",
                "building-permit-document-precheck",
                "official-notice-multilingual-translation-review",
                "patent-prior-art-evidence-pack",
                "public-records-lifecycle-review",
                "regulated-trade-procedure-precheck",
            )
        }
        actual_links = {
            capability["slug"]: capability["runtime_contract_id"]
            for capability in candidate["shared_capabilities"]
        }

        self.assertEqual(expected_nonempty_policies, actual_nonempty_policies)
        self.assertEqual(15, sum(not capability["source_policy_ids"] for capability in candidate["shared_capabilities"]))
        self.assertEqual(expected_links, actual_links)

    def test_live_operations_are_active_with_schemas_and_skills_are_bound(self) -> None:
        candidate = self.v6_candidate()
        operations = [
            operation
            for contract in candidate["runtime_contracts"]
            for operation in contract["operations"]
        ]
        bindings = [
            skill["runtime_binding"]
            for domain in candidate["domains"]
            for skill in domain["skills"]
            if "runtime_binding" in skill
        ]

        self.assertEqual(23, len(operations))
        self.assertEqual(22, sum(operation["schema_status"] == "active" for operation in operations))
        self.assertEqual(22, sum("input_schema" in operation and "output_schema" in operation for operation in operations))
        secondary = candidate["runtime_contracts"][19]["operations"][1]
        self.assertEqual("declared", secondary["schema_status"])
        self.assertNotIn("input_schema", secondary)
        self.assertNotIn("output_schema", secondary)
        self.assertEqual(308, len(bindings))
        contracts = {item["capability_slug"]: item for item in candidate["runtime_contracts"]}
        for domain in candidate["domains"]:
            for skill in domain["skills"]:
                contract = contracts[skill["capability"]]
                self.assertEqual(
                    {"contract_id": contract["id"], "operation": contract["default_operation_id"],
                     "fixed_input": {"argv": ["--fixture"]}},
                    skill["runtime_binding"],
                )

    def test_binding_is_required_when_a_skill_omits_it(self) -> None:
        # Given a catalog Skill without its required runtime binding.
        candidate = self.v6_candidate()
        candidate["domains"][0]["skills"][0].pop("runtime_binding", None)
        # When the catalog boundary parses the Skill.
        errors = self.validate_candidate(candidate)
        # Then omission fails before artifact checks.
        self.assertEqual(['V6_REQUIRED_FIELD "/domains/0/skills/0/runtime_binding"'], errors)

    def test_fixture_binding_fails_closed_when_its_fixed_input_changes(self) -> None:
        for fixed_input, suffix, code in (
            ({}, "/argv", "V6_REQUIRED_FIELD"),
            ({"argv": []}, "/argv", "V6_INVALID_VALUE"),
            ({"argv": ["--live"]}, "/argv", "V6_INVALID_VALUE"),
            ({"argv": [1]}, "/argv/0", "V6_INVALID_TYPE"),
            ({"argv": ["--fixture"], "url": "SECRET"}, "/url", "V6_INVALID_VALUE"),
        ):
            with self.subTest(fixed_input=fixed_input):
                # Given a changed shipped binding, not a generic partial preset.
                candidate = self.v6_candidate()
                candidate["domains"][0]["skills"][0]["runtime_binding"]["fixed_input"] = fixed_input
                errors: list[str] = []
                # When the catalog registry validates the binding against fixture_argv.
                validate_catalog._validate_v6_registries(candidate, date(2026, 9, 5), errors)
                # Then the precise field is rejected without echoing values.
                self.assertEqual(
                    [f'{code} "/domains/0/skills/0/runtime_binding/fixed_input{suffix}"'], errors,
                )
                self.assertNotIn("SECRET", "\n".join(errors))

    def test_capability_mutation_fails_at_binding_when_skill_identity_is_unchanged(self) -> None:
        # Given a shipped Skill whose capability no longer owns its bound contract.
        candidate = self.v6_candidate()
        candidate["domains"][0]["skills"][0]["capability"] = "official-source-research"
        # When the catalog boundary resolves its binding.
        errors = self.validate_candidate(candidate)
        # Then rejection precedes generated artifact validation.
        self.assertEqual(
            ['V6_BINDING_MISMATCH "/domains/0/skills/0/runtime_binding/contract_id"'], errors,
        )

    def test_catalog_schemas_are_closed_when_fixture_defaults_are_active(self) -> None:
        # Given the shipped catalog independently of generated artifacts.
        candidate = self.v6_candidate()
        errors: list[str] = []
        # When registries and the approved executable manifest are checked.
        validate_catalog._validate_v6_registries(candidate, date(2026, 9, 5), errors)
        validate_catalog._validate_approved_runtime_manifest(candidate, errors)
        # Then all nested schemas and 308 bindings validate.
        self.assertEqual([], errors)

    def test_blocked_operations_cannot_project_records_when_activated(self) -> None:
        for index in (5, 6):
            with self.subTest(index=index):
                # Given a blocked default whose source mode is illegally widened.
                candidate = self.v6_candidate()
                candidate["runtime_contracts"][index]["operations"][0]["source_output_mode"] = "projected-records"
                # When runtime policy semantics are checked.
                errors = RuntimeContractV6Test.validate_contracts(candidate)
                # Then fixture activation does not authorize source projection.
                self.assertEqual(
                    [f'V6_CONTRACT_INVARIANT "/runtime_contracts/{index}/operations/0/source_policy_ids"'], errors,
                )

    def test_live_evidence_is_downgraded_when_no_fresh_smoke_exists(self) -> None:
        # Given the two capabilities whose historical smoke predates source policies.
        candidate = self.v6_candidate()
        # When their machine-consumed evidence states are selected.
        states = {(item["execution_status"], item["live_smoke"])
                  for item in candidate["shared_capabilities"]
                  if item["slug"] in {"official-source-research", "korean-legal-citation-verification"}}
        # Then synthetic evidence makes no live claim.
        self.assertEqual({("fixture-verified", "blocked")}, states)

    def test_v6_phase_mutations_return_complete_exact_vectors(self) -> None:
        version = self.v6_candidate()
        original_version = version["schema_version"]
        version["schema_version"] = 5
        self.assertNotEqual(original_version, version["schema_version"])
        self.assertEqual(
            ['V6_UNSUPPORTED_SCHEMA_VERSION "/schema_version"'],
            self.validate_candidate(version),
        )

        missing_policy = self.v6_candidate()
        removed = missing_policy.pop("source_policies")
        self.assertNotEqual(removed, missing_policy.get("source_policies"))
        self.assertEqual(
            ['V6_REQUIRED_FIELD "/source_policies"'],
            self.validate_candidate(missing_policy),
        )

        duplicate_operation = self.v6_candidate()
        operation = duplicate_operation["runtime_contracts"][19]["operations"][1]
        original_id = operation["id"]
        operation["id"] = duplicate_operation["runtime_contracts"][19]["operations"][0]["id"]
        self.assertNotEqual(original_id, operation["id"])
        self.assertEqual(
            ['V6_DUPLICATE_ID "/runtime_contracts/19/operations/1/id"'],
            self.validate_candidate(duplicate_operation),
        )

    def test_nested_schema_stale_policy_and_unknown_binding_fail_closed(self) -> None:
        unsupported = self.v6_candidate()
        operation = unsupported["runtime_contracts"][0]["operations"][0]
        original_operation = copy.deepcopy(operation)
        operation["schema_status"] = "active"
        operation["input_schema"] = {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string", "pattern": "SECRET"}},
            "additionalProperties": False,
        }
        operation["output_schema"] = {"type": "null"}
        self.assertNotEqual(original_operation, operation)
        self.assertEqual(
            ['V6_UNSUPPORTED_SCHEMA_KEYWORD "/runtime_contracts/0/operations/0/input_schema/properties/query/pattern"'],
            self.validate_candidate(unsupported),
        )

        stale = self.v6_candidate()
        policy = stale["source_policies"][0]
        original_policy = copy.deepcopy(policy)
        policy["enabled"] = True
        policy["review"] = {
            "reviewed_on": "2026-09-01",
            "expires_on": "2026-09-04",
            "evidence_urls": ["https://www.law.go.kr/review?credential=SECRET"],
        }
        policy["robots"] = {"status": "required"}
        policy["terms"] = {"status": "allowed", "url": "https://www.law.go.kr/terms"}
        policy["rate_limit"] = {"status": "reviewed", "requests": 1, "per_seconds": 1, "burst": 1, "max_wait_seconds": 0}
        policy["response"] = {"status": "reviewed", "max_bytes": 1, "media_types": ["application/json"]}
        policy["license"] = {"status": "reviewed", "url": "https://www.law.go.kr/license", "allowed_output_modes": ["link-only"], "redistribution": "link-only"}
        self.assertNotEqual(original_policy, policy)
        stale_errors = self.validate_candidate(stale)
        self.assertEqual(
            [
                'V6_POLICY_NOT_ENABLEABLE "/source_policies/0/enabled"',
                'V6_POLICY_STALE "/source_policies/0/review/expires_on"',
            ],
            stale_errors,
        )
        rendered_errors = "\n".join(stale_errors)
        self.assertEqual(-1, rendered_errors.find("SECRET"))
        self.assertEqual(-1, rendered_errors.find("credential"))

        unknown_binding = self.v6_candidate()
        skill = unknown_binding["domains"][0]["skills"][0]
        original_skill = copy.deepcopy(skill)
        skill["runtime_binding"] = {
            "contract_id": "kgov/public-document-hwpx/v1",
            "operation": "kgov/public-document-hwpx/unknown/v1",
            "fixed_input": {},
        }
        self.assertNotEqual(original_skill, skill)
        self.assertEqual(
            ['V6_UNKNOWN_REFERENCE "/domains/0/skills/0/runtime_binding/operation"'],
            self.validate_candidate(unknown_binding),
        )

    def test_policy_paths_reject_every_ascii_control_character(self) -> None:
        for codepoint in (*range(0x20), 0x7F):
            with self.subTest(codepoint=codepoint):
                candidate = self.v6_candidate()
                candidate["source_policies"][0]["scope"]["path_rules"][0]["path"] = (
                    f"/safe{chr(codepoint)}suffix"
                )
                self.assertEqual(
                    ['V6_INVALID_FORMAT "/source_policies/0/scope/path_rules/0/path"'],
                    self.validate_candidate(candidate),
                )

    def test_valid_format_semantic_mutations_return_exact_legacy_phase_diagnostics(self) -> None:
        marker = "SECRET_QUERY_CREDENTIAL"
        cases = (
            (
                lambda candidate: candidate["domains"][0]["skills"][0].__setitem__("title", marker),
                [
                    'V6_CONTRACT_INVARIANT "/domains"',
                    'V6_CONTRACT_INVARIANT "/domains/0/skills/0"',
                ],
            ),
            (
                lambda candidate: candidate["domains"][0]["skills"][0]["reference_skills"].__setitem__(
                    0, "valid-attacker-reference",
                ),
                [
                    'V6_CONTRACT_INVARIANT "/domains"',
                    'V6_CONTRACT_INVARIANT "/domains/0/skills/0"',
                ],
            ),
            (
                lambda candidate: candidate["domains"][0]["skills"][5]["task_checks"].__setitem__(
                    0, marker,
                ),
                ['V6_CONTRACT_INVARIANT "/domains/0/skills/5"'],
            ),
            (
                lambda candidate: candidate["domains"][0].__setitem__("evidence", "adjacent"),
                ['V6_CONTRACT_INVARIANT "/domains"'],
            ),
            (
                lambda candidate: candidate.__setitem__("target_skills_per_domain", 4),
                ['V6_INVALID_VALUE "/target_skills_per_domain"'],
            ),
            (
                lambda candidate: candidate["shared_capabilities"][0].__setitem__(
                    "service", marker,
                ),
                ['V6_CONTRACT_INVARIANT "/shared_capabilities/0/service"'],
            ),
            (
                lambda candidate: candidate["shared_capabilities"][0].__setitem__(
                    "source_provenance", ["https://example.go.kr/"],
                ),
                ['V6_CONTRACT_INVARIANT "/shared_capabilities/0/source_provenance"'],
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                candidate = self.v6_candidate()
                mutate(candidate)
                errors = self.validate_candidate(candidate)
                self.assertEqual(expected, errors)
                self.assertEqual(-1, "\n".join(errors).find(marker))

    def test_valid_semantic_order_enum_and_skill_field_mutations_are_exact(self) -> None:
        cases = (
            (
                lambda candidate: candidate["domains"].__setitem__(
                    slice(0, 2), [candidate["domains"][1], candidate["domains"][0]],
                ),
                ['V6_CONTRACT_INVARIANT "/domains"'],
            ),
            (
                lambda candidate: candidate["domains"][0]["skills"].__setitem__(
                    slice(0, 2),
                    [candidate["domains"][0]["skills"][1], candidate["domains"][0]["skills"][0]],
                ),
                ['V6_CONTRACT_INVARIANT "/domains"'],
            ),
            (
                lambda candidate: candidate["domains"][0].__setitem__("group", "법무·치안"),
                ['V6_CONTRACT_INVARIANT "/domains"'],
            ),
            (
                lambda candidate: candidate["domains"][0]["skills"][0].__setitem__(
                    "capability", "official-source-research",
                ),
                ['V6_BINDING_MISMATCH "/domains/0/skills/0/runtime_binding/contract_id"'],
            ),
            (
                lambda candidate: candidate["domains"][0]["skills"][0].__setitem__(
                    "boundary", "manual-review-only",
                ),
                [
                    'V6_CONTRACT_INVARIANT "/domains"',
                    'V6_CONTRACT_INVARIANT "/domains/0/skills/0"',
                ],
            ),
        )
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                candidate = self.v6_candidate()
                mutate(candidate)
                self.assertEqual(expected, self.validate_candidate(candidate))

    def test_empty_repository_returns_exact_coded_artifact_vector(self) -> None:
        expected = [
            'V6_CONTRACT_INVARIANT "/domains"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/0"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/1"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/10"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/11"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/12"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/13"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/14"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/15"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/16"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/17"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/18"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/19"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/2"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/20"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/21"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/3"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/4"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/5"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/6"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/7"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/8"',
            'V6_CONTRACT_INVARIANT "/shared_capabilities/9"',
        ]
        with tempfile.TemporaryDirectory() as temp:
            errors = validate(self.data, Path(temp), on_date=date(2026, 9, 5))
        self.assertEqual(expected, errors)

    def test_artifact_renderer_and_instruction_failures_are_exact_and_non_leaking(self) -> None:
        marker = "SECRET_QUERY_CREDENTIAL"
        cases = (
            (
                "skill",
                lambda root: (
                    root / "domains/행정/skills/government-document-hwpx-review/SKILL.md"
                ).write_text(marker, encoding="utf-8"),
                [
                    'V6_CONTRACT_INVARIANT "/domains/0/skills/0"',
                    'V6_INVALID_FORMAT "/domains/0/skills/0/name"',
                    'V6_REQUIRED_FIELD "/domains/0/skills/0/title"',
                ],
            ),
            (
                "generated-skill-invalid-utf8",
                lambda root: (
                    root / "domains/행정/skills/government-document-hwpx-review/SKILL.md"
                ).write_bytes(b"\xff"),
                ['V6_CONTRACT_INVARIANT "/domains/0/skills/0"'],
            ),
            (
                "generated-catalog",
                lambda root: (root / "docs/domain-skill-candidates.md").write_text(
                    marker, encoding="utf-8",
                ),
                ['V6_CONTRACT_INVARIANT "/domains"'],
            ),
            (
                "generated-catalog-invalid-utf8",
                lambda root: (root / "docs/domain-skill-candidates.md").write_bytes(b"\xff"),
                ['V6_CONTRACT_INVARIANT "/domains"'],
            ),
            (
                "capability-artifact",
                lambda root: (root / "kgov_runtime/capabilities/public_document_hwpx.py").unlink(),
                ['V6_CONTRACT_INVARIANT "/shared_capabilities/0"'],
            ),
            (
                "instruction",
                lambda root: (root / "CLAUDE.md").write_text(marker, encoding="utf-8"),
                ['V6_CONTRACT_INVARIANT ""'],
            ),
            (
                "instruction-invalid-utf8",
                lambda root: (root / "CLAUDE.md").write_bytes(b"\xff"),
                ['V6_CONTRACT_INVARIANT ""'],
            ),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                temp = tempfile.TemporaryDirectory()
                self.addCleanup(temp.cleanup)
                root = Path(temp.name) / "repo"
                copy_repository_inputs(root)
                mutate(root)
                errors = validate(self.data, root, on_date=date(2026, 9, 5))
                self.assertEqual(expected, errors)
                self.assertEqual(-1, "\n".join(errors).find(marker))

    def test_generated_skill_entrypoint_must_be_a_regular_file(self) -> None:
        def replace_with_directory(path: Path, root: Path) -> None:
            del root
            path.unlink()
            path.mkdir()

        def replace_with_symlink(path: Path, root: Path) -> None:
            preserved = root / "preserved-skill-entrypoint"
            preserved.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(preserved)

        def replace_with_fifo(path: Path, root: Path) -> None:
            del root
            path.unlink()
            os.mkfifo(path)

        cases = (
            ("directory", replace_with_directory),
            ("symlink", replace_with_symlink),
            ("fifo", replace_with_fifo),
        )
        relative = Path("domains/행정/skills/government-document-hwpx-review/SKILL.md")
        expected = ['V6_CONTRACT_INVARIANT "/domains/0/skills/0"']
        for name, mutate in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp) / "repo"
                    copy_repository_inputs(root)
                    path = root / relative
                    self.assertTrue(path.is_file())
                    self.assertFalse(path.is_symlink())
                    mutate(path, root)
                    self.assertTrue(path.exists())
                    self.assertTrue(path.is_dir() or path.is_symlink() or not path.is_file())
                    self.assertEqual(
                        expected,
                        validate(self.data, root, on_date=date(2026, 9, 5)),
                    )

    def test_broad_legacy_phase_corpus_is_coded_sorted_and_non_leaking(self) -> None:
        marker = "SECRET_QUERY_CREDENTIAL"
        candidates = []
        for domain_index in (0, 1, 20, 59):
            for skill_index in (0, len(self.data["domains"][domain_index]["skills"]) - 1):
                for field, value in (
                    ("title", marker),
                    ("reference_skills", ["valid-attacker-reference"]),
                    ("boundary", "manual-review-only"),
                ):
                    candidate = self.v6_candidate()
                    candidate["domains"][domain_index]["skills"][skill_index][field] = value
                    candidates.append(candidate)
        for candidate in candidates:
            errors = self.validate_candidate(candidate)
            self.assertNotEqual([], errors)
            self.assertEqual(
                errors,
                sorted(
                    errors,
                    key=lambda error: (
                        json.loads(error.partition(" ")[2]).encode("utf-8"),
                        error.partition(" ")[0],
                    ),
                ),
            )
            for error in errors:
                code, separator, pointer_json = error.partition(" ")
                self.assertEqual(" ", separator)
                self.assertEqual(True, code in {
                    "V6_INVALID_VALUE", "V6_INVALID_FORMAT", "V6_INVALID_TYPE",
                    "V6_UNKNOWN_REFERENCE", "V6_CONTRACT_INVARIANT",
                    "V6_BINDING_MISMATCH", "V6_OPERATION_NOT_ACTIVE",
                })
                pointer = json.loads(pointer_json)
                self.assertIsInstance(pointer, str)
                self.assertEqual(True, pointer == "" or pointer[:1] == "/")
                self.assertEqual(json.dumps(pointer, ensure_ascii=False), pointer_json)
            rendered = "\n".join(errors)
            self.assertEqual(-1, rendered.find(marker))
            self.assertEqual(-1, rendered.find("SKILL.md"))
            self.assertEqual(-1, rendered.find(str(ROOT)))

    def test_cli_reports_exact_schema_v6_inventory(self) -> None:
        self.assertEqual(6, self.data.get("schema_version"))
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_catalog.py")],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual(
            "PASS schema=6 domains=60 domain_skills=308 capabilities=22 source_policies=7 "
            "runtime_contracts=22 operations=23 active_operations=22 bindings=308 top_level_skills=0 "
            "direct=35 adjacent=16 new=8 sensitive=1\n",
            result.stdout,
        )
        self.assertEqual("", result.stderr)


class ActiveCatalogOutputTest(unittest.TestCase):
    def test_real_fixture_outputs_match_catalog_schemas_when_defaults_execute(self) -> None:
        from kgov_runtime.contracts import load_contracts

        # Given the real catalog parser and fixture-backed capability CLIs.
        for contract in load_contracts():
            with self.subTest(capability=contract.capability_slug):
                operation = contract.operations[0]
                # When the executable fixture operation runs through its real surface.
                result = subprocess.run(
                    [sys.executable, "-m", "scripts.offline_fixture", contract.module, *operation.fixture_argv],
                    cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
                )
                # Then the actual output satisfies the catalog-owned closed schema.
                self.assertEqual(0, result.returncode, result.stderr)
                contract.validate_output(operation.id, json.loads(result.stdout))

    def test_nested_output_keys_are_rejected_when_not_in_the_catalog_schema(self) -> None:
        from kgov_runtime.contracts import ContractError, load_contracts

        # Given a real nested HWPX output with an undeclared metadata field.
        contract = load_contracts()[0]
        operation = contract.operations[0]
        result = subprocess.run(
            [sys.executable, "-m", "scripts.offline_fixture", contract.module, "--fixture"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
        )
        for key, code in (("unexpected", "schema-additional-property"), ("raw", "forbidden-output-key")):
            with self.subTest(key=key):
                output = json.loads(result.stdout)
                output["section_metadata"]["included"][0][key] = "SECRET"
                # When the actual runtime parser validates the mutated response.
                with self.assertRaises(ContractError) as caught:
                    contract.validate_output(operation.id, output)
                # Then nested extensions and sensitive fields both fail closed.
                self.assertEqual(code, caught.exception.code)
                self.assertNotIn("SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
