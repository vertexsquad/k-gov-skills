#!/usr/bin/env python3
"""Fail-closed local admission guard for official-notice-multilingual-translation-review."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final, Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug='official-notice-multilingual-translation-review',
    review_types=frozenset(['multilingual-translation-review', 'terminology-consistency-review']),
    allowed_hosts=frozenset(['www.mois.go.kr', 'www.korean.go.kr']),
    required_checks=('meaning-and-official-terms', 'numbers-dates-contact-consistency', 'language-specialist-review-route'),
    prohibited_decisions=('automatic-publication', 'legal-meaning-certification', 'medical-meaning-certification'),
    permitted_output='translation-review-draft-only',
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / 'official-notice-multilingual-translation-review.json'


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


RUNTIME_CONTRACT_ID: Final[str] = "kgov/official-notice-multilingual-translation-review/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/official-notice-multilingual-translation-review/review-case/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
