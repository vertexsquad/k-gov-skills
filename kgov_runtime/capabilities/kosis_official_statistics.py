#!/usr/bin/env python3
"""KOSIS 통계자료 exact read-only operation."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Final, Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonContractError, JsonOperation, load_fixture, query_json, run_json_cli  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "kosis-official-statistics.json"


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


def _period_key(period: str, value: str) -> tuple[int, int, int]:
    if len(value) < 4 or not value.isascii() or not value.isdecimal():
        raise JsonContractError("KOSIS period is invalid")
    year = int(value[:4])
    if year == 0:
        raise JsonContractError("KOSIS period is invalid")
    if period == "Y" and len(value) == 4:
        return year, 0, 0
    if period == "H" and len(value) == 6 and value[4:] in {"01", "02"}:
        return year, int(value[4:]), 0
    if period == "Q" and len(value) == 6 and value[4:] in {"01", "02", "03", "04"}:
        return year, int(value[4:]), 0
    try:
        if period == "M" and len(value) == 6:
            parsed = date(year, int(value[4:]), 1)
            return parsed.year, parsed.month, 0
        if period == "D" and len(value) == 8:
            parsed = date(year, int(value[4:6]), int(value[6:]))
            return parsed.year, parsed.month, parsed.day
    except ValueError:
        raise JsonContractError("KOSIS period is invalid") from None
    raise JsonContractError("KOSIS period is invalid")


def _validate_params(params: Mapping[str, str]) -> None:
    for key in ("orgId", "tblId", "itmId", "objL1"):
        if len(params[key]) > 80:
            raise JsonContractError("KOSIS identifier parameter exceeds its bound")
    start = _period_key(params["prdSe"], params["startPrdDe"])
    end = _period_key(params["prdSe"], params["endPrdDe"])
    if start > end:
        raise JsonContractError("KOSIS period range is reversed")
    if "newEstPrdCnt" in params and _decimal_integer(params["newEstPrdCnt"], "newEstPrdCnt") not in range(1, 101):
        raise JsonContractError("newEstPrdCnt parameter is outside its allowed range")


def _project(payload: Any, _params: Mapping[str, str]) -> list[dict[str, Any]]:
    records = _required_list(payload, "KOSIS response")
    projected: list[dict[str, Any]] = []
    for value in records:
        record = _required_mapping(value, "KOSIS record")
        projected.append({
            "table_name": _required_string(record.get("TBL_NM"), "TBL_NM"),
            "period": _required_string(record.get("PRD_DE"), "PRD_DE"),
            "category": _required_string(record.get("C1_NM"), "C1_NM"),
            "item": _required_string(record.get("ITM_NM"), "ITM_NM"),
            "value": _required_string(record.get("DT"), "DT"),
        })
    return projected


_project.__module__ = "kgov_runtime.capabilities.kosis_official_statistics"
_validate_params.__module__ = "kgov_runtime.capabilities.kosis_official_statistics"

OPERATION = JsonOperation(
    id="kgov/kosis-official-statistics/query-statistics/v1",
    contract_id="kgov/kosis-official-statistics/v1",
    endpoint="https://kosis.kr/openapi/Param/statisticsParameterData.do",
    policy_id="kosis-statistics-api",
    allowed_params=frozenset({"orgId", "tblId", "itmId", "objL1", "prdSe", "startPrdDe", "endPrdDe", "newEstPrdCnt"}),
    required_params=frozenset({"orgId", "tblId", "itmId", "objL1", "prdSe", "startPrdDe", "endPrdDe"}),
    credential_env="KOSIS_API_KEY",
    credential_param="apiKey",
    max_records=100,
    projector=_project,
    parameter_validator=_validate_params,
    default_params={"method": "getList", "format": "json", "jsonVD": "Y"},
)


def query(*, endpoint: str | None = None, params: Mapping[str, Any] | None = None, opener: Callable[..., Any] | None = None, resolver: Callable[[str], Iterable[Any]] | None = None) -> dict[str, Any]:
    return query_json(OPERATION, endpoint=endpoint, params=params, opener=opener, resolver=resolver)


def fixture_result() -> dict[str, Any]:
    return load_fixture(OPERATION, FIXTURE)


def main() -> int:
    return run_json_cli(OPERATION, FIXTURE)


RUNTIME_CONTRACT_ID: Final[str] = "kgov/kosis-official-statistics/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/kosis-official-statistics/query-statistics/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
