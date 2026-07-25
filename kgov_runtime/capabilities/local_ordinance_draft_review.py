#!/usr/bin/env python3
"""Fail-closed local admission guard for local-ordinance-draft-review."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug='local-ordinance-draft-review',
    review_types=frozenset(['ordinance-draft-review', 'legal-basis-review']),
    allowed_hosts=frozenset(['www.elis.go.kr', 'www.law.go.kr']),
    required_checks=('delegation-and-conflict-check', 'article-structure-and-supplementary-provisions', 'effective-date-and-transition'),
    prohibited_decisions=('final-legal-opinion', 'automatic-promulgation', 'automatic-legislative-notice'),
    permitted_output='ordinance-review-draft-only',
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / 'local-ordinance-draft-review.json'


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
