from __future__ import annotations

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
    spec = importlib.util.spec_from_file_location("administrative_document_adapter", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("adapter import spec is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = load_adapter()
        self.valid = {
            "document_type": "report",
            "title": "공원 시설 개선 검토 보고",
            "body": "공원 시설 3곳의 정비 필요성을 검토하고 관련 조례를 확인합니다.",
            "purpose": "담당자 검토용 초안을 작성합니다.",
            "source_refs": ["https://www.suwon.go.kr/"],
            "redaction_status": "redacted",
        }

    def test_admits_redacted_document_without_echoing_input(self) -> None:
        result = self.adapter.review_document(self.valid)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["manual_review_required"])
        self.assertEqual("draft-review-only", result["permitted_output"])
        self.assertEqual("report", result["document_type"])
        self.assertEqual("required", result["review_checks"]["numeric_claims"])
        self.assertEqual("required", result["review_checks"]["legal_authority"])
        for value in (
            self.valid["title"],
            self.valid["body"],
            self.valid["purpose"],
            self.valid["source_refs"][0],
        ):
            self.assertNotIn(value, serialized)

    def test_supports_only_bounded_document_types(self) -> None:
        for document_type in (
            "official-letter",
            "report",
            "meeting-material",
            "press-release",
        ):
            with self.subTest(document_type=document_type):
                result = self.adapter.review_document(
                    dict(self.valid, document_type=document_type)
                )
                self.assertEqual(document_type, result["document_type"])
        with self.assertRaisesRegex(ValueError, "unsupported document_type"):
            self.adapter.review_document(dict(self.valid, document_type="contract"))

    def test_rejects_unredacted_input_and_direct_identifiers(self) -> None:
        with self.assertRaisesRegex(ValueError, "redacted input is required"):
            self.adapter.review_document(
                dict(self.valid, redaction_status="contains-personal-data")
            )
        with self.assertRaisesRegex(ValueError, "potential personal identifier"):
            self.adapter.review_document(
                dict(self.valid, body="담당자 이메일은 user@example.org 입니다.")
            )

    def test_rejects_unknown_fields_and_oversized_body(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.adapter.review_document(dict(self.valid, attachment="internal.hwpx"))
        with self.assertRaisesRegex(ValueError, "body exceeds"):
            self.adapter.review_document(dict(self.valid, body="가" * 30_001))

    def test_rejects_invalid_source_references(self) -> None:
        for source_refs in (
            "https://www.suwon.go.kr/",
            ["http://www.suwon.go.kr/"],
            ["https://user:secret@example.org/"],
            ["https://example.org/?contact=user@example.org"],
            ["not-a-url"],
        ):
            with self.subTest(source_refs=source_refs):
                with self.assertRaisesRegex(ValueError, "source_refs"):
                    self.adapter.review_document(
                        dict(self.valid, source_refs=source_refs)
                    )

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
        self.assertTrue(json.loads(first.stdout)["accepted"])

    def test_fixture_contains_only_synthetic_redacted_input(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual("redacted", fixture["redaction_status"])
        serialized = json.dumps(fixture, ensure_ascii=False)
        self.assertNotRegex(serialized, r"01[016789]-?\d{3,4}-?\d{4}")
        self.assertNotIn("@", serialized)


if __name__ == "__main__":
    unittest.main()
