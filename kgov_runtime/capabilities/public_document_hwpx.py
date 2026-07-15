#!/usr/bin/env python3
"""Bounded, read-only text extraction for HWPX documents."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
MAX_ENTRIES = 2_000
MAX_UNCOMPRESSED_BYTES = 50_000_000


def extract_hwpx(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                raise ValueError(f"HWPX archive has too many entries: {len(entries)}")
            total_size = sum(entry.file_size for entry in entries)
            if total_size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError(f"HWPX archive is too large after decompression: {total_size}")
            section_names = sorted(
                entry.filename for entry in entries
                if entry.filename.startswith("Contents/section") and entry.filename.endswith(".xml")
            )
            if not section_names:
                raise ValueError("HWPX archive has no Contents/section*.xml files")
            fragments: list[str] = []
            for name in section_names:
                root = ElementTree.fromstring(archive.read(name))
                for element in root.iter():
                    if element.tag.rsplit("}", 1)[-1] == "t" and element.text:
                        fragments.append(element.text)
    except zipfile.BadZipFile as exc:
        raise ValueError("file is not a valid HWPX ZIP archive") from exc
    return {
        "count": len(section_names),
        "sections": section_names,
        "text": "\n".join(fragment for fragment in fragments if fragment.strip()),
        "uncompressed_bytes": total_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only HWPX text extraction")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="print the deterministic expected fixture")
    args = parser.parse_args()
    try:
        if args.fixture:
            result = json.loads((ROOT / "tests" / "fixtures" / "capabilities" / "public-document-hwpx.json").read_text(encoding="utf-8"))
        elif args.path:
            result = extract_hwpx(args.path)
        else:
            parser.error("path is required unless --fixture is used")
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
