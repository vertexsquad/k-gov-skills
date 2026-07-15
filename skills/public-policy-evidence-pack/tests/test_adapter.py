from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = SKILL_ROOT / "scripts" / "adapter.py"
FIXTURE_PATH = SKILL_ROOT / "fixtures" / "sample.json"


def load_adapter():
    spec = importlib.util.spec_from_file_location("public_policy_evidence_pack_adapter", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("adapter import spec is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = load_adapter()
        self.valid = {
            "question": "공공시설 개선 검토에 필요한 공식 근거를 정리합니다.",
            "as_of_date": "2026-07-15",
            "jurisdiction": "KR",
            "redaction_status": "redacted",
            "claims": [
                {
                    "claim_id": "C1",
                    "statement": "공개 통계에 시설 이용 증가가 나타납니다.",
                    "evidence": [
                        {
                            "source_url": "https://kosis.kr/openapi/",
                            "source_kind": "official-primary",
                            "retrieved_on": "2026-07-15",
                            "relationship": "supports",
                            "receipt_status": "retrieved",
                        }
                    ],
                },
                {
                    "claim_id": "C2",
                    "statement": "관련 기준의 적용 범위가 서로 다르게 제시됩니다.",
                    "evidence": [
                        {
                            "source_url": "https://www.law.go.kr/",
                            "source_kind": "official-primary",
                            "retrieved_on": "2026-07-15",
                            "relationship": "supports",
                            "receipt_status": "retrieved",
                        },
                        {
                            "source_url": "https://www.gov.kr/",
                            "source_kind": "official-primary",
                            "retrieved_on": "2026-07-15",
                            "relationship": "contradicts",
                            "receipt_status": "retrieved",
                        },
                    ],
                },
                {
                    "claim_id": "C3",
                    "statement": "추가 확인이 필요한 보조 설명입니다.",
                    "evidence": [
                        {
                            "source_url": "https://example.org/context",
                            "source_kind": "official-secondary",
                            "retrieved_on": "2026-07-15",
                            "relationship": "supports",
                            "receipt_status": "retrieved",
                        }
                    ],
                },
            ],
        }

    def test_derives_truth_safe_statuses_without_echoing_content(self) -> None:
        result = self.adapter.build_evidence_pack(self.valid)
        serialized = json.dumps(result, ensure_ascii=False)
        statuses = {item["claim_id"]: item["status"] for item in result["claims"]}
        self.assertEqual(
            {
                "C1": "structurally-supported-pending-human-review",
                "C2": "conflict-detected-pending-human-review",
                "C3": "insufficient-official-evidence",
            },
            statuses,
        )
        self.assertTrue(result["accepted"])
        self.assertTrue(result["manual_review_required"])
        self.assertEqual("evidence-pack-draft-only", result["permitted_output"])
        self.assertEqual("input-declared-not-independently-verified", result["source_kind_assurance"])
        self.assertEqual(3, result["claim_count"])
        for value in (
            self.valid["question"],
            *(claim["statement"] for claim in self.valid["claims"]),
            *(
                evidence["source_url"]
                for claim in self.valid["claims"]
                for evidence in claim["evidence"]
            ),
        ):
            self.assertNotIn(value, serialized)

    def test_secondary_or_not_retrieved_does_not_satisfy_support_gate(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["claims"] = [
            {
                "claim_id": "SECONDARY",
                "statement": "보조 출처만 있는 주장입니다.",
                "evidence": [
                    {
                        "source_url": "https://example.org/context",
                        "source_kind": "official-secondary",
                        "retrieved_on": "2026-07-15",
                        "relationship": "supports",
                        "receipt_status": "retrieved",
                    },
                    {
                        "source_url": "https://www.gov.kr/",
                        "source_kind": "official-primary",
                        "retrieved_on": "2026-07-15",
                        "relationship": "supports",
                        "receipt_status": "not-retrieved",
                    },
                ],
            }
        ]
        result = self.adapter.build_evidence_pack(changed)
        self.assertEqual("insufficient-official-evidence", result["claims"][0]["status"])

    def test_rejects_unknown_missing_fields_and_duplicate_claim_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.adapter.build_evidence_pack(dict(self.valid, output_path="internal.json"))
        missing = dict(self.valid)
        missing.pop("question")
        with self.assertRaisesRegex(ValueError, "missing fields"):
            self.adapter.build_evidence_pack(missing)
        duplicated = copy.deepcopy(self.valid)
        duplicated["claims"][1]["claim_id"] = "C1"
        with self.assertRaisesRegex(ValueError, "duplicate claim_id"):
            self.adapter.build_evidence_pack(duplicated)

    def test_rejects_invalid_dates_enums_and_unredacted_input(self) -> None:
        cases = (
            (dict(self.valid, as_of_date="2026-02-30"), "as_of_date"),
            (dict(self.valid, jurisdiction="US"), "jurisdiction"),
            (dict(self.valid, redaction_status="contains-personal-data"), "redacted input"),
        )
        for payload, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.adapter.build_evidence_pack(payload)
        for field, value in (
            ("source_kind", "blog"),
            ("relationship", "agrees"),
            ("receipt_status", "trusted"),
        ):
            changed = copy.deepcopy(self.valid)
            changed["claims"][0]["evidence"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    self.adapter.build_evidence_pack(changed)

    def test_rejects_identifiers_in_question_statement_and_url(self) -> None:
        payloads = []
        payloads.append(dict(self.valid, question="담당자 user@example.org의 요청입니다."))
        statement = copy.deepcopy(self.valid)
        statement["claims"][0]["statement"] = "담당자 연락처는 010-1234-5678입니다."
        payloads.append(statement)
        url = copy.deepcopy(self.valid)
        url["claims"][0]["evidence"][0]["source_url"] = (
            "https://www.gov.kr/?contact=user@example.org"
        )
        payloads.append(url)
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "direct identifier"):
                    self.adapter.build_evidence_pack(payload)

    def test_rejects_invalid_urls_and_oversized_collections(self) -> None:
        for source_url in (
            "http://www.gov.kr/",
            "https://user:secret@www.gov.kr/",
            "not-a-url",
        ):
            changed = copy.deepcopy(self.valid)
            changed["claims"][0]["evidence"][0]["source_url"] = source_url
            with self.subTest(source_url=source_url):
                with self.assertRaisesRegex(ValueError, "credential-free HTTPS"):
                    self.adapter.build_evidence_pack(changed)
        too_many_claims = copy.deepcopy(self.valid)
        too_many_claims["claims"] = [
            {"claim_id": f"C{index}", "statement": "합성 주장", "evidence": []}
            for index in range(51)
        ]
        with self.assertRaisesRegex(ValueError, "claims"):
            self.adapter.build_evidence_pack(too_many_claims)
        too_many_evidence = copy.deepcopy(self.valid)
        too_many_evidence["claims"][0]["evidence"] = [
            copy.deepcopy(self.valid["claims"][0]["evidence"][0]) for _ in range(21)
        ]
        with self.assertRaisesRegex(ValueError, "evidence"):
            self.adapter.build_evidence_pack(too_many_evidence)

    def test_rejects_output_visible_identifier_and_unknown_key_without_echo(self) -> None:
        identifier = "01012345678"
        changed = copy.deepcopy(self.valid)
        changed["claims"][0]["claim_id"] = f"C{identifier}"
        with self.assertRaisesRegex(ValueError, "claim_id.*direct identifier") as context:
            self.adapter.build_evidence_pack(changed)
        self.assertNotIn(identifier, str(context.exception))

        unknown_key = "user@example.org"
        changed = dict(self.valid)
        changed[unknown_key] = "synthetic"
        with self.assertRaisesRegex(ValueError, "unknown fields") as context:
            self.adapter.build_evidence_pack(changed)
        self.assertNotIn(unknown_key, str(context.exception))

    def test_rejects_receipts_after_pack_as_of_date(self) -> None:
        changed = copy.deepcopy(self.valid)
        changed["claims"][0]["evidence"][0]["retrieved_on"] = "2026-07-16"
        with self.assertRaisesRegex(ValueError, "retrieved_on cannot be after as_of_date"):
            self.adapter.build_evidence_pack(changed)

    def test_fixture_cli_is_deterministic(self) -> None:
        first = subprocess.run(
            [sys.executable, str(ADAPTER_PATH), "--fixture"],
            check=True,
            capture_output=True,
            text=True,
        )
        second = subprocess.run(
            [sys.executable, str(ADAPTER_PATH), "--fixture"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(first.stdout, second.stdout)
        result = json.loads(first.stdout)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["manual_review_required"])

    def test_fixture_contains_only_synthetic_redacted_input(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual("redacted", fixture["redaction_status"])
        serialized = json.dumps(fixture, ensure_ascii=False)
        self.assertNotRegex(serialized, r"01[016789]-?\d{3,4}-?\d{4}")
        self.assertNotIn("@", serialized)


if __name__ == "__main__":
    unittest.main()
