#!/usr/bin/env python3
"""국가법령정보 법령 검색 exact read-only operation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import (  # noqa: E402
    JsonContractError,
    JsonOperation,
    load_fixture,
    query_json,
    run_json_cli,
)

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "korean-law-bill-research.json"


def _required_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise JsonContractError(f"{label} must be an object")
    return value


def _required_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise JsonContractError(f"{label} must be an array")
    return value


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JsonContractError(f"{label} must be a non-empty string")
    return value.strip()


def _decimal_integer(value: Any, label: str) -> int:
    text = str(value) if isinstance(value, int) and not isinstance(value, bool) else _required_string(value, label)
    if not text.isascii() or not text.isdecimal():
        raise JsonContractError(f"{label} must be a decimal integer")
    return int(text)


def _validate_params(params: Mapping[str, str]) -> None:
    if _decimal_integer(params["display"], "display") not in range(1, 101):
        raise JsonContractError("display parameter is outside its allowed range")
    if _decimal_integer(params["page"], "page") not in range(1, 10_001):
        raise JsonContractError("page parameter is outside its allowed range")
    law_id = params.get("LID")
    if law_id is not None and (len(law_id) != 6 or not law_id.isascii() or not law_id.isdecimal()):
        raise JsonContractError("LID parameter must contain six ASCII digits")


def _project(payload: Any, params: Mapping[str, str]) -> list[dict[str, Any]]:
    root = _required_mapping(payload, "law search response")
    envelope = _required_mapping(root.get("LawSearch"), "LawSearch")
    records = _required_list(envelope.get("law"), "LawSearch.law")
    total, page, page_size = _decimal_integer(envelope.get("totalCnt"), "LawSearch.totalCnt"), int(params["page"]), int(params["display"])
    if len(records) != max(0, min(page_size, total - ((page - 1) * page_size))):
        raise JsonContractError("upstream page count is inconsistent")
    projected: list[dict[str, Any]] = []
    for record_value in records:
        record = _required_mapping(record_value, "law record")
        projected.append({
            "law_name": _required_string(record.get("법령명한글"), "법령명한글"),
            "law_id": _required_string(record.get("법령ID"), "법령ID"),
            "effective_date": _required_string(record.get("시행일자"), "시행일자"),
        })
    return projected


_project.__module__ = "kgov_runtime.capabilities.korean_law_bill_research"
_validate_params.__module__ = "kgov_runtime.capabilities.korean_law_bill_research"

OPERATION = JsonOperation(
    id="kgov/korean-law-bill-research/search-laws/v1",
    contract_id="kgov/korean-law-bill-research/v1",
    endpoint="https://www.law.go.kr/DRF/lawSearch.do",
    policy_id="law-go-kr-drf-api",
    allowed_params=frozenset({"query", "search", "LID", "display", "page"}),
    required_params=frozenset({"query"}),
    credential_env="LAW_OC",
    credential_param="OC",
    max_records=100,
    projector=_project,
    parameter_validator=_validate_params,
    default_params={"target": "law", "type": "JSON", "display": "20", "page": "1"},
)


def query(*, endpoint: str | None = None, params: Mapping[str, Any] | None = None, opener: Callable[..., Any] | None = None, resolver: Callable[[str], Iterable[Any]] | None = None) -> dict[str, Any]:
    return query_json(OPERATION, endpoint=endpoint, params=params, opener=opener, resolver=resolver)


def fixture_result() -> dict[str, Any]:
    return load_fixture(OPERATION, FIXTURE)


def main() -> int:
    return run_json_cli(OPERATION, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
