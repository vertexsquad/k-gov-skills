#!/usr/bin/env python3
"""Build a content-light, human-reviewed evidence-pack ledger from normalized receipts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.redaction import contains_direct_identifier  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "public-policy-evidence-pack.json"
TOP_LEVEL_FIELDS = frozenset(
    {"question", "as_of_date", "jurisdiction", "redaction_status", "claims"}
)
CLAIM_FIELDS = frozenset({"claim_id", "statement", "evidence"})
EVIDENCE_FIELDS = frozenset(
    {"source_url", "source_kind", "retrieved_on", "relationship", "receipt_status"}
)
SOURCE_KINDS = frozenset({"official-primary", "official-secondary", "non-official"})
RELATIONSHIPS = frozenset({"supports", "contradicts", "context"})
RECEIPT_STATUSES = frozenset({"retrieved", "not-retrieved"})
STATUS_SUPPORTED = "structurally-supported-pending-human-review"
STATUS_CONFLICTED = "conflict-detected-pending-human-review"
STATUS_INSUFFICIENT = "insufficient-official-evidence"
ALL_STATUSES = (STATUS_SUPPORTED, STATUS_CONFLICTED, STATUS_INSUFFICIENT)
CLAIM_ID = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
MAX_INPUT_FILE_BYTES = 250_000
MAX_QUESTION_CHARACTERS = 1_000
MAX_CLAIMS = 50
MAX_STATEMENT_CHARACTERS = 2_000
MAX_EVIDENCE_PER_CLAIM = 20
MAX_SOURCE_URL_CHARACTERS = 2_048


def _exact_fields(value: Mapping[str, Any], required: frozenset[str], scope: str) -> None:
    unknown = set(value) - required
    missing = sorted(required - set(value))
    if unknown:
        raise ValueError(f"{scope} has unknown fields")
    if missing:
        raise ValueError(f"{scope} missing fields: {', '.join(missing)}")


def _required_string(value: Any, field: str, *, max_characters: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if max_characters is not None and len(normalized) > max_characters:
        raise ValueError(f"{field} exceeds {max_characters} characters")
    return normalized


def _iso_date(value: Any, field: str) -> str:
    normalized = _required_string(value, field)
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO date") from exc
    if parsed.isoformat() != normalized:
        raise ValueError(f"{field} must use YYYY-MM-DD format")
    return normalized


def _source_url(value: Any) -> str:
    normalized = _required_string(
        value, "source_url", max_characters=MAX_SOURCE_URL_CHARACTERS
    )
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("source_url must be a credential-free HTTPS URL")
    try:
        parsed = urlsplit(normalized)
        parsed.port
    except ValueError as exc:
        raise ValueError("source_url must be a credential-free HTTPS URL") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("source_url must be a credential-free HTTPS URL")
    if contains_direct_identifier(normalized):
        raise ValueError("source_url contains a supported direct identifier")
    return normalized


def _enum(value: Any, field: str, allowed: frozenset[str]) -> str:
    normalized = _required_string(value, field)
    if normalized not in allowed:
        raise ValueError(f"{field} is invalid")
    return normalized


def _claim_result(claim: Mapping[str, Any], *, as_of_date: str) -> dict[str, Any]:
    if not isinstance(claim, Mapping):
        raise ValueError("claims entries must be JSON objects")
    _exact_fields(claim, CLAIM_FIELDS, "claim")
    claim_id = _required_string(claim.get("claim_id"), "claim_id")
    if not CLAIM_ID.fullmatch(claim_id):
        raise ValueError("claim_id must match the bounded identifier format")
    if contains_direct_identifier(claim_id):
        raise ValueError("claim_id contains a supported direct identifier")
    statement = _required_string(
        claim.get("statement"), "statement", max_characters=MAX_STATEMENT_CHARACTERS
    )
    if contains_direct_identifier(statement):
        raise ValueError("statement contains a supported direct identifier")

    evidence_items = claim.get("evidence")
    if not isinstance(evidence_items, list) or len(evidence_items) > MAX_EVIDENCE_PER_CLAIM:
        raise ValueError(
            f"evidence must be a list with at most {MAX_EVIDENCE_PER_CLAIM} entries"
        )

    retrieved_count = 0
    retrieved_primary_count = 0
    primary_support = False
    primary_contradiction = False
    for evidence in evidence_items:
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence entries must be JSON objects")
        _exact_fields(evidence, EVIDENCE_FIELDS, "evidence")
        _source_url(evidence.get("source_url"))
        source_kind = _enum(evidence.get("source_kind"), "source_kind", SOURCE_KINDS)
        retrieved_on = _iso_date(evidence.get("retrieved_on"), "retrieved_on")
        if retrieved_on > as_of_date:
            raise ValueError("retrieved_on cannot be after as_of_date")
        relationship = _enum(
            evidence.get("relationship"), "relationship", RELATIONSHIPS
        )
        receipt_status = _enum(
            evidence.get("receipt_status"), "receipt_status", RECEIPT_STATUSES
        )
        if receipt_status == "retrieved":
            retrieved_count += 1
        if source_kind == "official-primary" and receipt_status == "retrieved":
            retrieved_primary_count += 1
            if relationship == "supports":
                primary_support = True
            elif relationship == "contradicts":
                primary_contradiction = True

    if primary_support and primary_contradiction:
        status = STATUS_CONFLICTED
    elif primary_support:
        status = STATUS_SUPPORTED
    else:
        status = STATUS_INSUFFICIENT

    return {
        "claim_id": claim_id,
        "contradiction_detected": primary_contradiction,
        "evidence_count": len(evidence_items),
        "retrieved_evidence_count": retrieved_count,
        "retrieved_official_primary_count": retrieved_primary_count,
        "status": status,
    }


def build_evidence_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("input must be a JSON object")
    _exact_fields(payload, TOP_LEVEL_FIELDS, "input")
    question = _required_string(
        payload.get("question"), "question", max_characters=MAX_QUESTION_CHARACTERS
    )
    if contains_direct_identifier(question):
        raise ValueError("question contains a supported direct identifier")
    as_of_date = _iso_date(payload.get("as_of_date"), "as_of_date")
    if _required_string(payload.get("jurisdiction"), "jurisdiction") != "KR":
        raise ValueError("jurisdiction must be KR")
    if _required_string(payload.get("redaction_status"), "redaction_status") != "redacted":
        raise ValueError("redacted input is required")

    claims = payload.get("claims")
    if not isinstance(claims, list) or not claims or len(claims) > MAX_CLAIMS:
        raise ValueError(f"claims must contain between 1 and {MAX_CLAIMS} entries")
    results: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for claim in claims:
        result = _claim_result(claim, as_of_date=as_of_date)
        claim_id = result["claim_id"]
        if claim_id in seen_claim_ids:
            raise ValueError("duplicate claim_id")
        seen_claim_ids.add(claim_id)
        results.append(result)

    status_counts = {status: 0 for status in ALL_STATUSES}
    for result in results:
        status_counts[result["status"]] += 1

    return {
        "accepted": True,
        "as_of_date": as_of_date,
        "basic_identifier_scan": "no-match-not-proof-of-redaction",
        "claim_count": len(results),
        "claims": results,
        "jurisdiction": "KR",
        "manual_review_required": True,
        "permitted_output": "evidence-pack-draft-only",
        "receipt_assurance": "input-declared-not-live-retrieval-proof",
        "source_kind_assurance": "input-declared-not-independently-verified",
        "status_counts": status_counts,
    }


def _load_payload(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_INPUT_FILE_BYTES:
        raise ValueError(f"input file exceeds {MAX_INPUT_FILE_BYTES} bytes")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a redacted public-policy evidence ledger for human review"
    )
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="use the synthetic repository fixture")
    args = parser.parse_args()
    if args.fixture and args.path:
        parser.error("path cannot be combined with --fixture")
    if not args.fixture and args.path is None:
        parser.error("path is required unless --fixture is used")
    try:
        payload = _load_payload(FIXTURE if args.fixture else args.path)
        result = build_evidence_pack(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
