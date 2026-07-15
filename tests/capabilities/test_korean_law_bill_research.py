from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SPEC = importlib.util.spec_from_file_location("test_korean_law_bill_research_adapter", REPO_ROOT / "kgov_runtime" / "capabilities" / "korean_law_bill_research.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class _Response:
    headers = {"Content-Type": "application/json"}
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit=-1):
        body = json.dumps({"items": [{"id": "live-fixture"}]}).encode("utf-8")
        return body if limit < 0 else body[:limit]


class AdapterTest(unittest.TestCase):
    def test_fixture_mode_is_deterministic(self) -> None:
        payload = json.loads((REPO_ROOT / "tests" / "fixtures" / "capabilities" / "korean-law-bill-research.json").read_text(encoding="utf-8"))
        from kgov_runtime.http import normalize_records
        result = normalize_records(payload)
        self.assertEqual(1, result["count"])
        self.assertEqual("korean-law-bill-research", result["records"][0]["capability"])

    def test_live_query_path_is_mocked_and_read_only(self) -> None:
        opened = []
        def opener(request, timeout=0):
            opened.append(request.full_url)
            return _Response()
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = adapter.query(opener=opener, resolver=lambda _: ["1.1.1.1"])
        self.assertEqual(1, result["count"])
        self.assertEqual(1, len(opened))
        self.assertIn("OC=fixture-secret", opened[0])


if __name__ == "__main__":
    unittest.main()
