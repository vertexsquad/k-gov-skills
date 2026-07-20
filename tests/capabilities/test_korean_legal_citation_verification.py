from __future__ import annotations

import copy
from datetime import date, timedelta
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_PATH = REPO_ROOT / "kgov_runtime" / "capabilities" / "korean_legal_citation_verification.py"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "capabilities" / "korean-legal-citation-verification.json"


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
    spec = importlib.util.spec_from_file_location("legal_citation_adapter", ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = _load_adapter()

    def setUp(self) -> None:
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
                                                {"목번호": "가. ", "목내용": "가. 첫 번째 목의 공식 내용입니다."},
                                                {"목번호": "나. ", "목내용": "나. 두 번째 목의 공식 내용입니다."},
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
                return _Response({"Law": "일치하는 판례가 없습니다. 판례명을 확인하여 주십시오."})
            return _Response(self.prec_detail)
        if path.endswith("lawService.do") and target == "eflawjosub":
            return _Response(self.law_detail)
        raise AssertionError(request.full_url)

    def test_live_official_statute_and_precedent_are_admitted(self) -> None:
        self.assertEqual(
            self.adapter._normalized_text("개인정보의 수집·이용 목적"),
            self.adapter._normalized_text("  1. 개인정보의 수집ㆍ이용 목적  "),
        )
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.verify_citations(self.valid, opener=self.opener)

        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["admission_passed"])
        self.assertEqual(2, result["verified_count"])
        self.assertEqual(0, result["blocked_count"])
        self.assertEqual(
            ["verified-official-live-match", "verified-official-live-match"],
            [item["status"] for item in result["citations"]],
        )
        self.assertEqual("합성법률 제1조 제2항 제1호", result["citations"][0]["verified_citation"])
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
            subitem_result = self.adapter.verify_citations(subitem, opener=subitem_opener)
        self.assertTrue(subitem_result["admission_passed"])
        self.assertTrue(subitem_result["citations"][0]["verified_citation"].endswith("다목"))

    def test_caller_supplied_official_record_is_rejected(self) -> None:
        fabricated = copy.deepcopy(self.valid)
        fabricated["citations"][0]["official"] = {
            "law_name": "존재하지않는법",
            "text": "서로 맞춘 가짜 원문입니다.",
        }
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.adapter.verify_citations(fabricated, opener=self.opener)

    def test_wrong_locator_quote_and_case_metadata_are_blocked(self) -> None:
        wrong = copy.deepcopy(self.valid)
        wrong["citations"][0]["candidate"]["quoted_text"] = (
            "첫 번째 항의 서로 다른 공식 내용입니다."
        )
        wrong["citations"][1]["candidate"]["case_number"] = "2099다99999"
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.verify_citations(wrong, opener=self.opener)

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
            missing = self.adapter.verify_citations(payload, opener=self.opener)
        self.assertFalse(missing["admission_passed"])
        self.assertEqual("official-source-not-found", missing["citations"][0]["status"])

        statute_only = copy.deepcopy(self.valid)
        statute_only["citations"] = [statute_only["citations"][0]]

        def law_not_found(request, timeout=0):
            parsed = urlsplit(request.full_url)
            query = parse_qs(parsed.query)
            if parsed.path.endswith("lawSearch.do") and query.get("target") == ["eflaw"]:
                return _Response({"LawSearch": {"totalCnt": "0", "law": None}})
            return self.opener(request, timeout)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            missing_law = self.adapter.verify_citations(statute_only, opener=law_not_found)
        self.assertFalse(missing_law["admission_passed"])
        self.assertEqual("official-source-not-found", missing_law["citations"][0]["status"])

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
            result = self.adapter.verify_citations(future_payload, opener=future_opener)
        self.assertFalse(result["admission_passed"])
        self.assertIn("decision_date_after_as_of_date", result["citations"][0]["mismatched_fields"])

    def test_search_requires_manual_selection_and_never_echoes_pii_or_credential(self) -> None:
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            result = self.adapter.search_precedents(
                {"nb": "2026다12345", "display": 2}, opener=self.opener
            )
        self.assertEqual("ambiguous-candidates-manual-selection-required", result["selection_status"])
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
            with self.assertRaisesRegex(ValueError, "count is inconsistent"):
                self.adapter.search_precedents({"display": 1}, opener=inconsistent_opener)

        short_precedent_page = copy.deepcopy(self.prec_search)
        short_precedent_page["PrecSearch"]["prec"] = short_precedent_page["PrecSearch"]["prec"][:1]

        def short_precedent_page_opener(request, timeout=0):
            return _Response(short_precedent_page)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "count is inconsistent"):
                self.adapter.search_precedents(
                    {"display": 100}, opener=short_precedent_page_opener
                )

        inconsistent_law = copy.deepcopy(self.law_search)
        inconsistent_law["LawSearch"]["totalCnt"] = "1"

        def inconsistent_law_opener(request, timeout=0):
            return _Response(inconsistent_law)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "count is inconsistent"):
                self.adapter.search_laws({"display": 1}, opener=inconsistent_law_opener)

        short_law_page = copy.deepcopy(self.law_search)
        short_law_page["LawSearch"]["totalCnt"] = "2"
        short_law_page["LawSearch"]["law"] = short_law_page["LawSearch"]["law"][:1]

        def short_law_page_opener(request, timeout=0):
            return _Response(short_law_page)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "count is inconsistent"):
                self.adapter.search_laws({"display": 100}, opener=short_law_page_opener)

        history_records = []
        for index in range(100):
            record = copy.deepcopy(self.law_search["LawSearch"]["law"][0])
            record["법령일련번호"] = str(1000 + index)
            record["시행일자"] = (date(2025, 1, 1) + timedelta(days=index)).strftime("%Y%m%d")
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
            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.adapter.verify_citations(statute_only, opener=duplicate_history_opener)

        reflected = copy.deepcopy(self.law_search)
        reflected["LawSearch"]["law"][0]["현행연혁코드"] = "fixture-secret"

        def reflected_opener(request, timeout=0):
            return _Response(reflected)

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "credential"):
                self.adapter.search_laws({"display": 100}, opener=reflected_opener)

        reflected["LawSearch"]["law"][0]["현행연혁코드"] = "fixture%2fsecret"
        with patch.dict(os.environ, {"LAW_OC": "fixture/secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "credential"):
                self.adapter.search_laws({"display": 100}, opener=reflected_opener)

    def test_unicode_pii_and_output_controls_are_rejected(self) -> None:
        pii = copy.deepcopy(self.valid)
        pii["citations"][0]["candidate"]["law_name"] = "０１０－１２３４－５６７８"
        with self.assertRaisesRegex(ValueError, "direct identifier"):
            self.adapter.verify_citations(pii, opener=self.opener)

        separator = copy.deepcopy(self.valid)
        separator["citations"][0]["candidate"]["law_name"] = "합성법률\u2028위조근거"
        with self.assertRaisesRegex(ValueError, "single-line"):
            self.adapter.verify_citations(separator, opener=self.opener)

        bidi = copy.deepcopy(self.valid)
        bidi["citations"][1]["candidate"]["court"] = "대법원\u202e위조"
        with self.assertRaisesRegex(ValueError, "single-line"):
            self.adapter.verify_citations(bidi, opener=self.opener)

        hidden_pii = copy.deepcopy(self.valid)
        hidden_pii["citations"][1]["candidate"]["quoted_text"] = (
            "연락처 010\u200b-1234-5678 포함된 충분히 긴 인용문입니다."
        )
        with self.assertRaisesRegex(ValueError, "Unicode"):
            self.adapter.verify_citations(hidden_pii, opener=self.opener)

        for spaced_identifier in (
            "연락처 010  1234  5678 포함된 충분히 긴 인용문입니다.",
            "연락처 010 - 1234 - 5678 포함된 충분히 긴 인용문입니다.",
            "주민번호 900101  1234567 포함된 충분히 긴 인용문입니다.",
        ):
            spaced = copy.deepcopy(self.valid)
            spaced["citations"][1]["candidate"]["quoted_text"] = spaced_identifier
            with self.assertRaisesRegex(ValueError, "direct identifier"):
                self.adapter.verify_citations(spaced, opener=self.opener)

    def test_official_schema_and_error_envelopes_fail_closed(self) -> None:
        def empty_detail(request, timeout=0):
            return _Response({"PrecService": {}})

        payload = copy.deepcopy(self.valid)
        payload["citations"] = [payload["citations"][1]]
        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "official precedent detail schema"):
                self.adapter.verify_citations(payload, opener=empty_detail)

        def api_error(request, timeout=0):
            return _Response({"Law": "인증값이 올바르지 않습니다."})

        with patch.dict(os.environ, {"LAW_OC": "fixture-secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "official API error"):
                self.adapter.verify_citations(payload, opener=api_error)

    def test_fixture_cli_is_deterministic(self) -> None:
        command = [sys.executable, str(ADAPTER_PATH), "--fixture"]
        first = subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
        second = subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
        self.assertEqual(first.stdout, second.stdout)
        output = json.loads(first.stdout)
        self.assertTrue(output["fixture_contract_passed"])
        self.assertFalse(output["admission_passed"])
        self.assertEqual("synthetic-fixture", output["verification_mode"])
        self.assertTrue(
            all(item["status"] == "synthetic-fixture-match" for item in output["citations"])
        )
        self.assertNotIn("fixture-credential", first.stdout)

        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture["input"]["citations"][0]["candidate"]["quoted_text"] = (
            "공식 조문에 존재하지 않는 충분히 긴 인용문입니다."
        )
        with tempfile.TemporaryDirectory() as directory:
            blocked_path = Path(directory) / "blocked.json"
            blocked_path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
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



if __name__ == "__main__":
    unittest.main()
