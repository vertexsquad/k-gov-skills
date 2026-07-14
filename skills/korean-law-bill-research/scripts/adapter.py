#!/usr/bin/env python3
"""국가법령정보 공개 API read-only adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonAdapterConfig, query_json, run_json_cli  # noqa: E402

CONFIG = JsonAdapterConfig(
    slug="korean-law-bill-research",
    default_endpoint="https://www.law.go.kr/DRF/lawSearch.do",
    allowed_hosts=frozenset(['law.go.kr', 'open.assembly.go.kr']),
    credential_env="LAW_OC",
    credential_param="OC",
    default_params={'target': 'law', 'type': 'JSON'},
)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample.json"


def query(
    *,
    endpoint: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    opener: Optional[Callable[..., Any]] = None,
    resolver: Optional[Callable[[str], Iterable[Any]]] = None,
) -> dict[str, Any]:
    return query_json(CONFIG, endpoint=endpoint, params=params, opener=opener, resolver=resolver)


def main() -> int:
    return run_json_cli(CONFIG, FIXTURE)


if __name__ == "__main__":
    raise SystemExit(main())
