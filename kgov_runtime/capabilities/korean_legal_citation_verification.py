from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qs, quote, quote_plus, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kgov_runtime.json_adapter import (  # noqa: E402
    JsonAdapterConfig,
    parse_params,
    query_json,
)
from kgov_runtime.redaction import contains_direct_identifier  # noqa: E402


LAW_SEARCH_CONFIG = JsonAdapterConfig(
    slug="korean-legal-citation-law-search",
    default_endpoint="https://www.law.go.kr/DRF/lawSearch.do",
    allowed_hosts=frozenset({"law.go.kr"}),
    default_params={"target": "eflaw", "type": "JSON"},
    credential_env="LAW_OC",
    credential_param="OC",
)
LAW_DETAIL_CONFIG = JsonAdapterConfig(
    slug="korean-legal-citation-law-detail",
    default_endpoint="https://www.law.go.kr/DRF/lawService.do",
    allowed_hosts=frozenset({"law.go.kr"}),
    default_params={"target": "eflawjosub", "type": "JSON"},
    credential_env="LAW_OC",
    credential_param="OC",
)
PRECEDENT_SEARCH_CONFIG = JsonAdapterConfig(
    slug="korean-legal-citation-precedent-search",
    default_endpoint="https://www.law.go.kr/DRF/lawSearch.do",
    allowed_hosts=frozenset({"law.go.kr"}),
    default_params={"target": "prec", "type": "JSON"},
    credential_env="LAW_OC",
    credential_param="OC",
)
PRECEDENT_DETAIL_CONFIG = JsonAdapterConfig(
    slug="korean-legal-citation-precedent-detail",
    default_endpoint="https://www.law.go.kr/DRF/lawService.do",
    allowed_hosts=frozenset({"law.go.kr"}),
    default_params={"target": "prec", "type": "JSON"},
    credential_env="LAW_OC",
    credential_param="OC",
)

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
HTML_TAG = re.compile(r"<[^>]{1,200}>")
LEADING_UNIT = re.compile(r"^(?:[①-⑳]|\d+[.)]?|[가-힣][.)])\s*")
CIRCLED_NUMBERS = {char: index for index, char in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", 1)}
KOREAN_ITEM_LETTERS = "가나다라마바사아자차카타파하"
LAW_SEARCH_PARAMS = frozenset({"query", "search", "LID", "display", "page"})
PRECEDENT_SEARCH_PARAMS = frozenset(
    {"query", "search", "display", "page", "sort", "date", "prncYd", "nb", "curt", "org", "JO"}
)


class OfficialNotFound(ValueError):
    pass


class OfficialAmbiguous(ValueError):
    pass


def _exact_fields(value: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
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


def _normalized_text(value: str) -> str:
    without_tags = HTML_TAG.sub(" ", html.unescape(value))
    normalized = unicodedata.normalize("NFKC", without_tags)
    normalized = normalized.replace("ㆍ", "·").replace("ᆞ", "·")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return LEADING_UNIT.sub("", normalized).strip()


def _quoted_text(value: Any) -> str:
    normalized = _required_string(value, "quoted_text", MAX_QUOTED_TEXT)
    if len(_normalized_text(normalized)) < MIN_QUOTED_TEXT:
        raise ValueError(f"quoted_text must contain at least {MIN_QUOTED_TEXT} normalized characters")
    return normalized


def _contains_identifier_after_normalization(value: Any) -> bool:
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKC", value)
        without_controls = "".join(
            character
            for character in normalized
            if not unicodedata.category(character).startswith("C")
            and unicodedata.category(character) not in {"Zl", "Zp"}
        )
        dash_normalized = without_controls.translate(
            str.maketrans({character: "-" for character in "‐‑‒–—―−"})
        )
        collapsed = re.sub(r"\s+", " ", dash_normalized).strip()
        tight_separators = re.sub(r"\s*([@.\-])\s*", r"\1", collapsed)
        compact = re.sub(r"[\s-]+", "", tight_separators)
        return any(
            contains_direct_identifier(candidate)
            for candidate in (
                normalized,
                without_controls,
                collapsed,
                tight_separators,
                compact,
            )
        )
    if isinstance(value, Mapping):
        return any(_contains_identifier_after_normalization(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_identifier_after_normalization(item) for item in value)
    return False


def _contains_disallowed_unicode(value: Any) -> bool:
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKC", value)
        return any(
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
            for character in normalized
        )
    if isinstance(value, Mapping):
        return any(_contains_disallowed_unicode(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_disallowed_unicode(item) for item in value)
    return False


def _ensure_credential_free(value: Any) -> None:
    credential = os.environ.get("LAW_OC")
    if not credential:
        return
    encoded = quote(credential, safe="")
    encoded_plus = quote_plus(credential)

    def lowercase_escapes(text: str) -> str:
        return re.sub(r"%[0-9A-Fa-f]{2}", lambda match: match.group(0).lower(), text)

    needles = {
        credential,
        encoded,
        encoded_plus,
        lowercase_escapes(encoded),
        lowercase_escapes(encoded_plus),
    }

    def contains(item: Any) -> bool:
        if isinstance(item, str):
            return any(needle and needle in item for needle in needles)
        if isinstance(item, Mapping):
            return any(contains(child) for child in item.values())
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
        if not isinstance(value, (str, int)):
            raise ValueError(f"{key} must be a scalar")
        if len(str(value)) > 300:
            raise ValueError(f"{key} exceeds maximum length")
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
    return "https://www.law.go.kr/" + quote("판례", safe="") + "/(" + quote(case_number, safe="") + ")"


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
    _ensure_credential_free(normalized)
    return normalized


def search_precedents(
    params: Mapping[str, Any] | None = None,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    validated = _validated_search_params(params, PRECEDENT_SEARCH_PARAMS)
    kwargs: dict[str, Any] = {"params": validated}
    if opener is not None:
        kwargs["opener"] = opener
    return _normalize_precedent_search(
        query_json(PRECEDENT_SEARCH_CONFIG, **kwargs),
        int(validated.get("display", 20)),
        int(validated.get("page", 1)),
    )


def _precedent_detail(
    serial_number: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    serial = _required_string(serial_number, "serial_number", 30)
    if SERIAL_NUMBER.fullmatch(serial) is None:
        raise ValueError("serial_number must be numeric")
    kwargs: dict[str, Any] = {"params": {"ID": serial}}
    if opener is not None:
        kwargs["opener"] = opener
    result = query_json(PRECEDENT_DETAIL_CONFIG, **kwargs)
    records = result.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], Mapping):
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
        official_serial = _required_string(envelope.get("판례정보일련번호"), "판례정보일련번호", 30)
        case_number = _citation_label(envelope.get("사건번호"), "사건번호")
        court = _citation_label(envelope.get("법원명"), "법원명")
        decision_date = _compact_date(envelope.get("선고일자"), "precedent decision date")
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
    if isinstance(message, str) and message.strip().startswith("일치하는 판례가 없습니다"):
        raise OfficialNotFound("official precedent not found")
    if isinstance(message, str):
        raise ValueError("official API error response")
    raise ValueError("official precedent detail envelope is invalid")


def get_precedent(
    serial_number: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    try:
        detail = _precedent_detail(serial_number, opener=opener)
    except OfficialNotFound:
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
            "records": [
                {
                    "serial_number": detail["serial_number"],
                    "case_number": detail["case_number"],
                    "court": detail["court"],
                    "decision_date": detail["decision_date"],
                    "available_text_fields": sorted(detail["texts"]),
                    "official_url": detail["official_url"],
                }
            ],
        }
    _ensure_credential_free(output)
    return output


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
    _ensure_credential_free(normalized)
    return normalized


def search_laws(
    params: Mapping[str, Any] | None = None,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    validated = _validated_search_params(params, LAW_SEARCH_PARAMS)
    kwargs: dict[str, Any] = {"params": validated}
    if opener is not None:
        kwargs["opener"] = opener
    normalized = _normalize_law_search(
        query_json(LAW_SEARCH_CONFIG, **kwargs),
        int(validated.get("display", 20)),
        int(validated.get("page", 1)),
    )
    normalized["count"] = len(normalized["records"])
    return normalized


def _select_law_version(
    candidate: Mapping[str, Any],
    as_of_date: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    all_records: list[dict[str, Any]] = []
    seen_records: set[tuple[str, str, str, str]] = set()
    page = 1
    expected_total: int | None = None
    while True:
        if page > MAX_LAW_HISTORY_PAGES:
            raise ValueError("official law history exceeds safe pagination limit")
        result = search_laws(
            {"LID": candidate["law_id"], "display": 100, "page": page},
            opener=opener,
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
    latest = {record["mst"]: record for record in matching if record["effective_date"] == latest_date}
    if len(latest) != 1:
        raise OfficialAmbiguous("official statute version is ambiguous")
    return next(iter(latest.values()))


def _label_number(value: Any, field: str) -> int:
    label = _required_string(value, field, 30)
    first = label[0]
    if first in CIRCLED_NUMBERS:
        return CIRCLED_NUMBERS[first]
    if first in KOREAN_ITEM_LETTERS:
        return KOREAN_ITEM_LETTERS.index(first) + 1
    matched = re.match(r"(\d+)", label)
    if matched is None:
        raise ValueError(f"official {field} schema is invalid")
    return int(matched.group(1))


def _select_numbered(records: Any, code: str, label_field: str, container: str) -> Mapping[str, Any]:
    items = _as_record_list(records, container)
    expected = int(code)
    selected = [item for item in items if _label_number(item.get(label_field), label_field) == expected]
    if len(selected) != 1:
        raise ValueError(f"official {container} locator is missing or ambiguous")
    return selected[0]


def _collect_text(node: Mapping[str, Any], keys: Iterable[str]) -> str:
    parts = [node[key] for key in keys if isinstance(node.get(key), str) and node[key].strip()]
    return " ".join(parts)


def _statute_unit(
    candidate: Mapping[str, Any],
    as_of_date: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    version = _select_law_version(candidate, as_of_date, opener=opener)
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
    kwargs: dict[str, Any] = {"params": params}
    if opener is not None:
        kwargs["opener"] = opener
    result = query_json(LAW_DETAIL_CONFIG, **kwargs)
    records = result.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], Mapping):
        raise ValueError("official statute detail envelope is invalid")
    law = records[0].get("법령")
    if not isinstance(law, Mapping):
        message = records[0].get("Law")
        if isinstance(message, str) and message.strip().startswith("일치하는 법령이 없습니다"):
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
        node = _select_numbered(node.get("항"), candidate["paragraph_code"], "항번호", "statute paragraphs")
        text = _collect_text(node, ("항내용",))
    else:
        text += " " + " ".join(
            _collect_text(item, ("항내용",)) for item in _as_record_list(node.get("항"), "statute paragraphs")
        ) if node.get("항") is not None else ""
    if candidate["item_code"] is not None:
        node = _select_numbered(node.get("호"), candidate["item_code"], "호번호", "statute items")
        text = _collect_text(node, ("호내용",))
    elif candidate["paragraph_code"] is not None and node.get("호") is not None:
        text += " " + " ".join(
            _collect_text(item, ("호내용",)) for item in _as_record_list(node.get("호"), "statute items")
        )
    if candidate["subitem_code"] is not None:
        node = _select_numbered(node.get("목"), candidate["subitem_code"], "목번호", "statute subitems")
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


def _validate_candidate(kind: str, value: Any) -> dict[str, Any]:
    if kind == "statute":
        value = _exact_fields(value, STATUTE_FIELDS, "candidate")
        law_id = _required_string(value.get("law_id"), "law_id", 6)
        article = _required_string(value.get("article_code"), "article_code", 6)
        if LAW_ID.fullmatch(law_id) is None:
            raise ValueError("law_id must be six digits")
        if ARTICLE_CODE.fullmatch(article) is None or article == "000000":
            raise ValueError("article_code must be a non-zero six-digit code")
        paragraph = _optional_code(value.get("paragraph_code"), "paragraph_code")
        item = _optional_code(value.get("item_code"), "item_code")
        subitem = _optional_code(value.get("subitem_code"), "subitem_code")
        if item is not None and paragraph is None:
            raise ValueError("item_code requires paragraph_code")
        if subitem is not None and item is None:
            raise ValueError("subitem_code requires item_code")
        if subitem is not None and int(subitem) > len(KOREAN_ITEM_LETTERS):
            raise ValueError("subitem_code exceeds supported Korean item letters")
        return {
            "law_name": _citation_label(value.get("law_name"), "law_name"),
            "law_id": law_id,
            "article_code": article,
            "paragraph_code": paragraph,
            "item_code": item,
            "subitem_code": subitem,
            "quoted_text": _quoted_text(value.get("quoted_text")),
        }
    value = _exact_fields(value, PRECEDENT_FIELDS, "candidate")
    serial = _required_string(value.get("serial_number"), "serial_number", 30)
    if SERIAL_NUMBER.fullmatch(serial) is None:
        raise ValueError("serial_number must be numeric")
    return {
        "serial_number": serial,
        "case_number": _citation_label(value.get("case_number"), "case_number"),
        "court": _citation_label(value.get("court"), "court"),
        "decision_date": _iso_date(value.get("decision_date"), "decision_date"),
        "quoted_text": _quoted_text(value.get("quoted_text")),
    }


def _verified_statute(citation_id: str, candidate: Mapping[str, Any], official: Mapping[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    if candidate["law_name"] != official["law_name"]:
        mismatches.append("law_name")
    if candidate["law_id"] != official["law_id"]:
        mismatches.append("law_id")
    if _normalized_text(candidate["quoted_text"]) not in _normalized_text(official["text"]):
        mismatches.append("quoted_text")
    base = {"citation_id": citation_id, "kind": "statute", "mismatched_fields": sorted(mismatches)}
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
    citation_id: str,
    candidate: Mapping[str, Any],
    official: Mapping[str, Any],
    as_of_date: str,
) -> dict[str, Any]:
    mismatches: list[str] = []
    for field in ("serial_number", "case_number", "court", "decision_date"):
        if candidate[field] != official[field]:
            mismatches.append(field)
    if official["decision_date"] > as_of_date:
        mismatches.append("decision_date_after_as_of_date")
    quote = _normalized_text(candidate["quoted_text"])
    matched_fields = [field for field, text in official["texts"].items() if quote in _normalized_text(text)]
    if not matched_fields:
        mismatches.append("quoted_text")
    base = {"citation_id": citation_id, "kind": "precedent", "mismatched_fields": sorted(set(mismatches))}
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
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    _exact_fields(payload, TOP_LEVEL_FIELDS, "input")
    as_of_date = _iso_date(payload.get("as_of_date"), "as_of_date")
    if payload.get("jurisdiction") != "KR":
        raise ValueError("jurisdiction must be KR")
    if payload.get("input_scope") != "redacted-citations-only":
        raise ValueError("input_scope must be redacted-citations-only")
    citations = payload.get("citations")
    if not isinstance(citations, list) or not citations or len(citations) > MAX_CITATIONS:
        raise ValueError(f"citations must contain 1 to {MAX_CITATIONS} items")
    if _contains_disallowed_unicode(payload):
        raise ValueError("input contains disallowed single-line Unicode controls")
    if _contains_identifier_after_normalization(payload):
        raise ValueError("input contains a supported direct identifier")
    validated: list[tuple[str, str, dict[str, Any]]] = []
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
        if kind not in {"statute", "precedent"}:
            raise ValueError("kind must be statute or precedent")
        candidate = _validate_candidate(kind, citation.get("candidate"))
        validated.append((citation_id, kind, candidate))
    results: list[dict[str, Any]] = []
    for citation_id, kind, candidate in validated:
        try:
            if kind == "statute":
                official = _statute_unit(candidate, as_of_date, opener=opener)
                result = _verified_statute(citation_id, candidate, official)
            else:
                official = _precedent_detail(candidate["serial_number"], opener=opener)
                result = _verified_precedent(citation_id, candidate, official, as_of_date)
        except OfficialNotFound:
            result = {
                "citation_id": citation_id,
                "kind": kind,
                "status": "official-source-not-found",
                "mismatched_fields": ["official_source"],
            }
        except OfficialAmbiguous:
            result = {
                "citation_id": citation_id,
                "kind": kind,
                "status": "ambiguous-candidates-manual-selection-required",
                "mismatched_fields": ["official_source"],
            }
        results.append(result)
    verified_count = sum(item["status"] == "verified-official-live-match" for item in results)
    blocked_count = len(results) - verified_count
    admission_passed = blocked_count == 0
    output = {
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
    _ensure_credential_free(output)
    return output


def _load_json(path: Path) -> Mapping[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds maximum byte size")
    value = json.loads(raw.decode("utf-8"))
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
    previous = os.environ.get("LAW_OC")
    os.environ["LAW_OC"] = "fixture-credential"
    try:
        live_shape = verify_citations(fixture["input"], opener=_fixture_opener(responses))
        contract_passed = live_shape["admission_passed"]
        citations = []
        for item in live_shape["citations"]:
            transformed = dict(item)
            if transformed["status"] == "verified-official-live-match":
                transformed["status"] = "synthetic-fixture-match"
                transformed.pop("verified_citation", None)
                transformed.pop("source_url", None)
            citations.append(transformed)
        return {
            "schema_valid": live_shape["schema_valid"],
            "verification_mode": "synthetic-fixture",
            "fixture_contract_passed": contract_passed,
            "admission_passed": False,
            "jurisdiction": live_shape["jurisdiction"],
            "as_of_date": live_shape["as_of_date"],
            "verification_assurance": (
                "Synthetic fixture transport and matching contract only; no live official "
                "record was retrieved."
            ),
            "manual_review_required": True,
            "permitted_output": "fixture-validation-only",
            "matched_count": live_shape["verified_count"],
            "blocked_count": live_shape["blocked_count"],
            "citations": citations,
        }
    finally:
        if previous is None:
            os.environ.pop("LAW_OC", None)
        else:
            os.environ["LAW_OC"] = previous


def main() -> int:
    parser = argparse.ArgumentParser(description="Search and verify Korean legal citations")
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
                ROOT / "tests/fixtures/capabilities/korean-legal-citation-verification.json"
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
    except Exception as exc:
        print(
            json.dumps(
                {"error": "legal-citation-verification-failed", "error_type": type(exc).__name__},
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


if __name__ == "__main__":
    raise SystemExit(main())
