from __future__ import annotations

import json
import hashlib
import unittest
import subprocess
import sys
from pathlib import Path

from kgov_runtime.capabilities import patent_prior_art_evidence_pack as adapter
from tests.capabilities.review_admission_contract import ReviewAdmissionContractMixin

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "kgov_runtime" / "capabilities" / "patent_prior_art_evidence_pack.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "capabilities" / "patent-prior-art-evidence-pack.json"


class _Response:
    headers = {"Content-Type": "text/html; charset=utf-8"}
    status = 200
    body = "<html><head><title>KIPRIS 특허정보</title></head><body>공개문헌</body></html>".encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class AdapterTest(ReviewAdmissionContractMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = adapter
        cls.adapter_path = ADAPTER_PATH
        cls.valid = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_preserves_safe_kipris_read_only_lookup(self) -> None:
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            return _Response()

        result = adapter.inspect_patent_source(
            "https://www.kipris.or.kr/khome/main.do",
            opener=opener,
            resolver=lambda _: ["1.1.1.1"],
        )
        self.assertEqual("KIPRIS 특허정보", result["title"])
        self.assertEqual(hashlib.sha256(_Response.body).hexdigest(), result["sha256"])
        self.assertEqual(1, len(opened))

    def test_lookup_rejects_nonofficial_and_credential_bearing_urls(self) -> None:
        for url in (
            "https://example.org/",
            "https://www.kipris.or.kr/?api_key=SYNTHETIC_TOKEN",
            "https://user:secret@www.kipris.or.kr/",
            "https://www.kipris.or.kr/#internal",
        ):
            with self.subTest(url=url):
                with self.assertRaises((ValueError, RuntimeError)):
                    adapter.inspect_patent_source(url, resolver=lambda _: ["1.1.1.1"])

    def test_lookup_cli_does_not_echo_credential_value(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ADAPTER_PATH),
                "--lookup-url",
                "https://www.kipris.or.kr/?api_key=SYNTHETIC_TOKEN",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertNotIn("SYNTHETIC_TOKEN", result.stderr)


if __name__ == "__main__":
    unittest.main()
