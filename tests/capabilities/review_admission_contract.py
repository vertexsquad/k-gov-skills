from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from kgov_runtime.capabilities import building_permit_document_precheck, patent_prior_art_evidence_pack


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
                "source_assurance_levels",
                "source_output_mode",
                "source_ref_count",
                "status",
                "manual_review_reasons",
            },
            set(result),
        )
        for value in [
            self.valid["case_id"],
            self.valid["summary"],
            *self.valid["facts"],
            self.valid["source_refs"][0]["url"],
            self.valid["source_refs"][0]["institution"],
            self.valid["source_refs"][0]["title"],
            self.valid["source_refs"][0]["attribution"],
        ]:
            testcase.assertNotIn(value, serialized)
        testcase.assertEqual(sorted(result["manual_review_reasons"]), result["manual_review_reasons"])
        testcase.assertEqual(sorted(result["source_assurance_levels"]), result["source_assurance_levels"])

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
                dict(
                    self.valid,
                    source_refs=[dict(self.valid["source_refs"][0], url="https://example.org/")],
                )
            )
        with testcase.assertRaisesRegex(ValueError, "allowlisted"):
            self.adapter.review_case(
                dict(
                    self.valid,
                    source_refs=[
                        dict(
                            self.valid["source_refs"][0],
                            url=self.valid["source_refs"][0]["url"] + "?serviceKey=secret",
                        )
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


class ReviewAdmissionReceiptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.valid = json.loads(patent_prior_art_evidence_pack.FIXTURE.read_text(encoding="utf-8"))

    def test_missing_and_null_receipts_remain_caller_declared(self) -> None:
        missing = deepcopy(self.valid["source_refs"][0])
        del missing["policy_receipt"]
        null = dict(self.valid["source_refs"][0], policy_receipt=None)
        for source_ref in (missing, null):
            with self.subTest(source_ref=source_ref):
                result = patent_prior_art_evidence_pack.review_case(dict(self.valid, source_refs=[source_ref]))
                self.assertEqual(["caller-declared"], result["source_assurance_levels"])
                self.assertEqual("caller-declared-not-live-retrieval-proof", result["receipt_assurance"])
                self.assertIn("caller-declared-source", result["manual_review_reasons"])
                self.assertNotIn("policy-verified-not-authenticity-proof", result["source_assurance_levels"])

    def test_valid_receipt_is_policy_verified_without_authenticity_claim(self) -> None:
        result = patent_prior_art_evidence_pack.review_case(self.valid)
        self.assertEqual(["policy-verified-not-authenticity-proof"], result["source_assurance_levels"])
        self.assertEqual("policy-matched-not-cryptographic-authenticity-proof", result["receipt_assurance"])
        self.assertIn("policy-outcome-manual-review", result["manual_review_reasons"])
        self.assertEqual("link-only", result["source_output_mode"])

    def test_zero_policy_capability_rejects_registry_policy_before_assurance(self) -> None:
        valid = json.loads(building_permit_document_precheck.FIXTURE.read_text(encoding="utf-8"))
        source_ref = dict(
            valid["source_refs"][0],
            url="https://www.law.go.kr/DRF/lawSearch.do",
            policy_receipt={
                "source_url": "https://www.law.go.kr/DRF/lawSearch.do",
                "retrieved_on": "2026-07-25",
                "policy_id": "law-go-kr-drf-api",
                "policy_revision": 1,
                "policy_digest": "b913eca9c1df8f4284c41e94d9216fc7ad20f25bc2fdd5d6f7d107759c47a914",
                "outcome": "manual-review",
            },
        )
        with self.assertRaisesRegex(ValueError, "not declared for capability"):
            building_permit_document_precheck.review_case(dict(valid, source_refs=[source_ref]))

    def test_policy_receipt_rejects_institution_mismatch_without_leaking_value(self) -> None:
        candidate = deepcopy(self.valid)
        supplied = "미공개 외부기관"
        candidate["source_refs"][0]["institution"] = supplied
        with self.assertRaisesRegex(ValueError, "institution") as raised:
            patent_prior_art_evidence_pack.review_case(candidate)
        self.assertNotIn(supplied, str(raised.exception))

    def test_rejects_explicit_nonstandard_https_port(self) -> None:
        candidate = deepcopy(self.valid)
        candidate["source_refs"][0]["url"] = "https://www.kipris.or.kr:444/"
        candidate["source_refs"][0]["policy_receipt"] = None
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            patent_prior_art_evidence_pack.review_case(candidate)

    def test_mixed_receipt_assurance_and_reasons_are_deterministic(self) -> None:
        verified = self.valid["source_refs"][0]
        caller_declared = dict(verified, policy_receipt=None)
        first = patent_prior_art_evidence_pack.review_case(dict(self.valid, source_refs=[verified, caller_declared]))
        second = patent_prior_art_evidence_pack.review_case(dict(self.valid, source_refs=[caller_declared, verified]))
        self.assertEqual(["caller-declared", "policy-verified-not-authenticity-proof"], first["source_assurance_levels"])
        self.assertEqual(
            [
                "caller-declared-source",
                "license-unverified",
                "policy-outcome-manual-review",
                "redistribution-link-only",
            ],
            first["manual_review_reasons"],
        )
        self.assertEqual(first, second)

    def test_rejects_unknown_nested_fields(self) -> None:
        unknown_source = deepcopy(self.valid)
        unknown_source["source_refs"][0]["raw"] = "secret"
        unknown_receipt = deepcopy(self.valid)
        unknown_receipt["source_refs"][0]["policy_receipt"]["credential"] = "secret"
        for candidate in (unknown_source, unknown_receipt):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "unknown fields|missing fields"):
                    patent_prior_art_evidence_pack.review_case(candidate)

    def test_rejects_missing_metadata_identifier_and_credentials_without_leaking_them(self) -> None:
        missing_title = deepcopy(self.valid)
        del missing_title["source_refs"][0]["title"]
        identifier = deepcopy(self.valid)
        identifier["source_refs"][0]["attribution"] = "user@example.org"
        credential = deepcopy(self.valid)
        credential["source_refs"][0]["policy_receipt"] = None
        credential["source_refs"][0]["terms_url"] = "https://user:secret@www.kipris.or.kr/"
        for candidate, sensitive in (
            (missing_title, "합성 선행기술 공개자료"),
            (identifier, "user@example.org"),
            (credential, "secret"),
        ):
            with self.subTest(sensitive=sensitive):
                with self.assertRaises(ValueError) as raised:
                    patent_prior_art_evidence_pack.review_case(candidate)
                self.assertNotIn(sensitive, str(raised.exception))

    def test_rejects_stale_or_mismatched_policy_receipt(self) -> None:
        mutations = (
            ("source_url", "https://www.kipo.go.kr/"),
            ("retrieved_on", "2026-07-24"),
            ("policy_id", "retired-policy"),
            ("policy_revision", 2),
            ("policy_digest", "0" * 64),
            ("outcome", "allowed"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                candidate = deepcopy(self.valid)
                candidate["source_refs"][0]["policy_receipt"][field] = value
                with self.assertRaisesRegex(ValueError, "policy_receipt"):
                    patent_prior_art_evidence_pack.review_case(candidate)

    def test_rejects_inconsistent_dates(self) -> None:
        candidate = deepcopy(self.valid)
        candidate["source_refs"][0]["published_or_effective_on"] = "2026-07-26"
        with self.assertRaisesRegex(ValueError, "published_or_effective_on"):
            patent_prior_art_evidence_pack.review_case(candidate)

    def test_rejects_unverified_redistribution(self) -> None:
        candidate = deepcopy(self.valid)
        candidate["source_refs"][0]["policy_receipt"] = None
        candidate["source_refs"][0]["redistribution"] = "allowed"
        with self.assertRaisesRegex(ValueError, "redistribution"):
            patent_prior_art_evidence_pack.review_case(candidate)
