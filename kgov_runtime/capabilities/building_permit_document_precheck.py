#!/usr/bin/env python3
"""Fail-closed local admission guard for building-permit-document-precheck."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug='building-permit-document-precheck',
    review_types=frozenset(['permit-document-precheck', 'permit-evidence-gap-check']),
    allowed_hosts=frozenset(['www.eais.go.kr', 'www.law.go.kr']),
    required_checks=('building-action-region-classification', 'required-document-candidate-ledger', 'live-surface-and-evidence-gap'),
    prohibited_decisions=('permit-eligibility-decision', 'drawing-compliance-approval', 'automatic-application-submission'),
    permitted_output='permit-precheck-draft-only',
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / 'building-permit-document-precheck.json'


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
