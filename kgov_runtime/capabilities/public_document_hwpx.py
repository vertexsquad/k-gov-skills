#!/usr/bin/env python3
"""Bounded, metadata-only inspection for HWPX documents."""

from __future__ import annotations

import argparse
import json
import warnings
import zipfile
import zlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Never, TypedDict
from xml.etree import ElementTree

from kgov_runtime.redaction import contains_direct_identifier

MAX_ENTRIES: Final = 2_000
MAX_ENTRY_BYTES: Final = 10_000_000
MAX_UNCOMPRESSED_BYTES: Final = 50_000_000
MAX_COMPRESSION_RATIO: Final = 200
MAX_SECTION_METADATA: Final = 100
MAX_SECTION_INDEX_DIGITS: Final = 10
LOCAL_FILE_HEADER_BYTES: Final = 30
HWPX_MIMETYPE: Final = b"application/hwp+zip"
SECTION_PREFIX: Final = "Contents/section"
SUPPORTED_COMPRESSION_TYPES: Final = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)


class SectionSummary(TypedDict):
    """Safe metadata for one HWPX section."""

    ordinal: int
    character_count: int


class SectionMetadata(TypedDict):
    """Bounded section summaries and their disclosure limit."""

    limit: int
    included: list[SectionSummary]
    truncated: bool


class HwpxResult(TypedDict):
    """Metadata-only public result for an inspected HWPX document."""

    section_count: int
    section_metadata: SectionMetadata
    extracted_character_count: int
    identifier_scan_status: Literal[
        "no-match-not-proof-of-redaction", "match-detected-review-blocked"
    ]
    text_emitted: Literal[False]
    manual_review_required: Literal[True]


class HwpxErrorCode(StrEnum):
    """Machine-readable reasons for rejecting an HWPX input."""

    INPUT_UNAVAILABLE = "input-unavailable"
    INVALID_ARCHIVE = "invalid-archive"
    ARCHIVE_POLICY = "archive-policy"
    MALFORMED_XML = "malformed-xml"


@dataclass(frozen=True, slots=True)
class HwpxInputError(Exception):
    """A sanitized HWPX rejection that never contains source material."""

    code: HwpxErrorCode

    def __str__(self) -> str:
        return f"HWPX input rejected ({self.code})"


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> Never:
        self.exit(2, "ERROR invalid arguments\n")


