#!/usr/bin/env python3
"""Fail-closed local admission guard for public-record-disclosure-redaction-review."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug='public-record-disclosure-redaction-review',
    review_types=frozenset(['disclosure-redaction-review', 'partial-disclosure-review']),
    allowed_hosts=frozenset(['www.open.go.kr', 'www.archives.go.kr']),
    required_checks=('disclosure-ground-ledger', 'redaction-region-review', 'record-integrity-and-appeal-route'),
    prohibited_decisions=('final-nondisclosure-decision', 'source-record-mutation', 'automatic-publication'),
    permitted_output='disclosure-review-draft-only',
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / 'public-record-disclosure-redaction-review.json'


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
