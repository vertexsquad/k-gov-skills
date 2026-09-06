from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from kgov_runtime.capabilities import disaster_geospatial_brief as adapter

PARAMS = {"pageNo": "1", "numOfRows": "10", "base_date": "20260101", "base_time": "0500", "nx": "60", "ny": "127"}
ITEM = {"category": "TMP", "fcstDate": "20260101", "fcstTime": "1200", "fcstValue": "3", "nx": 60, "ny": 127, "text": "ignored"}


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
        self.assertEqual("kgov/disaster-geospatial-brief/query-village-forecast/v1", operation.id)
        self.assertEqual("data-go-kr-village-forecast-api", operation.policy_id)
        self.assertEqual("https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst", operation.endpoint)
        result = adapter.fixture_result()
        self.assertEqual([{"category": "TMP", "forecast_date": "20260101", "forecast_time": "1200", "forecast_value": "3", "grid_x": 60, "grid_y": 127}], result["records"])
        self.assertNotIn("baseDate", json.dumps(result))

    def test_happy_and_input_contract_rejections(self) -> None:
        calls = []
        def opener(*_a, **_k):
            calls.append(True)
            return Response(envelope([ITEM]))
        with patch.dict(os.environ, {"KMA_OPEN_API_KEY": "fixture-secret"}, clear=False):
            result = adapter.query(params=PARAMS, opener=opener, resolver=lambda _: ["1.1.1.1"])
        self.assertEqual(1, result["count"])
        self.assertNotIn("fixture-secret", json.dumps(result))
        with self.assertRaises(ValueError):
            adapter.query(endpoint="https://apis.data.go.kr/other", params=PARAMS, opener=opener)
        with self.assertRaises(ValueError):
            adapter.query(params=PARAMS | {"station": "x"}, opener=opener)
        with self.assertRaises(ValueError):
            adapter.query(params={}, opener=opener)
        self.assertEqual(1, len(calls))

    def test_envelope_status_missing_type_excess_and_identifier_fail_atomically(self) -> None:
        invalid = [{}, envelope([ITEM], "03"), envelope([ITEM | {"nx": "60"}]), envelope([ITEM] * 101), envelope([ITEM | {"fcstValue": "person@example.com"}])]
        with patch.dict(os.environ, {"KMA_OPEN_API_KEY": "fixture-secret"}, clear=False):
            for payload in invalid:
                with self.subTest(payload=list(payload)), self.assertRaises(ValueError):
                    adapter.query(params=PARAMS, opener=lambda *_a, payload=payload, **_k: Response(payload), resolver=lambda _: ["1.1.1.1"])


    def test_bounded_profile_params_reject_before_network(self) -> None:
        calls = []
        invalid = (
            PARAMS | {"pageNo": "0"},
            PARAMS | {"numOfRows": "101"},
            PARAMS | {"base_date": "20260230"},
            PARAMS | {"base_time": "0400"},
            PARAMS | {"nx": "0"},
            PARAMS | {"nx": "150"},
            PARAMS | {"ny": "254"},
            PARAMS | {"ny": ""},
        )
        for params in invalid:
            with self.subTest(params=params), self.assertRaises(ValueError):
                adapter.query(params=params, opener=lambda *_a, **_k: calls.append("open"), resolver=lambda _host: calls.append("resolve"))
        self.assertEqual([], calls)

    def test_count_and_page_metadata_are_coherent(self) -> None:
        with patch.dict(os.environ, {"KMA_OPEN_API_KEY": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "count"):
                adapter.query(params=PARAMS, opener=lambda *_a, **_k: Response(envelope([ITEM], total=999)), resolver=lambda _: ["1.1.1.1"])
            last_page = PARAMS | {"pageNo": "100"}
            result = adapter.query(params=last_page, opener=lambda *_a, **_k: Response(envelope([ITEM] * 9, total=999, page=100)), resolver=lambda _: ["1.1.1.1"])
        self.assertEqual(9, result["count"])


if __name__ == "__main__":
    unittest.main()
