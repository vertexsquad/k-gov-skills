#!/usr/bin/env python3
"""Validate the domain-owned Skill topology, capability runtime, and generated docs."""

from __future__ import annotations

import ipaddress
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final, TypeAlias
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GROUP_ORDER = (
    "국가운영",
    "법무·치안",
    "안전·국방",
    "사회서비스",
    "농림·해양·환경",
    "국토·산업",
    "과학·디지털",
    "문화·지식",
    "지역·생활행정",
)

DOMAIN_REQUIRED_KEYS = {"domain", "group", "evidence", "skills"}
SKILL_REQUIRED_KEYS = {"name", "title", "capability", "role", "reference_skills", "boundary"}
CAPABILITY_REQUIRED_KEYS = {
    "slug",
    "locale",
    "jurisdiction",
    "service",
    "credential_class",
    "proxy_mode",
    "side_effect_class",
    "manual_handoff_gate",
    "source_provenance",
    "execution_status",
    "live_smoke",
    "source_policy_ids",
    "runtime_contract_id",
}
EVIDENCE = {"direct", "adjacent", "new", "sensitive"}
BOUNDARIES = {"read-only", "draft-only", "manual-review-only"}
ROLES = {"primary", "additional"}
CREDENTIAL_CLASSES = {"none", "user-held", "operator-held", "mixed"}
PROXY_MODES = {"none", "optional", "required", "mixed"}
SIDE_EFFECT_CLASSES = {"read-only", "document-read", "draft-only"}
EXECUTION_STATUSES = {"planned", "fixture-verified", "live-verified", "blocked"}
LIVE_SMOKE_STATUSES = {"not-run", "passed", "failed", "blocked"}
TARGET_SKILLS_PER_DOMAIN = 5
WAVE_ONE_TASK_CHECKS = {
    "national-subsidy-project-evidence-review": (
        "사업·회계연도·소관기관·지원 근거를 주장 단위로 분리",
        "공식 법령·사업공고·재정자료 URL과 조회일을 보존",
        "지원대상 확정·교부결정·정책평가는 담당기관 승인으로 이관",
    ),
    "audit-action-plan-evidence-review": (
        "지적사항별 원인·조치·담당·기한·증빙 공백을 분리",
        "완료·예정 상태와 근거 URL·문서유형을 구분",
        "이행완료 판단·제출·수용 여부는 감사 담당자 승인",
    ),
    "immigration-statistics-policy-brief": (
        "통계 지표의 기준기간·대상·체류자격·단위를 분리",
        "공식 출입국·KOSIS 자료의 URL과 조회일을 보존",
        "체류자격·입국 허가·정책 해석은 담당기관 검토로 이관",
    ),
    "police-crime-statistics-brief": (
        "범죄유형·지역·기간·집계 단위를 구분",
        "공식 통계표 코드·조회일·통계 기준을 보존",
        "치안 수준·수사·개별 위험도 판단은 경찰 담당 검토로 이관",
    ),
    "disaster-response-plan-evidence-review": (
        "재난유형·대응단계·기관역할·연락체계·행동요령을 분리",
        "기준시각·공식 지침·공개 상황자료와 증빙 공백을 구분",
        "경보발령·대피·출동 판단은 공식기관 승인으로 이관",
    ),
    "school-facility-safety-plan-review": (
        "시설구역·위험요인·점검주기·담당·대응조치를 분리",
        "학생·보호자 개인정보 원문을 제외하고 공개 지침 근거를 보존",
        "시설 안전판단·긴급조치·계획 승인은 학교 담당자에게 이관",
    ),
    "welfare-eligibility-evidence-check": (
        "급여·서비스별 기준일과 소득·가구·연령 조건을 비식별 상태로 분리",
        "공식 법령·사업안내 URL과 조회일 및 상충 근거를 보존",
        "수급자격·지급액·신청 가능 여부는 담당기관 판단으로 이관",
    ),
}
WAVE_TWO_SKILL_CONTRACTS = {
    "고용노동": {
        "name": "industrial-accident-statistics-brief",
        "title": "산업재해 통계 근거 브리프",
        "capability": "kosis-official-statistics",
        "role": "additional",
        "reference_skills": (),
        "boundary": "draft-only",
        "task_checks": (
            "산업재해 지표의 기준기간·업종·재해유형·집계단위를 분리",
            "공식 고용노동·KOSIS 통계표 코드·조회일·통계 기준을 보존",
            "산재 인정·사업장 위험도·제재 판단은 담당기관 검토로 이관",
        ),
    },
    "토목시설": {
        "name": "infrastructure-maintenance-evidence-review",
        "title": "기반시설 유지관리 근거 검토",
        "capability": "administrative-document-draft-review",
        "role": "additional",
        "reference_skills": (),
        "boundary": "draft-only",
        "task_checks": (
            "시설·구간·점검일·손상유형·조치상태·증빙을 분리",
            "공식 기준·점검보고서·사진·도면 참조와 증빙 공백을 구분",
            "시설 안전등급·통제·보수 우선순위는 기술자·관리기관 승인으로 이관",
        ),
    },
    "건축": {
        "name": "building-code-citation-check",
        "title": "건축기준 조문 인용 점검",
        "capability": "korean-legal-citation-verification",
        "role": "additional",
        "reference_skills": (),
        "boundary": "draft-only",
        "task_checks": (
            "용도·규모·지역·행위별 적용 법령 후보와 기준시점을 분리",
            "국가법령정보센터의 조문·시행일·인용문과 공식 URL을 보존",
            "설계 적합성·허가 가능 여부·법적 해석은 건축사·허가권자 검토로 이관",
        ),
    },
    "전산": {
        "name": "public-it-security-checklist-review",
        "title": "공공 정보시스템 보안 체크리스트 검토",
        "capability": "public-it-project-procedure-review",
        "role": "additional",
        "reference_skills": (),
        "boundary": "draft-only",
        "task_checks": (
            "시스템·데이터등급·위협·통제·검증증빙을 항목별로 분리",
            "공식 보안·개인정보·정보화 지침의 버전·URL·조회일을 보존",
            "보안 적합성·취약점 수용·운영 승인은 보안책임자 검토로 이관",
        ),
    },
    "기록관리": {
        "name": "records-retention-schedule-review",
        "title": "기록물 보존기간표 검토",
        "capability": "public-records-lifecycle-review",
        "role": "additional",
        "reference_skills": (),
        "boundary": "draft-only",
        "task_checks": (
            "기록물계열·업무기능·보존기산점·보존기간 후보를 분리",
            "공식 기록관리기준·법령 URL과 조회일 및 근거 공백을 보존",
            "보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인으로 이관",
        ),
    },
    "지방의회": {
        "name": "local-council-budget-bill-comparison",
        "title": "지방의회 예산안 비교 브리프",
        "capability": "public-policy-evidence-pack",
        "role": "additional",
        "reference_skills": (),
        "boundary": "draft-only",
        "task_checks": (
            "예산안·수정안·심사보고서의 회계연도·사업·금액·근거를 분리",
            "공식 의안·회의록·예산서 URL과 조회일 및 문서 버전을 보존",
            "증감 적정성·재정 영향·의결 판단은 지방의회 담당자 검토로 이관",
        ),
    },
}
WAVE_THREE_SKILL_CONTRACTS = {
    "입법": (
        {
            "name": "bill-comparison-impact-brief",
            "title": "법안 비교·영향 근거 브리프",
            "capability": "korean-law-bill-research",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "법안·대안·수정안별 의안번호·기준일·처리단계·조문 차이를 분리",
                "국가법령정보·국회 공개정보의 공식 URL·조회일·문서 버전을 보존",
                "법적 효력·정책 영향·채택 여부 판단은 입법·법무 담당자 검토로 이관",
            ),
        },
        {
            "name": "committee-minutes-evidence-pack",
            "title": "상임위원회 회의록 근거 팩",
            "capability": "korean-law-bill-research",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "위원회·회기·안건·회의일·의결 결과를 문서 단위로 분리",
                "공식 회의록·심사보고서·의안정보 URL·공개일·조회일을 보존",
                "발언 취지·정치적 평가·의결 해석은 입법 담당자 검토로 이관",
            ),
        },
    ),
    "교육": (
        {
            "name": "education-statistics-brief",
            "title": "교육통계 근거 브리프",
            "capability": "kosis-official-statistics",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "지표명·학제·지역·학년도·분모·단위를 분리",
                "KOSIS 통계표 코드·작성기관·수록기간·조회일·개정 상태를 보존",
                "학교·학생 평가·정책 효과·자원배분 판단은 교육 담당기관 검토로 이관",
            ),
        },
        {
            "name": "school-policy-document-review",
            "title": "학교 정책문서 검토",
            "capability": "administrative-document-draft-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "정책 대상·적용기관·시행일·의무·권고·근거 문서를 분리",
                "교육부·법령 공식 URL·조회일·문서 버전과 근거 공백을 보존",
                "법적 해석·학교별 적용·공문 확정·발송은 교육 담당자 승인으로 이관",
            ),
        },
    ),
    "국토교통": (
        {
            "name": "transport-policy-project-evidence-pack",
            "title": "교통정책·사업 근거 팩",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "사업·노선·구간·단계·예산·일정 주장을 항목별로 분리",
                "공식 1차 자료로 입력된 URL·조회일·문서 버전과 상충·미수집 근거를 구분",
                "사업 타당성·우선순위·예산 승인·노선 결정은 담당기관 검토로 이관",
            ),
        },
        {
            "name": "traffic-safety-statistics-brief",
            "title": "교통안전 통계 근거 브리프",
            "capability": "kosis-official-statistics",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "기준기간·지역·도로유형·사고유형·지표·분모·단위를 분리",
                "KOSIS 통계표 코드·작성기관·조회일·통계 기준·개정 상태를 보존",
                "위험도 순위·단속·시설 개선 우선순위는 교통안전 담당기관 검토로 이관",
            ),
        },
    ),
}
WAVE_FOUR_SKILL_CONTRACTS = {
    "사법": (
        {
            "name": "judgment-citation-evidence-pack",
            "title": "판결 인용 근거 팩",
            "capability": "korean-legal-citation-verification",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "법원·사건번호·선고일·판례 원문 식별자와 정확한 인용 위치를 분리",
                "국가법령정보 공식 원문 URL·조회일·적용 법령 버전과 불일치·복수 후보를 보존",
                "법률적 효력·사안 적용·소송 제출 여부는 법무 담당자 최종 검토로 이관",
            ),
        },
        {
            "name": "court-statistics-evidence-brief",
            "title": "법원 통계 근거 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "작성기관·통계표 또는 보고서 식별자·기준기간·분모·단위·절차 단계를 분리",
                "공식 자료로 입력된 URL·공표일·조회일·문서 버전과 상충·미수집 근거를 구분",
                "사건 결과 예측·법원 또는 재판부 평가·정책 판단은 사법 담당자 검토로 이관",
            ),
        },
    ),
    "보건의료": (
        {
            "name": "healthcare-policy-statistics-brief",
            "title": "보건의료 정책통계 브리프",
            "capability": "kosis-official-statistics",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "지표명·지역·기간·기관 또는 질환 범주·분모·단위·집계 기준을 분리",
                "KOSIS 통계표 코드·작성기관·수록기간·조회일·개정 상태와 결측을 보존",
                "진단·치료·기관 서열화·정책 효과 판단은 보건의료 담당기관 검토로 이관",
            ),
        },
        {
            "name": "medical-benefit-criteria-evidence-pack",
            "title": "급여기준 근거 팩",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "급여기준 주장을 대상·조건·예외·시행일·적용 시점 단위로 분리",
                "공식 자료로 입력된 URL·조회일·문서 버전·개정 상태와 상충·미수집 근거를 구분",
                "환자별 급여 여부·진료·처방·청구 판단은 의료전문가와 담당기관 검토로 이관",
            ),
        },
    ),
    "식품의약": (
        {
            "name": "food-drug-recall-evidence-brief",
            "title": "식품·의약품 회수 근거 브리프",
            "capability": "welfare-health-safety-research",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "제품명·업체·품목 식별자·회수 등급·대상 제조번호·유통기한을 분리",
                "식약처·공공데이터 응답의 공식 endpoint·조회일·공표일·정정 상태와 미확인 항목을 보존",
                "복약·섭취 중단·행정처분·현장 회수 집행은 식약처·전문가·담당자 확인으로 이관",
            ),
        },
        {
            "name": "regulatory-notice-comparison-review",
            "title": "식품의약 규제고시 비교 검토",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "고시·공고·행정예고별 발행기관·문서번호·공포일·시행일·적용 대상을 분리",
                "공식 자료로 입력된 URL·조회일·문서 버전과 변경 전후·경과조치·상충·미수집 근거를 구분",
                "법적 효력·개별 사안 적용·기관 대응·발송·집행은 식품의약 담당자 검토로 이관",
            ),
        },
    ),
}
WAVE_FIVE_SKILL_CONTRACTS = {
    "통계": (
        {
            "name": "official-statistics-methodology-evidence-review",
            "title": "공식통계 방법론 근거 검토",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "통계명·통계표 코드·작성기관·작성목적·작성주기·조사대상·모집단·표본·가중치를 분리",
                "공식 자료로 입력된 URL·공표일·조회일·방법론 버전·개정 이력과 상충·미수집 근거를 구분",
                "방법론 적합성·통계 품질등급·정책 적용 판단은 통계 담당자 최종 검토로 이관",
            ),
        },
        {
            "name": "statistical-release-evidence-brief",
            "title": "통계 공표 근거 브리프",
            "capability": "kosis-official-statistics",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "통계표 코드·지표·분류·기준기간·분모·단위·잠정 또는 확정 상태를 분리",
                "KOSIS 통계표 코드·작성기관·수록기간·공표일·조회일·개정 상태·결측·시계열 단절을 보존",
                "추세 해석·인과관계·정책효과·공식 입장 판단은 통계 담당자 검토로 이관",
            ),
        },
    ),
    "소방": (
        {
            "name": "fire-safety-standard-evidence-pack",
            "title": "소방안전 기준 근거 팩",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "시설유형·점검대상·적용 법령·고시·안전기준·시행일을 분리",
                "공식 자료로 입력된 URL·문서번호·공표일·조회일·개정 상태와 상충·미수집 근거를 구분",
                "적합·부적합 판정·시정명령·과태료·현장 점검·안전조치는 소방 담당기관과 전문가에게 이관",
            ),
        },
        {
            "name": "fire-response-statistics-brief",
            "title": "소방 대응통계 브리프",
            "capability": "kosis-official-statistics",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "화재유형·지역·기준기간·출동 또는 진압 단계·지표·분모·단위를 분리",
                "KOSIS 통계표 코드·작성기관·공표일·조회일·개정 상태·결측을 보존",
                "위험도 순위·인력 또는 장비 배치·현장 대응·예방정책 우선순위는 소방 담당기관에 이관",
            ),
        },
    ),
    "과학기술": (
        {
            "name": "national-rd-program-evidence-brief",
            "title": "국가 R&D 사업 근거 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "사업명·사업 또는 과제 식별자·주관기관·공고번호·기간·예산·추진상태를 분리",
                "공식 자료로 입력된 NTIS·부처 URL·공표일·조회일·문서 버전과 상충·미수집 근거를 구분",
                "지원자격·선정·평가·예산배분·과제 수행 판단은 연구개발 담당기관에 이관",
            ),
        },
        {
            "name": "technology-impact-evidence-pack",
            "title": "과학기술 영향 근거 팩",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "기술·정책 주장별 기준선·지표·기간·대상·단위와 상관 또는 인과 표현을 분리",
                "공식 자료로 입력된 URL·발행기관·공표일·조회일·방법론·문서 버전과 상충·미수집 근거를 구분",
                "인과효과·기술성숙도·투자·규제·사업 우선순위 판단은 과학기술 담당자와 전문가 검토로 이관",
            ),
        },
    ),
}
WAVE_SIX_SKILL_CONTRACTS = {
    "선거관리": (
        {
            "name": "election-law-procedure-evidence-review",
            "title": "선거법·절차 근거 검토",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "선거유형·선거일·절차단계·행위주체·적용 법령·조문·기준시점을 분리",
                "공식 자료로 입력된 선관위·국가법령정보 URL·문서 식별자·조회일·시행일·개정 상태와 상충·미수집 근거를 구분",
                "위법성·후보자격·등록수리·제재·이의처리 판단은 선거관리위원회와 법무 담당자 검토로 이관",
            ),
        },
        {
            "name": "election-result-statistics-evidence-brief",
            "title": "선거결과 통계 근거 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "선거종류·회차·선거구·후보 또는 정당·기준일·득표수·득표율·투표율·분모·무효표를 분리",
                "공식 자료로 입력된 선거통계 URL·공표일·조회일·정정 상태와 상충·미수집 근거를 구분",
                "당락·재검표·선거무효·정치적 평가·인과관계 판단은 선거관리위원회와 담당자 검토로 이관",
            ),
        },
    ),
    "특허": (
        {
            "name": "patent-claim-citation-evidence-review",
            "title": "특허 청구항 인용 근거 검토",
            "capability": "patent-prior-art-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "출원번호·공개번호·등록번호·청구항 버전·청구항 요소·인용 문헌번호·인용 위치를 분리",
                "KIPRIS·특허청 공식 URL·공개일·조회일·공개 또는 등록 상태와 미확인·복수 후보를 보존",
                "신규성·진보성·침해·유효성·출원전략 판단은 변리사와 특허 담당자 검토로 이관",
            ),
        },
        {
            "name": "ip-policy-statistics-evidence-brief",
            "title": "지식재산 정책통계 근거 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "권리유형·정책 또는 사업·기준기간·출원인 범주·지역·건수·분모·단위를 분리",
                "공식 자료로 입력된 특허청·KIPRIS URL·보고서 또는 통계표 식별자·공표일·조회일·개정 상태와 결측을 구분",
                "인과관계·정책효과·산업경쟁력·지원 또는 규제 우선순위 판단은 지식재산 담당자 검토로 이관",
            ),
        },
    ),
    "사이버보안": (
        {
            "name": "privacy-impact-evidence-review",
            "title": "개인정보 영향평가 근거 검토",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "시스템·처리업무·개인정보 유형·처리목적·정보주체·법적근거·처리흐름·보유기간·제3자 제공을 분리",
                "공식 자료로 입력된 개인정보위·국가법령정보 URL·가이드 또는 법령 버전·조회일과 상충·미수집 근거를 구분",
                "영향평가 실시대상·적합성·법적준수·승인 판단은 개인정보 보호책임자와 전문기관 검토로 이관",
            ),
        },
        {
            "name": "cyber-incident-response-plan-evidence-review",
            "title": "사이버 침해사고 대응계획 근거 검토",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "사고유형·시스템경계·자산·담당역할·보고경로·격리·복구·로그보존 항목을 분리",
                "공식 자료로 입력된 KISA·국가 또는 기관 보안기준 URL·문서버전·시행일·조회일과 상충·미수집 근거를 구분",
                "사고등급·차단·격리·포렌식·외부신고·현장대응 실행은 보안책임자와 관할기관 검토로 이관",
            ),
        },
    ),
}
WAVE_SEVEN_SKILL_CONTRACTS = {
    "관세": (
        {
            "name": "customs-origin-document-precheck",
            "title": "원산지 증빙서류 사전점검",
            "capability": "regulated-trade-procedure-precheck",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "거래·품목·HS 코드·협정·원산지 기준·증빙서류·기준시점을 분리",
                "관세청·UNI-PASS·FTA 포털 공식 URL·문서 식별자·발급 또는 조회일·유효기간과 누락·상충 근거를 구분",
                "원산지 판정·특혜관세 적용·신고·제출·통관·제재 판단은 관세사와 세관 담당자 검토로 이관",
            ),
        },
        {
            "name": "customs-trade-statistics-brief",
            "title": "관세 무역통계 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "기준기간·수출입 구분·상대국·HS 코드·수량·금액·단위·정정 상태를 분리",
                "관세청 무역통계 공식 URL·통계표 또는 품목 식별자·공표일·조회일·잠정 또는 확정 상태와 결측·개정을 구분",
                "추세·인과관계·정책효과·세율 또는 통관 판단은 관세 통계 담당자 검토로 이관",
            ),
        },
    ),
    "외교": (
        {
            "name": "treaty-diplomatic-document-source-check",
            "title": "조약·외교문서 출처 점검",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "조약명·조약번호·당사국·서명일·비준일·발효일·언어·문서 버전을 분리",
                "외교부 조약정보 안내(https://www.mofa.go.kr/www/wpge/m_24251/contents.do)와 조약정보시스템(https://treatyweb.mofa.go.kr/) 공식 URL·문서 식별자·공표일·조회일·개정 또는 종료 상태와 상충·미수집 근거를 구분",
                "조약의 효력·법적 해석·외교적 입장·국제법 판단은 외교부와 법무 담당자 검토로 이관",
            ),
        },
        {
            "name": "overseas-safety-country-brief",
            "title": "해외안전 국가 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "국가·지역·여행경보 단계·안전공지 유형·기준일·긴급 연락처를 분리",
                "외교부 해외안전여행 공식 URL·공표일·조회일·갱신 상태와 상충·미수집 근거를 구분",
                "여행·철수·대피·영사조력·현장 긴급대응 판단은 외교부와 관할 공관으로 이관",
            ),
        },
    ),
    "통일": (
        {
            "name": "inter-korean-policy-timeline-evidence-pack",
            "title": "남북관계 정책연표 근거 팩",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "사건·정책·행위주체·공식문서·발생일·공표일·진행 상태를 연표 항목별 분리",
                "통일부 공식 URL·문서 식별자·공표일·조회일·문서 버전과 상충·미수집 근거를 구분",
                "정부 공식입장·법적 또는 정치적 평가·관계 전망 판단은 통일부와 담당 연구자 검토로 이관",
            ),
        },
        {
            "name": "dmz-policy-source-brief",
            "title": "DMZ 정책 출처 브리프",
            "capability": "public-policy-evidence-pack",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "지역·시설·사업·적용 규정·출입 조건·기준일·운영 상태를 분리",
                "통일부와 관계기관 공식 URL·문서 식별자·공표일·조회일·개정 상태와 근거 공백을 구분",
                "출입 승인·군사보안·현장 운영·환경 또는 법적 판단은 관할 기관과 담당자 검토로 이관",
            ),
        },
    ),
}
WAVE_TWO_CAPABILITY_CONTRACTS = {
    "public-records-lifecycle-review": {
        "service": "공공기록물 분류·보존기간·이관·폐기 검토 admission",
        "credential_class": "none",
        "proxy_mode": "none",
        "side_effect_class": "draft-only",
        "manual_handoff_gate": "보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인",
        "source_provenance": ("https://www.archives.go.kr/", "https://www.law.go.kr/"),
        "execution_status": "fixture-verified",
        "live_smoke": "not-run",
    }
}
WAVE_SEVEN_CAPABILITY_CONTRACTS = {
    "regulated-trade-procedure-precheck": {
        "service": "관세 원산지·통관 증빙서류 사전점검 admission",
        "credential_class": "none",
        "proxy_mode": "none",
        "side_effect_class": "draft-only",
        "manual_handoff_gate": "원산지 판정·특혜관세 적용·신고·제출·통관·제재 판단은 관세사와 세관 담당자가 승인",
        "source_provenance": (
            "https://www.customs.go.kr/ftaportalkor/main.do",
            "https://unipass.customs.go.kr/csp/index.do",
        ),
        "execution_status": "fixture-verified",
        "live_smoke": "not-run",
    }
}
_EXPECTED_CAPABILITY_SERVICE_AND_PROVENANCE: Final = {
    "public-document-hwpx": ("local HWPX documents", ("https://www.hancom.com/",)),
    "korean-law-bill-research": ("국가법령정보·국회 공개정보", ("https://www.law.go.kr/", "https://open.assembly.go.kr/")),
    "kosis-official-statistics": ("KOSIS OpenAPI", ("https://kosis.kr/openapi/",)),
    "public-procurement-research": ("G2B·S2B·D2B 공개조달", ("https://www.g2b.go.kr/", "https://www.data.go.kr/")),
    "disaster-geospatial-brief": ("기상·대기·수위·응급 공공데이터", ("https://www.weather.go.kr/", "https://www.data.go.kr/")),
    "welfare-health-safety-research": ("복지·연금·보건·식품의약 공공데이터", ("https://www.data.go.kr/",)),
    "land-housing-geospatial-research": ("토지·주택·교통·공간 공공데이터", ("https://www.data.go.kr/",)),
    "official-source-research": ("한국 공공기관 공식 웹·공시", ("https://www.gov.kr/",)),
    "civil-complaint-triage-draft": ("국민신문고·기관 민원 분류 및 답변 초안 admission", ("https://www.epeople.go.kr/", "https://www.acrc.go.kr/")),
    "administrative-document-draft-review": ("비식별 행정문서 초안·검토 admission", ("https://www.archives.go.kr/", "https://www.bai.go.kr/", "https://www.elis.go.kr/", "https://gnews.gg.go.kr/", "https://www.law.go.kr/", "https://www.moe.go.kr/", "https://www.mois.go.kr/", "https://www.open.go.kr/", "https://www.suwon.go.kr/")),
    "public-policy-evidence-pack": ("공식자료·법령·통계 evidence-pack orchestration", ("https://www.gov.kr/", "https://www.law.go.kr/", "https://kosis.kr/openapi/")),
    "korean-legal-citation-verification": ("국가법령정보 법령 조문·판례 조회 및 인용 정합성 검증", ("https://www.law.go.kr/", "https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdListGuide", "https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdJoListGuide", "https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precListGuide", "https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precInfoGuide")),
    "public-ai-governance-review": ("공공 AI 영향평가·위험관리계획 초안 admission", ("https://www.law.go.kr/", "https://www.msit.go.kr/", "https://www.pipc.go.kr/")),
    "public-it-project-procedure-review": ("공공 정보화사업 단계·산출물 절차 점검 admission", ("https://www.mois.go.kr/", "https://www.law.go.kr/")),
    "public-record-disclosure-redaction-review": ("공공기록 공개·비공개·부분공개·마스킹 검토 admission", ("https://www.open.go.kr/", "https://www.archives.go.kr/")),
    "local-ordinance-draft-review": ("자치법규 상위법·조문구조·입안점검 admission", ("https://www.elis.go.kr/", "https://www.law.go.kr/")),
    "construction-standard-bim-compliance-precheck": ("KCSC·BIM 기준 사전점검 admission", ("https://www.kcsc.re.kr/",)),
    "building-permit-document-precheck": ("건축 인허가 제출 전 서류 누락 점검 admission", ("https://www.eais.go.kr/", "https://www.law.go.kr/")),
    "official-notice-multilingual-translation-review": ("공공안내 다국어 번역·용어 일관성 검토 admission", ("https://www.mois.go.kr/", "https://www.korean.go.kr/")),
    "patent-prior-art-evidence-pack": ("KIPRIS 공식문헌 조회·선행기술 청구항-근거표 admission", ("https://www.kipris.or.kr/", "https://www.kipo.go.kr/")),
    "public-records-lifecycle-review": ("공공기록물 분류·보존기간·이관·폐기 검토 admission", ("https://www.archives.go.kr/", "https://www.law.go.kr/")),
    "regulated-trade-procedure-precheck": ("관세 원산지·통관 증빙서류 사전점검 admission", ("https://www.customs.go.kr/ftaportalkor/main.do", "https://unipass.customs.go.kr/csp/index.do")),
}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
JSONValue: TypeAlias = "None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]"
_SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
_SCHEMA_KEYWORDS = {
    "type",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "format",
}
_SCHEMA_APPLICABILITY = {
    "object": {"required", "properties", "additionalProperties"},
    "array": {"items", "minItems", "maxItems"},
    "string": {"minLength", "maxLength", "format"},
    "integer": {"minimum", "maximum"},
    "number": {"minimum", "maximum"},
    "boolean": set(),
    "null": set(),
}
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_DATE_TIME = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


