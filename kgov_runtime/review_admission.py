#!/usr/bin/env python3
"""Shared fail-closed admission seam for local public-sector review drafts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from kgov_runtime.redaction import contains_direct_identifier

TOP_LEVEL_FIELDS = frozenset({"case_id", "review_type", "summary", "facts", "source_refs", "as_of_date", "redaction_status"})
SOURCE_REF_FIELDS = frozenset(
    "url retrieved_on published_or_effective_on institution title license_status terms_url "
    "redistribution attribution policy_receipt".split()
)
POLICY_RECEIPT_ORDER = tuple("source_url retrieved_on policy_id policy_revision policy_digest outcome".split())
POLICY_RECEIPT_FIELDS = frozenset(POLICY_RECEIPT_ORDER)
LICENSE_STATUSES = frozenset({"unreviewed", "manual-review", "reviewed"})
REDISTRIBUTION_MODES = frozenset({"link-only", "allowed"})
MAX_FACTS = 50
MAX_SOURCE_REFS = 20
MAX_SOURCE_URL_CHARACTERS = 2_048
CASE_ID = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")


class AdmissionError(ValueError):
    """Reject an admission input without echoing its value."""


@dataclass(frozen=True, slots=True)
class ReviewContract:
    slug: str
    review_types: frozenset[str]
    allowed_hosts: frozenset[str]
    required_checks: tuple[str, ...]
    prohibited_decisions: tuple[str, ...]
    permitted_output: str


def _exact_fields(value: Mapping[str, Any], required: frozenset[str], scope: str) -> None:
    if set(value) - required:
        raise AdmissionError(f"{scope} has unknown fields")
    missing = sorted(required - set(value))
    if missing:
        raise AdmissionError(f"{scope} missing fields: {', '.join(missing)}")


def _required_string(value: Any, field: str, max_characters: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdmissionError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > max_characters:
        raise AdmissionError(f"{field} exceeds {max_characters} characters")
    return normalized


def _iso_date(value: Any, field: str) -> str:
    normalized = _required_string(value, field, 10)
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise AdmissionError(f"{field} must be a valid ISO date") from exc
    if parsed.isoformat() != normalized:
        raise AdmissionError(f"{field} must use YYYY-MM-DD format")
    return normalized


def _source_url(value: Any, allowed_hosts: frozenset[str]) -> str:
    normalized = _required_string(value, "source_ref.url", MAX_SOURCE_URL_CHARACTERS)
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise AdmissionError("source_ref.url must be an allowlisted credential-free HTTPS URL")
    try:
        parsed = urlsplit(normalized)
        parsed.port
    except ValueError as exc:
        raise AdmissionError("source_ref.url must be an allowlisted credential-free HTTPS URL") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AdmissionError("source_ref.url must be an allowlisted credential-free HTTPS URL")
    if contains_direct_identifier(normalized):
        raise AdmissionError("source_ref.url contains a supported direct identifier")
    return normalized


def _policy_for_receipt(receipt: Mapping[str, Any], source_url: str, capability_slug: str) -> Mapping[str, Any]:
    policy_id = _required_string(receipt.get("policy_id"), "policy_receipt.policy_id", 64)
    catalog = json.loads((Path(__file__).resolve().parents[1] / "catalog" / "domain-skills.json").read_text(encoding="utf-8"))
    contract = next((item for item in catalog["runtime_contracts"] if item.get("capability_slug") == capability_slug), None)
    if contract is None or not any(
        policy_id in operation.get("source_policy_ids", []) for operation in contract.get("operations", [])
    ):
        raise AdmissionError("policy_receipt.policy_id is not declared for capability")
    policies = catalog["source_policies"]
    policy = next((item for item in policies if item.get("id") == policy_id), None)
    if policy is None:
        raise AdmissionError("policy_receipt.policy_id is not current")
    parsed_source = urlsplit(source_url)
    scope = policy.get("scope")
    origins = scope.get("origins") if isinstance(scope, Mapping) else None
    rules = scope.get("path_rules") if isinstance(scope, Mapping) else None
    origin = f"{parsed_source.scheme}://{parsed_source.netloc}"
    path = parsed_source.path or "/"
    if not isinstance(origins, list) or origin not in origins or not isinstance(rules, list):
        raise AdmissionError("policy_receipt.policy_id does not cover source_url")
    matches = any(
        (rule["match"] == "exact" and path == rule["path"])
        or (
            rule["match"] == "prefix"
            and (rule["path"] == "/" or path == rule["path"] or path.startswith(f"{rule['path']}/"))
        )
        for rule in rules
    )
    if not matches:
        raise AdmissionError("policy_receipt.policy_id does not cover source_url")
    return policy


def _receipt_assurance(receipt: Any, source: tuple[str, str, str], capability_slug: str) -> tuple[str, str | None, Mapping[str, Any] | None]:
    if receipt is None:
        return "caller-declared", "caller-declared-source", None
    if not isinstance(receipt, Mapping):
        raise AdmissionError("source_ref.policy_receipt must be an object or null")
    _exact_fields(receipt, POLICY_RECEIPT_FIELDS, "source_ref.policy_receipt")
    source_url, retrieved_on, institution = source
    policy = _policy_for_receipt(receipt, source_url, capability_slug)
    if institution != policy.get("institution"):
        raise AdmissionError("source_ref.institution does not match policy_receipt")
    digest = hashlib.sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    outcome = "allowed" if policy.get("enabled") is True else "manual-review"
    actual = tuple(receipt.get(key) for key in POLICY_RECEIPT_ORDER)
    expected = (source_url, retrieved_on, policy.get("id"), policy.get("revision"), digest, outcome)
    if type(receipt.get("policy_revision")) is not int or actual != expected:
        raise AdmissionError("source_ref.policy_receipt does not match the current policy")
    reason = None if outcome == "allowed" else "policy-outcome-manual-review"
    return "policy-verified-not-authenticity-proof", reason, policy


def admit_review(payload: Mapping[str, Any], contract: ReviewContract) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise AdmissionError("input must be a JSON object")
    _exact_fields(payload, TOP_LEVEL_FIELDS, "input")
    case_id = _required_string(payload.get("case_id"), "case_id", 32)
    if not CASE_ID.fullmatch(case_id):
        raise AdmissionError("case_id must use a bounded alphanumeric identifier")
    review_type = _required_string(payload.get("review_type"), "review_type", 80)
    if review_type not in contract.review_types:
        raise AdmissionError("review_type is unsupported")
    summary = _required_string(payload.get("summary"), "summary", 2_000)
    as_of_date = _iso_date(payload.get("as_of_date"), "as_of_date")
    if payload.get("redaction_status") != "redacted":
        raise AdmissionError("redacted input is required")

    facts = payload.get("facts")
    if not isinstance(facts, list) or not facts or len(facts) > MAX_FACTS:
        raise AdmissionError(f"facts must contain between 1 and {MAX_FACTS} entries")
    normalized_facts = [_required_string(value, "facts entry", 1_000) for value in facts]
    if contains_direct_identifier("\n".join([case_id, summary, *normalized_facts])):
        raise AdmissionError("potential personal identifier remains in input")

    source_refs = payload.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs or len(source_refs) > MAX_SOURCE_REFS:
        raise AdmissionError(f"source_refs must contain between 1 and {MAX_SOURCE_REFS} entries")
    assurance_levels: set[str] = set()
    manual_review_reasons: set[str] = set()
    source_output_mode = "projected-records"
    for item in source_refs:
        if not isinstance(item, Mapping):
            raise AdmissionError("source_refs entries must be JSON objects")
        _exact_fields({**item, "policy_receipt": item.get("policy_receipt")}, SOURCE_REF_FIELDS, "source_ref")
        source_url = _source_url(item.get("url"), contract.allowed_hosts)
        retrieved_on = _iso_date(item.get("retrieved_on"), "source_ref.retrieved_on")
        published_on = _iso_date(item.get("published_or_effective_on"), "source_ref.published_or_effective_on")
        if retrieved_on > as_of_date:
            raise AdmissionError("source_ref.retrieved_on cannot be after as_of_date")
        if published_on > retrieved_on:
            raise AdmissionError("source_ref.published_or_effective_on cannot be after retrieved_on")
        metadata = tuple(
            _required_string(item.get(key), f"source_ref.{key}", limit)
            for key, limit in (("institution", 120), ("title", 500), ("attribution", 500))
        )
        if contains_direct_identifier("\n".join(metadata)):
            raise AdmissionError("potential personal identifier remains in source_ref metadata")
        license_status = item.get("license_status")
        redistribution = item.get("redistribution")
        if license_status not in LICENSE_STATUSES:
            raise AdmissionError("source_ref.license_status is unsupported")
        if redistribution not in REDISTRIBUTION_MODES:
            raise AdmissionError("source_ref.redistribution is unsupported")
        terms_url = item.get("terms_url")
        if terms_url is not None:
            _source_url(terms_url, contract.allowed_hosts)
        assurance, reason, policy = _receipt_assurance(item.get("policy_receipt"), (source_url, retrieved_on, metadata[0]), contract.slug)
        assurance_levels.add(assurance)
        if reason is not None:
            manual_review_reasons.add(reason)
        policy_license = policy.get("license") if policy is not None else None
        policy_terms = policy.get("terms") if policy is not None else None
        expected_terms_url = policy_terms.get("url") if isinstance(policy_terms, Mapping) else None
        expected_redistribution = (
            policy_license.get("redistribution", "link-only")
            if isinstance(policy_license, Mapping)
            else None
        )
        if policy is not None and (
            not isinstance(policy_license, Mapping)
            or license_status != policy_license.get("status")
            or terms_url != expected_terms_url
            or redistribution != expected_redistribution
        ):
            raise AdmissionError("source_ref metadata does not match policy_receipt outcome")
        if license_status != "reviewed":
            manual_review_reasons.add("license-unverified")
        if redistribution == "link-only":
            manual_review_reasons.add("redistribution-link-only")
            source_output_mode = "link-only"
        if (policy is None or license_status != "reviewed") and redistribution == "allowed":
            raise AdmissionError("source_ref.redistribution requires a verified license policy")

    return {
        "accepted": True,
        "basic_identifier_scan": "no-match-not-proof-of-redaction",
        "fact_count": len(facts),
        "manual_review_reasons": sorted(manual_review_reasons),
        "manual_review_required": True,
        "permitted_output": contract.permitted_output,
        "prohibited_decisions": list(contract.prohibited_decisions),
        "receipt_assurance": "policy-matched-not-cryptographic-authenticity-proof" if assurance_levels == {"policy-verified-not-authenticity-proof"} else "caller-declared-not-live-retrieval-proof",
        "required_checks": list(contract.required_checks),
        "review_type": review_type,
        "source_assurance_levels": sorted(assurance_levels),
        "source_output_mode": source_output_mode,
        "source_ref_count": len(source_refs),
        "status": "admitted-pending-human-review",
    }


def load_payload(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > 250_000:
        raise AdmissionError("input file exceeds 250000 bytes")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AdmissionError("input must be a JSON object")
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
