"""Patent local admission and enforced lookup contracts.

# noqa: SIZE_OK -- Issue #31 owns exactly one patent test file; local admission,
# attachment rights and the enforced transport matrix must remain in this path.
"""

from __future__ import annotations

import json
import hashlib
import unittest
import subprocess
import sys
from pathlib import Path
import tempfile
import io
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import date
from unittest.mock import patch

from kgov_runtime.http import HttpPolicyEnforcer, HttpTransport, ReadOnlyHttpError
from kgov_runtime.policy_state import PolicyState
from kgov_runtime.source_policy import canonical_policy_digest
from tests.capabilities.test_korean_legal_citation_verification import reviewed_registry
from tests.test_read_only_http import assert_live_state_initialization, Response

from kgov_runtime.capabilities import patent_prior_art_evidence_pack as adapter
from tests.capabilities import review_admission_contract
from tests.capabilities.review_admission_contract import ReviewAdmissionContractMixin

REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = (
    REPO_ROOT / "kgov_runtime" / "capabilities" / "patent_prior_art_evidence_pack.py"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "capabilities"
    / "patent-prior-art-evidence-pack.json"
)


class _Response:
    headers = {"Content-Type": "text/html; charset=utf-8"}
    status = 200
    body = "<html><head><title>KIPRIS 특허정보</title></head><body>공개문헌</body></html>".encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class ReviewAdmissionReceiptTest(review_admission_contract.ReviewAdmissionReceiptTest):
    pass


