from __future__ import annotations

import json
import os
import unittest
from decimal import Decimal
from types import MappingProxyType
from dataclasses import replace
from unittest.mock import patch

from kgov_runtime.capabilities import korean_law_bill_research as adapter
from kgov_runtime.json_adapter import _result, query_json


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

    def test_arbitrary_legacy_config_and_raw_param_are_rejected_before_network(self) -> None:
        from kgov_runtime.json_adapter import JsonAdapterConfig

        arbitrary = JsonAdapterConfig(slug="arbitrary", default_endpoint="https://example.com/data", allowed_hosts=frozenset({"example.com"}))
        legal = JsonAdapterConfig(
            slug="korean-legal-citation-law-search",
            default_endpoint="https://www.law.go.kr/DRF/lawSearch.do",
            allowed_hosts=frozenset({"law.go.kr"}),
            default_params={"target": "eflaw", "type": "JSON"},
            credential_env="LAW_OC",
            credential_param="OC",
        )
        calls = []
        for config, params in ((arbitrary, {}), (legal, {"raw": "yes"})):
            with self.subTest(slug=config.slug), self.assertRaises(ValueError):
                query_json(config, params=params, opener=lambda *_a, **_k: calls.append(True), resolver=lambda _host: calls.append(True))
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

    def test_exact_legal_compatibility_uses_strict_bounded_json(self) -> None:
        from kgov_runtime.json_adapter import JsonAdapterConfig

        config = JsonAdapterConfig(
            slug="korean-legal-citation-law-search",
            default_endpoint="https://www.law.go.kr/DRF/lawSearch.do",
            allowed_hosts=frozenset({"law.go.kr"}),
            default_params={"target": "eflaw", "type": "JSON"},
            credential_env="LAW_OC",
            credential_param="OC",
        )
        duplicate = b'{"LawSearch":{"totalCnt":"1","totalCnt":"2","law":[]}}'
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False), self.assertRaisesRegex(ValueError, "duplicate"):
            query_json(config, params={"query": "법"}, opener=lambda *_a, **_k: Response(duplicate), resolver=lambda _: ["1.1.1.1"])


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