@dataclass(frozen=True, slots=True)
class StrictJsonError(Exception):
    code: str

    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True)
class _DuplicateJsonKeyError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _NonFiniteJsonNumberError(Exception):
    pass


def _pointer_child(pointer: str, member: str | int) -> str:
    escaped = str(member).replace("~", "~0").replace("/", "~1")
    return f"{pointer}/{escaped}"


def _diagnostic(code: str, pointer: str) -> str:
    encoded_pointer = json.dumps(pointer, ensure_ascii=False)
    encoded_pointer = "".join(
        f"\\u{ord(character):04x}" if 0xD800 <= ord(character) <= 0xDFFF else character
        for character in encoded_pointer
    )
    return f"{code} {encoded_pointer}"


def _append_error(errors: list[str], code: str, pointer: str) -> None:
    diagnostic = _diagnostic(code, pointer)
    if diagnostic not in errors:
        errors.append(diagnostic)


def _sort_errors(errors: list[str], start: int) -> None:
    errors[start:] = sorted(
        errors[start:],
        key=lambda error: (
            json.loads(error.partition(" ")[2]).encode("utf-8", "surrogatepass"),
            error.partition(" ")[0],
        ),
    )


def _declared_type(schema: dict[str, JSONValue]) -> tuple[str, bool] | None:
    declared = schema.get("type")
    if isinstance(declared, str) and declared in _SCHEMA_TYPES:
        return declared, False
    if (
        isinstance(declared, list)
        and len(declared) == 2
        and isinstance(declared[0], str)
        and declared[0] in _SCHEMA_TYPES - {"null"}
        and declared[1] == "null"
    ):
        return declared[0], True
    return None


def _is_finite_number(value: JSONValue) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _matches_type(value: JSONValue, declared: str, nullable: bool) -> bool:
    if value is None:
        return nullable or declared == "null"
    predicates = {
        "object": lambda candidate: isinstance(candidate, dict),
        "array": lambda candidate: isinstance(candidate, list),
        "string": lambda candidate: isinstance(candidate, str),
        "integer": lambda candidate: type(candidate) is int,
        "number": _is_finite_number,
        "boolean": lambda candidate: type(candidate) is bool,
        "null": lambda candidate: candidate is None,
    }
    return predicates[declared](value)


def _json_equal(left: JSONValue, right: JSONValue) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    return left == right


def _contains_ascii_control(value: str) -> bool:
    return any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)


def _contains_unsafe_url_character(value: str) -> bool:
    return any(
        character.isspace() or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    ) or re.search(r"%(?![0-9A-Fa-f]{2})", value) is not None


def _valid_https_url(value: str) -> bool:
    if _contains_ascii_control(value) or _contains_unsafe_url_character(value) or "#" in value:
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    if (
        not value.startswith("https://")
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in (None, 443)
    ):
        return False
    authority = parsed.netloc.rsplit(":", 1)[0] if port is not None else parsed.netloc
    if authority.startswith("[") or authority.endswith("."):
        return False
    try:
        authority.encode("ascii")
    except UnicodeEncodeError:
        return False
    if authority != authority.lower() or not all(_DNS_LABEL.fullmatch(label) for label in authority.split(".")):
        return False
    try:
        ipaddress.ip_address(authority)
    except ValueError:
        return not parsed.path or parsed.path.startswith("/")
    return False


def _valid_format(format_name: str, value: str) -> bool:
    if format_name == "date":
        if _DATE.fullmatch(value) is None:
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True
    if format_name == "date-time":
        if _DATE_TIME.fullmatch(value) is None:
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True
    if format_name == "https-url":
        return _valid_https_url(value)
    if format_name == "sha256":
        return _SHA256.fullmatch(value) is not None
    return False


