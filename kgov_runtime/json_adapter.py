"""Exact-operation harness for bounded read-only JSON retrieval."""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlsplit
from urllib.request import Request

from .cli import SafeArgumentParser
from .http import DEFAULT_MAX_BYTES, DEFAULT_TIMEOUT, USER_AGENT, _default_resolver as default_resolver, build_url, safe_urlopen, validate_public_https_url
from .redaction import contains_direct_identifier

LEGAL_PROFILES = {
    "korean-legal-citation-law-search": ("https://www.law.go.kr/DRF/lawSearch.do", "eflaw", frozenset({"query", "search", "LID", "display", "page"})),
    "korean-legal-citation-law-detail": ("https://www.law.go.kr/DRF/lawService.do", "eflawjosub", frozenset({"MST", "efYd", "JO", "HANG", "HO", "MOK"})),
    "korean-legal-citation-precedent-search": ("https://www.law.go.kr/DRF/lawSearch.do", "prec", frozenset({"query", "search", "display", "page", "sort", "date", "prncYd", "nb", "curt", "org", "JO"})),
    "korean-legal-citation-precedent-detail": ("https://www.law.go.kr/DRF/lawService.do", "prec", frozenset({"ID"})),
}
OPERATION_PROFILES = MappingProxyType({
    "kgov/korean-law-bill-research/search-laws/v1": ("kgov/korean-law-bill-research/v1", "https://www.law.go.kr/DRF/lawSearch.do", "law-go-kr-drf-api", frozenset({"query", "search", "LID", "display", "page"}), frozenset({"query"}), "LAW_OC", "OC", 100, (("display", "20"), ("page", "1"), ("target", "law"), ("type", "JSON")), ("kgov_runtime.capabilities.korean_law_bill_research", "_project"), ("kgov_runtime.capabilities.korean_law_bill_research", "_validate_params")),
    "kgov/kosis-official-statistics/query-statistics/v1": ("kgov/kosis-official-statistics/v1", "https://kosis.kr/openapi/Param/statisticsParameterData.do", "kosis-statistics-api", frozenset({"orgId", "tblId", "itmId", "objL1", "prdSe", "startPrdDe", "endPrdDe", "newEstPrdCnt"}), frozenset({"orgId", "tblId", "itmId", "objL1", "prdSe", "startPrdDe", "endPrdDe"}), "KOSIS_API_KEY", "apiKey", 100, (("format", "json"), ("jsonVD", "Y"), ("method", "getList")), ("kgov_runtime.capabilities.kosis_official_statistics", "_project"), ("kgov_runtime.capabilities.kosis_official_statistics", "_validate_params")),
    "kgov/public-procurement-research/query-order-plans/v1": ("kgov/public-procurement-research/v1", "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService", "data-go-kr-order-plan-api", frozenset({"pageNo", "numOfRows", "inqryDiv", "inqryBgnDt", "inqryEndDt"}), frozenset({"pageNo", "numOfRows", "inqryDiv", "inqryBgnDt", "inqryEndDt"}), "DATA_GO_KR_API_KEY", "serviceKey", 100, (("type", "json"),), ("kgov_runtime.capabilities.public_procurement_research", "_project"), ("kgov_runtime.capabilities.public_procurement_research", "_validate_params")),
    "kgov/disaster-geospatial-brief/query-village-forecast/v1": ("kgov/disaster-geospatial-brief/v1", "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst", "data-go-kr-village-forecast-api", frozenset({"pageNo", "numOfRows", "base_date", "base_time", "nx", "ny"}), frozenset({"pageNo", "numOfRows", "base_date", "base_time", "nx", "ny"}), "KMA_OPEN_API_KEY", "serviceKey", 100, (("dataType", "JSON"),), ("kgov_runtime.capabilities.disaster_geospatial_brief", "_project"), ("kgov_runtime.capabilities.disaster_geospatial_brief", "_validate_params")),
})


class JsonContractError(ValueError):
    """Raised when JSON input or output violates an operation contract."""


class JsonTransportError(RuntimeError):
    """Raised when a bounded read-only request cannot complete."""


class BlockedOperationError(RuntimeError):
    """Raised when no exact live dataset operation has been approved."""


@dataclass(frozen=True, slots=True)
class JsonAdapterConfig:
    slug: str
    default_endpoint: str
    allowed_hosts: frozenset[str]
    credential_env: str | None = None
    credential_param: str | None = None
    default_params: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class JsonOperation:
    id: str
    contract_id: str
    endpoint: str
    policy_id: str
    allowed_params: frozenset[str]
    required_params: frozenset[str]
    credential_env: str
    credential_param: str
    max_records: int
    projector: Callable[[Any, Mapping[str, str]], list[dict[str, Any]]]
    parameter_validator: Callable[[Mapping[str, str]], None]
    default_params: Mapping[str, Any] | None = None


