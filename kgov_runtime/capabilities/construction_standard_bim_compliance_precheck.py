#!/usr/bin/env python3
"""Fail-closed local admission guard for construction-standard-bim-compliance-precheck."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.review_admission import ReviewContract, admit_review, run_cli  # noqa: E402

CONTRACT = ReviewContract(
    slug='construction-standard-bim-compliance-precheck',
    review_types=frozenset(['construction-standard-precheck', 'bim-precheck']),
    allowed_hosts=frozenset(['www.kcsc.re.kr']),
    required_checks=('standard-version-and-scope', 'model-drawing-item-ledger', 'deviation-and-evidence-gap'),
    prohibited_decisions=('engineering-approval', 'structural-safety-decision', 'completion-certification'),
    permitted_output='engineering-precheck-draft-only',
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / 'construction-standard-bim-compliance-precheck.json'


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    return admit_review(payload, CONTRACT)


def main() -> int:
    return run_cli(CONTRACT, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