def _validate_schema_definition(
    schema: JSONValue,
    pointer: str,
    errors: list[str],
) -> None:
    if not isinstance(schema, dict):
        _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", pointer)
        return
    for keyword in sorted(set(schema) - _SCHEMA_KEYWORDS):
        _append_error(
            errors,
            "V6_UNSUPPORTED_SCHEMA_KEYWORD",
            _pointer_child(pointer, keyword),
        )
    type_info = _declared_type(schema)
    if type_info is None:
        _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "type"))
        return
    declared, nullable = type_info
    applicable = _SCHEMA_APPLICABILITY[declared] | {"type", "enum", "const"}
    for keyword in sorted(set(schema) & _SCHEMA_KEYWORDS - applicable):
        _append_error(
            errors,
            "V6_INVALID_SCHEMA_DEFINITION",
            _pointer_child(pointer, keyword),
        )
    if "enum" in schema and "const" in schema:
        _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", pointer)
    enum = schema.get("enum")
    if "enum" in schema:
        if not isinstance(enum, list) or not enum:
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "enum"))
        else:
            for index, candidate in enumerate(enum):
                candidate_pointer = _pointer_child(_pointer_child(pointer, "enum"), index)
                if not _matches_type(candidate, declared, nullable):
                    _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", candidate_pointer)
                if any(_json_equal(candidate, previous) for previous in enum[:index]):
                    _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", candidate_pointer)
    if "const" in schema and not _matches_type(schema["const"], declared, nullable):
        _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "const"))
    if declared == "object":
        required = schema.get("required")
        properties = schema.get("properties")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "required"))
        if not isinstance(properties, dict):
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "properties"))
        if schema.get("additionalProperties") is not False:
            _append_error(
                errors,
                "V6_INVALID_SCHEMA_DEFINITION",
                _pointer_child(pointer, "additionalProperties"),
            )
        if isinstance(required, list) and all(isinstance(item, str) for item in required) and isinstance(properties, dict):
            property_order = {name: index for index, name in enumerate(properties)}
            required_valid = (
                len(required) == len(set(required))
                and all(name in properties for name in required)
                and [property_order[name] for name in required if name in property_order]
                == sorted(property_order[name] for name in required if name in property_order)
            )
            if not required_valid:
                _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "required"))
            for name in sorted(properties):
                _validate_schema_definition(
                    properties[name],
                    _pointer_child(_pointer_child(pointer, "properties"), name),
                    errors,
                )
    if declared == "array":
        if "items" not in schema:
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "items"))
        else:
            _validate_schema_definition(schema["items"], _pointer_child(pointer, "items"), errors)
    bound_pairs = {
        "string": ("minLength", "maxLength"),
        "array": ("minItems", "maxItems"),
        "integer": ("minimum", "maximum"),
        "number": ("minimum", "maximum"),
    }
    if declared in bound_pairs:
        minimum_key, maximum_key = bound_pairs[declared]
        minimum = schema.get(minimum_key)
        maximum = schema.get(maximum_key)
        length_bound = declared in {"string", "array"}
        minimum_valid = minimum_key not in schema or (
            type(minimum) is int and (not length_bound or minimum >= 0)
        )
        maximum_valid = maximum_key not in schema or (
            type(maximum) is int and (not length_bound or maximum >= 0)
        )
        if not length_bound:
            minimum_valid = minimum_key not in schema or _is_finite_number(minimum)
            maximum_valid = maximum_key not in schema or _is_finite_number(maximum)
        if not minimum_valid:
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, minimum_key))
        if not maximum_valid:
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, maximum_key))
        if minimum_valid and maximum_valid and minimum is not None and maximum is not None and minimum > maximum:
            _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, maximum_key))
    if "format" in schema and (
        not isinstance(schema["format"], str)
        or schema["format"] not in {"date", "date-time", "https-url", "sha256"}
    ):
        _append_error(errors, "V6_INVALID_SCHEMA_DEFINITION", _pointer_child(pointer, "format"))


def _validate_schema_value(
    schema: dict[str, JSONValue],
    value: JSONValue,
    pointer: str,
    errors: list[str],
) -> None:
    type_info = _declared_type(schema)
    if type_info is None:
        return
    declared, nullable = type_info
    if not _matches_type(value, declared, nullable):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return
    if value is None:
        enum = schema.get("enum")
        if isinstance(enum, list) and not any(_json_equal(value, item) for item in enum):
            _append_error(errors, "V6_INVALID_VALUE", pointer)
        if "const" in schema and not _json_equal(value, schema["const"]):
            _append_error(errors, "V6_INVALID_VALUE", pointer)
        return
    enum = schema.get("enum")
    if isinstance(enum, list) and not any(_json_equal(value, item) for item in enum):
        _append_error(errors, "V6_INVALID_VALUE", pointer)
    if "const" in schema and not _json_equal(value, schema["const"]):
        _append_error(errors, "V6_INVALID_VALUE", pointer)
    if declared == "object" and isinstance(value, dict):
        required = schema["required"]
        properties = schema["properties"]
        if isinstance(required, list) and isinstance(properties, dict):
            for name in required:
                if isinstance(name, str) and name not in value:
                    _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(pointer, name))
            for name in sorted(set(value) - set(properties)):
                _append_error(errors, "V6_UNKNOWN_FIELD", _pointer_child(pointer, name))
            for name in sorted(set(value) & set(properties)):
                child_schema = properties[name]
                if isinstance(child_schema, dict):
                    _validate_schema_value(child_schema, value[name], _pointer_child(pointer, name), errors)
    if declared == "array" and isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if (type(minimum) is int and len(value) < minimum) or (
            type(maximum) is int and len(value) > maximum
        ):
            _append_error(errors, "V6_INVALID_VALUE", pointer)
        items = schema["items"]
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_schema_value(items, item, _pointer_child(pointer, index), errors)
    if declared == "string" and isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if (type(minimum) is int and len(value) < minimum) or (
            type(maximum) is int and len(value) > maximum
        ):
            _append_error(errors, "V6_INVALID_VALUE", pointer)
        format_name = schema.get("format")
        if isinstance(format_name, str) and not _valid_format(format_name, value):
            _append_error(errors, "V6_INVALID_FORMAT", pointer)
    if declared in {"integer", "number"} and _is_finite_number(value):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if (_is_finite_number(minimum) and value < minimum) or (
            _is_finite_number(maximum) and value > maximum
        ):
            _append_error(errors, "V6_INVALID_VALUE", pointer)


def _validate_schema_node(
    schema: dict[str, JSONValue],
    value: JSONValue,
    pointer: str,
    errors: list[str],
) -> None:
    start = len(errors)
    _validate_schema_definition(schema, pointer, errors)
    if len(errors) == start:
        _validate_schema_value(schema, value, pointer, errors)
    _sort_errors(errors, start)


def _reject_duplicate_keys(pairs: list[tuple[str, JSONValue]]) -> dict[str, JSONValue]:
    result: dict[str, JSONValue] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError
        result[key] = value
    return result


def _reject_nonfinite_constant(_constant: str) -> JSONValue:
    raise _NonFiniteJsonNumberError


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteJsonNumberError
    return parsed


def _load_json_strict(path: Path) -> JSONValue:
    try:
        text = path.read_bytes().decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
            parse_float=_parse_finite_float,
        )
    except UnicodeDecodeError as error:
        raise StrictJsonError("V6_INVALID_JSON") from error
    except json.JSONDecodeError as error:
        raise StrictJsonError("V6_INVALID_JSON") from error
    except _DuplicateJsonKeyError as error:
        raise StrictJsonError("V6_DUPLICATE_JSON_KEY") from error
    except _NonFiniteJsonNumberError as error:
        raise StrictJsonError("V6_NON_FINITE_NUMBER") from error


_POLICY_IDS: Final = (
    "law-go-kr-drf-api",
    "kosis-statistics-api",
    "data-go-kr-order-plan-api",
    "data-go-kr-village-forecast-api",
    "gov-kr-web",
    "kipris-web",
    "kipo-web",
)
_CAPABILITY_POLICY_MAP: Final = {
    "public-document-hwpx": (),
    "korean-law-bill-research": ("law-go-kr-drf-api",),
    "kosis-official-statistics": ("kosis-statistics-api",),
    "public-procurement-research": ("data-go-kr-order-plan-api",),
    "disaster-geospatial-brief": ("data-go-kr-village-forecast-api",),
    "welfare-health-safety-research": (),
    "land-housing-geospatial-research": (),
    "official-source-research": ("gov-kr-web",),
    "civil-complaint-triage-draft": (),
    "administrative-document-draft-review": (),
    "public-policy-evidence-pack": (),
    "korean-legal-citation-verification": ("law-go-kr-drf-api",),
    "public-ai-governance-review": (),
    "public-it-project-procedure-review": (),
    "public-record-disclosure-redaction-review": (),
    "local-ordinance-draft-review": (),
    "construction-standard-bim-compliance-precheck": (),
    "building-permit-document-precheck": (),
    "official-notice-multilingual-translation-review": (),
    "patent-prior-art-evidence-pack": ("kipris-web", "kipo-web"),
    "public-records-lifecycle-review": (),
    "regulated-trade-procedure-precheck": (),
}
_POLICY_SHAPE: Final = (
    (
        "id",
        "revision",
        "enabled",
        "institution",
        "channel",
        "scope",
        "robots",
        "terms",
        "rate_limit",
        "response",
        "license",
        "retention",
    ),
    frozenset({"review"}),
)
_SCOPE_SHAPE: Final = (("origins", "path_rules", "methods"), frozenset())
_PATH_RULE_SHAPE: Final = (("match", "path"), frozenset())
_REVIEW_SHAPE: Final = (("reviewed_on", "expires_on", "evidence_urls"), frozenset())
_RETENTION_SHAPE: Final = (("raw_content", "receipts"), frozenset())


def _validate_object_shape(
    value: JSONValue,
    pointer: str,
    shape: tuple[tuple[str, ...], frozenset[str]],
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    required, optional = shape
    valid = True
    for key in required:
        if key not in value:
            _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(pointer, key))
            valid = False
    for key in sorted(set(value) - set(required) - optional):
        _append_error(errors, "V6_UNKNOWN_FIELD", _pointer_child(pointer, key))
        valid = False
    return valid


def _parse_policy_date(value: JSONValue, pointer: str, errors: list[str]) -> date | None:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        _append_error(errors, "V6_INVALID_FORMAT", pointer)
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        _append_error(errors, "V6_INVALID_FORMAT", pointer)
        return None


def _validate_unique_https_values(
    value: JSONValue,
    pointer: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, list) or not value:
        _append_error(errors, "V6_INVALID_VALUE", pointer)
        return False
    valid = True
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_pointer = _pointer_child(pointer, index)
        if not isinstance(item, str) or not _valid_https_url(item):
            _append_error(errors, "V6_INVALID_FORMAT", item_pointer)
            valid = False
        elif item in seen:
            _append_error(errors, "V6_DUPLICATE_VALUE", item_pointer)
            valid = False
        else:
            seen.add(item)
    return valid


def _valid_origin(value: str) -> bool:
    if "?" in value or "#" in value or not _valid_https_url(value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return not parsed.path and not parsed.query and not parsed.fragment and port is None


def _valid_policy_path(value: str, match_type: JSONValue) -> bool:
    lowered = value.lower()
    if (
        not value.startswith("/")
        or _contains_ascii_control(value)
        or _contains_unsafe_url_character(value)
        or "?" in value
        or "#" in value
        or "\\" in value
        or "//" in value
        or re.search(r"%(?:2f|5c|00)", lowered) is not None
        or any(segment in {".", ".."} for segment in value.split("/"))
    ):
        return False
    return not value.endswith("/") or (match_type == "prefix" and value == "/")


def _match_source_policy_path(
    path_rules: list[dict[str, JSONValue]],
    request_path: str,
) -> int | None:
    best_index: int | None = None
    best_length = -1
    for index, rule in enumerate(path_rules):
        match_type = rule.get("match")
        declared_path = rule.get("path")
        if not isinstance(declared_path, str):
            continue
        matches = (
            match_type == "exact" and request_path == declared_path
        ) or (
            match_type == "prefix"
            and (
                (declared_path == "/" and request_path.startswith("/"))
                or request_path == declared_path
                or request_path.startswith(f"{declared_path}/")
            )
        )
        if matches and len(declared_path) > best_length:
            best_index = index
            best_length = len(declared_path)
    return best_index


def _validate_scope(value: JSONValue, pointer: str, errors: list[str]) -> None:
    _validate_object_shape(value, pointer, _SCOPE_SHAPE, errors)
    if not isinstance(value, dict):
        return
    origins = value.get("origins")
    if not isinstance(origins, list) or not origins:
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "origins"))
    else:
        seen_origins: set[str] = set()
        for index, origin in enumerate(origins):
            origin_pointer = _pointer_child(_pointer_child(pointer, "origins"), index)
            if not isinstance(origin, str) or not _valid_origin(origin):
                _append_error(errors, "V6_INVALID_FORMAT", origin_pointer)
            elif origin in seen_origins:
                _append_error(errors, "V6_DUPLICATE_VALUE", origin_pointer)
            else:
                seen_origins.add(origin)
    methods = value.get("methods")
    if "methods" in value and methods != ["GET"]:
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "methods"))
    rules = value.get("path_rules")
    if not isinstance(rules, list) or not rules:
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "path_rules"))
        return
    seen_rules: list[tuple[str, str]] = []
    for index, rule in enumerate(rules):
        rule_pointer = _pointer_child(_pointer_child(pointer, "path_rules"), index)
        _validate_object_shape(rule, rule_pointer, _PATH_RULE_SHAPE, errors)
        if not isinstance(rule, dict):
            continue
        match_type = rule.get("match")
        path = rule.get("path")
        match_valid = isinstance(match_type, str) and match_type in {"exact", "prefix"}
        path_valid = isinstance(path, str) and _valid_policy_path(path, match_type)
        if "match" in rule and not match_valid:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(rule_pointer, "match"))
        if "path" in rule and not path_valid:
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(rule_pointer, "path"))
        if not match_valid or not path_valid or not isinstance(match_type, str) or not isinstance(path, str):
            continue
        identity = (match_type, path)
        if identity in seen_rules:
            _append_error(errors, "V6_DUPLICATE_VALUE", rule_pointer)
        elif any(previous_path == path for _, previous_path in seen_rules):
            _append_error(errors, "V6_INVALID_VALUE", rule_pointer)
        seen_rules.append(identity)


def _validate_review(
    value: JSONValue,
    pointer: str,
    on_date: date,
    errors: list[str],
) -> bool:
    shape_valid = _validate_object_shape(value, pointer, _REVIEW_SHAPE, errors)
    if not isinstance(value, dict):
        return False
    reviewed = (
        _parse_policy_date(value["reviewed_on"], _pointer_child(pointer, "reviewed_on"), errors)
        if "reviewed_on" in value
        else None
    )
    expires = (
        _parse_policy_date(value["expires_on"], _pointer_child(pointer, "expires_on"), errors)
        if "expires_on" in value
        else None
    )
    evidence_valid = "evidence_urls" in value and _validate_unique_https_values(
        value["evidence_urls"],
        _pointer_child(pointer, "evidence_urls"),
        errors,
    )
    dates_valid = reviewed is not None and expires is not None
    if dates_valid and reviewed is not None and expires is not None:
        if reviewed > on_date or reviewed > expires:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "reviewed_on"))
            dates_valid = False
        if on_date > expires:
            _append_error(errors, "V6_POLICY_STALE", _pointer_child(pointer, "expires_on"))
            dates_valid = False
    return shape_valid and dates_valid and evidence_valid


def _validate_robots(value: JSONValue, pointer: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    status = value.get("status")
    shapes = {
        "unreviewed": (("status",), frozenset()),
        "required": (("status",), frozenset()),
        "documented-api-exemption": (("status", "evidence_url"), frozenset()),
    }
    shape = shapes.get(status) if isinstance(status, str) else None
    if shape is None:
        _validate_object_shape(value, pointer, (("status",), frozenset()), errors)
        if "status" in value:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "status"))
        return False
    shape_valid = _validate_object_shape(value, pointer, shape, errors)
    url_valid = True
    if status == "documented-api-exemption" and "evidence_url" in value:
        url = value["evidence_url"]
        url_valid = isinstance(url, str) and _valid_https_url(url)
        if not url_valid:
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "evidence_url"))
    return shape_valid and url_valid and status in {"required", "documented-api-exemption"}


def _validate_terms(value: JSONValue, pointer: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    status = value.get("status")
    shapes = {
        "unreviewed": (("status",), frozenset()),
        "manual-review": (("status", "url"), frozenset()),
        "allowed": (("status", "url"), frozenset()),
        "prohibited": (("status", "url"), frozenset()),
    }
    shape = shapes.get(status) if isinstance(status, str) else None
    if shape is None:
        _validate_object_shape(value, pointer, (("status",), frozenset()), errors)
        if "status" in value:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "status"))
        return False
    shape_valid = _validate_object_shape(value, pointer, shape, errors)
    url_valid = True
    if status != "unreviewed" and "url" in value:
        url = value["url"]
        url_valid = isinstance(url, str) and _valid_https_url(url)
        if not url_valid:
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "url"))
    return shape_valid and url_valid and status == "allowed"


