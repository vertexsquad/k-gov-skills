"""Policy-enforced read-only HTTP contract tests.

# noqa: SIZE_OK -- Issue #30 owns one HTTP contract test path and requires the
# complete authorization, robots, rate, transport, and output boundary matrix.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import unittest
from dataclasses import replace
from datetime import date
from typing import Any, TypedDict
from urllib.error import URLError
from urllib.request import ProxyHandler, Request

from unittest.mock import patch

import kgov_runtime
from kgov_runtime.json_adapter import JsonAdapterConfig, query_json
from kgov_runtime.http import (
    HttpPolicyEnforcer,
    HttpTransport,
    ReadOnlyHttpError,
    RejectRedirectHandler,
    SourceRequest,
    UnsafeEndpointError,
    _policy_urlopen,
    build_url,
    fetch_json,
    fetch_text,
    safe_urlopen,
    validate_public_https_url,
)
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


class ReadOnlyHttpTest(unittest.TestCase):
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
        config = JsonAdapterConfig(
            slug="korean-legal-citation-law-search",
            default_endpoint="https://www.law.go.kr/DRF/lawSearch.do",
            allowed_hosts=frozenset({"law.go.kr"}),
            credential_env="LAW_OC",
            credential_param="OC",
            default_params={"target": "eflaw", "type": "JSON"},
        )

        def opener(*_args, **_kwargs):
            opened.append(True)
            return Response(b"[]", media_type="application/json")

        with patch.dict(os.environ, {"LAW_OC": "fixture-key"}, clear=False):
            with (
                patch("kgov_runtime.http.socket.getaddrinfo") as dns,
                patch("kgov_runtime.http.build_opener") as network,
                self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"),
            ):
                query_json(config, params={"query": "synthetic"})
            dns.assert_not_called()
            network.assert_not_called()
            result = query_json(
                config,
                params={"query": "synthetic"},
                opener=opener,
            )
        self.assertEqual([True], opened)
        self.assertEqual({"count": 0, "records": []}, result)

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
