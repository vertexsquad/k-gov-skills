"""Legal accuracy and policy-bound retrieval regressions.

# noqa: SIZE_OK -- Issue #31 owns exactly one legal test file; the accuracy and
# enforced retrieval regression matrix cannot be split outside that ownership.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from dataclasses import replace
from contextlib import redirect_stderr, redirect_stdout
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, quote, quote_plus, urlsplit
from unittest.mock import patch

from kgov_runtime.http import HttpPolicyEnforcer, HttpTransport, ReadOnlyHttpError
from kgov_runtime.policy_state import PolicyState
from kgov_runtime.source_policy import SourcePolicyRegistry
from tests.test_read_only_http import Response


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = (
    REPO_ROOT
    / "kgov_runtime"
    / "capabilities"
    / "korean_legal_citation_verification.py"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "capabilities"
    / "korean-legal-citation-verification.json"
)


def reviewed_registry(policy_id: str = "law-go-kr-drf-api") -> SourcePolicyRegistry:
    """Use real registered operations with explicitly synthetic reviewed policy."""
    catalog = json.loads((REPO_ROOT / "catalog/domain-skills.json").read_text())
    policy = next(
        item for item in catalog["source_policies"] if item["id"] == policy_id
    )
    origin = policy["scope"]["origins"][0]
    policy.update(
        enabled=True,
        review={
            "reviewed_on": "2026-09-01",
            "expires_on": "2026-10-01",
            "evidence_urls": [origin + "/synthetic-review"],
        },
        robots={"status": "required"},
        terms={"status": "allowed", "url": origin + "/synthetic-terms"},
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
            "media_types": [
                "application/json",
                "text/html",
                "application/xhtml+xml",
                "application/pdf",
                "image/png",
            ],
        },
        license={
            "status": "reviewed",
            "url": origin + "/synthetic-license",
            "allowed_output_modes": ["projected-records", "link-only"],
            "redistribution": "link-only",
        },
    )
    if policy_id == "law-go-kr-drf-api":
        policy["robots"] = {
            "status": "documented-api-exemption",
            "evidence_url": origin + "/synthetic-api-review",
        }
    return SourcePolicyRegistry.from_catalog(catalog, on_date=date(2026, 9, 6))


class _Response:
    headers = {"Content-Type": "application/json"}
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, *_):
        return json.dumps(self.payload, ensure_ascii=False).encode()


def _load_adapter():
    spec = importlib.util.spec_from_file_location(
        "legal_citation_adapter", ADAPTER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = _load_adapter()

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.registry = reviewed_registry()
        self.state = PolicyState(
            Path(self.directory.name) / "policy.sqlite3",
            clock=lambda: 1000.0,
            sleeper=self.fail,
        )
        self.prec_search = {
            "PrecSearch": {
                "totalCnt": "2",
                "prec": [
                    {
                        "판례일련번호": "999999",
                        "사건번호": "2026다12345",
                        "법원명": "대법원",
                        "선고일자": "2026. 1. 15.",
                        "사건명": "person@example.com 손해배상",
                        "판례상세링크": "/DRF/lawService.do?OC=fixture-secret&target=prec&ID=999999",
                    },
                    {
                        "판례일련번호": "888888",
                        "사건번호": "2025다77777",
                        "법원명": "대법원",
                        "선고일자": "2025. 12. 1.",
                    },
                ],
            }
        }
        self.prec_detail = {
            "PrecService": {
                "판례정보일련번호": "999999",
                "사건명": "person@example.com 손해배상",
                "사건번호": "2026다12345",
                "법원명": "대법원",
                "선고일자": "20260115",
                "판시사항": "공식 판례의 충분히 긴 판시사항입니다.<br/>두 번째 문장입니다.",
                "판결요지": "공식 판례의 충분히 긴 판결요지입니다.",
                "판례내용": "연락처 010-1234-5678이 들어간 원문은 결과로 출력하지 않습니다.",
            }
        }
        self.law_search = {
            "LawSearch": {
                "totalCnt": "3",
                "law": [
                    {
                        "법령명한글": "합성법률",
                        "법령ID": "000001",
                        "법령일련번호": "200002",
                        "시행일자": "20270101",
                        "현행연혁코드": "시행예정",
                        "법령상세링크": "/DRF/lawService.do?OC=fixture-secret&target=eflaw&MST=200002",
                    },
                    {
                        "법령명한글": "합성법률",
                        "법령ID": "000001",
                        "법령일련번호": "100001",
                        "시행일자": "20260101",
                        "현행연혁코드": "현행",
                    },
                    {
                        "법령명한글": "합성법률 시행령",
                        "법령ID": "000002",
                        "법령일련번호": "100002",
                        "시행일자": "20260101",
                        "현행연혁코드": "현행",
                    },
                ],
            }
        }
        self.law_detail = {
            "법령": {
                "법령키": "0000012026010100001",
                "기본정보": {
                    "법령명_한글": "합성법률",
                    "법령ID": "000001",
                    "시행일자": "20260101",
                    "전화번호": "010-1234-5678",
                },
                "조문": {
                    "조문단위": [
                        {"조문번호": "1", "조문키": "0001000", "조문여부": "전문"},
                        {
                            "조문번호": "1",
                            "조문키": "0001001",
                            "조문여부": "조문",
                            "조문내용": "제1조(합성 목적)",
                            "항": [
                                {
                                    "항번호": "① ",
                                    "항내용": "① 첫 번째 항의 서로 다른 공식 내용입니다.",
                                },
                                {
                                    "항번호": "② ",
                                    "항내용": "② 두 번째 항의 충분히 긴 공식 내용입니다.",
                                    "호": [
                                        {
                                            "호번호": "1. ",
                                            "호내용": "1. 검증 대상인 충분히 긴 공식 조문 내용입니다.",
                                        },
                                        {
                                            "호번호": "2. ",
                                            "호내용": "2. 목 단위 검증을 포함하는 공식 조문입니다.",
                                            "목": [
                                                {
                                                    "목번호": "가. ",
                                                    "목내용": "가. 첫 번째 목의 공식 내용입니다.",
                                                },
                                                {
                                                    "목번호": "나. ",
                                                    "목내용": "나. 두 번째 목의 공식 내용입니다.",
                                                },
                                                {
                                                    "목번호": "다. ",
                                                    "목내용": "다. 세 번째 목의 충분히 긴 공식 내용입니다.",
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ]
                },
            }
        }
        self.valid = {
            "as_of_date": "2026-07-20",
            "jurisdiction": "KR",
            "input_scope": "redacted-citations-only",
            "citations": [
                {
                    "citation_id": "LAW1",
                    "kind": "statute",
                    "candidate": {
                        "law_name": "합성법률",
                        "law_id": "000001",
                        "article_code": "000100",
                        "paragraph_code": "0002",
                        "item_code": "0001",
                        "subitem_code": None,
                        "quoted_text": "검증 대상인 충분히 긴 공식 조문 내용입니다.",
                    },
                },
                {
                    "citation_id": "PREC1",
                    "kind": "precedent",
                    "candidate": {
                        "serial_number": "999999",
                        "case_number": "2026다12345",
                        "court": "대법원",
                        "decision_date": "2026-01-15",
                        "quoted_text": "공식 판례의 충분히 긴 판시사항입니다. 두 번째 문장입니다.",
                    },
                },
            ],
        }

    def opener(self, request, timeout=0):
        query = parse_qs(urlsplit(request.full_url).query)
        target = query["target"][0]
        path = urlsplit(request.full_url).path
        if path.endswith("lawSearch.do") and target == "prec":
            return _Response(self.prec_search)
        if path.endswith("lawSearch.do") and target == "eflaw":
            return _Response(self.law_search)
        if path.endswith("lawService.do") and target == "prec":
            serial = query.get("ID", [""])[0]
            if serial == "000000":
                return _Response(
                    {"Law": "일치하는 판례가 없습니다. 판례명을 확인하여 주십시오."}
                )
            return _Response(self.prec_detail)
        if path.endswith("lawService.do") and target == "eflawjosub":
            return _Response(self.law_detail)
        raise AssertionError(request.full_url)

    def runtime(self, opener=None):
        return self.adapter.LegalRuntime(
            next(
                policy
                for policy in self.registry.policies
                if policy.id == "law-go-kr-drf-api"
            ),
            HttpPolicyEnforcer(
                self.registry,
                self.state,
                HttpTransport(opener or self.opener, lambda _host: ["1.1.1.1"]),
            ),
            "official-live",
        )

    def test_four_call_kinds_receive_registered_operation_receipts(self) -> None:
        # Given an offline transport beneath the real enforcer and a reviewed policy.
        runtime = self.runtime()
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            # When each public retrieval surface is exercised.
            results = [
                self.adapter.search_laws(runtime=runtime),
                self.adapter.search_precedents({"display": 2}, runtime=runtime),
                self.adapter.get_precedent("999999", runtime=runtime),
                self.adapter.verify_citations(self.valid, runtime=runtime),
            ]
        # Then every completed fetch is attributed without inventing operations.
        receipts = [
            receipt for result in results for receipt in result["source_receipts"]
        ]
        self.assertEqual(
            [
                "law-search",
                "precedent-search",
                "precedent-detail",
                "law-search",
                "law-detail",
                "precedent-detail",
            ],
            [item["call_kind"] for item in receipts],
        )
        for item in receipts:
            self.assertEqual(
                "kgov/korean-legal-citation-verification/verify-citations/v1",
                item["source_receipt"]["operation_id"],
            )
            self.assertEqual(
                runtime.policy.digest, item["source_receipt"]["policy_digest"]
            )
            self.assertEqual(
                runtime.policy.revision, item["source_receipt"]["policy_revision"]
            )
            self.assertNotIn("?", item["endpoint"])

    def test_live_official_statute_and_precedent_are_admitted(self) -> None:
        self.assertEqual(
            self.adapter._normalized_text("개인정보의 수집·이용 목적"),
            self.adapter._normalized_text("  1. 개인정보의 수집ㆍ이용 목적  "),
        )
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.verify_citations(
                self.valid, runtime=self.runtime(self.opener)
            )

        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["admission_passed"])
        self.assertEqual(2, result["verified_count"])
        self.assertEqual(0, result["blocked_count"])
        self.assertEqual(
            ["verified-official-live-match", "verified-official-live-match"],
            [item["status"] for item in result["citations"]],
        )
        self.assertEqual(
            "합성법률 제1조 제2항 제1호", result["citations"][0]["verified_citation"]
        )
        self.assertIn("lsiSeq=100", result["citations"][0]["source_url"])
        self.assertIn("joNo=0001", result["citations"][0]["source_url"])
        self.assertEqual(
            "대법원 2026-01-15 선고 2026다12345 판결",
            result["citations"][1]["verified_citation"],
        )
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("quoted_text", serialized)
        self.assertNotIn("공식 판례의", serialized)
        self.assertNotIn("010-1234-5678", serialized)
        self.assertNotIn("fixture-secret", serialized)

        subitem = copy.deepcopy(self.valid)
        subitem["citations"] = [subitem["citations"][0]]
        candidate = subitem["citations"][0]["candidate"]
        candidate["item_code"] = "0002"
        candidate["subitem_code"] = "0003"
        candidate["quoted_text"] = "세 번째 목의 충분히 긴 공식 내용입니다."

        def subitem_opener(request, timeout=0):
            query = parse_qs(urlsplit(request.full_url).query)
            if query.get("target") == ["eflawjosub"]:
                self.assertEqual(["000200"], query.get("HANG"))
                self.assertEqual(["000200"], query.get("HO"))
                self.assertEqual(["다"], query.get("MOK"))
            return self.opener(request, timeout)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            subitem_result = self.adapter.verify_citations(
                subitem, runtime=self.runtime(subitem_opener)
            )
        self.assertTrue(subitem_result["admission_passed"])
        self.assertTrue(
            subitem_result["citations"][0]["verified_citation"].endswith("다목")
        )

    def test_caller_supplied_official_record_is_rejected(self) -> None:
        fabricated = copy.deepcopy(self.valid)
        fabricated["citations"][0]["official"] = {
            "law_name": "존재하지않는법",
            "text": "서로 맞춘 가짜 원문입니다.",
        }
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.adapter.verify_citations(fabricated, runtime=self.runtime(self.opener))

    def test_wrong_locator_quote_and_case_metadata_are_blocked(self) -> None:
        wrong = copy.deepcopy(self.valid)
        wrong["citations"][0]["candidate"]["quoted_text"] = (
            "첫 번째 항의 서로 다른 공식 내용입니다."
        )
        wrong["citations"][1]["candidate"]["case_number"] = "2099다99999"
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.verify_citations(
                wrong, runtime=self.runtime(self.opener)
            )

        self.assertFalse(result["admission_passed"])
        self.assertEqual(0, result["verified_count"])
        self.assertEqual(2, result["blocked_count"])
        self.assertIn("quoted_text", result["citations"][0]["mismatched_fields"])
        self.assertIn("case_number", result["citations"][1]["mismatched_fields"])
        self.assertNotIn("verified_citation", result["citations"][0])

    def test_not_found_and_future_decision_fail_admission(self) -> None:
        payload = copy.deepcopy(self.valid)
        payload["citations"] = [payload["citations"][1]]
        payload["citations"][0]["candidate"]["serial_number"] = "000000"
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            missing = self.adapter.verify_citations(
                payload, runtime=self.runtime(self.opener)
            )
        self.assertFalse(missing["admission_passed"])
        self.assertEqual("official-source-not-found", missing["citations"][0]["status"])

        statute_only = copy.deepcopy(self.valid)
        statute_only["citations"] = [statute_only["citations"][0]]

        def law_not_found(request, timeout=0):
            parsed = urlsplit(request.full_url)
            query = parse_qs(parsed.query)
            if parsed.path.endswith("lawSearch.do") and query.get("target") == [
                "eflaw"
            ]:
                return _Response({"LawSearch": {"totalCnt": "0", "law": None}})
            return self.opener(request, timeout)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            missing_law = self.adapter.verify_citations(
                statute_only, runtime=self.runtime(law_not_found)
            )
        self.assertFalse(missing_law["admission_passed"])
        self.assertEqual(
            "official-source-not-found", missing_law["citations"][0]["status"]
        )

        future_payload = copy.deepcopy(self.valid)
        future_payload["citations"] = [future_payload["citations"][1]]
        future = copy.deepcopy(self.prec_detail)
        future["PrecService"]["선고일자"] = "20990101"

        def future_opener(request, timeout=0):
            query = parse_qs(urlsplit(request.full_url).query)
            if query.get("target") == ["prec"]:
                return _Response(future)
            return self.opener(request, timeout)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.verify_citations(
                future_payload, runtime=self.runtime(future_opener)
            )
        self.assertFalse(result["admission_passed"])
        self.assertIn(
            "decision_date_after_as_of_date",
            result["citations"][0]["mismatched_fields"],
        )

    def test_search_requires_manual_selection_and_never_echoes_pii_or_credential(
        self,
    ) -> None:
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.search_precedents(
                {"nb": "2026다12345", "display": 2}, runtime=self.runtime(self.opener)
            )
        self.assertEqual(
            "ambiguous-candidates-manual-selection-required", result["selection_status"]
        )
        self.assertTrue(result["manual_selection_required"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("fixture-secret", serialized)
        self.assertNotIn("person@example.com", serialized)
        self.assertNotIn("사건명", serialized)
        self.assertNotIn("raw", result)

        inconsistent = copy.deepcopy(self.prec_search)
        inconsistent["PrecSearch"]["totalCnt"] = "1"

        def inconsistent_opener(request, timeout=0):
            return _Response(inconsistent)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.search_precedents(
                    {"display": 1}, runtime=self.runtime(inconsistent_opener)
                )

        short_precedent_page = copy.deepcopy(self.prec_search)
        short_precedent_page["PrecSearch"]["prec"] = short_precedent_page["PrecSearch"][
            "prec"
        ][:1]

        def short_precedent_page_opener(request, timeout=0):
            return _Response(short_precedent_page)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.search_precedents(
                    {"display": 100}, runtime=self.runtime(short_precedent_page_opener)
                )

        inconsistent_law = copy.deepcopy(self.law_search)
        inconsistent_law["LawSearch"]["totalCnt"] = "1"

        def inconsistent_law_opener(request, timeout=0):
            return _Response(inconsistent_law)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.search_laws(
                    {"display": 1}, runtime=self.runtime(inconsistent_law_opener)
                )

        short_law_page = copy.deepcopy(self.law_search)
        short_law_page["LawSearch"]["totalCnt"] = "2"
        short_law_page["LawSearch"]["law"] = short_law_page["LawSearch"]["law"][:1]

        def short_law_page_opener(request, timeout=0):
            return _Response(short_law_page)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.search_laws(
                    {"display": 100}, runtime=self.runtime(short_law_page_opener)
                )

        history_records = []
        for index in range(100):
            record = copy.deepcopy(self.law_search["LawSearch"]["law"][0])
            record["법령일련번호"] = str(1000 + index)
            record["시행일자"] = (date(2025, 1, 1) + timedelta(days=index)).strftime(
                "%Y%m%d"
            )
            history_records.append(record)

        def duplicate_history_opener(request, timeout=0):
            query = parse_qs(urlsplit(request.full_url).query)
            page = int(query.get("page", ["1"])[0])
            envelope = copy.deepcopy(self.law_search)
            envelope["LawSearch"]["totalCnt"] = "101"
            envelope["LawSearch"]["law"] = (
                history_records if page == 1 else [history_records[0]]
            )
            return _Response(envelope)

        statute_only = copy.deepcopy(self.valid)
        statute_only["citations"] = [statute_only["citations"][0]]
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.verify_citations(
                    statute_only, runtime=self.runtime(duplicate_history_opener)
                )

        reflected = copy.deepcopy(self.law_search)
        reflected["LawSearch"]["law"][0]["현행연혁코드"] = "fixture-secret"

        def reflected_opener(request, timeout=0):
            return _Response(reflected)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.search_laws(
                    {"display": 100}, runtime=self.runtime(reflected_opener)
                )

        reflected["LawSearch"]["law"][0]["현행연혁코드"] = "fixture%2fsecret"
        with patch.dict(os.environ, {"LAW_OC": "fixture/secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.search_laws(
                    {"display": 100}, runtime=self.runtime(reflected_opener)
                )

    def test_search_cli_rejects_invalid_total_counts_before_receipts(self) -> None:
        # Given malformed counts with coherent coerced pages, plus count mismatches.
        cases = (
            (True, 1), (False, 0), (1.5, 1), (2.5, 2), (1.0, 1), (0.0, 0),
            (-0.5, 0), (-1, 0), ("-1", 0), ("+1", 1), ("-0", 0),
            (" 1", 1), ("1 ", 1), ("١", 1), ("１", 1), ("0_1", 1),
            ("1.0", 1), ("1e0", 1), ("", 0), (None, 0), ([], 0), ({}, 0),
            ("SYNTHETIC_COUNT_MARKER", 0),
            (0, 1), (2, 1), ("2", 1), (1, 0), ("1", 2),
        )
        for kind, envelope, key in (
            ("law", self.law_search["LawSearch"], "law"),
            ("precedent", self.prec_search["PrecSearch"], "prec"),
        ):
            records = envelope[key]
            for value, record_count in cases:
                with self.subTest(kind=kind, value=value, record_count=record_count):
                    envelope.update(totalCnt=value)
                    envelope[key] = records[:record_count]
                    with (
                        patch.object(sys, "argv", [str(ADAPTER_PATH), f"--search-{kind}"]),
                        patch.object(self.adapter, "_live_runtime", return_value=self.runtime()),
                        patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                        redirect_stdout(io.StringIO()) as output,
                        redirect_stderr(io.StringIO()) as error,
                    ):
                        # When the actual enforcer projects the response through the CLI.
                        exit_code = self.adapter.main()
                    # Then no successful output, receipt or reflected count escapes.
                    self.assertEqual(4, exit_code)
                    self.assertEqual("", output.getvalue())
                    self.assertEqual(
                        {
                            "error": "response-invalid",
                            "source_receipts": [],
                            "failed_call": {
                                "call_kind": f"{kind}-search",
                                "endpoint": "https://www.law.go.kr/DRF/lawSearch.do",
                                "citation_id": None,
                                "page": 1,
                            },
                        },
                        json.loads(error.getvalue()),
                    )

    def test_search_cli_accepts_integer_and_ascii_decimal_total_counts(self) -> None:
        # Given valid zero, integer and decimal-string counts, including later pages.
        cases = (
            (0, 1, 0), ("0", 1, 0), ("000", 1, 0),
            (1, 1, 1), ("1", 1, 1), ("01", 1, 1),
            (2, 1, 2), ("2", 1, 2),
            (3, 2, 1), ("3", 2, 1), (2, 2, 0),
        )
        for kind, envelope, key in (
            ("law", self.law_search["LawSearch"], "law"),
            ("precedent", self.prec_search["PrecSearch"], "prec"),
        ):
            records = envelope[key]
            for value, page, record_count in cases:
                with self.subTest(kind=kind, value=value, page=page):
                    envelope.update(totalCnt=value)
                    envelope[key] = records[:record_count]
                    with (
                        patch.object(sys, "argv", [
                            str(ADAPTER_PATH), f"--search-{kind}",
                            "--param", "display=2", "--param", f"page={page}",
                        ]),
                        patch.object(self.adapter, "_live_runtime", return_value=self.runtime()),
                        patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                        redirect_stdout(io.StringIO()) as output,
                        redirect_stderr(io.StringIO()) as error,
                    ):
                        # When the real CLI retrieves a coherent page through the enforcer.
                        exit_code = self.adapter.main()
                    # Then valid counts retain projected records and an allowed receipt.
                    self.assertEqual(0, exit_code, error.getvalue())
                    self.assertEqual("", error.getvalue())
                    result = json.loads(output.getvalue())
                    self.assertEqual(int(value), result["total_count"])
                    self.assertIs(type(result["total_count"]), int)
                    self.assertEqual(record_count, result["count"])
                    self.assertEqual(record_count, len(result["records"]))
                    self.assertEqual(1, len(result["source_receipts"]))
                    self.assertEqual(
                        "allowed", result["source_receipts"][0]["source_receipt"]["outcome"]
                    )

    def test_unicode_pii_and_output_controls_are_rejected(self) -> None:
        pii = copy.deepcopy(self.valid)
        pii["citations"][0]["candidate"]["law_name"] = "０１０－１２３４－５６７８"
        with self.assertRaisesRegex(ValueError, "direct identifier"):
            self.adapter.verify_citations(pii, runtime=self.runtime(self.opener))

        separator = copy.deepcopy(self.valid)
        separator["citations"][0]["candidate"]["law_name"] = "합성법률\u2028위조근거"
        with self.assertRaisesRegex(ValueError, "single-line"):
            self.adapter.verify_citations(separator, runtime=self.runtime(self.opener))

        bidi = copy.deepcopy(self.valid)
        bidi["citations"][1]["candidate"]["court"] = "대법원\u202e위조"
        with self.assertRaisesRegex(ValueError, "single-line"):
            self.adapter.verify_citations(bidi, runtime=self.runtime(self.opener))

        hidden_pii = copy.deepcopy(self.valid)
        hidden_pii["citations"][1]["candidate"]["quoted_text"] = (
            "연락처 010\u200b-1234-5678 포함된 충분히 긴 인용문입니다."
        )
        with self.assertRaisesRegex(ValueError, "Unicode"):
            self.adapter.verify_citations(hidden_pii, runtime=self.runtime(self.opener))

        for spaced_identifier in (
            "연락처 010  1234  5678 포함된 충분히 긴 인용문입니다.",
            "연락처 010 - 1234 - 5678 포함된 충분히 긴 인용문입니다.",
            "주민번호 900101  1234567 포함된 충분히 긴 인용문입니다.",
        ):
            spaced = copy.deepcopy(self.valid)
            spaced["citations"][1]["candidate"]["quoted_text"] = spaced_identifier
            with self.assertRaisesRegex(ValueError, "direct identifier"):
                self.adapter.verify_citations(spaced, runtime=self.runtime(self.opener))

    def test_official_schema_and_error_envelopes_fail_closed(self) -> None:
        def empty_detail(request, timeout=0):
            return _Response({"PrecService": {}})

        payload = copy.deepcopy(self.valid)
        payload["citations"] = [payload["citations"][1]]
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.verify_citations(
                    payload, runtime=self.runtime(empty_detail)
                )

        def api_error(request, timeout=0):
            return _Response({"Law": "인증값이 올바르지 않습니다."})

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ReadOnlyHttpError, "^response-invalid$"):
                self.adapter.verify_citations(payload, runtime=self.runtime(api_error))

    def test_not_found_receipt_is_retained_for_both_detail_kinds(self) -> None:
        # Given a recognized successful API not-found envelope, not an HTTP failure.
        for kind, message in (
            ("precedent", "일치하는 판례가 없습니다."),
            ("statute", "일치하는 법령이 없습니다."),
        ):
            with self.subTest(kind=kind):
                payload = copy.deepcopy(self.valid)
                payload["citations"] = [
                    item for item in payload["citations"] if item["kind"] == kind
                ]

                def opener(request, timeout=0):
                    if urlsplit(request.full_url).path.endswith("lawService.do"):
                        return _Response({"Law": message})
                    return self.opener(request, timeout)

                # When verification cannot locate the official unit.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime(opener)
                    )
                # Then admission is blocked but every completed lookup is evidenced.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(
                    "official-source-not-found", result["citations"][0]["status"]
                )
                self.assertEqual(
                    2 if kind == "statute" else 1, len(result["source_receipts"])
                )
                self.assertTrue(
                    all(
                        item["source_receipt"]["outcome"] == "allowed"
                        for item in result["source_receipts"]
                    )
                )

    def test_completed_receipts_survive_later_upstream_failure(self) -> None:
        # Given a successful statute followed by a denied precedent detail.
        def opener(request, timeout=0):
            if parse_qs(urlsplit(request.full_url).query)["target"] == ["prec"]:
                return Response(b"denied", status=403)
            return self.opener(request, timeout)

        # When the batch fails, it must not return partial admission.
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(self.adapter.LegalExecutionError) as raised,
        ):
            self.adapter.verify_citations(self.valid, runtime=self.runtime(opener))
        # Then only completed calls receive allowed receipts.
        self.assertEqual("upstream-403-manual", raised.exception.status)
        self.assertEqual(
            ["law-search", "law-detail"],
            [item["call_kind"] for item in raised.exception.source_receipts],
        )
        self.assertEqual("precedent-detail", raised.exception.failed_call["call_kind"])
        self.assertNotIn("fixture-secret", str(raised.exception))

    def test_all_history_pages_keep_ordered_receipts(self) -> None:
        # Given 101 unique eligible history records and two citations to the same law.
        payload = copy.deepcopy(self.valid)
        payload["citations"] = [
            payload["citations"][0],
            copy.deepcopy(payload["citations"][0]),
        ]
        payload["citations"][1]["citation_id"] = "LAW2"
        records = []
        for index in range(100):
            record = copy.deepcopy(self.law_search["LawSearch"]["law"][1])
            record["법령일련번호"] = str(300000 + index)
            record["시행일자"] = (date(2025, 1, 1) + timedelta(days=index)).strftime(
                "%Y%m%d"
            )
            records.append(record)
        records.append(self.law_search["LawSearch"]["law"][1])

        def opener(request, timeout=0):
            if urlsplit(request.full_url).path.endswith("lawSearch.do"):
                page = int(parse_qs(urlsplit(request.full_url).query)["page"][0])
                return _Response(
                    {
                        "LawSearch": {
                            "totalCnt": "101",
                            "law": records[(page - 1) * 100 : page * 100],
                        }
                    }
                )
            return self.opener(request, timeout)

        # When both citations retrieve the complete history independently.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(
                payload, runtime=self.runtime(opener)
            )
        # Then no page or repeated policy receipt is deduplicated.
        self.assertTrue(result["admission_passed"])
        self.assertEqual(
            [
                ("LAW1", "law-search", 1),
                ("LAW1", "law-search", 2),
                ("LAW1", "law-detail", None),
                ("LAW2", "law-search", 1),
                ("LAW2", "law-search", 2),
                ("LAW2", "law-detail", None),
            ],
            [
                (item["citation_id"], item["call_kind"], item["page"])
                for item in result["source_receipts"]
            ],
        )

    def test_same_date_versions_require_manual_selection(self) -> None:
        # Given two different versions at the latest eligible date.
        self.law_search["LawSearch"]["law"][0]["시행일자"] = "20260101"
        payload = dict(self.valid, citations=[self.valid["citations"][0]])
        # When verification selects history.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        # Then it never guesses or requests either detail.
        self.assertFalse(result["admission_passed"])
        self.assertEqual(
            "ambiguous-candidates-manual-selection-required",
            result["citations"][0]["status"],
        )
        self.assertEqual(
            ["law-search"], [item["call_kind"] for item in result["source_receipts"]]
        )

    def test_search_detail_identity_mismatch_fails_closed(self) -> None:
        # Given a detail from another law despite the selected search version.
        self.law_detail["법령"]["기본정보"]["법령ID"] = "000009"
        # When the detail is projected.
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(self.adapter.LegalExecutionError) as raised,
        ):
            self.adapter.verify_citations(self.valid, runtime=self.runtime())
        # Then only the successful search remains evidenced.
        self.assertEqual("response-invalid", raised.exception.status)
        self.assertEqual(1, len(raised.exception.source_receipts))

    def test_policy_denials_precede_credentials_dns_and_state(self) -> None:
        # Given each fail-closed policy decision on the exact registry-owned object.
        original = self.runtime().policy
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
                    original,
                    license=replace(
                        original.license, allowed_output_modes=("projected-records",)
                    ),
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
            with self.subTest(status=expected):
                registry = replace(
                    self.registry,
                    policies=tuple(
                        policy if item.id == policy.id else item
                        for item in self.registry.policies
                    ),
                )
                runtime = self.adapter.LegalRuntime(
                    policy,
                    HttpPolicyEnforcer(
                        registry, self.state, HttpTransport(self.fail, self.fail)
                    ),
                )
                # When retrieval is requested without consulting any credential/state.
                with (
                    patch.object(
                        self.adapter,
                        "build_url",
                        side_effect=AssertionError("credential"),
                    ),
                    patch.object(
                        self.state, "open", side_effect=AssertionError("state")
                    ),
                    self.assertRaises(ReadOnlyHttpError) as raised,
                ):
                    self.adapter.search_laws(runtime=runtime)
                # Then the stable policy reason wins before infrastructure.
                self.assertEqual(expected, raised.exception.status)

    def test_cloned_policy_is_rejected_before_credentials(self) -> None:
        # Given an equal but non-registry-owned policy object.
        runtime = self.runtime()
        runtime = replace(runtime, policy=replace(runtime.policy))
        # When retrieval attempts to bind that clone.
        with (
            patch.object(
                self.adapter, "build_url", side_effect=AssertionError("credential")
            ),
            self.assertRaises(ReadOnlyHttpError) as raised,
        ):
            self.adapter.search_laws(runtime=runtime)
        # Then equality is not mistaken for policy ownership.
        self.assertEqual("policy-disabled", raised.exception.status)

    def test_durable_budget_is_shared_across_call_kinds_and_reopened_state(
        self,
    ) -> None:
        # Given one exhausted durable slot from law search.
        original = self.runtime().policy
        policy = replace(
            original, rate_limit=replace(original.rate_limit, requests=1, burst=1)
        )
        registry = replace(
            self.registry,
            policies=tuple(
                policy if item.id == policy.id else item
                for item in self.registry.policies
            ),
        )
        runtime = self.adapter.LegalRuntime(
            policy,
            HttpPolicyEnforcer(
                registry, self.state, HttpTransport(self.opener, lambda _: ["1.1.1.1"])
            ),
        )
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            self.adapter.search_laws(runtime=runtime)
        reopened = PolicyState(
            Path(self.directory.name) / "policy.sqlite3",
            clock=lambda: 1000.0,
            sleeper=self.fail,
        )
        next_runtime = self.adapter.LegalRuntime(
            policy,
            HttpPolicyEnforcer(
                registry, reopened, HttpTransport(self.fail, lambda _: ["1.1.1.1"])
            ),
        )
        # When another call kind uses the same policy after reopening state.
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(ReadOnlyHttpError) as raised,
        ):
            self.adapter.get_precedent("999999", runtime=next_runtime)
        # Then it cannot mint a new capability/call-local budget.
        self.assertEqual("budget-exhausted", raised.exception.status)

    def test_transport_failures_do_not_retry_or_receive_receipts(self) -> None:
        # Given bounded wire failures, including decodable but invalid envelopes/media.
        cases = [
            (Response(b"denied", status=403), "upstream-403-manual"),
            (
                Response(b"limited", status=429, headers={"Retry-After": "60"}),
                "upstream-429-manual",
            ),
            (Response(b"missing", status=404), "upstream-unavailable"),
            (Response(b"failure", status=500), "upstream-unavailable"),
            (Response(b"{", media_type="application/json"), "response-invalid"),
            (Response(b"{}", media_type="application/pdf"), "response-invalid"),
            (
                Response(b"x" * 2000001, media_type="application/json"),
                "response-invalid",
            ),
            (
                Response(b"CAPTCHA", media_type="application/json"),
                "upstream-403-manual",
            ),
        ]
        for index, (response, expected) in enumerate(cases):
            with self.subTest(status=expected, index=index):
                opened = []

                def opener(request, timeout=0):
                    opened.append(request.full_url)
                    return response

                state = PolicyState(
                    Path(self.directory.name) / f"failure-{index}.sqlite3",
                    clock=lambda: 1000.0,
                    sleeper=self.fail,
                )
                runtime = self.runtime(opener)
                runtime = replace(
                    runtime,
                    enforcer=HttpPolicyEnforcer(
                        self.registry,
                        state,
                        HttpTransport(opener, lambda _: ["1.1.1.1"]),
                    ),
                )
                # When one source fetch fails.
                with (
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    self.assertRaises(self.adapter.LegalExecutionError) as raised,
                ):
                    self.adapter.search_laws(runtime=runtime)
                # Then no success receipt or retry conceals the failure.
                self.assertEqual(expected, raised.exception.status)
                self.assertEqual((), raised.exception.source_receipts)
                self.assertEqual(1, len(opened))

    def test_required_robots_denial_prevents_target_fetch(self) -> None:
        # Given a reviewed policy requiring robots and a disallowed DRF path.
        runtime = self.runtime()
        policy = replace(
            runtime.policy, robots=replace(runtime.policy.robots, status="required")
        )
        registry = replace(
            self.registry,
            policies=tuple(
                policy if item.id == policy.id else item
                for item in self.registry.policies
            ),
        )
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            return Response(
                b"User-agent: *\nDisallow: /DRF/\n", media_type="text/plain"
            )

        runtime = self.adapter.LegalRuntime(
            policy,
            HttpPolicyEnforcer(
                registry, self.state, HttpTransport(opener, lambda _: ["1.1.1.1"])
            ),
        )
        # When the legal search is attempted.
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(ReadOnlyHttpError) as raised,
        ):
            self.adapter.search_laws(runtime=runtime)
        # Then robots uses one reservation but no allowed source receipt.
        self.assertEqual("robots-denied", raised.exception.status)
        self.assertEqual(["https://www.law.go.kr/robots.txt"], opened)

    def test_disabled_live_modes_stop_before_state_and_credentials(self) -> None:
        # Given the unchanged disabled catalog and infrastructure tripwires.
        for args in (
            ["--search-law"],
            ["--search-precedent"],
            ["--precedent-id", "999999"],
        ):
            with (
                self.subTest(args=args),
                patch.object(sys, "argv", [str(ADAPTER_PATH), *args]),
                patch.object(
                    self.adapter, "PolicyState", side_effect=AssertionError("state")
                ),
                patch.object(
                    self.adapter, "build_url", side_effect=AssertionError("credential")
                ),
                patch("socket.getaddrinfo", side_effect=AssertionError("DNS")),
                redirect_stderr(io.StringIO()) as error,
            ):
                # When the real CLI parses a valid live request.
                exit_code = self.adapter.main()
            # Then disabled policy has the stable exit and no infrastructure effect.
            self.assertEqual(3, exit_code)
            self.assertEqual("policy-disabled", json.loads(error.getvalue())["error"])

    def test_cli_upstream_failure_emits_completed_receipts_and_exit_four(self) -> None:
        # Given a reviewed runtime whose source returns 429 exactly once.
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            return Response(b"limited", status=429)

        runtime = self.runtime(opener)
        with (
            patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
            patch.object(self.adapter, "_live_runtime", return_value=runtime),
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            redirect_stderr(io.StringIO()) as error,
            redirect_stdout(io.StringIO()) as output,
        ):
            # When the real parser and entrypoint execute under the injected enforcer.
            exit_code = self.adapter.main()
        # Then no admission is emitted and errors do not echo request credentials.
        self.assertEqual(4, exit_code)
        self.assertEqual("", output.getvalue())
        self.assertEqual("upstream-429-manual", json.loads(error.getvalue())["error"])
        self.assertNotIn("fixture-secret", error.getvalue())
        self.assertEqual(1, len(opened))

    def test_cli_partial_failure_redacts_credential_conflicting_citation_metadata(
        self,
    ) -> None:
        # Given a successful history fetch followed by 403 for citation LAW1.
        path = Path(self.directory.name) / "partial.json"
        path.write_text(json.dumps(self.valid), encoding="utf-8")
        opened = []

        def opener(request, timeout=0):
            opened.append(request.full_url)
            if urlsplit(request.full_url).path.endswith("lawService.do"):
                return Response(b"denied", status=403)
            return self.opener(request, timeout)

        runtime = self.runtime(opener)
        with (
            patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
            patch.object(self.adapter, "_live_runtime", return_value=runtime),
            patch.dict(os.environ, {"LAW_OC": "LAW1"}),
            redirect_stderr(io.StringIO()) as error,
            redirect_stdout(io.StringIO()) as output,
        ):
            # When the real CLI serializes its partial execution error.
            exit_code = self.adapter.main()
        # Then authentic receipt coordinates remain, but caller metadata cannot leak.
        self.assertEqual(4, exit_code)
        self.assertEqual("", output.getvalue())
        self.assertNotIn("LAW1", error.getvalue())
        result = json.loads(error.getvalue())
        self.assertEqual("upstream-403-manual", result["error"])
        self.assertEqual(2, len(opened))
        self.assertEqual(1, len(result["source_receipts"]))
        receipt = result["source_receipts"][0]
        self.assertIsNone(receipt["citation_id"])
        self.assertEqual("law-search", receipt["call_kind"])
        self.assertEqual(1, receipt["page"])
        self.assertEqual(
            runtime.policy.digest, receipt["source_receipt"]["policy_digest"]
        )
        self.assertEqual("allowed", receipt["source_receipt"]["outcome"])
        self.assertIsNone(result["failed_call"]["citation_id"])
        self.assertEqual("law-detail", result["failed_call"]["call_kind"])

    def test_cli_partial_failure_drops_trace_when_constant_fields_conflict(
        self,
    ) -> None:
        # Given a credential matching an allowed receipt value or a trace field name.
        path = Path(self.directory.name) / "partial.json"
        path.write_text(json.dumps(self.valid), encoding="utf-8")

        def opener(request, timeout=0):
            if urlsplit(request.full_url).path.endswith("lawService.do"):
                return Response(b"denied", status=403)
            return self.opener(request, timeout)

        runtime = self.runtime(opener)
        for marker in ("allowed", "call_kind"):
            with (
                self.subTest(marker=marker),
                patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
                patch.object(self.adapter, "_live_runtime", return_value=runtime),
                patch.dict(os.environ, {"LAW_OC": marker}),
                redirect_stderr(io.StringIO()) as error,
                redirect_stdout(io.StringIO()) as output,
            ):
                # When even immutable receipt fields cannot be safely serialized.
                exit_code = self.adapter.main()
            # Then a receipt collision fails at the shared boundary, before later calls.
            self.assertEqual(4, exit_code)
            self.assertEqual("", output.getvalue())
            self.assertNotIn(marker, error.getvalue())
            self.assertEqual(
                {
                    "error": "response-invalid",
                    "source_receipts": [],
                    "failed_call": None,
                },
                json.loads(error.getvalue()),
            )

    def test_fixture_error_serialization_does_not_read_credentials(self) -> None:
        # Given a synthetic fixture whose detail projection fails after a search.
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["responses"]["law_detail"] = {}
        path = Path(self.directory.name) / "invalid-fixture.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        with (
            patch.object(
                sys,
                "argv",
                [str(ADAPTER_PATH), "--fixture", "--fixture-path", str(path)],
            ),
            patch.object(self.adapter.os, "environ") as environment,
            redirect_stderr(io.StringIO()) as error,
            redirect_stdout(io.StringIO()) as output,
        ):
            environment.get.side_effect = lambda key, default=None: (
                self.fail("credential read") if key == "LAW_OC" else default
            )
            environment.__setitem__.side_effect = self.fail
            # When the real fixture CLI reports a failed projection.
            exit_code = self.adapter.main()
        # Then credential-free execution includes the error path, with no live evidence.
        self.assertEqual(4, exit_code)
        self.assertEqual("", output.getvalue())
        self.assertEqual(
            {"error": "response-invalid", "source_receipts": [], "failed_call": None},
            json.loads(error.getvalue()),
        )

    def test_precedent_identifiers_are_rejected_before_runtime(self) -> None:
        # Given numeric serials containing direct identifiers, including normalized digits.
        for serial in ("01012345678", "9001011234567", "０１０１２３４５６７８"):
            with (
                self.subTest(serial=serial),
                patch.object(
                    self.adapter, "_live_runtime", side_effect=AssertionError("runtime")
                ),
            ):
                # When standalone detail input is parsed.
                with self.assertRaises(ValueError):
                    self.adapter.get_precedent(serial)
                # Then a numeric shape is not enough to authorize transport.

    def test_cli_blocks_each_percent_escape_casing_in_reflected_credentials(
        self,
    ) -> None:
        # Given raw, URL and plus encodings with independently mixed hex case.
        credential = "SYNTHETIC/SECRET+VALUE X"
        quoted = quote(credential, safe="")
        plus_quoted = quote_plus(credential)
        reflections = (
            credential,
            *(
                encoded.replace("%2F", slash).replace("%2B", plus)
                for encoded in (quoted, plus_quoted)
                for slash in ("%2F", "%2f")
                for plus in ("%2B", "%2b")
            ),
        )
        runtime = self.runtime()
        for reflection in reflections:
            with self.subTest(reflection=reflection):
                self.law_search["LawSearch"]["law"][0]["법령명한글"] = reflection
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
                    patch.object(self.adapter, "_live_runtime", return_value=runtime),
                    patch.dict(os.environ, {"LAW_OC": credential}),
                    redirect_stderr(io.StringIO()) as error,
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When a successful official response is projected through the real CLI.
                    exit_code = self.adapter.main()
                # Then all encodings fail closed without returning the credential or trace.
                self.assertEqual(4, exit_code)
                self.assertEqual("", output.getvalue())
                self.assertNotIn(credential, error.getvalue())
                self.assertNotIn(reflection, error.getvalue())
                self.assertEqual(
                    {
                        "error": "response-invalid",
                        "source_receipts": [],
                        "failed_call": None,
                    },
                    json.loads(error.getvalue()),
                )

    def test_cli_blocks_single_layer_mixed_credential_spellings(self) -> None:
        # Given raw/default-safe/full/plus quoting and partial literal-encoded mixtures.
        credential = "SYNTHETIC/SECRET+VALUE X"
        spellings = (
            credential,
            quote(credential),
            quote(credential, safe=""),
            quote_plus(credential),
            "SYNTHETIC/SECRET%2bVALUE X",
            "SYNTHETIC%2fSECRET+VALUE X",
            "%53YNTHETIC/SECRET%2BVALUE X",
            "%53YNTHETIC%2fSECRET+VALUE+X",
        )
        runtime = self.runtime()
        for spelling in spellings:
            with self.subTest(spelling=spelling):
                self.law_search["LawSearch"]["law"][0]["법령명한글"] = spelling
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
                    patch.object(self.adapter, "_live_runtime", return_value=runtime),
                    patch.dict(os.environ, {"LAW_OC": credential}),
                    redirect_stdout(io.StringIO()) as output,
                    redirect_stderr(io.StringIO()) as error,
                ):
                    # When the real CLI projects the otherwise successful official page.
                    code = self.adapter.main()
                # Then one-layer equivalent credential spellings cannot escape.
                self.assertEqual(4, code)
                self.assertEqual("", output.getvalue())
                self.assertNotIn(credential, error.getvalue())
                self.assertNotIn(spelling, error.getvalue())
                self.assertEqual(
                    {
                        "error": "response-invalid",
                        "source_receipts": [],
                        "failed_call": None,
                    },
                    json.loads(error.getvalue()),
                )

    def test_library_blocks_partially_encoded_credential(self) -> None:
        # Given a literal slash combined with an encoded plus sign in source metadata.
        self.law_search["LawSearch"]["law"][0]["법령명한글"] = (
            "SYNTHETIC/SECRET%2BVALUE"
        )
        with patch.dict(os.environ, {"LAW_OC": "SYNTHETIC/SECRET+VALUE"}):
            # When the public library uses the same real enforcer and output boundary.
            with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                self.adapter.search_laws(runtime=self.runtime())
        # Then the library exception is already safe before any CLI serializer.
        self.assertEqual("response-invalid", raised.exception.status)
        self.assertEqual((), raised.exception.source_receipts)
        self.assertIsNone(raised.exception.failed_call)

    def test_credential_decoding_rejects_invalid_utf8_before_output(self) -> None:
        # Given syntactically valid percent octets that do not encode valid UTF-8.
        for spelling in ("SYNTHETIC%FF", "SYNTHETIC%C0%AF"):
            with self.subTest(spelling=spelling):
                self.law_search["LawSearch"]["law"][0]["법령명한글"] = spelling
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    # When the enforcer projects the metadata through strict decoding.
                    with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                        self.adapter.search_laws(runtime=self.runtime())
                # Then invalid byte sequences are not replaced or reflected.
                self.assertEqual("response-invalid", raised.exception.status)
                self.assertEqual((), raised.exception.source_receipts)
                self.assertIsNone(raised.exception.failed_call)

    def test_credential_decoding_has_an_explicit_byte_bound(self) -> None:
        # Given a comparison string beyond the existing bounded input budget.
        oversized = "x" * (self.adapter.MAX_INPUT_BYTES + 1)
        # When the credential boundary would decode it.
        with self.assertRaises(ValueError):
            self.adapter._ensure_credential_free(oversized, "fixture-secret")
        # Then decoding cannot consume an unbounded comparison string.

    def test_dot_continuation_ranges_cannot_lose_the_first_endpoint(self) -> None:
        # Given ellipsis or repeated-dot ranges with a different or missing first endpoint.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        for official, candidate in (
            ("1…5%", "9…5%"),
            ("1…5%", ".5%"),
            ("1..5%", "9..5%"),
            ("1..5%", ".5%"),
        ):
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When the public verifier normalizes and checks both citation kinds.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then no numeric dot continuation is erased as a structural list prefix.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])
                self.assertTrue(
                    all(
                        item["mismatched_fields"] == ["quoted_text"]
                        for item in result["citations"]
                    )
                )

    def test_complete_dot_ranges_and_real_list_markers_remain_valid(self) -> None:
        # Given complete ranges and both contracted list-marker spellings.
        pairs = (
            (
                "1…5%에 관한 충분히 긴 공식 설명입니다.",
                "1…5%에 관한 충분히 긴 공식 설명입니다.",
            ),
            (
                "1..5%에 관한 충분히 긴 공식 설명입니다.",
                "1..5%에 관한 충분히 긴 공식 설명입니다.",
            ),
            (
                "1. 문장에는 검토가 필요하다고 규정합니다.",
                "문장에는 검토가 필요하다고 규정합니다.",
            ),
            (
                "1.문장에는 검토가 필요하다고 규정합니다.",
                "문장에는 검토가 필요하다고 규정합니다.",
            ),
        )
        for official, candidate in pairs:
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official
                self.prec_detail["PrecService"]["판시사항"] = official
                # When both paths compare the complete valid excerpt.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then range preservation does not disable actual list markup.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_spaced_korean_amount_components_cannot_be_sliced(self) -> None:
        # Given whitespace inside a single Korean scaled amount or its currency suffix.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        for official, candidate in (
            ("1억 5000만원", "5000만원"),
            ("1억 원", "원"),
            ("1 억 5000 만 원", "5000 만 원"),
            ("1억 5000만 2000원", "2000원"),
        ):
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When both public paths use the shared numeric containment helper.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then spaces cannot manufacture a smaller amount from an interior component.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])

    def test_spaced_amounts_and_prose_separated_numbers_remain_valid(self) -> None:
        # Given complete amounts and separate numbers connected only by ordinary prose.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        pairs = (
            ("1억 5000만원", "1억 5000만원"),
            ("1억 원", "1억 원"),
            ("1 억 5000 만 원", "1 억 5000 만 원"),
            ("1억 5000만 2000원", "1억 5000만 2000원"),
            ("1억 및 5000만원", "5000만원"),
            ("1억 지원금과 별도로 5000만원", "5000만원"),
        )
        for official, candidate in pairs:
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When complete or genuinely separate numeric excerpts are verified.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then whitespace recognition stays narrow rather than joining arbitrary prose.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_compatibility_forms_never_flatten_into_matchable_fragments(self) -> None:
        # Given every saturated-review compatibility-form counterexample.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        for official, candidate in (
            ("1½", "11/2"),
            ("3¾", "33/4"),
            ("1&frac12;", "11/2"),
            ("10₅", "105"),
            ("10<sub>5</sub>", "105"),
            ("10&#8325;", "105"),
            ("10ⁿ", "10n"),
            ("10ᵃ", "10a"),
            ("10㎥", "3"),
            ("10㎡", "2"),
            ("⒈5%", "1.5%"),
        ):
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    library = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                self.assertFalse(library["admission_passed"])
                self.assertEqual(2, library["blocked_count"])
                path = Path(self.directory.name) / "compatibility-input.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When both public kinds run through the real CLI boundary.
                    exit_code = self.adapter.main()
                # Then no compatibility expansion can create an admitted excerpt.
                result = json.loads(output.getvalue())
                self.assertEqual(1, exit_code)
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])

    def test_supported_html_cannot_manufacture_numeric_boundaries(self) -> None:
        # Given supported attribute-bearing and void inline markup in one rendered number.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        for official in (
            '1<b class="rate">1.5%</b>',
            '1<span lang="ko">1.5%</span>',
            "1<wbr>1.5%",
        ):
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = "1.5%" + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    library = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                self.assertFalse(library["admission_passed"])
                self.assertEqual(2, library["blocked_count"])
                path = Path(self.directory.name) / "markup-input.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When the actual parser and verifier run through the CLI.
                    exit_code = self.adapter.main()
                # Then tags cannot split the rendered 11.5% token.
                self.assertEqual(1, exit_code)
                self.assertFalse(json.loads(output.getvalue())["admission_passed"])
        # Given entity-escaped tag text rather than actual markup.
        literal = "&lt;b&gt;검토 문구&lt;/b&gt;"
        # When comparison markup is parsed exactly once.
        normalized = self.adapter._normalized_text(literal)
        # Then the literal angle-tag text is retained and never reparsed.
        self.assertEqual("<b>검토 문구</b>", normalized)

    def test_quantitative_table_and_end_fragments_fail_through_cli(self) -> None:
        # Given the saturated-review quantity table and end-fragment counterexamples.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        cases = (
            ("2026. 1.", "2025. 1."),
            ("2026. 1. ~ 2026. 5.", "2025. 1. ~ 2026. 5."),
            ("２０２６． １．", "２０２５． １．"),
            ("일억 5000만원", "5000만원"),
            ("일억 오천만원", "오천만원"),
            ("5분의 1", "1"),
            ("1 1/2", "1/2"),
            ("1 000원", "000원"),
            ("1 000원", "000원"),
            ("1⋯5%", "5%"),
            ("≤1.5%", "1.5%"),
            ("<=1.5%", "1.5%"),
            (">=1.5%", "1.5%"),
            ("-일억 오천만원", "일억 오천만원"),
            ("≤일억원", "일억원"),
            ("일억원 내지 오천만원", "오천만원"),
            ("일억원 ~ 오천만원", "오천만원"),
            ("<1.5%", "1.5%"),
            (">1.5%", "1.5%"),
            ("√5원", "5원"),
            ("2026년 1월 1일", "1월 1일"),
            ("10 %", "10"),
            ("10 ‰", "10"),
            ("10㎡", "10m"),
        )
        for official, candidate in cases:
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    library = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                self.assertFalse(library["admission_passed"])
                self.assertEqual(2, library["blocked_count"])
                path = Path(self.directory.name) / "quantity-input.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When statute and precedent verification run through the real CLI.
                    exit_code = self.adapter.main()
                # Then no altered or interior quantitative fragment is admitted.
                result = json.loads(output.getvalue())
                self.assertEqual(1, exit_code)
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])
        prefix = "공식 규정에서 정한 수치는 "
        payload = copy.deepcopy(self.valid)
        for citation in payload["citations"]:
            citation["candidate"]["quoted_text"] = prefix + "10"
        official = prefix + "10<sup>1.5</sup>원입니다."
        self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0]["호내용"] = (
            official
        )
        self.prec_detail["PrecService"]["판시사항"] = official
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        self.assertFalse(result["admission_passed"])
        self.assertEqual(2, result["blocked_count"])

    def test_quantitative_complete_controls_remain_verifiable(self) -> None:
        # Given complete quantitative forms and an unrelated prose excerpt.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        for value in (
            "2026. 1.",
            "2026. 1. ~ 2026. 5.",
            "２０２６． １．",
            "일억 5000만원",
            "일억 오천만원",
            "5분의 1",
            "1 1/2",
            "1 000원",
            "1 000원",
            "1⋯5%",
            "≤1.5%",
            "<=1.5%",
            ">=1.5%",
            "-일억 오천만원",
            "≤일억원",
            "일억원 내지 오천만원",
            "일억원 ~ 오천만원",
            "<1.5%",
            ">1.5%",
            "√5원",
            "2026년 1월 1일",
            "10 %",
            "10 ‰",
            "10㎡",
        ):
            with self.subTest(value=value):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = value + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = "앞선 문장입니다. " + value + suffix
                self.prec_detail["PrecService"]["판시사항"] = (
                    "앞선 문장입니다. " + value + suffix
                )
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_dotted_dates_preserve_year_and_reject_internal_fragments(self) -> None:
        # Given altered dates and excerpts cut from inside an official dotted date.
        suffix = " 선고된 충분히 긴 공식 문장입니다."
        for official, candidate in (
            ("2026. 1. 1.", "2025. 1. 1."),
            ("2026.1.1", "2025.1.1"),
            ("2026. 1. 1.", "1. 1."),
            ("2026. 1. 1.", "2026. 1."),
        ):
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When both public verification paths compare the date excerpt.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then neither a changed year nor an internal date slice is admitted.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])
                self.assertTrue(
                    all(
                        item["mismatched_fields"] == ["quoted_text"]
                        for item in result["citations"]
                    )
                )

    def test_complete_dotted_date_forms_remain_verifiable(self) -> None:
        # Given equivalent spaced, compact and optional-terminal-dot date forms.
        suffix = " 선고된 충분히 긴 공식 문장입니다."
        for official, candidate in (
            ("2026. 1. 1.", "2026.1.1"),
            ("2026.1.1", "2026. 1. 1."),
            ("앞서 2026. 1. 1. 판결", "2026.1.1 판결"),
        ):
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When both paths normalize a complete dotted date.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then formatting differences do not block the same complete date.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_dotted_date_regressions_through_real_cli(self) -> None:
        # Given altered, internal-fragment and equivalent complete date citations.
        suffix = " 선고된 충분히 긴 공식 문장입니다."
        for official, candidate, expected_exit in (
            ("2026. 1. 1.", "2025. 1. 1.", 1),
            ("2026. 1. 1.", "1. 1.", 1),
            ("2026. 1. 1.", "2026.1.1", 0),
        ):
            with self.subTest(candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                path = Path(self.directory.name) / "dotted-date-input.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When the real CLI verifies through the policy enforcer.
                    exit_code = self.adapter.main()
                # Then its admission exit agrees with the public library contract.
                self.assertEqual(expected_exit, exit_code)
                self.assertEqual(
                    expected_exit == 0,
                    json.loads(output.getvalue())["admission_passed"],
                )

    def test_quote_scanner_only_receives_fixed_boundary_windows(self) -> None:
        # Given one exact excerpt occurrence in a source longer than a scan window.
        source = "만" * 600 + " 충분히 긴 공식 문장입니다."
        scanned_lengths = []
        pattern = self.adapter.QUANTITATIVE_TOKEN

        class RecordingScanner:
            def finditer(self, value):
                scanned_lengths.append(len(value))
                return pattern.finditer(value)

        # When quote matching checks the occurrence boundaries.
        with patch.object(self.adapter, "QUANTITATIVE_TOKEN", RecordingScanner()):
            matched = self.adapter._quote_matches("충분히 긴 공식 문장입니다.", source)
        # Then no regex sees source-wide input and only two boundaries are inspected.
        self.assertTrue(matched)
        self.assertEqual(2, len(scanned_lengths))
        self.assertTrue(
            all(
                length <= self.adapter.QUANTITATIVE_SCAN_RADIUS * 2
                for length in scanned_lengths
            )
        )

    def test_public_long_korean_text_completes_with_bounded_scanning(self) -> None:
        # Given a permitted dense 20KB official string with the valid excerpt at its end.
        script = r"""