def _validate_rate(value: JSONValue, pointer: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    status = value.get("status")
    status_valid = isinstance(status, str) and status in {"unreviewed", "reviewed"}
    shape = (
        (("status",), frozenset())
        if status == "unreviewed"
        else (("status", "requests", "per_seconds", "burst", "max_wait_seconds"), frozenset())
    )
    if not status_valid:
        shape = (("status",), frozenset())
    shape_valid = _validate_object_shape(value, pointer, shape, errors)
    if not status_valid:
        if "status" in value:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "status"))
        return False
    values_valid = True
    if status == "reviewed":
        for key in ("requests", "per_seconds", "burst"):
            item = value.get(key)
            if key in value and (type(item) is not int or item <= 0):
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, key))
                values_valid = False
        maximum_wait = value.get("max_wait_seconds")
        if "max_wait_seconds" in value and (
            not _is_finite_number(maximum_wait) or maximum_wait < 0
        ):
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "max_wait_seconds"))
            values_valid = False
    return shape_valid and values_valid and status == "reviewed"


def _validate_response(value: JSONValue, pointer: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    status = value.get("status")
    status_valid = isinstance(status, str) and status in {"unreviewed", "reviewed"}
    shape = (
        (("status",), frozenset())
        if status == "unreviewed"
        else (("status", "max_bytes", "media_types"), frozenset())
    )
    if not status_valid:
        shape = (("status",), frozenset())
    shape_valid = _validate_object_shape(value, pointer, shape, errors)
    if not status_valid:
        if "status" in value:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "status"))
        return False
    values_valid = True
    maximum_bytes = value.get("max_bytes")
    if status == "reviewed" and "max_bytes" in value and (
        type(maximum_bytes) is not int or maximum_bytes <= 0
    ):
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "max_bytes"))
        values_valid = False
    media_types = value.get("media_types")
    if status == "reviewed":
        media_pointer = _pointer_child(pointer, "media_types")
        if not isinstance(media_types, list) or not media_types:
            if "media_types" in value:
                _append_error(errors, "V6_INVALID_VALUE", media_pointer)
            values_valid = False
        else:
            seen: set[str] = set()
            for index, media_type in enumerate(media_types):
                item_pointer = _pointer_child(media_pointer, index)
                if not isinstance(media_type, str) or not media_type or media_type != media_type.lower():
                    _append_error(errors, "V6_INVALID_VALUE", item_pointer)
                    values_valid = False
                if isinstance(media_type, str) and media_type in seen:
                    _append_error(errors, "V6_DUPLICATE_VALUE", item_pointer)
                    values_valid = False
                elif isinstance(media_type, str):
                    seen.add(media_type)
    return shape_valid and values_valid and status == "reviewed"


def _validate_license(value: JSONValue, pointer: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    status = value.get("status")
    shapes = {
        "unreviewed": (("status",), frozenset()),
        "manual-review": (("status", "url"), frozenset()),
        "reviewed": (
            ("status", "url", "allowed_output_modes", "redistribution"),
            frozenset(),
        ),
    }
    shape = shapes.get(status) if isinstance(status, str) else None
    if shape is None:
        _validate_object_shape(value, pointer, (("status",), frozenset()), errors)
        if "status" in value:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "status"))
        return False
    shape_valid = _validate_object_shape(value, pointer, shape, errors)
    values_valid = True
    if status != "unreviewed" and "url" in value:
        url = value["url"]
        if not isinstance(url, str) or not _valid_https_url(url):
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "url"))
            values_valid = False
    if status == "reviewed":
        modes = value.get("allowed_output_modes")
        modes_pointer = _pointer_child(pointer, "allowed_output_modes")
        if not isinstance(modes, list) or not modes:
            if "allowed_output_modes" in value:
                _append_error(errors, "V6_INVALID_VALUE", modes_pointer)
            values_valid = False
        else:
            seen: set[str] = set()
            for index, mode in enumerate(modes):
                item_pointer = _pointer_child(modes_pointer, index)
                if not isinstance(mode, str) or mode not in {"link-only", "projected-records"}:
                    _append_error(errors, "V6_INVALID_VALUE", item_pointer)
                    values_valid = False
                if isinstance(mode, str) and mode in seen:
                    _append_error(errors, "V6_DUPLICATE_VALUE", item_pointer)
                    values_valid = False
                elif isinstance(mode, str):
                    seen.add(mode)
        redistribution = value.get("redistribution")
        if "redistribution" in value and (
            not isinstance(redistribution, str)
            or redistribution not in {"link-only", "allowed"}
        ):
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "redistribution"))
            values_valid = False
    return shape_valid and values_valid and status == "reviewed"


def _validate_retention(value: JSONValue, pointer: str, errors: list[str]) -> None:
    _validate_object_shape(value, pointer, _RETENTION_SHAPE, errors)
    if not isinstance(value, dict):
        return
    if "raw_content" in value and value["raw_content"] != "none":
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "raw_content"))
    if "receipts" in value and value["receipts"] != "metadata-only":
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "receipts"))


def _validate_policy(value: JSONValue, pointer: str, on_date: date, errors: list[str]) -> None:
    _validate_object_shape(value, pointer, _POLICY_SHAPE, errors)
    if not isinstance(value, dict):
        return
    policy_id = value.get("id")
    if "id" in value and (
        not isinstance(policy_id, str)
        or len(policy_id) > 64
        or SLUG.fullmatch(policy_id) is None
    ):
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "id"))
    revision = value.get("revision")
    if "revision" in value and (type(revision) is not int or revision < 1):
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "revision"))
    if "enabled" in value and type(value["enabled"]) is not bool:
        _append_error(errors, "V6_INVALID_TYPE", _pointer_child(pointer, "enabled"))
    institution = value.get("institution")
    if "institution" in value and (
        not isinstance(institution, str)
        or not institution
        or len(institution) > 120
    ):
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "institution"))
    channel = value.get("channel")
    if "channel" in value and (
        not isinstance(channel, str) or channel not in {"api", "web"}
    ):
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "channel"))
    if "scope" in value:
        _validate_scope(value["scope"], _pointer_child(pointer, "scope"), errors)
    review_valid = False
    if "review" in value:
        review_valid = _validate_review(
            value["review"],
            _pointer_child(pointer, "review"),
            on_date,
            errors,
        )
    robots_valid = "robots" in value and _validate_robots(
        value["robots"], _pointer_child(pointer, "robots"), errors
    )
    terms_valid = "terms" in value and _validate_terms(
        value["terms"], _pointer_child(pointer, "terms"), errors
    )
    rate_valid = "rate_limit" in value and _validate_rate(
        value["rate_limit"], _pointer_child(pointer, "rate_limit"), errors
    )
    response_valid = "response" in value and _validate_response(
        value["response"], _pointer_child(pointer, "response"), errors
    )
    license_valid = "license" in value and _validate_license(
        value["license"], _pointer_child(pointer, "license"), errors
    )
    if "retention" in value:
        _validate_retention(value["retention"], _pointer_child(pointer, "retention"), errors)
    if value.get("enabled") is True and not all(
        (review_valid, robots_valid, terms_valid, rate_valid, response_valid, license_valid)
    ):
        _append_error(errors, "V6_POLICY_NOT_ENABLEABLE", _pointer_child(pointer, "enabled"))


def _validate_capability_policy_references(
    value: JSONValue,
    policy_ids: set[str],
    errors: list[str],
) -> None:
    pointer = "/shared_capabilities"
    if not isinstance(value, list):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return
    policy_order = {policy_id: index for index, policy_id in enumerate(_POLICY_IDS)}
    for index, capability in enumerate(value):
        capability_pointer = _pointer_child(pointer, index)
        if not isinstance(capability, dict):
            _append_error(errors, "V6_INVALID_TYPE", capability_pointer)
            continue
        refs_pointer = _pointer_child(capability_pointer, "source_policy_ids")
        if "source_policy_ids" not in capability:
            _append_error(errors, "V6_REQUIRED_FIELD", refs_pointer)
            continue
        refs = capability["source_policy_ids"]
        if not isinstance(refs, list):
            _append_error(errors, "V6_INVALID_TYPE", refs_pointer)
            continue
        seen: set[str] = set()
        refs_valid = True
        for ref_index, policy_id in enumerate(refs):
            ref_pointer = _pointer_child(refs_pointer, ref_index)
            if (
                not isinstance(policy_id, str)
                or policy_id not in policy_ids
                or policy_id not in policy_order
            ):
                _append_error(errors, "V6_UNKNOWN_REFERENCE", ref_pointer)
                refs_valid = False
            elif policy_id in seen:
                _append_error(errors, "V6_DUPLICATE_VALUE", ref_pointer)
                refs_valid = False
            else:
                seen.add(policy_id)
        if refs_valid and refs != sorted(refs, key=policy_order.__getitem__):
            _append_error(errors, "V6_INVALID_VALUE", refs_pointer)
            refs_valid = False
        slug = capability.get("slug")
        expected = _CAPABILITY_POLICY_MAP.get(slug) if isinstance(slug, str) else None
        if refs_valid and expected is not None and tuple(refs) != expected:
            _append_error(errors, "V6_INVALID_VALUE", refs_pointer)


def _validate_source_policies(
    data: dict[str, JSONValue],
    *,
    on_date: date,
    errors: list[str],
) -> None:
    start = len(errors)
    policies = data.get("source_policies")
    if not isinstance(policies, list):
        _append_error(errors, "V6_INVALID_TYPE", "/source_policies")
        _sort_errors(errors, start)
        return
    if len(policies) != len(_POLICY_IDS):
        _append_error(errors, "V6_INVALID_VALUE", "/source_policies")
    seen: set[str] = set()
    ids: list[str] = []
    duplicate = False
    for index, policy in enumerate(policies):
        pointer = _pointer_child("/source_policies", index)
        _validate_policy(policy, pointer, on_date, errors)
        if not isinstance(policy, dict):
            continue
        policy_id = policy.get("id")
        if not isinstance(policy_id, str):
            continue
        ids.append(policy_id)
        if policy_id in seen:
            _append_error(errors, "V6_DUPLICATE_ID", _pointer_child(pointer, "id"))
            duplicate = True
        else:
            seen.add(policy_id)
    if not duplicate and len(ids) == len(_POLICY_IDS):
        for index, (actual, expected) in enumerate(zip(ids, _POLICY_IDS, strict=True)):
            if actual != expected:
                _append_error(
                    errors,
                    "V6_INVALID_VALUE",
                    _pointer_child(_pointer_child("/source_policies", index), "id"),
                )
    if not duplicate:
        _validate_capability_policy_references(data.get("shared_capabilities"), seen, errors)
    _sort_errors(errors, start)


_RUNTIME_CONTRACT_SHAPE: Final = (
    (
        "id",
        "capability_slug",
        "module",
        "kind",
        "network_mode",
        "default_operation_id",
        "operations",
        "exit_codes",
        "forbidden_output_keys",
    ),
    frozenset(),
)
_OPERATION_SHAPE: Final = (
    ("id", "schema_status", "source_policy_ids", "source_output_mode"),
    frozenset({"fixture_argv", "input_schema", "output_schema"}),
)
_BINDING_SHAPE: Final = (("contract_id", "operation", "fixed_input"), frozenset())
_EXIT_CODES_SHAPE: Final = (
    ("success", "review_blocked", "input_error", "policy_blocked", "upstream_error"),
    frozenset(),
)
_EXIT_CODES: Final = {
    "success": 0,
    "review_blocked": 1,
    "input_error": 2,
    "policy_blocked": 3,
    "upstream_error": 4,
}
_FORBIDDEN_OUTPUT_KEYS: Final = [
    "authorization",
    "body",
    "cookie",
    "credential",
    "headers",
    "raw",
    "text",
]
_APPROVED_RUNTIME_MANIFEST: Final = (
    ("public-document-hwpx", "local-document", "none", (("inspect-document", (), "none", True),)),
    ("korean-law-bill-research", "retrieval", "optional-live", (("search-laws", ("law-go-kr-drf-api",), "projected-records", True),)),
    ("kosis-official-statistics", "retrieval", "optional-live", (("query-statistics", ("kosis-statistics-api",), "projected-records", True),)),
    ("public-procurement-research", "retrieval", "optional-live", (("query-order-plans", ("data-go-kr-order-plan-api",), "projected-records", True),)),
    ("disaster-geospatial-brief", "retrieval", "optional-live", (("query-village-forecast", ("data-go-kr-village-forecast-api",), "projected-records", True),)),
    ("welfare-health-safety-research", "retrieval", "blocked", (("blocked-dataset-query", (), "projected-records", True),)),
    ("land-housing-geospatial-research", "retrieval", "blocked", (("blocked-dataset-query", (), "projected-records", True),)),
    ("official-source-research", "retrieval", "optional-live", (("inspect-page", ("gov-kr-web",), "link-only", True),)),
    ("civil-complaint-triage-draft", "admission", "none", (("admit-draft", (), "none", True),)),
    ("administrative-document-draft-review", "admission", "none", (("review-draft", (), "none", True),)),
    ("public-policy-evidence-pack", "admission", "none", (("build-pack", (), "none", True),)),
    ("korean-legal-citation-verification", "verification", "optional-live", (("verify-citations", ("law-go-kr-drf-api",), "link-only", True),)),
    ("public-ai-governance-review", "admission", "none", (("review-case", (), "none", True),)),
    ("public-it-project-procedure-review", "admission", "none", (("review-case", (), "none", True),)),
    ("public-record-disclosure-redaction-review", "admission", "none", (("review-case", (), "none", True),)),
    ("local-ordinance-draft-review", "admission", "none", (("review-case", (), "none", True),)),
    ("construction-standard-bim-compliance-precheck", "admission", "none", (("review-case", (), "none", True),)),
    ("building-permit-document-precheck", "admission", "none", (("review-case", (), "none", True),)),
    ("official-notice-multilingual-translation-review", "admission", "none", (("review-case", (), "none", True),)),
    (
        "patent-prior-art-evidence-pack",
        "hybrid",
        "mixed",
        (
            ("review-case", (), "none", True),
            ("inspect-source", ("kipris-web", "kipo-web"), "link-only", False),
        ),
    ),
    ("public-records-lifecycle-review", "admission", "none", (("review-case", (), "none", True),)),
    ("regulated-trade-procedure-precheck", "admission", "none", (("review-case", (), "none", True),)),
)


_RUNTIME_KINDS: Final = {
    "local-document",
    "retrieval",
    "admission",
    "verification",
    "hybrid",
}
_NETWORK_MODES: Final = {"none", "optional-live", "blocked", "mixed"}
_SOURCE_OUTPUT_MODES: Final = {"none", "projected-records", "link-only"}


def _validate_exit_codes(value: JSONValue, pointer: str, errors: list[str]) -> None:
    _validate_object_shape(value, pointer, _EXIT_CODES_SHAPE, errors)
    if not isinstance(value, dict):
        return
    for name, expected in _EXIT_CODES.items():
        if name not in value:
            continue
        member_pointer = _pointer_child(pointer, name)
        actual = value[name]
        if type(actual) is not int:
            _append_error(errors, "V6_INVALID_TYPE", member_pointer)
        elif actual != expected:
            _append_error(errors, "V6_CONTRACT_INVARIANT", member_pointer)


def _validate_runtime_shapes(
    contracts: JSONValue,
    pointer: str,
    errors: list[str],
) -> bool:
    if not isinstance(contracts, list):
        _append_error(errors, "V6_INVALID_TYPE", pointer)
        return False
    if not contracts:
        _append_error(errors, "V6_INVALID_VALUE", pointer)
        return False
    for contract_index, contract in enumerate(contracts):
        contract_pointer = _pointer_child(pointer, contract_index)
        _validate_object_shape(contract, contract_pointer, _RUNTIME_CONTRACT_SHAPE, errors)
        if not isinstance(contract, dict):
            continue
        if "exit_codes" in contract:
            _validate_exit_codes(
                contract["exit_codes"],
                _pointer_child(contract_pointer, "exit_codes"),
                errors,
            )
        operations = contract.get("operations")
        operations_pointer = _pointer_child(contract_pointer, "operations")
        if not isinstance(operations, list):
            if "operations" in contract:
                _append_error(errors, "V6_INVALID_TYPE", operations_pointer)
            continue
        if not operations:
            _append_error(errors, "V6_INVALID_VALUE", operations_pointer)
        for operation_index, operation in enumerate(operations):
            _validate_object_shape(
                operation,
                _pointer_child(operations_pointer, operation_index),
                _OPERATION_SHAPE,
                errors,
            )
    return True


