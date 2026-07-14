#!/usr/bin/env python3
"""KOSIS OpenAPI read-only adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonAdapterConfig, query_json, run_json_cli  # noqa: E402

CONFIG = JsonAdapterConfig(
    slug="kosis-official-statistics",
    default_endpoint="https://kosis.kr/openapi/Param/statisticsParameterData.do",
    allowed_hosts=frozenset(['kosis.kr']),
    credential_env="KOSIS_API_KEY",
    credential_param="apiKey",
    default_params={'method': 'getList', 'format': 'json', 'jsonVD': 'Y'},
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
