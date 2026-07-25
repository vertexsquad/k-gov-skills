#!/usr/bin/env python3
"""Fail-closed local admission guard for public-it-project-procedure-review."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug='public-it-project-procedure-review',
    review_types=frozenset(['project-stage-check', 'deliverable-check']),
    allowed_hosts=frozenset(['www.mois.go.kr', 'www.law.go.kr']),
    required_checks=('project-stage-identification', 'required-deliverables', 'approval-owner-and-current-rule'),
    prohibited_decisions=('automatic-procurement-start', 'automatic-acceptance', 'institution-rule-assumption'),
    permitted_output='procedure-review-draft-only',
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / 'public-it-project-procedure-review.json'


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