def _collect_runtime_ids(contracts: JSONValue, errors: list[str]) -> bool:
    if not isinstance(contracts, list):
        return False
    duplicate = False
    contract_ids: set[str] = set()
    operation_ids: set[str] = set()
    for contract_index, contract in enumerate(contracts):
        if not isinstance(contract, dict):
            continue
        contract_pointer = _pointer_child("/runtime_contracts", contract_index)
        contract_id = contract.get("id")
        if isinstance(contract_id, str):
            if contract_id in contract_ids:
                _append_error(errors, "V6_DUPLICATE_ID", _pointer_child(contract_pointer, "id"))
                duplicate = True
            else:
                contract_ids.add(contract_id)
        operations = contract.get("operations")
        if not isinstance(operations, list):
            continue
        for operation_index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("id")
            if not isinstance(operation_id, str):
                continue
            if operation_id in operation_ids:
                _append_error(
                    errors,
                    "V6_DUPLICATE_ID",
                    _pointer_child(
                        _pointer_child(_pointer_child(contract_pointer, "operations"), operation_index),
                        "id",
                    ),
                )
                duplicate = True
            else:
                operation_ids.add(operation_id)
    return duplicate


def _validate_operation_policy_ids(
    operation: dict[str, JSONValue],
    capability_policy_ids: list[str],
    pointer: str,
    errors: list[str],
) -> tuple[list[str], bool]:
    refs = operation.get("source_policy_ids")
    refs_pointer = _pointer_child(pointer, "source_policy_ids")
    if not isinstance(refs, list):
        if "source_policy_ids" in operation:
            _append_error(errors, "V6_INVALID_TYPE", refs_pointer)
        return [], False
    order = {policy_id: index for index, policy_id in enumerate(_POLICY_IDS)}
    valid = True
    seen: set[str] = set()
    normalized: list[str] = []
    for index, policy_id in enumerate(refs):
        item_pointer = _pointer_child(refs_pointer, index)
        if not isinstance(policy_id, str) or policy_id not in order:
            _append_error(errors, "V6_UNKNOWN_REFERENCE", item_pointer)
            valid = False
            continue
        if policy_id in seen:
            _append_error(errors, "V6_DUPLICATE_VALUE", item_pointer)
            valid = False
            continue
        seen.add(policy_id)
        normalized.append(policy_id)
        if policy_id not in capability_policy_ids:
            _append_error(errors, "V6_UNKNOWN_REFERENCE", item_pointer)
            valid = False
    if valid and normalized != sorted(normalized, key=order.__getitem__):
        _append_error(errors, "V6_INVALID_VALUE", refs_pointer)
        valid = False
    return normalized, valid


def _validate_forbidden_output_properties(
    schema: JSONValue,
    pointer: str,
    forbidden: set[str],
    errors: list[str],
) -> None:
    if not isinstance(schema, dict):
        return
    properties = schema.get("properties")
    if isinstance(properties, dict):
        properties_pointer = _pointer_child(pointer, "properties")
        for name in sorted(properties):
            child_pointer = _pointer_child(properties_pointer, name)
            if name in forbidden:
                _append_error(errors, "V6_CONTRACT_INVARIANT", child_pointer)
            _validate_forbidden_output_properties(properties[name], child_pointer, forbidden, errors)
    if "items" in schema:
        _validate_forbidden_output_properties(
            schema["items"],
            _pointer_child(pointer, "items"),
            forbidden,
            errors,
        )


def _validate_operation_contract(
    operation: dict[str, JSONValue],
    operation_index: int,
    contract: dict[str, JSONValue],
    capability_policy_ids: list[str],
    pointer: str,
    errors: list[str],
) -> list[str]:
    capability = contract.get("capability_slug")
    operation_id = operation.get("id")
    if (
        not isinstance(operation_id, str)
        or not isinstance(capability, str)
        or re.fullmatch(rf"kgov/{re.escape(capability)}/[a-z0-9]+(?:-[a-z0-9]+)*/v1", operation_id)
        is None
    ):
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "id"))
    fixture = operation.get("fixture_argv")
    if operation_index == 0 and fixture != ["--fixture"]:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "fixture_argv"))
    if operation_index > 0 and "fixture_argv" in operation:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "fixture_argv"))
    status = operation.get("schema_status")
    if not isinstance(status, str) or status not in {"declared", "active"}:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "schema_status"))
    output_mode = operation.get("source_output_mode")
    if not isinstance(output_mode, str) or output_mode not in _SOURCE_OUTPUT_MODES:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "source_output_mode"))
    policy_ids, _ = _validate_operation_policy_ids(
        operation,
        capability_policy_ids,
        pointer,
        errors,
    )
    if status == "declared":
        for schema_key in ("input_schema", "output_schema"):
            if schema_key in operation:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, schema_key))
    if status == "active":
        for schema_key in ("input_schema", "output_schema"):
            schema_pointer = _pointer_child(pointer, schema_key)
            if schema_key not in operation:
                _append_error(errors, "V6_REQUIRED_FIELD", schema_pointer)
                continue
            before = len(errors)
            _validate_schema_definition(operation[schema_key], schema_pointer, errors)
            if schema_key == "output_schema" and len(errors) == before:
                _validate_forbidden_output_properties(
                    operation[schema_key],
                    schema_pointer,
                    set(_FORBIDDEN_OUTPUT_KEYS),
                    errors,
                )
    return policy_ids


def _validate_contract_semantics(
    contract: dict[str, JSONValue],
    contract_index: int,
    capability: dict[str, JSONValue],
    pointer: str,
    errors: list[str],
) -> None:
    slug = contract.get("capability_slug")
    expected_slug = capability.get("slug")
    if slug != expected_slug:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "capability_slug"))
    if isinstance(slug, str):
        if contract.get("id") != f"kgov/{slug}/v1":
            _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "id"))
        if contract.get("module") != f"kgov_runtime.capabilities.{slug.replace('-', '_')}":
            _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "module"))
    kind = contract.get("kind")
    if not isinstance(kind, str) or kind not in _RUNTIME_KINDS:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "kind"))
    network = contract.get("network_mode")
    if not isinstance(network, str) or network not in _NETWORK_MODES:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "network_mode"))
    if contract.get("forbidden_output_keys") != _FORBIDDEN_OUTPUT_KEYS:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "forbidden_output_keys"))
    capability_policy_ids = capability.get("source_policy_ids")
    if not isinstance(capability_policy_ids, list):
        capability_policy_ids = []
    operations = contract.get("operations")
    if not isinstance(operations, list) or not operations:
        return
    first = operations[0]
    if isinstance(first, dict) and contract.get("default_operation_id") != first.get("id"):
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "default_operation_id"))
    union: list[str] = []
    linked_flags: list[bool] = []
    operation_outputs: list[JSONValue] = []
    for operation_index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            continue
        operation_pointer = _pointer_child(_pointer_child(pointer, "operations"), operation_index)
        policy_ids = _validate_operation_contract(
            operation,
            operation_index,
            contract,
            capability_policy_ids,
            operation_pointer,
            errors,
        )
        linked_flags.append(bool(policy_ids))
        operation_outputs.append(operation.get("source_output_mode"))
        for policy_id in policy_ids:
            if policy_id not in union:
                union.append(policy_id)
    if union != capability_policy_ids:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "operations"))
    has_linked = any(linked_flags)
    has_local = any(not linked for linked in linked_flags)
    network_valid = (
        (network == "none" and not has_linked)
        or (network == "blocked" and not has_linked)
        or (network == "optional-live" and has_linked)
        or (network == "mixed" and has_linked and has_local)
    )
    if not network_valid:
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "network_mode"))
    for operation_index, (linked, output_mode) in enumerate(
        zip(linked_flags, operation_outputs, strict=True)
    ):
        operation = operations[operation_index]
        if not isinstance(operation, dict):
            continue
        operation_pointer = _pointer_child(
            _pointer_child(pointer, "operations"),
            operation_index,
        )
        if network == "none" and output_mode != "none":
            _append_error(
                errors,
                "V6_CONTRACT_INVARIANT",
                _pointer_child(operation_pointer, "source_output_mode"),
            )
        if (
            operation.get("schema_status") == "active"
            and not linked
            and output_mode in {"link-only", "projected-records"}
        ):
            _append_error(
                errors,
                "V6_CONTRACT_INVARIANT",
                _pointer_child(operation_pointer, "source_policy_ids"),
            )


def _validate_runtime_contracts(
    data: dict[str, JSONValue],
    *,
    errors: list[str],
) -> None:
    start = len(errors)
    contracts = data.get("runtime_contracts")
    capabilities = data.get("shared_capabilities")
    _validate_runtime_shapes(contracts, "/runtime_contracts", errors)
    if not isinstance(capabilities, list):
        _append_error(errors, "V6_INVALID_TYPE", "/shared_capabilities")
    shape_error = len(errors) != start
    duplicate = _collect_runtime_ids(contracts, errors)
    if shape_error or duplicate or not isinstance(contracts, list) or not isinstance(capabilities, list):
        _sort_errors(errors, start)
        return
    if len(contracts) != len(capabilities):
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/runtime_contracts")
    count = min(len(contracts), len(capabilities))
    for index in range(count):
        contract = contracts[index]
        capability = capabilities[index]
        if not isinstance(contract, dict) or not isinstance(capability, dict):
            continue
        pointer = _pointer_child("/runtime_contracts", index)
        if contract.get("capability_slug") != capability.get("slug"):
            _append_error(
                errors,
                "V6_CONTRACT_INVARIANT",
                _pointer_child(pointer, "capability_slug"),
            )
            continue
        _validate_contract_semantics(contract, index, capability, pointer, errors)
    contracts_by_id = {
        contract["id"]: contract
        for contract in contracts
        if isinstance(contract, dict) and isinstance(contract.get("id"), str)
    }
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            continue
        link_pointer = _pointer_child(
            _pointer_child("/shared_capabilities", index),
            "runtime_contract_id",
        )
        contract_id = capability.get("runtime_contract_id")
        slug = capability.get("slug")
        linked = contracts_by_id.get(contract_id) if isinstance(contract_id, str) else None
        if (
            linked is None
            or not isinstance(slug, str)
            or linked.get("capability_slug") != slug
        ):
            _append_error(errors, "V6_CONTRACT_INVARIANT", link_pointer)
    _sort_errors(errors, start)


def _validate_runtime_binding(
    binding: JSONValue,
    *,
    capability_slug: str,
    contracts_by_id: dict[str, dict[str, JSONValue]],
    pointer: str,
    errors: list[str],
) -> None:
    start = len(errors)
    shape_valid = _validate_object_shape(binding, pointer, _BINDING_SHAPE, errors)
    if not isinstance(binding, dict) or not shape_valid:
        _sort_errors(errors, start)
        return
    contract_id = binding.get("contract_id")
    contract = contracts_by_id.get(contract_id) if isinstance(contract_id, str) else None
    if contract is None:
        _append_error(errors, "V6_UNKNOWN_REFERENCE", _pointer_child(pointer, "contract_id"))
        _sort_errors(errors, start)
        return
    if contract.get("capability_slug") != capability_slug:
        _append_error(errors, "V6_BINDING_MISMATCH", _pointer_child(pointer, "contract_id"))
        _sort_errors(errors, start)
        return
    operation_id = binding.get("operation")
    operations = contract.get("operations")
    operation = None
    if isinstance(operations, list):
        operation = next(
            (
                candidate
                for candidate in operations
                if isinstance(candidate, dict) and candidate.get("id") == operation_id
            ),
            None,
        )
    if operation is None:
        _append_error(errors, "V6_UNKNOWN_REFERENCE", _pointer_child(pointer, "operation"))
        _sort_errors(errors, start)
        return
    if operation.get("schema_status") != "active":
        _append_error(errors, "V6_OPERATION_NOT_ACTIVE", _pointer_child(pointer, "operation"))
        _sort_errors(errors, start)
        return
    fixed_input = binding.get("fixed_input")
    fixed_pointer = _pointer_child(pointer, "fixed_input")
    if not isinstance(fixed_input, dict):
        _append_error(errors, "V6_INVALID_TYPE", fixed_pointer)
        _sort_errors(errors, start)
        return
    input_schema = operation.get("input_schema")
    if not isinstance(input_schema, dict):
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "operation"))
        _sort_errors(errors, start)
        return
    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "operation"))
        _sort_errors(errors, start)
        return
    for key in sorted(fixed_input):
        value_pointer = _pointer_child(fixed_pointer, key)
        schema = properties.get(key)
        if not isinstance(schema, dict):
            _append_error(errors, "V6_INVALID_VALUE", value_pointer)
            continue
        _validate_schema_node(schema, fixed_input[key], value_pointer, errors)
    _sort_errors(errors, start)


