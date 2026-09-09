from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import kgov_runtime.capabilities.civil_complaint_triage_draft as adapter


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "kgov_runtime" / "capabilities" / "civil_complaint_triage_draft.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "capabilities" / "civil-complaint-triage-draft.json"


class AdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = adapter
        self.valid = {
            "title": "공원 시설 이용 문의",
            "body": "공원 운동기구 이용 가능 시간을 알려 주세요.",
            "channel": "국민신문고",
            "received_at": "2026-07-15T09:00:00+09:00",
            "redaction_status": "redacted",
        }

    def test_admits_redacted_synthetic_request_without_echoing_text(self) -> None:
        result = self.adapter.admit_request(self.valid)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["manual_review_required"])
        self.assertEqual("draft-only", result["permitted_output"])
        self.assertNotIn(self.valid["title"], serialized)
        self.assertNotIn(self.valid["body"], serialized)

    def test_rejects_unredacted_or_unknown_redaction_state(self) -> None:
        for status in ("contains-personal-data", "unknown"):
            changed = dict(self.valid, redaction_status=status)
            with self.subTest(status=status):
                with self.assertRaisesRegex(ValueError, "redacted input is required"):
                    self.adapter.admit_request(changed)

    def test_rejects_common_direct_identifier_even_with_attestation(self) -> None:
        changed = dict(self.valid, body="연락처는 010-1234-5678입니다.")
        with self.assertRaisesRegex(ValueError, "potential personal identifier"):
            self.adapter.admit_request(changed)

    def test_rejects_unknown_fields_and_oversized_body(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.adapter.admit_request(dict(self.valid, attachment="secret.pdf"))
        with self.assertRaisesRegex(ValueError, "body exceeds"):
            self.adapter.admit_request(dict(self.valid, body="가" * 20_001))

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
        self.assertNotRegex(fixture["body"], r"01[016789]-?\d{3,4}-?\d{4}")


if __name__ == "__main__":
    unittest.main()