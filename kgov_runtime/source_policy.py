"""Deterministic, fail-closed authorization for catalog v6 source policies.

# noqa: SIZE_OK -- Issue #24 limits this policy engine and its tests to exactly two owned paths;
# splitting the catalog parser or authorization model would violate that explicit file scope.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal, Mapping, TypeAlias, assert_never
from urllib.parse import unquote_to_bytes, urlsplit

JSONValue: TypeAlias = "None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]"
PathMatch: TypeAlias = Literal["exact", "prefix"]
OutputMode: TypeAlias = Literal["none", "link-only", "projected-records"]

_POLICY_FIELDS: Final = (("id", "revision", "enabled", "institution", "channel", "scope", "robots", "terms", "rate_limit", "response", "license", "retention"), ("review",))
_CONTRACT_FIELDS: Final = (("id", "capability_slug", "module", "kind", "network_mode", "default_operation_id", "operations", "exit_codes", "forbidden_output_keys"), ())
_OPERATION_FIELDS: Final = (("id", "schema_status", "source_policy_ids", "source_output_mode"), ("fixture_argv", "input_schema", "output_schema"))
_SLUG: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_BAD_ESCAPE: Final = re.compile(r"%(?![0-9A-Fa-f]{2})")
_MAX_URL_LENGTH: Final = 2048
_MAX_PATH_LENGTH: Final = 2048
_RUNTIME_KINDS: Final = frozenset({"local-document", "retrieval", "admission", "verification", "hybrid"})
_NETWORK_MODES: Final = frozenset({"none", "optional-live", "blocked", "mixed"})
_OUTPUT_MODES: Final = frozenset({"none", "link-only", "projected-records"})
_EXIT_CODES: Final = {"success": 0, "review_blocked": 1, "input_error": 2,
                      "policy_blocked": 3, "upstream_error": 4}
_FORBIDDEN_OUTPUT_KEYS: Final = ["authorization", "body", "cookie", "credential",
                                 "headers", "raw", "text"]
_SCHEMA_TYPES: Final = frozenset({"object", "array", "string", "integer", "number", "boolean", "null"})
_SCHEMA_FIELDS: Final = {
    "object": frozenset({"required", "properties", "additionalProperties"}),
    "array": frozenset({"items", "minItems", "maxItems"}),
    "string": frozenset({"minLength", "maxLength", "format"}),
    "integer": frozenset({"minimum", "maximum"}),
    "number": frozenset({"minimum", "maximum"}),
    "boolean": frozenset(),
    "null": frozenset(),
}


@dataclass(frozen=True, slots=True)
class SourcePolicyError(ValueError):
    code: str
    location: str

    def __str__(self) -> str:
        return f"{self.code}: {self.location}"


@dataclass(frozen=True, slots=True)
class PolicyEvidence:
    reviewed_on: date
    expires_on: date
    evidence_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceScope:
    origins: tuple[str, ...]
    path_rules: tuple[tuple[PathMatch, str], ...]
    methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RobotsPolicy:
    status: Literal["unreviewed", "required", "documented-api-exemption"]
    evidence_url: str | None = None


@dataclass(frozen=True, slots=True)
class TermsPolicy:
    status: Literal["unreviewed", "manual-review", "allowed", "prohibited"]
    url: str | None = None


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    status: Literal["unreviewed", "reviewed"]
    requests: int | None = None
    per_seconds: int | None = None
    burst: int | None = None
    max_wait_seconds: int | float | None = None


@dataclass(frozen=True, slots=True)
class ResponsePolicy:
    status: Literal["unreviewed", "reviewed"]
    max_bytes: int | None = None
    media_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LicensePolicy:
    status: Literal["unreviewed", "manual-review", "reviewed"]
    url: str | None = None
    allowed_output_modes: tuple[Literal["link-only", "projected-records"], ...] = ()
    redistribution: Literal["link-only", "allowed"] | None = None


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    raw_content: Literal["none"]
    receipts: Literal["metadata-only"]


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    id: str
    revision: int
    enabled: bool
    institution: str
    channel: Literal["api", "web"]
    scope: SourceScope
    robots: RobotsPolicy
    terms: TermsPolicy
    rate_limit: RateLimitPolicy
    response: ResponsePolicy
    license: LicensePolicy
    retention: RetentionPolicy
    review: PolicyEvidence | None
    digest: str


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    code: str
    policy_id: str | None
    policy_digest: str | None


@dataclass(frozen=True, slots=True)
class _Operation:
    id: str
    policy_ids: tuple[str, ...]
    output_mode: OutputMode


@dataclass(frozen=True, slots=True)
class SourcePolicyRegistry:
    policies: tuple[SourcePolicy, ...]
    _operations: tuple[_Operation, ...]
    _on_date: date

    @classmethod
    def from_catalog(cls, catalog: Mapping[str, JSONValue], *, on_date: date) -> SourcePolicyRegistry:
        if catalog.get("schema_version") != 6:
            raise SourcePolicyError("unsupported-schema", "/schema_version")
        raw_policies = _list(catalog.get("source_policies"), "/source_policies")
        policies = tuple(_parse_policy(_node(item, "/source_policies"), on_date) for item in raw_policies)
        ids = [policy.id for policy in policies]
        if len(ids) != len(set(ids)):
            raise SourcePolicyError("duplicate-policy", "/source_policies")
        operations = _parse_operations(catalog.get("runtime_contracts"),
                                       catalog.get("shared_capabilities"), tuple(ids))
        return cls(policies, operations, on_date)

    def authorize(self, url: str, operation_id: str, method: str = "GET") -> AccessDecision:
        target = _request_target(url)
        if target is None:
            return AccessDecision(False, "invalid-url", None, None)
        operation = next((item for item in self._operations if item.id == operation_id), None)
        if operation is None:
            return AccessDecision(False, "unknown-operation", None, None)
        origin, path = target
        matches: list[tuple[int, SourcePolicy]] = []
        for policy in self.policies:
            if policy.id not in operation.policy_ids or method not in policy.scope.methods or origin not in policy.scope.origins:
                continue
            specificity = _path_specificity(policy.scope.path_rules, path)
            if specificity is not None:
                matches.append((specificity, policy))
        if not matches:
            return AccessDecision(False, "missing-policy", None, None)
        best = max(length for length, _ in matches)
        selected = [policy for length, policy in matches if length == best]
        if len(selected) != 1:
            return AccessDecision(False, "ambiguous-policy", None, None)
        return _authorize_policy(selected[0], operation.output_mode, self._on_date)


def _error(location: str) -> SourcePolicyError:
    return SourcePolicyError("invalid-policy", location)


def _node(value: JSONValue, location: str) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise _error(location)
    return value


def _list(value: JSONValue, location: str) -> list[JSONValue]:
    if not isinstance(value, list):
        raise _error(location)
    return value


def _shape(value: dict[str, JSONValue], shape: tuple[tuple[str, ...], tuple[str, ...]], location: str) -> None:
    required, optional = shape
    if any(field not in value for field in required) or set(value) - set(required) - set(optional):
        raise _error(location)


def _text(value: JSONValue, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(location)
    return value


def _integer(value: JSONValue, location: str) -> int:
    if type(value) is not int or value < 1:
        raise _error(location)
    return value


def canonical_policy_digest(policy: Mapping[str, JSONValue]) -> str:
    """Return the SHA-256 digest of a policy encoded as canonical JSON."""
    try:
        encoded = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise _error("/source_policies") from exc
    return hashlib.sha256(encoded).hexdigest()


def _https_url(value: JSONValue, location: str, *, origin: bool = False) -> str:
    text = _text(value, location)
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as exc:
        raise _error(location) from exc
    host = parsed.hostname
    authority = host if port is None else f"{host}:{port}"
    valid = (len(text) <= _MAX_URL_LENGTH and _strict_percent_decode(text) is not None
             and parsed.scheme == "https" and host is not None and _valid_hostname(host)
             and parsed.netloc == authority and parsed.username is None and parsed.password is None
             and "#" not in text and port in (None, 443))
    if origin:
        valid = valid and "?" not in text and "#" not in text and not parsed.path and not parsed.query and port is None
    if not valid:
        raise _error(location)
    return text


def _valid_hostname(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return (host == host.lower() and host.isascii() and not host.endswith(".")
                and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in host.split(".")))
    return False


def _policy_path(value: JSONValue, match: PathMatch, location: str) -> str:
    path = _text(value, location)
    if _unsafe_path(path) or not path.startswith("/") or "?" in path or "#" in path or (path.endswith("/") and not (match == "prefix" and path == "/")):
        raise _error(location)
    return path


def _normalize_unreserved_path(path: str) -> str:
    """Normalize only unreserved escapes after the path passes safety checks."""
    def decode(escape: re.Match[str]) -> str:
        character = chr(int(escape[0][1:], 16))
        return character if character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~" else escape[0]

    return re.sub(r"%[0-9A-Fa-f]{2}", decode, path)


def _unsafe_characters(value: str) -> bool:
    return any(character.isspace() or ord(character) < 32 or ord(character) == 127
               or 0xD800 <= ord(character) <= 0xDFFF for character in value)


def _strict_percent_decode(value: str) -> str | None:
    if _BAD_ESCAPE.search(value) or _unsafe_characters(value):
        return None
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return None
    if "%" in decoded or _unsafe_characters(decoded):
        return None
    return decoded


def _unsafe_path(path: str) -> bool:
    if len(path) > _MAX_PATH_LENGTH:
        return True
    decoded = _strict_percent_decode(path)
    if decoded is None:
        return True
    return ("\\" in path or "//" in path or any(part in {".", ".."} for part in path.split("/"))
            or decoded.count("/") != path.count("/") or "\\" in decoded or "\0" in decoded
            or any(part in {".", ".."} for part in decoded.split("/")))


def _status_node(raw: JSONValue, shapes: Mapping[str, tuple[str, ...]], location: str) -> tuple[dict[str, JSONValue], str]:
    node = _node(raw, location)
    status = _text(node.get("status"), f"{location}/status")
    required = shapes.get(status)
    if required is None:
        raise _error(f"{location}/status")
    _shape(node, (required, ()), location)
    return node, status


def _parse_scope(raw: JSONValue) -> SourceScope:
    node = _node(raw, "/scope")
    _shape(node, (("origins", "path_rules", "methods"), ()), "/scope")
    origins = tuple(_https_url(value, "/scope/origins", origin=True) for value in _list(node["origins"], "/scope/origins"))
    if not origins or len(origins) != len(set(origins)) or node["methods"] != ["GET"]:
        raise _error("/scope")
    rules: list[tuple[PathMatch, str]] = []
    for raw_rule in _list(node["path_rules"], "/scope/path_rules"):
        rule = _node(raw_rule, "/scope/path_rules")
        _shape(rule, (("match", "path"), ()), "/scope/path_rules")
        try:
            match rule["match"]:
                case "exact" | "prefix" as kind:
                    path = _policy_path(rule["path"], kind, "/scope/path_rules/path")
                case unreachable:
                    assert_never(unreachable)
        except AssertionError as exc:
            raise _error("/scope/path_rules/match") from exc
        normalized_path = _normalize_unreserved_path(path)
        if any(_normalize_unreserved_path(previous_path) == normalized_path for _, previous_path in rules):
            raise _error("/scope/path_rules")
        rules.append((kind, path))
    if not rules:
        raise _error("/scope/path_rules")
    return SourceScope(origins, tuple(rules), ("GET",))


def _policy_date(value: JSONValue, location: str) -> date:
    text = _text(value, location)
    if _DATE.fullmatch(text) is None:
        raise _error(location)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise _error(location) from exc
    if parsed.isoformat() != text:
        raise _error(location)
    return parsed


def _parse_review(raw: JSONValue, on_date: date) -> PolicyEvidence:
    node = _node(raw, "/review")
    _shape(node, (("reviewed_on", "expires_on", "evidence_urls"), ()), "/review")
    reviewed = _policy_date(node["reviewed_on"], "/review/reviewed_on")
    expires = _policy_date(node["expires_on"], "/review/expires_on")
    urls = tuple(_https_url(value, "/review/evidence_urls") for value in _list(node["evidence_urls"], "/review/evidence_urls"))
    if reviewed > on_date or reviewed > expires or not urls or len(urls) != len(set(urls)):
        raise _error("/review")
    return PolicyEvidence(reviewed, expires, urls)


def _parse_robots(raw: JSONValue) -> RobotsPolicy:
    node, status = _status_node(raw, {"unreviewed": ("status",), "required": ("status",), "documented-api-exemption": ("status", "evidence_url")}, "/robots")
    match status:
        case "unreviewed" | "required":
            return RobotsPolicy(status)
        case "documented-api-exemption":
            return RobotsPolicy(status, _https_url(node["evidence_url"], "/robots/evidence_url"))
        case unreachable:
            assert_never(unreachable)


def _parse_terms(raw: JSONValue) -> TermsPolicy:
    node, status = _status_node(raw, {"unreviewed": ("status",), "manual-review": ("status", "url"), "allowed": ("status", "url"), "prohibited": ("status", "url")}, "/terms")
    match status:
        case "unreviewed":
            return TermsPolicy(status)
        case "manual-review" | "allowed" | "prohibited":
            return TermsPolicy(status, _https_url(node["url"], "/terms/url"))
        case unreachable:
            assert_never(unreachable)


def _parse_rate(raw: JSONValue) -> RateLimitPolicy:
    node, status = _status_node(raw, {"unreviewed": ("status",), "reviewed": ("status", "requests", "per_seconds", "burst", "max_wait_seconds")}, "/rate_limit")
    if status == "unreviewed":
        return RateLimitPolicy(status)
    values = tuple(_integer(node[key], f"/rate_limit/{key}") for key in ("requests", "per_seconds", "burst"))
    wait = node["max_wait_seconds"]
    if type(wait) not in (int, float) or not math.isfinite(wait) or wait < 0:
        raise _error("/rate_limit/max_wait_seconds")
    return RateLimitPolicy(status, *values, wait)


def _parse_response(raw: JSONValue) -> ResponsePolicy:
    node, status = _status_node(raw, {"unreviewed": ("status",), "reviewed": ("status", "max_bytes", "media_types")}, "/response")
    if status == "unreviewed":
        return ResponsePolicy(status)
    media = tuple(_text(value, "/response/media_types") for value in _list(node["media_types"], "/response/media_types"))
    if not media or len(media) != len(set(media)) or any(value != value.lower() for value in media):
        raise _error("/response/media_types")
    return ResponsePolicy(status, _integer(node["max_bytes"], "/response/max_bytes"), media)


def _parse_license(raw: JSONValue) -> LicensePolicy:
    shapes = {"unreviewed": ("status",), "manual-review": ("status", "url"), "reviewed": ("status", "url", "allowed_output_modes", "redistribution")}
    node, status = _status_node(raw, shapes, "/license")
    if status == "unreviewed":
        return LicensePolicy(status)
    url = _https_url(node["url"], "/license/url")
    if status == "manual-review":
        return LicensePolicy(status, url)
    modes = tuple(_text(value, "/license/allowed_output_modes") for value in _list(node["allowed_output_modes"], "/license/allowed_output_modes"))
    redistribution = _text(node["redistribution"], "/license/redistribution")
    if not modes or len(modes) != len(set(modes)) or any(mode not in {"link-only", "projected-records"} for mode in modes) or redistribution not in {"link-only", "allowed"}:
        raise _error("/license")
    return LicensePolicy(status, url, modes, redistribution)


def _parse_policy(raw: dict[str, JSONValue], on_date: date) -> SourcePolicy:
    _shape(raw, _POLICY_FIELDS, "/source_policies")
    policy_id = _text(raw["id"], "/source_policies/id")
    institution = _text(raw["institution"], "/source_policies/institution")
    if not _SLUG.fullmatch(policy_id) or len(policy_id) > 64 or len(institution) > 120 or type(raw["enabled"]) is not bool:
        raise _error("/source_policies")
    try:
        match raw["channel"]:
            case "api" | "web" as channel:
                pass
            case unreachable:
                assert_never(unreachable)
    except AssertionError as exc:
        raise _error("/source_policies/channel") from exc
    retention = _node(raw["retention"], "/retention")
    _shape(retention, (("raw_content", "receipts"), ()), "/retention")
    if retention != {"raw_content": "none", "receipts": "metadata-only"}:
        raise _error("/retention")
    review = _parse_review(raw["review"], on_date) if "review" in raw else None
    digest = canonical_policy_digest(raw)
    return SourcePolicy(policy_id, _integer(raw["revision"], "/revision"), raw["enabled"], institution, channel,
                        _parse_scope(raw["scope"]), _parse_robots(raw["robots"]), _parse_terms(raw["terms"]),
                        _parse_rate(raw["rate_limit"]), _parse_response(raw["response"]), _parse_license(raw["license"]),
                        RetentionPolicy("none", "metadata-only"), review, digest)


def _schema_value_matches(value: JSONValue, declared: str, nullable: bool) -> bool:
    if value is None:
        return nullable or declared == "null"
    predicates = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: type(item) is int,
        "number": lambda item: type(item) is int or (type(item) is float and math.isfinite(item)),
        "boolean": lambda item: type(item) is bool,
        "null": lambda item: item is None,
    }
    return predicates[declared](value)


def _parse_schema(raw: JSONValue, location: str, depth: int = 0) -> None:
    if depth > 32:
        raise _error(location)
    schema = _node(raw, location)
    raw_type = schema.get("type")
    nullable = False
    if isinstance(raw_type, str):
        declared = raw_type
    elif (isinstance(raw_type, list) and len(raw_type) == 2
          and isinstance(raw_type[0], str) and raw_type[1] == "null"):
        declared = raw_type[0]
        nullable = True
    else:
        raise _error(location)
    if declared not in _SCHEMA_TYPES or (nullable and declared == "null"):
        raise _error(location)
    allowed = _SCHEMA_FIELDS[declared] | {"type", "enum", "const"}
    if set(schema) - allowed or ("enum" in schema and "const" in schema):
        raise _error(location)
    if "enum" in schema:
        enum = _list(schema["enum"], location)
        try:
            identities = tuple(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
                               for value in enum)
        except (TypeError, ValueError) as exc:
            raise _error(location) from exc
        if (not enum or len(identities) != len(set(identities))
                or not all(_schema_value_matches(value, declared, nullable) for value in enum)):
            raise _error(location)
    if "const" in schema:
        if not _schema_value_matches(schema["const"], declared, nullable):
            raise _error(location)
        try:
            json.dumps(schema["const"], allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise _error(location) from exc
    if declared == "object":
        required = tuple(_text(value, location) for value in _list(schema.get("required"), location))
        properties = _node(schema.get("properties"), location)
        property_order = {name: index for index, name in enumerate(properties)}
        required_order = [property_order[name] for name in required if name in property_order]
        if (schema.get("additionalProperties") is not False or len(required) != len(set(required))
                or not set(required) <= set(properties) or required_order != sorted(required_order)):
            raise _error(location)
        for child in properties.values():
            _parse_schema(child, location, depth + 1)
    if declared == "array":
        _parse_schema(schema.get("items"), location, depth + 1)
    bounds = (("minLength", "maxLength") if declared == "string" else
              ("minItems", "maxItems") if declared == "array" else
              ("minimum", "maximum") if declared in {"integer", "number"} else None)
    if bounds is not None:
        minimum = schema.get(bounds[0])
        maximum = schema.get(bounds[1])
        length_bounds = declared in {"string", "array"}
        valid_minimum = bounds[0] not in schema or (type(minimum) is int and (not length_bounds or minimum >= 0))
        valid_maximum = bounds[1] not in schema or (type(maximum) is int and (not length_bounds or maximum >= 0))
        if not length_bounds:
            valid_minimum = bounds[0] not in schema or _schema_value_matches(minimum, "number", False)
            valid_maximum = bounds[1] not in schema or _schema_value_matches(maximum, "number", False)
        if not valid_minimum or not valid_maximum or (minimum is not None and maximum is not None and minimum > maximum):
            raise _error(location)
    if "format" in schema:
        format_name = _text(schema["format"], location)
        if format_name not in {"date", "date-time", "https-url", "sha256"}:
            raise _error(location)


def _reject_forbidden_schema_properties(raw: JSONValue, location: str) -> None:
    schema = _node(raw, location)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        if set(properties) & set(_FORBIDDEN_OUTPUT_KEYS):
            raise _error(location)
        for child in properties.values():
            _reject_forbidden_schema_properties(child, location)
    if "items" in schema:
        _reject_forbidden_schema_properties(schema["items"], location)


def _parse_operations(raw: JSONValue, raw_capabilities: JSONValue,
                      policy_ids: tuple[str, ...]) -> tuple[_Operation, ...]:
    contracts = _list(raw, "/runtime_contracts")
    capabilities = _list(raw_capabilities, "/shared_capabilities")
    if not contracts or len(contracts) != len(capabilities):
        raise _error("/runtime_contracts")
    known_policies = frozenset(policy_ids)
    policy_order = {policy_id: index for index, policy_id in enumerate(policy_ids)}
    parsed_operations: list[_Operation] = []
    contract_ids: list[str] = []
    capability_slugs: list[str] = []
    for raw_contract, raw_capability in zip(contracts, capabilities, strict=True):
        contract = _node(raw_contract, "/runtime_contracts")
        capability = _node(raw_capability, "/shared_capabilities")
        _shape(contract, _CONTRACT_FIELDS, "/runtime_contracts")
        slug = _text(contract["capability_slug"], "/runtime_contracts/capability_slug")
        contract_id = _text(contract["id"], "/runtime_contracts/id")
        module = _text(contract["module"], "/runtime_contracts/module")
        kind = _text(contract["kind"], "/runtime_contracts/kind")
        network = _text(contract["network_mode"], "/runtime_contracts/network_mode")
        default_id = _text(contract["default_operation_id"], "/runtime_contracts/default_operation_id")
        capability_slug = _text(capability.get("slug"), "/shared_capabilities/slug")
        capability_contract = _text(capability.get("runtime_contract_id"), "/shared_capabilities/runtime_contract_id")
        capability_refs = tuple(_text(value, "/shared_capabilities/source_policy_ids")
                                for value in _list(capability.get("source_policy_ids"), "/shared_capabilities/source_policy_ids"))
        valid_identity = (_SLUG.fullmatch(slug) is not None and capability_slug == slug
                          and contract_id == capability_contract == f"kgov/{slug}/v1"
                          and module == f"kgov_runtime.capabilities.{slug.replace('-', '_')}")
        if (not valid_identity or kind not in _RUNTIME_KINDS or network not in _NETWORK_MODES
                or len(capability_refs) != len(set(capability_refs))
                or not set(capability_refs) <= known_policies
                or list(capability_refs) != sorted(capability_refs, key=policy_order.__getitem__)):
            raise _error("/runtime_contracts")
        exit_codes = _node(contract["exit_codes"], "/runtime_contracts/exit_codes")
        _shape(exit_codes, (tuple(_EXIT_CODES), ()), "/runtime_contracts/exit_codes")
        if (any(type(exit_codes[key]) is not int for key in _EXIT_CODES)
                or exit_codes != _EXIT_CODES
                or _list(contract["forbidden_output_keys"], "/runtime_contracts/forbidden_output_keys") != _FORBIDDEN_OUTPUT_KEYS):
            raise _error("/runtime_contracts")
        raw_operations = _list(contract["operations"], "/runtime_contracts/operations")
        if not raw_operations:
            raise _error("/runtime_contracts/operations")
        contract_operations: list[_Operation] = []
        policy_union: list[str] = []
        for index, raw_operation in enumerate(raw_operations):
            operation = _node(raw_operation, "/runtime_contracts/operations")
            _shape(operation, _OPERATION_FIELDS, "/runtime_contracts/operations")
            operation_id = _text(operation["id"], "/runtime_contracts/operations/id")
            status = _text(operation["schema_status"], "/runtime_contracts/operations/schema_status")
            mode = _text(operation["source_output_mode"], "/runtime_contracts/operations/source_output_mode")
            refs = tuple(_text(value, "/runtime_contracts/operations/source_policy_ids")
                         for value in _list(operation["source_policy_ids"], "/runtime_contracts/operations/source_policy_ids"))
            if (re.fullmatch(rf"kgov/{re.escape(slug)}/[a-z0-9]+(?:-[a-z0-9]+)*/v1", operation_id) is None
                    or status not in {"declared", "active"} or mode not in _OUTPUT_MODES
                    or len(refs) != len(set(refs)) or not set(refs) <= known_policies
                    or list(refs) != sorted(refs, key=policy_order.__getitem__)
                    or (index == 0 and operation.get("fixture_argv") != ["--fixture"])
                    or (index > 0 and "fixture_argv" in operation)):
                raise _error("/runtime_contracts/operations")
            if status == "declared" and ("input_schema" in operation or "output_schema" in operation):
                raise _error("/runtime_contracts/operations")
            if status == "active":
                _parse_schema(operation.get("input_schema"), "/runtime_contracts/operations/input_schema")
                _parse_schema(operation.get("output_schema"), "/runtime_contracts/operations/output_schema")
                _reject_forbidden_schema_properties(operation["output_schema"],
                                                    "/runtime_contracts/operations/output_schema")
                if not refs and mode in {"link-only", "projected-records"}:
                    raise _error("/runtime_contracts/operations")
            for policy_id in refs:
                if policy_id not in policy_union:
                    policy_union.append(policy_id)
            contract_operations.append(_Operation(operation_id, refs, mode))
        has_linked = any(operation.policy_ids for operation in contract_operations)
        has_local = any(not operation.policy_ids for operation in contract_operations)
        network_valid = ((network in {"none", "blocked"} and not has_linked)
                         or (network == "optional-live" and has_linked)
                         or (network == "mixed" and has_linked and has_local))
        if (default_id != contract_operations[0].id or tuple(policy_union) != capability_refs
                or not network_valid
                or (network == "none" and any(operation.output_mode != "none" for operation in contract_operations))):
            raise _error("/runtime_contracts")
        parsed_operations.extend(contract_operations)
        contract_ids.append(contract_id)
        capability_slugs.append(slug)
    operation_ids = [operation.id for operation in parsed_operations]
    if len(contract_ids) != len(set(contract_ids)) or len(capability_slugs) != len(set(capability_slugs)):
        raise _error("/runtime_contracts")
    if len(operation_ids) != len(set(operation_ids)):
        raise SourcePolicyError("duplicate-operation", "/runtime_contracts")
    return tuple(parsed_operations)


def _request_target(url: str) -> tuple[str, str] | None:
    if len(url) > _MAX_URL_LENGTH or "#" in url or _strict_percent_decode(url) is None:
        return None
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname
    authority = host if port is None else f"{host}:{port}"
    if (parsed.scheme.lower() != "https" or host is None or not host.isascii()
            or parsed.netloc.lower() != authority or parsed.username is not None
            or parsed.password is not None or port not in (None, 443) or _unsafe_path(parsed.path)):
        return None
    return f"https://{host.lower()}", _normalize_unreserved_path(parsed.path or "/")


def _path_specificity(rules: tuple[tuple[PathMatch, str], ...], path: str) -> int | None:
    normalized_rules = ((kind, _normalize_unreserved_path(rule)) for kind, rule in rules)
    lengths = [len(rule) for kind, rule in normalized_rules if (kind == "exact" and path == rule) or (kind == "prefix" and (rule == "/" or path == rule or path.startswith(f"{rule}/")))]
    return max(lengths) if lengths else None


def _authorize_policy(policy: SourcePolicy, output_mode: OutputMode, on_date: date) -> AccessDecision:
    def blocked(code: str) -> AccessDecision:
        return AccessDecision(False, code, policy.id, policy.digest)

    if not policy.enabled:
        return blocked("policy-disabled")
    if policy.review is None:
        return blocked("review-required")
    if policy.review.reviewed_on > on_date or policy.review.expires_on < on_date:
        return blocked("review-stale")
    match policy.robots.status:
        case "unreviewed":
            return blocked("robots-review-required")
        case "required" | "documented-api-exemption":
            pass
        case unreachable:
            assert_never(unreachable)
    match policy.terms.status:
        case "unreviewed":
            return blocked("terms-review-required")
        case "manual-review":
            return blocked("terms-manual-review")
        case "prohibited":
            return blocked("terms-prohibited")
        case "allowed":
            pass
        case unreachable:
            assert_never(unreachable)
    match policy.rate_limit.status:
        case "unreviewed":
            return blocked("rate-limit-review-required")
        case "reviewed":
            pass
        case unreachable:
            assert_never(unreachable)
    match policy.response.status:
        case "unreviewed":
            return blocked("response-review-required")
        case "reviewed":
            pass
        case unreachable:
            assert_never(unreachable)
    match policy.license.status:
        case "unreviewed":
            return blocked("license-review-required")
        case "manual-review":
            return blocked("license-manual-review")
        case "reviewed":
            pass
        case unreachable:
            assert_never(unreachable)
    if output_mode not in policy.license.allowed_output_modes:
        return blocked("license-operation-mismatch")
    return AccessDecision(True, "allowed", policy.id, policy.digest)
