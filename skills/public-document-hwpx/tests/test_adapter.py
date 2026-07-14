from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_public_document_hwpx_adapter", SKILL_ROOT / "scripts" / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class AdapterTest(unittest.TestCase):
    def test_fixture_is_deterministic(self) -> None:
        fixture = json.loads((SKILL_ROOT / "fixtures" / "sample.json").read_text(encoding="utf-8"))
        self.assertEqual("테스트 문서", fixture["text"])
        self.assertEqual(1, fixture["count"])

    def test_extracts_text_without_mutating_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.hwpx"
            xml = '<hp:section xmlns:hp="urn:hancom:hwpx"><hp:p><hp:t>테스트 문서</hp:t></hp:p></hp:section>'
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("mimetype", "application/hwp+zip")
                archive.writestr("Contents/section0.xml", xml)
            before = path.read_bytes()
            result = adapter.extract_hwpx(path)
            after = path.read_bytes()
        self.assertEqual(before, after)
        self.assertEqual("테스트 문서", result["text"])
        self.assertEqual(["Contents/section0.xml"], result["sections"])

    def test_rejects_non_hwpx_zip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.hwpx"
            path.write_text("not a zip", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "valid HWPX"):
                adapter.extract_hwpx(path)


if __name__ == "__main__":
    unittest.main()
