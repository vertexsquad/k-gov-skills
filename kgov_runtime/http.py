"""Policy-enforced, bounded HTTP for read-only official-source adapters.

# noqa: SIZE_OK -- Issue #30 confines the transport, policy lifecycle, robots
# enforcement, compatibility quarantine, and matching tests to one HTTP module.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import socket
import ssl
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
from typing import Any, Final, Generic, Literal, Protocol, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from .policy_state import (
    PolicyConfigurationError,
    PolicyDigest,
    PolicyDigestMismatchError,
    PolicyId,
    PolicyKey,
    PolicyStateUnavailableError,
    RatePolicy,
    RetryAfterError,
    WaitLimitExceededError,
)
from .redaction import scan_output
from .source_policy import SourcePolicy, SourcePolicyRegistry

USER_AGENT: Final = "k-gov-skills/0.1 read-only"
DEFAULT_TIMEOUT: Final = 10.0
DEFAULT_MAX_BYTES: Final = 2_000_000
_MAX_ROBOTS_BYTES: Final = 512_000
_BAD_PERCENT: Final = re.compile(r"%(?![0-9A-Fa-f]{2})")
_ROBOTS_AGENT: Final = re.compile(r"(?:\*|[A-Za-z_-]+)\Z")
_UNRESERVED: Final = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-"
)
_FORBIDDEN_KEYS: Final = frozenset(
    {"authorization", "body", "cookie", "credential", "headers", "raw", "text"}
)
HttpFailureStatus = Literal[
    "invalid-request",
    "policy-disabled",
    "policy-expired",
    "robots-denied",
    "terms-unverified",
    "license-unverified",
    "budget-exhausted",
    "response-invalid",
    "upstream-403-manual",
    "upstream-429-manual",
    "upstream-unavailable",
]
T = TypeVar("T")


class UnsafeEndpointError(ValueError):
    """A compatibility URL does not satisfy the public HTTPS boundary."""


class MissingCredentialError(RuntimeError):
    """An explicitly required user-held credential is absent."""


class ResponseTooLargeError(RuntimeError):
    """A compatibility response exceeds its bounded read limit."""


class HttpContractError(ValueError):
    """Legacy URL construction input violates its compatibility contract."""


class LegacyTransportError(RuntimeError):
    """An injected compatibility transport did not complete."""


class ReadOnlyHttpError(RuntimeError):
    def __init__(self, status: HttpFailureStatus) -> None:
        self.status = status
        super().__init__(status)

    def __str__(self) -> str:
        return self.status


@dataclass(frozen=True, slots=True)
class SourceRequest:
    url: str
    operation_id: str
    policy: SourcePolicy


@dataclass(frozen=True, slots=True)
class HttpTransport:
    opener: Callable[..., Any]
    resolver: Callable[[str], Iterable[Any]]
    timeout: float = DEFAULT_TIMEOUT


@dataclass(frozen=True, slots=True)
class SourceReceipt:
    operation_id: str
    policy_id: str
    policy_revision: int
    policy_digest: str
    outcome: Literal["allowed"] = "allowed"


@dataclass(frozen=True, slots=True)
class FetchResult(Generic[T]):
    value: T
    source_receipt: SourceReceipt


@dataclass(frozen=True, slots=True)
class TextDocument:
    text: str
    status: int
    media_type: str
    content_length: int


class PolicyStatePort(Protocol):
    def open(self, policy: RatePolicy, opener: Callable[[], T]) -> T: ...
    def record_retry_after(self, policy: RatePolicy, value: str) -> float: ...


class RejectRedirectHandler(HTTPRedirectHandler):
    """Reject every redirect before an unreviewed target can be reached."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        try:
            if fp is not None:
                fp.close()
        finally:
            raise UnsafeEndpointError("redirects are forbidden") from None


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(
        self,
        host: str,
        *,
        approved_address: str,
        context: ssl.SSLContext,
        **kwargs: Any,
    ) -> None:
        super().__init__(host, context=context, **kwargs)
        self._approved_address = approved_address

    def connect(self) -> None:
        if self._tunnel_host is not None:
            raise UnsafeEndpointError("tunneling is forbidden")
        address = ipaddress.ip_address(self._approved_address)
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        raw_socket = socket.socket(family, socket.SOCK_STREAM)
        try:
            if self.timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                raw_socket.settimeout(self.timeout)
            if self.source_address:
                raw_socket.bind(self.source_address)
            destination = (
                (self._approved_address, self.port, 0, 0)
                if address.version == 6
                else (self._approved_address, self.port)
            )
            raw_socket.connect(destination)
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except (OSError, ssl.SSLError):
            raw_socket.close()
            raise


