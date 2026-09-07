#!/usr/bin/env python3
"""Fail-closed admission guard for redacted civil-complaint draft workflows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Final, Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.redaction import contains_direct_identifier  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "civil-complaint-triage-draft.json"
REQUIRED_FIELDS = frozenset({"title", "body", "channel", "received_at", "redaction_status"})
MAX_INPUT_FILE_BYTES = 100_000
MAX_TITLE_CHARACTERS = 200
MAX_BODY_CHARACTERS = 20_000
MAX_CHANNEL_CHARACTERS = 50


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_received_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("received_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("received_at must include a timezone offset")


def admit_request(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("input must be a JSON object")
    unknown = sorted(set(payload) - REQUIRED_FIELDS)
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")

    title = _required_string(payload, "title")
    body = _required_string(payload, "body")
    channel = _required_string(payload, "channel")
    received_at = _required_string(payload, "received_at")
    redaction_status = _required_string(payload, "redaction_status")

    if len(title) > MAX_TITLE_CHARACTERS:
        raise ValueError(f"title exceeds {MAX_TITLE_CHARACTERS} characters")
    if len(body) > MAX_BODY_CHARACTERS:
        raise ValueError(f"body exceeds {MAX_BODY_CHARACTERS} characters")
    if len(channel) > MAX_CHANNEL_CHARACTERS:
        raise ValueError(f"channel exceeds {MAX_CHANNEL_CHARACTERS} characters")
    if redaction_status != "redacted":
        raise ValueError("redacted input is required")
    _parse_received_at(received_at)

    combined = f"{title}\n{body}"
    if contains_direct_identifier(combined):
        raise ValueError("potential personal identifier remains in input")

    return {
        "accepted": True,
        "basic_identifier_scan": "no-match-not-proof-of-redaction",
        "input_characters": len(body),
        "manual_review_required": True,
        "permitted_output": "draft-only",
        "title_characters": len(title),
        "workflow_steps": [
            "민원 요약과 요청사항 분리",
            "관련 법령·공식 안내·소관 후보 확인",
            "답변 초안과 불확실성 작성",
            "담당 공무원 검토 후 발송 여부 결정",
        ],
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
    parser = argparse.ArgumentParser(description="Validate redacted civil-complaint draft input")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="use the synthetic repository fixture")
    args = parser.parse_args()
    if args.fixture and args.path:
        parser.error("path cannot be combined with --fixture")
    if not args.fixture and args.path is None:
        parser.error("path is required unless --fixture is used")
    try:
        payload = _load_payload(FIXTURE if args.fixture else args.path)
        result = admit_request(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/civil-complaint-triage-draft/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/civil-complaint-triage-draft/admit-draft/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