def extract_hwpx(path: Path) -> HwpxResult:
    """Inspect one HWPX without emitting or persisting extracted document text."""
    try:
        if not path.is_file():
            raise HwpxInputError(HwpxErrorCode.INPUT_UNAVAILABLE)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ENTRIES:
                    raise HwpxInputError(HwpxErrorCode.ARCHIVE_POLICY)
                if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                    raise HwpxInputError(HwpxErrorCode.ARCHIVE_POLICY)
                seen_names: set[str] = set()
                header_offsets: set[int] = set()
                local_entry_ranges: list[tuple[int, int]] = []
                sections_by_index: dict[int, zipfile.ZipInfo] = {}
                for entry in entries:
                    name = entry.filename
                    path_parts = name.rstrip("/").split("/")
                    compression_ratio = entry.file_size / max(entry.compress_size, 1)
                    if (
                        not name
                        or name.startswith("/")
                        or "\\" in name
                        or any(part in {"", ".", ".."} for part in path_parts)
                        or ":" in path_parts[0]
                        or name in seen_names
                        or bool(entry.flag_bits & 1)
                        or entry.compress_type not in SUPPORTED_COMPRESSION_TYPES
                        or entry.file_size > MAX_ENTRY_BYTES
                        or compression_ratio > MAX_COMPRESSION_RATIO
                    ):
                        raise HwpxInputError(HwpxErrorCode.ARCHIVE_POLICY)
                    seen_names.add(name)
                    if entry.header_offset < 0 or entry.header_offset in header_offsets:
                        raise HwpxInputError(HwpxErrorCode.INVALID_ARCHIVE)
                    header_offsets.add(entry.header_offset)
                    local_entry_ranges.append((entry.header_offset, entry.header_offset + LOCAL_FILE_HEADER_BYTES + entry.compress_size))
                    if name.startswith(SECTION_PREFIX) and name.endswith(".xml"):
                        suffix = name[len(SECTION_PREFIX) : -4]
                        if (
                            not suffix
                            or len(suffix) > MAX_SECTION_INDEX_DIGITS
                            or not suffix.isascii()
                            or not suffix.isdecimal()
                        ):
                            raise HwpxInputError(HwpxErrorCode.ARCHIVE_POLICY)
                        section_index = int(suffix)
                        if section_index in sections_by_index:
                            raise HwpxInputError(HwpxErrorCode.ARCHIVE_POLICY)
                        sections_by_index[section_index] = entry
                local_entry_ranges.sort()
                if any(end > next_start for (_, end), (next_start, _) in zip(local_entry_ranges, local_entry_ranges[1:])):
                    raise HwpxInputError(HwpxErrorCode.INVALID_ARCHIVE)
                if archive.testzip() is not None:
                    raise HwpxInputError(HwpxErrorCode.INVALID_ARCHIVE)
                entries_by_name = {entry.filename: entry for entry in entries}
                mimetype = entries_by_name.get("mimetype")
                if mimetype is None or archive.read(mimetype) != HWPX_MIMETYPE:
                    raise HwpxInputError(HwpxErrorCode.INVALID_ARCHIVE)
                section_entries = [
                    entry for _, entry in sorted(sections_by_index.items())
                ]
                if not section_entries:
                    raise HwpxInputError(HwpxErrorCode.INVALID_ARCHIVE)

                summaries: list[SectionSummary] = []
                character_count = 0
                identifier_detected = False
                for ordinal, entry in enumerate(section_entries, start=1):
                    xml_bytes = archive.read(entry)
                    xml_markup = xml_bytes.replace(b"\x00", b"").upper()
                    if b"<!DOCTYPE" in xml_markup or b"<!ENTITY" in xml_markup:
                        raise HwpxInputError(HwpxErrorCode.MALFORMED_XML)
                    root = ElementTree.fromstring(xml_bytes)
                    fragments: list[str] = []
                    pending_elements = [root]
                    while pending_elements:
                        element = pending_elements.pop()
                        if element.tag.rsplit("}", 1)[-1] == "t":
                            fragments.extend(element.itertext())
                            continue
                        pending_elements.extend(reversed(element))
                    section_text = "".join(fragments)
                    section_character_count = len(section_text)
                    character_count += section_character_count
                    identifier_detected = identifier_detected or contains_direct_identifier(
                        section_text
                    )
                    if len(summaries) < MAX_SECTION_METADATA:
                        summaries.append(
                            {
                                "ordinal": ordinal,
                                "character_count": section_character_count,
                            }
                        )
    except HwpxInputError:
        raise
    except (ElementTree.ParseError, LookupError) as exc:
        raise HwpxInputError(HwpxErrorCode.MALFORMED_XML) from exc
    except (
        EOFError,
        NotImplementedError,
        OSError,
        RuntimeError,
        UnicodeDecodeError,
        UserWarning,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
    ) as exc:
        raise HwpxInputError(HwpxErrorCode.INVALID_ARCHIVE) from exc

    return {
        "section_count": len(section_entries),
        "section_metadata": {
            "limit": MAX_SECTION_METADATA,
            "included": summaries,
            "truncated": len(section_entries) > MAX_SECTION_METADATA,
        },
        "extracted_character_count": character_count,
        "identifier_scan_status": (
            "match-detected-review-blocked"
            if identifier_detected
            else "no-match-not-proof-of-redaction"
        ),
        "text_emitted": False,
        "manual_review_required": True,
    }


def main() -> int:
    """Run the metadata-only HWPX CLI."""
    parser = _SafeArgumentParser(description="Read-only HWPX metadata inspection")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="print synthetic metadata")
    args = parser.parse_args()
    if args.fixture and args.path is not None:
        parser.error("fixture and path are mutually exclusive")
    if args.fixture:
        result: HwpxResult = {
            "section_count": 1,
            "section_metadata": {
                "limit": MAX_SECTION_METADATA,
                "included": [{"ordinal": 1, "character_count": 8}],
                "truncated": False,
            },
            "extracted_character_count": 8,
            "identifier_scan_status": "no-match-not-proof-of-redaction",
            "text_emitted": False,
            "manual_review_required": True,
        }
    elif args.path is not None:
        try:
            result = extract_hwpx(args.path)
        except HwpxInputError as exc:
            parser.exit(2, f"ERROR {exc}\n")
    else:
        parser.error("path is required unless --fixture is used")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result["identifier_scan_status"] == "match-detected-review-blocked" else 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/public-document-hwpx/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/public-document-hwpx/inspect-document/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
