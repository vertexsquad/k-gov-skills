from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from kgov_runtime.capabilities import kosis_official_statistics as adapter

PARAMS = {"orgId": "101", "tblId": "DT_FIXTURE", "itmId": "T10", "objL1": "ALL", "prdSe": "Y", "startPrdDe": "2025", "endPrdDe": "2025"}
RECORD = {"TBL_NM": "합성 통계", "PRD_DE": "2025", "C1_NM": "전국", "ITM_NM": "인구", "DT": "100", "raw": "ignored"}


class Response:
    def __init__(self, payload):
        self.body = json.dumps(payload, ensure_ascii=False).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def read(self, limit=-1): return self.body if limit < 0 else self.body[:limit]


class AdapterTest(unittest.TestCase):
    def test_operation_and_projection_are_exact(self) -> None:
        operation = adapter.OPERATION
        self.assertEqual("kgov/kosis-official-statistics/query-statistics/v1", operation.id)
        self.assertEqual("kosis-statistics-api", operation.policy_id)
        self.assertEqual("https://kosis.kr/openapi/Param/statisticsParameterData.do", operation.endpoint)
        self.assertEqual(100, operation.max_records)
        result = adapter.fixture_result()
        self.assertEqual([{"table_name": "합성 인구 통계", "period": "2025", "category": "전국", "item": "인구", "value": "100"}], result["records"])
        self.assertNotIn("UNIT_NM", json.dumps(result, ensure_ascii=False))

    def test_live_happy_path_and_pre_network_rejections(self) -> None:
        opened = []
        def opener(request, timeout=0):
            opened.append(request.full_url)
            return Response([RECORD])
        with patch.dict(os.environ, {"KOSIS_API_KEY": "fixture-secret"}, clear=False):
            result = adapter.query(params=PARAMS, opener=opener, resolver=lambda _: ["1.1.1.1"])
        self.assertEqual(1, result["count"])
        self.assertNotIn("fixture-secret", json.dumps(result, ensure_ascii=False))
        self.assertEqual(1, len(opened))
        with self.assertRaisesRegex(ValueError, "endpoint override"):
            adapter.query(endpoint="https://kosis.kr/other", params=PARAMS, opener=opener)
        with self.assertRaisesRegex(ValueError, "unknown parameter"):
            adapter.query(params=PARAMS | {"query": "x"}, opener=opener)
        with self.assertRaisesRegex(ValueError, "required parameter"):
            adapter.query(params={}, opener=opener)
        self.assertEqual(1, len(opened))

    def test_missing_type_envelope_excess_and_identifier_fail_whole_query(self) -> None:
        invalid = [
            {},
            [RECORD | {"DT": 100}],
            [RECORD for _ in range(101)],
            [RECORD | {"TBL_NM": "person@example.com"}],
            [RECORD | {"TBL_NM": "fixture-secret"}],
        ]
        with patch.dict(os.environ, {"KOSIS_API_KEY": "fixture-secret"}, clear=False):
            for payload in invalid:
                with self.subTest(payload_type=type(payload).__name__), self.assertRaises(ValueError):
                    adapter.query(params=PARAMS, opener=lambda *_a, payload=payload, **_k: Response(payload), resolver=lambda _: ["1.1.1.1"])

    def test_bounded_profile_params_reject_before_network(self) -> None:
        calls = []
        invalid = (
            PARAMS | {"orgId": ""},
            PARAMS | {"tblId": "x" * 81},
            PARAMS | {"prdSe": "INVALID"},
            PARAMS | {"startPrdDe": "20X5"},
            PARAMS | {"startPrdDe": "2026", "endPrdDe": "2025"},
            PARAMS | {"newEstPrdCnt": "101"},
            PARAMS | {"prdSe": "H", "startPrdDe": "20251", "endPrdDe": "20252"},
            PARAMS | {"prdSe": "H", "startPrdDe": "202503", "endPrdDe": "202503"},
            PARAMS | {"prdSe": "Q", "startPrdDe": "20251", "endPrdDe": "20254"},
            PARAMS | {"prdSe": "Q", "startPrdDe": "202505", "endPrdDe": "202505"},
            PARAMS | {"prdSe": "M", "startPrdDe": "202513", "endPrdDe": "202513"},
            PARAMS | {"prdSe": "D", "startPrdDe": "20260230", "endPrdDe": "20260230"},
        )
        with patch.dict(os.environ, {"KOSIS_API_KEY": "fixture-secret"}, clear=False):
            for params in invalid:
                with self.subTest(params=params), self.assertRaises(ValueError):
                    adapter.query(params=params, opener=lambda *_a, **_k: calls.append("open"), resolver=lambda _host: calls.append("resolve"))
        self.assertEqual([], calls)


    def test_calendar_valid_kosis_period_variants_are_accepted(self) -> None:
        valid = (
            ("H", "202501", "202502"),
            ("Q", "202501", "202504"),
            ("M", "202501", "202512"),
            ("D", "20260228", "20260301"),
        )
        with patch.dict(os.environ, {"KOSIS_API_KEY": "fixture-secret"}, clear=False):
            for period, start, end in valid:
                params = PARAMS | {"prdSe": period, "startPrdDe": start, "endPrdDe": end}
                with self.subTest(period=period):
                    result = adapter.query(params=params, opener=lambda *_a, **_k: Response([RECORD]), resolver=lambda _: ["1.1.1.1"])
                    self.assertEqual(1, result["count"])


if __name__ == "__main__":
    unittest.main()