class AdapterTest(ReviewAdmissionContractMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = adapter
        cls.adapter_path = ADAPTER_PATH
        cls.valid = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_live_state_initialization_order_and_error_boundary(self) -> None:
        assert_live_state_initialization(
            self, adapter, "kipo-web",
            "https://www.kipo.go.kr/%70age", ('canonicalize', 'registry', 'authorize', 'select'),
        )

    def test_current_kipo_attribution_requires_a_fresh_receipt(self) -> None:
        catalog = json.loads(adapter.CATALOG.read_text(encoding="utf-8"))
        policy = next(item for item in catalog["source_policies"] if item["id"] == "kipo-web")
        current = dict(policy, institution="지식재산처", revision=2)
        payload = deepcopy(self.valid)
        source = next(item for item in payload["source_refs"] if item["policy_receipt"]["policy_id"] == "kipo-web")
        source["institution"] = current["institution"]
        source["policy_receipt"].update(
            policy_revision=current["revision"],
            policy_digest=canonical_policy_digest(current),
        )

        result = adapter.review_case(payload)
        self.assertTrue(result["accepted"])
        self.assertEqual("policy-matched-not-cryptographic-authenticity-proof", result["receipt_assurance"])
        self.assertEqual(self.valid, payload)
        self.assertEqual({"www.kipris.or.kr", "www.kipo.go.kr"}, adapter.CONTRACT.allowed_hosts)

        legacy = dict(current, institution="특허청", revision=1)
        for stale_fields in (
            {"policy_revision": legacy["revision"]},
            {"policy_digest": canonical_policy_digest(legacy)},
            {"policy_revision": legacy["revision"], "policy_digest": canonical_policy_digest(legacy)},
        ):
            with self.subTest(stale_fields=stale_fields):
                stale = deepcopy(payload)
                stale_source = next(item for item in stale["source_refs"] if item["policy_receipt"]["policy_id"] == "kipo-web")
                stale_source["policy_receipt"].update(stale_fields)
                with self.assertRaises(ValueError):
                    adapter.review_case(stale)

    def test_lookup_receipt_uses_exact_operation_when_each_host_is_reviewed(
        self,
    ) -> None:
        # Given a real registry, isolated durable state and an offline wire transport.
        for host, policy_id in (
            ("www.kipris.or.kr", "kipris-web"),
            ("www.kipo.go.kr", "kipo-web"),
        ):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as directory:
                registry = reviewed_registry(policy_id)
                policy = next(
                    item for item in registry.policies if item.id == policy_id
                )
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                responses = iter(
                    [
                        Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                        _Response(),
                    ]
                )
                enforcer = HttpPolicyEnforcer(
                    registry,
                    state,
                    HttpTransport(
                        lambda *_a, **_k: next(responses), lambda _host: ["1.1.1.1"]
                    ),
                )
                # When an official page is inspected.
                result = adapter.inspect_patent_source(
                    f"https://{host}/page?q=discarded", policy, enforcer
                )
                # Then metadata has an authentic fetch receipt, never an admission receipt.
                self.assertEqual(
                    "kgov/patent-prior-art-evidence-pack/inspect-source/v1",
                    result["source_receipt"]["operation_id"],
                )
                self.assertEqual(
                    policy.digest, result["source_receipt"]["policy_digest"]
                )
                self.assertNotIn("policy_receipt", result)
                self.assertNotIn("discarded", json.dumps(result))

    def test_preserves_safe_kipris_read_only_lookup(self) -> None:
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            if request.full_url.endswith("/robots.txt"):
                return Response(b"User-agent: *\nAllow: /\n", media_type="text/plain")
            return _Response()

        registry = reviewed_registry("kipris-web")
        policy = next(item for item in registry.policies if item.id == "kipris-web")
        with tempfile.TemporaryDirectory() as directory:
            state = PolicyState(
                Path(directory) / "state.sqlite3",
                clock=lambda: 1000.0,
                sleeper=self.fail,
            )
            enforcer = HttpPolicyEnforcer(
                registry, state, HttpTransport(opener, lambda _: ["1.1.1.1"])
            )
            result = adapter.inspect_patent_source(
                "https://www.kipris.or.kr/khome/main.do?doc=A", policy, enforcer
            )
        self.assertEqual("KIPRIS 특허정보", result["title"])
        self.assertEqual(hashlib.sha256(_Response.body).hexdigest(), result["sha256"])
        self.assertEqual("https://www.kipris.or.kr/khome/main.do", result["url"])
        self.assertNotIn("doc=A", result["url"])
        self.assertEqual(
            {
                "url",
                "status",
                "content_type",
                "title",
                "content_length",
                "sha256",
                "source_receipt",
                "execution_mode",
                "manual_review_required",
            },
            set(result),
        )
        self.assertEqual(2, len(opened))
        self.assertEqual("https://www.kipris.or.kr/khome/main.do?doc=A", opened[1])

    def test_lookup_rejects_nonofficial_and_credential_bearing_urls(self) -> None:
        for url in (
            "https://example.org/",
            "https://evil.kipris.or.kr/",
            "https://evil.kipo.go.kr/",
            "https://www.kipris.or.kr/?api_key=SYNTHETIC_TOKEN",
            "https://www.kipris.or.kr/?client_secret=SYNTHETIC_TOKEN",
            "https://www.kipris.or.kr/?password=SYNTHETIC_TOKEN",
            "https://user:secret@www.kipris.or.kr/",
            "https://www.kipris.or.kr/#internal",
            "https://www.kipris.or.kr/search?q=user@example.org",
        ):
            with self.subTest(url=url):
                with self.assertRaises((ValueError, RuntimeError)):
                    adapter._live(url)

    def test_encoded_unsafe_paths_fail_before_policy_state_or_network(self) -> None:
        # Given encoded PII, nested encodings, malformed UTF-8/percent and controls.
        for path in (
            "/user%40example.org",
            "/user%2540example.org",
            "/user%252540example.org",
            "/%ff",
            "/%C0%AF",
            "/bad%",
            "/bad%2G",
            "/%1b",
            "/%E2%80%AE",
            "/%E2%80%A8",
            "/%E2%80%A9",
        ):
            with (
                self.subTest(path=path),
                patch.object(
                    adapter.SourcePolicyRegistry,
                    "from_catalog",
                    side_effect=AssertionError("policy"),
                ),
                patch(
                    "kgov_runtime.http.PolicyState", side_effect=AssertionError("state")
                ),
                patch("socket.getaddrinfo", side_effect=AssertionError("DNS")),
            ):
                # When a lookup URL crosses the public live boundary.
                with self.assertRaises(ValueError) as raised:
                    adapter._live("https://www.kipris.or.kr" + path)
                # Then even failure messages contain no path or decoded identifier.
                self.assertNotIn(path, str(raised.exception))
                self.assertNotIn("user@example.org", str(raised.exception))

    def test_safe_encoded_paths_are_canonicalized_before_lookup(self) -> None:
        # Given a safe percent-encoded unreserved path character.
        # When the URL boundary parses it.
        result = adapter._validated_lookup_url("https://www.kipo.go.kr/%70age?q=public")
        # Then policy and transport receive one canonical path spelling.
        self.assertEqual("https://www.kipo.go.kr/page?q=public", result)

    def test_lookup_rejects_direct_identifier_without_echo(self) -> None:
        marker = "user@example.org"
        with self.assertRaises(ValueError) as raised:
            adapter._live(f"https://www.kipris.or.kr/search?q={marker}")
        self.assertNotIn(marker, str(raised.exception))

        result = subprocess.run(
            [
                sys.executable,
                str(ADAPTER_PATH),
                "--lookup-url",
                f"https://www.kipris.or.kr/search?q={marker}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertNotIn(marker, result.stdout)
        self.assertNotIn(marker, result.stderr)

    def test_lookup_cli_does_not_echo_credential_value(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ADAPTER_PATH),
                "--lookup-url",
                "https://www.kipris.or.kr/?api_key=SYNTHETIC_TOKEN",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertNotIn("SYNTHETIC_TOKEN", result.stderr)

    def test_admission_is_network_and_state_free(self) -> None:
        # Given local source declarations and forbidden infrastructure seams.
        with (
            patch.object(adapter, "_live", side_effect=AssertionError("network")),
            patch("kgov_runtime.http.PolicyState", side_effect=AssertionError("state")),
            patch("socket.getaddrinfo", side_effect=AssertionError("DNS")),
        ):
            # When the local review is evaluated.
            result = adapter.review_case(self.valid)
        # Then it remains a human-review draft, not live retrieval evidence.
        self.assertTrue(result["accepted"])
        self.assertTrue(result["manual_review_required"])

    def test_noncanonical_host_is_rejected_as_input(self) -> None:
        # Given a hostname that the legacy boundary normalized inconsistently.
        registry = reviewed_registry("kipris-web")
        policy = next(item for item in registry.policies if item.id == "kipris-web")
        with tempfile.TemporaryDirectory() as directory:
            state = PolicyState(
                Path(directory) / "state.sqlite3",
                clock=lambda: 1000.0,
                sleeper=self.fail,
            )
            enforcer = HttpPolicyEnforcer(
                registry, state, HttpTransport(self.fail, self.fail)
            )
            # When trailing-dot authority enters the lookup API.
            with self.assertRaises(ValueError):
                adapter.inspect_patent_source(
                    "https://www.kipris.or.kr./", policy, enforcer
                )
            # Then no policy lookup, state reservation or DNS was attempted.

    def test_attachment_media_never_inherit_page_permission(self) -> None:
        # Given a policy broadly permitting media, not an attachment license.
        for media in (
            "application/pdf",
            "image/png",
            "image/svg+xml",
            "application/octet-stream",
            "application/dxf",
            "text/plain",
        ):
            with self.subTest(media=media), tempfile.TemporaryDirectory() as directory:
                registry = reviewed_registry("kipris-web")
                original = next(
                    item for item in registry.policies if item.id == "kipris-web"
                )
                policy = replace(
                    original, response=replace(original.response, media_types=(media,))
                )
                registry = replace(
                    registry,
                    policies=tuple(
                        policy if item.id == policy.id else item
                        for item in registry.policies
                    ),
                )
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                responses = iter(
                    [
                        Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                        Response(b"attachment contents", media_type=media),
                    ]
                )
                enforcer = HttpPolicyEnforcer(
                    registry,
                    state,
                    HttpTransport(
                        lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                    ),
                )
                # When the page endpoint responds with attachment/drawing media.
                with self.assertRaises(ReadOnlyHttpError) as raised:
                    adapter.inspect_patent_source(
                        "https://www.kipris.or.kr/attachment", policy, enforcer
                    )
                # Then even otherwise allowed media cannot produce a lookup receipt.
                self.assertEqual("response-invalid", raised.exception.status)

    def test_encoded_identifier_titles_fail_for_both_hosts_at_library_boundary(
        self,
    ) -> None:
        # Given encoded email, phone and resident identifiers in public page titles.
        for host, policy_id in (
            ("www.kipris.or.kr", "kipris-web"),
            ("www.kipo.go.kr", "kipo-web"),
        ):
            for encoded in (
                "person%40example.org",
                "010%2d1234%2D5678",
                "900101%2D1234567",
            ):
                with (
                    self.subTest(host=host, encoded=encoded),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    registry = reviewed_registry(policy_id)
                    policy = next(
                        item for item in registry.policies if item.id == policy_id
                    )
                    state = PolicyState(
                        Path(directory) / "state.sqlite3",
                        clock=lambda: 1000.0,
                        sleeper=self.fail,
                    )
                    responses = iter(
                        [
                            Response(
                                b"User-agent: *\nAllow: /\n", media_type="text/plain"
                            ),
                            Response(f"<title>{encoded}</title>".encode()),
                        ]
                    )
                    enforcer = HttpPolicyEnforcer(
                        registry,
                        state,
                        HttpTransport(
                            lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                        ),
                    )
                    # When the real enforcer projects the fetched title.
                    with self.assertRaises(ReadOnlyHttpError) as raised:
                        adapter.inspect_patent_source(
                            f"https://{host}/page", policy, enforcer
                        )
                    # Then no lookup result or allowed receipt is returned.
                    self.assertEqual("response-invalid", raised.exception.status)
                    self.assertEqual("response-invalid", str(raised.exception))

    def test_encoded_identifier_titles_fail_for_both_hosts_through_real_cli(
        self,
    ) -> None:
        # Given the real parser/runtime flow with only infrastructure injected.
        for host, policy_id in (
            ("www.kipris.or.kr", "kipris-web"),
            ("www.kipo.go.kr", "kipo-web"),
        ):
            for encoded, decoded in (
                ("person%40example.org", "person@example.org"),
                ("010%2D1234%2D5678", "010-1234-5678"),
                ("900101%2d1234567", "900101-1234567"),
            ):
                with (
                    self.subTest(host=host, encoded=encoded),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    registry = reviewed_registry(policy_id)
                    state = PolicyState(
                        Path(directory) / "state.sqlite3",
                        clock=lambda: 1000.0,
                        sleeper=self.fail,
                    )
                    responses = iter(
                        [
                            Response(
                                b"User-agent: *\nAllow: /\n", media_type="text/plain"
                            ),
                            Response(f"<title>{encoded}</title>".encode()),
                        ]
                    )
                    enforcer = HttpPolicyEnforcer(
                        registry,
                        state,
                        HttpTransport(
                            lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                        ),
                    )
                    with (
                        patch.object(
                            sys,
                            "argv",
                            [str(ADAPTER_PATH), "--lookup-url", f"https://{host}/page"],
                        ),
                        patch.object(
                            adapter.SourcePolicyRegistry,
                            "from_catalog",
                            return_value=registry,
                        ),
                        patch.object(
                            adapter,
                            "_state_path",
                            return_value=Path(directory) / "state.sqlite3",
                        ),
                        patch("kgov_runtime.http.PolicyState", return_value=state) as constructor,
                        patch.object(
                            adapter, "HttpPolicyEnforcer", return_value=enforcer
                        ),
                        redirect_stdout(io.StringIO()) as output,
                        redirect_stderr(io.StringIO()) as error,
                    ):
                        # When the public CLI tries to emit the page metadata.
                        code = adapter.main()
                        constructor.assert_called_once()
                    # Then neither encoded nor decoded identifiers or receipts can escape.
                    self.assertEqual(4, code)
                    self.assertEqual("", output.getvalue())
                    self.assertEqual(
                        {"error": "response-invalid"}, json.loads(error.getvalue())
                    )
                    self.assertNotIn(encoded, error.getvalue())
                    self.assertNotIn(decoded, error.getvalue())

    def test_composed_identifier_views_fail_for_both_hosts_and_cli(self) -> None:
        # Given percent-to-entity and fullwidth-ampersand identifiers in page titles.
        values = (
            "person%26%2364%3Bexample.org",
            "010%26%2345%3B1234%26%2345%3B5678",
            "900101%26%2345%3B1234567",
            "person＆#64;example.org",
        )
        for host, policy_id in (
            ("www.kipris.or.kr", "kipris-web"),
            ("www.kipo.go.kr", "kipo-web"),
        ):
            for value in values:
                with (
                    self.subTest(host=host, value=value),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    registry = reviewed_registry(policy_id)
                    policy = next(
                        item for item in registry.policies if item.id == policy_id
                    )
                    state = PolicyState(
                        Path(directory) / "state.sqlite3",
                        clock=lambda: 1000.0,
                        sleeper=self.fail,
                    )
                    responses = iter(
                        [
                            Response(
                                b"User-agent: *\nAllow: /\n", media_type="text/plain"
                            ),
                            Response(f"<title>{value}</title>".encode()),
                        ]
                    )
                    enforcer = HttpPolicyEnforcer(
                        registry,
                        state,
                        HttpTransport(
                            lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                        ),
                    )
                    # When the library projects the composed semantic view.
                    with self.assertRaises(ReadOnlyHttpError) as raised:
                        adapter.inspect_patent_source(
                            f"https://{host}/page", policy, enforcer
                        )
                    self.assertEqual("response-invalid", raised.exception.status)
                    responses = iter(
                        [
                            Response(
                                b"User-agent: *\nAllow: /\n", media_type="text/plain"
                            ),
                            Response(f"<title>{value}</title>".encode()),
                        ]
                    )
                    cli_enforcer = HttpPolicyEnforcer(
                        registry,
                        state,
                        HttpTransport(
                            lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                        ),
                    )
                    with (
                        patch.object(
                            sys,
                            "argv",
                            [str(ADAPTER_PATH), "--lookup-url", f"https://{host}/page"],
                        ),
                        patch.object(
                            adapter.SourcePolicyRegistry,
                            "from_catalog",
                            return_value=registry,
                        ),
                        patch.object(
                            adapter,
                            "_state_path",
                            return_value=Path(directory) / "state.sqlite3",
                        ),
                        patch("kgov_runtime.http.PolicyState", return_value=state) as constructor,
                        patch.object(
                            adapter, "HttpPolicyEnforcer", return_value=cli_enforcer
                        ),
                        redirect_stdout(io.StringIO()) as output,
                        redirect_stderr(io.StringIO()) as error,
                    ):
                        # When the same title reaches the real CLI.
                        code = adapter.main()
                        constructor.assert_called_once()
                    # Then no metadata or authentic allowed receipt is emitted.
                    self.assertEqual(4, code)
                    self.assertEqual("", output.getvalue())
                    self.assertEqual(
                        {"error": "response-invalid"}, json.loads(error.getvalue())
                    )

    def test_nested_title_identifier_encoding_remains_one_layer_only(self) -> None:
        # Given a nested title escape, distinct from a one-layer encoded email.
        for host, policy_id in (
            ("www.kipris.or.kr", "kipris-web"),
            ("www.kipo.go.kr", "kipo-web"),
        ):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as directory:
                registry = reviewed_registry(policy_id)
                policy = next(
                    item for item in registry.policies if item.id == policy_id
                )
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                responses = iter(
                    [
                        Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                        Response(b"<title>person%2540example.org</title>"),
                    ]
                )
                enforcer = HttpPolicyEnforcer(
                    registry,
                    state,
                    HttpTransport(
                        lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                    ),
                )
                # When the same projector applies exactly one comparison decode.
                result = adapter.inspect_patent_source(
                    f"https://{host}/page", policy, enforcer
                )
                # Then source spelling and authentic receipt identity are preserved.
                self.assertEqual("person%2540example.org", result["title"])
                self.assertEqual(
                    policy.digest, result["source_receipt"]["policy_digest"]
                )
                self.assertEqual("allowed", result["source_receipt"]["outcome"])

    def test_title_identifier_decoding_is_strict_and_utf8_byte_bounded(self) -> None:
        # Given invalid encoded UTF-8 or a title exceeding 250,000 UTF-8 bytes.
        for title in ("INVALID%FF", "INVALID%C0%AF", "가" * 83334):
            with (
                self.subTest(size=len(title)),
                tempfile.TemporaryDirectory() as directory,
            ):
                registry = reviewed_registry("kipris-web")
                policy = next(
                    item for item in registry.policies if item.id == "kipris-web"
                )
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                responses = iter(
                    [
                        Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                        Response(f"<title>{title}</title>".encode()),
                    ]
                )
                enforcer = HttpPolicyEnforcer(
                    registry,
                    state,
                    HttpTransport(
                        lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                    ),
                )
                # When title decoding crosses the real projection boundary.
                with self.assertRaises(ReadOnlyHttpError) as raised:
                    adapter.inspect_patent_source(
                        "https://www.kipris.or.kr/page", policy, enforcer
                    )
                # Then malformed or oversized comparison views receive no receipt.
                self.assertEqual("response-invalid", raised.exception.status)

    def test_control_bearing_titles_are_rejected_before_receipt(self) -> None:
        # Given reviewed HTML pages carrying raw or entity-encoded unsafe title controls.
        for marker in ("\u202e", "\x1b", "\u2028", "\u2029", "\u200b", "&#x202E;"):
            with (
                self.subTest(marker=repr(marker)),
                tempfile.TemporaryDirectory() as directory,
            ):
                registry = reviewed_registry("kipris-web")
                policy = next(
                    item for item in registry.policies if item.id == "kipris-web"
                )
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                responses = iter(
                    [
                        Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                        Response(
                            f"<title>Synthetic{marker}title</title>".encode("utf-8")
                        ),
                    ]
                )
                enforcer = HttpPolicyEnforcer(
                    registry,
                    state,
                    HttpTransport(
                        lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]
                    ),
                )
                # When metadata is projected inside the real enforcer.
                with self.assertRaises(ReadOnlyHttpError) as raised:
                    adapter.inspect_patent_source(
                        "https://www.kipris.or.kr/page", policy, enforcer
                    )
                # Then no allowed receipt or reflecting error can escape.
                self.assertEqual("response-invalid", raised.exception.status)
                self.assertEqual("response-invalid", str(raised.exception))

    def test_wrong_or_cloned_policy_never_reaches_dns(self) -> None:
        # Given a reviewed KIPRIS registry and a policy not owned by that operation/host.
        registry = reviewed_registry("kipris-web")
        original = next(item for item in registry.policies if item.id == "kipris-web")
        wrong = next(item for item in registry.policies if item.id == "kipo-web")
        for policy in (wrong, replace(original)):
            with (
                self.subTest(policy=policy.id),
                tempfile.TemporaryDirectory() as directory,
            ):
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                enforcer = HttpPolicyEnforcer(
                    registry, state, HttpTransport(self.fail, self.fail)
                )
                # When the caller supplies a wrong policy or an equal clone.
                with self.assertRaises(ReadOnlyHttpError) as raised:
                    adapter.inspect_patent_source(
                        "https://www.kipris.or.kr/page", policy, enforcer
                    )
                # Then receipt identity remains registry-owned.
                self.assertEqual("policy-disabled", raised.exception.status)

    def test_parent_admission_receipt_cannot_cover_child_attachment(self) -> None:
        # Given a local parent-page receipt with an unchanged source_url.
        payload = deepcopy(self.valid)
        payload["source_refs"][0]["url"] += "attachment.pdf"
        # When it is reused as proof for a distinct child URL.
        with self.assertRaises(ValueError):
            adapter.review_case(payload)
        # Then the admission boundary rejects it rather than inheriting page rights.

    def test_lookup_receipt_is_not_an_admission_receipt(self) -> None:
        # Given a genuine offline-enforced page lookup receipt.
        registry = reviewed_registry("kipris-web")
        policy = next(item for item in registry.policies if item.id == "kipris-web")
        with tempfile.TemporaryDirectory() as directory:
            state = PolicyState(
                Path(directory) / "state.sqlite3",
                clock=lambda: 1000.0,
                sleeper=self.fail,
            )
            responses = iter(
                [
                    Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                    _Response(),
                ]
            )
            enforcer = HttpPolicyEnforcer(
                registry,
                state,
                HttpTransport(lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]),
            )
            lookup = adapter.inspect_patent_source(
                "https://www.kipris.or.kr/", policy, enforcer
            )
        payload = deepcopy(self.valid)
        payload["source_refs"][0]["policy_receipt"] = lookup["source_receipt"]
        # When that different schema is submitted as local admission evidence.
        with self.assertRaises(ValueError):
            adapter.review_case(payload)
        # Then no implicit promotion can claim rights or authenticated admission.

    def test_policy_matrix_blocks_before_dns_or_reservation(self) -> None:
        # Given registry-owned policies failing each independent authorization gate.
        registry = reviewed_registry("kipris-web")
        original = next(item for item in registry.policies if item.id == "kipris-web")
        cases = [
            (replace(original, enabled=False), "policy-disabled"),
            (
                replace(
                    original,
                    review=replace(original.review, expires_on=date(2026, 9, 5)),
                ),
                "policy-expired",
            ),
            (
                replace(original, terms=replace(original.terms, status="prohibited")),
                "terms-unverified",
            ),
            (
                replace(
                    original, license=replace(original.license, status="manual-review")
                ),
                "license-unverified",
            ),
            (
                replace(original, robots=replace(original.robots, status="unreviewed")),
                "robots-denied",
            ),
            (
                replace(
                    original,
                    rate_limit=replace(original.rate_limit, status="unreviewed"),
                ),
                "budget-exhausted",
            ),
        ]
        for policy, expected in cases:
            with (
                self.subTest(expected=expected),
                tempfile.TemporaryDirectory() as directory,
            ):
                selected_registry = replace(
                    registry,
                    policies=tuple(
                        policy if item.id == policy.id else item
                        for item in registry.policies
                    ),
                )
                state = PolicyState(
                    Path(directory) / "state.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                enforcer = HttpPolicyEnforcer(
                    selected_registry, state, HttpTransport(self.fail, self.fail)
                )
                # When a denied policy reaches the real enforcer.
                with (
                    patch.object(state, "open", side_effect=AssertionError("state")),
                    self.assertRaises(ReadOnlyHttpError) as raised,
                ):
                    adapter.inspect_patent_source(
                        "https://www.kipris.or.kr/page", policy, enforcer
                    )
                # Then the stable policy decision wins before state/DNS/open.
                self.assertEqual(expected, raised.exception.status)

    def test_disabled_cli_hosts_are_state_and_network_free(self) -> None:
        # Given the current disabled catalog and the real CLI parser.
        for host in ("www.kipris.or.kr", "www.kipo.go.kr"):
            with (
                self.subTest(host=host),
                patch.object(
                    sys, "argv", [str(ADAPTER_PATH), "--lookup-url", f"https://{host}/"]
                ),
                patch(
                    "kgov_runtime.http.PolicyState", side_effect=AssertionError("state")
                ),
                patch("socket.getaddrinfo", side_effect=AssertionError("DNS")),
                redirect_stderr(io.StringIO()) as error,
            ):
                # When a valid lookup is requested.
                exit_code = adapter.main()
            # Then authorization denies before creating persistent state or opening sockets.
            self.assertEqual(3, exit_code)
            self.assertEqual("policy-disabled", json.loads(error.getvalue())["error"])

    def test_reviewed_cli_transport_failure_uses_exit_four(self) -> None:
        # Given real runtime construction with only catalog/state/transport dependencies injected.
        registry = reviewed_registry("kipris-web")
        with tempfile.TemporaryDirectory() as directory:
            state = PolicyState(
                Path(directory) / "state.sqlite3",
                clock=lambda: 1000.0,
                sleeper=self.fail,
            )
            responses = iter(
                [
                    Response(b"User-agent: *\nAllow: /\n", media_type="text/plain"),
                    Response(b"denied", status=403),
                ]
            )
            enforcer = HttpPolicyEnforcer(
                registry,
                state,
                HttpTransport(lambda *_a, **_k: next(responses), lambda _: ["1.1.1.1"]),
            )
            with (
                patch.object(
                    sys,
                    "argv",
                    [str(ADAPTER_PATH), "--lookup-url", "https://www.kipris.or.kr/"],
                ),
                patch.object(
                    adapter.SourcePolicyRegistry, "from_catalog", return_value=registry
                ),
                patch.object(
                    adapter,
                    "_state_path",
                    return_value=Path(directory) / "state.sqlite3",
                ),
                patch("kgov_runtime.http.PolicyState", return_value=state) as constructor,
                patch.object(adapter, "HttpPolicyEnforcer", return_value=enforcer),
                redirect_stderr(io.StringIO()) as error,
                redirect_stdout(io.StringIO()) as output,
            ):
                # When the real CLI lookup reaches the offline source.
                exit_code = adapter.main()
                constructor.assert_called_once()
            # Then upstream denial is not confused with input or policy failure.
            self.assertEqual(4, exit_code)
            self.assertEqual("", output.getvalue())
            self.assertEqual(
                "upstream-403-manual", json.loads(error.getvalue())["error"]
            )

    def test_cli_parser_never_reflects_unrecognized_sensitive_arguments(self) -> None:
        # Given an accidental credential argument that is not a supported option.
        marker = "SYNTHETIC_PRIVATE_VALUE"
        # When the real CLI parser rejects it.
        result = subprocess.run(
            [sys.executable, str(ADAPTER_PATH), "--fixture", f"--unknown={marker}"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Then parser errors do not leak input while still returning input exit 2.
        self.assertEqual(2, result.returncode)
        self.assertNotIn(marker, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
