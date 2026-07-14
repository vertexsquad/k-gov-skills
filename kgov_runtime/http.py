"""Safe, bounded HTTP primitives for read-only official-source adapters."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

USER_AGENT = "k-gov-skills/0.1 read-only"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_BYTES = 2_000_000


class UnsafeEndpointError(ValueError):
    """Raised when a URL does not satisfy the official-source network policy."""


class MissingCredentialError(RuntimeError):
    """Raised when an explicitly required user-held credential is absent."""


class ResponseTooLargeError(RuntimeError):
    """Raised when a response exceeds the bounded read limit."""


class RejectRedirectHandler(HTTPRedirectHandler):
    """Prevent a validated endpoint from redirecting to an unvalidated target."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        raise UnsafeEndpointError("HTTP redirects are forbidden; request the final official URL directly")


def safe_urlopen(request: Request, timeout: float = DEFAULT_TIMEOUT) -> Any:
    return build_opener(RejectRedirectHandler()).open(request, timeout=timeout)


def _default_resolver(host: str) -> list[str]:
    return sorted({str(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})


def _resolved_addresses(result: Iterable[Any]) -> list[str]:
    addresses: list[str] = []
    for item in result:
        if isinstance(item, str):
            addresses.append(item)
        elif isinstance(item, tuple) and len(item) >= 5:
            addresses.append(item[4][0])
        else:
            raise UnsafeEndpointError("resolver returned an unsupported address shape")
    return addresses


def validate_public_https_url(
    url: str,
    allowed_hosts: set[str],
    *,
    resolver: Callable[[str], Iterable[Any]] = _default_resolver,
) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeEndpointError("only HTTPS endpoints are allowed")
    if parsed.username or parsed.password:
        raise UnsafeEndpointError("embedded URL credentials are forbidden")
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = {value.lower().rstrip(".") for value in allowed_hosts}
    if not host or not any(host == value or host.endswith("." + value) for value in allowed):
        raise UnsafeEndpointError(f"host is not allowlisted: {host or '<missing>'}")
    addresses = _resolved_addresses(resolver(host))
    if not addresses:
        raise UnsafeEndpointError("endpoint did not resolve")
    for address in addresses:
        try:
            parsed_ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeEndpointError(f"resolver returned invalid IP: {address}") from exc
        if not parsed_ip.is_global:
            raise UnsafeEndpointError(f"non-public endpoint address is forbidden: {address}")
    return url


def build_url(
    base_url: str,
    params: Optional[Mapping[str, Any]] = None,
    *,
    credential_env: Optional[str] = None,
    credential_param: Optional[str] = None,
) -> str:
    parsed = urlsplit(base_url)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            query.extend((key, str(item)) for item in value)
        else:
            query.append((key, str(value)))
    if credential_env:
        credential = os.environ.get(credential_env)
        if not credential:
            raise MissingCredentialError(f"required environment variable is missing: {credential_env}")
        if not credential_param:
            raise ValueError("credential_param is required with credential_env")
        if any(key.lower() == credential_param.lower() for key, _ in query):
            raise ValueError(f"credential parameter must come from environment only: {credential_param}")
        query.append((credential_param, credential))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _read_response(response: Any, max_bytes: int) -> bytes:
    body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ResponseTooLargeError(f"response exceeded {max_bytes} bytes")
    return body


def fetch_json(
    base_url: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    allowed_hosts: set[str],
    credential_env: Optional[str] = None,
    credential_param: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    opener: Callable[..., Any] = safe_urlopen,
    resolver: Callable[[str], Iterable[Any]] = _default_resolver,
) -> Any:
    validate_public_https_url(base_url, allowed_hosts, resolver=resolver)
    url = build_url(
        base_url,
        params,
        credential_env=credential_env,
        credential_param=credential_param,
    )
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=timeout) as response:
            body = _read_response(response, max_bytes)
    except (HTTPError, URLError):
        raise RuntimeError("read-only request failed") from None
    return json.loads(body.decode("utf-8"))


def fetch_text(
    url: str,
    *,
    allowed_hosts: set[str],
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    opener: Callable[..., Any] = safe_urlopen,
    resolver: Callable[[str], Iterable[Any]] = _default_resolver,
) -> dict[str, Any]:
    validate_public_https_url(url, allowed_hosts, resolver=resolver)
    request = Request(url, headers={"Accept": "text/html,text/plain,application/xml", "User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=timeout) as response:
            body = _read_response(response, max_bytes)
            content_type = response.headers.get("Content-Type", "")
            status = getattr(response, "status", 200)
    except (HTTPError, URLError):
        raise RuntimeError("read-only request failed") from None
    return {
        "url": url,
        "status": status,
        "content_type": content_type,
        "text": body.decode("utf-8", errors="replace"),
    }


def normalize_records(payload: Any) -> dict[str, Any]:
    """Normalize common public-API envelopes without discarding the original payload."""
    records: list[Any]
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        candidate: Any = None
        for key in ("records", "items", "data", "results", "row"):
            if key in payload:
                candidate = payload[key]
                break
        if isinstance(candidate, dict) and "item" in candidate:
            candidate = candidate["item"]
        if candidate is None:
            records = [payload]
        elif isinstance(candidate, list):
            records = candidate
        else:
            records = [candidate]
    else:
        records = [payload]
    return {"count": len(records), "records": records, "raw": payload}
