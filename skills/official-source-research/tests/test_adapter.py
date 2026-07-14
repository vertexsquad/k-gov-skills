from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "test_official_source_research_adapter",
    SKILL_ROOT / "scripts" / "adapter.py",
)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class _Response:
    headers = {"Content-Type": "text/html; charset=utf-8"}
    status = 200
    body = "<html><head><title> 정부 서비스 </title></head><body>공개정보</body></html>".encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class AdapterTest(unittest.TestCase):
    def test_fixture_is_deterministic(self) -> None:
        fixture = json.loads((SKILL_ROOT / "fixtures" / "sample.json").read_text(encoding="utf-8"))
        self.assertEqual("정부24", fixture["title"])

    def test_inspects_allowlisted_official_source(self) -> None:
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            return _Response()

        result = adapter.inspect_source(
            "https://www.gov.kr/portal/main",
            opener=opener,
            resolver=lambda _: ["1.1.1.1"],
        )
        self.assertEqual("정부 서비스", result["title"])
        self.assertEqual(hashlib.sha256(_Response.body).hexdigest(), result["sha256"])
        self.assertEqual(1, len(opened))

    def test_rejects_non_official_host(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            adapter.inspect_source("https://example.com/", resolver=lambda _: ["1.1.1.1"])


if __name__ == "__main__":
    unittest.main()