_ROOT_V6_SHAPE: Final = (
    (
        "schema_version",
        "target_skills_per_domain",
        "enforced_minimum_skills_by_domain",
        "research_source",
        "source_policies",
        "runtime_contracts",
        "shared_capabilities",
        "domains",
    ),
    frozenset(),
)
_EXPECTED_DOMAIN_SKILLS: Final = (
    ('행정', (
        'government-document-hwpx-review',
        'public-administration-civil-complaint-triage-draft',
        'public-administration-administrative-document-draft-review',
        'public-administration-public-policy-evidence-pack',
        'public-administration-legal-citation-verification',
        'public-ai-impact-assessment-draft-review',
        'public-ai-risk-management-plan-review',
        'official-notice-multilingual-translation-review',
    )),
    ('재정', (
        'budget-settlement-comparison',
        'local-finance-evidence-pack',
        'national-subsidy-project-evidence-review',
        'fiscal-law-citation-evidence-review',
        'fiscal-budget-execution-evidence-pack',
    )),
    ('세무', (
        'business-tax-status-lookup',
        'tax-law-bill-research',
        'national-tax-statistics-lookup',
        'property-tax-land-housing-research',
        'hometax-official-guidance-search',
        'local-tax-ordinance-search',
        'tax-civil-complaint-triage-draft',
        'tax-administrative-document-draft-review',
        'tax-policy-evidence-pack',
        'tax-document-hwpx-review',
    )),
    ('관세', (
        'tariff-hs-code-research',
        'customs-origin-document-precheck',
        'customs-trade-statistics-brief',
        'customs-law-citation-evidence-review',
        'customs-civil-complaint-triage-draft',
    )),
    ('감사', (
        'audit-evidence-cross-check',
        'audit-finding-response-draft-review',
        'audit-action-plan-evidence-review',
        'audit-legal-basis-citation-review',
        'audit-records-disclosure-redaction-review',
    )),
    ('통계', (
        'kosis-statistics-lookup',
        'official-statistics-methodology-evidence-review',
        'statistical-release-evidence-brief',
        'statistics-civil-complaint-triage-draft',
        'statistics-quality-evidence-pack',
    )),
    ('조달', (
        'public-procurement-plan-check',
        'ai-product-procurement-readiness-check',
        'procurement-specification-hwpx-review',
        'procurement-law-citation-evidence-review',
        'procurement-records-disclosure-redaction-review',
    )),
    ('외교', (
        'official-country-brief',
        'treaty-diplomatic-document-source-check',
        'overseas-safety-country-brief',
        'diplomatic-policy-evidence-pack',
        'diplomatic-treaty-law-citation-review',
    )),
    ('통일', (
        'unification-policy-source-search',
        'inter-korean-policy-timeline-evidence-pack',
        'dmz-policy-source-brief',
        'unification-law-citation-evidence-review',
        'unification-policy-statistics-brief',
    )),
    ('선거관리', (
        'local-election-candidate-lookup',
        'election-law-procedure-evidence-review',
        'election-result-statistics-evidence-brief',
        'election-law-citation-verification',
        'election-records-disclosure-redaction-review',
    )),
    ('입법', (
        'assembly-bill-vote-lookup',
        'bill-comparison-impact-brief',
        'committee-minutes-evidence-pack',
        'legislative-records-disclosure-redaction-review',
        'legislative-enacted-law-citation-review',
    )),
    ('사법', (
        'law-court-registry-research',
        'judgment-citation-evidence-pack',
        'court-statistics-evidence-brief',
        'judicial-records-disclosure-redaction-review',
        'judicial-records-lifecycle-review',
    )),
    ('검찰', (
        'prosecution-legal-basis-research',
        'prosecution-official-source-evidence-review',
        'prosecution-statistics-evidence-brief',
        'prosecution-administrative-document-review',
        'prosecution-policy-evidence-brief',
    )),
    ('교정', (
        'corrections-regulation-search',
        'corrections-official-source-evidence-review',
        'corrections-statistics-evidence-brief',
        'corrections-administrative-document-review',
        'corrections-policy-evidence-brief',
    )),
    ('보호관찰', (
        'probation-compliance-search',
        'probation-official-source-evidence-review',
        'probation-statistics-evidence-brief',
        'probation-administrative-document-review',
        'probation-policy-evidence-brief',
    )),
    ('출입국', (
        'immigration-procedure-search',
        'immigration-civil-complaint-triage-draft',
        'immigration-statistics-policy-brief',
        'immigration-law-citation-evidence-review',
        'immigration-records-disclosure-redaction-review',
    )),
    ('경찰', (
        'police-lost-property-lookup',
        'police-civil-complaint-triage-draft',
        'police-crime-statistics-brief',
        'police-law-citation-evidence-review',
        'police-records-disclosure-redaction-review',
    )),
    ('해양경찰', (
        'maritime-safety-brief',
        'coast-guard-official-source-evidence-review',
        'coast-guard-statistics-evidence-brief',
        'coast-guard-administrative-document-review',
        'coast-guard-policy-evidence-brief',
    )),
    ('소방', (
        'fire-emergency-resource-brief',
        'fire-safety-standard-evidence-pack',
        'fire-response-statistics-brief',
        'fire-law-citation-evidence-review',
        'fire-records-disclosure-redaction-review',
    )),
    ('재난안전', (
        'disaster-situation-brief',
        'disaster-public-message-draft-review',
        'disaster-response-plan-evidence-review',
        'disaster-law-citation-evidence-review',
        'disaster-records-disclosure-redaction-review',
    )),
    ('국방', (
        'defense-procurement-notice-search',
        'defense-official-source-evidence-review',
        'defense-statistics-evidence-brief',
        'defense-administrative-document-review',
        'defense-policy-evidence-brief',
    )),
    ('군무', (
        'civilian-military-regulation-search',
        'military-civil-service-official-source-evidence-review',
        'military-civil-service-statistics-evidence-brief',
        'military-civil-service-administrative-document-review',
        'military-civil-service-policy-evidence-brief',
    )),
    ('경호', (
        'public-event-security-review',
        'security-protection-official-source-evidence-review',
        'security-protection-statistics-evidence-brief',
        'security-protection-administrative-document-review',
        'security-protection-policy-evidence-brief',
    )),
    ('교육', (
        'education-public-data-search',
        'education-statistics-brief',
        'school-policy-document-review',
        'education-civil-complaint-triage-draft',
        'education-policy-evidence-pack',
    )),
    ('교육행정', (
        'education-procurement-notice-search',
        'education-administrative-document-draft-review',
        'school-facility-safety-plan-review',
        'education-records-disclosure-redaction-review',
        'education-records-lifecycle-review',
    )),
    ('사회복지', (
        'welfare-pension-support-search',
        'welfare-civil-complaint-triage-draft',
        'welfare-eligibility-evidence-check',
        'welfare-policy-statistics-brief',
        'welfare-administrative-document-draft-review',
    )),
    ('고용노동', (
        'labor-job-law-research',
        'labor-civil-complaint-triage-draft',
        'industrial-accident-statistics-brief',
        'labor-law-citation-evidence-review',
        'workplace-safety-policy-evidence-pack',
    )),
    ('보건의료', (
        'healthcare-facility-search',
        'healthcare-policy-statistics-brief',
        'medical-benefit-criteria-evidence-pack',
        'healthcare-civil-complaint-triage-draft',
        'healthcare-public-notice-multilingual-review',
    )),
    ('식품의약', (
        'food-drug-safety-check',
        'food-drug-recall-evidence-brief',
        'regulatory-notice-comparison-review',
        'food-drug-labeling-guidance-evidence-review',
        'food-drug-public-notice-multilingual-review',
    )),
    ('농업', (
        'agriculture-weather-statistics',
        'agriculture-official-source-evidence-review',
        'agriculture-statistics-evidence-brief',
        'agriculture-administrative-document-review',
        'agriculture-policy-evidence-brief',
    )),
    ('축산', (
        'livestock-disease-statistics',
        'livestock-official-source-evidence-review',
        'livestock-statistics-evidence-brief',
        'livestock-administrative-document-review',
        'livestock-policy-evidence-brief',
    )),
    ('농촌지도', (
        'rural-extension-brief',
        'rural-extension-official-source-evidence-review',
        'rural-extension-statistics-evidence-brief',
        'rural-extension-administrative-document-review',
        'rural-extension-policy-evidence-brief',
    )),
    ('산림', (
        'forest-recreation-weather',
        'forestry-official-source-evidence-review',
        'forestry-statistics-evidence-brief',
        'forestry-administrative-document-review',
        'forestry-policy-evidence-brief',
    )),
    ('해양수산', (
        'fisheries-weather-statistics',
        'marine-fisheries-official-source-evidence-review',
        'marine-fisheries-statistics-evidence-brief',
        'marine-fisheries-administrative-document-review',
        'marine-fisheries-policy-evidence-brief',
    )),
    ('환경', (
        'environment-air-water-waste',
        'environment-official-source-evidence-review',
        'environment-statistics-evidence-brief',
        'environment-administrative-document-review',
        'environment-policy-evidence-brief',
    )),
    ('기상', (
        'kma-weather-forecast',
        'meteorology-official-source-evidence-review',
        'meteorology-statistics-evidence-brief',
        'meteorology-administrative-document-review',
        'meteorology-policy-evidence-brief',
    )),
    ('국토교통', (
        'public-transit-map-research',
        'transport-policy-project-evidence-pack',
        'traffic-safety-statistics-brief',
        'land-transport-procedure-evidence-review',
        'land-transport-statistics-evidence-brief',
    )),
    ('토목시설', (
        'civil-facility-project-review',
        'construction-standard-bim-compliance-precheck',
        'infrastructure-maintenance-evidence-review',
        'infrastructure-procedure-evidence-review',
        'infrastructure-statistics-evidence-brief',
    )),
    ('건축', (
        'land-building-housing-research',
        'building-permit-document-precheck',
        'building-code-citation-check',
        'architecture-procedure-evidence-review',
        'architecture-statistics-evidence-brief',
    )),
    ('도시계획', (
        'urban-planning-density-land',
        'urban-planning-official-source-evidence-review',
        'urban-planning-statistics-evidence-brief',
        'urban-planning-administrative-document-review',
        'urban-planning-policy-evidence-brief',
    )),
    ('산업', (
        'corporate-industry-information',
        'industry-official-source-evidence-review',
        'industry-statistics-evidence-brief',
        'industry-administrative-document-review',
        'industry-policy-evidence-brief',
    )),
    ('에너지', (
        'fuel-energy-statistics',
        'energy-official-source-evidence-review',
        'energy-statistics-evidence-brief',
        'energy-administrative-document-review',
        'energy-policy-evidence-brief',
    )),
    ('중소기업', (
        'sme-startup-due-diligence',
        'sme-official-source-evidence-review',
        'sme-statistics-evidence-brief',
        'sme-administrative-document-review',
        'sme-policy-evidence-brief',
    )),
    ('과학기술', (
        'science-technology-trend-search',
        'national-rd-program-evidence-brief',
        'technology-impact-evidence-pack',
        'science-technology-procedure-evidence-review',
        'science-technology-statistics-evidence-brief',
    )),
    ('특허', (
        'korean-patent-lookup',
        'patent-claim-citation-evidence-review',
        'ip-policy-statistics-evidence-brief',
        'patent-procedure-evidence-review',
        'patent-statistics-evidence-brief',
    )),
    ('정보통신', (
        'ict-policy-domain-research',
        'ict-official-source-evidence-review',
        'ict-statistics-evidence-brief',
        'ict-administrative-document-review',
        'ict-policy-evidence-brief',
    )),
    ('전산', (
        'public-it-operations-check',
        'public-it-project-procedure-check',
        'public-it-security-checklist-review',
        'public-it-procedure-evidence-review',
        'public-it-statistics-evidence-brief',
    )),
    ('사이버보안', (
        'privacy-security-baseline-review',
        'privacy-impact-evidence-review',
        'cyber-incident-response-plan-evidence-review',
        'cybersecurity-procedure-evidence-review',
        'cybersecurity-statistics-evidence-brief',
    )),
    ('문화예술', (
        'performance-arts-search',
        'arts-culture-official-source-evidence-review',
        'arts-culture-statistics-evidence-brief',
        'arts-culture-administrative-document-review',
        'arts-culture-policy-evidence-brief',
    )),
    ('체육', (
        'sports-results-facility-search',
        'sports-official-source-evidence-review',
        'sports-statistics-evidence-brief',
        'sports-administrative-document-review',
        'sports-policy-evidence-brief',
    )),
    ('관광', (
        'public-tourism-information',
        'tourism-official-source-evidence-review',
        'tourism-statistics-evidence-brief',
        'tourism-administrative-document-review',
        'tourism-policy-evidence-brief',
    )),
    ('문화유산', (
        'cultural-heritage-source-search',
        'cultural-heritage-official-source-evidence-review',
        'cultural-heritage-statistics-evidence-brief',
        'cultural-heritage-administrative-document-review',
        'cultural-heritage-policy-evidence-brief',
    )),
    ('기록관리', (
        'records-classification-hwpx',
        'public-record-disclosure-redaction-review',
        'records-retention-schedule-review',
        'records-management-procedure-evidence-review',
        'records-management-statistics-evidence-brief',
    )),
    ('도서관', (
        'public-library-holdings-search',
        'library-official-source-evidence-review',
        'library-statistics-evidence-brief',
        'library-administrative-document-review',
        'library-policy-evidence-brief',
    )),
    ('학예연구', (
        'museum-object-provenance-research',
        'museum-research-official-source-evidence-review',
        'museum-research-statistics-evidence-brief',
        'museum-research-administrative-document-review',
        'museum-research-policy-evidence-brief',
    )),
    ('연구', (
        'official-research-brief',
        'research-official-source-evidence-review',
        'research-statistics-evidence-brief',
        'research-administrative-document-review',
        'research-policy-evidence-brief',
    )),
    ('지방자치', (
        'local-government-business-status',
        'local-government-civil-complaint-triage-draft',
        'local-government-administrative-document-draft-review',
        'local-government-public-policy-evidence-pack',
        'local-ordinance-draft-review',
    )),
    ('지역개발', (
        'regional-development-housing-land',
        'regional-development-official-source-evidence-review',
        'regional-development-statistics-evidence-brief',
        'regional-development-administrative-document-review',
        'regional-development-policy-evidence-brief',
    )),
    ('지방의회', (
        'local-council-minutes-ordinance',
        'local-council-agenda-draft-review',
        'local-council-budget-bill-comparison',
        'local-council-procedure-evidence-review',
        'local-council-statistics-evidence-brief',
    )),
    ('우정', (
        'postal-code-delivery-tracking',
        'postal-official-source-evidence-review',
        'postal-statistics-evidence-brief',
        'postal-administrative-document-review',
        'postal-policy-evidence-brief',
    )),
)

_RESEARCH_SOURCE_VALUES: Final = {
    "wiki_authority": "domains/harness-engineering/korea-local-agent-skillpack-runtime-contract.md",
    "wiki_source_map": "raw/2026-05-28-nomadamas-k-skill-source-map.md",
    "reference_repository": "https://github.com/NomaDamas/k-skill",
    "reference_head": "0c1bcdc9288545297897b0eee349d30ab2e1b230",
}
_RESEARCH_V6_SHAPE: Final = (
    ("wiki_authority", "wiki_source_map", "reference_repository", "reference_head"),
    frozenset(),
)
_CAPABILITY_V6_SHAPE: Final = (tuple(CAPABILITY_REQUIRED_KEYS), frozenset())
_DOMAIN_V6_SHAPE: Final = (("domain", "group", "evidence", "skills"), frozenset())
_SKILL_V6_SHAPE: Final = (
    ("name", "title", "capability", "role", "reference_skills", "boundary"),
    frozenset({"task_checks", "runtime_binding"}),
)


def _validate_capability_v6_fields(
    capability: dict[str, JSONValue],
    pointer: str,
    errors: list[str],
) -> None:
    string_fields = (
        "slug",
        "locale",
        "jurisdiction",
        "service",
        "credential_class",
        "proxy_mode",
        "side_effect_class",
        "manual_handoff_gate",
        "execution_status",
        "live_smoke",
        "runtime_contract_id",
    )
    valid_strings: dict[str, str] = {}
    for field in string_fields:
        if field not in capability:
            continue
        value = capability[field]
        field_pointer = _pointer_child(pointer, field)
        if not isinstance(value, str):
            _append_error(errors, "V6_INVALID_TYPE", field_pointer)
        else:
            valid_strings[field] = value

    slug = valid_strings.get("slug")
    if slug is not None and SLUG.fullmatch(slug) is None:
        _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "slug"))
    for field, expected in (("locale", "ko-KR"), ("jurisdiction", "KR")):
        value = valid_strings.get(field)
        if value is not None and value != expected:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, field))
    for field in ("service", "manual_handoff_gate"):
        value = valid_strings.get(field)
        if value is not None and not value.strip():
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, field))
    for field, allowed in (
        ("credential_class", CREDENTIAL_CLASSES),
        ("proxy_mode", PROXY_MODES),
        ("side_effect_class", SIDE_EFFECT_CLASSES),
        ("execution_status", EXECUTION_STATUSES),
        ("live_smoke", LIVE_SMOKE_STATUSES),
    ):
        value = valid_strings.get(field)
        if value is not None and value not in allowed:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, field))

    contract_id = valid_strings.get("runtime_contract_id")
    if contract_id is not None and re.fullmatch(
        r"kgov/[a-z0-9]+(?:-[a-z0-9]+)*/v1",
        contract_id,
    ) is None:
        _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "runtime_contract_id"))

    for field, require_nonempty, validate_format in (
        ("source_provenance", True, _valid_https_url),
        ("source_policy_ids", False, lambda value: SLUG.fullmatch(value) is not None),
    ):
        if field not in capability:
            continue
        values = capability[field]
        values_pointer = _pointer_child(pointer, field)
        if not isinstance(values, list):
            _append_error(errors, "V6_INVALID_TYPE", values_pointer)
            continue
        if require_nonempty and not values:
            _append_error(errors, "V6_INVALID_VALUE", values_pointer)
        for index, value in enumerate(values):
            value_pointer = _pointer_child(values_pointer, index)
            if not isinstance(value, str):
                _append_error(errors, "V6_INVALID_TYPE", value_pointer)
            elif not validate_format(value):
                _append_error(errors, "V6_INVALID_FORMAT", value_pointer)

    execution_status = valid_strings.get("execution_status")
    live_smoke = valid_strings.get("live_smoke")
    if (
        execution_status in EXECUTION_STATUSES
        and live_smoke in LIVE_SMOKE_STATUSES
        and (
            (execution_status == "live-verified" and live_smoke != "passed")
            or (live_smoke == "passed" and execution_status != "live-verified")
        )
    ):
        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "live_smoke"))


def _expected_domain_skill_names() -> dict[str, set[str]]:
    return {domain: set(skills) for domain, skills in _EXPECTED_DOMAIN_SKILLS}


