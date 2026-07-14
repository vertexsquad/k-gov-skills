"""Reusable CLI harness for read-only JSON public-data adapters."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional
from .http import fetch_json, normalize_records


@dataclass(frozen=True)
class JsonAdapterConfig:
    slug: str
    default_endpoint: str
    allowed_hosts: frozenset[str]
    credential_env: Optional[str] = None
    credential_param: Optional[str] = None
    default_params: Optional[Mapping[str, Any]] = None


def parse_params(values: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"parameter must use key=value form: {value}")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("parameter key must not be empty")
        params[key] = raw
    return params


def load_fixture(path: Path) -> dict[str, Any]:
    return normalize_records(json.loads(path.read_text(encoding="utf-8")))


def query_json(
    config: JsonAdapterConfig,
    *,
    endpoint: Optional[str] = None,
    params: Optional[Mapping[str, Any]] = None,
    opener: Optional[Callable[..., Any]] = None,
    resolver: Optional[Callable[[str], Iterable[Any]]] = None,
) -> dict[str, Any]:
    merged = dict(config.default_params or {})
    merged.update(params or {})
    kwargs: dict[str, Any] = {
        "params": merged,
        "allowed_hosts": set(config.allowed_hosts),
        "credential_env": config.credential_env,
        "credential_param": config.credential_param,
    }
    if opener is not None:
        kwargs["opener"] = opener
    if resolver is not None:
        kwargs["resolver"] = resolver
    payload = fetch_json(endpoint or config.default_endpoint, **kwargs)
    return normalize_records(payload)


def run_json_cli(config: JsonAdapterConfig, fixture_path: Path) -> int:
    parser = argparse.ArgumentParser(description=f"Read-only adapter: {config.slug}")
    parser.add_argument("--endpoint", default=config.default_endpoint)
    parser.add_argument("--param", action="append", default=[], help="repeatable key=value query parameter")
    parser.add_argument("--fixture", action="store_true", help="use the repository fixture; no network or credential")
    args = parser.parse_args()
    try:
        result = load_fixture(fixture_path) if args.fixture else query_json(
            config,
            endpoint=args.endpoint,
            params=parse_params(args.param),
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
