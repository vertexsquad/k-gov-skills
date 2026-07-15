#!/usr/bin/env python3
"""나라장터 발주계획 공개 API read-only adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonAdapterConfig, query_json, run_json_cli  # noqa: E402

CONFIG = JsonAdapterConfig(
    slug="public-procurement-research",
    default_endpoint="https://apis.data.go.kr/1230000/ao/OrderPlanSttusService",
    allowed_hosts=frozenset(['apis.data.go.kr', 'g2b.go.kr', 'd2b.go.kr', 's2b.kr']),
    credential_env="DATA_GO_KR_API_KEY",
    credential_param="serviceKey",
    default_params={'type': 'json'},
)
FIXTURE = ROOT / "tests" / "fixtures" / "capabilities" / "public-procurement-research.json"


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
