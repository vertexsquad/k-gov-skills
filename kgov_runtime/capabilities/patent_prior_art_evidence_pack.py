#!/usr/bin/env python3
"""Safe KIPRIS/KIPO lookup plus fail-closed prior-art evidence-pack admission.

# noqa: SIZE_OK -- Issue #31 owns exactly this patent implementation path;
# splitting the URL/projector boundary would exceed the eight-file ownership.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any, Final, Literal, Mapping, NoReturn, TypedDict, assert_never
from urllib.parse import parse_qsl, quote, unquote_to_bytes, urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.capabilities.korean_legal_citation_verification import (  # noqa: E402
    _contains_identifier_after_normalization as contains_encoded_identifier,
)
from kgov_runtime.http import (  # noqa: E402
    HttpPolicyEnforcer,
    ReadOnlyHttpError,
    SourceRequest,
    TextDocument,
    UnsafeEndpointError,
    policy_failure_status,
)
from kgov_runtime.policy_state import PolicyState, PolicyStateUnavailableError  # noqa: E402
from kgov_runtime.source_policy import SourcePolicy, SourcePolicyRegistry  # noqa: E402
from kgov_runtime.redaction import contains_direct_identifier  # noqa: E402
from kgov_runtime.review_admission import (  # noqa: E402
    ReviewContract,
    admit_review,
    load_payload,
)

CONTRACT = ReviewContract(
    slug="patent-prior-art-evidence-pack",
    review_types=frozenset(["prior-art-evidence-pack", "claim-element-mapping"]),
    allowed_hosts=frozenset(["www.kipris.or.kr", "www.kipo.go.kr"]),
    required_checks=(
        "publication-number-and-date",
        "claim-element-citation-map",
        "family-duplicate-and-gap-review",
    ),
    prohibited_decisions=(
        "novelty-decision",
        "inventive-step-decision",
        "infringement-or-registration-opinion",
    ),
    permitted_output="prior-art-evidence-pack-draft-only",
)
FIXTURE = (
    ROOT / "tests" / "fixtures" / "capabilities" / "patent-prior-art-evidence-pack.json"
)
# Exact official hosts only. Do not use parent-domain suffix matching here.
LOOKUP_ALLOWED_HOSTS = set(CONTRACT.allowed_hosts)
OPERATION_ID: Final = "kgov/patent-prior-art-evidence-pack/inspect-source/v1"
CATALOG: Final = ROOT / "catalog/domain-skills.json"
CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_id",
        "client_secret",
        "key",
        "password",
        "passwd",
        "secret",
        "service_key",
        "servicekey",
        "token",
    }
)


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a redacted, user-supplied evidence-pack draft without network access."""

    return admit_review(payload, CONTRACT)


class LookupMetadata(TypedDict):
    url: str
    status: int
    content_type: str
    title: str
    content_length: int
    sha256: str


class PolicyReceipt(TypedDict):
    operation_id: str
    policy_id: str
    policy_revision: int
    policy_digest: str
    outcome: Literal["allowed"]


class PatentLookupResult(LookupMetadata):
    execution_mode: Literal["official-live"]
    source_receipt: PolicyReceipt
    manual_review_required: bool


def _safe_lookup_display_url(url: str) -> str:
    """Return only scheme/host/path so query values never appear in receipts."""

    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path or '/'}"


