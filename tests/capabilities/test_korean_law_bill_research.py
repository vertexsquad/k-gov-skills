from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from io import StringIO
from types import MappingProxyType
from dataclasses import replace
from unittest.mock import patch

from kgov_runtime.capabilities import korean_law_bill_research as adapter
from kgov_runtime.json_adapter import JsonContractError, _ensure_safe_output, _result, query_json, strict_json_loads


SYNTHETIC_CREDENTIAL = "Fixture/ÿ+ Key"
ESCAPED_CREDENTIALS = (
    "Fixture%2F%C3%BF%2B%20Key",
    "Fixture%2f%c3%bf%2b%20Key",
    "Fixture%2f%c3%Bf%2B%20Key",
    "Fixture%2F%C3%BF%2B+Key",
    "Fixture%2f%c3%bf%2b+Key",
    "Fixture%2f%c3%Bf%2B+Key",
)


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


def encoded(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode()


def payload(record=None, count="1"):
    item = record or {"법령명한글": "합성법률", "법령ID": "000001", "시행일자": "20260101", "unknown": "discarded"}
    return {"LawSearch": {"totalCnt": count, "law": [item]}}


class AdapterTest(unittest.TestCase):
    def test_operation_contract_is_exact(self) -> None:
        operation = adapter.OPERATION
        self.assertEqual("kgov/korean-law-bill-research/search-laws/v1", operation.id)
        self.assertEqual("https://www.law.go.kr/DRF/lawSearch.do", operation.endpoint)
        self.assertEqual("law-go-kr-drf-api", operation.policy_id)
        self.assertEqual(frozenset({"query", "search", "LID", "display", "page"}), operation.allowed_params)
        self.assertEqual(frozenset({"query"}), operation.required_params)
        self.assertEqual(("LAW_OC", "OC", 100), (operation.credential_env, operation.credential_param, operation.max_records))

    def test_fixture_projects_only_semantic_fields(self) -> None:
        result = adapter.fixture_result()
        self.assertEqual({"contract_id", "execution_mode", "status", "count", "records", "source_receipt", "manual_review_required"}, set(result))
        self.assertEqual("synthetic-fixture", result["execution_mode"])
        self.assertEqual([{"law_name": "합성법률", "law_id": "000001", "effective_date": "20260101"}], result["records"])
        self.assertNotIn("discarded", json.dumps(result, ensure_ascii=False))

    def test_live_projection_is_credential_free(self) -> None:
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            return Response(encoded(payload()))

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = adapter.query(params={"query": "합성"}, opener=opener, resolver=lambda _: ["1.1.1.1"])
        self.assertEqual("official-live", result["execution_mode"])
        self.assertIn("OC=fixture-secret", opened[0])
        self.assertNotIn("fixture-secret", json.dumps(result, ensure_ascii=False))

    def test_input_contract_rejects_before_network(self) -> None:
        opened = []

        def opener(*_args, **_kwargs):
            opened.append(True)
            raise AssertionError

        with self.assertRaisesRegex(ValueError, "endpoint override"):
            adapter.query(endpoint="https://www.law.go.kr/DRF/lawService.do", params={"query": "법"}, opener=opener)
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            adapter.query(params={"query": "법", "raw": "x"}, opener=opener)
        with self.assertRaisesRegex(ValueError, "required parameter"):
            adapter.query(params={}, opener=opener)
        self.assertEqual([], opened)

    def test_envelope_type_excess_and_unsafe_projection_fail_atomically(self) -> None:
        invalid = [
            {"unexpected": []},
            payload({"법령명한글": "법", "법령ID": 1, "시행일자": "20260101"}),
            {"LawSearch": {"totalCnt": "2", "law": [{"법령명한글": "법", "법령ID": "1", "시행일자": "20260101"}, {"법령명한글": "법", "법령ID": 2, "시행일자": "20260101"}]}},
            {"LawSearch": {"totalCnt": "101", "law": [{"법령명한글": "법", "법령ID": str(i), "시행일자": "20260101"} for i in range(101)]}},
            payload({"법령명한글": "fixture-secret", "법령ID": "1", "시행일자": "20260101"}),
            payload({"법령명한글": "person@example.com", "법령ID": "1", "시행일자": "20260101"}),
        ]
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            for value in invalid:
                with self.subTest(value=list(value)), self.assertRaises(ValueError):
                    adapter.query(params={"query": "법"}, opener=lambda *_a, value=value, **_k: Response(encoded(value)), resolver=lambda _: ["1.1.1.1"])

    def test_shared_json_adapter_error_contract(self) -> None:
        nested = []
        for _ in range(20):
            nested = [nested]
        text = "\u00e9" * 20_000
        valid = (
            (b'{"a":[null,true,1,1.5]}', {"a": [None, True, 1, 1.5]}),
            (b'[' * 21 + b']' * 21, nested),
            (json.dumps([0] * 19_999).encode(), [0] * 19_999),
            (json.dumps({"a": [0] * 19_997}).encode(), {"a": [0] * 19_997}),
            (json.dumps(text, ensure_ascii=False).encode(), text),
            (json.dumps({text: 0}, ensure_ascii=False).encode(), {text: 0}),
            (b'"\\ud83d\\ude00"', "\U0001f600"),
        )
        invalid = (
            (b'[' * 22 + b']' * 22, "JSON structural limit exceeded"),
            (b'[' * 20 + b'{"a":0}' + b']' * 20, "JSON structural limit exceeded"),
            (json.dumps([0] * 20_000).encode(), "JSON structural limit exceeded"),
            (json.dumps({"a": [0] * 19_998}).encode(), "JSON structural limit exceeded"),
            (json.dumps(text + "x", ensure_ascii=False).encode(), "JSON string limit or Unicode contract violated"),
            (json.dumps({text + "x": 0}, ensure_ascii=False).encode(), "JSON string limit or Unicode contract violated"),
            (b'{"a":1,"\\u0061":2}', "duplicate JSON key is forbidden"),
            (b'NaN', "non-finite JSON number is forbidden"),
            (b'Infinity', "non-finite JSON number is forbidden"),
            (b'-Infinity', "non-finite JSON number is forbidden"),
            (b'1e309', "non-finite JSON number is forbidden"),
            (b'"\\ud800"', "JSON string limit or Unicode contract violated"),
            (b'"\\udfff"', "JSON string limit or Unicode contract violated"),
            (b'{"\\ud800":0}', "JSON string limit or Unicode contract violated"),
            (b'{"x":' + json.dumps(text + "x").encode() + b',"a":1,"\\u0061":2}', "duplicate JSON key is forbidden"),
            (b'{"a":NaN,"a":2}', "non-finite JSON number is forbidden"),
        )
        for turn in range(2):
            for index, (body, expected) in enumerate(valid):
                with self.subTest(turn=turn, valid=index):
                    self.assertEqual(expected, strict_json_loads(body))
            for index, (body, message) in enumerate(invalid):
                with self.subTest(turn=turn, invalid=index):
                    with self.assertRaises(JsonContractError) as caught:
                        strict_json_loads(body)
                    error = caught.exception
                    self.assertIs(type(error), JsonContractError)
                    self.assertEqual(("kgov_runtime.json_adapter", "JsonContractError"), (type(error).__module__, type(error).__name__))
                    self.assertEqual((message,), error.args)
                    self.assertIsNone(error.__cause__)
                    self.assertIsNone(error.__context__)
                    self.assertFalse(error.__suppress_context__)

    def test_strict_json_rejects_duplicate_nonfinite_depth_string_and_utf8(self) -> None:
        bodies = [
            b'{"LawSearch":{"totalCnt":"1","totalCnt":"1","law":[]}}',
            b'{"LawSearch":{"totalCnt":NaN,"law":[]}}',
            b'{"LawSearch":{"totalCnt":"0","law":[],"x":' + b'[' * 25 + b'0' + b']' * 25 + b'}}',
            encoded({"LawSearch": {"totalCnt": "0", "law": [], "x": [0] * 20_001}}),
            encoded({"LawSearch": {"totalCnt": "0", "law": [], "x": "z" * 20_001}}),
            b"\xff",
        ]
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            for body in bodies:
                with self.subTest(body=body[:20]), self.assertRaises((UnicodeDecodeError, ValueError)):
                    adapter.query(params={"query": "법"}, opener=lambda *_a, body=body, **_k: Response(body), resolver=lambda _: ["1.1.1.1"])


    def test_recursive_forbidden_output_key_is_rejected(self) -> None:
        operation = replace(adapter.OPERATION, projector=lambda _payload, _params: [{"nested": {"raw": "forbidden"}}])
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False), self.assertRaisesRegex(ValueError, "forbidden output key"):
            _result(operation, {}, "synthetic-fixture", MappingProxyType(dict(operation.default_params or {})))

    def test_normalized_keys_values_and_lowercase_percent_credentials_are_blocked_without_leak(self) -> None:
        unsafe = (
            {"r\u200baw": "x"},
            {"person＠example.com": "x"},
            {"safe": "person@\u200bexample.com"},
            {"safe": "fixture%2fsecret"},
            {"safe": "fixture / secret"},
            {"fixture/\u200bsecret": "x"},
            {"safe": "ｆｉｘｔｕｒｅ/secret"},
        )
        with patch.dict(os.environ, {"LAW_OC": "fixture/secret"}, clear=False):
            for projected in unsafe:
                operation = replace(adapter.OPERATION, projector=lambda _payload, _params, projected=projected: [projected])
                with self.subTest(projected=projected):
                    with self.assertRaises(ValueError) as caught:
                        _result(operation, {}, "synthetic-fixture", MappingProxyType(dict(operation.default_params or {})))
                    message = str(caught.exception)
                    self.assertNotIn("person", message)
                    self.assertNotIn("fixture", message)

    def test_registered_projector_rejects_mixed_percent_credential(self) -> None:
        response = payload({"법령명한글": "Fixture%2fA%2BB", "법령ID": "000001", "시행일자": "20260101"})
        with patch.dict(os.environ, {"LAW_OC": "Fixture/A+B"}, clear=False):
            with self.assertRaises(ValueError) as caught:
                adapter.query(
                    params={"query": "법"},
                    opener=lambda *_a, **_k: Response(encoded(response)),
                    resolver=lambda _: ["1.1.1.1"],
                )
        self.assertNotIn("Fixture", str(caught.exception))

    def test_percent_escape_variants_are_blocked_in_nested_output_and_registered_cli(self) -> None:
        with patch.dict(os.environ, {"LAW_OC": SYNTHETIC_CREDENTIAL}, clear=False):
            for reflection in (SYNTHETIC_CREDENTIAL, *ESCAPED_CREDENTIALS):
                for output in ({"nested": [{"safe": reflection}]}, {"nested": [{reflection: "safe"}]}):
                    with self.subTest(reflection=reflection, output=output):
                        with self.assertRaises(JsonContractError) as caught:
                            _ensure_safe_output(output, adapter.OPERATION)
                        self.assertNotIn("Fixture", str(caught.exception))
                response = payload({"법령명한글": reflection, "법령ID": "000001", "시행일자": "20260101"})
                stdout, stderr = StringIO(), StringIO()
                with (
                    self.subTest(cli_reflection=reflection),
                    patch("sys.argv", ["law-search", "--param", "query=법"]),
                    patch("kgov_runtime.json_adapter.safe_urlopen", return_value=Response(encoded(response))) as opener,
                    redirect_stdout(stdout), redirect_stderr(stderr),
                    self.assertRaises(SystemExit) as caught,
                ):
                    adapter.main()
                self.assertEqual(1, opener.call_count)
                self.assertEqual(2, caught.exception.code)
                self.assertEqual("", stdout.getvalue())
                self.assertTrue(stderr.getvalue())
                self.assertNotIn("Fixture", stderr.getvalue())

    def test_percent_comparison_preserves_case_unrelated_values_and_nested_boundaries(self) -> None:
        controls = (
            *((SYNTHETIC_CREDENTIAL, value.replace("Fixture", "fixture")) for value in ESCAPED_CREDENTIALS),
            *((SYNTHETIC_CREDENTIAL, value.replace("Key", "KEY")) for value in ESCAPED_CREDENTIALS),
            *((SYNTHETIC_CREDENTIAL, value.replace("Fixture", "Unrelated")) for value in ESCAPED_CREDENTIALS),
            (SYNTHETIC_CREDENTIAL, "Fixture%252F%25C3%25BF%252B%2520Key"),
            (SYNTHETIC_CREDENTIAL, "Fixture%252f%25c3%25Bf%252B%2520Key"),
            (SYNTHETIC_CREDENTIAL, "Fixture%2G%c3%Bf%2B%20Key"),
            ("Fixture%2FPart", "Fixture%252fPart"),
            ("", ESCAPED_CREDENTIALS[2]),
        )
        for credential, value in controls:
            with self.subTest(credential=credential, value=value), patch.dict(os.environ, {"LAW_OC": credential}):
                output = {"nested": [{value: value}]}
                _ensure_safe_output(output, adapter.OPERATION)
                self.assertEqual({"nested": [{value: value}]}, output)
                response = payload({"법령명한글": value, "법령ID": "000001", "시행일자": "20260101"})
                result = _result(adapter.OPERATION, response, "synthetic-fixture", adapter.OPERATION.default_params)
                self.assertEqual(value, result["records"][0]["law_name"])
        with patch.dict(os.environ, {"LAW_OC": "Fixture%2FPart"}):
            for reflection in ("Fixture%2FPart", "Fixture%2fPart", "Fixture%252FPart"):
                with self.subTest(nested_reflection=reflection), self.assertRaises(JsonContractError):
                    _ensure_safe_output({"safe": reflection}, adapter.OPERATION)

    def test_actual_cli_keeps_escaped_inputs_out_of_fixture_and_rejection_output(self) -> None:
        command = [sys.executable, "-m", "kgov_runtime.capabilities.korean_law_bill_research"]
        for reflection in ESCAPED_CREDENTIALS:
            for flags in ([], ["--fixture"], ["--unknown=" + reflection]):
                with self.subTest(reflection=reflection, flags=flags):
                    result = subprocess.run(
                        [*command, "--param", "query=" + reflection, *flags],
                        cwd=adapter.ROOT, env={"LAW_OC": SYNTHETIC_CREDENTIAL},
                        capture_output=True, text=True, timeout=10, check=False,
                    )
                    self.assertNotIn("Fixture", result.stdout + result.stderr)
                    self.assertEqual(0 if flags == ["--fixture"] else 2, result.returncode)
                    if result.returncode == 0:
                        self.assertEqual("", result.stderr)
                        self.assertEqual("synthetic-fixture", json.loads(result.stdout)["execution_mode"])
                    else:
                        self.assertEqual("", result.stdout)
                        self.assertTrue(result.stderr)

    def test_unregistered_operation_and_raw_param_are_rejected_before_network(self) -> None:
        arbitrary = replace(adapter.OPERATION, id="kgov/unregistered/search/v1")
        calls = []
        for operation, params in ((arbitrary, {"query": "법"}), (adapter.OPERATION, {"query": "법", "raw": "yes"})):
            with self.subTest(operation=operation.id), self.assertRaises(ValueError):
                query_json(operation, params=params, opener=lambda *_a, **_k: calls.append(True), resolver=lambda _host: calls.append(True))
        self.assertEqual([], calls)

    def test_parameters_and_missing_credential_fail_before_dns(self) -> None:
        calls = []
        invalid = (
            {"query": ""},
            {"query": "x" * 201},
            {"query": "법", "display": "0"},
            {"query": "법", "display": "101"},
            {"query": "법", "page": "0"},
            {"query": "법", "LID": "not-digits"},
        )
        for params in invalid:
            with self.subTest(params=params), self.assertRaises(ValueError):
                adapter.query(params=params, opener=lambda *_a, **_k: calls.append("open"), resolver=lambda _host: calls.append("resolve"))
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            adapter.query(params={"query": "법"}, opener=lambda *_a, **_k: calls.append("open"), resolver=lambda _host: calls.append("resolve"))
        self.assertEqual([], calls)

    def test_total_count_requires_a_coherent_page_but_allows_valid_pagination(self) -> None:
        response = payload(count="999")
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "count"):
                adapter.query(params={"query": "법"}, opener=lambda *_a, **_k: Response(encoded(response)), resolver=lambda _: ["1.1.1.1"])
            result = adapter.query(params={"query": "법", "display": "1"}, opener=lambda *_a, **_k: Response(encoded(response)), resolver=lambda _: ["1.1.1.1"])
        self.assertEqual(1, result["count"])

    def test_registered_operation_uses_strict_bounded_json(self) -> None:
        duplicate = b'{"LawSearch":{"totalCnt":"1","totalCnt":"2","law":[]}}'
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False), self.assertRaisesRegex(ValueError, "duplicate"):
            query_json(adapter.OPERATION, params={"query": "법"}, opener=lambda *_a, **_k: Response(duplicate), resolver=lambda _: ["1.1.1.1"])


    def test_security_contract_mutations_are_rejected_before_network(self) -> None:
        operation = adapter.OPERATION
        mutations = (
            replace(operation, endpoint="https://attacker.example/collect"),
            replace(operation, credential_env="ATTACKER_SECRET"),
            replace(operation, credential_param="token"),
            replace(operation, policy_id="attacker-policy"),
            replace(operation, contract_id="kgov/attacker/v1"),
            replace(operation, allowed_params=operation.allowed_params | {"callback"}),
            replace(operation, required_params=frozenset()),
            replace(operation, max_records=101),
            replace(operation, default_params=dict(operation.default_params or {}) | {"callback": "https://attacker.example"}),
            replace(operation, id="kgov/attacker/collect/v1"),
        )
        calls = []
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret", "ATTACKER_SECRET": "stolen"}, clear=False):
            for mutated in mutations:
                with self.subTest(operation=mutated.id), self.assertRaisesRegex(ValueError, "approved operation"):
                    query_json(
                        mutated,
                        params={"query": "법"},
                        opener=lambda *_a, **_k: calls.append("open"),
                        resolver=lambda _host: calls.append("resolve"),
                    )
        self.assertEqual([], calls)

    def test_projector_and_validator_replacements_are_rejected_before_network(self) -> None:
        callbacks = []

        def exfiltrating_validator(_params) -> None:
            callbacks.append("validator")

        mutations = (
            replace(adapter.OPERATION, projector=lambda _payload, _params: []),
            replace(adapter.OPERATION, parameter_validator=exfiltrating_validator),
        )
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            for operation in mutations:
                with self.subTest(callable=operation.projector.__qualname__), self.assertRaisesRegex(ValueError, "approved operation"):
                    query_json(
                        operation,
                        params={"query": "법"},
                        opener=lambda *_a, **_k: callbacks.append("open"),
                        resolver=lambda _host: callbacks.append("resolve"),
                    )
        self.assertEqual([], callbacks)

    def test_projected_output_requires_exact_json_shape_and_finite_primitives(self) -> None:
        invalid_records = (
            ({"safe": "value"},),
            [MappingProxyType({"safe": "value"})],
            [{"safe": ("fixture-secret",)}],
            [{"safe": {"fixture-secret"}}],
            [{"safe": b"fixture-secret"}],
            [{"safe": float("nan")}],
            [{"safe": float("inf")}],
            [{"safe": Decimal("1")}],
        )
        for records in invalid_records:
            operation = replace(adapter.OPERATION, projector=lambda _payload, _params, records=records: records)
            with self.subTest(records_type=type(records).__name__):
                with self.assertRaises(ValueError) as caught:
                    _result(operation, {}, "synthetic-fixture", MappingProxyType(dict(operation.default_params or {})))
                self.assertNotIn("fixture-secret", str(caught.exception))

    def test_registered_projector_blocks_spaced_unicode_identifiers(self) -> None:
        identifiers = (
            "person @ example . com",
            "010 ‐ 1234 − 5678",
            "900101 - 1234567",
        )
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            for identifier in identifiers:
                response = payload({"법령명한글": identifier, "법령ID": "000001", "시행일자": "20260101"})
                with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "identifier"):
                    adapter.query(
                        params={"query": "법"},
                        opener=lambda *_a, response=response, **_k: Response(encoded(response)),
                        resolver=lambda _: ["1.1.1.1"],
                    )


if __name__ == "__main__":
    unittest.main()
