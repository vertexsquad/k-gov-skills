from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from datetime import date
from pathlib import Path

from kgov_runtime.redaction import (
    contains_direct_identifier,
    find_direct_identifiers,
    scan_output,
)


class RedactionTest(unittest.TestCase):
    def test_detects_supported_direct_identifier_patterns(self) -> None:
        samples = (
            "연락처 010-1234-5678",
            "주민번호 900101-1234567",
            "회신 user@example.org",
            "담당자 user@example.org의 요청",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(contains_direct_identifier(sample))

    def test_detects_email_before_sentence_final_period(self) -> None:
        samples = (
            "회신 synthetic@example.org",
            "회신 synthetic@example.org.",
            "회신 (synthetic@example.org)",
            "회신 (synthetic@example.org.)",
            "회신 synthetic@example.org. 확인 바랍니다.",
            "회신 synthetic @ example . org .",
            "회신 ｓｙｎｔｈｅｔｉｃ＠ｅｘａｍｐｌｅ．ｏｒｇ．",
            "회신 synthetic@example.org!",
            "회신 synthetic@example.org?",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(("email",), find_direct_identifiers(sample))

    def test_civil_complaint_cli_rejects_email_without_reflecting_input(self) -> None:
        root = Path(__file__).resolve().parents[1]
        adapter = root / "kgov_runtime/capabilities/civil_complaint_triage_draft.py"
        fixture = root / "tests/fixtures/capabilities/civil-complaint-triage-draft.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        samples = ((payload["body"], 0), ("회신 synthetic@example.org.", 2))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for body, expected_code in samples:
                with self.subTest(expected_code=expected_code):
                    path.write_text(json.dumps(dict(payload, body=body)), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(adapter), str(path)],
                        capture_output=True, text=True, check=False, timeout=10,
                    )
                    self.assertEqual(expected_code, result.returncode, result.stderr)
                    if expected_code == 0:
                        self.assertTrue(json.loads(result.stdout)["accepted"])
                        self.assertEqual("", result.stderr)
                    else:
                        self.assertEqual("", result.stdout)
                        self.assertTrue(result.stderr.startswith("ERROR "))
                    self.assertNotIn(body, result.stdout + result.stderr)
                    self.assertNotIn("synthetic@example.org", result.stdout + result.stderr)

    def test_detects_nfkc_and_unicode_dash_variants(self) -> None:
        samples = (
            "연락처 ０１０－１２３４－５６７８",
            "연락처 010—1234—5678",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(("mobile_phone",), find_direct_identifiers(sample))

    def test_detects_every_unicode_dash_punctuation_code_point(self) -> None:
        dash_characters = (
            character
            for code_point in range(sys.maxunicode + 1)
            if unicodedata.category(character := chr(code_point)) == "Pd"
        )

        for character in dash_characters:
            with self.subTest(code_point=f"U+{ord(character):04X}"):
                sample = f"연락처 010{character}1234{character}5678"
                self.assertEqual(("mobile_phone",), find_direct_identifiers(sample))

    def test_detects_zero_width_and_control_obfuscation(self) -> None:
        samples = (
            "연락처 010\u200b-1234-5678",
            "연락처 010-12\x0034-5678",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(("mobile_phone",), find_direct_identifiers(sample))

    def test_detects_separator_whitespace(self) -> None:
        samples = (
            ("연락처 010 - 1234 - 5678", ("mobile_phone",)),
            ("회신 synthetic @ example . org", ("email",)),
        )
        for sample, expected in samples:
            with self.subTest(sample=sample):
                self.assertEqual(expected, find_direct_identifiers(sample))

    def test_detects_foreign_registration_and_limited_domestic_phones(self) -> None:
        samples = (
            ("등록번호 900101-5123456", ("foreign_registration_number",)),
            ("대표전화 02-1234-5678", ("domestic_phone",)),
            ("대표전화 031-123-4567", ("domestic_phone",)),
            ("대표전화 070-1234-5678", ("domestic_phone",)),
            ("대표전화 02\u200b1234\u200b5678", ("domestic_phone",)),
            ("대표전화 0212345678", ("domestic_phone",)),
        )
        for sample, expected in samples:
            with self.subTest(sample=sample):
                self.assertEqual(expected, find_direct_identifiers(sample))

    def test_registration_dates_respect_month_day_and_discriminator_century(self) -> None:
        samples = (
            ("주민번호 000229-3123456", ("resident_registration_number",)),
            ("등록번호 000229-7123456", ("foreign_registration_number",)),
            ("등록번호 202609-5123456", ()),
            ("등록번호 991332-5123456", ()),
            ("주민번호 000229-1123456", ()),
            ("등록번호 000229-5123456", ()),
        )
        for sample, expected in samples:
            with self.subTest(sample=sample):
                self.assertEqual(expected, find_direct_identifiers(sample))

    def test_registration_dates_do_not_exceed_injected_evaluation_date(self) -> None:
        on_date = date(2026, 9, 6)
        samples = (
            ("주민번호 260906-3123456", ("resident_registration_number",)),
            ("등록번호 260906-7123456", ("foreign_registration_number",)),
            ("주민번호 260907-3123456", ()),
            ("등록번호 261001-7123456", ()),
        )
        for sample, expected in samples:
            with self.subTest(sample=sample):
                self.assertEqual(
                    expected,
                    find_direct_identifiers(sample, on_date=on_date),
                )
        self.assertFalse(
            contains_direct_identifier("주민번호 260907-3123456", on_date=on_date)
        )
        self.assertEqual(
            (),
            scan_output(
                {"nested": ["등록번호 261001-7123456"]},
                on_date=on_date,
            ),
        )

    def test_rejects_malformed_email_dot_and_domain_hyphen_syntax(self) -> None:
        samples = (
            "회신 .synthetic@example.org",
            "회신 synthetic..alias@example.org",
            "회신 synthetic.@example.org",
            "회신 synthetic@.example.org",
            "회신 synthetic@example..org",
            "회신 synthetic@example-.org",
            "회신 synthetic@example.org-",
            "회신 synthetic@example.org_",
            "회신 synthetic@example.org..invalid",
            "회신 synthetic@example.org.123",
            "회신 synthetic@example.org._invalid",
            "회신 synthetic@example.org.-invalid",
            "회신 synthetic@example.org.a",
            "회신 synthetic@example.org1",
            "회신 (synthetic@example.org..invalid)",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual((), find_direct_identifiers(sample))

    def test_email_lengths_are_bounded_without_rejecting_boundary_values(self) -> None:
        local_at_limit = "a" * 64
        label_at_limit = "b" * 63
        overlong_domain = ".".join(("c" * 63,) * 4) + ".org"
        email_at_limit = f"{local_at_limit}@" + ".".join(("b" * 63, "c" * 63, "d" * 61))
        samples = (
            (f"{local_at_limit}@example.org", ("email",)),
            (f"synthetic@{label_at_limit}.org", ("email",)),
            (f"a{local_at_limit}@example.org", ()),
            (f"synthetic@b{label_at_limit}.org", ()),
            (f"synthetic@{overlong_domain}", ()),
            (email_at_limit, ("email",)),
            (email_at_limit + "d", ()),
        )
        for sample, expected in samples:
            for suffix in ("", "."):
                with self.subTest(length=len(sample), suffix=suffix, expected=expected):
                    self.assertEqual(expected, find_direct_identifiers(sample + suffix))

    def test_recursive_scan_returns_only_paths_and_categories(self) -> None:
        value = {
            "summary": "안전한 행정 검토 문구",
            "claims": [
                {"contact": "synthetic @ example . org."},
                "등록번호 900101—5123456",
            ],
        }

        findings = scan_output(value)

        self.assertEqual(
            (
                {"path": "$.claims[0].contact", "category": "email"},
                {
                    "path": "$.claims[1]",
                    "category": "foreign_registration_number",
                },
            ),
            findings,
        )
        serialized = repr(findings)
        self.assertNotIn("synthetic", serialized)
        self.assertNotIn("900101", serialized)

    def test_recursive_scan_uses_non_leaking_collision_free_paths_for_unsafe_keys(
        self,
    ) -> None:
        value = {
            "safe": "안전한 값",
            "synthetic@example.org.": "안전한 값",
            "010-1234-5678": "안전한 값",
            "dotted.key": "회신 other@example.org",
        }

        findings = scan_output(value)

        self.assertEqual(
            (
                {"path": "$[key:1]", "category": "email"},
                {"path": "$[key:2]", "category": "mobile_phone"},
                {"path": "$[value:3]", "category": "email"},
            ),
            findings,
        )
        paths = tuple(finding["path"] for finding in findings)
        self.assertEqual(len(paths), len(set(paths)))
        serialized = repr(findings)
        self.assertNotIn("synthetic", serialized)
        self.assertNotIn("010-1234-5678", serialized)
        self.assertNotIn("dotted.key", serialized)

    def test_dotted_key_path_does_not_collide_with_nested_safe_key_path(self) -> None:
        value = {
            "section": {"item": "회신 first@example.org"},
            "section.item": "회신 second@example.org",
        }

        findings = scan_output(value)

        self.assertEqual(
            (
                {"path": "$.section.item", "category": "email"},
                {"path": "$[value:1]", "category": "email"},
            ),
            findings,
        )
        self.assertEqual(2, len({finding["path"] for finding in findings}))

    def test_allows_synthetic_administrative_text(self) -> None:
        samples = (
            "2026년 공원 시설 3곳의 정비 계획을 검토합니다.",
            "시행일은 2026-09-06이며 문서번호는 제2026-1234호입니다.",
            "사업비 123-4567원과 우편번호 03123을 검토합니다.",
            "내선 030-123-4567과 071-1234-5678은 지원하지 않는 번호 형식입니다.",
            "참조번호 9900101-51234567과 031-1234-56789를 확인합니다.",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual((), find_direct_identifiers(sample))
                self.assertFalse(contains_direct_identifier(sample))


if __name__ == "__main__":
    unittest.main()
