from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from kgov_runtime.http import (
    RejectRedirectHandler,
    UnsafeEndpointError,
    build_url,
    fetch_json,
    validate_public_https_url,
)


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Type": "application/json; charset=utf-8"}
        self.status = 200

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self._body if limit < 0 else self._body[:limit]


class ReadOnlyHttpTest(unittest.TestCase):
    def test_rejects_non_https_and_unapproved_host(self) -> None:
        with self.assertRaises(UnsafeEndpointError):
            validate_public_https_url("http://kosis.kr/api", {"kosis.kr"}, resolver=lambda _: ["1.1.1.1"])
        with self.assertRaises(UnsafeEndpointError):
            validate_public_https_url("https://example.com/api", {"kosis.kr"}, resolver=lambda _: ["1.1.1.1"])

    def test_rejects_embedded_credentials_and_private_address(self) -> None:
        with self.assertRaises(UnsafeEndpointError):
            validate_public_https_url("https://user:pass@kosis.kr/api", {"kosis.kr"}, resolver=lambda _: ["1.1.1.1"])
        with self.assertRaises(UnsafeEndpointError):
            validate_public_https_url("https://kosis.kr/api", {"kosis.kr"}, resolver=lambda _: ["127.0.0.1"])

    def test_build_url_injects_key_without_logging_it(self) -> None:
        with patch.dict("os.environ", {"KOSIS_API_KEY": "fixture-secret"}, clear=True):
            url = build_url(
                "https://kosis.kr/openapi/example",
                {"format": "json"},
                credential_env="KOSIS_API_KEY",
                credential_param="apiKey",
            )
        self.assertIn("apiKey=fixture-secret", url)
        self.assertIn("format=json", url)

    def test_credential_parameter_cannot_come_from_cli_params(self) -> None:
        with patch.dict("os.environ", {"KOSIS_API_KEY": "fixture-secret"}, clear=True):
            with self.assertRaisesRegex(ValueError, "environment only"):
                build_url(
                    "https://kosis.kr/openapi/example",
                    {"apiKey": "shell-history-secret"},
                    credential_env="KOSIS_API_KEY",
                    credential_param="apiKey",
                )

    def test_fetch_json_uses_injected_opener(self) -> None:
        opened: list[str] = []

        def opener(request: object, timeout: float = 0) -> _Response:
            opened.append(request.full_url)  # type: ignore[attr-defined]
            self.assertEqual(10.0, timeout)
            return _Response({"items": [{"id": 1}]})

        payload = fetch_json(
            "https://kosis.kr/openapi/example",
            params={"format": "json"},
            allowed_hosts={"kosis.kr"},
            opener=opener,
            resolver=lambda _: ["1.1.1.1"],
        )
        self.assertEqual({"items": [{"id": 1}]}, payload)
        self.assertEqual(1, len(opened))

    def test_redirect_handler_rejects_unvalidated_target(self) -> None:
        handler = RejectRedirectHandler()
        with self.assertRaisesRegex(UnsafeEndpointError, "redirects are forbidden"):
            handler.redirect_request(None, None, 302, "Found", {}, "https://example.com/private")

    def test_network_error_does_not_expose_credential(self) -> None:
        def opener(request: object, timeout: float = 0) -> _Response:
            raise URLError("fixture-secret")

        with patch.dict("os.environ", {"KOSIS_API_KEY": "fixture-secret"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "read-only request failed") as raised:
                fetch_json(
                    "https://kosis.kr/openapi/example",
                    allowed_hosts={"kosis.kr"},
                    credential_env="KOSIS_API_KEY",
                    credential_param="apiKey",
                    opener=opener,
                    resolver=lambda _: ["1.1.1.1"],
                )
        self.assertNotIn("fixture-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
