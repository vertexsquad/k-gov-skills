from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast


class ReviewAdmissionContractMixin:
    adapter: Any
    valid: dict[str, Any]
    adapter_path: Path

    def test_admits_fixture_without_echoing_content(self) -> None:
        testcase = cast(unittest.TestCase, self)
        result = self.adapter.review_case(self.valid)
        serialized = json.dumps(result, ensure_ascii=False)
        testcase.assertTrue(result["accepted"])
        testcase.assertTrue(result["manual_review_required"])
        testcase.assertEqual("admitted-pending-human-review", result["status"])
        testcase.assertEqual(3, len(result["required_checks"]))
        testcase.assertEqual(
            {
                "accepted",
                "basic_identifier_scan",
                "fact_count",
                "manual_review_required",
                "permitted_output",
                "prohibited_decisions",
                "receipt_assurance",
                "required_checks",
                "review_type",
                "source_ref_count",
                "status",
            },
            set(result),
        )
        for value in [
            self.valid["case_id"],
            self.valid["summary"],
            *self.valid["facts"],
            self.valid["source_refs"][0]["url"],
        ]:
            testcase.assertNotIn(value, serialized)

    def test_rejects_unknown_unredacted_and_identifier_input(self) -> None:
        testcase = cast(unittest.TestCase, self)
        with testcase.assertRaisesRegex(ValueError, "unknown fields"):
            self.adapter.review_case(dict(self.valid, attachment="internal.hwpx"))
        with testcase.assertRaisesRegex(ValueError, "redacted input is required"):
            self.adapter.review_case(dict(self.valid, redaction_status="unknown"))
        with testcase.assertRaisesRegex(ValueError, "personal identifier"):
            self.adapter.review_case(dict(self.valid, summary="연락처 user@example.org"))
        with testcase.assertRaisesRegex(ValueError, "case_id must use"):
            self.adapter.review_case(dict(self.valid, case_id="lowercase-id"))

    def test_rejects_unsupported_type_host_and_future_receipt(self) -> None:
        testcase = cast(unittest.TestCase, self)
        with testcase.assertRaisesRegex(ValueError, "review_type is unsupported"):
            self.adapter.review_case(dict(self.valid, review_type="automatic-approval"))
        with testcase.assertRaisesRegex(ValueError, "allowlisted"):
            self.adapter.review_case(
                dict(self.valid, source_refs=[{"url": "https://example.org/", "retrieved_on": "2026-07-25"}])
            )
        with testcase.assertRaisesRegex(ValueError, "allowlisted"):
            self.adapter.review_case(
                dict(
                    self.valid,
                    source_refs=[
                        {
                            "url": self.valid["source_refs"][0]["url"] + "?serviceKey=secret",
                            "retrieved_on": "2026-07-25",
                        }
                    ],
                )
            )
        with testcase.assertRaisesRegex(ValueError, "cannot be after"):
            self.adapter.review_case(
                dict(self.valid, source_refs=[dict(self.valid["source_refs"][0], retrieved_on="2026-07-26")])
            )

    def test_accepts_every_declared_review_type(self) -> None:
        testcase = cast(unittest.TestCase, self)
        for review_type in self.adapter.CONTRACT.review_types:
            with testcase.subTest(review_type=review_type):
                result = self.adapter.review_case(dict(self.valid, review_type=review_type))
                testcase.assertEqual(review_type, result["review_type"])

    def test_fixture_cli_is_deterministic(self) -> None:
        testcase = cast(unittest.TestCase, self)
        command = [sys.executable, str(self.adapter_path), "--fixture"]
        first = subprocess.run(command, check=True, capture_output=True, text=True)
        second = subprocess.run(command, check=True, capture_output=True, text=True)
        testcase.assertEqual(first.stdout, second.stdout)
        testcase.assertTrue(json.loads(first.stdout)["accepted"])

    def test_cli_file_errors_do_not_echo_sensitive_path_or_content(self) -> None:
        testcase = cast(unittest.TestCase, self)
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "user@example.org.json"
            missing_result = subprocess.run(
                [sys.executable, str(self.adapter_path), str(missing)],
                check=False,
                capture_output=True,
                text=True,
            )
            testcase.assertEqual(2, missing_result.returncode)
            testcase.assertNotIn("user@example.org", missing_result.stderr)

            invalid = Path(temporary_directory) / "invalid.json"
            invalid.write_text('{"summary":"user@example.org"', encoding="utf-8")
            invalid_result = subprocess.run(
                [sys.executable, str(self.adapter_path), str(invalid)],
                check=False,
                capture_output=True,
                text=True,
            )
            testcase.assertEqual(2, invalid_result.returncode)
            testcase.assertNotIn("user@example.org", invalid_result.stderr)