def _validate_v6_identities(
    data: dict[str, JSONValue],
    errors: list[str],
) -> None:
    start = len(errors)
    expected_topology = _expected_domain_skill_names()
    expected_domains = set(expected_topology)
    minimums = data.get("enforced_minimum_skills_by_domain")
    if isinstance(minimums, dict):
        minimum_pointer = "/enforced_minimum_skills_by_domain"
        for domain in sorted(expected_domains - set(minimums)):
            _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(minimum_pointer, domain))
        for domain in sorted(set(minimums) - expected_domains):
            _append_error(errors, "V6_UNKNOWN_FIELD", _pointer_child(minimum_pointer, domain))
        for domain in sorted(set(minimums) & expected_domains):
            value = minimums[domain]
            pointer = _pointer_child(minimum_pointer, domain)
            if type(value) is not int:
                _append_error(errors, "V6_INVALID_TYPE", pointer)
            elif not 1 <= value <= TARGET_SKILLS_PER_DOMAIN:
                _append_error(errors, "V6_INVALID_VALUE", pointer)

    capabilities = data.get("shared_capabilities")
    expected_capabilities = tuple(item[0] for item in _APPROVED_RUNTIME_MANIFEST)
    valid_capability_ids: set[str] = set()
    capabilities_by_slug: dict[str, dict[str, JSONValue]] = {}
    if isinstance(capabilities, list):
        seen_capabilities: set[str] = set()
        for index, capability in enumerate(capabilities):
            if not isinstance(capability, dict):
                continue
            slug = capability.get("slug")
            if not isinstance(slug, str):
                continue
            capabilities_by_slug[slug] = capability
            pointer = _pointer_child(_pointer_child("/shared_capabilities", index), "slug")
            if slug in seen_capabilities:
                _append_error(errors, "V6_DUPLICATE_ID", pointer)
            elif index >= len(expected_capabilities) or slug != expected_capabilities[index]:
                _append_error(errors, "V6_INVALID_VALUE", pointer)
            else:
                valid_capability_ids.add(slug)
            seen_capabilities.add(slug)

    domains = data.get("domains")
    if isinstance(domains, list):
        seen_domains: set[str] = set()
        seen_skills: set[str] = set()
        for domain_index, domain in enumerate(domains):
            if not isinstance(domain, dict):
                continue
            domain_name = domain.get("domain")
            domain_pointer = _pointer_child(_pointer_child("/domains", domain_index), "domain")
            domain_valid = isinstance(domain_name, str)
            if domain_valid and domain_name in seen_domains:
                _append_error(errors, "V6_DUPLICATE_ID", domain_pointer)
                domain_valid = False
            elif domain_valid and domain_name not in expected_domains:
                _append_error(errors, "V6_INVALID_VALUE", domain_pointer)
                domain_valid = False
            if isinstance(domain_name, str):
                seen_domains.add(domain_name)
            skills = domain.get("skills")
            if not isinstance(skills, list):
                continue
            if domain_valid and len(skills) != len(expected_topology[domain_name]):
                _append_error(
                    errors,
                    "V6_INVALID_VALUE",
                    _pointer_child(_pointer_child("/domains", domain_index), "skills"),
                )
            for skill_index, skill in enumerate(skills):
                if not isinstance(skill, dict):
                    continue
                skill_pointer = _pointer_child(
                    _pointer_child(_pointer_child("/domains", domain_index), "skills"),
                    skill_index,
                )
                name = skill.get("name")
                name_pointer = _pointer_child(skill_pointer, "name")
                if isinstance(name, str):
                    if name in seen_skills:
                        _append_error(errors, "V6_DUPLICATE_ID", name_pointer)
                    elif domain_valid and name not in expected_topology[domain_name]:
                        _append_error(errors, "V6_INVALID_VALUE", name_pointer)
                    seen_skills.add(name)
                capability = skill.get("capability")
                if isinstance(capability, str) and capability not in valid_capability_ids:
                    _append_error(
                        errors,
                        "V6_UNKNOWN_REFERENCE",
                        _pointer_child(skill_pointer, "capability"),
                    )
                references = skill.get("reference_skills")
                if isinstance(references, list):
                    seen_references: set[str] = set()
                    for ref_index, reference in enumerate(references):
                        if not isinstance(reference, str):
                            continue
                        if reference in seen_references:
                            _append_error(
                                errors,
                                "V6_DUPLICATE_VALUE",
                                _pointer_child(
                                    _pointer_child(skill_pointer, "reference_skills"),
                                    ref_index,
                                ),
                            )
                        seen_references.add(reference)
            if domain_valid:
                primary_count = sum(
                    isinstance(skill, dict) and skill.get("role") == "primary"
                    for skill in skills
                )
                if primary_count != 1:
                    _append_error(
                        errors,
                        "V6_INVALID_VALUE",
                        _pointer_child(_pointer_child("/domains", domain_index), "skills"),
                    )
                evidence = domain.get("evidence")
                for skill_index, skill in enumerate(skills):
                    if not isinstance(skill, dict):
                        continue
                    skill_pointer = _pointer_child(
                        _pointer_child(_pointer_child("/domains", domain_index), "skills"),
                        skill_index,
                    )
                    references = skill.get("reference_skills")
                    if (
                        primary_count == 1
                        and skill.get("role") == "primary"
                        and isinstance(references, list)
                        and (
                            (evidence in {"direct", "adjacent"} and not references)
                            or (evidence in {"new", "sensitive"} and references)
                        )
                    ):
                        _append_error(
                            errors,
                            "V6_INVALID_VALUE",
                            _pointer_child(skill_pointer, "reference_skills"),
                        )
                    if evidence == "sensitive" and skill.get("boundary") != "manual-review-only":
                        _append_error(
                            errors,
                            "V6_INVALID_VALUE",
                            _pointer_child(skill_pointer, "boundary"),
                        )
                    capability = capabilities_by_slug.get(skill.get("capability"))
                    if (
                        skill.get("boundary") == "read-only"
                        and capability is not None
                        and capability.get("side_effect_class") == "draft-only"
                    ):
                        _append_error(
                            errors,
                            "V6_BINDING_MISMATCH",
                            _pointer_child(skill_pointer, "boundary"),
                        )
    _sort_errors(errors, start)


def _validate_approved_runtime_manifest(
    data: dict[str, JSONValue],
    errors: list[str],
) -> None:
    start = len(errors)
    contracts = data.get("runtime_contracts")
    if not isinstance(contracts, list):
        return
    for index, expected in enumerate(_APPROVED_RUNTIME_MANIFEST):
        if index >= len(contracts) or not isinstance(contracts[index], dict):
            continue
        contract = contracts[index]
        slug, kind, network, expected_operations = expected
        pointer = _pointer_child("/runtime_contracts", index)
        expected_fields = {
            "id": f"kgov/{slug}/v1",
            "capability_slug": slug,
            "module": f"kgov_runtime.capabilities.{slug.replace('-', '_')}",
            "kind": kind,
            "network_mode": network,
            "default_operation_id": f"kgov/{slug}/{expected_operations[0][0]}/v1",
        }
        for field, expected_value in expected_fields.items():
            if contract.get(field) != expected_value:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, field))
        operations = contract.get("operations")
        operations_pointer = _pointer_child(pointer, "operations")
        if not isinstance(operations, list):
            continue
        if len(operations) != len(expected_operations):
            _append_error(errors, "V6_CONTRACT_INVARIANT", operations_pointer)
            continue
        for operation_index, operation_spec in enumerate(expected_operations):
            operation = operations[operation_index]
            if not isinstance(operation, dict):
                continue
            operation_name, policy_ids, output_mode, has_fixture = operation_spec
            operation_pointer = _pointer_child(operations_pointer, operation_index)
            expected_operation_fields = {
                "id": f"kgov/{slug}/{operation_name}/v1",
                "schema_status": "declared",
                "source_policy_ids": list(policy_ids),
                "source_output_mode": output_mode,
            }
            for field, expected_value in expected_operation_fields.items():
                if operation.get(field) != expected_value:
                    _append_error(
                        errors,
                        "V6_CONTRACT_INVARIANT",
                        _pointer_child(operation_pointer, field),
                    )
            if (operation.get("fixture_argv") == ["--fixture"]) != has_fixture:
                _append_error(
                    errors,
                    "V6_CONTRACT_INVARIANT",
                    _pointer_child(operation_pointer, "fixture_argv"),
                )
    _sort_errors(errors, start)


def _validate_v6_shape(data: dict[str, JSONValue], errors: list[str]) -> None:
    _validate_object_shape(data, "", _ROOT_V6_SHAPE, errors)
    if "schema_version" in data and (
        type(data["schema_version"]) is not int or data["schema_version"] != 6
    ):
        _append_error(errors, "V6_UNSUPPORTED_SCHEMA_VERSION", "/schema_version")
    if "target_skills_per_domain" in data and (
        type(data["target_skills_per_domain"]) is not int
        or data["target_skills_per_domain"] != TARGET_SKILLS_PER_DOMAIN
    ):
        _append_error(errors, "V6_INVALID_VALUE", "/target_skills_per_domain")
    if "enforced_minimum_skills_by_domain" in data and not isinstance(
        data["enforced_minimum_skills_by_domain"], dict
    ):
        _append_error(errors, "V6_INVALID_TYPE", "/enforced_minimum_skills_by_domain")
    research = data.get("research_source")
    if "research_source" in data:
        _validate_object_shape(research, "/research_source", _RESEARCH_V6_SHAPE, errors)
        if isinstance(research, dict):
            for key in ("wiki_authority", "wiki_source_map"):
                if key in research and not isinstance(research[key], str):
                    _append_error(errors, "V6_INVALID_TYPE", _pointer_child("/research_source", key))
            repository = research.get("reference_repository")
            if "reference_repository" in research and (
                not isinstance(repository, str) or not _valid_https_url(repository)
            ):
                _append_error(errors, "V6_INVALID_FORMAT", "/research_source/reference_repository")
            head = research.get("reference_head")
            if "reference_head" in research and (
                not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None
            ):
                _append_error(errors, "V6_INVALID_FORMAT", "/research_source/reference_head")
            for key, expected in _RESEARCH_SOURCE_VALUES.items():
                if isinstance(research.get(key), str) and research[key] != expected:
                    _append_error(
                        errors,
                        "V6_INVALID_VALUE",
                        _pointer_child("/research_source", key),
                    )
    for key in ("source_policies", "runtime_contracts", "shared_capabilities", "domains"):
        if key in data and not isinstance(data[key], list):
            _append_error(errors, "V6_INVALID_TYPE", _pointer_child("", key))
    for key, expected_count in (("runtime_contracts", 22), ("shared_capabilities", 22), ("domains", 60)):
        value = data.get(key)
        if isinstance(value, list) and len(value) != expected_count:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child("", key))
    capabilities = data.get("shared_capabilities")
    if isinstance(capabilities, list):
        for index, capability in enumerate(capabilities):
            capability_pointer = _pointer_child("/shared_capabilities", index)
            _validate_object_shape(
                capability,
                capability_pointer,
                _CAPABILITY_V6_SHAPE,
                errors,
            )
            if isinstance(capability, dict):
                _validate_capability_v6_fields(capability, capability_pointer, errors)
    domains = data.get("domains")
    if isinstance(domains, list):
        for domain_index, domain in enumerate(domains):
            domain_pointer = _pointer_child("/domains", domain_index)
            _validate_object_shape(domain, domain_pointer, _DOMAIN_V6_SHAPE, errors)
            if not isinstance(domain, dict):
                continue
            for key in ("domain", "group", "evidence"):
                if key in domain and not isinstance(domain[key], str):
                    _append_error(errors, "V6_INVALID_TYPE", _pointer_child(domain_pointer, key))
            if isinstance(domain.get("domain"), str) and not domain["domain"]:
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "domain"))
            if isinstance(domain.get("group"), str) and domain["group"] not in GROUP_ORDER:
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "group"))
            if isinstance(domain.get("evidence"), str) and domain["evidence"] not in EVIDENCE:
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "evidence"))
            skills = domain.get("skills")
            if "skills" in domain and not isinstance(skills, list):
                _append_error(errors, "V6_INVALID_TYPE", _pointer_child(domain_pointer, "skills"))
                continue
            if isinstance(skills, list):
                if not skills:
                    _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "skills"))
                for skill_index, skill in enumerate(skills):
                    skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skill_index)
                    _validate_object_shape(
                        skill,
                        skill_pointer,
                        _SKILL_V6_SHAPE,
                        errors,
                    )
                    if not isinstance(skill, dict):
                        continue
                    for key in ("name", "title", "capability", "role", "boundary"):
                        if key in skill and not isinstance(skill[key], str):
                            _append_error(errors, "V6_INVALID_TYPE", _pointer_child(skill_pointer, key))
                    for key in ("name", "capability"):
                        value = skill.get(key)
                        if isinstance(value, str) and SLUG.fullmatch(value) is None:
                            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(skill_pointer, key))
                    if isinstance(skill.get("title"), str) and not skill["title"]:
                        _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "title"))
                    for key, allowed in (("role", ROLES), ("boundary", BOUNDARIES)):
                        value = skill.get(key)
                        if isinstance(value, str) and value not in allowed:
                            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, key))
                    for key in ("reference_skills", "task_checks"):
                        if key not in skill:
                            continue
                        values = skill[key]
                        values_pointer = _pointer_child(skill_pointer, key)
                        if not isinstance(values, list):
                            _append_error(errors, "V6_INVALID_TYPE", values_pointer)
                            continue
                        if key == "task_checks" and not 1 <= len(values) <= 8:
                            _append_error(errors, "V6_INVALID_VALUE", values_pointer)
                        for value_index, value in enumerate(values):
                            value_pointer = _pointer_child(values_pointer, value_index)
                            if not isinstance(value, str):
                                _append_error(errors, "V6_INVALID_TYPE", value_pointer)
                            elif key == "reference_skills" and SLUG.fullmatch(value) is None:
                                _append_error(errors, "V6_INVALID_FORMAT", value_pointer)
                            elif key == "task_checks" and (not value.strip() or len(value) > 200):
                                _append_error(errors, "V6_INVALID_VALUE", value_pointer)
    _sort_errors(errors, 0)


def _validate_v6_registries(
    data: dict[str, JSONValue],
    on_date: date,
    errors: list[str],
) -> None:
    _validate_source_policies(data, on_date=on_date, errors=errors)
    _validate_runtime_contracts(data, errors=errors)
    contracts = data.get("runtime_contracts")
    contracts_by_id = {
        contract["id"]: contract
        for contract in contracts
        if isinstance(contracts, list)
        and isinstance(contract, dict)
        and isinstance(contract.get("id"), str)
    }
    domains = data.get("domains")
    if isinstance(domains, list):
        for domain_index, domain in enumerate(domains):
            if not isinstance(domain, dict):
                continue
            skills = domain.get("skills")
            if not isinstance(skills, list):
                continue
            for skill_index, skill in enumerate(skills):
                if not isinstance(skill, dict) or "runtime_binding" not in skill:
                    continue
                capability = skill.get("capability")
                if not isinstance(capability, str):
                    continue
                pointer = _pointer_child(
                    _pointer_child(
                        _pointer_child(_pointer_child("/domains", domain_index), "skills"),
                        skill_index,
                    ),
                    "runtime_binding",
                )
                _validate_runtime_binding(
                    skill["runtime_binding"],
                    capability_slug=capability,
                    contracts_by_id=contracts_by_id,
                    pointer=pointer,
                    errors=errors,
                )
    _sort_errors(errors, 0)


def collect_used_capabilities(domains: list[dict[str, Any]]) -> set[str]:
    used: set[str] = set()
    for domain in domains:
        skills = domain.get("skills", [])
        if not isinstance(skills, list):
            continue
        used.update(
            skill["capability"]
            for skill in skills
            if isinstance(skill, dict) and isinstance(skill.get("capability"), str)
        )
    return used


def _skill_contract_matches(actual: dict[str, Any], contract: dict[str, Any]) -> bool:
    scalar_matches = all(
        actual.get(key) == value
        for key, value in contract.items()
        if key not in {"reference_skills", "task_checks"}
    )
    return (
        scalar_matches
        and tuple(actual.get("reference_skills") or ()) == contract["reference_skills"]
        and tuple(actual.get("task_checks") or ()) == contract["task_checks"]
    )


def _append_skill_contract_errors(
    actual: dict[str, Any],
    contract: dict[str, Any],
    pointer: str,
    errors: list[str],
) -> None:
    for field, expected in contract.items():
        value = tuple(actual.get(field) or ()) if field in {"reference_skills", "task_checks"} else actual.get(field)
        if value != expected:
            _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, field))


