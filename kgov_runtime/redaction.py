"""Shared direct-identifier scan for local redacted-input admission guards."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from typing import Final, TypeAlias, TypedDict, assert_never


DIRECT_IDENTIFIER_PATTERNS: Final = (
    re.compile(r"(?<!\d)01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(
        r"(?<!\d)(?P<birth_date>\d{6})[-\s]?"
        r"(?P<discriminator>[1-4])\d{6}(?!\d)"
    ),
    re.compile(
        r"(?<![A-Za-z0-9._%+-])"
        r"(?P<local>[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+)*)@"
        r"(?P<domain>(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,})(?![A-Za-z0-9_-]|\.[A-Za-z0-9_.-])"
    ),
    re.compile(
        r"(?<!\d)(?P<birth_date>\d{6})[-\s]?"
        r"(?P<discriminator>[5-8])\d{6}(?!\d)"
    ),
    re.compile(
        r"(?<!\d)(?:02|0(?:3[1-3]|4[1-4]|5[1-5]|6[1-4]|70))"
        r"[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"
    ),
)
_IDENTIFIER_CATEGORIES: Final = (
    "mobile_phone",
    "resident_registration_number",
    "email",
    "foreign_registration_number",
    "domestic_phone",
)
_REGISTRATION_CENTURIES: Final = {
    "resident_registration_number": {"1": 1900, "2": 1900, "3": 2000, "4": 2000},
    "foreign_registration_number": {"5": 1900, "6": 1900, "7": 2000, "8": 2000},
}
_MINUS_VARIANTS: Final = frozenset({"−"})
_MAX_EMAIL_LOCAL_CHARACTERS: Final = 64
_MAX_EMAIL_LABEL_CHARACTERS: Final = 63
_MAX_EMAIL_DOMAIN_CHARACTERS: Final = 253
_MAX_EMAIL_CHARACTERS: Final = 254


JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | Mapping[str, "JsonValue"]
    | list["JsonValue"]
    | tuple["JsonValue", ...]
)


class IdentifierFinding(TypedDict):
    """A non-sensitive identifier category and its location in an output."""

    path: str
    category: str


def find_direct_identifiers(
    text: str, *, on_date: date | None = None
) -> tuple[str, ...]:
    """Return detected identifier categories without returning matched text."""
    evaluation_date = date.today() if on_date is None else on_date
    normalized = unicodedata.normalize("NFKC", text)
    without_controls = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    )
    canonical = "".join(
        "-"
        if unicodedata.category(character) == "Pd" or character in _MINUS_VARIANTS
        else character
        for character in without_controls
    )
    canonical = re.sub(r"\s+", " ", canonical).strip()
    canonical = re.sub(r"\s*([@.\-])\s*", r"\1", canonical)
    findings: list[str] = []
    for category, pattern in zip(
        _IDENTIFIER_CATEGORIES, DIRECT_IDENTIFIER_PATTERNS, strict=True
    ):
        centuries = _REGISTRATION_CENTURIES.get(category)
        if centuries is not None:
            detected = False
            for match in pattern.finditer(canonical):
                birth_date = match.group("birth_date")
                try:
                    parsed_birth_date = date(
                        centuries[match.group("discriminator")]
                        + int(birth_date[:2]),
                        int(birth_date[2:4]),
                        int(birth_date[4:]),
                    )
                except ValueError:
                    continue
                if parsed_birth_date <= evaluation_date:
                    detected = True
                    break
        elif "local" in pattern.groupindex:
            detected = False
            for match in pattern.finditer(canonical):
                local = match.group("local")
                domain = match.group("domain")
                if (
                    len(local) <= _MAX_EMAIL_LOCAL_CHARACTERS
                    and len(domain) <= _MAX_EMAIL_DOMAIN_CHARACTERS
                    and len(match.group()) <= _MAX_EMAIL_CHARACTERS
                    and all(
                        len(label) <= _MAX_EMAIL_LABEL_CHARACTERS
                        for label in domain.split(".")
                    )
                ):
                    detected = True
                    break
        else:
            detected = pattern.search(canonical) is not None
        if detected:
            findings.append(category)
    return tuple(findings)


def scan_output(
    value: JsonValue, *, on_date: date | None = None
) -> tuple[IdentifierFinding, ...]:
    """Recursively return identifier categories and JSON-style paths only."""
    evaluation_date = date.today() if on_date is None else on_date
    findings: list[IdentifierFinding] = []

    def visit(current: JsonValue, path: str) -> None:
        match current:
            case str():
                findings.extend(
                    {"path": path, "category": category}
                    for category in find_direct_identifiers(
                        current, on_date=evaluation_date
                    )
                )
            case Mapping():
                for index, (key, item) in enumerate(current.items()):
                    key_categories = find_direct_identifiers(
                        key, on_date=evaluation_date
                    )
                    findings.extend(
                        {"path": f"{path}[key:{index}]", "category": category}
                        for category in key_categories
                    )
                    key_is_safe = key.isidentifier() and not key_categories
                    item_path = (
                        f"{path}.{key}" if key_is_safe else f"{path}[value:{index}]"
                    )
                    visit(item, item_path)
            case list() | tuple():
                for index, item in enumerate(current):
                    visit(item, f"{path}[{index}]")
            case int() | float() | bool() | None:
                return
            case unreachable:
                assert_never(unreachable)

    visit(value, "$")
    return tuple(findings)


def contains_direct_identifier(text: str, *, on_date: date | None = None) -> bool:
    """Return whether text contains a supported direct-identifier pattern."""
    return bool(find_direct_identifiers(text, on_date=on_date))
