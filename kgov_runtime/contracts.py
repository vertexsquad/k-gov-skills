"""Frozen catalog contracts; schemas describe CLI argv and successful JSON output.

Catalog operations remain declared, not activated Skill bindings. Output schemas
specify minimum guarantees, allow safe extensions, and never infer keys from a
fixture or a runtime result. Existing parsers own domain-input validation.

# noqa: SIZE_OK -- Issue #32 permits exactly one contract implementation file;
# the frozen schema templates stay with their catalog parser rather than adding
# an out-of-scope schema module or moving schema logic into capability exports.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, replace
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
)
from kgov_runtime.source_policy import (
    _Operation as CatalogOperation,
)

type JSONDocument = dict[str, JSONValue]
type SchemaType = Literal[
    "object", "array", "string", "integer", "number", "boolean", "null"
]
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
    """Immutable standard JSON-Schema subset; all declared properties are required."""

    kind: SchemaType
    properties: tuple[tuple[str, Schema], ...] = ()
    items: Schema | None = None
    const_json: str | None = None
    nullable: bool = False
    enum: tuple[str, ...] = ()

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
                    required=[key for key, _ in self.properties],
                    additionalProperties=True,
                )
            case "array":
                result["items"] = (
                    self.items.document() if self.items is not None else {}
                )
            case "string" | "integer" | "number" | "boolean" | "null":
                pass
            case unreachable:
                assert_never(unreachable)
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
                for key, child in self.properties:
                    if key not in value:
                        raise ContractError("schema-required", f"{location}/{key}")
                    child.validate(value[key], f"{location}/{key}")
            case list():
                if self.items is not None:
                    for index, child in enumerate(value):
                        self.items.validate(child, f"{location}/{index}")
            case str() | int() | float() | bool() | None:
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
    schema_status: Literal["declared"]
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
            if operation["schema_status"] != "declared":
                raise ContractError("unsupported-active-binding", "/schema_status")
            parsed = next(parsed_operations)
            operations.append(
                OperationContract(
                    OperationId(parsed.id),
                    "declared",
                    tuple(PolicyId(value) for value in parsed.policy_ids),
                    parsed.output_mode,
                    tuple(
                        _text(value, "/fixture_argv")
                        for value in _list(operation["fixture_argv"], "/fixture_argv")
                    )
                    if "fixture_argv" in operation
                    else None,
                    STRINGS,
                    _output_schema(raw, parsed),
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
