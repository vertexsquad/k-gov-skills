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
        self.assertEqual(132, len(entrypoints))
        self.assertEqual(132, len({path.parent.name for path in entrypoints}))
        self.assertFalse(list(ROOT.glob("domains/*/.gitkeep")))

    def test_evidence_distribution_matches_review(self) -> None:
        counts = Counter(item["evidence"] for item in self.data["domains"])
        self.assertEqual({"direct": 35, "adjacent": 16, "new": 8, "sensitive": 1}, dict(counts))

    def test_capability_runtime_manifest_is_complete(self) -> None:
        self.assertEqual(4, self.data["schema_version"])
        capabilities = self.data["shared_capabilities"]
        self.assertEqual(21, len(capabilities))
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
        self.assertEqual(132, len(names))
        self.assertEqual(len(names), len(set(names)))

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
                self.assertEqual(3, len(domain["skills"]))
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
                self.assertIn(
                    f"{domain_name}: requires at least 3 Skills in minimum-three rollout, got 2",
                    errors,
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
                self.assertIn(
                    f"{domain_name}/{skill_name}: wave-one task_checks contract mismatch",
                    errors,
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
                self.assertEqual(3, len(domain["skills"]))
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
                self.assertIn(
                    f"{domain_name}: requires at least 3 Skills in minimum-three rollout, got 2",
                    errors,
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
                    self.assertIn(f"{domain_name}/{skill_name}: wave-two contract mismatch", errors)

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
                self.assertIn(
                    "public-records-lifecycle-review: wave-two capability contract mismatch",
                    errors,
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
                self.assertEqual(3, len(domain["skills"]))
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
                        self.assertIn(f"{domain_name}/{skill_name}: wave-three contract mismatch", errors)

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
                    self.assertIn(
                        f"{domain_name}: requires at least 3 Skills in minimum-three rollout, got 2",
                        errors,
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
                self.assertEqual(3, len(domain["skills"]))
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
                        self.assertIn(f"{domain_name}/{skill_name}: wave-four contract mismatch", errors)

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
                    self.assertIn(
                        f"{domain_name}: requires at least 3 Skills in minimum-three rollout, got 2",
                        errors,
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
                self.assertEqual(3, len(domain["skills"]))
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
                        self.assertIn(f"{domain_name}/{skill_name}: wave-five contract mismatch", errors)

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
                    self.assertIn(
                        f"{domain_name}: requires at least 3 Skills in minimum-three rollout, got 2",
                        errors,
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
                        "KIPRIS·특허청 공식 URL·공개일·조회일·공개 또는 등록 상태와 미확인·복수 후보를 보존",
                        "신규성·진보성·침해·유효성·출원전략 판단은 변리사와 특허 담당자 검토로 이관",
                    ),
                ),
                (
                    "ip-policy-statistics-evidence-brief",
                    "지식재산 정책통계 근거 브리프",
                    "public-policy-evidence-pack",
                    (
                        "권리유형·정책 또는 사업·기준기간·출원인 범주·지역·건수·분모·단위를 분리",
                        "공식 자료로 입력된 특허청·KIPRIS URL·보고서 또는 통계표 식별자·공표일·조회일·개정 상태와 결측을 구분",
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
                self.assertEqual(3, len(domain["skills"]))
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
                        self.assertIn(f"{domain_name}/{skill_name}: wave-six contract mismatch", errors)

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
                    self.assertIn(
                        f"{domain_name}: requires at least 3 Skills in minimum-three rollout, got 2",
                        errors,
                    )
        self.assertEqual(66, mutation_count)

    def test_unknown_capability_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][0]["skills"][0]["capability"] = "unknown-capability"
        errors = validate(changed, ROOT)
        self.assertTrue(any("unknown capability unknown-capability" in error for error in errors))

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
        self.assertIn(
            "감사/audit-finding-response-draft-review: read-only boundary is incompatible with draft-only capability",
            errors,
        )

    def test_invalid_skill_container_is_rejected_without_crashing(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["domains"][0]["skills"] = None
        errors = validate(changed, ROOT)
        self.assertTrue(any("skills must be a non-empty list" in error for error in errors))

    def test_non_object_catalog_root_is_rejected_without_crashing(self) -> None:
        for bad in (None, 123, "x", ["domains"]):
            with self.subTest(bad=type(bad).__name__):
                errors = validate(bad, ROOT)  # type: ignore[arg-type]
                self.assertEqual(["catalog root must be a JSON object"], errors)

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
        self.assertIn("domain-owned Skill: **132개**", current)

    def test_generated_domain_skills_match_catalog(self) -> None:
        expected = expected_domain_skills(self.data, ROOT)
        self.assertEqual(132, len(expected))
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
        self.assertIn("CLAUDE.md: missing required anchor 'top-level `skills/`'", errors)

    def test_validator_cli_reports_owned_topology(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_catalog.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("domains=60 domain_skills=132 capabilities=21 top_level_skills=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
