#!/usr/bin/env python3
"""Safe KIPRIS/KIPO lookup plus fail-closed prior-art evidence-pack admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html import unescape
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.http import fetch_text  # noqa: E402
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
    ROOT
    / "tests"
    / "fixtures"
    / "capabilities"
    / "patent-prior-art-evidence-pack.json"
)
# Exact official hosts only. Do not use parent-domain suffix matching here.
LOOKUP_ALLOWED_HOSTS = set(CONTRACT.allowed_hosts)
LOOKUP_OUTPUT_KEYS = frozenset(
    {"url", "status", "content_type", "title", "content_length", "sha256"}
)
CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "key",
        "service_key",
        "servicekey",
        "token",
    }
)


def review_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a redacted, user-supplied evidence-pack draft without network access."""

    return admit_review(payload, CONTRACT)


def _safe_lookup_display_url(url: str) -> str:
    """Return only scheme/host/path so query values never appear in receipts."""

    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path or '/'}"


def _validated_lookup_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https":
        raise ValueError("only HTTPS lookup URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("embedded URL credentials are forbidden")
    if host not in LOOKUP_ALLOWED_HOSTS:
        raise ValueError(f"host is not allowlisted: {host or '<missing>'}")
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
    return url


def inspect_patent_source(
    url: str,
    *,
    opener: Callable[..., Any] | None = None,
    resolver: Callable[[str], Iterable[Any]] | None = None,
) -> dict[str, Any]:
    """Read one public KIPRIS/KIPO page with bounded, redirect-rejecting HTTP."""

    validated = _validated_lookup_url(url)
    kwargs: dict[str, Any] = {"allowed_hosts": LOOKUP_ALLOWED_HOSTS}
    if opener is not None:
        kwargs["opener"] = opener
    if resolver is not None:
        kwargs["resolver"] = resolver
    response = fetch_text(validated, **kwargs)
    text = response.pop("text")
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", unescape(match.group(1))).strip() if match else ""
    body = text.encode("utf-8")
    result = {
        "url": _safe_lookup_display_url(validated),
        "status": response.get("status"),
        "content_type": response.get("content_type"),
        "title": title,
        "content_length": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    unexpected = set(result) - LOOKUP_OUTPUT_KEYS
    if unexpected:
        raise RuntimeError("lookup receipt schema drifted")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read an official patent page or validate a redacted prior-art evidence-pack draft"
    )
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="use the synthetic admission fixture")
    parser.add_argument("--lookup-url", help="read one public KIPRIS/KIPO HTTPS page")
    args = parser.parse_args()
    if sum((args.path is not None, args.fixture, args.lookup_url is not None)) != 1:
        parser.error("choose exactly one of path, --fixture, or --lookup-url")
    try:
        if args.lookup_url is not None:
            result = inspect_patent_source(args.lookup_url)
        else:
            result = review_case(load_payload(FIXTURE if args.fixture else args.path))
    except OSError:
        parser.exit(2, "ERROR input or read-only source is unavailable\n")
    except json.JSONDecodeError:
        parser.exit(2, "ERROR input must be valid JSON\n")
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