def parse_params(values: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise JsonContractError("parameter must use key=value form")
        key, raw = value.split("=", 1)
        if not key.strip():
            raise JsonContractError("parameter key must not be empty")
        if key in params:
            raise JsonContractError("duplicate parameter is forbidden")
        params[key] = raw
    return params


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonContractError("duplicate JSON key is forbidden")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise JsonContractError("non-finite JSON number is forbidden")


def _walk_json(value: Any, depth: int = 0, nodes: list[int] | None = None) -> None:
    counter = [0] if nodes is None else nodes
    counter[0] += 1
    if depth > 20 or counter[0] > 20_000:
        raise JsonContractError("JSON structural limit exceeded")
    if isinstance(value, str):
        if len(value) > 20_000 or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise JsonContractError("JSON string limit or Unicode contract violated")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise JsonContractError("non-finite JSON number is forbidden")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _walk_json(key, depth + 1, counter)
            _walk_json(child, depth + 1, counter)
        return
    if isinstance(value, list):
        for child in value:
            _walk_json(child, depth + 1, counter)


def strict_json_loads(body: bytes) -> Any:
    value = json.loads(body.decode("utf-8", errors="strict"), object_pairs_hook=_reject_duplicate, parse_constant=_reject_constant)
    _walk_json(value)
    return value


def _parameter_strings(params: Mapping[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in params.items():
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise JsonContractError("parameter value must be a string or integer")
        text = str(value)
        if not text.strip() or len(text) > 200 or any(unicodedata.category(char).startswith("C") for char in text):
            raise JsonContractError("parameter value violates bounded string requirements")
        normalized[key] = text
    return normalized


def _request_json(
    request: tuple[str, set[str], Mapping[str, str], tuple[str, str]],
    opener: Callable[..., Any],
    resolver: Callable[[str], Iterable[Any]],
) -> Any:
    endpoint, allowed_hosts, params, credential = request
    credential_env, credential_param = credential
    if not os.environ.get(credential_env):
        raise JsonTransportError("required credential is missing")
    validate_public_https_url(endpoint, allowed_hosts, resolver=resolver)
    url = build_url(endpoint, params, credential_env=credential_env, credential_param=credential_param)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=DEFAULT_TIMEOUT) as response:
            body = response.read(DEFAULT_MAX_BYTES + 1)
    except (HTTPError, URLError):
        raise JsonTransportError("read-only request failed") from None
    if len(body) > DEFAULT_MAX_BYTES:
        raise JsonTransportError("response exceeded bounded size")
    return strict_json_loads(body)


def _safety_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join("-" if unicodedata.category(char) == "Pd" or "MINUS" in unicodedata.name(char, "") else char for char in normalized if not unicodedata.category(char).startswith("C"))
    return re.sub(r"\s*([@.\-])\s*", r"\1", " ".join(normalized.split()))


def _ensure_safe_output(value: Any, operation: JsonOperation) -> None:
    credential = os.environ.get(operation.credential_env, "")
    encoded = (credential, quote(credential, safe=""), quote_plus(credential)) if credential else ()
    secrets = tuple(_safety_text(item) for item in encoded) + tuple(_safety_text(re.sub(r"%[0-9A-Fa-f]{2}", lambda match: match.group().lower(), item)) for item in encoded)

    def unsafe_text(text: str) -> None:
        normalized = _safety_text(text)
        if contains_direct_identifier(normalized):
            raise JsonContractError("output contains a direct identifier")
        if any(secret and (secret in normalized or "".join(secret.split()) in "".join(normalized.split())) for secret in secrets):
            raise JsonContractError("output contains reflected credential material")

    def visit(item: Any) -> None:
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise JsonContractError("output mapping key must be a string")
                normalized_key = _safety_text(key)
                if normalized_key.casefold() in {"raw", "body", "text", "headers", "cookie", "authorization", "credential"}:
                    raise JsonContractError("forbidden output key")
                unsafe_text(key)
                visit(child)
            return
        if type(item) is list:
            for child in item:
                visit(child)
            return
        if type(item) is str:
            unsafe_text(item)
            return
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is float and math.isfinite(item):
            return
        raise JsonContractError("output contains a non-JSON value")

    visit(value)


def _result(operation: JsonOperation, payload: Any, execution_mode: str, params: Mapping[str, str]) -> dict[str, Any]:
    records = operation.projector(payload, MappingProxyType(dict(params)))
    if type(records) is not list or any(type(record) is not dict for record in records):
        raise JsonContractError("projected records must be an exact list of dictionaries")
    if len(records) > operation.max_records:
        raise JsonContractError("upstream record limit exceeded")
    result = {
        "contract_id": operation.contract_id,
        "execution_mode": execution_mode,
        "status": "fixture-validated" if execution_mode == "synthetic-fixture" else "records-retrieved",
        "count": len(records),
        "records": records,
        "source_receipt": {"operation_id": operation.id, "policy_id": operation.policy_id, "endpoint": operation.endpoint},
        "manual_review_required": True,
    }
    _ensure_safe_output(result, operation)
    return result


def load_fixture(operation: JsonOperation, path: Path) -> dict[str, Any]:
    _verify_operation(operation)
    return _result(operation, strict_json_loads(path.read_bytes()), "synthetic-fixture", _parameter_strings(operation.default_params or {}))


def _legal_profile(config: JsonAdapterConfig) -> tuple[str, frozenset[str]]:
    profile = LEGAL_PROFILES.get(config.slug)
    if profile is None:
        raise JsonContractError("unsupported compatibility config")
    endpoint, target, allowed = profile
    if (config.default_endpoint, config.allowed_hosts, config.credential_env, config.credential_param, dict(config.default_params or {})) != (endpoint, frozenset({"law.go.kr"}), "LAW_OC", "OC", {"target": target, "type": "JSON"}):
        raise JsonContractError("unsupported compatibility config")
    return endpoint, allowed


def _verify_operation(operation: JsonOperation) -> None:
    signature = (operation.contract_id, operation.endpoint, operation.policy_id, operation.allowed_params, operation.required_params, operation.credential_env, operation.credential_param, operation.max_records, tuple(sorted((operation.default_params or {}).items())), (operation.projector.__module__, operation.projector.__qualname__), (operation.parameter_validator.__module__, operation.parameter_validator.__qualname__))
    if OPERATION_PROFILES.get(operation.id) is None or type(operation.allowed_params) is not frozenset or type(operation.required_params) is not frozenset or type(operation.default_params) is not dict or signature != OPERATION_PROFILES.get(operation.id):
        raise JsonContractError("operation does not match the approved operation registry")


def query_json(
    operation: JsonOperation | JsonAdapterConfig,
    *,
    endpoint: str | None = None,
    params: Mapping[str, Any] | None = None,
    opener: Callable[..., Any] | None = None,
    resolver: Callable[[str], Iterable[Any]] | None = None,
) -> dict[str, Any]:
    if endpoint is not None:
        raise JsonContractError("endpoint override is forbidden")
    if isinstance(operation, JsonOperation):
        _verify_operation(operation)
    supplied = _parameter_strings(params or {})
    active_opener = opener or safe_urlopen
    active_resolver = resolver or default_resolver
    if isinstance(operation, JsonAdapterConfig):
        legal_endpoint, allowed = _legal_profile(operation)
        unknown = set(supplied) - allowed
        if unknown:
            raise JsonContractError("unknown parameter is forbidden")
        merged = _parameter_strings(operation.default_params or {}) | supplied
        payload = _request_json((legal_endpoint, {"law.go.kr"}, merged, ("LAW_OC", "OC")), active_opener, active_resolver)
        return {"count": len(payload) if isinstance(payload, list) else 1, "records": payload if isinstance(payload, list) else [payload]}
    unknown = set(supplied) - operation.allowed_params
    if unknown:
        raise JsonContractError("unknown parameter is forbidden")
    merged = _parameter_strings(operation.default_params or {}) | supplied
    if operation.required_params - set(merged):
        raise JsonContractError("required parameter is missing")
    immutable_params = MappingProxyType(dict(merged))
    operation.parameter_validator(immutable_params)
    if _parameter_strings(immutable_params) != merged:
        raise JsonContractError("validated parameters changed during validation")
    host = urlsplit(operation.endpoint).hostname
    if host is None:
        raise JsonContractError("operation endpoint is invalid")
    payload = _request_json((operation.endpoint, {host}, merged, (operation.credential_env, operation.credential_param)), active_opener, active_resolver)
    return _result(operation, payload, "official-live", immutable_params)


def run_json_cli(operation: JsonOperation, fixture_path: Path) -> int:
    parser = SafeArgumentParser(description=f"Read-only operation: {operation.id}")
    parser.add_argument("--param", action="append", default=[], help="repeatable allowlisted key=value parameter")
    parser.add_argument("--fixture", action="store_true", help="use the repository fixture; no network or credential")
    args = parser.parse_args()
    try:
        result = load_fixture(operation, fixture_path) if args.fixture else query_json(operation, params=parse_params(args.param))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0
