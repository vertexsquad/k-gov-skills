"""Offline machine-contract parity for every catalog capability."""

import importlib
import io
import json
import sys
import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from subprocess import CompletedProcess, run
from tempfile import TemporaryDirectory
from typing import Final
from unittest.mock import patch

from kgov_runtime.capabilities import official_source_research
from kgov_runtime.http import ReadOnlyHttpError
from kgov_runtime.json_adapter import JsonOperation, strict_json_loads
from kgov_runtime.review_admission import ReviewContract
from kgov_runtime.source_policy import JSONValue
from tests.capabilities import test_patent_prior_art_evidence_pack as patent

ROOT: Final = Path(__file__).resolve().parents[1]
CATALOG: Final = ROOT / "catalog/domain-skills.json"


class RuntimeContractsTest(unittest.TestCase):
    def test_exports_match_when_catalog_modules_are_imported(self) -> None:
        # Given the catalog, not a duplicate module registry.
        catalog = json.loads(CATALOG.read_bytes())
        for contract in catalog["runtime_contracts"]:
            with self.subTest(module=contract["module"]):
                # When importing the real capability.
                module = importlib.import_module(contract["module"])
                # Then stable machine exports identify all declared operations.
                self.assertEqual(
                    contract["id"], getattr(module, "RUNTIME_CONTRACT_ID", None)
                )
                self.assertEqual(
                    tuple(operation["id"] for operation in contract["operations"]),
                    getattr(module, "RUNTIME_OPERATION_IDS", None),
                )


def cli(module: str, argv: tuple[str, ...]) -> CompletedProcess[str]:
    return run(
        [sys.executable, "-m", "scripts.offline_fixture", module, *argv],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={"PYTHONIOENCODING": "utf-8"},
    )


class ContractSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Given the missing implementation, fail explicitly before importing.
        assert importlib.util.find_spec("kgov_runtime.contracts") is not None
        cls.api = importlib.import_module("kgov_runtime.contracts")
        cls.catalog = json.loads(CATALOG.read_bytes())
        cls.contracts = cls.api.load_contracts()
        # Each distinct declared argv executes once; tests reuse these receipts.
        cls.fixtures = [
            (contract, op)
            for contract in cls.contracts
            for op in contract.operations
            if op.fixture_argv is not None
        ]
        commands = dict.fromkeys((c.module, op.fixture_argv) for c, op in cls.fixtures)
        cls.receipts = {command: cli(*command) for command in commands}
        cls.outputs = {
            op.id: json.loads(cls.receipts[c.module, op.fixture_argv].stdout)
            for c, op in cls.fixtures
        }

        # Given reviewed synthetic policy and real isolated state; only wire I/O is fake.
        policy_id = "kipris-web"
        registry = patent.reviewed_registry(policy_id)
        policy = next(item for item in registry.policies if item.id == policy_id)
        robots = patent.Response(b"User-agent: *\nAllow: /\n", media_type="text/plain")
        responses = iter((robots, patent._Response()))
        transport = patent.HttpTransport(
            lambda *_a, **_k: next(responses), lambda _host: ["1.1.1.1"]
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite3"
            state = patent.PolicyState(path, clock=lambda: 1000.0, sleeper=cls().fail)
            enforcer = patent.HttpPolicyEnforcer(registry, state, transport)
            # When the real patent adapter runs. Then cache its unmodified result.
            result = patent.adapter.inspect_patent_source(
                policy.scope.origins[0] + "/page", policy, enforcer
            )
            cls.outputs[patent.adapter.OPERATION_ID] = result

    def test_parity_when_catalog_is_loaded(self) -> None:
        # Given the SSOT. When comparing it to real module exports.
        self.api.validate_parity(self.contracts)
        # Then every catalog field survives parsing.
        for contract, raw in zip(
            self.contracts, self.catalog["runtime_contracts"], strict=True
        ):
            with self.subTest(contract=contract.id):
                self.assertEqual(raw, contract.catalog_document())

    def test_fixtures_when_network_is_disabled(self) -> None:
        # Given catalog commands. When observing their real CLI receipts.
        for contract, operation in self.fixtures:
            with self.subTest(operation=operation.id):
                receipt = self.receipts[contract.module, operation.fixture_argv]
                # Then success is one JSON object, quiet stderr, valid schemas.
                self.assertEqual(0, receipt.returncode, receipt.stderr)
                self.assertEqual("", receipt.stderr)
                output = strict_json_loads(receipt.stdout.encode())
                contract.validate_output(operation.id, output)

    def test_help_when_network_is_disabled(self) -> None:
        # Given each module. When invoking its original parser.
        for contract in self.contracts:
            with self.subTest(module=contract.module):
                receipt = cli(contract.module, ("--help",))
                # Then the heterogeneous CLI remains reachable offline.
                self.assertEqual(0, receipt.returncode, receipt.stderr)
                self.assertEqual("", receipt.stderr)
                self.assertTrue(receipt.stdout)

    def test_invalid_arguments_when_using_real_clis(self) -> None:
        # Given rejected option names, values and excess paths.
        marker = "synthetic-argv-marker"
        arguments = (
            (f"--{marker}",),
            (f"--{marker}=synthetic-value-marker",),
            ("--fixture=synthetic-value-marker",),
            ("--fixture", "synthetic-path-marker", "synthetic-path-marker"),
        )
        for contract in self.contracts:
            for argv in arguments:
                with self.subTest(module=contract.module, argv=argv):
                    # When parsing offline. Then no rejected data is reflected.
                    receipt = cli(contract.module, argv)
                    self.assertEqual(contract.exit_codes.input_error, receipt.returncode)
                    self.assertEqual("", receipt.stdout)
                    self.assertTrue(receipt.stderr)
                    for rejected in (marker, "synthetic-value-marker", "synthetic-path-marker", "Traceback"):
                        self.assertNotIn(rejected, receipt.stderr)

    def test_source_enums_when_arrays_or_objects_are_supplied(self) -> None:
        # Given every caller of shared admission, including the patent CLI.
        marker = "synthetic-enum-marker"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-path-marker.json"
            for contract in self.contracts:
                adapter = importlib.import_module(contract.module)
                if not isinstance(getattr(adapter, "CONTRACT", None), ReviewContract):
                    continue
                for field in ("license_status", "redistribution"):
                    for value in ([], {}, [marker], {marker: marker}, None, True, 1, marker):
                        candidate = json.loads(adapter.FIXTURE.read_bytes())
                        candidate["source_refs"][0][field] = value
                        path.write_text(json.dumps(candidate), encoding="utf-8")
                        with self.subTest(module=contract.module, field=field, value=value):
                            # When the real CLI admits it. Then rejection is controlled.
                            receipt = cli(contract.module, (str(path),))
                            self.assertEqual(2, receipt.returncode, receipt.stderr)
                            self.assertEqual("", receipt.stdout)
                            for rejected in (marker, path.name, "Traceback"):
                                self.assertNotIn(rejected, receipt.stderr)

    def test_input_errors_when_keys_values_or_paths_are_private(self) -> None:
        # Given synthetic private data at file and parameter boundaries.
        marker = "synthetic-private-marker"
        with TemporaryDirectory() as directory:
            path = Path(directory) / f"{marker}.json"
            for contract in self.contracts:
                adapter = importlib.import_module(contract.module)
                cases = [((str(path / marker),), None)]
                if contract.kind in ("admission", "hybrid"):
                    valid = json.loads(adapter.FIXTURE.read_bytes())
                    cases.extend((
                        ((str(path),), valid | {marker: marker}),
                        ((str(path),), valid | {"redaction_status": marker}),
                    ))
                    if "document_type" in valid:
                        cases.append(((str(path),), valid | {"document_type": marker}))
                operation = getattr(adapter, "OPERATION", None)
                if isinstance(operation, JsonOperation):
                    cases.extend((
                        (("--param", f"{marker}={marker}"), None),
                        (("--param", marker), None),
                        (("--param", f"{marker}=1", "--param", f"{marker}=2"), None),
                    ))
                for argv, payload in cases:
                    if payload is not None:
                        path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.subTest(module=contract.module, argv=argv, payload=payload):
                        # When rejecting input. Then neither values nor paths escape.
                        receipt = cli(contract.module, argv)
                        self.assertEqual(2, receipt.returncode, receipt.stderr)
                        self.assertEqual("", receipt.stdout)
                        self.assertNotIn(marker, receipt.stderr)
                        self.assertNotIn("Traceback", receipt.stderr)

    def test_official_source_exit_codes_when_retrieval_fails(self) -> None:
        # Given deterministic failures at the retrieval boundary; no live I/O.
        for status, code in (("invalid-request", 2), ("policy-disabled", 3), ("upstream-unavailable", 4)):
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                self.subTest(status=status),
                patch.object(sys, "argv", ["official-source", "https://www.gov.kr/"]),
                patch.object(sys, "stdout", stdout),
                patch.object(sys, "stderr", stderr),
                patch.object(official_source_research, "_live", side_effect=ReadOnlyHttpError(status)),
                self.assertRaises(SystemExit) as raised,
            ):
                # When the real parser and handler run. Then exit semantics survive.
                official_source_research.main()
            self.assertEqual(code, raised.exception.code)
            self.assertEqual("", stdout.getvalue())
            self.assertIn(status, stderr.getvalue())

    def test_rejects_metadata_when_catalog_fields_are_mutated(self) -> None:
        # Given distinct mutations at each contract boundary.
        changes: tuple[tuple[str, JSONValue], ...] = (
            ("id", "kgov/wrong/v1"),
            ("module", "kgov_runtime.capabilities.wrong"),
            ("capability_slug", "wrong"),
            ("kind", "retrieval"),
            ("network_mode", "blocked"),
            ("default_operation_id", "kgov/wrong/run/v1"),
            ("forbidden_output_keys", []),
            ("unexpected", True),
        )
        for field, value in changes:
            candidate = deepcopy(self.catalog)
            candidate["runtime_contracts"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                # When parsing and checking parity. Then no drift is admitted.
                self.api.validate_parity(self.api.parse_contracts(candidate))

    def test_rejects_operations_when_catalog_fields_are_mutated(self) -> None:
        # Given operation, fixture, schema and policy mutations.
        changes: tuple[tuple[str, JSONValue], ...] = (
            ("id", "kgov/public-document-hwpx/other/v1"),
            ("fixture_argv", ["--help"]),
            ("source_policy_ids", ["unknown-policy"]),
            ("source_output_mode", "link-only"),
            ("schema_status", "unknown"),
            ("input_schema", {"type": "null"}),
            ("unknown", None),
        )
        for field, value in changes:
            candidate = deepcopy(self.catalog)
            candidate["runtime_contracts"][0]["operations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                # When checking the candidate. Then it fails closed.
                self.api.validate_parity(self.api.parse_contracts(candidate))

    def test_rejects_exits_when_integers_or_types_change(self) -> None:
        # Given every exit field and coercible or incorrect values.
        for field in self.catalog["runtime_contracts"][0]["exit_codes"]:
            for value in (False, True, 0.0, 9, "0", None):
                candidate = deepcopy(self.catalog)
                candidate["runtime_contracts"][0]["exit_codes"][field] = value
                with self.subTest(case=(field, value)), self.assertRaises(ValueError):
                    # When parsing. Then coercion cannot hide drift.
                    self.api.parse_contracts(candidate)

    def test_rejects_exports_when_modules_drift(self) -> None:
        # Given altered stable exports and existing operation constants.
        for contract in self.contracts:
            module = importlib.import_module(contract.module)
            changes = [("RUNTIME_CONTRACT_ID", "wrong"), ("RUNTIME_OPERATION_IDS", ())]
            if hasattr(module, "OPERATION_ID"):
                changes.append(("OPERATION_ID", "wrong"))
            if getattr(module, "OPERATION", None) is not None:
                changes.append(
                    ("OPERATION", replace(module.OPERATION, policy_id="wrong"))
                )
            for field, value in changes:
                with (
                    self.subTest(module=contract.module, field=field),
                    patch.object(module, field, value),
                ):
                    # When comparing. Then module disagreement is detected.
                    with self.assertRaises(self.api.ContractError):
                        self.api.validate_parity(self.contracts)

    def test_rejects_outputs_when_required_keys_or_consts_change(self) -> None:
        # Given independent schemas and cached CLI output.
        for contract in self.contracts:
            for operation in contract.operations:
                self.assertIn(operation.id, self.outputs)
                output = deepcopy(self.outputs[operation.id])
                contract.validate_output(operation.id, output)
                for field, schema in operation.output_schema.properties:
                    mutations = []
                    if field in (operation.output_schema.required or ()):
                        missing = dict(output)
                        del missing[field]
                        mutations.append(("missing", missing))
                    if schema.const_json is not None:
                        value = output[field]
                        wrong = not value if type(value) is bool else "wrong-const"
                        mutations.append(("const", output | {field: wrong}))
                    for kind, candidate in mutations:
                        with (
                            self.subTest(operation=operation.id, case=(kind, field)),
                            self.assertRaises(self.api.ContractError),
                        ):
                            # When each required key or const changes. Then it fails.
                            contract.validate_output(operation.id, candidate)

    def test_rejects_forbidden_keys_when_nested_inside_arrays(self) -> None:
        # Given nested extensions; schemas deliberately allow extra safe fields.
        variants = ("RAW", "\uff52\uff41\uff57", "r\u200baw")
        for contract in self.contracts:
            operation = contract.operations[0]
            output = deepcopy(self.outputs[operation.id])
            for key in contract.forbidden_output_keys + variants:
                candidate = {**output, "extension": [{"nested": {key: "sentinel"}}]}
                with (
                    self.subTest(contract=contract.id, key=key),
                    self.assertRaises(self.api.ContractError),
                ):
                    # When checking recursively. Then depth cannot bypass policy.
                    contract.validate_output(operation.id, candidate)

    def test_contracts_are_frozen_when_callers_try_to_mutate_them(self) -> None:
        # Given contract, operation, schema and exit value objects.
        contract = self.contracts[0]
        values = (
            (contract, "id"),
            (contract.operations[0], "id"),
            (contract.exit_codes, "success"),
            (contract.operations[0].output_schema, "kind"),
        )
        for value, field in values:
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                # When assigning. Then immutable ownership is enforced.
                setattr(value, field, "changed")

    def test_json_boundary_when_documents_are_ambiguous(self) -> None:
        # Given duplicate keys or non-finite JSON at the file boundary.
        for raw in (
            '{"schema_version":6,"schema_version":6}',
            '{"schema_version":NaN}',
        ):
            with TemporaryDirectory() as directory:
                path = Path(directory) / "catalog.json"
                path.write_text(raw)
                # When loading. Then ambiguous JSON cannot enter typed contracts.
                with self.assertRaises(ValueError):
                    self.api.load_contracts(path)

    def test_rejects_receipts_when_operation_or_policy_is_forged(self) -> None:
        # Given projected fixtures or metadata-only page/verification receipts.
        for contract in self.contracts:
            for operation in contract.operations:
                if not operation.source_policy_ids:
                    continue
                output = deepcopy(self.outputs[operation.id])
                receipt = {
                    "operation_id": operation.id,
                    "policy_id": operation.source_policy_ids[0],
                    "policy_revision": 1,
                    "policy_digest": "0" * 64,
                    "outcome": "allowed",
                }
                if "source_receipts" in output:
                    output["source_receipts"][0]["source_receipt"] = receipt
                elif output["source_receipt"] is None:
                    output["source_receipt"] = receipt
                else:
                    receipt = output["source_receipt"]
                contract.validate_output(operation.id, output)
                for field in ("operation_id", "policy_id"):
                    original = receipt[field]
                    receipt[field] = "wrong"
                    with (
                        self.subTest(operation=operation.id, field=field),
                        self.assertRaises(self.api.ContractError),
                    ):
                        # When validating altered identity. Then output cannot launder policy.
                        contract.validate_output(operation.id, output)
                    receipt[field] = original

    def test_rejects_nonfinite_output_when_hidden_in_extensions(self) -> None:
        # Given an otherwise successful fixture with an invalid JSON extension.
        contract = self.contracts[0]
        operation = contract.operations[0]
        output = deepcopy(self.outputs[operation.id])
        output["extension"] = [{"number": float("inf")}]
        # When checking the boundary. Then extensions cannot bypass JSON validity.
        with self.assertRaises(self.api.ContractError):
            contract.validate_output(operation.id, output)
