#!/usr/bin/env python3
"""기상·재난 공공데이터 API read-only adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonAdapterConfig, query_json, run_json_cli  # noqa: E402

CONFIG = JsonAdapterConfig(
    slug="disaster-geospatial-brief",
    default_endpoint="https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
    allowed_hosts=frozenset(['apis.data.go.kr', 'weather.go.kr']),
    credential_env="KMA_OPEN_API_KEY",
    credential_param="serviceKey",
    default_params={'dataType': 'JSON'},
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
