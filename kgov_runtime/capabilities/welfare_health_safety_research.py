#!/usr/bin/env python3
"""복지·보건 retrieval blocked pending an exact dataset profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final, Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import BlockedOperationError  # noqa: E402

CONTRACT_ID = "kgov/welfare-health-safety-research/v1"
OPERATION_ID = "kgov/welfare-health-safety-research/blocked-dataset-query/v1"
OPERATION = None


def query(*, params: Mapping[str, Any] | None = None, opener: Callable[..., Any] | None = None, resolver: Callable[[str], Iterable[Any]] | None = None) -> dict[str, Any]:
    del params, opener, resolver
    raise BlockedOperationError("live operation is blocked until an exact dataset profile is declared")


def fixture_result() -> dict[str, Any]:
    return {
        "contract_id": CONTRACT_ID,
        "execution_mode": "synthetic-fixture",
        "status": "live-operation-blocked",
        "count": 0,
        "records": [],
        "source_receipt": {"operation_id": OPERATION_ID, "policy_id": None, "endpoint": None},
        "manual_review_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Blocked read-only operation: {OPERATION_ID}")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    if not args.fixture:
        parser.exit(3, "ERROR live operation is blocked until an exact dataset profile is declared\n")
    print(json.dumps(fixture_result(), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/welfare-health-safety-research/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/welfare-health-safety-research/blocked-dataset-query/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
