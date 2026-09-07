#!/usr/bin/env python3
"""Fail-closed local admission guard for regulated-trade-procedure-precheck."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final, Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug="regulated-trade-procedure-precheck",
    review_types=frozenset(
        ["customs-origin-document-precheck", "trade-procedure-document-precheck"]
    ),
    allowed_hosts=frozenset(["www.customs.go.kr", "unipass.customs.go.kr"]),
    required_checks=(
        "goods-and-origin-criteria-ledger",
        "official-document-and-validity-review",
        "manual-customs-decision-route",
    ),
    prohibited_decisions=(
        "origin-determination",
        "customs-declaration-or-submission",
        "clearance-or-enforcement-action",
    ),
    permitted_output="regulated-trade-review-draft-only",
)
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "capabilities"
    / "regulated-trade-procedure-precheck.json"
)


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


RUNTIME_CONTRACT_ID: Final[str] = "kgov/regulated-trade-procedure-precheck/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/regulated-trade-procedure-precheck/review-case/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
