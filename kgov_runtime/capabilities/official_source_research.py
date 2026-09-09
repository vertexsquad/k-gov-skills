#!/usr/bin/env python3
"""Inspect one policy-approved government page without page actions."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from html import unescape
from pathlib import Path
from typing import Final, TypedDict
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.cli import SafeArgumentParser  # noqa: E402
from kgov_runtime.http import (  # noqa: E402
    HttpPolicyEnforcer,
    ReadOnlyHttpError,
    SourceRequest,
    TextDocument,
    open_policy_state,
    policy_failure_status,
)
from kgov_runtime.policy_state import policy_state_path as _state_path  # noqa: E402
from kgov_runtime.source_policy import SourcePolicy, SourcePolicyRegistry  # noqa: E402

OPERATION_ID = "kgov/official-source-research/inspect-page/v1"
POLICY_ID = "gov-kr-web"
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "official-source-research.json"
CATALOG = ROOT / "catalog" / "domain-skills.json"


class ReceiptOutput(TypedDict):
    operation_id: str
    policy_id: str
    policy_revision: int
    policy_digest: str
    outcome: str


class OfficialSourceResult(TypedDict):
    url: str
    status: int
    content_type: str
    title: str
    content_length: int
    sha256: str
    execution_mode: str
    source_receipt: ReceiptOutput
    manual_review_required: bool


def _project(document: TextDocument, url: str) -> dict[str, str | int]:
    match = re.search(
        r"<title[^>]*>(.*?)</title>", document.text, flags=re.IGNORECASE | re.DOTALL
    )
    title = re.sub(r"\s+", " ", unescape(match.group(1))).strip() if match else ""
    parsed = urlsplit(url)
    return {
        "url": f"{parsed.scheme}://{parsed.hostname}{parsed.path or '/'}",
        "status": document.status,
        "content_type": document.media_type,
        "title": title,
        "content_length": document.content_length,
        "sha256": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
    }


def inspect_source(
    url: str, policy: SourcePolicy, enforcer: HttpPolicyEnforcer
) -> OfficialSourceResult:
    """Return a metadata-only receipt for the exact approved operation."""
    fetched = enforcer.fetch_text(
        SourceRequest(url, OPERATION_ID, policy),
        lambda document: _project(document, url),
    )
    receipt = fetched.source_receipt
    return {
        **fetched.value,
        "execution_mode": "official-live",
        "source_receipt": {
            "operation_id": receipt.operation_id,
            "policy_id": receipt.policy_id,
            "policy_revision": receipt.policy_revision,
            "policy_digest": receipt.policy_digest,
            "outcome": receipt.outcome,
        },
        "manual_review_required": True,
    }


def _live(url: str) -> OfficialSourceResult:
    registry = SourcePolicyRegistry.from_catalog(
        json.loads(CATALOG.read_text(encoding="utf-8")), on_date=date.today()
    )
    policy = next(item for item in registry.policies if item.id == POLICY_ID)
    decision = registry.authorize(url, OPERATION_ID)
    if not decision.allowed:
        raise ReadOnlyHttpError(policy_failure_status(decision.code))
    state_path = _state_path()
    state = open_policy_state(state_path)
    return inspect_source(url, policy, HttpPolicyEnforcer(registry, state))


def main() -> int:
    parser = SafeArgumentParser(
        description="Read-only Korean official-source inspector"
    )
    parser.add_argument("url", nargs="?")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    try:
        if args.fixture:
            result = json.loads(FIXTURE.read_text(encoding="utf-8"))
        elif args.url:
            result = _live(args.url)
        else:
            parser.error("URL is required unless --fixture is used")
    except ReadOnlyHttpError as exc:
        policy_statuses = {
            "policy-disabled",
            "policy-expired",
            "robots-denied",
            "terms-unverified",
            "license-unverified",
            "budget-exhausted",
        }
        parser.exit(
            2
            if exc.status == "invalid-request"
            else 3
            if exc.status in policy_statuses
            else 4,
            f"ERROR {exc}\n",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/official-source-research/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/official-source-research/inspect-page/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
