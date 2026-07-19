#!/usr/bin/env python3
"""Inspect a public Korean official source without executing page actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html import unescape
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.http import fetch_text  # noqa: E402

ALLOWED_HOSTS = {
    "gov.kr",
    "data.go.kr",
    "law.go.kr",
    "nts.go.kr",
    "hometax.go.kr",
    "wetax.go.kr",
    "assembly.go.kr",
    "weather.go.kr",
    "g2b.go.kr",
    "mfds.go.kr",
    "nhis.or.kr",
    "e-gen.or.kr",
    "lh.or.kr",
    "i-sh.co.kr",
    "realtyprice.kr",
}
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "official-source-research.json"


def inspect_source(
    url: str,
    *,
    opener: Optional[Callable[..., Any]] = None,
    resolver: Optional[Callable[[str], Iterable[Any]]] = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"allowed_hosts": ALLOWED_HOSTS}
    if opener is not None:
        kwargs["opener"] = opener
    if resolver is not None:
        kwargs["resolver"] = resolver
    response = fetch_text(url, **kwargs)
    text = response.pop("text")
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", unescape(match.group(1))).strip() if match else ""
    body = text.encode("utf-8")
    return {
        **response,
        "title": title,
        "content_length": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Korean official-source inspector")
    parser.add_argument("url", nargs="?")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    try:
        if args.fixture:
            result = json.loads(FIXTURE.read_text(encoding="utf-8"))
        elif args.url:
            result = inspect_source(args.url)
        else:
            parser.error("URL is required unless --fixture is used")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
