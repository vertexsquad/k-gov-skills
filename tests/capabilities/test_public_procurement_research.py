from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from kgov_runtime.capabilities import public_procurement_research as adapter

PARAMS = {"pageNo": "1", "numOfRows": "10", "inqryDiv": "1", "inqryBgnDt": "20260101", "inqryEndDt": "20260131"}
ITEM = {"orderPlanUntyNo": "P-1", "bizNm": "합성 사업", "orderInsttNm": "합성기관", "orderPlanAmt": "1000", "orderPlanDate": "20260101", "body": "ignored"}


def envelope(items, code="00", *, total=None, page=1, rows=10):
    count = len(items) if total is None else total
    return {"response": {"header": {"resultCode": code}, "body": {"totalCount": count, "pageNo": page, "numOfRows": rows, "items": {"item": items}}}}


class Response:
    def __init__(self, payload): self.body = json.dumps(payload, ensure_ascii=False).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def read(self, limit=-1): return self.body if limit < 0 else self.body[:limit]


class AdapterTest(unittest.TestCase):
    def test_operation_and_projection_are_exact(self) -> None:
        operation = adapter.OPERATION
        self.assertEqual("kgov/public-procurement-research/query-order-plans/v1", operation.id)
        self.assertEqual("data-go-kr-order-plan-api", operation.policy_id)
        self.assertEqual("https://apis.data.go.kr/1230000/ao/OrderPlanSttusService", operation.endpoint)
        self.assertEqual(("DATA_GO_KR_API_KEY", "serviceKey", 100), (operation.credential_env, operation.credential_param, operation.max_records))
        result = adapter.fixture_result()
        self.assertEqual("PLAN-001", result["records"][0]["plan_number"])
        self.assertNotIn("contact", json.dumps(result, ensure_ascii=False))

    def test_happy_and_input_rejections_are_pre_network(self) -> None:
        calls = []
        def opener(*_a, **_k):
            calls.append(True)
            return Response(envelope([ITEM]))
        with patch.dict(os.environ, {"DATA_GO_KR_API_KEY": "fixture-secret"}, clear=False):
            result = adapter.query(params=PARAMS, opener=opener, resolver=lambda _: ["1.1.1.1"])
        self.assertEqual([{"plan_number": "P-1", "business_name": "합성 사업", "ordering_agency": "합성기관", "planned_amount": "1000", "planned_date": "20260101"}], result["records"])
        with self.assertRaises(ValueError):
            adapter.query(endpoint="https://apis.data.go.kr/other", params=PARAMS, opener=opener)
        with self.assertRaises(ValueError):
            adapter.query(params=PARAMS | {"url": "x"}, opener=opener)
        with self.assertRaises(ValueError):
            adapter.query(params={}, opener=opener)
        self.assertEqual(1, len(calls))

    def test_envelope_status_missing_type_excess_and_identifier_fail_atomically(self) -> None:
        invalid = [{}, envelope([ITEM], "99"), envelope([ITEM | {"bizNm": 1}]), envelope([ITEM] * 101), envelope([ITEM | {"bizNm": "010-1234-5678"}])]
        with patch.dict(os.environ, {"DATA_GO_KR_API_KEY": "fixture-secret"}, clear=False):
            for payload in invalid:
                with self.subTest(payload=list(payload)), self.assertRaises(ValueError):
                    adapter.query(params=PARAMS, opener=lambda *_a, payload=payload, **_k: Response(payload), resolver=lambda _: ["1.1.1.1"])


    def test_bounded_profile_params_reject_before_network(self) -> None:
        calls = []
        invalid = (
            PARAMS | {"pageNo": "0"},
            PARAMS | {"numOfRows": "101"},
            PARAMS | {"inqryDiv": "9"},
            PARAMS | {"inqryBgnDt": "20260230"},
            PARAMS | {"inqryBgnDt": "20260201", "inqryEndDt": "20260101"},
            PARAMS | {"inqryEndDt": ""},
            PARAMS | {"inqryEndDt": "1" * 201},
        )
        for params in invalid:
            with self.subTest(params=params), self.assertRaises(ValueError):
                adapter.query(params=params, opener=lambda *_a, **_k: calls.append("open"), resolver=lambda _host: calls.append("resolve"))
        self.assertEqual([], calls)

    def test_count_and_page_metadata_are_coherent(self) -> None:
        with patch.dict(os.environ, {"DATA_GO_KR_API_KEY": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "count"):
                adapter.query(params=PARAMS, opener=lambda *_a, **_k: Response(envelope([ITEM], total=999)), resolver=lambda _: ["1.1.1.1"])
            last_page = PARAMS | {"pageNo": "100"}
            result = adapter.query(params=last_page, opener=lambda *_a, **_k: Response(envelope([ITEM] * 9, total=999, page=100)), resolver=lambda _: ["1.1.1.1"])
        self.assertEqual(9, result["count"])


if __name__ == "__main__":
    unittest.main()