def _validated_lookup_url(url: str) -> str:
    if any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in url
    ):
        raise UnsafeEndpointError("unsafe lookup URL")
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if re.search(r"%(?![0-9A-Fa-f]{2})", path):
        raise UnsafeEndpointError("unsafe lookup path")
    try:
        decoded_path = unicodedata.normalize(
            "NFKC", unquote_to_bytes(path).decode("utf-8", errors="strict")
        )
    except (UnicodeDecodeError, UnicodeEncodeError):
        raise UnsafeEndpointError("unsafe lookup path") from None
    if (
        "%" in decoded_path
        or "\\" in decoded_path
        or "//" in decoded_path
        or decoded_path.count("/") != path.count("/")
        or any(part in {".", ".."} for part in decoded_path.split("/"))
        or any(
            unicodedata.category(character).startswith("C") or character.isspace()
            for character in decoded_path
        )
        or contains_direct_identifier(decoded_path)
    ):
        raise UnsafeEndpointError("unsafe lookup path")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("only HTTPS lookup URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("embedded URL credentials are forbidden")
    if host not in LOOKUP_ALLOWED_HOSTS:
        raise ValueError("host is not allowlisted")
    if parsed.fragment:
        raise ValueError("lookup URL fragments are forbidden")
    if contains_direct_identifier(url):
        raise ValueError("lookup URL contains a supported direct identifier")
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query_keys = {key.lower() for key, _ in query_items}
    if query_keys & CREDENTIAL_QUERY_KEYS:
        raise ValueError("credential-bearing lookup query parameters are forbidden")
    for key, value in query_items:
        if contains_direct_identifier(f"{key}={value}"):
            raise ValueError("lookup URL contains a supported direct identifier")
    return parsed._replace(path=quote(decoded_path, safe="/-._~")).geturl()


def inspect_patent_source(
    url: str,
    policy: SourcePolicy,
    enforcer: HttpPolicyEnforcer,
) -> PatentLookupResult:
    """Read one public KIPRIS/KIPO page with bounded, redirect-rejecting HTTP."""

    validated = _validated_lookup_url(url)
    expected = {"www.kipris.or.kr": "kipris-web", "www.kipo.go.kr": "kipo-web"}[
        urlsplit(validated).hostname
    ]
    if policy.id != expected:
        raise ReadOnlyHttpError("policy-disabled")

    def project(document: TextDocument) -> LookupMetadata:
        # Page permission is not permission to extract drawings or attachments.
        if document.media_type not in {"text/html", "application/xhtml+xml"}:
            raise ReadOnlyHttpError("response-invalid")
        matched = re.search(
            r"<title[^>]*>(.*?)</title>", document.text, flags=re.IGNORECASE | re.DOTALL
        )
        title = unicodedata.normalize(
            "NFKC", unescape(matched.group(1)) if matched else ""
        )
        if any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in title
        ):
            raise ReadOnlyHttpError("response-invalid")
        if contains_encoded_identifier(title):
            raise ReadOnlyHttpError("response-invalid")
        title = re.sub(r"\s+", " ", title).strip()
        return {
            "url": _safe_lookup_display_url(validated),
            "status": document.status,
            "content_type": document.media_type,
            "title": title,
            "content_length": document.content_length,
            "sha256": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
        }

    fetched = enforcer.fetch_text(
        SourceRequest(validated, OPERATION_ID, policy), project
    )
    receipt = fetched.source_receipt
    return {
        **fetched.value,
        "execution_mode": "official-live",
        "manual_review_required": True,
        "source_receipt": {
            "operation_id": receipt.operation_id,
            "policy_id": receipt.policy_id,
            "policy_revision": receipt.policy_revision,
            "policy_digest": receipt.policy_digest,
            "outcome": receipt.outcome,
        },
    }


def _state_path() -> Path:
    if configured := os.environ.get("KGOV_POLICY_STATE_PATH"):
        return Path(configured)
    if xdg_state := os.environ.get("XDG_STATE_HOME"):
        return Path(xdg_state) / "k-gov-skills/policy-state.sqlite3"
    return Path.home() / ".local/state/k-gov-skills/policy-state.sqlite3"


def _live(url: str) -> PatentLookupResult:
    validated = _validated_lookup_url(url)
    registry = SourcePolicyRegistry.from_catalog(
        json.loads(CATALOG.read_text(encoding="utf-8")), on_date=date.today()
    )
    decision = registry.authorize(validated, OPERATION_ID)
    if not decision.allowed:
        raise ReadOnlyHttpError(policy_failure_status(decision.code))
    policy = next(item for item in registry.policies if item.id == decision.policy_id)
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state = PolicyState(path, clock=time.time, sleeper=time.sleep)
    except (OSError, PolicyStateUnavailableError) as exc:
        raise ReadOnlyHttpError("budget-exhausted") from exc
    return inspect_patent_source(validated, policy, HttpPolicyEnforcer(registry, state))


class _ArgumentParser(argparse.ArgumentParser):
    """Keep argparse's validation without reflecting rejected argument values."""

    def error(self, _message: str) -> NoReturn:
        self.exit(2, "ERROR invalid command-line arguments\n")


def main() -> int:
    parser = _ArgumentParser(
        description="Read an official patent page or validate a redacted prior-art evidence-pack draft"
    )
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument(
        "--fixture", action="store_true", help="use the synthetic admission fixture"
    )
    parser.add_argument("--lookup-url", help="read one public KIPRIS/KIPO HTTPS page")
    args = parser.parse_args()
    if sum((args.path is not None, args.fixture, args.lookup_url is not None)) != 1:
        parser.error("choose exactly one of path, --fixture, or --lookup-url")
    try:
        if args.lookup_url is not None:
            result = _live(args.lookup_url)
        else:
            result = review_case(load_payload(FIXTURE if args.fixture else args.path))
    except ReadOnlyHttpError as exc:
        print(json.dumps({"error": exc.status}), file=sys.stderr)
        match exc.status:
            case "invalid-request":
                return 2
            case (
                "policy-disabled"
                | "policy-expired"
                | "robots-denied"
                | "terms-unverified"
                | "license-unverified"
                | "budget-exhausted"
            ):
                return 3
            case (
                "response-invalid"
                | "upstream-403-manual"
                | "upstream-429-manual"
                | "upstream-unavailable"
            ):
                return 4
            case unreachable:
                assert_never(unreachable)
    except OSError:
        parser.exit(2, "ERROR input or read-only source is unavailable\n")
    except json.JSONDecodeError:
        parser.exit(2, "ERROR input must be valid JSON\n")
    except (ValueError, RuntimeError):
        parser.exit(2, "ERROR invalid input or unavailable source\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/patent-prior-art-evidence-pack/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = (
    "kgov/patent-prior-art-evidence-pack/review-case/v1",
    "kgov/patent-prior-art-evidence-pack/inspect-source/v1",
)


if __name__ == "__main__":
    raise SystemExit(main())
