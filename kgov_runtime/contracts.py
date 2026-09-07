"""Frozen catalog contracts for Skill inputs and successful JSON output.

Active schemas come from the catalog and remain closed; declared operations use
the predecessor's minimum fallback until a reviewed binding activates them.
Existing capability parsers retain business-input validation.

# noqa: SIZE_OK -- Issues #32/#33 keep frozen schemas and their parser together
# instead of adding another registry module or moving contract logic into the
# 22 capability exports.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Final, Literal, Mapping, NewType, assert_never

from kgov_runtime.json_adapter import JsonOperation, _safety_text, strict_json_loads
from kgov_runtime.review_admission import ReviewContract
from kgov_runtime.source_policy import (
    JSONValue,
    OutputMode,
    _list,
    _node,
    _parse_operations,
    _schema_value_matches,
    _text,
    _https_url,
)
from kgov_runtime.source_policy import (
    _Operation as CatalogOperation,
)

type JSONDocument = dict[str, JSONValue]
type SchemaType = Literal[
    "object", "array", "string", "integer", "number", "boolean", "null"
]
type SchemaFormat = Literal["date", "date-time", "https-url", "sha256"]
ContractId = NewType("ContractId", str)
OperationId = NewType("OperationId", str)
PolicyId = NewType("PolicyId", str)
CATALOG: Final = Path(__file__).resolve().parents[1] / "catalog/domain-skills.json"


class RuntimeKind(StrEnum):
    LOCAL_DOCUMENT = "local-document"
    RETRIEVAL = "retrieval"
    ADMISSION = "admission"
    VERIFICATION = "verification"
    HYBRID = "hybrid"


class NetworkMode(StrEnum):
    NONE = "none"
    OPTIONAL_LIVE = "optional-live"
    BLOCKED = "blocked"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class ContractError(ValueError):
    code: str
    location: str

    def __str__(self) -> str:
        return f"{self.code}: {self.location}"


@dataclass(frozen=True, slots=True)
class Schema:
    """Immutable standard JSON-Schema subset."""

    kind: SchemaType
    properties: tuple[tuple[str, Schema], ...] = ()
    items: Schema | None = None
    const_json: str | None = None
    nullable: bool = False
    enum: tuple[str, ...] = ()
    additional_properties: bool = True
    required: tuple[str, ...] | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_items: int | None = None
    max_items: int | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    format: SchemaFormat | None = None

    def document(self) -> JSONDocument:
        result: JSONDocument = {
            "type": [self.kind, "null"] if self.nullable else self.kind
        }
        if self.const_json is not None:
            result["const"] = strict_json_loads(self.const_json.encode())
        if self.enum:
            result["enum"] = list(self.enum)
        match self.kind:
            case "object":
                result.update(
                    properties={
                        key: child.document() for key, child in self.properties
                    },
                    required=list(
                        self.required
                        if self.required is not None
                        else (key for key, _ in self.properties)
                    ),
                    additionalProperties=self.additional_properties,
                )
            case "array":
                result["items"] = (
                    self.items.document() if self.items is not None else {}
                )
            case "string" | "integer" | "number" | "boolean" | "null":
                pass
            case unreachable:
                assert_never(unreachable)
        for key, value in (
            ("minLength", self.min_length),
            ("maxLength", self.max_length),
            ("minItems", self.min_items),
            ("maxItems", self.max_items),
            ("minimum", self.minimum),
            ("maximum", self.maximum),
            ("format", self.format),
        ):
            if value is not None:
                result[key] = value
        return result

    def validate(self, value: JSONValue, location: str = "") -> None:
        if not _schema_value_matches(value, self.kind, self.nullable):
            raise ContractError("schema-type", location)
        if (
            self.const_json is not None
            and json.dumps(value, sort_keys=True) != self.const_json
        ):
            raise ContractError("schema-const", location)
        if self.enum and value not in self.enum:
            raise ContractError("schema-enum", location)
        match value:
            case dict():
                if not self.additional_properties:
                    declared = {key for key, _ in self.properties}
                    unknown = next((key for key in value if key not in declared), None)
                    if unknown is not None:
                        raise ContractError(
                            "schema-additional-property", f"{location}/{unknown}"
                        )
                required = (
                    self.required
                    if self.required is not None
                    else tuple(key for key, _ in self.properties)
                )
                for key, child in self.properties:
                    if key in required and key not in value:
                        raise ContractError("schema-required", f"{location}/{key}")
                    if key in value:
                        child.validate(value[key], f"{location}/{key}")
            case list():
                if (
                    self.min_items is not None
                    and len(value) < self.min_items
                    or self.max_items is not None
                    and len(value) > self.max_items
                ):
                    raise ContractError("schema-length", location)
                if self.items is not None:
                    for index, child in enumerate(value):
                        self.items.validate(child, f"{location}/{index}")
            case str():
                if (
                    self.min_length is not None
                    and len(value) < self.min_length
                    or self.max_length is not None
                    and len(value) > self.max_length
                ):
                    raise ContractError("schema-length", location)
                if self.format is not None and not _matches_format(self.format, value):
                    raise ContractError("schema-format", location)
            case int() | float():
                if (
                    self.minimum is not None
                    and value < self.minimum
                    or self.maximum is not None
                    and value > self.maximum
                ):
                    raise ContractError("schema-range", location)
            case bool() | None:
                pass
            case unreachable:
                assert_never(unreachable)


def record(properties: Mapping[str, Schema]) -> Schema:
    return Schema("object", properties=tuple(properties.items()))


def constant(value: str | bool) -> Schema:
    match value:
        case bool():
            return Schema("boolean", const_json=json.dumps(value))
        case str():
            return Schema("string", const_json=json.dumps(value))
        case unreachable:
            assert_never(unreachable)


STRING: Final = Schema("string")
INTEGER: Final = Schema("integer")
STRINGS: Final = Schema("array", items=STRING)
RECORDS: Final = Schema("array", items=Schema("object"))
_DATE_TIME: Final = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)


def _matches_format(name: SchemaFormat, value: str) -> bool:
    match name:
        case "date":
            try:
                return date.fromisoformat(value).isoformat() == value
            except ValueError:
                return False
        case "date-time":
            if _DATE_TIME.fullmatch(value) is None:
                return False
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return False
            return True
        case "https-url":
            try:
                _https_url(value, "/format")
            except ValueError:
                return False
            return True
        case "sha256":
            return re.fullmatch(r"[0-9a-f]{64}", value) is not None
        case unreachable:
            assert_never(unreachable)


def _schema_format(value: JSONValue, location: str) -> SchemaFormat | None:
    if value is None:
        return None
    if value == "date":
        return "date"
    if value == "date-time":
        return "date-time"
    if value == "https-url":
        return "https-url"
    if value == "sha256":
        return "sha256"
    raise ContractError("schema-format", location)


def _schema(raw: JSONValue, location: str) -> Schema:
    node = _node(raw, location)
    declared = node.get("type")
    nullable = False
    if isinstance(declared, list):
        if (
            len(declared) != 2
            or not isinstance(declared[0], str)
            or declared[1] != "null"
        ):
            raise ContractError("schema-type", f"{location}/type")
        declared, nullable = declared[0], True
    if not isinstance(declared, str) or declared not in {
        "object",
        "array",
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }:
        raise ContractError("schema-type", f"{location}/type")
    properties: tuple[tuple[str, Schema], ...] = ()
    items = None
    additional = True
    match declared:
        case "object":
            raw_properties = _node(node.get("properties"), f"{location}/properties")
            required = tuple(
                _text(value, f"{location}/required")
                for value in _list(node.get("required"), f"{location}/required")
            )
            if any(key not in raw_properties for key in required):
                raise ContractError("schema-required", f"{location}/required")
            properties = tuple(
                (key, _schema(value, f"{location}/properties/{key}"))
                for key, value in raw_properties.items()
            )
            if type(node.get("additionalProperties")) is not bool:
                raise ContractError(
                    "schema-additional-properties",
                    f"{location}/additionalProperties",
                )
            additional = node["additionalProperties"]
        case "array":
            items = _schema(node.get("items"), f"{location}/items")
        case "string" | "integer" | "number" | "boolean" | "null":
            pass
        case unreachable:
            assert_never(unreachable)
    raw_enum = node.get("enum", [])
    enum = tuple(
        _text(value, f"{location}/enum")
        for value in _list(raw_enum, f"{location}/enum")
    )
    return Schema(
        kind=declared,
        properties=properties,
        items=items,
        const_json=json.dumps(node["const"], sort_keys=True)
        if "const" in node
        else None,
        nullable=nullable,
        enum=enum,
        additional_properties=additional,
        required=required if declared == "object" else None,
        min_length=node.get("minLength")
        if type(node.get("minLength")) is int
        else None,
        max_length=node.get("maxLength")
        if type(node.get("maxLength")) is int
        else None,
        min_items=node.get("minItems") if type(node.get("minItems")) is int else None,
        max_items=node.get("maxItems") if type(node.get("maxItems")) is int else None,
        minimum=node.get("minimum")
        if type(node.get("minimum")) in {int, float}
        else None,
        maximum=node.get("maximum")
        if type(node.get("maximum")) in {int, float}
        else None,
        format=_schema_format(node.get("format"), f"{location}/format"),
    )


@dataclass(frozen=True, slots=True)
class ExitCodes:
    """Catalog categories, not a remapping of legacy CLI failures."""

    success: int
    review_blocked: int
    input_error: int
    policy_blocked: int
    upstream_error: int


@dataclass(frozen=True, slots=True)
class OperationContract:
    id: OperationId
    schema_status: Literal["declared", "active"]
    source_policy_ids: tuple[PolicyId, ...]
    source_output_mode: OutputMode
    fixture_argv: tuple[str, ...] | None
    input_schema: Schema
    output_schema: Schema

    def catalog_document(self) -> JSONDocument:
        result: JSONDocument = {
            "id": self.id,
            "schema_status": self.schema_status,
            "source_policy_ids": list(self.source_policy_ids),
            "source_output_mode": self.source_output_mode,
        }
        if self.fixture_argv is not None:
            result["fixture_argv"] = list(self.fixture_argv)
        if self.schema_status == "active":
            result["input_schema"] = self.input_schema.document()
            result["output_schema"] = self.output_schema.document()
        return result


@dataclass(frozen=True, slots=True)
class RuntimeContract:
    id: ContractId
    capability_slug: str
    module: str
    kind: RuntimeKind
    network_mode: NetworkMode
    default_operation_id: OperationId
    operations: tuple[OperationContract, ...]
    exit_codes: ExitCodes
    forbidden_output_keys: tuple[str, ...]

    def catalog_document(self) -> JSONDocument:
        return {
            "id": self.id,
            "capability_slug": self.capability_slug,
            "module": self.module,
            "kind": self.kind.value,
            "network_mode": self.network_mode.value,
            "default_operation_id": self.default_operation_id,
            "operations": [
                operation.catalog_document() for operation in self.operations
            ],
            "exit_codes": asdict(self.exit_codes),
            "forbidden_output_keys": list(self.forbidden_output_keys),
        }

    def validate_output(self, operation_id: OperationId, output: JSONValue) -> None:
        operation = next(
            (item for item in self.operations if item.id == operation_id), None
        )
        if operation is None:
            raise ContractError("unknown-operation", operation_id)
        _reject_keys(output, self.forbidden_output_keys)
        operation.output_schema.validate(output)


def _reject_keys(value: JSONValue, forbidden: tuple[str, ...]) -> None:
    match value:
        case dict():
            for key, child in value.items():
                if _safety_text(key).casefold() in forbidden:
                    raise ContractError("forbidden-output-key", key)
                _reject_keys(child, forbidden)
        case list():
            for child in value:
                _reject_keys(child, forbidden)
        case float():
            if not math.isfinite(value):
                raise ContractError("nonfinite-output", "")
        case str() | int() | bool() | None:
            pass
        case unreachable:
            assert_never(unreachable)


def _output_schema(raw: Mapping[str, JSONValue], operation: CatalogOperation) -> Schema:
    """Schema families describe output, never catalog identity or network metadata."""
    common = {"manual_review_required": constant(True)}
    module = import_module(_text(raw["module"], "/module"))
    review = getattr(module, "CONTRACT", None)
    kind = RuntimeKind(_text(raw["kind"], "/kind"))
    receipt = record(
        {
            "operation_id": constant(operation.id),
            "policy_id": Schema("string", enum=operation.policy_ids),
            "policy_revision": INTEGER,
            "policy_digest": STRING,
            "outcome": constant("allowed"),
        }
    )
    match kind:
        case RuntimeKind.LOCAL_DOCUMENT:
            return record(
                common
                | {
                    "section_count": INTEGER,
                    "extracted_character_count": INTEGER,
                    "section_metadata": record(
                        {
                            "limit": INTEGER,
                            "truncated": Schema("boolean"),
                            "included": Schema(
                                "array",
                                items=record(
                                    {"ordinal": INTEGER, "character_count": INTEGER}
                                ),
                            ),
                        }
                    ),
                    "identifier_scan_status": STRING,
                    "text_emitted": constant(False),
                }
            )
        case RuntimeKind.VERIFICATION:
            return record(
                common
                | dict.fromkeys(
                    (
                        "as_of_date",
                        "permitted_output",
                        "execution_mode",
                        "verification_assurance",
                    ),
                    STRING,
                )
                | {
                    "schema_valid": constant(True),
                    "jurisdiction": constant("KR"),
                    "admission_passed": Schema("boolean"),
                    "verified_count": INTEGER,
                    "blocked_count": INTEGER,
                    "citations": RECORDS,
                    "source_receipts": Schema(
                        "array",
                        items=record(
                            {"source_receipt": replace(receipt, nullable=True)}
                        ),
                    ),
                }
            )
        case RuntimeKind.RETRIEVAL | RuntimeKind.HYBRID | RuntimeKind.ADMISSION:
            pass
        case unreachable:
            assert_never(unreachable)
    match operation.output_mode:
        case "projected-records":
            policies = operation.policy_ids
            return record(
                common
                | {
                    "contract_id": constant(_text(raw["id"], "/id")),
                    "execution_mode": STRING,
                    "status": STRING,
                    "count": INTEGER,
                    "records": RECORDS,
                    "source_receipt": record(
                        {
                            "operation_id": constant(operation.id),
                            "policy_id": Schema("string", enum=policies)
                            if policies
                            else Schema("null"),
                            "endpoint": STRING if policies else Schema("null"),
                        }
                    ),
                }
            )
        case "link-only":
            return record(
                common
                | dict.fromkeys(
                    ("url", "content_type", "title", "sha256", "execution_mode"), STRING
                )
                | {
                    "status": INTEGER,
                    "content_length": INTEGER,
                    "source_receipt": replace(
                        receipt, nullable=operation.id == raw["default_operation_id"]
                    ),
                }
            )
        case "none":
            pass
        case unreachable:
            assert_never(unreachable)
    if isinstance(review, ReviewContract):
        return record(
            common
            | dict.fromkeys(("fact_count", "source_ref_count"), INTEGER)
            | dict.fromkeys(
                (
                    "review_type",
                    "receipt_assurance",
                    "source_output_mode",
                    "basic_identifier_scan",
                ),
                STRING,
            )
            | dict.fromkeys(
                (
                    "manual_review_reasons",
                    "prohibited_decisions",
                    "required_checks",
                    "source_assurance_levels",
                ),
                STRINGS,
            )
            | {
                "accepted": constant(True),
                "status": constant("admitted-pending-human-review"),
                "permitted_output": constant(review.permitted_output),
            }
        )
    if hasattr(module, "build_evidence_pack"):
        return record(
            common
            | {
                "accepted": constant(True),
                "jurisdiction": constant("KR"),
                "permitted_output": constant("evidence-pack-draft-only"),
                "claims": RECORDS,
                "status_counts": Schema("object"),
                "claim_count": INTEGER,
            }
            | dict.fromkeys(
                (
                    "as_of_date",
                    "basic_identifier_scan",
                    "receipt_assurance",
                    "source_kind_assurance",
                ),
                STRING,
            )
        )
    if hasattr(module, "review_document"):
        return record(
            common
            | {
                "accepted": constant(True),
                "permitted_output": constant("draft-review-only"),
                "review_checks": Schema("object"),
                "document_type": STRING,
                "basic_identifier_scan": STRING,
            }
            | dict.fromkeys(
                (
                    "body_characters",
                    "purpose_characters",
                    "source_ref_count",
                    "title_characters",
                ),
                INTEGER,
            )
        )
    return record(
        common
        | {
            "accepted": constant(True),
            "permitted_output": constant("draft-only"),
            "basic_identifier_scan": STRING,
            "input_characters": INTEGER,
            "title_characters": INTEGER,
            "workflow_steps": STRINGS,
        }
    )


def _exit_code(value: JSONValue) -> int:
    if type(value) is not int:
        raise ContractError("exit-type", "/exit_codes")
    return value


def parse_contracts(catalog: Mapping[str, JSONValue]) -> tuple[RuntimeContract, ...]:
    """Reuse the v6 policy boundary; retain only frozen typed runtime contracts."""
    if (
        type(catalog.get("schema_version")) is not int
        or catalog.get("schema_version") != 6
    ):
        raise ContractError("schema-version", "/schema_version")
    policy_ids = tuple(
        _text(_node(item, "/source_policies")["id"], "/id")
        for item in _list(catalog.get("source_policies"), "/source_policies")
    )
    if len(policy_ids) != len(set(policy_ids)):
        raise ContractError("duplicate-policy", "/source_policies")
    parsed_operations = iter(
        _parse_operations(
            catalog.get("runtime_contracts"),
            catalog.get("shared_capabilities"),
            policy_ids,
        )
    )
    contracts: list[RuntimeContract] = []
    for item in _list(catalog.get("runtime_contracts"), "/runtime_contracts"):
        raw = _node(item, "/runtime_contracts")
        operations: list[OperationContract] = []
        for item in _list(raw["operations"], "/operations"):
            operation = _node(item, "/operations")
            parsed = next(parsed_operations)
            status = _text(operation["schema_status"], "/schema_status")
            if status not in {"declared", "active"}:
                raise ContractError("schema-status", "/schema_status")
            if status == "declared":
                input_schema = STRINGS
                output_schema = _output_schema(raw, parsed)
            else:
                input_schema = _schema(operation.get("input_schema"), "/input_schema")
                output_schema = _schema(
                    operation.get("output_schema"), "/output_schema"
                )
            operations.append(
                OperationContract(
                    OperationId(parsed.id),
                    status,
                    tuple(PolicyId(value) for value in parsed.policy_ids),
                    parsed.output_mode,
                    tuple(
                        _text(value, "/fixture_argv")
                        for value in _list(operation["fixture_argv"], "/fixture_argv")
                    )
                    if "fixture_argv" in operation
                    else None,
                    input_schema,
                    output_schema,
                )
            )
        exits = _node(raw["exit_codes"], "/exit_codes")
        # The shared boundary has proved exact integer types and the closed map.
        contracts.append(
            RuntimeContract(
                ContractId(_text(raw["id"], "/id")),
                _text(raw["capability_slug"], "/capability_slug"),
                _text(raw["module"], "/module"),
                RuntimeKind(_text(raw["kind"], "/kind")),
                NetworkMode(_text(raw["network_mode"], "/network_mode")),
                OperationId(
                    _text(raw["default_operation_id"], "/default_operation_id")
                ),
                tuple(operations),
                ExitCodes(**{key: _exit_code(value) for key, value in exits.items()}),
                tuple(
                    _text(value, "/forbidden_output_keys")
                    for value in _list(
                        raw["forbidden_output_keys"], "/forbidden_output_keys"
                    )
                ),
            )
        )
    return tuple(contracts)


def load_contracts(path: Path = CATALOG) -> tuple[RuntimeContract, ...]:
    return parse_contracts(_node(strict_json_loads(path.read_bytes()), "/"))


def validate_parity(contracts: tuple[RuntimeContract, ...]) -> None:
    """Compare metadata to the only SSOT, then check independent implementation exports."""
    if contracts != load_contracts():
        raise ContractError("catalog-parity", "/runtime_contracts")
    for contract in contracts:
        module: ModuleType = import_module(contract.module)
        operation_ids = tuple(operation.id for operation in contract.operations)
        if (
            getattr(module, "RUNTIME_CONTRACT_ID", None) != contract.id
            or getattr(module, "RUNTIME_OPERATION_IDS", None) != operation_ids
        ):
            raise ContractError("module-exports", contract.module)
        if hasattr(module, "OPERATION_ID") and module.OPERATION_ID not in operation_ids:
            raise ContractError("operation-constant", contract.module)
        if hasattr(module, "CONTRACT_ID") and module.CONTRACT_ID != contract.id:
            raise ContractError("contract-constant", contract.module)
        operation = getattr(module, "OPERATION", None)
        if isinstance(operation, JsonOperation) and (
            operation.id != contract.default_operation_id
            or operation.contract_id != contract.id
            or (operation.policy_id,) != contract.operations[0].source_policy_ids
        ):
            raise ContractError("json-operation", contract.module)
        if hasattr(module, "POLICY_ID") and not any(
            module.POLICY_ID in op.source_policy_ids for op in contract.operations
        ):
            raise ContractError("policy-constant", contract.module)
