"""Policy-bound Korean legal citation verification.

# noqa: SIZE_OK -- Issue #31 limits legal implementation to this exact file;
# the existing structural verifier and its policy boundary cannot be split.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import (
    Any,
    Callable,
    Final,
    Iterable,
    Literal,
    Mapping,
    NoReturn,
    TypedDict,
    TypeVar,
    assert_never,
)
from urllib.parse import parse_qs, quote, unquote, unquote_plus, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import JsonContractError, parse_params, strict_json_loads  # noqa: E402
from kgov_runtime.http import (  # noqa: E402
    HttpFailureStatus,
    HttpPolicyEnforcer,
    HttpTransport,
    ReadOnlyHttpError,
    SourceRequest,
    build_url,
    policy_failure_status,
)
from kgov_runtime.policy_state import PolicyState, PolicyStateUnavailableError  # noqa: E402
from kgov_runtime.source_policy import JSONValue, SourcePolicy, SourcePolicyRegistry  # noqa: E402
from kgov_runtime.redaction import contains_direct_identifier  # noqa: E402


OPERATION_ID: Final = "kgov/korean-legal-citation-verification/verify-citations/v1"
POLICY_ID: Final = "law-go-kr-drf-api"
CATALOG: Final = ROOT / "catalog/domain-skills.json"
CallKind = Literal["law-search", "law-detail", "precedent-search", "precedent-detail"]
ExecutionMode = Literal["official-live", "synthetic-fixture"]
Projection = TypeVar("Projection")


class StatuteCandidate(TypedDict):
    law_name: str
    law_id: str
    article_code: str
    paragraph_code: str | None
    item_code: str | None
    subitem_code: str | None
    quoted_text: str


class PrecedentCandidate(TypedDict):
    serial_number: str
    case_number: str
    court: str
    decision_date: str
    quoted_text: str


class PrecedentMetadata(TypedDict):
    serial_number: str
    case_number: str
    court: str
    decision_date: str
    available_text_fields: list[str]
    official_url: str


@dataclass(frozen=True, slots=True)
class CitationContext:
    citation_id: str
    as_of_date: str


@dataclass(frozen=True, slots=True)
class StatuteCitation:
    context: CitationContext
    candidate: StatuteCandidate
    kind: Literal["statute"] = "statute"


@dataclass(frozen=True, slots=True)
class PrecedentCitation:
    context: CitationContext
    candidate: PrecedentCandidate
    kind: Literal["precedent"] = "precedent"


@dataclass(frozen=True, slots=True)
class LegalRuntime:
    policy: SourcePolicy
    enforcer: HttpPolicyEnforcer
    execution_mode: ExecutionMode = "official-live"


class PolicyReceipt(TypedDict):
    operation_id: str
    policy_id: str
    policy_revision: int
    policy_digest: str
    outcome: Literal["allowed"]


class CallMetadata(TypedDict):
    call_kind: CallKind
    endpoint: str
    citation_id: str | None
    page: int | None


class CallReceipt(CallMetadata):
    source_receipt: PolicyReceipt | None


class NotFoundProjection(TypedDict):
    status: Literal["official-source-not-found"]


@dataclass(frozen=True, slots=True)
class LegalCall:
    kind: CallKind
    params: Mapping[str, str | int]
    citation_id: str | None = None

    @property
    def profile(self) -> tuple[str, str]:
        match self.kind:
            case "law-search":
                return "https://www.law.go.kr/DRF/lawSearch.do", "eflaw"
            case "law-detail":
                return "https://www.law.go.kr/DRF/lawService.do", "eflawjosub"
            case "precedent-search":
                return "https://www.law.go.kr/DRF/lawSearch.do", "prec"
            case "precedent-detail":
                return "https://www.law.go.kr/DRF/lawService.do", "prec"
            case unreachable:
                assert_never(unreachable)

    @property
    def metadata(self) -> CallMetadata:
        return {
            "call_kind": self.kind,
            "endpoint": self.profile[0],
            "citation_id": self.citation_id,
            "page": int(self.params.get("page", 1))
            if self.kind.endswith("-search")
            else None,
        }


class LegalExecutionError(ReadOnlyHttpError):
    """Expose only completed receipts and safe failed-call coordinates."""

    def __init__(
        self,
        status: HttpFailureStatus,
        trace: tuple[tuple[CallReceipt, ...], CallMetadata | None],
    ) -> None:
        super().__init__(status)
        self.source_receipts, self.failed_call = trace


def _state_path() -> Path:
    if configured := os.environ.get("KGOV_POLICY_STATE_PATH"):
        return Path(configured)
    if xdg_state := os.environ.get("XDG_STATE_HOME"):
        return Path(xdg_state) / "k-gov-skills/policy-state.sqlite3"
    return Path.home() / ".local/state/k-gov-skills/policy-state.sqlite3"


def _live_runtime() -> LegalRuntime:
    registry = SourcePolicyRegistry.from_catalog(
        json.loads(CATALOG.read_text(encoding="utf-8")), on_date=date.today()
    )
    decision = registry.authorize(LegalCall("law-search", {}).profile[0], OPERATION_ID)
    if not decision.allowed:
        raise ReadOnlyHttpError(policy_failure_status(decision.code))
    policy = next(item for item in registry.policies if item.id == POLICY_ID)
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state = PolicyState(path, clock=time.time, sleeper=time.sleep)
    except (OSError, PolicyStateUnavailableError) as exc:
        raise ReadOnlyHttpError("budget-exhausted") from exc
    return LegalRuntime(policy, HttpPolicyEnforcer(registry, state))


class LegalSession:
    """Accumulate ordered, request-local receipts; never retain raw documents."""

    def __init__(self, runtime: LegalRuntime | None) -> None:
        self.runtime = runtime or _live_runtime()
        self.receipts: list[CallReceipt] = []
        self._credentials: set[str] = set()

    def protect(self, value: Projection) -> Projection:
        """Own a safe projected copy; redact caller IDs, never authentic receipt fields."""
        safe = deepcopy(value)
        match self.runtime.execution_mode:
            case "synthetic-fixture":
                return safe
            case "official-live":
                pass
            case unreachable:
                assert_never(unreachable)

        def redact(item: JSONValue) -> None:
            """Redact only caller citation IDs in this boundary-owned copy."""
            match item:
                case dict():
                    if "citation_id" in item:
                        try:
                            for credential in self._credentials:
                                _ensure_credential_free(item["citation_id"], credential)
                        except ValueError:
                            item["citation_id"] = None
                    for child in item.values():
                        redact(child)
                case list():
                    for child in item:
                        redact(child)
                case str() | int() | float() | bool() | None:
                    pass
                case unreachable:
                    assert_never(unreachable)

        redact(safe)
        try:
            for credential in self._credentials:
                _ensure_credential_free(safe, credential)
        except ValueError:
            raise LegalExecutionError("response-invalid", ((), None)) from None
        return safe

    def error(
        self, status: HttpFailureStatus, failed_call: CallMetadata | None
    ) -> LegalExecutionError:
        # Before authorization, and in fixtures, no credential may be consulted.
        if not self._credentials:
            return LegalExecutionError(status, ((), None))
        trace = self.protect(
            {"source_receipts": self.receipts, "failed_call": failed_call}
        )
        return LegalExecutionError(
            status, (tuple(trace["source_receipts"]), trace["failed_call"])
        )

    def output(self, value: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
        return self.protect(
            dict(
                value,
                execution_mode=self.runtime.execution_mode,
                source_receipts=self.receipts,
            )
        )

    def fetch(
        self,
        call: LegalCall,
        projector: Callable[[Mapping[str, JSONValue]], Projection],
    ) -> Projection | NotFoundProjection:
        endpoint, target = call.profile
        runtime = self.runtime
        try:
            if {key.casefold() for key in call.params} & {"target", "type", "oc"}:
                raise ReadOnlyHttpError("invalid-request")
            # The enforcer owns identity checks, including injected runtimes.
            runtime.enforcer._authorize(
                SourceRequest(endpoint, OPERATION_ID, runtime.policy)
            )
            params = {**call.params, "target": target, "type": "JSON"}
            match runtime.execution_mode:
                case "official-live":
                    url = build_url(
                        endpoint, params, credential_env="LAW_OC", credential_param="OC"
                    )
                    # Track the credential actually inserted by the shared builder,
                    # including changes between fetches, without a second env read.
                    self._credentials.add(parse_qs(urlsplit(url).query)["OC"][0])
                case "synthetic-fixture":
                    url = build_url(endpoint, params)
                case unreachable:
                    assert_never(unreachable)

            def project(raw: JSONValue) -> Projection | NotFoundProjection:
                try:
                    value = projector({"records": [raw]})
                except OfficialNotFound:
                    missing: NotFoundProjection = {
                        "status": "official-source-not-found"
                    }
                    return self.protect(missing)
                value = self.protect(value)
                if _contains_identifier_after_normalization(
                    value
                ) or _contains_disallowed_unicode(value):
                    raise JsonContractError("unsafe official projection")
                return value

            fetched = runtime.enforcer.fetch_json(
                SourceRequest(url, OPERATION_ID, runtime.policy), project
            )
        except LegalExecutionError:
            raise
        except ReadOnlyHttpError as exc:
            raise self.error(exc.status, call.metadata) from None
        receipt = fetched.source_receipt
        evidence: PolicyReceipt | None
        match runtime.execution_mode:
            case "official-live":
                evidence = {
                    "operation_id": receipt.operation_id,
                    "policy_id": receipt.policy_id,
                    "policy_revision": receipt.policy_revision,
                    "policy_digest": receipt.policy_digest,
                    "outcome": receipt.outcome,
                }
            case "synthetic-fixture":
                evidence = None
            case unreachable:
                assert_never(unreachable)
        self.receipts.append(
            self.protect({**call.metadata, "source_receipt": evidence})
        )
        return fetched.value


TOP_LEVEL_FIELDS = frozenset({"as_of_date", "jurisdiction", "input_scope", "citations"})
CITATION_FIELDS = frozenset({"citation_id", "kind", "candidate"})
STATUTE_FIELDS = frozenset(
    {
        "law_name",
        "law_id",
        "article_code",
        "paragraph_code",
        "item_code",
        "subitem_code",
        "quoted_text",
    }
)
PRECEDENT_FIELDS = frozenset(
    {
        "serial_number",
        "case_number",
        "court",
        "decision_date",
        "quoted_text",
    }
)
MAX_CITATIONS = 30
MAX_INPUT_BYTES = 250_000
MAX_QUOTED_TEXT = 4_000
MIN_QUOTED_TEXT = 12
MAX_LAW_HISTORY_PAGES = 20
CITATION_ID = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
LAW_ID = re.compile(r"^[0-9]{6}$")
ARTICLE_CODE = re.compile(r"^[0-9]{6}$")
SUBUNIT_CODE = re.compile(r"^[0-9]{4}$")
SERIAL_NUMBER = re.compile(r"^[0-9]+$")
_BLOCK_TAGS: Final = frozenset(
    {
        "br",
        "p",
        "div",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
        "blockquote",
    }
)
_INLINE_TAGS: Final = frozenset({"span", "b", "strong", "em", "i", "u", "wbr"})
_SCRIPT_TAGS: Final = frozenset({"sup", "sub"})
_SCRIPT_MARKERS: Final = {"sup": ("⟪sup:", "⟫"), "sub": ("⟪sub:", "⟫")}
_SUPERSCRIPT_FOLD: Final = dict(
    zip(
        "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ",
        "0123456789+-=()abcdefghijklmnoprstuvwxyz",
        strict=True,
    )
)
_SUBSCRIPT_FOLD: Final = dict(
    zip(
        "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ",
        "0123456789+-=()aehijklmnoprstuvx",
        strict=True,
    )
)
_SCRIPT_FOLD: Final = _SUPERSCRIPT_FOLD | _SUBSCRIPT_FOLD
_SCRIPT_KIND: Final = {
    **dict.fromkeys(_SUPERSCRIPT_FOLD, "sup"),
    **dict.fromkeys(_SUBSCRIPT_FOLD, "sub"),
}
_SAFE_PUNCTUATION: Final = str.maketrans(
    {
        "−": "-",
        "➖": "-",
        "➕": "+",
        "⁄": "/",
        "∕": "/",
        "∶": ":",
        "∼": "~",
        "～": "~",
        "…": "...",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "ㆍ": "·",
        "ᆞ": "·",
    }
)
LEADING_UNIT = re.compile(r"^(?:[①-⑳]|\d+(?:\.(?![\d.])|\)(?!\d))|[가-힣][.)])\s*")
DOTTED_DATE = re.compile(
    r"(?<![\d.])(?P<year>\d{4})[ ]*\.[ ]*"
    r"(?P<month>0?[1-9]|1[0-2])(?:[ ]*\.[ ]*"
    r"(?P<day>0?[1-9]|[12]\d|3[01]))?(?:[ ]*\.)?(?![\d.])"
)
_DOTTED_DATE_TOKEN: Final = r"\d{4}\.\d{1,2}\.(?:\d{1,2}\.)?"
_GROUPED_NUMBER: Final = r"(?:\d{1,3}(?:[ ]\d{3})++|\d++(?:[.,]\d++)*+|\.\d++)"
_SCRIPT_VALUE: Final = r"⟪(?:sup|sub):[^⟫]{1,64}+⟫"
_COMPATIBILITY_FRACTION: Final = r"[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]"
_NUMERIC_VALUE: Final = (
    rf"{_GROUPED_NUMBER}(?:[eE][+\-±∓]?\d++|{_SCRIPT_VALUE})?"
    rf"(?:{_COMPATIBILITY_FRACTION})?"
)
_KOREAN_NUMBER: Final = r"[일이삼사오육칠팔구십백천만억조]{1,32}+"
_NUMERIC_UNIT: Final = r"(?:원|[%‰‱]|㎡|㎥|㎠|㎤|[kcm]?m(?:2|3|²|³)?)"
_QUANTITY_PREFIX: Final = r"(?:(?:<=|>=|[<>≤≥√+\-±∓])[ ]*)?"
_NUMERIC_QUANTITY: Final = (
    rf"(?:{_KOREAN_NUMBER}[ ]*)?{_NUMERIC_VALUE}"
    rf"(?:[ ]*[십백천만억조](?:[ ]*{_NUMERIC_VALUE})?){{0,8}}+"
    rf"(?:[ ]*{_NUMERIC_UNIT})?"
)
_KOREAN_AMOUNT_COMPONENT: Final = (
    rf"(?:{_KOREAN_NUMBER}|{_NUMERIC_VALUE}(?:[ ]*[십백천만억조])?)"
)
_KOREAN_AMOUNT: Final = (
    rf"(?>{_KOREAN_AMOUNT_COMPONENT}"
    rf"(?:[ ]+{_KOREAN_AMOUNT_COMPONENT}){{0,15}}+[ ]*원)"
)
QUANTITY_ATOM: Final = (
    rf"(?:{_QUANTITY_PREFIX}(?:{_KOREAN_AMOUNT}|{_NUMERIC_QUANTITY}))"
)
QUANTITATIVE_TOKEN = re.compile(
    rf"(?:"
    rf"{_DOTTED_DATE_TOKEN}(?:[ ]*~[ ]*{_DOTTED_DATE_TOKEN})?"
    rf"|\d{{4}}[ ]*년[ ]*\d{{1,2}}[ ]*월(?:[ ]*\d{{1,2}}[ ]*일)?"
    rf"|{QUANTITY_ATOM}[ ]*분의[ ]*{QUANTITY_ATOM}"
    rf"|{_QUANTITY_PREFIX}{_GROUPED_NUMBER}[ ]+\d++[ ]*/[ ]*\d++(?:[ ]*{_NUMERIC_UNIT})?"
    rf"|(?>{QUANTITY_ATOM}(?:[ ]*(?:[-+/:~*×÷^·⋯]|\.{{2,3}}|(?ai:to|through)|부터|까지|내지|에서)[ ]*{QUANTITY_ATOM})*+)"
    rf")"
)
QUANTITATIVE_SCAN_RADIUS: Final = 256


class _ComparisonHTMLParser(HTMLParser):
    """Render only contracted formatting while retaining script provenance."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append(" ")
        elif tag in _INLINE_TAGS:
            pass
        elif tag in _SCRIPT_TAGS:
            if self.scripts:
                raise JsonContractError("nested comparison scripts are unsupported")
            self.scripts.append(tag)
            self.parts.append(_SCRIPT_MARKERS[tag][0])
        else:
            raise JsonContractError("unsupported comparison markup")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SCRIPT_TAGS:
            raise JsonContractError("self-closing script markup is ambiguous")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS:
            self.parts.append(" ")
        elif tag in _INLINE_TAGS:
            pass
        elif tag in _SCRIPT_TAGS:
            if not self.scripts or self.scripts.pop() != tag:
                raise JsonContractError("unbalanced comparison markup")
            self.parts.append(_SCRIPT_MARKERS[tag][1])
        else:
            raise JsonContractError("unsupported comparison markup")

    def _source_text(self, data: str) -> None:
        if "⟪" in data or "⟫" in data:
            raise JsonContractError("comparison provenance markers are reserved")
        self.parts.append(data)

    def handle_data(self, data: str) -> None:
        self._source_text(data)

    def handle_entityref(self, name: str) -> None:
        self._source_text(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self._source_text(html.unescape(f"&#{name};"))

    def handle_comment(self, _data: str) -> None:
        raise JsonContractError("comparison comments are unsupported")

    def handle_decl(self, _decl: str) -> None:
        raise JsonContractError("comparison declarations are unsupported")

    def handle_pi(self, _data: str) -> None:
        raise JsonContractError("comparison processing instructions are unsupported")

    def unknown_decl(self, _data: str) -> None:
        raise JsonContractError("comparison declarations are unsupported")

    def rendered(self) -> str:
        self.close()
        if self.scripts:
            raise JsonContractError("unbalanced comparison markup")
        return "".join(self.parts)


KOREAN_ITEM_LETTERS = "가나다라마바사아자차카타파하"
LAW_SEARCH_PARAMS = frozenset({"query", "search", "LID", "display", "page"})
PRECEDENT_SEARCH_PARAMS = frozenset(
    {
        "query",
        "search",
        "display",
        "page",
        "sort",
        "date",
        "prncYd",
        "nb",
        "curt",
        "org",
        "JO",
    }
)


class OfficialNotFound(ValueError):
    pass


class OfficialAmbiguous(ValueError):
    pass


def _exact_fields(
    value: Any, expected: frozenset[str], label: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    keys = set(value)
    missing = expected - keys
    unknown = keys - expected
    if missing:
        raise ValueError(f"{label} missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{label} unknown fields: {', '.join(sorted(unknown))}")
    return value


def _required_string(value: Any, field: str, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = unicodedata.normalize("NFKC", value.strip())
    if len(normalized) > maximum:
        raise ValueError(f"{field} exceeds maximum length")
    return normalized


def _citation_label(value: Any, field: str) -> str:
    normalized = _required_string(value, field)
    if any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in normalized
    ):
        raise ValueError(f"{field} must be a safe single-line value")
    if contains_direct_identifier(normalized):
        raise ValueError("input contains a supported direct identifier")
    return normalized


def _optional_code(value: Any, field: str) -> str | None:
    if value is None:
        return None
    normalized = _required_string(value, field, 4)
    if SUBUNIT_CODE.fullmatch(normalized) is None or normalized == "0000":
        raise ValueError(f"{field} must be a non-zero four-digit code")
    return normalized


def _iso_date(value: Any, field: str) -> str:
    normalized = _required_string(value, field, 10)
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD format") from exc
    if parsed.isoformat() != normalized:
        raise ValueError(f"{field} must use YYYY-MM-DD format")
    return normalized


def _compact_date(value: Any, field: str) -> str:
    normalized = _required_string(value, field, 20)
    compact = re.fullmatch(r"\s*(\d{4})(\d{2})(\d{2})\s*", normalized)
    dotted = re.fullmatch(
        r"\s*(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*(\d{1,2})\s*[.]?\s*",
        normalized,
    )
    matched = compact or dotted
    if matched is None:
        raise ValueError(f"unexpected official {field} format")
    try:
        return date(*(int(part) for part in matched.groups())).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid official {field}") from exc


def _fold_comparison_text(value: str) -> str:
    folded: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        kind = _SCRIPT_KIND.get(character)
        if kind is not None:
            run: list[str] = []
            while index < len(value) and _SCRIPT_KIND.get(value[index]) == kind:
                run.append(_SCRIPT_FOLD[value[index]])
                index += 1
            folded.append(f"⟪{kind}:{''.join(run)}⟫")
            continue
        codepoint = ord(character)
        if 0xFF01 <= codepoint <= 0xFF5E:
            character = chr(codepoint - 0xFEE0)
        elif character == "\u3000" or unicodedata.category(character) == "Zs":
            character = " "
        folded.append(character.translate(_SAFE_PUNCTUATION))
        index += 1
    return "".join(folded)


def _merge_script_runs(value: str) -> str:
    parts: list[str] = []
    pending_kind: str | None = None
    pending_payload = ""

    def flush() -> None:
        nonlocal pending_kind, pending_payload
        if pending_kind is not None:
            parts.append(f"⟪{pending_kind}:{pending_payload}⟫")
            pending_kind, pending_payload = None, ""

    index = 0
    while index < len(value):
        kind = next(
            (
                candidate
                for candidate in _SCRIPT_TAGS
                if value.startswith(f"⟪{candidate}:", index)
            ),
            None,
        )
        if kind is None:
            if value[index] in "⟪⟫":
                raise JsonContractError("malformed comparison provenance marker")
            flush()
            parts.append(value[index])
            index += 1
            continue
        payload_start = index + len(kind) + 2
        payload_end = value.find("⟫", payload_start)
        if payload_end < 0:
            raise JsonContractError("malformed comparison provenance marker")
        payload = value[payload_start:payload_end]
        if not payload or len(payload) > 64 or "⟪" in payload:
            raise JsonContractError("comparison script payload is invalid")
        if pending_kind == kind:
            pending_payload += payload
        else:
            flush()
            pending_kind, pending_payload = kind, payload
        if len(pending_payload) > 64:
            raise JsonContractError("comparison script payload is too long")
        index = payload_end + 1
    flush()
    return "".join(parts)


def _normalized_text(value: str) -> str:
    parser = _ComparisonHTMLParser()
    parser.feed(value)
    rendered = parser.rendered()
    # Strip circled structural markers before selective folding; parenthesized forms remain evidence.
    rendered = re.sub(r"^\s*[①-⑳]\s*", "", rendered)
    normalized = _merge_script_runs(_fold_comparison_text(rendered))
    normalized = re.sub(r"\s+", " ", normalized).strip()

    def dotted(matched: re.Match[str]) -> str:
        day = matched.group("day")
        suffix = "" if day is None else f"{int(day)}."
        return f"{matched.group('year')}.{int(matched.group('month'))}.{suffix}"

    normalized = DOTTED_DATE.sub(dotted, normalized)
    return LEADING_UNIT.sub("", normalized).strip()


def _boundary_splits_quantitative(text: str, boundary: int) -> bool:
    left = max(0, boundary - QUANTITATIVE_SCAN_RADIUS)
    right = min(len(text), boundary + QUANTITATIVE_SCAN_RADIUS)
    window = text[left:right]
    local = boundary - left
    for token in QUANTITATIVE_TOKEN.finditer(window):
        if token.start() < local < token.end():
            return True
        if left > 0 and token.start() == 0 and token.end() >= local:
            return True
        if right < len(text) and token.end() == len(window) and token.start() <= local:
            return True
    return False


def _quote_matches(candidate: str, official: str) -> bool:
    """Find exact excerpts, scanning only fixed-size windows at their boundaries."""
    excerpt = _normalized_text(candidate)
    source = _normalized_text(official)
    start = source.find(excerpt)
    while start >= 0:
        end = start + len(excerpt)
        if not _boundary_splits_quantitative(
            source, start
        ) and not _boundary_splits_quantitative(source, end):
            return True
        start = source.find(excerpt, start + 1)
    return False


def _quoted_text(value: Any) -> str:
    _required_string(value, "quoted_text", MAX_QUOTED_TEXT)
    # Preserve structural Unicode until the comparison normalizer can identify it.
    trimmed = value.strip()
    if len(_normalized_text(trimmed)) < MIN_QUOTED_TEXT:
        raise ValueError(
            f"quoted_text must contain at least {MIN_QUOTED_TEXT} normalized characters"
        )
    return trimmed


def _bounded_semantic_text(text: str) -> str:
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        raise JsonContractError("semantic comparison exceeds bounded size")
    return text


def _decode_percent_once(text: str) -> str:
    """Build one bounded strict UTF-8 comparison view without mutating source text."""
    return _bounded_semantic_text(
        unquote(_bounded_semantic_text(text), encoding="utf-8", errors="strict")
    )


def _semantic_views(text: str) -> frozenset[str]:
    """Apply percent, entity and compatibility transforms at most once each."""
    transforms = (
        lambda item: (
            _decode_percent_once(item),
            _bounded_semantic_text(
                unquote_plus(item, encoding="utf-8", errors="strict")
            ),
        ),
        lambda item: (_bounded_semantic_text(html.unescape(item)),),
        lambda item: (_bounded_semantic_text(unicodedata.normalize("NFKC", item)),),
    )
    pending = [(0, _bounded_semantic_text(text))]
    states: set[tuple[int, str]] = set()
    views: set[str] = set()
    while pending:
        used, current = pending.pop()
        if (used, current) in states:
            continue
        states.add((used, current))
        views.add(current)
        for index, transform in enumerate(transforms):
            bit = 1 << index
            if not used & bit:
                pending.extend((used | bit, result) for result in transform(current))
    return frozenset(views)


def _identifier_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if type(value) in {int, float, bool}:
        try:
            return json.dumps(value, ensure_ascii=False, allow_nan=False)
        except ValueError:
            return None
    return None


def _contains_identifier_after_normalization(value: Any) -> bool:
    text = _identifier_text(value)
    if text is not None:
        for semantic in _semantic_views(text):
            without_controls = "".join(
                character
                for character in semantic
                if not unicodedata.category(character).startswith("C")
                and unicodedata.category(character) not in {"Zl", "Zp"}
            )
            dash_normalized = without_controls.translate(
                str.maketrans({character: "-" for character in "‐‑‒–—―−"})
            )
            collapsed = re.sub(r"\s+", " ", dash_normalized).strip()
            tight_separators = re.sub(r"\s*([@.\-])\s*", r"\1", collapsed)
            compact = re.sub(r"[\s-]+", "", tight_separators)
            if any(
                contains_direct_identifier(candidate)
                for candidate in (
                    semantic,
                    without_controls,
                    collapsed,
                    tight_separators,
                    compact,
                )
            ):
                return True
        return False
    if isinstance(value, Mapping):
        return any(
            _contains_identifier_after_normalization(key)
            or _contains_identifier_after_normalization(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_identifier_after_normalization(item) for item in value)
    return False


def _contains_disallowed_unicode(value: Any) -> bool:
    text = _identifier_text(value)
    if text is not None:
        return any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for semantic in _semantic_views(text)
            for character in semantic
        )
    if isinstance(value, Mapping):
        return any(
            _contains_disallowed_unicode(key) or _contains_disallowed_unicode(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_disallowed_unicode(item) for item in value)
    return False


def _ensure_credential_free(value: Any, credential: str | None) -> None:
    if not credential:
        return
    needles = {view for view in _semantic_views(credential) if view}

    def contains(item: Any) -> bool:
        text = _identifier_text(item)
        if text is not None:
            return any(
                needle in view for view in _semantic_views(text) for needle in needles
            )
        if isinstance(item, Mapping):
            return any(contains(key) or contains(child) for key, child in item.items())
        if isinstance(item, list):
            return any(contains(child) for child in item)
        return False

    if contains(value):
        raise ValueError("output contains reflected credential material")


def _as_record_list(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return list(value)
    raise ValueError(f"official {label} schema is invalid")


def _positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"official {label} schema is invalid") from exc
    if parsed < 0:
        raise ValueError(f"official {label} schema is invalid")
    return parsed


def _validated_search_params(
    params: Mapping[str, Any] | None,
    allowed: frozenset[str],
) -> dict[str, Any]:
    normalized = dict(params or {})
    unknown = set(normalized) - allowed
    if unknown:
        raise ValueError(f"unknown parameters: {', '.join(sorted(unknown))}")
    for key, value in normalized.items():
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError(f"{key} must be a scalar")
        if (
            not str(value).strip()
            or len(str(value)) > 200
            or _contains_disallowed_unicode(value)
        ):
            raise ValueError(f"{key} violates bounded string requirements")
        if _contains_identifier_after_normalization(str(value)):
            raise JsonContractError("parameter contains a supported direct identifier")
    for key, maximum in (("display", 100), ("page", 10_000)):
        if key in normalized:
            try:
                number = int(normalized[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be an integer") from exc
            if number < 1 or number > maximum:
                raise ValueError(f"{key} is outside the allowed range")
            normalized[key] = number
    return normalized


def _precedent_url(case_number: str) -> str:
    return (
        "https://www.law.go.kr/"
        + quote("판례", safe="")
        + "/("
        + quote(case_number, safe="")
        + ")"
    )


def _article_display(code: str) -> str:
    article = int(code[:4])
    subarticle = int(code[4:])
    return f"제{article}조" + (f"의{subarticle}" if subarticle else "")


def _article_api_number(code: str) -> str:
    article = int(code[:4])
    subarticle = int(code[4:])
    return str(article) + (f"의{subarticle}" if subarticle else "")


def _law_url(mst: str, article_code: str) -> str:
    query = urlencode(
        {
            "lsiSeq": mst,
            "joNo": article_code[:4],
            "joBrNo": article_code[4:],
            "docCls": "jo",
            "urlMode": "lsScJoRltInfoR",
        }
    )
    return "https://www.law.go.kr/LSW/lsSideInfoP.do?" + query


def _expected_page_count(total: int, display: int, page: int) -> int:
    start = (page - 1) * display
    return 0 if start >= total else min(display, total - start)


def _normalize_precedent_search(
    result: Mapping[str, Any], requested_display: int, requested_page: int
) -> dict[str, Any]:
    raw_records = result.get("records")
    if not isinstance(raw_records, list) or len(raw_records) != 1:
        raise ValueError("official precedent search envelope is invalid")
    raw = raw_records[0]
    if not isinstance(raw, Mapping) or not isinstance(raw.get("PrecSearch"), Mapping):
        raise ValueError("official precedent search envelope is invalid")
    envelope = raw["PrecSearch"]
    total = _positive_int(envelope.get("totalCnt"), "precedent search totalCnt")
    records = _as_record_list(envelope.get("prec"), "precedent search records")
    if len(records) != _expected_page_count(total, requested_display, requested_page):
        raise ValueError("official precedent search count is inconsistent")
    safe_records: list[dict[str, Any]] = []
    for record in records:
        serial = _required_string(record.get("판례일련번호"), "판례일련번호", 30)
        case_number = _citation_label(record.get("사건번호"), "사건번호")
        court = _citation_label(record.get("법원명"), "법원명")
        decision_date = _compact_date(record.get("선고일자"), "precedent decision date")
        if SERIAL_NUMBER.fullmatch(serial) is None:
            raise ValueError("official precedent search serial number is invalid")
        safe_records.append(
            {
                "serial_number": serial,
                "case_number": case_number,
                "court": court,
                "decision_date": decision_date,
                "official_url": _precedent_url(case_number),
            }
        )
    if total == 0:
        selection_status = "no-candidates"
    elif total == 1:
        selection_status = "unique-candidate"
    else:
        selection_status = "ambiguous-candidates-manual-selection-required"
    normalized = {
        "source": "law.go.kr",
        "target": "prec",
        "total_count": total,
        "count": len(safe_records),
        "records": safe_records,
        "selection_status": selection_status,
        "manual_selection_required": total != 1,
    }
    return normalized


def search_precedents(
    params: Mapping[str, Any] | None = None,
    *,
    runtime: LegalRuntime | None = None,
) -> dict[str, Any]:
    validated = _validated_search_params(params, PRECEDENT_SEARCH_PARAMS)
    session = LegalSession(runtime)
    result = session.fetch(
        LegalCall("precedent-search", validated),
        lambda raw: _normalize_precedent_search(
            raw, int(validated.get("display", 20)), int(validated.get("page", 1))
        ),
    )
    return session.output(result)


def _precedent_detail(
    serial_number: str,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    serial = _required_string(serial_number, "serial_number", 30)
    if SERIAL_NUMBER.fullmatch(serial) is None:
        raise ValueError("serial_number must be numeric")
    records = result.get("records")
    if (
        not isinstance(records, list)
        or len(records) != 1
        or not isinstance(records[0], Mapping)
    ):
        raise ValueError("official precedent detail envelope is invalid")
    raw = records[0]
    envelope = raw.get("PrecService")
    if isinstance(envelope, Mapping):
        required = {
            "판례정보일련번호",
            "사건번호",
            "법원명",
            "선고일자",
        }
        if not required.issubset(envelope):
            raise ValueError("official precedent detail schema is invalid")
        official_serial = _required_string(
            envelope.get("판례정보일련번호"), "판례정보일련번호", 30
        )
        case_number = _citation_label(envelope.get("사건번호"), "사건번호")
        court = _citation_label(envelope.get("법원명"), "법원명")
        decision_date = _compact_date(
            envelope.get("선고일자"), "precedent decision date"
        )
        texts: dict[str, str] = {}
        for field in ("판시사항", "판결요지", "판례내용"):
            value = envelope.get(field)
            if isinstance(value, str) and value.strip():
                texts[field] = value
        if not texts:
            raise ValueError("official precedent detail has no citable text")
        if official_serial != serial:
            raise ValueError("official precedent detail serial mismatch")
        return {
            "serial_number": official_serial,
            "case_number": case_number,
            "court": court,
            "decision_date": decision_date,
            "texts": texts,
            "official_url": _precedent_url(case_number),
        }
    message = raw.get("Law")
    if isinstance(message, str) and message.strip().startswith(
        "일치하는 판례가 없습니다"
    ):
        raise OfficialNotFound("official precedent not found")
    if isinstance(message, str):
        raise ValueError("official API error response")
    raise ValueError("official precedent detail envelope is invalid")


def get_precedent(
    serial_number: str,
    *,
    runtime: LegalRuntime | None = None,
) -> dict[str, Any]:
    serial = _required_string(serial_number, "serial_number", 30)
    if SERIAL_NUMBER.fullmatch(serial) is None:
        raise JsonContractError("serial_number must be numeric")
    if _contains_identifier_after_normalization(serial):
        raise JsonContractError("serial_number contains a supported direct identifier")
    session = LegalSession(runtime)

    def project(raw: Mapping[str, JSONValue]) -> PrecedentMetadata:
        detail = _precedent_detail(serial, raw)
        return {
            "serial_number": detail["serial_number"],
            "case_number": detail["case_number"],
            "court": detail["court"],
            "decision_date": detail["decision_date"],
            "available_text_fields": sorted(detail["texts"]),
            "official_url": detail["official_url"],
        }

    detail = session.fetch(LegalCall("precedent-detail", {"ID": serial}), project)
    if detail.get("status") == "official-source-not-found":
        output = {
            "source": "law.go.kr",
            "target": "prec",
            "status": "official-precedent-not-found",
            "not_found": True,
            "count": 0,
            "records": [],
        }
    else:
        output = {
            "source": "law.go.kr",
            "target": "prec",
            "status": "official-precedent-retrieved",
            "not_found": False,
            "count": 1,
            "records": [detail],
        }
    return session.output(output)


def _normalize_law_search(
    result: Mapping[str, Any], requested_display: int, requested_page: int
) -> dict[str, Any]:
    raw_records = result.get("records")
    if not isinstance(raw_records, list) or len(raw_records) != 1:
        raise ValueError("official law search envelope is invalid")
    raw = raw_records[0]
    if not isinstance(raw, Mapping) or not isinstance(raw.get("LawSearch"), Mapping):
        raise ValueError("official law search envelope is invalid")
    envelope = raw["LawSearch"]
    total = _positive_int(envelope.get("totalCnt"), "law search totalCnt")
    records = _as_record_list(envelope.get("law"), "law search records")
    if len(records) != _expected_page_count(total, requested_display, requested_page):
        raise ValueError("official law search count is inconsistent")
    safe: list[dict[str, Any]] = []
    for record in records:
        law_name = _citation_label(record.get("법령명한글"), "법령명한글")
        law_id = _required_string(record.get("법령ID"), "법령ID", 20)
        mst = _required_string(record.get("법령일련번호"), "법령일련번호", 30)
        effective_date = _compact_date(record.get("시행일자"), "law effective date")
        if not law_id.isdigit() or not mst.isdigit():
            raise ValueError("official law search identifier is invalid")
        safe.append(
            {
                "law_name": law_name,
                "law_id": law_id,
                "mst": mst,
                "effective_date": effective_date,
                "history_status": _required_string(
                    record.get("현행연혁코드"), "현행연혁코드", 30
                ),
            }
        )
    normalized = {
        "source": "law.go.kr",
        "target": "eflaw",
        "total_count": total,
        "records": safe,
    }
    return normalized


def search_laws(
    params: Mapping[str, Any] | None = None,
    *,
    runtime: LegalRuntime | None = None,
) -> dict[str, Any]:
    validated = _validated_search_params(params, LAW_SEARCH_PARAMS)
    session = LegalSession(runtime)
    normalized = session.fetch(
        LegalCall("law-search", validated),
        lambda raw: _normalize_law_search(
            raw, int(validated.get("display", 20)), int(validated.get("page", 1))
        ),
    )
    normalized["count"] = len(normalized["records"])
    return session.output(normalized)


def _select_law_version(
    candidate: Mapping[str, Any],
    context: CitationContext,
    session: LegalSession,
) -> dict[str, Any]:
    citation_id, as_of_date = context.citation_id, context.as_of_date
    all_records: list[dict[str, Any]] = []
    seen_records: set[tuple[str, str, str, str]] = set()
    page = 1
    expected_total: int | None = None
    while True:
        if page > MAX_LAW_HISTORY_PAGES:
            raise ValueError("official law history exceeds safe pagination limit")
        result = session.fetch(
            LegalCall(
                "law-search",
                {"LID": candidate["law_id"], "display": 100, "page": page},
                citation_id,
            ),
            lambda raw: _normalize_law_search(raw, 100, page),
        )
        if expected_total is None:
            expected_total = result["total_count"]
        elif result["total_count"] != expected_total:
            raise ValueError("official law history total changed across pages")
        if expected_total is None:
            raise ValueError("official law history total is unavailable")
        for record in result["records"]:
            key = (
                record["law_id"],
                record["mst"],
                record["effective_date"],
                record["law_name"],
            )
            if key in seen_records:
                raise ValueError("official law history contains a duplicate record")
            seen_records.add(key)
            all_records.append(record)
        if len(all_records) == expected_total:
            break
        if len(all_records) > expected_total:
            raise ValueError("official law history count is inconsistent")
        page += 1
    matching = [
        record
        for record in all_records
        if record["law_id"] == candidate["law_id"]
        and record["law_name"] == candidate["law_name"]
        and record["effective_date"] <= as_of_date
    ]
    if not matching:
        raise OfficialNotFound("official statute version not found")
    latest_date = max(record["effective_date"] for record in matching)
    latest = {
        record["mst"]: record
        for record in matching
        if record["effective_date"] == latest_date
    }
    if len(latest) != 1:
        raise OfficialAmbiguous("official statute version is ambiguous")
    return next(iter(latest.values()))


def _label_number(value: Any, field: str) -> int:
    label = _required_string(value, field, 30)
    matched = re.fullmatch(rf"(\d+|[{KOREAN_ITEM_LETTERS}])(?:[ ]*[.)])?", label)
    if matched is None:
        raise ValueError(f"official {field} schema is invalid")
    number = matched.group(1)
    return (
        KOREAN_ITEM_LETTERS.index(number) + 1
        if number in KOREAN_ITEM_LETTERS
        else int(number)
    )


def _select_numbered(
    records: Any, code: str, label_field: str, container: str
) -> Mapping[str, Any]:
    items = _as_record_list(records, container)
    expected = int(code)
    selected = [
        item
        for item in items
        if _label_number(item.get(label_field), label_field) == expected
    ]
    if len(selected) != 1:
        raise ValueError(f"official {container} locator is missing or ambiguous")
    return selected[0]


def _collect_text(node: Mapping[str, Any], keys: Iterable[str]) -> str:
    parts = [
        node[key]
        for key in keys
        if isinstance(node.get(key), str) and node[key].strip()
    ]
    return " ".join(parts)


def _statute_unit(
    candidate: Mapping[str, Any],
    context: CitationContext,
    session: LegalSession,
) -> dict[str, Any]:
    citation_id = context.citation_id
    version = _select_law_version(candidate, context, session)
    params: dict[str, Any] = {
        "MST": version["mst"],
        "efYd": version["effective_date"].replace("-", ""),
        "JO": candidate["article_code"],
    }
    for source, target in (("paragraph_code", "HANG"), ("item_code", "HO")):
        if candidate[source] is not None:
            params[target] = f"{int(candidate[source]):04d}00"
    if candidate["subitem_code"] is not None:
        params["MOK"] = KOREAN_ITEM_LETTERS[int(candidate["subitem_code"]) - 1]
    return session.fetch(
        LegalCall("law-detail", params, citation_id),
        lambda raw: _verified_statute(
            citation_id, candidate, _parse_statute_unit(raw, candidate, version)
        ),
    )


def _parse_statute_unit(
    result: Mapping[str, Any],
    candidate: Mapping[str, Any],
    version: Mapping[str, Any],
) -> dict[str, Any]:
    records = result.get("records")
    if (
        not isinstance(records, list)
        or len(records) != 1
        or not isinstance(records[0], Mapping)
    ):
        raise ValueError("official statute detail envelope is invalid")
    law = records[0].get("법령")
    if not isinstance(law, Mapping):
        message = records[0].get("Law")
        if isinstance(message, str) and message.strip().startswith(
            "일치하는 법령이 없습니다"
        ):
            raise OfficialNotFound("official statute unit not found")
        raise ValueError("official statute detail envelope is invalid")
    basic = law.get("기본정보")
    articles = law.get("조문")
    if not isinstance(basic, Mapping) or not isinstance(articles, Mapping):
        raise ValueError("official statute detail schema is invalid")
    official_name = _citation_label(basic.get("법령명_한글"), "법령명_한글")
    official_id = _required_string(basic.get("법령ID"), "법령ID", 20)
    effective_date = _compact_date(basic.get("시행일자"), "law effective date")
    if (
        official_name != version["law_name"]
        or official_id != version["law_id"]
        or effective_date != version["effective_date"]
    ):
        raise ValueError("official statute search/detail identity mismatch")
    units = _as_record_list(articles.get("조문단위"), "statute article units")
    expected_article = _article_api_number(candidate["article_code"])
    selected_articles = [
        unit
        for unit in units
        if unit.get("조문여부") == "조문"
        and _required_string(unit.get("조문번호"), "조문번호", 20) == expected_article
    ]
    if len(selected_articles) != 1:
        raise ValueError("official statute article locator is missing or ambiguous")
    node = selected_articles[0]
    text = _collect_text(node, ("조문내용",))
    if candidate["paragraph_code"] is not None:
        node = _select_numbered(
            node.get("항"), candidate["paragraph_code"], "항번호", "statute paragraphs"
        )
        text = _collect_text(node, ("항내용",))
    else:
        text += (
            " "
            + " ".join(
                _collect_text(item, ("항내용",))
                for item in _as_record_list(node.get("항"), "statute paragraphs")
            )
            if node.get("항") is not None
            else ""
        )
    if candidate["item_code"] is not None:
        node = _select_numbered(
            node.get("호"), candidate["item_code"], "호번호", "statute items"
        )
        text = _collect_text(node, ("호내용",))
    elif candidate["paragraph_code"] is not None and node.get("호") is not None:
        text += " " + " ".join(
            _collect_text(item, ("호내용",))
            for item in _as_record_list(node.get("호"), "statute items")
        )
    if candidate["subitem_code"] is not None:
        node = _select_numbered(
            node.get("목"), candidate["subitem_code"], "목번호", "statute subitems"
        )
        text = _collect_text(node, ("목내용",))
    if not text.strip():
        raise ValueError("official statute locator has no citable text")
    return {
        "law_name": official_name,
        "law_id": official_id,
        "effective_date": effective_date,
        "text": text,
        "official_url": _law_url(version["mst"], candidate["article_code"]),
    }


def _validate_statute_candidate(value: JSONValue) -> StatuteCandidate:
    fields = _exact_fields(value, STATUTE_FIELDS, "candidate")
    law_id = _required_string(fields.get("law_id"), "law_id", 6)
    article = _required_string(fields.get("article_code"), "article_code", 6)
    if LAW_ID.fullmatch(law_id) is None:
        raise ValueError("law_id must be six digits")
    if ARTICLE_CODE.fullmatch(article) is None or article == "000000":
        raise ValueError("article_code must be a non-zero six-digit code")
    paragraph = _optional_code(fields.get("paragraph_code"), "paragraph_code")
    item = _optional_code(fields.get("item_code"), "item_code")
    subitem = _optional_code(fields.get("subitem_code"), "subitem_code")
    if item is not None and paragraph is None:
        raise ValueError("item_code requires paragraph_code")
    if subitem is not None and item is None:
        raise ValueError("subitem_code requires item_code")
    if subitem is not None and int(subitem) > len(KOREAN_ITEM_LETTERS):
        raise ValueError("subitem_code exceeds supported Korean item letters")
    return {
        "law_name": _citation_label(fields.get("law_name"), "law_name"),
        "law_id": law_id,
        "article_code": article,
        "paragraph_code": paragraph,
        "item_code": item,
        "subitem_code": subitem,
        "quoted_text": _quoted_text(fields.get("quoted_text")),
    }


def _validate_precedent_candidate(value: JSONValue) -> PrecedentCandidate:
    fields = _exact_fields(value, PRECEDENT_FIELDS, "candidate")
    serial = _required_string(fields.get("serial_number"), "serial_number", 30)
    if SERIAL_NUMBER.fullmatch(serial) is None:
        raise ValueError("serial_number must be numeric")
    return {
        "serial_number": serial,
        "case_number": _citation_label(fields.get("case_number"), "case_number"),
        "court": _citation_label(fields.get("court"), "court"),
        "decision_date": _iso_date(fields.get("decision_date"), "decision_date"),
        "quoted_text": _quoted_text(fields.get("quoted_text")),
    }


def _verified_statute(
    citation_id: str, candidate: Mapping[str, Any], official: Mapping[str, Any]
) -> dict[str, Any]:
    mismatches: list[str] = []
    if candidate["law_name"] != official["law_name"]:
        mismatches.append("law_name")
    if candidate["law_id"] != official["law_id"]:
        mismatches.append("law_id")
    if not _quote_matches(candidate["quoted_text"], official["text"]):
        mismatches.append("quoted_text")
    base = {
        "citation_id": citation_id,
        "kind": "statute",
        "mismatched_fields": sorted(mismatches),
    }
    if mismatches:
        return dict(base, status="mismatch-blocked")
    citation = official["law_name"] + " " + _article_display(candidate["article_code"])
    if candidate["paragraph_code"] is not None:
        citation += f" 제{int(candidate['paragraph_code'])}항"
    if candidate["item_code"] is not None:
        citation += f" 제{int(candidate['item_code'])}호"
    if candidate["subitem_code"] is not None:
        subitem = int(candidate["subitem_code"])
        if subitem > len(KOREAN_ITEM_LETTERS):
            raise ValueError("subitem_code exceeds supported Korean item letters")
        citation += f" {KOREAN_ITEM_LETTERS[subitem - 1]}목"
    return dict(
        base,
        status="verified-official-live-match",
        effective_date=official["effective_date"],
        source_url=official["official_url"],
        verified_citation=citation,
    )


def _verified_precedent(
    context: CitationContext,
    candidate: Mapping[str, Any],
    official: Mapping[str, Any],
) -> dict[str, Any]:
    mismatches: list[str] = []
    for field in ("serial_number", "case_number", "court", "decision_date"):
        if candidate[field] != official[field]:
            mismatches.append(field)
    if official["decision_date"] > context.as_of_date:
        mismatches.append("decision_date_after_as_of_date")
    matched_fields = [
        field
        for field, text in official["texts"].items()
        if _quote_matches(candidate["quoted_text"], text)
    ]
    if not matched_fields:
        mismatches.append("quoted_text")
    base = {
        "citation_id": context.citation_id,
        "kind": "precedent",
        "mismatched_fields": sorted(set(mismatches)),
    }
    if mismatches:
        return dict(base, status="mismatch-blocked")
    return dict(
        base,
        status="verified-official-live-match",
        quote_source_field=matched_fields[0],
        source_url=official["official_url"],
        verified_citation=(
            f"{official['court']} {official['decision_date']} 선고 "
            f"{official['case_number']} 판결"
        ),
    )


def verify_citations(
    payload: Mapping[str, Any],
    *,
    runtime: LegalRuntime | None = None,
) -> dict[str, Any]:
    _exact_fields(payload, TOP_LEVEL_FIELDS, "input")
    as_of_date = _iso_date(payload.get("as_of_date"), "as_of_date")
    if payload.get("jurisdiction") != "KR":
        raise ValueError("jurisdiction must be KR")
    if payload.get("input_scope") != "redacted-citations-only":
        raise ValueError("input_scope must be redacted-citations-only")
    citations = payload.get("citations")
    if (
        not isinstance(citations, list)
        or not citations
        or len(citations) > MAX_CITATIONS
    ):
        raise ValueError(f"citations must contain 1 to {MAX_CITATIONS} items")
    if _contains_disallowed_unicode(payload):
        raise ValueError("input contains disallowed single-line Unicode controls")
    if _contains_identifier_after_normalization(payload):
        raise ValueError("input contains a supported direct identifier")
    validated: list[StatuteCitation | PrecedentCitation] = []
    seen: set[str] = set()
    for raw in citations:
        citation = _exact_fields(raw, CITATION_FIELDS, "citation")
        citation_id = _required_string(citation.get("citation_id"), "citation_id", 32)
        if CITATION_ID.fullmatch(citation_id) is None:
            raise ValueError("citation_id has an invalid format")
        if citation_id in seen:
            raise ValueError("citation_id values must be unique")
        seen.add(citation_id)
        kind = _required_string(citation.get("kind"), "kind", 20)
        context = CitationContext(citation_id, as_of_date)
        try:
            match kind:
                case "statute":
                    validated.append(
                        StatuteCitation(
                            context,
                            _validate_statute_candidate(citation.get("candidate")),
                        )
                    )
                case "precedent":
                    validated.append(
                        PrecedentCitation(
                            context,
                            _validate_precedent_candidate(citation.get("candidate")),
                        )
                    )
                case unreachable:
                    assert_never(unreachable)
        except AssertionError as exc:
            raise JsonContractError("kind must be statute or precedent") from exc
    session = LegalSession(runtime)
    results: list[dict[str, Any]] = []
    for citation in validated:
        context = citation.context
        try:
            match citation:
                case StatuteCitation(candidate=candidate):
                    result = _statute_unit(candidate, context, session)
                case PrecedentCitation(candidate=candidate):
                    result = session.fetch(
                        LegalCall(
                            "precedent-detail",
                            {"ID": candidate["serial_number"]},
                            context.citation_id,
                        ),
                        lambda raw: _verified_precedent(
                            context,
                            candidate,
                            _precedent_detail(candidate["serial_number"], raw),
                        ),
                    )
                case unreachable:
                    assert_never(unreachable)
            if result.get("status") == "official-source-not-found":
                raise OfficialNotFound("official source not found")
        except OfficialNotFound:
            result = {
                "citation_id": context.citation_id,
                "kind": citation.kind,
                "status": "official-source-not-found",
                "mismatched_fields": ["official_source"],
            }
        except OfficialAmbiguous:
            result = {
                "citation_id": context.citation_id,
                "kind": citation.kind,
                "status": "ambiguous-candidates-manual-selection-required",
                "mismatched_fields": ["official_source"],
            }
        except ValueError:
            raise session.error("response-invalid", None) from None
        results.append(result)
    verified_count = sum(
        item["status"] == "verified-official-live-match" for item in results
    )
    blocked_count = len(results) - verified_count
    admission_passed = blocked_count == 0
    output = {
        "execution_mode": session.runtime.execution_mode,
        "source_receipts": session.receipts,
        "schema_valid": True,
        "admission_passed": admission_passed,
        "jurisdiction": "KR",
        "as_of_date": as_of_date,
        "verification_assurance": (
            "Official law.go.kr records were retrieved live and matched structurally. "
            "Legal relevance and final use still require human review."
        ),
        "manual_review_required": True,
        "permitted_output": (
            "verified-citations-draft" if admission_passed else "no-citations-admitted"
        ),
        "verified_count": verified_count,
        "blocked_count": blocked_count,
        "citations": results,
    }
    match session.runtime.execution_mode:
        case "official-live":
            pass
        case "synthetic-fixture":
            output.update(
                verification_mode="synthetic-fixture",
                fixture_contract_passed=admission_passed,
                admission_passed=False,
                permitted_output="fixture-validation-only",
                verification_assurance="Synthetic matching contract only; no live official record was retrieved.",
                matched_count=verified_count,
            )
            for item in results:
                if item["status"] == "verified-official-live-match":
                    item["status"] = "synthetic-fixture-match"
                    item.pop("verified_citation", None)
                    item.pop("source_url", None)
        case unreachable:
            assert_never(unreachable)
    return session.protect(output)


def _load_json(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds maximum byte size")
    value = strict_json_loads(raw)
    if not isinstance(value, Mapping):
        raise ValueError("input must be a JSON object")
    return value


def _fixture_opener(responses: Mapping[str, Any]) -> Callable[..., Any]:
    class Response:
        headers = {"Content-Type": "application/json"}
        status = 200

        def __init__(self, payload: Any):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, *_):
            return json.dumps(self.payload, ensure_ascii=False).encode()

    def opener(request, timeout=0):
        parsed = urlsplit(request.full_url)
        query = parse_qs(parsed.query)
        target = query.get("target", [""])[0]
        if parsed.path.endswith("lawSearch.do") and target == "eflaw":
            key = "law_search"
        elif parsed.path.endswith("lawService.do") and target == "eflawjosub":
            key = "law_detail"
        elif parsed.path.endswith("lawService.do") and target == "prec":
            key = "precedent_detail"
        elif parsed.path.endswith("lawSearch.do") and target == "prec":
            key = "precedent_search"
        else:
            raise ValueError("fixture request is not supported")
        if key not in responses:
            raise ValueError("fixture response is missing")
        return Response(responses[key])

    return opener


def _fixture_result(path: Path) -> dict[str, Any]:
    fixture = _load_json(path)
    _exact_fields(fixture, frozenset({"input", "responses"}), "fixture")
    responses = fixture["responses"]
    if not isinstance(responses, Mapping):
        raise ValueError("fixture responses must be an object")
    # Only this in-memory synthetic registry is reviewed; the catalog stays disabled.
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    policy = next(
        item for item in catalog["source_policies"] if item["id"] == POLICY_ID
    )
    evidence = "https://www.law.go.kr/synthetic-fixture-only"
    policy.update(
        enabled=True,
        review={
            "reviewed_on": "2026-09-01",
            "expires_on": "2026-10-01",
            "evidence_urls": [evidence],
        },
        robots={"status": "documented-api-exemption", "evidence_url": evidence},
        terms={"status": "allowed", "url": evidence},
        rate_limit={
            "status": "reviewed",
            "requests": 1000,
            "per_seconds": 60,
            "burst": 1000,
            "max_wait_seconds": 0,
        },
        response={
            "status": "reviewed",
            "max_bytes": 2000000,
            "media_types": ["application/json"],
        },
        license={
            "status": "reviewed",
            "url": evidence,
            "allowed_output_modes": ["projected-records", "link-only"],
            "redistribution": "link-only",
        },
    )
    registry = SourcePolicyRegistry.from_catalog(catalog, on_date=date(2026, 9, 6))
    selected = next(item for item in registry.policies if item.id == POLICY_ID)

    def reject_wait(_seconds: float) -> None:
        raise ReadOnlyHttpError("budget-exhausted")

    with TemporaryDirectory(prefix="kgov-legal-fixture-") as directory:
        state = PolicyState(
            Path(directory) / "state.sqlite3", clock=lambda: 1000.0, sleeper=reject_wait
        )
        enforcer = HttpPolicyEnforcer(
            registry,
            state,
            HttpTransport(_fixture_opener(responses), lambda _host: ["1.1.1.1"]),
        )
        return verify_citations(
            fixture["input"],
            runtime=LegalRuntime(selected, enforcer, "synthetic-fixture"),
        )


class _ArgumentParser(argparse.ArgumentParser):
    """Keep argparse's validation without reflecting rejected argument values."""

    def error(self, _message: str) -> NoReturn:
        self.exit(2, "ERROR invalid command-line arguments\n")


def main() -> int:
    parser = _ArgumentParser(description="Search and verify Korean legal citations")
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixture-path", type=Path)
    parser.add_argument("--search-precedent", action="store_true")
    parser.add_argument("--search-law", action="store_true")
    parser.add_argument("--precedent-id")
    parser.add_argument("--param", action="append", default=[])
    args = parser.parse_args()
    modes = sum(
        (
            args.fixture,
            args.search_precedent,
            args.search_law,
            args.precedent_id is not None,
            args.path is not None,
        )
    )
    if modes != 1:
        parser.error("choose exactly one verification, fixture, search, or detail mode")
    try:
        if args.fixture:
            path = args.fixture_path or (
                ROOT
                / "tests/fixtures/capabilities/korean-legal-citation-verification.json"
            )
            result = _fixture_result(path)
        elif args.search_precedent:
            result = search_precedents(parse_params(args.param))
        elif args.search_law:
            result = search_laws(parse_params(args.param))
        elif args.precedent_id is not None:
            result = get_precedent(args.precedent_id)
        else:
            result = verify_citations(_load_json(args.path))
    except ReadOnlyHttpError as exc:
        error = {"error": exc.status, "source_receipts": [], "failed_call": None}
        match exc:
            case LegalExecutionError():
                error.update(
                    source_receipts=list(exc.source_receipts),
                    failed_call=exc.failed_call,
                )
            case ReadOnlyHttpError():
                pass
            case unreachable:
                assert_never(unreachable)
        print(json.dumps(error, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        match exc.status:
            case "invalid-request":
                return 2
            case (
                "policy-disabled"
                | "policy-expired"
                | "robots-denied"
                | "terms-unverified"
                | "license-unverified"
                | "budget-exhausted"
            ):
                return 3
            case (
                "response-invalid"
                | "upstream-403-manual"
                | "upstream-429-manual"
                | "upstream-unavailable"
            ):
                return 4
            case unreachable:
                assert_never(unreachable)
    except (OSError, ValueError, RuntimeError) as exc:
        print(
            json.dumps(
                {
                    "error": "legal-citation-verification-failed",
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.fixture:
        return 0 if result["fixture_contract_passed"] else 1
    if "admission_passed" in result and not result["admission_passed"]:
        return 1
    return 0


RUNTIME_CONTRACT_ID: Final[str] = "kgov/korean-legal-citation-verification/v1"
RUNTIME_OPERATION_IDS: Final[tuple[str, ...]] = ("kgov/korean-legal-citation-verification/verify-citations/v1",)


if __name__ == "__main__":
    raise SystemExit(main())
