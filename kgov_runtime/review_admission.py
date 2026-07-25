#!/usr/bin/env python3
"""Shared fail-closed admission seam for local public-sector review drafts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from kgov_runtime.redaction import contains_direct_identifier

TOP_LEVEL_FIELDS = frozenset(
    {"case_id", "review_type", "summary", "facts", "source_refs", "as_of_date", "redaction_status"}
)
SOURCE_REF_FIELDS = frozenset({"url", "retrieved_on"})
MAX_INPUT_FILE_BYTES = 250_000
MAX_SUMMARY_CHARACTERS = 2_000
MAX_FACTS = 50
MAX_FACT_CHARACTERS = 1_000
MAX_SOURCE_REFS = 20
MAX_SOURCE_URL_CHARACTERS = 2_048
CASE_ID = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")


@dataclass(frozen=True)
class ReviewContract:
    slug: str
    review_types: frozenset[str]
    allowed_hosts: frozenset[str]
    required_checks: tuple[str, ...]
    prohibited_decisions: tuple[str, ...]
    permitted_output: str


def _exact_fields(value: Mapping[str, Any], required: frozenset[str], scope: str) -> None:
    if set(value) - required:
        raise ValueError(f"{scope} has unknown fields")
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{scope} missing fields: {', '.join(missing)}")


def _required_string(value: Any, field: str, max_characters: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > max_characters:
        raise ValueError(f"{field} exceeds {max_characters} characters")
    return normalized


def _iso_date(value: Any, field: str) -> str:
    normalized = _required_string(value, field, 10)
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO date") from exc
    if parsed.isoformat() != normalized:
        raise ValueError(f"{field} must use YYYY-MM-DD format")
    return normalized


def _source_url(value: Any, allowed_hosts: frozenset[str]) -> str:
    normalized = _required_string(value, "source_ref.url", MAX_SOURCE_URL_CHARACTERS)
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("source_ref.url must be an allowlisted credential-free HTTPS URL")
    try:
        parsed = urlsplit(normalized)
        parsed.port
    except ValueError as exc:
        raise ValueError("source_ref.url must be an allowlisted credential-free HTTPS URL") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("source_ref.url must be an allowlisted credential-free HTTPS URL")
    if contains_direct_identifier(normalized):
        raise ValueError("source_ref.url contains a supported direct identifier")
    return normalized


def admit_review(payload: Mapping[str, Any], contract: ReviewContract) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("input must be a JSON object")
    _exact_fields(payload, TOP_LEVEL_FIELDS, "input")
    case_id = _required_string(payload.get("case_id"), "case_id", 32)
    if not CASE_ID.fullmatch(case_id):
        raise ValueError("case_id must use a bounded alphanumeric identifier")
    review_type = _required_string(payload.get("review_type"), "review_type", 80)
    if review_type not in contract.review_types:
        raise ValueError("review_type is unsupported")
    summary = _required_string(payload.get("summary"), "summary", MAX_SUMMARY_CHARACTERS)
    as_of_date = _iso_date(payload.get("as_of_date"), "as_of_date")
    if payload.get("redaction_status") != "redacted":
        raise ValueError("redacted input is required")

    facts = payload.get("facts")
    if not isinstance(facts, list) or not facts or len(facts) > MAX_FACTS:
        raise ValueError(f"facts must contain between 1 and {MAX_FACTS} entries")
    normalized_facts = [
        _required_string(value, "facts entry", MAX_FACT_CHARACTERS) for value in facts
    ]
    if contains_direct_identifier("\n".join([case_id, summary, *normalized_facts])):
        raise ValueError("potential personal identifier remains in input")

    source_refs = payload.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs or len(source_refs) > MAX_SOURCE_REFS:
        raise ValueError(f"source_refs must contain between 1 and {MAX_SOURCE_REFS} entries")
    for item in source_refs:
        if not isinstance(item, Mapping):
            raise ValueError("source_refs entries must be JSON objects")
        _exact_fields(item, SOURCE_REF_FIELDS, "source_ref")
        _source_url(item.get("url"), contract.allowed_hosts)
        if _iso_date(item.get("retrieved_on"), "source_ref.retrieved_on") > as_of_date:
            raise ValueError("source_ref.retrieved_on cannot be after as_of_date")

    return {
        "accepted": True,
        "basic_identifier_scan": "no-match-not-proof-of-redaction",
        "fact_count": len(facts),
        "manual_review_required": True,
        "permitted_output": contract.permitted_output,
        "prohibited_decisions": list(contract.prohibited_decisions),
        "receipt_assurance": "input-declared-not-live-retrieval-proof",
        "required_checks": list(contract.required_checks),
        "review_type": review_type,
        "source_ref_count": len(source_refs),
        "status": "admitted-pending-human-review",
    }


def load_payload(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_INPUT_FILE_BYTES:
        raise ValueError(f"input file exceeds {MAX_INPUT_FILE_BYTES} bytes")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    return payload


def run_cli(contract: ReviewContract, fixture: Path) -> int:
    parser = argparse.ArgumentParser(description=f"Validate a redacted {contract.slug} review draft")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="use the synthetic repository fixture")
    args = parser.parse_args()
    if args.fixture and args.path:
        parser.error("path cannot be combined with --fixture")
    if not args.fixture and args.path is None:
        parser.error("path is required unless --fixture is used")
    try:
        result = admit_review(load_payload(fixture if args.fixture else args.path), contract)
    except OSError:
        parser.exit(2, "ERROR input file cannot be read\n")
    except json.JSONDecodeError:
        parser.exit(2, "ERROR input must be valid JSON\n")
    except ValueError as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
