#!/usr/bin/env python3
"""Fail-closed local admission guard for public-records-lifecycle-review."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final, Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug="public-records-lifecycle-review",
    review_types=frozenset(["retention-schedule-review", "transfer-disposal-precheck"]),
    allowed_hosts=frozenset(["www.archives.go.kr", "www.law.go.kr"]),
    required_checks=(
        "records-series-and-business-function",
        "retention-basis-and-trigger",
        "transfer-disposal-and-approval-gate",
    ),
    prohibited_decisions=(
        "final-retention-period",
        "source-record-mutation",
        "automatic-transfer-or-disposal",
    ),
    permitted_output="records-lifecycle-review-draft-only",
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "public-records-lifecycle-review.json"


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


RUNTIME_CONTRACT_ID: Final[str] = "kgov/public-records-lifecycle-review/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/public-records-lifecycle-review/review-case/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
