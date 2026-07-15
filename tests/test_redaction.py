from __future__ import annotations

import unittest

from kgov_runtime.redaction import contains_direct_identifier


class RedactionTest(unittest.TestCase):
    def test_detects_supported_direct_identifier_patterns(self) -> None:
        samples = (
            "연락처 010-1234-5678",
            "주민번호 900101-1234567",
            "회신 user@example.org",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(contains_direct_identifier(sample))

    def test_allows_synthetic_administrative_text(self) -> None:
        self.assertFalse(
            contains_direct_identifier("2026년 공원 시설 3곳의 정비 계획을 검토합니다.")
        )


if __name__ == "__main__":
    unittest.main()
