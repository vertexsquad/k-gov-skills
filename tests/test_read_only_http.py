"""Policy-enforced read-only HTTP contract tests.

# noqa: SIZE_OK -- Issue #30 owns one HTTP contract test path and requires the
# complete authorization, robots, rate, transport, and output boundary matrix.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import date
from http.client import HTTPResponse, IncompleteRead
from pathlib import Path
from typing import Any, TypedDict
from urllib.error import URLError
from urllib.request import ProxyHandler, Request

from unittest.mock import Mock, patch

import kgov_runtime
from kgov_runtime.capabilities import korean_law_bill_research
from kgov_runtime.json_adapter import query_json, strict_json_loads
from kgov_runtime.http import (
    HttpPolicyEnforcer,
    HttpTransport,
    ReadOnlyHttpError,
    RejectRedirectHandler,
    SourceReceipt,
    SourceRequest,
    UnsafeEndpointError,
    _policy_urlopen,
    _strict_json,
    build_url,
    fetch_json,
    fetch_text,
    open_policy_state,
    safe_urlopen,
    validate_public_https_url,
)
from kgov_runtime.policy_state import PolicyState, PolicyStateUnavailableError, policy_state_path
from kgov_runtime.source_policy import SourcePolicyRegistry

OPERATION = "kgov/example/inspect/v1"


class CatalogFixture(TypedDict):
    schema_version: int
    source_policies: list[dict[str, Any]]
    runtime_contracts: list[dict[str, Any]]
    shared_capabilities: list[dict[str, Any]]


def reviewed_catalog(
    *, robots: str = "required", media_type: str = "text/html", max_bytes: int = 1000
) -> CatalogFixture:
    policy = {
        "id": "example-web",
        "revision": 2,
        "enabled": True,
        "institution": "Example",
        "channel": "web",
        "scope": {
            "origins": ["https://www.example.go.kr"],
            "path_rules": [{"match": "prefix", "path": "/"}],
            "methods": ["GET"],
        },
        "review": {
            "reviewed_on": "2026-09-01",
            "expires_on": "2026-10-01",
            "evidence_urls": ["https://www.example.go.kr/review"],
        },
        "robots": {"status": robots},
        "terms": {"status": "allowed", "url": "https://www.example.go.kr/terms"},
        "rate_limit": {
            "status": "reviewed",
            "requests": 100,
            "per_seconds": 60,
            "burst": 100,
            "max_wait_seconds": 0,
        },
        "response": {
            "status": "reviewed",
            "max_bytes": max_bytes,
            "media_types": [media_type],
        },
        "license": {
            "status": "reviewed",
            "url": "https://www.example.go.kr/license",
            "allowed_output_modes": ["link-only"],
            "redistribution": "link-only",
        },
        "retention": {"raw_content": "none", "receipts": "metadata-only"},
    }
    if robots == "documented-api-exemption":
        policy["channel"] = "api"
        policy["scope"]["path_rules"] = [{"match": "exact", "path": "/page"}]
        policy["robots"]["evidence_url"] = "https://www.example.go.kr/robots-review"
    operation = {
        "id": OPERATION,
        "schema_status": "declared",
        "source_policy_ids": ["example-web"],
        "source_output_mode": "link-only",
        "fixture_argv": ["--fixture"],
    }
    contract = {
        "id": "kgov/example/v1",
        "capability_slug": "example",
        "module": "kgov_runtime.capabilities.example",
        "kind": "retrieval",
        "network_mode": "optional-live",
        "default_operation_id": OPERATION,
        "operations": [operation],
        "exit_codes": {
            "success": 0,
            "review_blocked": 1,
            "input_error": 2,
            "policy_blocked": 3,
            "upstream_error": 4,
        },
        "forbidden_output_keys": [
            "authorization",
            "body",
            "cookie",
            "credential",
            "headers",
            "raw",
            "text",
        ],
    }
    return {
        "schema_version": 6,
        "source_policies": [policy],
        "runtime_contracts": [contract],
        "shared_capabilities": [
            {
                "slug": "example",
                "source_policy_ids": ["example-web"],
                "runtime_contract_id": "kgov/example/v1",
            }
        ],
    }


class Response:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        media_type: str = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.body, self.status = body, status
        self.headers = {"Content-Type": media_type} | (headers or {})

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


@contextmanager
def wire_response(payload: bytes, *, timeout: bool = False) -> Iterator[HTTPResponse]:
    """Feed real HTTP parsing through local sockets; optionally withhold body EOF."""
    reader, writer = socket.socketpair()
    with reader, writer:
        reader.settimeout(0.01 if timeout else 1.0)
        writer.settimeout(1.0)
        writer.sendall(payload)
        if not timeout:
            writer.shutdown(socket.SHUT_WR)
        with HTTPResponse(reader) as response:
            response.begin()
            yield response


class FakeState:
    def __init__(self) -> None:
        self.opens = 0
        self.retry_after: list[str] = []

    def open(self, _policy, opener):
        self.opens += 1
        return opener()

    def record_retry_after(self, _policy, value: str) -> float:
        self.retry_after.append(value)
        return float(value)


def assert_live_state_initialization(test, adapter, policy_id, url, expected_order):
    """Exercise caller-local ordering with real policy parsing and temporary state."""
    test.assertIs(policy_state_path, adapter._state_path)
    catalog = reviewed_catalog()
    slug = adapter.OPERATION_ID.split("/")[1]
    policy = catalog["source_policies"][0]
    policy["id"] = policy_id
    policy["scope"]["origins"] = [url.rsplit("/", 1)[0]]
    if policy_id == "law-go-kr-drf-api":
        policy["scope"]["origins"] = ["https://www.law.go.kr"]
    contract = catalog["runtime_contracts"][0]
    contract.update(id=f"kgov/{slug}/v1", capability_slug=slug,
                    module=f"kgov_runtime.capabilities.{slug.replace('-', '_')}",
                    default_operation_id=adapter.OPERATION_ID)
    contract["operations"][0].update(id=adapter.OPERATION_ID, source_policy_ids=[policy_id])
    catalog["shared_capabilities"][0].update(
        slug=slug, source_policy_ids=[policy_id], runtime_contract_id=contract["id"]
    )
    parse = SourcePolicyRegistry.from_catalog
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "nested/state.sqlite3"
        catalog_path = Path(directory) / "catalog.json"
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
        registry = parse(catalog, on_date=date(2026, 9, 6))
        for fault in (None, "path", "mkdir", "state", "untranslated", "enforcer", "denied"):
            events = []
            error = PolicyStateUnavailableError(path) if fault == "state" else OSError("synthetic")
            if fault == "untranslated":
                error = ValueError("synthetic")

            class TracedRegistry:
                @property
                def policies(self):
                    events.append("select")
                    return registry.policies

                def authorize(self, *args):
                    events.append("authorize")
                    test.assertEqual((url.replace("/%70age", "/page"), adapter.OPERATION_ID), args)
                    return registry.authorize(*args)

            traced = TracedRegistry()

            def from_catalog(value, **kwargs):
                events.append("registry")
                test.assertEqual(catalog, value)
                test.assertEqual({"on_date": date(2026, 9, 6)}, kwargs)
                return traced

            def state_path():
                events.append("path")
                if fault == "path":
                    raise error
                return path

            mkdir_original = Path.mkdir

            def mkdir(parent, **kwargs):
                events.append("mkdir")
                test.assertEqual(path.parent, parent)
                test.assertEqual({"parents": True, "exist_ok": True}, kwargs)
                if fault == "mkdir":
                    raise error
                with patch.object(Path, "mkdir", mkdir_original):
                    mkdir_original(parent, **kwargs)

            clock, sleeper = Mock(return_value=1000.0), Mock(side_effect=test.fail)

            def construct(selected, **kwargs):
                events.append("state")
                test.assertEqual(path, selected)
                test.assertEqual({"clock": clock, "sleeper": sleeper}, kwargs)
                if fault in {"state", "untranslated"}:
                    raise error
                return PolicyState(selected, **kwargs)

            def enforcer(*args):
                events.append("enforcer")
                if fault == "enforcer":
                    raise error
                return HttpPolicyEnforcer(*args)

            validate = getattr(adapter, "_validated_lookup_url", None)
            runtime_type = getattr(adapter, "LegalRuntime", None)

            def canonicalize(value):
                events.append("canonicalize")
                return validate(value)

            def runtime(*args):
                events.append("runtime")
                return runtime_type(*args)

            if fault == "denied":
                catalog["source_policies"][0]["enabled"] = False
                registry = parse(catalog, on_date=date(2026, 9, 6))
                catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            with (
                patch.object(adapter, "_validated_lookup_url", side_effect=canonicalize) if validate else nullcontext(),
                patch.object(adapter, "LegalRuntime", side_effect=runtime) if runtime_type else nullcontext(),
                patch.object(adapter, "CATALOG", catalog_path),
                patch.object(adapter, "date", **{"today.return_value": date(2026, 9, 6)}),
                patch.object(SourcePolicyRegistry, "from_catalog", side_effect=from_catalog),
                patch.object(adapter, "_state_path", side_effect=state_path) as resolve,
                patch.object(Path, "mkdir", mkdir),
                patch("kgov_runtime.http.PolicyState", side_effect=construct) as constructor,
                patch.object(adapter, "open_policy_state", wraps=open_policy_state) as open_state,
                patch.object(time, "time", clock),
                patch.object(time, "sleep", sleeper),
                patch.object(adapter, "HttpPolicyEnforcer", side_effect=enforcer),
                patch("kgov_runtime.http._network_resolver", return_value=["1.1.1.1"]) as dns,
                patch("socket.getaddrinfo", side_effect=test.fail) as system_dns,
                patch("kgov_runtime.http._policy_urlopen", side_effect=[
                    Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                    Response(b"<title>Synthetic</title>"),
                ]) as opener,
                patch.object(os.environ, "get", side_effect=test.fail) as credential,
            ):
                try:
                    result = adapter._live_runtime() if policy_id == "law-go-kr-drf-api" else adapter._live(url)
                except (OSError, ValueError, RuntimeError) as caught:
                    test.assertIsNotNone(fault)
                    if fault in {"mkdir", "state"}:
                        test.assertIs(type(caught), ReadOnlyHttpError)
                        test.assertEqual("budget-exhausted", caught.status)
                        test.assertIs(error, caught.__cause__)
                        test.assertIs(error, caught.__context__)
                        test.assertTrue(caught.__suppress_context__)
                    elif fault == "denied":
                        test.assertIs(type(caught), ReadOnlyHttpError)
                        test.assertEqual("policy-disabled", caught.status)
                    else:
                        test.assertIs(error, caught)
                        test.assertIsNone(caught.__cause__)
                else:
                    test.assertIsNone(fault)
                    test.assertTrue(path.is_file())
                    if policy_id == "law-go-kr-drf-api":
                        test.assertEqual("official-live", result.execution_mode)
                    else:
                        test.assertEqual("allowed", result["source_receipt"]["outcome"])
                order = list(expected_order)
                if fault == "denied":
                    order = order[:order.index("authorize") + 1]
                    resolve.assert_not_called()
                    open_state.assert_not_called()
                    constructor.assert_not_called()
                else:
                    order += ["path"]
                    resolve.assert_called_once_with()
                    if fault != "path":
                        open_state.assert_called_once_with(path)
                        order += ["mkdir"]
                        if fault != "mkdir":
                            order += ["state"]
                            constructor.assert_called_once_with(path, clock=clock, sleeper=sleeper)
                            if fault not in {"state", "untranslated"}:
                                order += ["enforcer"]
                                if fault is None and runtime_type:
                                    order += ["runtime"]
                        else:
                            constructor.assert_not_called()
                    else:
                        open_state.assert_not_called()
                        constructor.assert_not_called()
                test.assertEqual(order, events[:len(order)])
                if fault is not None:
                    test.assertEqual(order, events)
                    dns.assert_not_called()
                    opener.assert_not_called()
                system_dns.assert_not_called()
                credential.assert_not_called()
                sleeper.assert_not_called()


class ReadOnlyHttpTest(unittest.TestCase):
    def test_open_policy_state_error_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/state.sqlite3"
            for _ in range(2):
                clock, sleeper = Mock(return_value=1000.0), Mock(side_effect=self.fail)
                with (
                    patch("kgov_runtime.http.time.time", clock),
                    patch("kgov_runtime.http.time.sleep", sleeper),
                    patch("kgov_runtime.http.PolicyState", wraps=PolicyState) as constructor,
                ):
                    state = open_policy_state(path)
                constructor.assert_called_once_with(path, clock=clock, sleeper=sleeper)
                self.assertIs(clock, state._clock)
                self.assertIs(sleeper, state._sleeper)
                self.assertTrue(path.is_file())
                self.assertEqual(0, state.purge())
                sleeper.assert_not_called()
            for stage in ("mkdir", "state"):
                for error in (OSError("synthetic"), PolicyStateUnavailableError(path), ValueError("synthetic")):
                    with (
                        self.subTest(stage=stage, error=type(error)),
                        patch.object(Path, "mkdir", side_effect=error if stage == "mkdir" else None) as mkdir,
                        patch("kgov_runtime.http.PolicyState", side_effect=error) as constructor,
                        self.assertRaises((ReadOnlyHttpError, ValueError)) as raised,
                    ):
                        open_policy_state(path)
                    mkdir.assert_called_once_with(parents=True, exist_ok=True)
                    if stage == "mkdir":
                        constructor.assert_not_called()
                    else:
                        constructor.assert_called_once_with(path, clock=time.time, sleeper=time.sleep)
                    if isinstance(error, ValueError):
                        self.assertIs(error, raised.exception)
                        self.assertIsNone(raised.exception.__cause__)
                    else:
                        self.assertIs(type(raised.exception), ReadOnlyHttpError)
                        self.assertEqual("budget-exhausted", raised.exception.status)
                        self.assertIs(error, raised.exception.__cause__)
                        self.assertIs(error, raised.exception.__context__)
                        self.assertTrue(raised.exception.__suppress_context__)
            corrupt = Path(directory) / "corrupt.sqlite3"
            corrupt.write_bytes(b"synthetic-corrupt-sqlite")
            with self.assertRaises(ReadOnlyHttpError) as raised:
                open_policy_state(corrupt)
            self.assertEqual("budget-exhausted", raised.exception.status)
            self.assertIs(type(raised.exception.__cause__), PolicyStateUnavailableError)
            self.assertIsInstance(raised.exception.__cause__.__cause__, sqlite3.Error)

    def registry(self, **kwargs) -> SourcePolicyRegistry:
        return SourcePolicyRegistry.from_catalog(
            reviewed_catalog(**kwargs), on_date=date(2026, 9, 6)
        )

    def enforcer(self, registry, responses, state=None, opened=None):
        calls = [] if opened is None else opened

        def opener(request, timeout=0):
            calls.append(request.full_url)
            return responses.pop(0)

        return HttpPolicyEnforcer(
            registry,
            state or FakeState(),
            HttpTransport(opener, lambda _host: ["1.1.1.1"], 10.0),
        )

    def test_authorization_and_registry_owned_identity_precede_state_dns_and_opener(
        self,
    ) -> None:
        registry, touched, state = self.registry(), [], FakeState()
        policy = registry.policies[0]
        enforcer = HttpPolicyEnforcer(
            registry,
            state,
            HttpTransport(
                lambda *_a, **_k: touched.append("open"),
                lambda _h: touched.append("dns") or ["1.1.1.1"],
                10.0,
            ),
        )
        for request in (
            SourceRequest(
                "https://www.example.go.kr/page", "kgov/example/missing/v1", policy
            ),
            SourceRequest("https://www.example.go.kr/page", OPERATION, replace(policy)),
        ):
            with (
                self.subTest(request=request),
                self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"),
            ):
                enforcer.fetch_text(request, lambda document: {"title": document.text})
        self.assertEqual(([], 0), (touched, state.opens))

    def test_required_robots_and_target_each_reserve_once_then_return_metadata_receipt(
        self,
    ) -> None:
        registry, state, opened = self.registry(), FakeState(), []
        enforcer = self.enforcer(
            registry,
            [
                Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                Response(b"<title>Official</title>"),
            ],
            state,
            opened,
        )
        result = enforcer.fetch_text(
            SourceRequest(
                "https://www.example.go.kr/page?ignored=1",
                OPERATION,
                registry.policies[0],
            ),
            lambda document: {"title": document.text[7:-8]},
        )
        self.assertEqual(
            (
                2,
                [
                    "https://www.example.go.kr/robots.txt",
                    "https://www.example.go.kr/page?ignored=1",
                ],
            ),
            (state.opens, opened),
        )
        self.assertEqual({"title": "Official"}, result.value)
        self.assertEqual(
            (OPERATION, "example-web", 2, "allowed"),
            (
                result.source_receipt.operation_id,
                result.source_receipt.policy_id,
                result.source_receipt.policy_revision,
                result.source_receipt.outcome,
            ),
        )

    def test_body_read_failures_stop_before_projection_or_receipt(self) -> None:
        for method in ("fetch_text", "fetch_json"):
            for robots in (True, False):
                for timeout in (False, True):
                    registry, state, opened = (
                        self.registry(media_type="application/json"),
                        FakeState(),
                        [],
                    )
                    media = "text/plain" if robots else "application/json"
                    body = b"User-agent: *\nAllow: /\n" if robots else b'{"title":"ok"}'
                    payload = (
                        (
                            f"HTTP/1.1 200 OK\r\nContent-Type: {media}\r\n"
                            f"Transfer-Encoding: chunked\r\n\r\n{len(body):x}\r\n"
                        ).encode()
                        + body
                        + b"\r\n20\r\nsynthetic-body-marker"
                    )
                    projector, results = Mock(), []
                    with (
                        self.subTest(method=method, robots=robots, timeout=timeout),
                        wire_response(payload, timeout=timeout) as response,
                        patch(
                            "kgov_runtime.http.SourceReceipt", wraps=SourceReceipt
                        ) as receipt,
                    ):
                        responses = (
                            []
                            if robots
                            else [
                                Response(
                                    b"User-agent: *\nAllow: /\n",
                                    media_type="text/plain",
                                )
                            ]
                        )
                        responses.append(response)
                        enforcer = self.enforcer(registry, responses, state, opened)
                        with self.assertRaises(ReadOnlyHttpError) as raised:
                            results.append(
                                getattr(enforcer, method)(
                                    SourceRequest(
                                        "https://www.example.go.kr/page",
                                        OPERATION,
                                        registry.policies[0],
                                    ),
                                    projector,
                                )
                            )
                        expected = "robots-denied" if robots else "upstream-unavailable"
                        self.assertEqual(
                            (expected, expected),
                            (raised.exception.status, str(raised.exception)),
                        )
                        self.assertIsInstance(
                            raised.exception.__cause__,
                            TimeoutError if timeout else IncompleteRead,
                        )
                        self.assertTrue(response.isclosed())
                        projector.assert_not_called()
                        receipt.assert_not_called()
                        self.assertEqual([], results)
                        expected_urls = ["https://www.example.go.kr/robots.txt"]
                        if not robots:
                            expected_urls.append("https://www.example.go.kr/page")
                        self.assertEqual(
                            (len(expected_urls), expected_urls), (state.opens, opened)
                        )

    def test_complete_chunked_responses_still_project_and_return_receipt(self) -> None:
        for method in ("fetch_text", "fetch_json"):
            registry, state = self.registry(media_type="application/json"), FakeState()
            with (
                self.subTest(method=method),
                wire_response(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
                    b"Transfer-Encoding: chunked\r\n\r\n17\r\n"
                    b"User-agent: *\nAllow: /\n\r\n0\r\n\r\n"
                ) as robots,
                wire_response(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    b"Transfer-Encoding: chunked\r\n\r\ne\r\n"
                    b'{"title":"ok"}\r\n0\r\n\r\n'
                ) as target,
            ):
                enforcer = self.enforcer(registry, [robots, target], state)
                projector = Mock(
                    side_effect=(
                        (lambda document: json.loads(document.text))
                        if method == "fetch_text"
                        else (lambda value: value)
                    )
                )
                result = getattr(enforcer, method)(
                    SourceRequest(
                        "https://www.example.go.kr/page",
                        OPERATION,
                        registry.policies[0],
                    ),
                    projector,
                )
                self.assertEqual({"title": "ok"}, result.value)
                self.assertEqual(
                    (OPERATION, "allowed", 2),
                    (
                        result.source_receipt.operation_id,
                        result.source_receipt.outcome,
                        state.opens,
                    ),
                )
                projector.assert_called_once()
                self.assertTrue(robots.isclosed() and target.isclosed())

    def test_opener_errors_keep_policy_and_upstream_statuses(self) -> None:
        for robots in (True, False):
            for error_type in (URLError, TimeoutError):
                registry, state = self.registry(), FakeState()
                responses = (
                    []
                    if robots
                    else [
                        Response(b"User-agent: *\nAllow: /\n", media_type="text/plain")
                    ]
                )
                responses.append(error_type("synthetic-upstream-marker"))
                opener, projector = Mock(side_effect=responses), Mock()
                enforcer = HttpPolicyEnforcer(
                    registry, state, HttpTransport(opener, lambda _host: ["1.1.1.1"])
                )
                with (
                    self.subTest(robots=robots, error=error_type.__name__),
                    patch(
                        "kgov_runtime.http.SourceReceipt", wraps=SourceReceipt
                    ) as receipt,
                    self.assertRaises(ReadOnlyHttpError) as raised,
                ):
                    enforcer.fetch_text(
                        SourceRequest(
                            "https://www.example.go.kr/page",
                            OPERATION,
                            registry.policies[0],
                        ),
                        projector,
                    )
                expected = "robots-denied" if robots else "upstream-unavailable"
                self.assertEqual(
                    (expected, expected),
                    (raised.exception.status, str(raised.exception)),
                )
                self.assertEqual(1 if robots else 2, state.opens)
                self.assertEqual(state.opens, opener.call_count)
                projector.assert_not_called()
                receipt.assert_not_called()

    def test_robots_uses_longest_rule_with_allow_winning_equal_length(self) -> None:
        rules = b"User-agent: *\nDisallow: /private\nAllow: /private/public\nDisallow: /equal\nAllow: /equal\n"
        for path, allowed in (
            ("/private/public/page", True),
            ("/private/secret", False),
            ("/equal", True),
        ):
            registry = self.registry()
            responses = [Response(rules, media_type="text/plain")]
            if allowed:
                responses.append(Response(b"<title>ok</title>"))
            request = SourceRequest(
                f"https://www.example.go.kr{path}", OPERATION, registry.policies[0]
            )
            if allowed:
                self.assertEqual(
                    "ok",
                    self.enforcer(registry, responses)
                    .fetch_text(request, lambda item: item.text[7:-8])
                    .value,
                )
            else:
                with self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"):
                    self.enforcer(registry, responses).fetch_text(
                        request, lambda item: item.text
                    )

    def test_client_robots_group_overrides_opposite_wildcard_rules(self) -> None:
        wildcard = "User-agent: *\nDisallow: /client-allowed\nAllow: /client-denied\n"
        less_specific = (
            "User-agent: k-gov\nDisallow: /client-allowed\nAllow: /client-denied\n"
        )
        client_allow = "User-agent: k-gov-skills\nAllow: /client-allowed\n"
        client_deny = "User-agent: k-gov-skills\nDisallow: /client-denied\n"
        for groups in (
            (wildcard, less_specific, client_allow, client_deny),
            (client_deny, client_allow, less_specific, wildcard),
        ):
            rules = "".join(groups).encode()
            registry = self.registry()
            allowed_state, allowed_opens = FakeState(), []
            allowed = self.enforcer(
                registry,
                [Response(rules, media_type="text/plain"), Response(b"allowed")],
                allowed_state,
                allowed_opens,
            ).fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/client-allowed",
                    OPERATION,
                    registry.policies[0],
                ),
                lambda document: document.text,
            )
            self.assertEqual(("allowed", 2), (allowed.value, allowed_state.opens))

            denied_state, denied_opens = FakeState(), []
            with self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"):
                self.enforcer(
                    registry,
                    [Response(rules, media_type="text/plain")],
                    denied_state,
                    denied_opens,
                ).fetch_text(
                    SourceRequest(
                        "https://www.example.go.kr/client-denied",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda document: document.text,
                )
            self.assertEqual(1, denied_state.opens)
            self.assertEqual(["https://www.example.go.kr/robots.txt"], denied_opens)

    def test_robots_canonicalizes_encoded_paths_and_matches_query(self) -> None:
        cases = (
            (b"User-agent: *\nDisallow: /private\n", "/%70rivate"),
            (b"User-agent: *\nDisallow: /%70rivate\n", "/private"),
            (b"User-agent: *\nDisallow: /search?secret=\n", "/search?secret=1"),
            (b"User-agent: *\nDisallow: /private%zz\n", "/private"),
        )
        for rules, target in cases:
            registry, state, opened = self.registry(), FakeState(), []
            with (
                self.subTest(rules=rules, target=target),
                self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"),
            ):
                self.enforcer(
                    registry,
                    [Response(rules, media_type="text/plain")],
                    state,
                    opened,
                ).fetch_text(
                    SourceRequest(
                        f"https://www.example.go.kr{target}",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda document: document.text,
                )
            self.assertEqual(1, state.opens)
            self.assertEqual(["https://www.example.go.kr/robots.txt"], opened)

    def test_robots_preserves_encoded_reserved_octets_during_matching(self) -> None:
        cases = (
            ("/search?q=a%2Fb", "/search?q=a/b"),
            ("/search?q=a%3Fb", "/search?q=a?b"),
            ("/search?q=a%26b", "/search?q=a&b"),
            ("/search?q=a%3Db", "/search?q=a=b"),
        )
        for encoded, literal in cases:
            rules = (f"User-agent: *\nDisallow: {encoded}\nAllow: {literal}\n").encode()
            registry, state, opened = self.registry(), FakeState(), []
            with (
                self.subTest(encoded=encoded, literal=literal),
                self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"),
            ):
                self.enforcer(
                    registry,
                    [Response(rules, media_type="text/plain")],
                    state,
                    opened,
                ).fetch_text(
                    SourceRequest(
                        f"https://www.example.go.kr{encoded}",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda document: document.text,
                )
            self.assertEqual(1, state.opens)
            self.assertEqual(["https://www.example.go.kr/robots.txt"], opened)

    def test_invalid_recognized_robots_data_fails_before_target_open(self) -> None:
        invalid_documents = (
            b"User-agent: *\nDisallow: private\n",
            b"User-agent: *\nDisallow: /private\x00\n",
            b"User-agent: *\nDisallow\x00: /private\n",
            b"User-agent: *\nDisallow: /pri vate\n",
            b"User-agent: bad\x00token\nDisallow: /private\n",
            b"User-agent: bot1\nDisallow: /private\nUser-agent: *\nAllow: /\n",
        )
        for rules in invalid_documents:
            registry, state, opened = self.registry(), FakeState(), []
            with (
                self.subTest(rules=rules),
                self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"),
            ):
                self.enforcer(
                    registry,
                    [Response(rules, media_type="text/plain")],
                    state,
                    opened,
                ).fetch_text(
                    SourceRequest(
                        "https://www.example.go.kr/private",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda document: document.text,
                )
            self.assertEqual(1, state.opens)
            self.assertEqual(["https://www.example.go.kr/robots.txt"], opened)

    def test_robots_preserves_empty_query_delimiter(self) -> None:
        rules = b"User-agent: *\nDisallow: /page?$\nAllow: /page$\n"
        registry = self.registry()

        denied_state, denied_opens = FakeState(), []
        with self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"):
            self.enforcer(
                registry,
                [Response(rules, media_type="text/plain")],
                denied_state,
                denied_opens,
            ).fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/page?",
                    OPERATION,
                    registry.policies[0],
                ),
                lambda document: document.text,
            )
        self.assertEqual(1, denied_state.opens)
        self.assertEqual(["https://www.example.go.kr/robots.txt"], denied_opens)

        allowed_state, allowed_opens = FakeState(), []
        result = self.enforcer(
            registry,
            [Response(rules, media_type="text/plain"), Response(b"allowed")],
            allowed_state,
            allowed_opens,
        ).fetch_text(
            SourceRequest(
                "https://www.example.go.kr/page",
                OPERATION,
                registry.policies[0],
            ),
            lambda document: document.text,
        )
        self.assertEqual(("allowed", 2), (result.value, allowed_state.opens))

    def test_wildcard_matching_is_bounded_without_regex_backtracking(self) -> None:
        repetitions = 128
        pattern = "/" + "*a" * repetitions + "b$"
        target = "/" + "a" * repetitions + "c"
        rules = f"User-agent: *\nDisallow:\t{pattern} \nDisallow:   \n".encode()
        registry, state, opened = self.registry(), FakeState(), []
        result = self.enforcer(
            registry,
            [Response(rules, media_type="text/plain"), Response(b"allowed")],
            state,
            opened,
        ).fetch_text(
            SourceRequest(
                f"https://www.example.go.kr{target}",
                OPERATION,
                registry.policies[0],
            ),
            lambda document: document.text,
        )
        self.assertEqual(("allowed", 2), (result.value, state.opens))

    def test_target_429_is_persisted_without_retry_and_errors_do_not_reflect_input(
        self,
    ) -> None:
        registry, state = self.registry(robots="documented-api-exemption"), FakeState()
        enforcer = self.enforcer(
            registry,
            [Response(b"private-marker", status=429, headers={"Retry-After": "17"})],
            state,
        )
        with self.assertRaises(ReadOnlyHttpError) as raised:
            enforcer.fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/page", OPERATION, registry.policies[0]
                ),
                lambda item: item.text,
            )
        self.assertEqual(
            ("upstream-429-manual", ["17"], 1),
            (str(raised.exception), state.retry_after, state.opens),
        )
        self.assertNotIn("private-marker", str(raised.exception))

    def test_target_media_size_decode_and_output_scan_fail_closed(self) -> None:
        cases = (
            (
                self.registry(),
                Response(b"plain", media_type="text/plain"),
                lambda item: item.text,
            ),
            (self.registry(max_bytes=3), Response(b"four"), lambda item: item.text),
            (self.registry(), Response(b"\xff"), lambda item: item.text),
            (self.registry(), Response(b"ok"), lambda _item: {"text": "forbidden"}),
            (
                self.registry(),
                Response(b"ok"),
                lambda _item: {"contact": "user@example.org"},
            ),
        )
        for registry, response, projector in cases:
            enforcer = self.enforcer(
                registry,
                [
                    Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                    response,
                ],
            )
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                enforcer.fetch_text(
                    SourceRequest(
                        "https://www.example.go.kr/page",
                        OPERATION,
                        registry.policies[0],
                    ),
                    projector,
                )

    def test_shared_json_guard_error_contract(self) -> None:
        nested = []
        for _ in range(20):
            nested = [nested]
        text = "\u00e9" * 20_000
        valid = (
            (b'{"a":[null,true,1,1.5]}', {"a": [None, True, 1, 1.5]}),
            (b'[' * 21 + b']' * 21, nested),
            (json.dumps([0] * 19_999).encode(), [0] * 19_999),
            (json.dumps({"a": [0] * 19_997}).encode(), {"a": [0] * 19_997}),
            (json.dumps(text, ensure_ascii=False).encode(), text),
            (json.dumps({text: 0}, ensure_ascii=False).encode(), {text: 0}),
            (b'"\\ud83d\\ude00"', "\U0001f600"),
        )
        invalid = (
            ("depth", b'[' * 22 + b']' * 22),
            ("key-depth", b'[' * 20 + b'{"a":0}' + b']' * 20),
            ("list-nodes", json.dumps([0] * 20_000).encode()),
            ("mapping-nodes", json.dumps({"a": [0] * 19_998}).encode()),
            ("string", json.dumps(text + "x", ensure_ascii=False).encode()),
            ("key", json.dumps({text + "x": 0}, ensure_ascii=False).encode()),
            ("duplicate", b'{"a":1,"\\u0061":2}'),
            ("nan", b'NaN'),
            ("infinity", b'Infinity'),
            ("negative-infinity", b'-Infinity'),
            ("float-overflow", b'1e309'),
            ("high-surrogate", b'"\\ud800"'),
            ("low-surrogate", b'"\\udfff"'),
            ("surrogate-key", b'{"\\ud800":0}'),
            ("duplicate-before-walk", b'{"x":' + json.dumps(text + "x").encode() + b',"a":1,"\\u0061":2}'),
        )
        for turn in range(2):
            for index, (body, expected) in enumerate(valid):
                with self.subTest(turn=turn, valid=index):
                    self.assertEqual(expected, _strict_json(body))
            for label, body in invalid:
                with self.subTest(turn=turn, invalid=label):
                    with self.assertRaises(ValueError) as caught:
                        _strict_json(body)
                    error = caught.exception
                    self.assertIs(type(error), ValueError)
                    self.assertEqual("builtins", type(error).__module__)
                    self.assertEqual((), error.args)
                    self.assertIsNone(error.__cause__)
                    self.assertIsNone(error.__context__)
                    self.assertFalse(error.__suppress_context__)

    def test_shared_json_native_error_chain(self) -> None:
        for parser in (_strict_json, strict_json_loads):
            for body, start, end, reason in (
                (b'"\xff"', 1, 2, "invalid start byte"),
                (b'{"a":1,"a":2}\xff', 13, 14, "invalid start byte"),
                (b'"\xc3', 1, 2, "unexpected end of data"),
            ):
                with self.subTest(parser=parser.__name__, unicode_start=start, reason=reason):
                    with self.assertRaises(UnicodeDecodeError) as caught:
                        parser(body)
                    error = caught.exception
                    self.assertIs(type(error), UnicodeDecodeError)
                    self.assertEqual("builtins", type(error).__module__)
                    self.assertEqual(("utf-8", body, start, end, reason), error.args)
                    self.assertEqual(("utf-8", body, start, end, reason), (error.encoding, error.object, error.start, error.end, error.reason))
                    self.assertIsNone(error.__cause__)
                    self.assertIsNone(error.__context__)
                    self.assertFalse(error.__suppress_context__)
            for body, message, position, line, column, context_position in (
                (b'', "Expecting value", 0, 1, 1, 0),
                (b'\xef\xbb\xbf{}', "Unexpected UTF-8 BOM (decode using utf-8-sig)", 0, 1, 1, None),
                (b'{\n"a":}', "Expecting value", 6, 2, 5, 6),
            ):
                with self.subTest(parser=parser.__name__, json_position=position, message=message):
                    with self.assertRaises(json.JSONDecodeError) as caught:
                        parser(body)
                    error = caught.exception
                    self.assertIs(type(error), json.JSONDecodeError)
                    self.assertEqual("json.decoder", type(error).__module__)
                    self.assertEqual((f"{message}: line {line} column {column} (char {position})",), error.args)
                    self.assertEqual((message, body.decode("utf-8"), position, line, column), (error.msg, error.doc, error.pos, error.lineno, error.colno))
                    self.assertIsNone(error.__cause__)
                    self.assertEqual(context_position is not None, error.__suppress_context__)
                    if context_position is None:
                        self.assertIsNone(error.__context__)
                    else:
                        context = error.__context__
                        self.assertIs(type(context), StopIteration)
                        self.assertEqual("builtins", type(context).__module__)
                        self.assertEqual((context_position,), context.args)
                        self.assertIsNone(context.__cause__)
                        self.assertIsNone(context.__context__)
                        self.assertFalse(context.__suppress_context__)
        result = subprocess.run(
            [sys.executable, "-c", '''
import sys
from kgov_runtime.http import _strict_json
from kgov_runtime.json_adapter import strict_json_loads
sys.set_int_max_str_digits(640)
for parser in (_strict_json, strict_json_loads):
    assert parser(b"1" * 640) == int("1" * 640)
    try:
        parser(b"1" * 641)
    except ValueError as error:
        assert type(error) is ValueError
        assert type(error).__module__ == "builtins"
        assert error.args == ("Exceeds the limit (640 digits) for integer string conversion: value has 641 digits; use sys.set_int_max_str_digits() to increase the limit",)
        assert error.__cause__ is None
        assert error.__context__ is None
        assert not error.__suppress_context__
    else:
        raise AssertionError("oversized integer accepted")
print("native-integer-contract")
'''],
            cwd=korean_law_bill_research.ROOT,
            env={"PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual((0, "native-integer-contract\n", ""), (result.returncode, result.stdout, result.stderr))

    def test_json_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            registry = self.registry(
                robots="documented-api-exemption", media_type="application/json"
            )
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.enforcer(
                    registry, [Response(body, media_type="application/json")]
                ).fetch_json(
                    SourceRequest(
                        "https://www.example.go.kr/page",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda value: value,
                )

    def test_json_rejects_surrogates_and_bounded_string_or_key_overflow(self) -> None:
        bodies = (
            b'"\\ud800"',
            json.dumps("x" * 20_001).encode(),
            json.dumps({"x" * 20_001: 1}).encode(),
        )
        for body in bodies:
            registry = self.registry(
                robots="documented-api-exemption", media_type="application/json"
            )
            with (
                self.subTest(body_length=len(body)),
                self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"),
            ):
                self.enforcer(
                    registry, [Response(body, media_type="application/json")]
                ).fetch_json(
                    SourceRequest(
                        "https://www.example.go.kr/page",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda value: value,
                )

    def test_default_resolution_and_live_compatibility_never_fabricate_dns(
        self,
    ) -> None:
        opened: list[bool] = []
        with self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"):
            validate_public_https_url("https://anything.invalid/", {"anything.invalid"})
        with self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"):
            fetch_json(
                "https://anything.invalid/",
                allowed_hosts={"anything.invalid"},
                opener=lambda *_args, **_kwargs: opened.append(True),
            )
        self.assertEqual([], opened)

    def test_json_adapter_default_transport_is_blocked_without_dns(self) -> None:
        opened: list[bool] = []

        def opener(*_args, **_kwargs):
            opened.append(True)
            return Response(
                b'{"LawSearch":{"totalCnt":"0","law":[]}}',
                media_type="application/json",
            )

        with patch.dict(os.environ, {"LAW_OC": "fixture-key"}, clear=False):
            with (
                patch("kgov_runtime.http.socket.getaddrinfo") as dns,
                patch("kgov_runtime.http.build_opener") as network,
                self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"),
            ):
                query_json(korean_law_bill_research.OPERATION, params={"query": "synthetic"})
            dns.assert_not_called()
            network.assert_not_called()
            result = query_json(
                korean_law_bill_research.OPERATION,
                params={"query": "synthetic"},
                opener=opener,
            )
        self.assertEqual([True], opened)
        self.assertEqual(
            {
                "contract_id": "kgov/korean-law-bill-research/v1",
                "execution_mode": "official-live",
                "status": "records-retrieved",
                "count": 0,
                "records": [],
                "source_receipt": {
                    "operation_id": "kgov/korean-law-bill-research/search-laws/v1",
                    "policy_id": "law-go-kr-drf-api",
                    "endpoint": "https://www.law.go.kr/DRF/lawSearch.do",
                },
                "manual_review_required": True,
            },
            result,
        )

    def test_forbidden_output_keys_are_unicode_canonicalized_without_reflection(
        self,
    ) -> None:
        for key in ("ｒａｗ", "r\u200baw", " raw "):
            registry = self.registry(robots="documented-api-exemption")
            with self.subTest(key=key):
                with self.assertRaises(ReadOnlyHttpError) as raised:
                    self.enforcer(registry, [Response(b"ok")]).fetch_text(
                        SourceRequest(
                            "https://www.example.go.kr/page",
                            OPERATION,
                            registry.policies[0],
                        ),
                        lambda _document, output_key=key: {
                            output_key: "private-payload"
                        },
                    )
                self.assertEqual("response-invalid", str(raised.exception))
                self.assertNotIn("private-payload", str(raised.exception))

    def test_package_normalize_records_remains_callable_legacy_api(self) -> None:
        self.assertTrue(callable(kgov_runtime.normalize_records))
        self.assertEqual(
            {"count": 1, "records": [{"id": 1}], "raw": {"id": 1}},
            kgov_runtime.normalize_records({"id": 1}),
        )

    def test_invalid_scope_and_policy_states_block_before_dns_state_or_opener(
        self,
    ) -> None:
        invalid_urls = (
            ("https://other.example.go.kr/page", "policy-disabled"),
            ("https://child.www.example.go.kr/page", "policy-disabled"),
            ("https://www.example.go.kr:444/page", "invalid-request"),
            ("https://www.example.go.kr/page/../secret", "invalid-request"),
            ("https://www.example.go.kr/page%2Fsecret", "invalid-request"),
        )
        for url, expected in invalid_urls:
            registry, touched, state = self.registry(), [], FakeState()
            enforcer = HttpPolicyEnforcer(
                registry,
                state,
                HttpTransport(
                    lambda *_args, **_kwargs: touched.append("open"),
                    lambda _host: touched.append("dns") or ["1.1.1.1"],
                ),
            )
            with (
                self.subTest(url=url),
                self.assertRaisesRegex(ReadOnlyHttpError, f"^{expected}$"),
            ):
                enforcer.fetch_text(
                    SourceRequest(url, OPERATION, registry.policies[0]),
                    lambda document: document.text,
                )
            self.assertEqual(([], 0), (touched, state.opens))

        mutations = (
            (
                "review",
                lambda policy: policy["review"].update(expires_on="2026-09-05"),
                "policy-expired",
            ),
            (
                "terms",
                lambda policy: policy.update(
                    terms={
                        "status": "manual-review",
                        "url": "https://www.example.go.kr/terms",
                    }
                ),
                "terms-unverified",
            ),
            (
                "license",
                lambda policy: policy.update(
                    license={
                        "status": "manual-review",
                        "url": "https://www.example.go.kr/license",
                    }
                ),
                "license-unverified",
            ),
            (
                "budget",
                lambda policy: policy.update(rate_limit={"status": "unreviewed"}),
                "budget-exhausted",
            ),
        )
        for label, mutate, expected in mutations:
            catalog = reviewed_catalog()
            mutate(catalog["source_policies"][0])
            registry = SourcePolicyRegistry.from_catalog(
                catalog, on_date=date(2026, 9, 6)
            )
            touched, state = [], FakeState()
            enforcer = HttpPolicyEnforcer(
                registry,
                state,
                HttpTransport(
                    lambda *_a, **_k: touched.append("open"),
                    lambda _h: touched.append("dns") or ["1.1.1.1"],
                ),
            )
            with (
                self.subTest(label=label),
                self.assertRaisesRegex(ReadOnlyHttpError, f"^{expected}$"),
            ):
                enforcer.fetch_text(
                    SourceRequest(
                        "https://www.example.go.kr/page",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda document: document.text,
                )
            self.assertEqual(([], 0), (touched, state.opens))

    def test_robots_status_matrix_is_bounded_and_never_retries(self) -> None:
        allowed = (
            Response(b"", media_type="text/plain"),
            Response(b"missing", status=404),
            Response(b"gone", status=410),
        )
        for robots in allowed:
            registry, state = self.registry(), FakeState()
            result = self.enforcer(
                registry, [robots, Response(b"ok")], state
            ).fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/page", OPERATION, registry.policies[0]
                ),
                lambda document: document.text,
            )
            self.assertEqual(("ok", 2), (result.value, state.opens))
        denied = (
            Response(b"auth", status=401),
            Response(b"forbidden", status=403),
            Response(b"later", status=429, headers={"Retry-After": "17"}),
            Response(b"error", status=500),
            Response(b"malformed line", media_type="text/plain"),
            Response(b"#" + b"x" * 512_000, media_type="text/plain"),
        )
        for robots in denied:
            registry, state = self.registry(), FakeState()
            with (
                self.subTest(status=robots.status),
                self.assertRaisesRegex(ReadOnlyHttpError, "^robots-denied$"),
            ):
                self.enforcer(registry, [robots], state).fetch_text(
                    SourceRequest(
                        "https://www.example.go.kr/page",
                        OPERATION,
                        registry.policies[0],
                    ),
                    lambda document: document.text,
                )
            self.assertEqual(1, state.opens)
            if robots.status == 429:
                self.assertEqual(["17"], state.retry_after)

    def test_target_403_and_transport_failure_open_once_without_retry(self) -> None:
        registry = self.registry(robots="documented-api-exemption")
        state = FakeState()
        with self.assertRaisesRegex(ReadOnlyHttpError, "^upstream-403-manual$"):
            self.enforcer(
                registry, [Response(b"denied", status=403)], state
            ).fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/page", OPERATION, registry.policies[0]
                ),
                lambda document: document.text,
            )
        self.assertEqual(1, state.opens)

    def test_default_legacy_paths_fail_closed_but_two_injections_remain_compatible(
        self,
    ) -> None:
        with self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"):
            safe_urlopen(Request("https://www.example.go.kr/"))
        with self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"):
            fetch_text(
                "https://www.example.go.kr/",
                allowed_hosts={"www.example.go.kr"},
                opener=lambda *_a, **_k: Response(b"ok"),
            )
        with self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"):
            fetch_text(
                "https://www.example.go.kr/",
                allowed_hosts={"www.example.go.kr"},
                resolver=lambda _host: ["1.1.1.1"],
            )
        result = fetch_text(
            "https://www.example.go.kr/",
            allowed_hosts={"www.example.go.kr"},
            opener=lambda *_a, **_k: Response(b"ok"),
            resolver=lambda _host: ["1.1.1.1"],
        )
        self.assertEqual("ok", result["text"])

    def test_default_enforcer_connects_only_approved_address_with_original_tls_identity(
        self,
    ) -> None:
        approved = "2001:4860:4860::8888"
        handlers: list[Any] = []
        sockets: list[Any] = []
        connections: list[tuple[Any, ...]] = []
        tls_names: list[str] = []
        requests: list[tuple[str, str | None]] = []

        class FakeSocket:
            def settimeout(self, timeout):
                self.timeout = timeout

            def connect(self, address):
                connections.append(address)

        class FakeContext:
            check_hostname = True
            verify_mode = ssl.CERT_REQUIRED

            def wrap_socket(self, raw_socket, *, server_hostname):
                tls_names.append(server_hostname)
                return raw_socket

        class CapturingOpener:
            def open(self, request, timeout=0):
                requests.append((request.full_url, request.get_header("Host")))
                return Response(b"ok")

        def make_socket(family, socket_type):
            raw_socket = FakeSocket()
            sockets.append((family, socket_type, raw_socket))
            return raw_socket

        def build(*values):
            handlers.extend(values)
            pinned = next(
                handler
                for handler in values
                if handler.__class__.__name__ == "_PinnedHTTPSHandler"
            )
            connection = pinned.connection("www.example.go.kr", timeout=3.0)
            connection.connect()
            return CapturingOpener()

        registry = self.registry(robots="documented-api-exemption")
        with (
            patch("kgov_runtime.http._network_resolver", return_value=[approved]),
            patch("kgov_runtime.http.socket.getaddrinfo") as hostname_dns,
            patch("kgov_runtime.http.socket.socket", side_effect=make_socket),
            patch(
                "kgov_runtime.http.ssl.create_default_context",
                return_value=FakeContext(),
            ),
            patch("kgov_runtime.http.build_opener", side_effect=build),
        ):
            result = HttpPolicyEnforcer(registry, FakeState()).fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/page",
                    OPERATION,
                    registry.policies[0],
                ),
                lambda document: document.text,
            )
        hostname_dns.assert_not_called()
        self.assertEqual("ok", result.value)
        self.assertEqual([(approved, 443, 0, 0)], connections)
        self.assertEqual(["www.example.go.kr"], tls_names)
        self.assertEqual(
            [("https://www.example.go.kr/page", "www.example.go.kr")], requests
        )
        self.assertEqual(socket.AF_INET6, sockets[0][0])
        self.assertEqual(
            [{}], [item.proxies for item in handlers if isinstance(item, ProxyHandler)]
        )
        self.assertEqual(
            1,
            sum(
                item.__class__.__name__ == "RejectRedirectHandler" for item in handlers
            ),
        )

    def test_redirect_error_closes_response_without_following_or_reflecting(
        self,
    ) -> None:
        class RedirectResponse:
            def __init__(self) -> None:
                self.reads = 0
                self.closes = 0

            def read(self) -> bytes:
                self.reads += 1
                return b"redirect-body"

            def close(self) -> None:
                self.closes += 1

        class FollowupOpener:
            def __init__(self) -> None:
                self.requests: list[str] = []

            def open(self, request, timeout=0):
                self.requests.append(request.full_url)
                return Response(b"unexpected")

        marker = "private-redirect-marker"
        response = RedirectResponse()
        followup = FollowupOpener()
        handler = RejectRedirectHandler()
        handler.add_parent(followup)
        with self.assertRaises(UnsafeEndpointError) as raised:
            handler.http_error_302(
                Request("https://www.example.go.kr/page"),
                response,
                302,
                "Found",
                {"location": f"https://redirect.invalid/{marker}"},
            )
        self.assertEqual("redirects are forbidden", str(raised.exception))
        self.assertNotIn(marker, str(raised.exception))
        self.assertEqual((0, 1), (response.reads, response.closes))
        self.assertEqual([], followup.requests)

    def test_policy_transport_disables_environment_proxies_and_rejects_redirects(
        self,
    ) -> None:
        handlers: list[Any] = []
        opened: list[tuple[str, float]] = []
        sentinel = object()

        class CapturingOpener:
            def open(self, request, timeout=0):
                opened.append((request.full_url, timeout))
                return sentinel

        def build(*values):
            handlers.extend(values)
            return CapturingOpener()

        proxy_environment = {
            "HTTP_PROXY": "http://proxy.invalid:8080",
            "HTTPS_PROXY": "http://proxy.invalid:8443",
            "ALL_PROXY": "socks5://proxy.invalid:1080",
            "NO_PROXY": "www.example.go.kr",
            "no_proxy": "example.go.kr",
        }
        with (
            patch.dict(os.environ, proxy_environment, clear=False),
            patch("kgov_runtime.http.build_opener", side_effect=build),
        ):
            result = _policy_urlopen(
                Request("https://www.example.go.kr/page"),
                timeout=3.0,
                approved_address="1.1.1.1",
            )
        proxies = [handler for handler in handlers if isinstance(handler, ProxyHandler)]
        redirects = [
            handler
            for handler in handlers
            if handler.__class__.__name__ == "RejectRedirectHandler"
        ]
        self.assertIs(sentinel, result)
        self.assertEqual([{}], [handler.proxies for handler in proxies])
        self.assertEqual(1, len(redirects))
        self.assertEqual([("https://www.example.go.kr/page", 3.0)], opened)

    def test_build_url_and_transport_failure_remain_non_reflecting(self) -> None:
        self.assertEqual(
            "https://example.go.kr/?a=1", build_url("https://example.go.kr/", {"a": 1})
        )
        registry = self.registry(robots="documented-api-exemption")
        transport = HttpTransport(
            lambda *_a, **_k: (_ for _ in ()).throw(URLError("secret")),
            lambda _host: ["1.1.1.1"],
            10.0,
        )
        state = FakeState()
        with self.assertRaisesRegex(ReadOnlyHttpError, "^upstream-unavailable$"):
            HttpPolicyEnforcer(registry, state, transport).fetch_text(
                SourceRequest(
                    "https://www.example.go.kr/page", OPERATION, registry.policies[0]
                ),
                lambda item: item.text,
            )
        self.assertEqual(1, state.opens)


if __name__ == "__main__":
    unittest.main()