def _validate_instructions(root: Path, errors: list[str]) -> None:
    contracts = {
        "CLAUDE.md": {
            "max_lines": 80,
            "anchors": (
                "domains/<domain>/skills/<unique-slug>/SKILL.md",
                "top-level `skills/`",
                "catalog/domain-skills.json",
                "python3 scripts/check.py",
                "비밀값",
                "명시적 승인",
            ),
        },
        "AGENTS.md": {
            "max_lines": 20,
            "anchors": (
                "CLAUDE.md",
                "domains/<domain>/skills/",
                "top-level `skills/`",
                "python3 scripts/check.py",
            ),
        },
    }
    for name, contract in contracts.items():
        path = root / name
        if not path.is_file():
            _append_error(errors, "V6_CONTRACT_INVARIANT", "")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            _append_error(errors, "V6_CONTRACT_INVARIANT", "")
            continue
        if len(text.splitlines()) > contract["max_lines"]:
            _append_error(errors, "V6_CONTRACT_INVARIANT", "")
        for anchor in contract["anchors"]:
            if anchor not in text:
                _append_error(errors, "V6_CONTRACT_INVARIANT", "")
    for typo in ("Agent.md", "Cluade.md"):
        if (root / typo).exists():
            _append_error(errors, "V6_CONTRACT_INVARIANT", "")


def _validate_capabilities(
    raw_capabilities: Any,
    root: Path,
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    if not isinstance(raw_capabilities, list):
        _append_error(errors, "V6_INVALID_TYPE", "/shared_capabilities")
        return set(), {}
    if len(raw_capabilities) != 22:
        _append_error(errors, "V6_INVALID_VALUE", "/shared_capabilities")
    slugs: set[str] = set()
    by_slug: dict[str, dict[str, Any]] = {}
    for index, capability in enumerate(raw_capabilities):
        pointer = _pointer_child("/shared_capabilities", index)
        if not isinstance(capability, dict):
            _append_error(errors, "V6_INVALID_TYPE", pointer)
            continue
        missing = CAPABILITY_REQUIRED_KEYS - set(capability)
        if missing:
            for field in missing:
                _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(pointer, field))
            continue
        slug = capability["slug"]
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "slug"))
            continue
        if slug in slugs:
            _append_error(errors, "V6_DUPLICATE_ID", _pointer_child(pointer, "slug"))
        slugs.add(slug)
        by_slug[slug] = capability
        if capability["locale"] != "ko-KR":
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "locale"))
        if capability["jurisdiction"] != "KR":
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "jurisdiction"))
        for field, allowed in (
            ("credential_class", CREDENTIAL_CLASSES),
            ("proxy_mode", PROXY_MODES),
            ("side_effect_class", SIDE_EFFECT_CLASSES),
            ("execution_status", EXECUTION_STATUSES),
            ("live_smoke", LIVE_SMOKE_STATUSES),
        ):
            if capability[field] not in allowed:
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, field))
        if capability["execution_status"] == "live-verified" and capability["live_smoke"] != "passed":
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "live_smoke"))
        if capability["live_smoke"] == "passed" and capability["execution_status"] != "live-verified":
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(pointer, "live_smoke"))
        for contract in (
            WAVE_TWO_CAPABILITY_CONTRACTS.get(slug),
            WAVE_SEVEN_CAPABILITY_CONTRACTS.get(slug),
        ):
            if contract is None:
                continue
            contract_matches = all(
                capability.get(key) == value
                for key, value in contract.items()
                if key != "source_provenance"
            )
            contract_matches = (
                contract_matches
                and tuple(capability.get("source_provenance") or ())
                == contract["source_provenance"]
            )
            if not contract_matches:
                for field, expected in contract.items():
                    actual = tuple(capability.get(field) or ()) if field == "source_provenance" else capability.get(field)
                    if actual != expected:
                        _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, field))
        provenance = capability["source_provenance"]
        if not isinstance(provenance, list) or not provenance or not all(
            isinstance(url, str) and _valid_https_url(url) for url in provenance
        ):
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(pointer, "source_provenance"))
        expected_semantics = _EXPECTED_CAPABILITY_SERVICE_AND_PROVENANCE.get(slug)
        if expected_semantics is not None:
            expected_service, expected_provenance = expected_semantics
            if capability.get("service") != expected_service:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "service"))
            if tuple(provenance or ()) != expected_provenance:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(pointer, "source_provenance"))

        module = slug.replace("-", "_")
        required_paths = [
            root / "kgov_runtime" / "capabilities" / f"{module}.py",
            root / "tests" / "capabilities" / f"test_{module}.py",
            root / "tests" / "fixtures" / "capabilities" / f"{slug}.json",
            root / "docs" / "capabilities" / slug / "procedure.md",
            root / "docs" / "capabilities" / slug / "runtime-contract.md",
        ]
        for path in required_paths:
            if not path.is_file():
                _append_error(errors, "V6_CONTRACT_INVARIANT", pointer)
        if capability["execution_status"] == "live-verified":
            path = root / "docs" / "capabilities" / slug / "live-smoke.md"
            if not path.is_file():
                _append_error(errors, "V6_CONTRACT_INVARIANT", pointer)
    return slugs, by_slug


def validate(
    data: dict[str, Any],
    root: Path = ROOT,
    *,
    on_date: date | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [_diagnostic("V6_INVALID_TYPE", "")]
    _validate_v6_shape(data, errors)
    if errors:
        return errors
    _validate_v6_identities(data, errors)
    if errors:
        return errors
    _validate_v6_registries(
        data,
        on_date if on_date is not None else date.today(),
        errors,
    )
    if errors:
        return errors
    _validate_approved_runtime_manifest(data, errors)
    if errors:
        return errors
    target_skills = data.get("target_skills_per_domain")
    if type(target_skills) is not int or target_skills != TARGET_SKILLS_PER_DOMAIN:
        _append_error(errors, "V6_INVALID_VALUE", "/target_skills_per_domain")
    enforced_minimums = data.get("enforced_minimum_skills_by_domain")
    if not isinstance(enforced_minimums, dict):
        _append_error(errors, "V6_INVALID_TYPE", "/enforced_minimum_skills_by_domain")
        enforced_minimums = {}
    domains = data.get("domains")
    if not isinstance(domains, list):
        _append_error(errors, "V6_INVALID_TYPE", "/domains")
        _sort_errors(errors, 0)
        return errors
    if len(domains) != 60:
        _append_error(errors, "V6_INVALID_VALUE", "/domains")

    capability_slugs, capability_by_slug = _validate_capabilities(data.get("shared_capabilities"), root, errors)
    seen_domains: set[str] = set()
    seen_names: set[str] = set()
    declared_entrypoints: set[Path] = set()
    declared_entrypoint_pointers: dict[Path, str] = {}
    total_skills = 0

    for index, item in enumerate(domains):
        domain_pointer = _pointer_child("/domains", index)
        if not isinstance(item, dict):
            _append_error(errors, "V6_INVALID_TYPE", domain_pointer)
            continue
        missing = DOMAIN_REQUIRED_KEYS - set(item)
        if missing:
            for field in missing:
                _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(domain_pointer, field))
            continue
        domain = item["domain"]
        evidence = item["evidence"]
        skills = item["skills"]
        if not isinstance(domain, str) or not domain:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "domain"))
            continue
        if domain in seen_domains:
            _append_error(errors, "V6_DUPLICATE_ID", _pointer_child(domain_pointer, "domain"))
        seen_domains.add(domain)
        if item["group"] not in GROUP_ORDER:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "group"))
        if evidence not in EVIDENCE:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "evidence"))
        if not isinstance(skills, list) or not skills:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "skills"))
            continue
        enforced_minimum = enforced_minimums.get(domain)
        minimum_pointer = _pointer_child("/enforced_minimum_skills_by_domain", domain)
        if (
            type(enforced_minimum) is not int
            or not 1 <= enforced_minimum <= TARGET_SKILLS_PER_DOMAIN
        ):
            _append_error(errors, "V6_INVALID_VALUE", minimum_pointer)
        elif len(skills) < enforced_minimum:
            _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
        wave_two_contract = WAVE_TWO_SKILL_CONTRACTS.get(domain)
        if wave_two_contract is not None:
            expected_name = wave_two_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
            else:
                actual = matches[0]
                if not _skill_contract_matches(actual, wave_two_contract):
                    skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skills.index(actual))
                    _append_skill_contract_errors(actual, wave_two_contract, skill_pointer, errors)
        for wave_three_contract in WAVE_THREE_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_three_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
            elif not _skill_contract_matches(matches[0], wave_three_contract):
                actual = matches[0]
                skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skills.index(actual))
                _append_skill_contract_errors(actual, wave_three_contract, skill_pointer, errors)
        for wave_four_contract in WAVE_FOUR_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_four_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
            elif not _skill_contract_matches(matches[0], wave_four_contract):
                actual = matches[0]
                skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skills.index(actual))
                _append_skill_contract_errors(actual, wave_four_contract, skill_pointer, errors)
        for wave_five_contract in WAVE_FIVE_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_five_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
            elif not _skill_contract_matches(matches[0], wave_five_contract):
                actual = matches[0]
                skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skills.index(actual))
                _append_skill_contract_errors(actual, wave_five_contract, skill_pointer, errors)
        for wave_six_contract in WAVE_SIX_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_six_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
            elif not _skill_contract_matches(matches[0], wave_six_contract):
                actual = matches[0]
                skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skills.index(actual))
                _append_skill_contract_errors(actual, wave_six_contract, skill_pointer, errors)
        for wave_seven_contract in WAVE_SEVEN_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_seven_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(domain_pointer, "skills"))
            elif not _skill_contract_matches(matches[0], wave_seven_contract):
                actual = matches[0]
                skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skills.index(actual))
                _append_skill_contract_errors(actual, wave_seven_contract, skill_pointer, errors)
        total_skills += len(skills)
        primary_count = sum(isinstance(skill, dict) and skill.get("role") == "primary" for skill in skills)
        if primary_count != 1:
            _append_error(errors, "V6_INVALID_VALUE", _pointer_child(domain_pointer, "skills"))
        for skill_index, skill in enumerate(skills):
            skill_pointer = _pointer_child(_pointer_child(domain_pointer, "skills"), skill_index)
            if not isinstance(skill, dict):
                _append_error(errors, "V6_INVALID_TYPE", skill_pointer)
                continue
            missing_skill = SKILL_REQUIRED_KEYS - set(skill)
            if missing_skill:
                for field in missing_skill:
                    _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(skill_pointer, field))
                continue
            name = skill["name"]
            capability = skill["capability"]
            role = skill["role"]
            boundary = skill["boundary"]
            references = skill["reference_skills"]
            task_checks = skill.get("task_checks")
            if not isinstance(name, str) or not SLUG.fullmatch(name):
                _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(skill_pointer, "name"))
                continue
            if name in seen_names:
                _append_error(errors, "V6_DUPLICATE_ID", _pointer_child(skill_pointer, "name"))
            seen_names.add(name)
            if role not in ROLES:
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "role"))
            if not isinstance(capability, str) or not SLUG.fullmatch(capability):
                _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(skill_pointer, "capability"))
            elif capability not in capability_slugs:
                _append_error(errors, "V6_UNKNOWN_REFERENCE", _pointer_child(skill_pointer, "capability"))
            if boundary not in BOUNDARIES:
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "boundary"))
            capability_manifest = capability_by_slug.get(capability)
            if (
                boundary == "read-only"
                and capability_manifest is not None
                and capability_manifest.get("side_effect_class") == "draft-only"
            ):
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(skill_pointer, "boundary"))
            if not isinstance(references, list) or not all(
                isinstance(value, str) and SLUG.fullmatch(value) for value in references
            ):
                _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(skill_pointer, "reference_skills"))
                references = []
            if task_checks is not None and (
                not isinstance(task_checks, list)
                or not 1 <= len(task_checks) <= 8
                or not all(
                    isinstance(check, str) and check.strip() and len(check) <= 200
                    for check in task_checks
                )
            ):
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "task_checks"))
            expected_task_checks = WAVE_ONE_TASK_CHECKS.get(name)
            if expected_task_checks is not None and tuple(task_checks or ()) != expected_task_checks:
                _append_error(errors, "V6_CONTRACT_INVARIANT", _pointer_child(skill_pointer, "task_checks"))
            if role == "primary":
                if evidence in {"direct", "adjacent"} and not references:
                    _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "reference_skills"))
                if evidence in {"new", "sensitive"} and references:
                    _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "reference_skills"))
            if evidence == "sensitive" and boundary != "manual-review-only":
                _append_error(errors, "V6_INVALID_VALUE", _pointer_child(skill_pointer, "boundary"))
            entrypoint = Path("domains") / domain / "skills" / name / "SKILL.md"
            declared_entrypoints.add(entrypoint)
            declared_entrypoint_pointers[entrypoint] = skill_pointer

    if total_skills != 308:
        _append_error(errors, "V6_INVALID_VALUE", "/domains")
    minimum_domains = set(enforced_minimums)
    if minimum_domains != seen_domains:
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/enforced_minimum_skills_by_domain")
    domains_root = root / "domains"
    actual_domains = {path.name for path in domains_root.iterdir() if path.is_dir()} if domains_root.is_dir() else set()
    if actual_domains != seen_domains:
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")
    if (root / "skills").exists():
        _append_error(errors, "V6_CONTRACT_INVARIANT", "")

    actual_entrypoints = {path.relative_to(root) for path in domains_root.glob("*/skills/*/SKILL.md")}
    if actual_entrypoints != declared_entrypoints:
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")
    for entrypoint in declared_entrypoints:
        path = root / entrypoint
        if (path.exists() or path.is_symlink()) and (not path.is_file() or path.is_symlink()):
            _append_error(errors, "V6_CONTRACT_INVARIANT", declared_entrypoint_pointers[entrypoint])
    for _gitkeep in domains_root.glob("*/.gitkeep"):
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")

    used = collect_used_capabilities(domains)
    if used != capability_slugs:
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/shared_capabilities")
    if errors:
        _sort_errors(errors, 0)
        return errors
    try:
        from render_catalog import render_catalog
        from render_domain_skills import expected_domain_skills
    except ImportError:
        _append_error(errors, "V6_CONTRACT_INVARIANT", "")
        return errors
    try:
        expected_skills = expected_domain_skills(data, root)
    except (KeyError, TypeError):
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")
        expected_skills = {}
    for path, expected in expected_skills.items():
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        skill_pointer = declared_entrypoint_pointers.get(relative_path, "/domains")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            _append_error(errors, "V6_CONTRACT_INVARIANT", skill_pointer)
            continue
        if text != expected:
            _append_error(errors, "V6_CONTRACT_INVARIANT", skill_pointer)
        name_match = re.search(r"^name:\s*([^\s]+)\s*$", text, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)\s*$", text, re.MULTILINE)
        if not name_match or name_match.group(1) != path.parent.name:
            _append_error(errors, "V6_INVALID_FORMAT", _pointer_child(skill_pointer, "name"))
        if not description_match:
            _append_error(errors, "V6_REQUIRED_FIELD", _pointer_child(skill_pointer, "title"))

    generated = root / "docs" / "domain-skill-candidates.md"
    try:
        expected_catalog = render_catalog(data)
    except (KeyError, TypeError):
        _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")
    else:
        if not generated.is_file():
            _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")
        else:
            try:
                generated_text = generated.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")
            else:
                if generated_text != expected_catalog:
                    _append_error(errors, "V6_CONTRACT_INVARIANT", "/domains")

    _validate_instructions(root, errors)
    _sort_errors(errors, 0)
    return errors


def main() -> int:
    catalog_path = ROOT / "catalog/domain-skills.json"
    if not catalog_path.is_file():
        print('ERROR V6_REQUIRED_FIELD ""')
        return 1
    try:
        data = _load_json_strict(catalog_path)
    except StrictJsonError as error:
        print(f'ERROR {error.code} ""')
        return 1
    errors = validate(data, on_date=date.today())
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    counts = Counter(item["evidence"] for item in data["domains"])
    capabilities = collect_used_capabilities(data["domains"])
    domain_skills = sum(len(item["skills"]) for item in data["domains"])
    operations = [
        operation
        for contract in data["runtime_contracts"]
        for operation in contract["operations"]
    ]
    bindings = sum(
        "runtime_binding" in skill
        for domain in data["domains"]
        for skill in domain["skills"]
    )
    print(
        "PASS "
        f"schema={data['schema_version']} domains={len(data['domains'])} "
        f"domain_skills={domain_skills} capabilities={len(capabilities)} "
        f"source_policies={len(data['source_policies'])} "
        f"runtime_contracts={len(data['runtime_contracts'])} operations={len(operations)} "
        f"active_operations={sum(operation['schema_status'] == 'active' for operation in operations)} "
        f"bindings={bindings} top_level_skills=0 "
        + " ".join(f"{name}={counts[name]}" for name in ("direct", "adjacent", "new", "sensitive"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