class _PinnedHTTPSHandler(HTTPSHandler):
    def __init__(self, approved_address: str, context: ssl.SSLContext) -> None:
        super().__init__(context=context)
        self._approved_address = approved_address

    def connection(self, host: str, **kwargs: Any) -> _PinnedHTTPSConnection:
        return _PinnedHTTPSConnection(
            host,
            approved_address=self._approved_address,
            context=self._context,
            **kwargs,
        )

    def https_open(self, request: Request) -> Any:
        return self.do_open(self.connection, request)


def _policy_urlopen(
    request: Request, timeout: float = DEFAULT_TIMEOUT, *, approved_address: str
) -> Any:
    parsed = urlsplit(request.full_url)
    if parsed.hostname is None:
        raise UnsafeEndpointError("host is required")
    context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise UnsafeEndpointError("verified TLS is required")
    request.add_unredirected_header("Host", parsed.netloc)
    return build_opener(
        ProxyHandler({}),
        _PinnedHTTPSHandler(approved_address, context),
        RejectRedirectHandler(),
    ).open(request, timeout=timeout)


def safe_urlopen(_request: Request, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """Quarantine legacy default live transport behind the policy enforcer."""
    del timeout
    raise ReadOnlyHttpError("policy-disabled")


def _network_resolver(host: str) -> list[str]:
    return sorted(
        {
            str(item[4][0])
            for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    )


def _default_resolver(_host: str) -> tuple[()]:
    """Represent the explicit-opener compatibility lane without DNS."""
    return ()


def _resolved_addresses(result: Iterable[Any]) -> list[str]:
    addresses: list[str] = []
    for item in result:
        if isinstance(item, str):
            addresses.append(item)
        elif isinstance(item, tuple) and len(item) >= 5:
            addresses.append(item[4][0])
        else:
            raise UnsafeEndpointError("unsupported resolver result")
    return addresses


def validate_public_https_url(
    url: str,
    allowed_hosts: set[str],
    *,
    resolver: Callable[[str], Iterable[Any]] | None = None,
) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise UnsafeEndpointError("unsafe HTTPS endpoint")
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = {value.lower().rstrip(".") for value in allowed_hosts}
    if not host or not any(
        host == value or host.endswith("." + value) for value in allowed
    ):
        raise UnsafeEndpointError("host is not allowlisted")
    if resolver is None:
        raise ReadOnlyHttpError("policy-disabled")
    if resolver is _default_resolver:
        return url
    addresses = _resolved_addresses(resolver(host))
    if not addresses:
        raise UnsafeEndpointError("endpoint did not resolve")
    for address in addresses:
        try:
            parsed_ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeEndpointError("resolver returned invalid IP") from exc
        if not parsed_ip.is_global:
            raise UnsafeEndpointError("non-public endpoint is forbidden")
    return url


def build_url(
    base_url: str,
    params: Mapping[str, Any] | None = None,
    *,
    credential_env: str | None = None,
    credential_param: str | None = None,
) -> str:
    parsed = urlsplit(base_url)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in (params or {}).items():
        if value is None:
            continue
        query.extend((key, str(item)) for item in value) if isinstance(
            value, (list, tuple)
        ) else query.append((key, str(value)))
    if credential_env:
        credential = os.environ.get(credential_env)
        if not credential:
            raise MissingCredentialError("required environment variable is missing")
        if not credential_param:
            raise HttpContractError("credential_param is required")
        if any(key.lower() == credential_param.lower() for key, _ in query):
            raise HttpContractError(
                "credential parameter must come from environment only"
            )
        query.append((credential_param, credential))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _read(response: Any, maximum: int) -> bytes:
    body = response.read(maximum + 1)
    if len(body) > maximum:
        raise ResponseTooLargeError
    return body


def _strict_json(body: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def constant(_value: str) -> None:
        raise ValueError

    value = json.loads(
        body.decode("utf-8", errors="strict"),
        object_pairs_hook=pairs,
        parse_constant=constant,
    )
    nodes = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if depth > 20 or nodes > 20_000:
            raise ValueError
        if isinstance(item, str):
            if len(item) > 20_000 or any(
                0xD800 <= ord(character) <= 0xDFFF for character in item
            ):
                raise ValueError
            return
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError
        if isinstance(item, dict):
            for key, child in item.items():
                visit(key, depth + 1)
                visit(child, depth + 1)
            return
        if isinstance(item, list):
            for child in item:
                visit(child, depth + 1)

    visit(value, 0)
    return value


def _safe_projection(value: Any) -> None:
    def visit(item: Any) -> None:
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise ValueError
                normalized_key = unicodedata.normalize("NFKC", key)
                if (
                    any(
                        unicodedata.category(character).startswith("C")
                        for character in normalized_key
                    )
                    or normalized_key.strip().casefold() in _FORBIDDEN_KEYS
                ):
                    raise ValueError
                visit(child)
            return
        if type(item) is list:
            for child in item:
                visit(child)
            return
        if item is not None and type(item) not in {str, bool, int, float}:
            raise ValueError
        if type(item) is float and not math.isfinite(item):
            raise ValueError

    visit(value)
    if scan_output(value):
        raise ValueError


def policy_failure_status(code: str) -> HttpFailureStatus:
    """Map registry decisions to a stable, non-reflecting transport status."""
    if code == "invalid-url":
        return "invalid-request"
    if code in {"review-required", "review-stale"}:
        return "policy-expired"
    if code.startswith("robots-"):
        return "robots-denied"
    if code.startswith("terms-"):
        return "terms-unverified"
    if code.startswith("license-"):
        return "license-unverified"
    if code.startswith("rate-"):
        return "budget-exhausted"
    if code.startswith("response-"):
        return "response-invalid"
    return "policy-disabled"


def _canonical_robots_value(value: str, *, operators: bool) -> str:
    if _BAD_PERCENT.search(value):
        raise ValueError
    normalized: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if operators and character in {"*", "$"}:
            normalized.append(character)
            index += 1
            continue
        if character == "%":
            octet = int(value[index + 1 : index + 3], 16)
            if octet < 0x20 or octet == 0x7F:
                raise ValueError
            if octet in _UNRESERVED:
                normalized.append(chr(octet))
                index += 3
                continue
            if octet < 0x80:
                normalized.append(f"%{octet:02X}")
                index += 3
                continue
            if 0xC2 <= octet <= 0xDF:
                width = 2
            elif 0xE0 <= octet <= 0xEF:
                width = 3
            elif 0xF0 <= octet <= 0xF4:
                width = 4
            else:
                raise ValueError
            encoded: list[int] = []
            for _offset in range(width):
                if index + 2 >= len(value) or value[index] != "%":
                    raise ValueError
                encoded.append(int(value[index + 1 : index + 3], 16))
                index += 3
            bytes(encoded).decode("utf-8", errors="strict")
            normalized.extend(f"%{item:02X}" for item in encoded)
            continue
        if unicodedata.category(character).startswith("C"):
            raise ValueError
        if operators and character == " ":
            raise ValueError
        if character.isascii():
            normalized.append(character)
        else:
            normalized.extend(f"%{octet:02X}" for octet in character.encode("utf-8"))
        index += 1
    return "".join(normalized)


def _robots_pattern_matches(pattern: str, target: str, *, terminal: bool) -> bool:
    if "*" not in pattern:
        return target == pattern if terminal else target.startswith(pattern)
    segments = pattern.split("*")
    cursor = 0
    first = segments[0]
    if first:
        if not target.startswith(first):
            return False
        cursor = len(first)
    remaining = [
        (index, segment) for index, segment in enumerate(segments[1:], 1) if segment
    ]
    for position, (index, segment) in enumerate(remaining):
        is_last = position == len(remaining) - 1
        if terminal and is_last and index == len(segments) - 1:
            start = len(target) - len(segment)
            if start < cursor or not target.startswith(segment, start):
                return False
            cursor = len(target)
            continue
        found = target.find(segment, cursor)
        if found < 0:
            return False
        cursor = found + len(segment)
    return True


def _robots_allowed(body: bytes, url: str) -> bool:
    text = body.decode("utf-8", errors="strict")
    groups: list[tuple[tuple[str, ...], tuple[tuple[bool, str], ...]]] = []
    agents: list[str] = []
    rules: list[tuple[bool, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError
        field, value = (part.strip() for part in line.split(":", 1))
        if not field or any(
            unicodedata.category(character).startswith("C") for character in field
        ):
            raise ValueError
        field = field.casefold()
        if field == "user-agent":
            if _ROBOTS_AGENT.fullmatch(value) is None:
                raise ValueError
            if rules:
                groups.append((tuple(agents), tuple(rules)))
                agents, rules = [], []
            agents.append(value.casefold())
            continue
        if field in {"allow", "disallow"}:
            if not agents:
                raise ValueError
            if value:
                if not value.startswith("/"):
                    raise ValueError
                rules.append(
                    (field == "allow", _canonical_robots_value(value, operators=True))
                )
    if agents:
        groups.append((tuple(agents), tuple(rules)))

    product = "k-gov-skills"
    candidates = {
        agent
        for group_agents, _group_rules in groups
        for agent in group_agents
        if agent != "*" and agent in product
    }
    if candidates:
        specificity = max(len(agent) for agent in candidates)
        winners = {agent for agent in candidates if len(agent) == specificity}
        if len(winners) != 1:
            raise ValueError
        winning_agent = winners.pop()
        selected = [
            group_rules
            for group_agents, group_rules in groups
            if winning_agent in group_agents
        ]
    else:
        selected = [
            group_rules for group_agents, group_rules in groups if "*" in group_agents
        ]

    parsed = urlsplit(url)
    path_and_query = parsed.path or "/"
    if "?" in url.partition("#")[0]:
        path_and_query = f"{path_and_query}?{parsed.query}"
    target = _canonical_robots_value(path_and_query, operators=False)
    matches: list[tuple[int, bool]] = []
    for allowed, pattern in (rule for group in selected for rule in group):
        terminal = pattern.endswith("$")
        raw_pattern = pattern[:-1] if terminal else pattern
        if "$" in raw_pattern:
            raise ValueError
        if _robots_pattern_matches(raw_pattern, target, terminal=terminal):
            octets = re.sub(r"%[0-9A-F]{2}", "x", raw_pattern.replace("*", ""))
            matches.append((len(octets), allowed))
    return not matches or max(matches)[1]


class HttpPolicyEnforcer:
    """Authorize exact registry policy identity before all mutable or network work."""

    def __init__(
        self,
        registry: SourcePolicyRegistry,
        state: PolicyStatePort,
        transport: HttpTransport | None = None,
    ) -> None:
        self._pins_address = transport is None
        self._registry, self._state = registry, state
        self._transport = transport or HttpTransport(_policy_urlopen, _network_resolver)

    def _authorize(self, request: SourceRequest) -> RatePolicy:
        decision = self._registry.authorize(request.url, request.operation_id)
        selected = next(
            (policy for policy in self._registry.policies if policy is request.policy),
            None,
        )
        if (
            not decision.allowed
            or selected is None
            or decision.policy_id != selected.id
            or decision.policy_digest != selected.digest
        ):
            raise ReadOnlyHttpError(policy_failure_status(decision.code))
        rate = selected.rate_limit
        if None in (rate.requests, rate.per_seconds, rate.burst, rate.max_wait_seconds):
            raise ReadOnlyHttpError("budget-exhausted")
        return RatePolicy(
            PolicyKey(PolicyId(selected.id), PolicyDigest(selected.digest)),
            rate.requests,
            float(rate.per_seconds),
            rate.burst,
            float(rate.max_wait_seconds),
        )

    def _validated(self, url: str, *, robots: bool = False) -> str:
        host = urlsplit(url).hostname
        try:
            addresses = _resolved_addresses(self._transport.resolver(host or ""))
            validate_public_https_url(
                url, {host or ""}, resolver=lambda _host: addresses
            )
        except (UnsafeEndpointError, OSError, ReadOnlyHttpError) as exc:
            raise ReadOnlyHttpError(
                "robots-denied" if robots else "invalid-request"
            ) from exc
        return sorted(set(addresses))[0]

    def _open(self, url: str, rate: RatePolicy, *, robots: bool = False) -> Any:
        approved_address = self._validated(url, robots=robots)
        request = Request(
            url,
            headers={
                "Accept": "text/plain"
                if robots
                else "text/html,text/plain,application/json,application/xml",
                "User-Agent": USER_AGENT,
            },
        )
        try:

            def open_once() -> Any:
                if self._pins_address:
                    return self._transport.opener(
                        request,
                        timeout=self._transport.timeout,
                        approved_address=approved_address,
                    )
                return self._transport.opener(request, timeout=self._transport.timeout)

            return self._state.open(rate, open_once)
        except (
            WaitLimitExceededError,
            PolicyDigestMismatchError,
            PolicyConfigurationError,
            PolicyStateUnavailableError,
        ) as exc:
            raise ReadOnlyHttpError("budget-exhausted") from exc
        except HTTPError as response:
            return response
        except (URLError, OSError, UnsafeEndpointError) as exc:
            raise ReadOnlyHttpError(
                "robots-denied" if robots else "upstream-unavailable"
            ) from exc

    def _robots(self, request: SourceRequest, rate: RatePolicy) -> None:
        policy = request.policy
        if policy.robots.status == "documented-api-exemption":
            exact = any(
                kind == "exact" and path == (urlsplit(request.url).path or "/")
                for kind, path in policy.scope.path_rules
            )
            if (
                policy.channel != "api"
                or policy.robots.evidence_url is None
                or not exact
            ):
                raise ReadOnlyHttpError("robots-denied")
            return
        origin = next(
            (
                origin
                for origin in policy.scope.origins
                if urlsplit(request.url).hostname == urlsplit(origin).hostname
            ),
            None,
        )
        if origin is None:
            raise ReadOnlyHttpError("robots-denied")
        response = self._open(f"{origin}/robots.txt", rate, robots=True)
        with response:
            status = getattr(response, "status", 200)
            if status in {404, 410} and policy.terms.status == "allowed":
                return
            if status == 429:
                retry = response.headers.get("Retry-After")
                if retry:
                    try:
                        self._state.record_retry_after(rate, retry)
                    except RetryAfterError as exc:
                        raise ReadOnlyHttpError("robots-denied") from exc
                    except (
                        PolicyStateUnavailableError,
                        PolicyDigestMismatchError,
                    ) as exc:
                        raise ReadOnlyHttpError("budget-exhausted") from exc
                raise ReadOnlyHttpError("robots-denied")
            if (
                status != 200
                or response.headers.get("Content-Type", "")
                .split(";", 1)[0]
                .strip()
                .casefold()
                != "text/plain"
            ):
                raise ReadOnlyHttpError("robots-denied")
            try:
                allowed = _robots_allowed(
                    _read(response, _MAX_ROBOTS_BYTES), request.url
                )
            except (
                UnicodeDecodeError,
                ValueError,
                ResponseTooLargeError,
                HTTPException,
                OSError,
            ) as exc:
                raise ReadOnlyHttpError("robots-denied") from exc
        if not allowed:
            raise ReadOnlyHttpError("robots-denied")

    def _fetch(self, request: SourceRequest) -> tuple[bytes, int, str]:
        rate = self._authorize(request)
        self._robots(request, rate)
        response = self._open(request.url, rate)
        with response:
            status = getattr(response, "status", 200)
            if status in {401, 403}:
                raise ReadOnlyHttpError("upstream-403-manual")
            if status == 429:
                retry = response.headers.get("Retry-After")
                if retry:
                    try:
                        self._state.record_retry_after(rate, retry)
                    except RetryAfterError as exc:
                        raise ReadOnlyHttpError("upstream-429-manual") from exc
                    except (
                        PolicyStateUnavailableError,
                        PolicyDigestMismatchError,
                    ) as exc:
                        raise ReadOnlyHttpError("budget-exhausted") from exc
                raise ReadOnlyHttpError("upstream-429-manual")
            if not 200 <= status < 300:
                raise ReadOnlyHttpError("upstream-unavailable")
            media = (
                response.headers.get("Content-Type", "")
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            expected = request.policy.response
            if expected.max_bytes is None or media not in {
                item.casefold() for item in expected.media_types
            }:
                raise ReadOnlyHttpError("response-invalid")
            try:
                body = _read(response, expected.max_bytes)
            except ResponseTooLargeError as exc:
                raise ReadOnlyHttpError("response-invalid") from exc
            except (HTTPException, OSError) as exc:
                raise ReadOnlyHttpError("upstream-unavailable") from exc
        if b"captcha" in body.lower() or b"recaptcha" in body.lower():
            raise ReadOnlyHttpError("upstream-403-manual")
        return body, status, media

    def _result(self, request: SourceRequest, value: T) -> FetchResult[T]:
        try:
            _safe_projection(value)
        except (TypeError, ValueError) as exc:
            raise ReadOnlyHttpError("response-invalid") from exc
        policy = request.policy
        return FetchResult(
            value,
            SourceReceipt(
                request.operation_id, policy.id, policy.revision, policy.digest
            ),
        )

    def fetch_text(
        self, request: SourceRequest, projector: Callable[[TextDocument], T]
    ) -> FetchResult[T]:
        body, status, media = self._fetch(request)
        try:
            document = TextDocument(
                body.decode("utf-8", errors="strict"), status, media, len(body)
            )
            value = projector(document)
        except (UnicodeDecodeError, TypeError, ValueError, KeyError) as exc:
            raise ReadOnlyHttpError("response-invalid") from exc
        return self._result(request, value)

    def fetch_json(
        self, request: SourceRequest, projector: Callable[[Any], T]
    ) -> FetchResult[T]:
        body, _status, _media = self._fetch(request)
        try:
            value = projector(_strict_json(body))
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            raise ReadOnlyHttpError("response-invalid") from exc
        return self._result(request, value)


def fetch_json(
    base_url: str,
    *,
    params: Mapping[str, Any] | None = None,
    allowed_hosts: set[str],
    credential_env: str | None = None,
    credential_param: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    opener: Callable[..., Any] | None = None,
    resolver: Callable[[str], Iterable[Any]] | None = None,
) -> Any:
    if opener is None or resolver is None:
        raise ReadOnlyHttpError("policy-disabled")
    url = build_url(
        base_url,
        params,
        credential_env=credential_env,
        credential_param=credential_param,
    )
    validate_public_https_url(url, allowed_hosts, resolver=resolver)
    try:
        with opener(
            Request(
                url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
            ),
            timeout=timeout,
        ) as response:
            return _strict_json(_read(response, max_bytes))
    except (HTTPError, URLError):
        raise LegacyTransportError("read-only request failed") from None


def fetch_text(
    url: str,
    *,
    allowed_hosts: set[str],
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    opener: Callable[..., Any] | None = None,
    resolver: Callable[[str], Iterable[Any]] | None = None,
) -> dict[str, Any]:
    if opener is None or resolver is None:
        raise ReadOnlyHttpError("policy-disabled")
    validate_public_https_url(url, allowed_hosts, resolver=resolver)
    try:
        with opener(
            Request(
                url,
                headers={
                    "Accept": "text/html,text/plain,application/xml",
                    "User-Agent": USER_AGENT,
                },
            ),
            timeout=timeout,
        ) as response:
            body = _read(response, max_bytes)
            content_type = response.headers.get("Content-Type", "")
            status = getattr(response, "status", 200)
    except (HTTPError, URLError):
        raise LegacyTransportError("read-only request failed") from None
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
        return {"count": len(payload), "records": payload, "raw": payload}
    if isinstance(payload, dict):
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
        return {"count": len(records), "records": records, "raw": payload}
    records = [payload]
    return {"count": len(records), "records": records, "raw": payload}
