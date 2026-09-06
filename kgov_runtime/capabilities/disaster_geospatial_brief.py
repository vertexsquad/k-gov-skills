#!/usr/bin/env python3
"""기상청 단기예보 exact read-only operation."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonContractError, JsonOperation, load_fixture, query_json, run_json_cli  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "disaster-geospatial-brief.json"
BASE_TIMES = frozenset({"0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"})


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
    if _decimal_integer(params["nx"], "nx") not in range(1, 150):
        raise JsonContractError("nx parameter is outside its allowed range")
    if _decimal_integer(params["ny"], "ny") not in range(1, 254):
        raise JsonContractError("ny parameter is outside its allowed range")
    base_date = params["base_date"]
    if len(base_date) != 8 or not base_date.isascii() or not base_date.isdecimal():
        raise JsonContractError("base_date parameter is invalid")
    try:
        date.fromisoformat(f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:]}")
    except ValueError:
        raise JsonContractError("base_date parameter is invalid") from None
    if params["base_time"] not in BASE_TIMES:
        raise JsonContractError("base_time parameter is unsupported")


def _project(payload: Any, params: Mapping[str, str]) -> list[dict[str, Any]]:
    root = _required_mapping(payload, "forecast response")
    response = _required_mapping(root.get("response"), "response")
    header = _required_mapping(response.get("header"), "response.header")
    if _required_string(header.get("resultCode"), "resultCode") != "00":
        raise JsonContractError("upstream forecast status is not successful")
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
        record = _required_mapping(value, "forecast record")
        if isinstance(record.get("nx"), bool) or not isinstance(record.get("nx"), int) or isinstance(record.get("ny"), bool) or not isinstance(record.get("ny"), int):
            raise JsonContractError("forecast grid coordinates must be integers")
        projected.append({
            "category": _required_string(record.get("category"), "category"),
            "forecast_date": _required_string(record.get("fcstDate"), "fcstDate"),
            "forecast_time": _required_string(record.get("fcstTime"), "fcstTime"),
            "forecast_value": _required_string(record.get("fcstValue"), "fcstValue"),
            "grid_x": record.get("nx"),
            "grid_y": record.get("ny"),
        })
    return projected


_project.__module__ = "kgov_runtime.capabilities.disaster_geospatial_brief"
_validate_params.__module__ = "kgov_runtime.capabilities.disaster_geospatial_brief"

OPERATION = JsonOperation(
    id="kgov/disaster-geospatial-brief/query-village-forecast/v1",
    contract_id="kgov/disaster-geospatial-brief/v1",
    endpoint="https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
    policy_id="data-go-kr-village-forecast-api",
    allowed_params=frozenset({"pageNo", "numOfRows", "base_date", "base_time", "nx", "ny"}),
    required_params=frozenset({"pageNo", "numOfRows", "base_date", "base_time", "nx", "ny"}),
    credential_env="KMA_OPEN_API_KEY",
    credential_param="serviceKey",
    max_records=100,
    projector=_project,
    parameter_validator=_validate_params,
    default_params={"dataType": "JSON"},
)


def query(*, endpoint: str | None = None, params: Mapping[str, Any] | None = None, opener: Callable[..., Any] | None = None, resolver: Callable[[str], Iterable[Any]] | None = None) -> dict[str, Any]:
    return query_json(OPERATION, endpoint=endpoint, params=params, opener=opener, resolver=resolver)


def fixture_result() -> dict[str, Any]:
    return load_fixture(OPERATION, FIXTURE)


def main() -> int:
    return run_json_cli(OPERATION, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
