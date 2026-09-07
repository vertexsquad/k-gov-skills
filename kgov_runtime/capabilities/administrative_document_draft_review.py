#!/usr/bin/env python3
"""Fail-closed admission and review guard for redacted administrative drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Final, Any, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.redaction import contains_direct_identifier  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "administrative-document-draft-review.json"
REQUIRED_FIELDS = frozenset(
    {"document_type", "title", "body", "purpose", "source_refs", "redaction_status"}
)
SUPPORTED_DOCUMENT_TYPES = frozenset(
    {
        "official-letter",
        "report",
        "meeting-material",
        "press-release",
        "audit-response",
        "council-agenda",
        "education-notice",
    }
)
MAX_INPUT_FILE_BYTES = 150_000
MAX_TITLE_CHARACTERS = 200
MAX_BODY_CHARACTERS = 30_000
MAX_PURPOSE_CHARACTERS = 500
MAX_SOURCE_REFS = 20
ALLOWED_SOURCE_HOSTS = frozenset(
    {
        "www.archives.go.kr",
        "www.bai.go.kr",
        "www.elis.go.kr",
        "gnews.gg.go.kr",
        "www.law.go.kr",
        "www.moe.go.kr",
        "www.mois.go.kr",
        "www.open.go.kr",
        "www.suwon.go.kr",
    }
)
LEGAL_TERMS = re.compile(r"법률|법령|조례|시행령|시행규칙|고시|훈령|예규")
NUMERIC_CLAIM = re.compile(r"\d")


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_source_refs(value: Any) -> int:
    if not isinstance(value, list) or len(value) > MAX_SOURCE_REFS:
        raise ValueError(f"source_refs must be a list with at most {MAX_SOURCE_REFS} entries")
    for source_ref in value:
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_refs entries must be non-empty HTTPS URLs")
        normalized = source_ref.strip()
        try:
            parsed = urlsplit(normalized)
            port = parsed.port
        except ValueError as exc:
            raise ValueError(
                "source_refs entries must be credential-free allowlisted HTTPS URLs without query or fragment"
            ) from exc
        if contains_direct_identifier(normalized):
            raise ValueError("source_refs entries must not contain direct identifiers")
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.lower().rstrip(".") not in ALLOWED_SOURCE_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or bool(parsed.query)
            or bool(parsed.fragment)
        ):
            raise ValueError(
                "source_refs entries must be credential-free allowlisted HTTPS URLs without query or fragment"
            )
    return len(value)


def review_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("input must be a JSON object")
    unknown = sorted(set(payload) - REQUIRED_FIELDS)
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")

    document_type = _required_string(payload, "document_type")
    title = _required_string(payload, "title")
    body = _required_string(payload, "body")
    purpose = _required_string(payload, "purpose")
    redaction_status = _required_string(payload, "redaction_status")

    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise ValueError(f"unsupported document_type: {document_type}")
    if len(title) > MAX_TITLE_CHARACTERS:
        raise ValueError(f"title exceeds {MAX_TITLE_CHARACTERS} characters")
    if len(body) > MAX_BODY_CHARACTERS:
        raise ValueError(f"body exceeds {MAX_BODY_CHARACTERS} characters")
    if len(purpose) > MAX_PURPOSE_CHARACTERS:
        raise ValueError(f"purpose exceeds {MAX_PURPOSE_CHARACTERS} characters")
    if redaction_status != "redacted":
        raise ValueError("redacted input is required")
    source_ref_count = _validate_source_refs(payload.get("source_refs"))

    combined = f"{title}\n{body}\n{purpose}"
    if contains_direct_identifier(combined):
        raise ValueError("potential personal identifier remains in input")

    return {
        "accepted": True,
        "basic_identifier_scan": "no-match-not-proof-of-redaction",
        "body_characters": len(body),
        "document_type": document_type,
        "manual_review_required": True,
        "permitted_output": "draft-review-only",
        "purpose_characters": len(purpose),
        "review_checks": {
            "institution_template": "required",
            "legal_authority": "required" if LEGAL_TERMS.search(combined) else "not-detected",
            "numeric_claims": "required" if NUMERIC_CLAIM.search(combined) else "not-detected",
            "privacy": "manual-confirmation-required",
            "source_traceability": "provided-review-required" if source_ref_count else "required",
        },
        "source_ref_count": source_ref_count,
        "title_characters": len(title),
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
        description="Validate a redacted administrative document draft for human review"
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
        result = review_document(payload)
    except OSError:
        parser.exit(2, "ERROR input file cannot be read\n")
    except json.JSONDecodeError:
        parser.exit(2, "ERROR input must be valid JSON\n")
    except ValueError as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/administrative-document-draft-review/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/administrative-document-draft-review/review-draft/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
