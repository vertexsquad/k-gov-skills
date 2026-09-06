#!/usr/bin/env python3
"""나라장터 발주계획 exact read-only operation."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonContractError, JsonOperation, load_fixture, query_json, run_json_cli  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "public-procurement-research.json"


def _date_param(value: str) -> date:
    if len(value) != 8 or not value.isascii() or not value.isdecimal():
        raise JsonContractError("procurement date parameter is invalid")
    try:
        return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:]}")
    except ValueError:
        raise JsonContractError("procurement date parameter is invalid") from None


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
    if _decimal_integer(params["pageNo"], "pageNo") not in range(1, 10_001):
        raise JsonContractError("pageNo parameter is outside its allowed range")
    if _decimal_integer(params["numOfRows"], "numOfRows") not in range(1, 101):
        raise JsonContractError("numOfRows parameter is outside its allowed range")
    if params["inqryDiv"] not in {"1", "2"}:
        raise JsonContractError("inqryDiv parameter is unsupported")
    if _date_param(params["inqryBgnDt"]) > _date_param(params["inqryEndDt"]):
        raise JsonContractError("procurement date range is reversed")


def _project(payload: Any, params: Mapping[str, str]) -> list[dict[str, Any]]:
    root = _required_mapping(payload, "procurement response")
    response = _required_mapping(root.get("response"), "response")
    header = _required_mapping(response.get("header"), "response.header")
    if _required_string(header.get("resultCode"), "resultCode") != "00":
        raise JsonContractError("upstream procurement status is not successful")
    body = _required_mapping(response.get("body"), "response.body")
    records = _required_list(_required_mapping(body.get("items"), "response.body.items").get("item"), "response.body.items.item")
    total = _decimal_integer(body.get("totalCount"), "totalCount")
    page = _decimal_integer(body.get("pageNo"), "pageNo")
    page_size = _decimal_integer(body.get("numOfRows"), "numOfRows")
    if "pageNo" in params and (page != int(params["pageNo"]) or page_size != int(params["numOfRows"])):
        raise JsonContractError("upstream page metadata does not match the request")
    if len(records) != max(0, min(page_size, total - ((page - 1) * page_size))):
        raise JsonContractError("upstream page count is inconsistent")
    projected: list[dict[str, Any]] = []
    for value in records:
        record = _required_mapping(value, "procurement record")
        projected.append({
            "plan_number": _required_string(record.get("orderPlanUntyNo"), "orderPlanUntyNo"),
            "business_name": _required_string(record.get("bizNm"), "bizNm"),
            "ordering_agency": _required_string(record.get("orderInsttNm"), "orderInsttNm"),
            "planned_amount": _required_string(record.get("orderPlanAmt"), "orderPlanAmt"),
            "planned_date": _required_string(record.get("orderPlanDate"), "orderPlanDate"),
        })
    return projected


_project.__module__ = "kgov_runtime.capabilities.public_procurement_research"
_validate_params.__module__ = "kgov_runtime.capabilities.public_procurement_research"

OPERATION = JsonOperation(
    id="kgov/public-procurement-research/query-order-plans/v1",
    contract_id="kgov/public-procurement-research/v1",
    endpoint="https://apis.data.go.kr/1230000/ao/OrderPlanSttusService",
    policy_id="data-go-kr-order-plan-api",
    allowed_params=frozenset({"pageNo", "numOfRows", "inqryDiv", "inqryBgnDt", "inqryEndDt"}),
    required_params=frozenset({"pageNo", "numOfRows", "inqryDiv", "inqryBgnDt", "inqryEndDt"}),
    credential_env="DATA_GO_KR_API_KEY",
    credential_param="serviceKey",
    max_records=100,
    projector=_project,
    parameter_validator=_validate_params,
    default_params={"type": "json"},
)


def query(*, endpoint: str | None = None, params: Mapping[str, Any] | None = None, opener: Callable[..., Any] | None = None, resolver: Callable[[str], Iterable[Any]] | None = None) -> dict[str, Any]:
    return query_json(OPERATION, endpoint=endpoint, params=params, opener=opener, resolver=resolver)


def fixture_result() -> dict[str, Any]:
    return load_fixture(OPERATION, FIXTURE)


def main() -> int:
    return run_json_cli(OPERATION, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
