from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from kgov_runtime.capabilities import public_document_hwpx as adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests/fixtures/capabilities/public-document-hwpx.json"
PUBLIC_KEYS = {"section_count", "section_metadata", "extracted_character_count", "identifier_scan_status", "text_emitted", "manual_review_required"}
SYNTHETIC_TEXT = "합성 검토 문서"
SYNTHETIC_IDENTIFIER = "010-2345-6789"


def _write_hwpx(
    path: Path,
    sections: list[str],
    *,
    extra_entries: tuple[tuple[str, str], ...] = (),
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/hwp+zip")
        for name, content in extra_entries:
            archive.writestr(name, content)
        for index, text in enumerate(sections):
            archive.writestr(
                f"Contents/section{index}.xml",
                '<hp:section xmlns:hp="urn:hancom:hwpx"><hp:p>'
                f"<hp:t>{text}</hp:t></hp:p></hp:section>",
            )


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "kgov_runtime.capabilities.public_document_hwpx", *arguments],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class AdapterTest(unittest.TestCase):
    def _assert_sanitized_input_error(self, completed: subprocess.CompletedProcess[str], private_values: tuple[str, ...]) -> None:
        self.assertEqual((2, ""), (completed.returncode, completed.stdout))
        combined_output = completed.stdout + completed.stderr
        for value in ("Traceback", *private_values):
            self.assertNotIn(value, combined_output)

    def test_fixture_is_metadata_only_and_matches_public_contract(self) -> None:
        # Given
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        # When
        completed = _run_cli("--fixture")

        # Then
        self.assertEqual((0, fixture, PUBLIC_KEYS, False, True), (completed.returncode, json.loads(completed.stdout), set(fixture), fixture["text_emitted"], fixture["manual_review_required"]))
        self.assertTrue({"text", "body", "raw"}.isdisjoint(fixture))

    def test_extracts_only_bounded_metadata_without_mutating_document(self) -> None:
        # Given
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.hwpx"
            _write_hwpx(path, [SYNTHETIC_TEXT])
            before = path.read_bytes()

            # When
            result = adapter.extract_hwpx(path)

            # Then
            self.assertEqual(before, path.read_bytes())
        self.assertEqual((PUBLIC_KEYS, 1, len(SYNTHETIC_TEXT), "no-match-not-proof-of-redaction", False), (set(result), result["section_count"], result["extracted_character_count"], result["identifier_scan_status"], result["text_emitted"]))
        self.assertEqual(
            {
                "limit": adapter.MAX_SECTION_METADATA,
                "included": [{"ordinal": 1, "character_count": len(SYNTHETIC_TEXT)}],
                "truncated": False,
            },
            result["section_metadata"],
        )

    def test_bounds_section_metadata_while_counting_all_sections(self) -> None:
        # Given
        section_total = adapter.MAX_SECTION_METADATA + 2
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "many-sections.hwpx"
            _write_hwpx(path, ["가"] * section_total)

            # When
            result = adapter.extract_hwpx(path)

        # Then
        metadata = result["section_metadata"]
        self.assertEqual((section_total, adapter.MAX_SECTION_METADATA, True, section_total), (result["section_count"], len(metadata["included"]), metadata["truncated"], result["extracted_character_count"]))

    def test_identifier_scan_blocks_cli_without_reflecting_identifier_or_text(self) -> None:
        # Given
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identifier.hwpx"
            _write_hwpx(path, [f"{SYNTHETIC_TEXT} {SYNTHETIC_IDENTIFIER}"])

            # When
            completed = _run_cli(str(path))

        # Then
        self.assertEqual(1, completed.returncode)
        result = json.loads(completed.stdout)
        self.assertEqual("match-detected-review-blocked", result["identifier_scan_status"])
        self.assertTrue(result["manual_review_required"])
        combined_output = completed.stdout + completed.stderr
        self.assertNotIn(SYNTHETIC_TEXT, combined_output)
        self.assertNotIn(SYNTHETIC_IDENTIFIER, combined_output)
        self.assertNotIn(str(path), combined_output)

    def test_counts_and_scans_many_nested_text_nodes_once(self) -> None:
        # Given
        nested_depth = 512
        xml = "<section>" + "<t>" * nested_depth + SYNTHETIC_IDENTIFIER + "</t>" * nested_depth + "</section>"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "split-identifier.hwpx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("mimetype", "application/hwp+zip")
                archive.writestr("Contents/section0.xml", xml)

            # When
            completed = _run_cli(str(path))

        # Then
        self.assertEqual(1, completed.returncode)
        result = json.loads(completed.stdout)
        self.assertEqual((len(SYNTHETIC_IDENTIFIER), len(SYNTHETIC_IDENTIFIER), "match-detected-review-blocked"), (result["extracted_character_count"], result["section_metadata"]["included"][0]["character_count"], result["identifier_scan_status"]))
        self.assertNotIn(SYNTHETIC_IDENTIFIER, completed.stdout + completed.stderr)

    def test_rejects_malformed_or_ambiguous_section_indexes(self) -> None:
        # Given
        cases = (
            ("non-ascii", ("Contents/section².xml",)),
            ("unbounded", (f"Contents/section{'1' * 5_000}.xml",)),
            ("duplicate", ("Contents/section1.xml", "Contents/section01.xml")),
        )
        section_content = "<section><t>SECTION_CONTROLLED_CONTENT</t></section>"
        with tempfile.TemporaryDirectory() as directory:
            for label, section_names in cases:
                with self.subTest(label=label):
                    path = Path(directory) / f"{label}.hwpx"
                    _write_hwpx(path, [], extra_entries=tuple((name, section_content) for name in section_names))

                    # When
                    completed = _run_cli(str(path))

                    # Then
                    self._assert_sanitized_input_error(completed, (str(path), section_content, *section_names))

    def test_rejects_undecodable_or_overlapping_entries_without_reflection(self) -> None:
        # Given
        private_name, alias_name, entry_content = "private-name.bin", "alias-name.bin", "PRIVATE_NAME_CONTENT"
        with tempfile.TemporaryDirectory() as directory:
            for undecodable_name in (True, False):
                with self.subTest(undecodable_name=undecodable_name):
                    path = Path(directory) / f"malformed-{undecodable_name}.hwpx"
                    _write_hwpx(path, [SYNTHETIC_TEXT], extra_entries=((private_name, entry_content), (alias_name, "alias")))
                    archive_bytes = bytearray(path.read_bytes())
                    private_offset = archive_bytes.find(private_name.encode()) - 30
                    if undecodable_name:
                        central_header = archive_bytes.rfind(private_name.encode()) - 46
                        struct.pack_into("<H", archive_bytes, central_header + 8, struct.unpack_from("<H", archive_bytes, central_header + 8)[0] | 0x800)
                        archive_bytes[central_header + 46] = 0xFF
                    else:
                        central_header = archive_bytes.rfind(alias_name.encode()) - 46
                        struct.pack_into("<L", archive_bytes, central_header + 42, private_offset)
                    path.write_bytes(archive_bytes)

                    # When
                    completed = _run_cli(str(path))

                    # Then
                    self._assert_sanitized_input_error(completed, (str(path), "Overlapped entries", private_name, alias_name, entry_content))

    def test_rejects_non_hwpx_and_malformed_xml_without_input_reflection(self) -> None:
        # Given
        cases = (("not-a-zip.hwpx", b"PRIVATE_ARCHIVE_BYTES"), ("malformed.hwpx", b"<private-raw-xml>"))
        with tempfile.TemporaryDirectory() as directory:
            for filename, content in cases:
                with self.subTest(filename=filename):
                    path = Path(directory) / filename
                    if filename == "not-a-zip.hwpx":
                        path.write_bytes(content)
                    else:
                        _write_hwpx(path, [])
                        with zipfile.ZipFile(path, "a") as archive:
                            archive.writestr("Contents/section0.xml", content)

                    # When
                    completed = _run_cli(str(path))

                    # Then
                    self._assert_sanitized_input_error(
                        completed, (str(path), content.decode())
                    )

    def test_unknown_xml_encoding_is_sanitized_as_input_error(self) -> None:
        # Given
        unknown_encoding = "x-private-unknown"
        xml = (
            f'<?xml version="1.0" encoding="{unknown_encoding}"?>'
            f"<section><t>{SYNTHETIC_IDENTIFIER}</t></section>"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unknown-encoding.hwpx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("mimetype", "application/hwp+zip")
                archive.writestr("Contents/section0.xml", xml)

            # When
            completed = _run_cli(str(path))

        # Then
        self._assert_sanitized_input_error(
            completed, (str(path), unknown_encoding, SYNTHETIC_IDENTIFIER)
        )

    def test_rejects_utf_encoded_dtd(self) -> None:
        # Given
        xml = (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<!DOCTYPE section [<!ENTITY private "synthetic">]>'
            '<section><t>&private;</t></section>'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dtd.hwpx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("mimetype", "application/hwp+zip")
                archive.writestr("Contents/section0.xml", xml.encode("utf-16"))

            # When / Then
            with self.assertRaises(adapter.HwpxInputError) as raised:
                adapter.extract_hwpx(path)
        self.assertEqual(adapter.HwpxErrorCode.MALFORMED_XML, raised.exception.code)

    def test_rejects_traversal_entry(self) -> None:
        # Given
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "traversal.hwpx"
            _write_hwpx(path, [SYNTHETIC_TEXT], extra_entries=(("../private.xml", "secret"),))

            # When / Then
            with self.assertRaises(adapter.HwpxInputError):
                adapter.extract_hwpx(path)

    def test_rejects_entry_count_and_uncompressed_size_limits(self) -> None:
        # Given
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bounded.hwpx"
            _write_hwpx(path, [SYNTHETIC_TEXT], extra_entries=(("extra", "x"),))

            # When / Then
            with mock.patch.object(adapter, "MAX_ENTRIES", 2):
                with self.assertRaises(adapter.HwpxInputError):
                    adapter.extract_hwpx(path)
            with mock.patch.object(adapter, "MAX_UNCOMPRESSED_BYTES", 10):
                with self.assertRaises(adapter.HwpxInputError):
                    adapter.extract_hwpx(path)

    def test_rejects_compression_bomb(self) -> None:
        # Given
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compression-bomb.hwpx"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("mimetype", "application/hwp+zip")
                archive.writestr(
                    "Contents/section0.xml",
                    '<hp:section xmlns:hp="urn:hancom:hwpx"><hp:t>'
                    + ("가" * 10_000)
                    + "</hp:t></hp:section>",
                )

            # When / Then
            with mock.patch.object(adapter, "MAX_COMPRESSION_RATIO", 2):
                with self.assertRaises(adapter.HwpxInputError):
                    adapter.extract_hwpx(path)

    def test_rejects_corrupt_non_section_entries_without_reflection(self) -> None:
        # Given
        attachment_name = "Attachments/private-synthetic.bin"
        attachment_content = "SYNTHETIC_ATTACHMENT_CONTENT"
        with tempfile.TemporaryDirectory() as directory:
            cases = ((zipfile.ZIP_STORED, 0, 0xF8, 0x07), (zipfile.ZIP_DEFLATED, 0, 0xF8, 0x07), (zipfile.ZIP_BZIP2, -1, 0, 0), (zipfile.ZIP_LZMA, 4, 0, 0xFF))
            for compression, relative_offset, mask, value in cases:
                with self.subTest(compression=compression):
                    path = Path(directory) / f"corrupt-{compression}.hwpx"
                    with zipfile.ZipFile(path, "w", compression=compression) as archive:
                        archive.writestr("mimetype", "application/hwp+zip")
                        archive.writestr("Contents/section0.xml", "<section><t>synthetic</t></section>")
                        archive.writestr(attachment_name, attachment_content)
                    with zipfile.ZipFile(path) as archive:
                        attachment = archive.getinfo(attachment_name)
                    if relative_offset >= 0:
                        archive_bytes = bytearray(path.read_bytes())
                        content_offset = attachment.header_offset + len(attachment.FileHeader()) + relative_offset
                        archive_bytes[content_offset] = (archive_bytes[content_offset] & mask) | value
                        path.write_bytes(archive_bytes)

                    # When
                    completed = _run_cli(str(path))

                    # Then
                    self._assert_sanitized_input_error(completed, (str(path), attachment_name, attachment_content))

    def test_rejects_encrypted_entry(self) -> None:
        # Given
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "encrypted.hwpx"
            _write_hwpx(path, [SYNTHETIC_TEXT])
            archive_bytes = bytearray(path.read_bytes())
            for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
                position = archive_bytes.find(signature)
                flags = struct.unpack_from("<H", archive_bytes, position + flag_offset)[0]
                struct.pack_into("<H", archive_bytes, position + flag_offset, flags | 1)
            path.write_bytes(archive_bytes)

            # When / Then
            with self.assertRaises(adapter.HwpxInputError):
                adapter.extract_hwpx(path)

    def test_cli_sanitizes_missing_path_and_extra_argument_errors(self) -> None:
        # Given
        private_path = "/private/records/secret.hwpx"

        # When
        completed_cases = (_run_cli(private_path), _run_cli("--fixture", private_path))

        # Then
        for completed in completed_cases:
            self.assertEqual(2, completed.returncode)
            self.assertNotIn(private_path, completed.stderr)


if __name__ == "__main__":
    unittest.main()
