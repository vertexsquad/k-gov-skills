"""Shared direct-identifier scan for local redacted-input admission guards."""

from __future__ import annotations

import re


DIRECT_IDENTIFIER_PATTERNS = (
    re.compile(r"(?<!\d)01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


def contains_direct_identifier(text: str) -> bool:
    """Return whether text contains a supported direct-identifier pattern."""
    return any(pattern.search(text) for pattern in DIRECT_IDENTIFIER_PATTERNS)