import copy
import os
from unittest.mock import patch
from tests.capabilities.test_korean_legal_citation_verification import AdapterTest
AdapterTest.setUpClass()
t = AdapterTest()
t.setUp()
try:
    payload = copy.deepcopy(t.valid)
    excerpt = "충분히 긴 공식 문장입니다."
    for citation in payload["citations"]:
        citation["candidate"]["quoted_text"] = excerpt
    official = "만" * 6500 + " " + excerpt
    t.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0]["호내용"] = official
    t.prec_detail["PrecService"]["판시사항"] = official
    with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
        result = t.adapter.verify_citations(payload, runtime=t.runtime())
    assert result["admission_passed"]
    assert result["verified_count"] == 2
finally:
    t.doCleanups()
"""
        # When both public verification kinds execute in a bounded child process.
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        # Then behavior completes normally without an elapsed-time assertion.
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_extended_numeric_token_fragments_fail_on_both_public_paths(self) -> None:
        # Given leading-dot, signed, exponent, fraction and connected numeric expressions.
        pairs = (
            (".5%", "5%"),
            ("−1.5%", "1.5%"),
            ("-1.5%", "1.5%"),
            ("－1.5%", "1.5%"),
            ("–1.5%", "1.5%"),
            ("➖1.5%", "1.5%"),
            ("+1.5%", "1.5%"),
            ("＋1.5%", "1.5%"),
            ("±1.5%", "1.5%"),
            ("∓.5%", ".5%"),
            ("1e5원", "5원"),
            ("1E+5원", "+5원"),
            ("1e−5%", "−5%"),
            ("1/5", "5"),
            ("1⁄5", "5"),
            ("1~5%", "5%"),
            ("1～5%", "5%"),
            ("1–5%", "–5%"),
            ("1 : 5%", "5%"),
            ("1 to 5%", "5%"),
            ("1 내지 5%", "5%"),
            ("1×5%", "5%"),
            ("1+5%", "+5%"),
        )
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        for official, candidate in pairs:
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When the shared containment seam verifies both citation kinds.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then no expression suffix can be admitted as a complete numeric value.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])
                self.assertTrue(
                    all(
                        item["mismatched_fields"] == ["quoted_text"]
                        for item in result["citations"]
                    )
                )

    def test_extended_numeric_end_fragments_fail_on_both_public_paths(self) -> None:
        # Given excerpts ending before a decimal, exponent, fraction or range finishes.
        prefix = "공식 규정에서 지정한 수치는 "
        for official, candidate in (
            (".5%", "."),
            ("1e5원", "1"),
            ("1/5", "1"),
            ("1~5%", "1"),
            ("−1.5%", "−1"),
        ):
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = prefix + candidate
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = prefix + official + "입니다."
                self.prec_detail["PrecService"]["판시사항"] = (
                    prefix + official + "입니다."
                )
                # When a public verification would otherwise accept the shared prefix.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then both paths require the numeric expression's end boundary.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])

    def test_complete_extended_numbers_and_ordinary_excerpts_remain_valid(self) -> None:
        # Given complete signed/leading-dot/exponent/fraction/range expressions.
        suffix = "에 관한 충분히 긴 공식 설명입니다."
        pairs = (
            (".5%", ".5%"),
            ("−1.5%", "-1.5%"),
            ("－.5%", "-.5%"),
            ("➖1.5%", "-1.5%"),
            ("＋1.5%", "+1.5%"),
            ("±1.5%", "±1.5%"),
            ("1e5원", "1e5원"),
            ("1/5", "1/5"),
            ("1⁄5", "1/5"),
            ("1~5%", "1~5%"),
            ("-1.5% ~ +2.5%", "-1.5% ~ +2.5%"),
        )
        for official, candidate in pairs:
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = "앞선 문장입니다. " + official + suffix
                self.prec_detail["PrecService"]["판시사항"] = (
                    "앞선 문장입니다. " + official + suffix
                )
                # When normalization compares full tokens rather than evaluating numbers.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then complete equivalents remain valid substring excerpts on both paths.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_superscript_amount_cannot_flatten_into_ordinary_digits(self) -> None:
        # Given exponent notation represented as Unicode or official-source markup.
        suffix = "원을 지급하여야 하는 충분히 긴 공식 규정입니다."
        for official in ("10⁵", "10<sup>5</sup>"):
            for candidate in ("105", "5}"):
                with self.subTest(official=official, candidate=candidate):
                    payload = copy.deepcopy(self.valid)
                    for citation in payload["citations"]:
                        citation["candidate"]["quoted_text"] = candidate + suffix
                    self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                        "호내용"
                    ] = official + suffix
                    self.prec_detail["PrecService"]["판시사항"] = official + suffix
                    # When both public verification paths normalize the official text.
                    with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                        result = self.adapter.verify_citations(
                            payload, runtime=self.runtime()
                        )
                    # Then exponent semantics cannot become an ordinary monetary amount.
                    self.assertFalse(result["admission_passed"])
                    self.assertEqual(2, result["blocked_count"])
                    self.assertTrue(
                        all(
                            item["mismatched_fields"] == ["quoted_text"]
                            for item in result["citations"]
                        )
                    )

    def test_equivalent_script_representations_remain_verifiable(self) -> None:
        # Given equivalent Unicode and official HTML script notation.
        suffix = "원을 지급하여야 하는 충분히 긴 공식 규정입니다."
        for candidate, official in (
            ("10⁵", "10<sup>5</sup>"),
            ("10ᵇ", "10<sup>b</sup>"),
            ("10₅", "10<sub>5</sub>"),
            ("10ₓ", "10<sub>x</sub>"),
        ):
            with self.subTest(candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                # When both public paths normalize equivalent rendered notation.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then provenance markers preserve equivalent script semantics.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_adjacent_script_runs_are_merged_before_matching(self) -> None:
        # Given adjacent HTML/Unicode scripts and excerpts that drop part or all provenance.
        suffix = "원을 지급하여야 하는 충분히 긴 공식 규정입니다."
        for official, candidate in (
            ("10<sup>1</sup><sup>5</sup>", "10<sup>1</sup>"),
            ("10<sup>1</sup>⁵", "10<sup>1</sup>"),
            ("10<sub>1</sub><sub>5</sub>", "10<sub>5</sub>"),
            ("10<sub>1</sub>₅", "10<sub>5</sub>"),
            ("10<sup>1</sup><sup>5</sup>", "1015"),
        ):
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    library = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                self.assertFalse(library["admission_passed"])
                self.assertEqual(2, library["blocked_count"])
                path = Path(self.directory.name) / "script-composition.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When both legal kinds run through the real CLI.
                    code = self.adapter.main()
                # Then neither a partial run nor baseline-only text is admitted.
                self.assertEqual(1, code)
                self.assertFalse(json.loads(output.getvalue())["admission_passed"])

    def test_script_run_limits_and_window_independence(self) -> None:
        # Given one maximum-size run and oversized individual/merged/nested forms.
        suffix = "원을 지급하여야 하는 충분히 긴 공식 규정입니다."
        maximum = "<sup>" + "1" * 64 + "</sup>" + suffix
        self.assertTrue(self.adapter._quote_matches("¹" * 64 + suffix, maximum))
        for invalid in (
            "<sup>" + "1" * 65 + "</sup>",
            "<sup>" + "1" * 300 + "</sup>",
            "<sup>" + "1" * 40 + "</sup><sup>" + "2" * 25 + "</sup>",
            "<sup></sup>",
            "<sup><sup>1</sup></sup>",
            "<sup>1<sub>2</sub></sup>",
            "<sup>1",
        ):
            with self.subTest(length=len(invalid)):
                # When normalization runs before any boundary-window scan.
                with self.assertRaises(self.adapter.JsonContractError):
                    self.adapter._normalized_text("만" * 600 + invalid + suffix)
                # Then invalid scripts fail even when located beyond one scan radius.

    def test_complete_adjacent_script_runs_verify_both_kinds(self) -> None:
        # Given equivalent continuous HTML and Unicode script runs.
        suffix = "원을 지급하여야 하는 충분히 긴 공식 규정입니다."
        for official, candidate in (
            ("10<sup>1</sup><sup>5</sup>", "10¹⁵"),
            ("10<sup>1</sup>⁵", "10¹⁵"),
            ("10<sub>1</sub><sub>5</sub>", "10₁₅"),
            ("10<sub>1</sub>₅", "10₁₅"),
        ):
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate + suffix
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official + suffix
                self.prec_detail["PrecService"]["판시사항"] = official + suffix
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_semantic_credential_views_block_library_and_cli_reflections(self) -> None:
        # Given credentials reflected through an actual metadata fold or HTML entity.
        for credential, reflected in (
            ("ＳＹＮＴＨＥＴＩＣ", "ＳＹＮＴＨＥＴＩＣ"),
            ("SYNTHETIC", "SYN&#84;HETIC"),
        ):
            with self.subTest(credential=credential):
                self.law_search["LawSearch"]["totalCnt"] = "1"
                self.law_search["LawSearch"]["law"] = [
                    self.law_search["LawSearch"]["law"][0]
                ]
                self.law_search["LawSearch"]["law"][0]["법령명한글"] = reflected
                with (
                    patch.dict(os.environ, {"LAW_OC": credential}),
                    self.assertRaises(self.adapter.LegalExecutionError) as raised,
                ):
                    # When the public library projects the reflected metadata.
                    self.adapter.search_laws({"display": 1}, runtime=self.runtime())
                self.assertEqual("response-invalid", raised.exception.status)
                self.assertEqual((), raised.exception.source_receipts)
                with (
                    patch.object(
                        sys,
                        "argv",
                        [str(ADAPTER_PATH), "--search-law", "--param", "display=1"],
                    ),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": credential}),
                    redirect_stdout(io.StringIO()) as output,
                    redirect_stderr(io.StringIO()) as error,
                ):
                    # When the same value reaches the real CLI.
                    exit_code = self.adapter.main()
                # Then neither surface emits a reflected value or allowed receipt.
                self.assertEqual(4, exit_code)
                self.assertEqual("", output.getvalue())
                self.assertNotIn(reflected, error.getvalue())
                self.assertEqual([], json.loads(error.getvalue())["source_receipts"])

    def test_identifier_semantic_views_and_numeric_scalars_block_before_receipt(
        self,
    ) -> None:
        # Given numeric and HTML-entity identifiers in both legal search projections.
        for kind, value in (
            ("law", "9001011234567"),
            ("precedent", "9001011234567"),
            ("law", "person&#64;example.org"),
            ("law", "010&#45;1234&#45;5678"),
            ("law", "900101&#45;1234567"),
            ("precedent", "person&#64;example.org"),
            ("precedent", "010&#45;1234&#45;5678"),
            ("precedent", "900101&#45;1234567"),
        ):
            with self.subTest(kind=kind, value=value):
                if kind == "law":
                    self.law_search["LawSearch"]["totalCnt"] = (
                        value if value.isdigit() else "1"
                    )
                    self.law_search["LawSearch"]["law"] = [
                        self.law_search["LawSearch"]["law"][0]
                    ]
                    if not value.isdigit():
                        self.law_search["LawSearch"]["law"][0]["법령명한글"] = value
                    call = self.adapter.search_laws
                    argv = [str(ADAPTER_PATH), "--search-law", "--param", "display=1"]
                else:
                    self.prec_search["PrecSearch"]["totalCnt"] = (
                        value if value.isdigit() else "1"
                    )
                    self.prec_search["PrecSearch"]["prec"] = [
                        self.prec_search["PrecSearch"]["prec"][0]
                    ]
                    if not value.isdigit():
                        self.prec_search["PrecSearch"]["prec"][0]["사건번호"] = value
                    call = self.adapter.search_precedents
                    argv = [
                        str(ADAPTER_PATH),
                        "--search-precedent",
                        "--param",
                        "display=1",
                    ]
                with (
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    self.assertRaises(self.adapter.LegalExecutionError) as raised,
                ):
                    # When the library projects the untrusted scalar or text.
                    call({"display": 1}, runtime=self.runtime())
                self.assertEqual("response-invalid", raised.exception.status)
                self.assertEqual((), raised.exception.source_receipts)
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                    redirect_stderr(io.StringIO()) as error,
                ):
                    # When the same projection is attempted through the real CLI.
                    exit_code = self.adapter.main()
                # Then both boundaries fail before an allowed receipt is created.
                self.assertEqual(4, exit_code)
                self.assertEqual("", output.getvalue())
                self.assertEqual([], json.loads(error.getvalue())["source_receipts"])

    def test_encoded_identifiers_in_projected_metadata_fail_at_library_boundary(
        self,
    ) -> None:
        # Given encoded email, phone and resident identifiers in otherwise valid metadata.
        for encoded in (
            "person%40example.org",
            "010%2d1234%2D5678",
            "900101%2D1234567",
            "%30%31%30%2D%31%32%33%34%2D%35%36%37%38",
        ):
            with self.subTest(encoded=encoded):
                self.law_search["LawSearch"]["law"][0]["법령명한글"] = encoded
                # When the real enforcer projects the official search record.
                with (
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    self.assertRaises(self.adapter.LegalExecutionError) as raised,
                ):
                    self.adapter.search_laws(runtime=self.runtime())
                # Then no allowed receipt or reflecting public exception is produced.
                self.assertEqual("response-invalid", raised.exception.status)
                self.assertEqual((), raised.exception.source_receipts)
                self.assertEqual(
                    "law-search", raised.exception.failed_call["call_kind"]
                )
                self.assertNotIn(encoded, json.dumps(raised.exception.failed_call))
                self.assertNotIn(encoded, str(raised.exception))

    def test_encoded_identifiers_in_projected_metadata_fail_through_real_cli(
        self,
    ) -> None:
        # Given the same identifier classes through public CLI parsing and the real enforcer.
        for encoded, decoded in (
            ("person%40example.org", "person@example.org"),
            ("010%2D1234%2D5678", "010-1234-5678"),
            ("900101%2d1234567", "900101-1234567"),
        ):
            with self.subTest(encoded=encoded):
                self.law_search["LawSearch"]["law"][0]["법령명한글"] = encoded
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
                    patch.object(
                        self.adapter, "_live_runtime", return_value=self.runtime()
                    ),
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    redirect_stdout(io.StringIO()) as output,
                    redirect_stderr(io.StringIO()) as error,
                ):
                    # When the CLI would emit the projected metadata.
                    code = self.adapter.main()
                # Then both encoded and decoded identifier representations remain private.
                self.assertEqual(4, code)
                self.assertEqual("", output.getvalue())
                self.assertNotIn(encoded, error.getvalue())
                self.assertNotIn(decoded, error.getvalue())
                result = json.loads(error.getvalue())
                self.assertEqual("response-invalid", result["error"])
                self.assertEqual([], result["source_receipts"])
                self.assertEqual("law-search", result["failed_call"]["call_kind"])

    def test_nested_encoded_identifier_is_not_recursively_decoded(self) -> None:
        # Given a nested email escape whose one-layer view still contains no at-sign.
        nested = "person%2540example.org"
        self.law_search["LawSearch"]["law"][0]["법령명한글"] = nested
        runtime = self.runtime()
        # When projected metadata passes the credential and identifier boundaries.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.search_laws(runtime=runtime)
        # Then independent scans do not cumulatively decode or rewrite source evidence.
        self.assertEqual(nested, result["records"][0]["law_name"])
        self.assertEqual(
            runtime.policy.digest,
            result["source_receipts"][0]["source_receipt"]["policy_digest"],
        )
        self.assertEqual(
            "allowed", result["source_receipts"][0]["source_receipt"]["outcome"]
        )

    def test_numeric_token_fragments_fail_on_both_verification_paths(self) -> None:
        # Given substring matches that cut into a number, decimal or amount.
        pairs = (
            (
                "11.5%를 적용하여야 하는 공식 규정입니다.",
                "1.5%를 적용하여야 하는 공식 규정입니다.",
            ),
            (
                "1.5%를 적용하여야 하는 공식 규정입니다.",
                "5%를 적용하여야 하는 공식 규정입니다.",
            ),
            (
                "5000000원을 지급하여야 하는 공식 규정입니다.",
                "000000원을 지급하여야 하는 공식 규정입니다.",
            ),
            ("공식 규정에서 정한 비율은 11.5%입니다.", "공식 규정에서 정한 비율은 11"),
            (
                "공식 규정에서 정한 금액은 5000000원입니다.",
                "공식 규정에서 정한 금액은 500000",
            ),
            (
                "1억5000만원을 지급하여야 하는 공식 규정입니다.",
                "5000만원을 지급하여야 하는 공식 규정입니다.",
            ),
        )
        for official, candidate in pairs:
            with self.subTest(official=official, candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official
                self.prec_detail["PrecService"]["판시사항"] = official
                # When the public verifier handles both statute and precedent text.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then matching a substring cannot change a numeric token's value.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])
                self.assertTrue(
                    all(
                        item["mismatched_fields"] == ["quoted_text"]
                        for item in result["citations"]
                    )
                )

    def test_numeric_boundaries_preserve_complete_and_non_numeric_excerpts(
        self,
    ) -> None:
        # Given complete tokens adjacent to text, a later valid match and plain excerpts.
        pairs = (
            (
                "법정한도1.5%를 적용하여야 하는 공식 규정입니다.",
                "1.5%를 적용하여야 하는 공식 규정입니다.",
            ),
            (
                "11.5%를 적용하여야 합니다. 별도 기준은1.5%를 적용하여야 합니다.",
                "1.5%를 적용하여야 합니다.",
            ),
            (
                "금액은5000000원을 지급하여야 하는 공식 규정입니다.",
                "5000000원을 지급하여야 하는 공식 규정입니다.",
            ),
            (
                "11.5% 고시와 별개로 정해진 검토 절차를 따라야 합니다.",
                "정해진 검토 절차를 따라야 합니다.",
            ),
        )
        for official, candidate in pairs:
            with self.subTest(candidate=candidate):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = candidate
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official
                self.prec_detail["PrecService"]["판시사항"] = official
                # When both public verification paths search for a valid occurrence.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then boundary checks do not turn substring matching into whole-text matching.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_bracketed_rate_changes_fail_on_both_verification_paths(self) -> None:
        # Given angle-bracketed rates that are substantive text, not HTML tags.
        for official in (
            "<1.5%>를 적용하여야 하는 공식 규정입니다.",
            "&lt;1.5%&gt;를 적용하여야 하는 공식 규정입니다.",
        ):
            with self.subTest(official=official):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = (
                        "<9.5%>를 적용하여야 하는 공식 규정입니다."
                    )
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official
                self.prec_detail["PrecService"]["판시사항"] = official
                # When both public verification paths compare the quoted rate.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then a broad tag stripper cannot erase the conflicting values.
                self.assertFalse(result["admission_passed"])
                self.assertEqual(2, result["blocked_count"])
                self.assertTrue(
                    all(
                        item["mismatched_fields"] == ["quoted_text"]
                        for item in result["citations"]
                    )
                )

    def test_inline_markup_cannot_split_one_numeric_token(self) -> None:
        # Given a rendered 11.5% rate whose inner digits have inline formatting.
        payload = copy.deepcopy(self.valid)
        for citation in payload["citations"]:
            citation["candidate"]["quoted_text"] = (
                "1.5%를 적용하여야 하는 공식 규정입니다."
            )
        official = "1<b>1.5%를 적용하여야 하는 공식 규정입니다.</b>"
        self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0]["호내용"] = (
            official
        )
        self.prec_detail["PrecService"]["판시사항"] = official
        # When both public verification paths interpret known inline markup.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        # Then removing inline tags cannot insert an artificial numeric boundary.
        self.assertFalse(result["admission_passed"])
        self.assertEqual(2, result["blocked_count"])

    def test_recognized_markup_still_normalizes_on_both_verification_paths(
        self,
    ) -> None:
        # Given ordinary formatting tags, including the existing br normalization.
        payload = copy.deepcopy(self.valid)
        for citation in payload["citations"]:
            citation["candidate"]["quoted_text"] = (
                "공식 첫 번째 문장입니다. 두 번째 문장도 검토합니다."
            )
        official = "<p>공식 첫 번째 문장입니다.<br/>두 번째 문장도 검토합니다.</p>"
        self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0]["호내용"] = (
            official
        )
        self.prec_detail["PrecService"]["판시사항"] = official
        # When the public verifier compares ordinary marked-up official text.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        # Then conservative markup recognition retains known formatting behavior.
        self.assertTrue(result["admission_passed"])
        self.assertEqual(2, result["verified_count"])

    def test_ambiguous_angle_content_is_handled_consistently(self) -> None:
        # Given numeric angle text, unsupported markup and a supported attributed tag.
        literal = "<1.5%> 공식 문장입니다."
        # When each form reaches the parser exactly once.
        self.assertEqual(literal, self.adapter._normalized_text(literal))
        with self.assertRaises(self.adapter.JsonContractError):
            self.adapter._normalized_text("<rate 1.5%> 공식 문장입니다.")
        rendered = self.adapter._normalized_text("<br rate=1.5%>공식 문장입니다.")
        # Then literal text stays literal, unknown markup fails, and supported markup renders.
        self.assertEqual("공식 문장입니다.", rendered)

    def test_markup_provenance_and_declarations_fail_closed(self) -> None:
        # Given literal internal markers, declarations, and processing instructions.
        for value in (
            "10⟪sup:5⟫원을 지급하는 충분히 긴 문장입니다.",
            "10&#10218;sup:5&#10219;원을 지급하는 충분히 긴 문장입니다.",
            "<!DOCTYPE html>충분히 긴 공식 문장입니다.",
            "<?other lost?>충분히 긴 공식 문장입니다.",
        ):
            with self.subTest(value=value):
                # When text enters the comparison parser.
                with self.assertRaises(self.adapter.JsonContractError):
                    self.adapter._normalized_text(value)
                # Then source text cannot impersonate parser-owned provenance.

    def test_percent_escape_comparison_does_not_decode_unrelated_values(self) -> None:
        # Given a nested percent sequence, not any permitted encoding of this credential.
        credential = "SYNTHETIC/SECRET+VALUE"
        unrelated = "SYNTHETIC%252FSECRET%252BVALUE"
        self.law_search["LawSearch"]["law"][0]["법령명한글"] = unrelated
        # When the same enforcer-backed output boundary compares it.
        with patch.dict(os.environ, {"LAW_OC": credential}):
            result = self.adapter.search_laws(runtime=self.runtime())
        # Then normalizing hex case does not introduce recursive URL decoding.
        self.assertEqual(unrelated, result["records"][0]["law_name"])
        self.assertEqual(
            "allowed", result["source_receipts"][0]["source_receipt"]["outcome"]
        )

    def test_different_leading_amount_cannot_match_official_list_text(self) -> None:
        # Given a structural list marker followed by a substantive official amount.
        payload = copy.deepcopy(self.valid)
        payload["citations"] = [payload["citations"][0]]
        payload["citations"][0]["candidate"]["quoted_text"] = (
            "5000000원을 지급하여야 하는 공식 규정입니다."
        )
        self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0]["호내용"] = (
            "1. 1000000원을 지급하여야 하는 공식 규정입니다."
        )
        # When full verification compares the selected item, not a standalone helper.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        # Then stripping the list marker cannot erase the candidate's amount.
        self.assertFalse(result["admission_passed"])
        self.assertEqual("mismatch-blocked", result["citations"][0]["status"])
        self.assertEqual(["quoted_text"], result["citations"][0]["mismatched_fields"])

    def test_identical_amounts_match_with_existing_structural_prefixes(self) -> None:
        # Given identical amounts with numeric, circled and Korean-letter list markers.
        amount = "1000000원을 지급하여야 하는 공식 규정입니다."
        for official_prefix, candidate_prefix in (
            ("1. ", ""),
            ("1) ", ""),
            ("① ", ""),
            ("가. ", ""),
            ("1. ", "① "),
        ):
            with self.subTest(
                official_prefix=official_prefix, candidate_prefix=candidate_prefix
            ):
                payload = copy.deepcopy(self.valid)
                payload["citations"] = [payload["citations"][0]]
                payload["citations"][0]["candidate"]["quoted_text"] = (
                    candidate_prefix + amount
                )
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = official_prefix + amount
                # When the full verifier compares the correctly located quote.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then the existing structural forms remain usable without losing digits.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(
                    "verified-official-live-match", result["citations"][0]["status"]
                )

    def test_text_normalization_preserves_substantive_digits(self) -> None:
        # Given substantive leading numbers and the supported structural list forms.
        for prefix in ("", "1. ", "1) ", "① ", "가. ", "나) "):
            with self.subTest(prefix=prefix):
                # When one quote is normalized for matching.
                result = self.adapter._normalized_text(
                    prefix + "1000000원을 지급합니다."
                )
                # Then only the structural prefix disappears, never the amount.
                self.assertEqual("1000000원을 지급합니다.", result)

    def test_statute_decimal_integer_part_cannot_be_stripped(self) -> None:
        # Given an official decimal rate and a different candidate integer part.
        payload = copy.deepcopy(self.valid)
        payload["citations"] = [payload["citations"][0]]
        payload["citations"][0]["candidate"]["quoted_text"] = (
            "9.5%를 적용하여야 하는 공식 규정입니다."
        )
        self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0]["호내용"] = (
            "1.5%를 적용하여야 하는 공식 규정입니다."
        )
        # When the public verifier retrieves and matches the selected statute unit.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        # Then a decimal point is not mistaken for a list delimiter.
        self.assertFalse(result["admission_passed"])
        self.assertEqual("mismatch-blocked", result["citations"][0]["status"])
        self.assertEqual(["quoted_text"], result["citations"][0]["mismatched_fields"])

    def test_precedent_decimal_integer_part_cannot_be_stripped(self) -> None:
        # Given matching precedent metadata but different decimal rates in the quote.
        payload = copy.deepcopy(self.valid)
        payload["citations"] = [payload["citations"][1]]
        payload["citations"][0]["candidate"]["quoted_text"] = (
            "9.5%를 적용하여야 하는 공식 판시사항입니다."
        )
        self.prec_detail["PrecService"]["판시사항"] = (
            "1.5%를 적용하여야 하는 공식 판시사항입니다."
        )
        # When the public verifier retrieves and compares the precedent text.
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            result = self.adapter.verify_citations(payload, runtime=self.runtime())
        # Then the integer part remains substantive evidence.
        self.assertFalse(result["admission_passed"])
        self.assertEqual("mismatch-blocked", result["citations"][0]["status"])
        self.assertEqual(["quoted_text"], result["citations"][0]["mismatched_fields"])

    def test_decimal_quotes_keep_legitimate_list_markers_on_both_public_paths(
        self,
    ) -> None:
        # Given identical rates after spaced or no-space structural list markers.
        for prefix, body in (
            ("1. ", "1.5%를 적용하여야 하는 공식 문장입니다."),
            ("1.", "문장에는 1.5%를 적용하도록 규정합니다."),
        ):
            with self.subTest(prefix=prefix):
                payload = copy.deepcopy(self.valid)
                for citation in payload["citations"]:
                    citation["candidate"]["quoted_text"] = body
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호내용"
                ] = prefix + body
                self.prec_detail["PrecService"]["판시사항"] = prefix + body
                # When both public verification paths use the same normalization boundary.
                with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
                    result = self.adapter.verify_citations(
                        payload, runtime=self.runtime()
                    )
                # Then real list syntax still matches without losing a decimal integer part.
                self.assertTrue(result["admission_passed"])
                self.assertEqual(2, result["verified_count"])

    def test_numeric_delimiter_followed_by_digit_remains_substantive(self) -> None:
        # Given decimal text, delimiter-adjacent digits and bare leading amounts.
        for value in (
            "1.5%를 적용합니다.",
            "1)5000000원을 지급합니다.",
            "1000000원을 지급합니다.",
        ):
            with self.subTest(value=value):
                # When the text matching normalizer examines its prefix.
                result = self.adapter._normalized_text(value)
                # Then a numeric prefix without an unambiguous delimiter remains intact.
                self.assertEqual(value, result)

    def test_numeric_total_count_credential_is_blocked_by_library(self) -> None:
        # Given a coherent one-record page whose total count equals the credential.
        self.law_search["LawSearch"]["totalCnt"] = "654321"
        self.law_search["LawSearch"]["law"] = self.law_search["LawSearch"]["law"][:1]
        runtime = self.runtime()
        with patch.dict(os.environ, {"LAW_OC": "654321"}):
            # When the public library projects totalCnt into an integer total_count.
            with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                self.adapter.search_laws({"display": 1}, runtime=runtime)
        # Then numeric serialization cannot bypass the credential boundary.
        self.assertEqual("response-invalid", raised.exception.status)
        self.assertEqual((), raised.exception.source_receipts)
        self.assertIsNone(raised.exception.failed_call)

    def test_numeric_total_count_credential_is_blocked_by_real_cli(self) -> None:
        # Given the same valid page through real CLI parsing and an injected enforcer.
        self.law_search["LawSearch"]["totalCnt"] = "654321"
        self.law_search["LawSearch"]["law"] = self.law_search["LawSearch"]["law"][:1]
        with (
            patch.object(
                sys, "argv", [str(ADAPTER_PATH), "--search-law", "--param", "display=1"]
            ),
            patch.object(self.adapter, "_live_runtime", return_value=self.runtime()),
            patch.dict(os.environ, {"LAW_OC": "654321"}),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()) as error,
        ):
            # When the CLI attempts to emit the projected numeric count.
            exit_code = self.adapter.main()
        # Then the failure is non-reflecting and no partial result or receipt is emitted.
        self.assertEqual(4, exit_code)
        self.assertEqual("", output.getvalue())
        self.assertNotIn("654321", error.getvalue())
        self.assertEqual(
            {"error": "response-invalid", "source_receipts": [], "failed_call": None},
            json.loads(error.getvalue()),
        )

    def test_numeric_failed_page_credential_is_blocked_at_library_boundary(
        self,
    ) -> None:
        # Given an upstream denial whose caller page coordinate equals the credential.
        runtime = self.runtime(lambda *_a, **_k: Response(b"denied", status=403))
        with patch.dict(os.environ, {"LAW_OC": "9999"}):
            # When the public library creates its failed-call trace.
            with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                self.adapter.search_laws({"page": 9999}, runtime=runtime)
        # Then numeric caller metadata cannot survive into the exception object.
        self.assertEqual("response-invalid", raised.exception.status)
        self.assertEqual((), raised.exception.source_receipts)
        self.assertIsNone(raised.exception.failed_call)
        self.assertNotIn("9999", str(raised.exception))

    def test_numeric_failed_page_credential_is_blocked_by_real_cli(self) -> None:
        # Given the same denied page through the real parser and enforcer.
        runtime = self.runtime(lambda *_a, **_k: Response(b"denied", status=403))
        with (
            patch.object(
                sys, "argv", [str(ADAPTER_PATH), "--search-law", "--param", "page=9999"]
            ),
            patch.object(self.adapter, "_live_runtime", return_value=runtime),
            patch.dict(os.environ, {"LAW_OC": "9999"}),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()) as error,
        ):
            # When the CLI serializes the already-protected library error.
            exit_code = self.adapter.main()
        # Then neither stdout nor the failed-call page reveals credential digits.
        self.assertEqual(4, exit_code)
        self.assertEqual("", output.getvalue())
        self.assertNotIn("9999", error.getvalue())
        self.assertEqual(
            {"error": "response-invalid", "source_receipts": [], "failed_call": None},
            json.loads(error.getvalue()),
        )

    def test_scalar_credential_comparison_uses_json_number_and_boolean_spelling(
        self,
    ) -> None:
        # Given the exact JSON spellings of integer, finite-float and boolean values.
        for value, credential in (
            (654321, "654321"),
            (654321.25, "654321.25"),
            (1e20, "1e+20"),
            (True, "true"),
            (False, "false"),
        ):
            with self.subTest(value=value):
                # When a nested scalar is checked at the shared credential boundary.
                with self.assertRaises(ValueError):
                    self.adapter._ensure_credential_free(
                        {"nested": [value]}, credential
                    )
                # Then its serialized representation is treated like a string reflection.

    def test_scalar_comparison_does_not_use_python_boolean_or_none_spelling(
        self,
    ) -> None:
        # Given spellings that are not JSON representations, and null that carries no value.
        for value, credential in (
            (True, "True"),
            (False, "False"),
            (None, "None"),
            (None, "null"),
        ):
            with self.subTest(value=value, credential=credential):
                # When these values cross the same comparison boundary.
                result = self.adapter._ensure_credential_free(
                    {"nested": [value]}, credential
                )
                # Then None is not stringified and booleans do not use Python capitalization.
                self.assertIsNone(result)

    def test_protocol_error_status_survives_coincidental_credential_equality(
        self,
    ) -> None:
        # Given credentials equal to stable failure tokens, not reflected source fields.
        for token, response in (
            ("upstream-403-manual", Response(b"UNTRUSTED_UPSTREAM_MARKER", status=403)),
            (
                "response-invalid",
                Response(b"UNTRUSTED_UPSTREAM_MARKER", media_type="application/json"),
            ),
        ):
            with self.subTest(token=token):
                runtime = self.runtime(lambda *_a, **_k: response)
                with (
                    patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
                    patch.object(self.adapter, "_live_runtime", return_value=runtime),
                    patch.dict(os.environ, {"LAW_OC": token}),
                    redirect_stderr(io.StringIO()) as error,
                    redirect_stdout(io.StringIO()) as output,
                ):
                    # When the CLI classifies the failure using implementation constants.
                    exit_code = self.adapter.main()
                # Then the necessary protocol token remains while source material does not.
                self.assertEqual(4, exit_code)
                self.assertEqual("", output.getvalue())
                result = json.loads(error.getvalue())
                self.assertEqual(token, result["error"])
                self.assertNotIn(
                    token,
                    json.dumps([result["source_receipts"], result["failed_call"]]),
                )
                self.assertNotIn("UNTRUSTED_UPSTREAM_MARKER", error.getvalue())

    def test_search_cli_rejects_credential_collisions_in_appended_receipts(
        self,
    ) -> None:
        # Given credentials colliding only with authentic receipt fields.
        runtime = self.runtime()
        for marker in ("allowed", runtime.policy.digest):
            with (
                self.subTest(marker=marker),
                patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
                patch.object(self.adapter, "_live_runtime", return_value=runtime),
                patch.dict(os.environ, {"LAW_OC": marker}),
                redirect_stderr(io.StringIO()) as error,
                redirect_stdout(io.StringIO()) as output,
            ):
                # When the real CLI assembles a successful source fetch and its receipt.
                exit_code = self.adapter.main()
                # Then no successful output or falsified receipt can escape.
                self.assertEqual(4, exit_code)
                self.assertEqual("", output.getvalue())
                self.assertNotIn(marker, error.getvalue())
                self.assertEqual(
                    {
                        "error": "response-invalid",
                        "source_receipts": [],
                        "failed_call": None,
                    },
                    json.loads(error.getvalue()),
                )

    def test_library_partial_error_trace_is_credential_safe_without_cli(self) -> None:
        # Given a completed law history followed by an upstream denial for LAW1.
        def opener(request, timeout=0):
            if urlsplit(request.full_url).path.endswith("lawService.do"):
                return Response(b"denied", status=403)
            return self.opener(request, timeout)

        runtime = self.runtime(opener)
        with patch.dict(os.environ, {"LAW_OC": "LAW1"}):
            # When the public library raises before any CLI serializer runs.
            with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                self.adapter.verify_citations(self.valid, runtime=runtime)
        # Then the exception itself retains authentic evidence without caller-ID leakage.
        error = raised.exception
        self.assertEqual("upstream-403-manual", error.status)
        self.assertNotIn("LAW1", json.dumps([error.source_receipts, error.failed_call]))
        self.assertEqual(1, len(error.source_receipts))
        self.assertIsNone(error.source_receipts[0]["citation_id"])
        self.assertIsNone(error.failed_call["citation_id"])
        self.assertEqual(
            runtime.policy.digest,
            error.source_receipts[0]["source_receipt"]["policy_digest"],
        )

    def test_every_public_success_surface_checks_complete_output(self) -> None:
        # Given collisions in appended receipt or wrapper fields, not raw source content.
        for operation, marker in (
            (lambda runtime: self.adapter.search_laws(runtime=runtime), "allowed"),
            (
                lambda runtime: self.adapter.search_precedents(runtime=runtime),
                "allowed",
            ),
            (
                lambda runtime: self.adapter.get_precedent("999999", runtime=runtime),
                "official-precedent-retrieved",
            ),
            (
                lambda runtime: self.adapter.verify_citations(
                    self.valid, runtime=runtime
                ),
                "allowed",
            ),
        ):
            with (
                self.subTest(marker=marker),
                patch.dict(os.environ, {"LAW_OC": marker}),
            ):
                # When a public library result would otherwise expose a credential.
                with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                    operation(self.runtime())
                # Then failures are sanitized before returning to the library caller.
                self.assertEqual("response-invalid", raised.exception.status)
                self.assertEqual((), raised.exception.source_receipts)
                self.assertIsNone(raised.exception.failed_call)

    def test_request_boundary_tracks_each_credential_actually_used(self) -> None:
        # Given a batch whose environment credential changes between actual fetches.
        payload = copy.deepcopy(self.valid)
        payload["citations"][1]["candidate"]["court"] = "rotated-secret"
        self.prec_detail["PrecService"]["법원명"] = "rotated-secret"
        environment = {"LAW_OC": "initial-secret"}

        def opener(request, timeout=0):
            if parse_qs(urlsplit(request.full_url).query)["target"] == ["eflawjosub"]:
                environment["LAW_OC"] = "rotated-secret"
            return self.opener(request, timeout)

        with patch.object(self.adapter.os, "environ", environment):
            # When a later source reflects the credential used for that request.
            with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                self.adapter.verify_citations(payload, runtime=self.runtime(opener))
        # Then one batch-wide boundary protects every actual request credential.
        self.assertEqual("response-invalid", raised.exception.status)
        self.assertEqual((), raised.exception.source_receipts)
        self.assertIsNone(raised.exception.failed_call)

    def test_not_found_projection_uses_the_same_credential_boundary(self) -> None:
        # Given a recognized not-found value whose status equals the request credential.
        runtime = self.runtime(
            lambda *_a, **_k: _Response({"Law": "일치하는 판례가 없습니다."})
        )
        session = self.adapter.LegalSession(runtime)
        with patch.dict(os.environ, {"LAW_OC": "official-source-not-found"}):
            # When the session projects the typed not-found sentinel.
            with self.assertRaises(self.adapter.LegalExecutionError) as raised:
                session.fetch(
                    self.adapter.LegalCall("precedent-detail", {"ID": "999999"}),
                    lambda raw: self.adapter._precedent_detail("999999", raw),
                )
        # Then even the sentinel cannot escape before the public wrapper runs.
        self.assertEqual("response-invalid", raised.exception.status)
        self.assertEqual((), raised.exception.source_receipts)
        self.assertIsNone(raised.exception.failed_call)

    def test_successful_verification_redacts_only_colliding_citation_ids(self) -> None:
        # Given valid citations where only the caller-supplied ID equals the credential.
        with patch.dict(os.environ, {"LAW_OC": "LAW1"}):
            # When all structural verification succeeds through the real enforcer.
            result = self.adapter.verify_citations(self.valid, runtime=self.runtime())
        # Then useful verification survives without changing any authentic receipt field.
        self.assertTrue(result["admission_passed"])
        self.assertNotIn("LAW1", json.dumps(result))
        self.assertIsNone(result["citations"][0]["citation_id"])
        self.assertEqual("PREC1", result["citations"][1]["citation_id"])
        self.assertTrue(
            all(
                item["source_receipt"]["outcome"] == "allowed"
                for item in result["source_receipts"]
            )
        )

    def test_branch_numbered_statute_labels_cannot_match_simple_locators(self) -> None:
        # Given an upstream branch-numbered item whose quote would otherwise match.
        for label in ("1의2.", "1-2.", "1.2", "1garbage", "①의2."):
            with self.subTest(label=label):
                self.law_detail["법령"]["조문"]["조문단위"][1]["항"][1]["호"][0][
                    "호번호"
                ] = label
                # When a simple item locator is verified against that unsupported label.
                with (
                    patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
                    self.assertRaises(ReadOnlyHttpError) as raised,
                ):
                    self.adapter.verify_citations(self.valid, runtime=self.runtime())
                # Then a prefix match cannot admit the wrong legal unit.
                self.assertEqual("response-invalid", raised.exception.status)

    def test_label_parser_preserves_simple_formats_and_rejects_suffixes(self) -> None:
        # Given the supported numeric, circled and Korean-letter labels.
        for label, expected in (
            ("1", 1),
            (" 1. ", 1),
            ("1)", 1),
            ("② ", 2),
            ("⑳", 20),
            ("가", 1),
            ("나. ", 2),
            ("다)", 3),
        ):
            with self.subTest(label=label):
                # When the entire label is parsed.
                result = self.adapter._label_number(label, "label")
                # Then the exact supported simple number is preserved.
                self.assertEqual(expected, result)
        for label in ("가의2.", "나-1", "다목", "②의1", "2조", "1.2"):
            with self.subTest(label=label):
                # Given/When an unsupported branch or suffix is parsed.
                with self.assertRaises(ValueError):
                    self.adapter._label_number(label, "label")
                # Then no truncated number is returned.

    def test_integer_identifier_parameters_are_rejected_before_runtime(self) -> None:
        # Given equivalent identifier text and scalar integer representations.
        for value in ("9001011234567", 9001011234567, "01012345678"):
            for search in (self.adapter.search_laws, self.adapter.search_precedents):
                with (
                    self.subTest(value=value, search=search.__name__),
                    patch.object(
                        self.adapter,
                        "_live_runtime",
                        side_effect=AssertionError("runtime"),
                    ),
                ):
                    # When either public search parses a query at its input boundary.
                    with self.assertRaises(ValueError):
                        search({"query": value})
                    # Then stringification cannot bypass the identifier guard.

    def test_session_rejects_reserved_parameters_before_infrastructure(self) -> None:
        # Given direct session calls attempting to replace fixed routing or credentials.
        runtime = self.runtime(self.fail)
        session = self.adapter.LegalSession(runtime)
        for key in ("target", "type", "OC", "TARGET", "Type", "oc"):
            with (
                self.subTest(key=key),
                patch.object(
                    self.adapter, "build_url", side_effect=AssertionError("credential")
                ),
                patch.object(self.state, "open", side_effect=AssertionError("state")),
            ):
                # When a caller bypasses the higher-level search whitelist.
                with self.assertRaises(ReadOnlyHttpError) as raised:
                    session.fetch(
                        self.adapter.LegalCall("law-search", {key: "override"}),
                        lambda _raw: {},
                    )
                # Then the direct seam rejects the request before any side effect.
                self.assertEqual("invalid-request", raised.exception.status)
                self.assertEqual([], session.receipts)

    def test_invalid_parameters_stop_before_runtime(self) -> None:
        # Given the full effective legacy scalar boundary, not just the local whitelist.
        for params in (
            {"OC": "SYNTHETIC"},
            {"target": "prec"},
            {"type": "XML"},
            {"display": True},
            {"display": 0},
            {"page": 10001},
            {"query": ""},
            {"query": "x" * 201},
            {"query": "control\nvalue"},
        ):
            with (
                self.subTest(params=params),
                patch.object(
                    self.adapter, "_live_runtime", side_effect=AssertionError("runtime")
                ),
            ):
                # When invalid parameters enter the public search boundary.
                with self.assertRaises(ValueError):
                    self.adapter.search_laws(params)
                # Then no runtime was needed to reject them.

    def test_fixture_does_not_consult_or_mutate_credentials(self) -> None:
        # Given a fixture execution with all credential access forbidden.
        with patch.object(self.adapter.os, "environ") as environment:
            environment.get.side_effect = lambda key, default=None: (
                self.fail("credential read") if key == "LAW_OC" else default
            )
            environment.__setitem__.side_effect = self.fail
            # When the actual fixture path is evaluated through the enforcer.
            result = self.adapter._fixture_result(FIXTURE_PATH)
            # Then it neither mutates credentials nor returns allowed live receipts.
            environment.__setitem__.assert_not_called()
        self.assertFalse(result["admission_passed"])
        self.assertEqual("synthetic-fixture", result["execution_mode"])
        self.assertTrue(
            all(item["source_receipt"] is None for item in result["source_receipts"])
        )

    def test_retry_after_cooldown_survives_state_reopening(self) -> None:
        # Given a persisted source cooldown from a 429 search response.
        runtime = self.runtime(
            lambda *_a, **_k: Response(
                b"limited", status=429, headers={"Retry-After": "60"}
            )
        )
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(ReadOnlyHttpError),
        ):
            self.adapter.search_laws(runtime=runtime)
        reopened = PolicyState(
            Path(self.directory.name) / "policy.sqlite3",
            clock=lambda: 1000.0,
            sleeper=self.fail,
        )
        runtime = replace(
            runtime,
            enforcer=HttpPolicyEnforcer(
                self.registry, reopened, HttpTransport(self.fail, lambda _: ["1.1.1.1"])
            ),
        )
        # When a different call kind tries to ignore the persisted cooldown.
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(ReadOnlyHttpError) as raised,
        ):
            self.adapter.get_precedent("999999", runtime=runtime)
        # Then the upstream is not retried through a different call path.
        self.assertEqual("budget-exhausted", raised.exception.status)

    def test_persisted_policy_digest_conflict_never_resets_budget(self) -> None:
        # Given durable state for one policy digest.
        runtime = self.runtime()
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}):
            self.adapter.search_laws(runtime=runtime)
        policy = replace(runtime.policy, digest="0" * 64)
        registry = replace(
            self.registry,
            policies=tuple(
                policy if item.id == policy.id else item
                for item in self.registry.policies
            ),
        )
        runtime = self.adapter.LegalRuntime(
            policy,
            HttpPolicyEnforcer(
                registry, self.state, HttpTransport(self.fail, lambda _: ["1.1.1.1"])
            ),
        )
        # When a reviewed but incompatible digest reaches the same durable budget.
        with (
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            self.assertRaises(ReadOnlyHttpError) as raised,
        ):
            self.adapter.get_precedent("999999", runtime=runtime)
        # Then it fails rather than purging or opening a fresh quota.
        self.assertEqual("budget-exhausted", raised.exception.status)

    def test_cli_mismatch_returns_exit_one_without_admission(self) -> None:
        # Given a real input file with structurally valid but mismatching citations.
        payload = copy.deepcopy(self.valid)
        payload["citations"][0]["candidate"]["quoted_text"] = (
            "다른 법령에서 가져온 충분히 긴 인용문입니다."
        )
        path = Path(self.directory.name) / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        runtime = self.runtime()
        with (
            patch.object(sys, "argv", [str(ADAPTER_PATH), str(path)]),
            patch.object(self.adapter, "_live_runtime", return_value=runtime),
            patch.dict(os.environ, {"LAW_OC": "fixture-secret"}),
            redirect_stdout(io.StringIO()) as output,
        ):
            # When the real CLI reads and verifies the file through the enforcer.
            exit_code = self.adapter.main()
        # Then it reports a review block, not an upstream failure or partial admission.
        self.assertEqual(1, exit_code)
        self.assertFalse(json.loads(output.getvalue())["admission_passed"])

    def test_cli_missing_credential_returns_exit_two_after_authorization(self) -> None:
        # Given an authorized runtime, absent credential and unreachable wire.
        runtime = self.runtime(self.fail)
        with (
            patch.object(sys, "argv", [str(ADAPTER_PATH), "--search-law"]),
            patch.object(self.adapter, "_live_runtime", return_value=runtime),
            patch.dict(os.environ, {}, clear=True),
            redirect_stderr(io.StringIO()) as error,
        ):
            # When live URL construction requires the user-held credential.
            exit_code = self.adapter.main()
        # Then credential absence is an input/setup error without network access.
        self.assertEqual(2, exit_code)
        self.assertEqual(
            "MissingCredentialError", json.loads(error.getvalue())["error_type"]
        )

    def test_history_as_of_date_does_not_control_policy_review_date(self) -> None:
        # Given historical citations and the unchanged catalog.
        payload = copy.deepcopy(self.valid)
        payload["as_of_date"] = "2020-01-01"
        today = date(2026, 9, 6)

        class FixedDate(date):
            @classmethod
            def today(cls):
                return today

        parse_registry = SourcePolicyRegistry.from_catalog
        with (
            patch.object(self.adapter, "date", FixedDate),
            patch.object(
                self.adapter.SourcePolicyRegistry, "from_catalog", wraps=parse_registry
            ) as parse,
        ):
            # When runtime authorization runs after input validation.
            with self.assertRaises(ReadOnlyHttpError):
                self.adapter.verify_citations(payload)
        # Then authorization uses execution date, never historical citation date.
        self.assertEqual(today, parse.call_args.kwargs["on_date"])

    def test_state_path_precedence_matches_the_shared_runtime(self) -> None:
        # Given explicit override, XDG fallback and home fallback configurations.
        for environment, expected in (
            (
                {
                    "KGOV_POLICY_STATE_PATH": "/synthetic/explicit.sqlite3",
                    "XDG_STATE_HOME": "/synthetic/xdg",
                },
                Path("/synthetic/explicit.sqlite3"),
            ),
            (
                {"XDG_STATE_HOME": "/synthetic/xdg"},
                Path("/synthetic/xdg/k-gov-skills/policy-state.sqlite3"),
            ),
            ({}, Path.home() / ".local/state/k-gov-skills/policy-state.sqlite3"),
        ):
            with (
                self.subTest(environment=environment),
                patch.dict(os.environ, environment, clear=True),
            ):
                # When the capability resolves its state location.
                result = self.adapter._state_path()
                # Then precedence is identical across capabilities.
                self.assertEqual(expected, result)

    def test_fixture_cli_is_deterministic(self) -> None:
        command = [sys.executable, str(ADAPTER_PATH), "--fixture"]
        first = subprocess.run(
            command, cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
        second = subprocess.run(
            command, cwd=REPO_ROOT, check=True, capture_output=True, text=True
        )
        self.assertEqual(first.stdout, second.stdout)
        output = json.loads(first.stdout)
        self.assertTrue(output["fixture_contract_passed"])
        self.assertFalse(output["admission_passed"])
        self.assertEqual("synthetic-fixture", output["verification_mode"])
        self.assertTrue(
            all(
                item["status"] == "synthetic-fixture-match"
                for item in output["citations"]
            )
        )
        self.assertNotIn("fixture-credential", first.stdout)

        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["input"]["citations"][0]["candidate"]["quoted_text"] = (
            "공식 조문에 존재하지 않는 충분히 긴 인용문입니다."
        )
        with tempfile.TemporaryDirectory() as directory:
            blocked_path = Path(directory) / "blocked.json"
            blocked_path.write_text(
                json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
            )
            blocked = subprocess.run(
                command + ["--fixture-path", str(blocked_path)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(1, blocked.returncode)
        blocked_output = json.loads(blocked.stdout)
        self.assertFalse(blocked_output["fixture_contract_passed"])
        self.assertFalse(blocked_output["admission_passed"])

    def test_cli_parser_never_reflects_unrecognized_sensitive_arguments(self) -> None:
        # Given a caller accidentally passing sensitive material as an unknown option.
        marker = "user@example.org"
        # When the real CLI rejects the arguments before any runtime construction.
        result = subprocess.run(
            [sys.executable, str(ADAPTER_PATH), "--fixture", f"--unknown={marker}"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Then the input error is stable and non-reflecting.
        self.assertEqual(2, result.returncode)
        self.assertNotIn(marker, result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
