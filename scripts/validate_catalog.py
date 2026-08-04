#!/usr/bin/env python3
"""Validate the domain-owned Skill topology, capability runtime, and generated docs."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_catalog import GROUP_ORDER, render_catalog  # noqa: E402
from render_domain_skills import expected_domain_skills  # noqa: E402

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
SOCIAL_SERVICE_MINIMUM_FIVE_SKILLS = {'교육': {'education-civil-complaint-triage-draft': {'name': 'education-civil-complaint-triage-draft',
                                                   'title': '교육 민원 분류·답변 초안',
                                                   'capability': 'civil-complaint-triage-draft',
                                                   'role': 'additional',
                                                   'reference_skills': (),
                                                   'boundary': 'draft-only',
                                                   'task_checks': ('민원 목적·대상기관·학교급·요청사항·처리기한을 비식별 상태로 분리',
                                                                   '교육부·교육청·국가법령정보 공식 URL·조회일·문서 버전과 근거 공백을 보존',
                                                                   '소관 확정·학생 또는 학교 판단·처분·답변 발송은 교육 담당자 승인으로 이관')},
        'education-policy-evidence-pack': {'name': 'education-policy-evidence-pack',
                                           'title': '교육정책 근거 팩',
                                           'capability': 'public-policy-evidence-pack',
                                           'role': 'additional',
                                           'reference_skills': (),
                                           'boundary': 'draft-only',
                                           'task_checks': ('정책 대상·적용기관·시행시점·주장·평가지표를 분리',
                                                           '교육부·교육청·법령·KOSIS 공식 URL·조회일·문서 버전과 상충·미수집 근거를 구분',
                                                           '정책 효과·학교별 적용·자원배분·문서 결재와 발송은 교육 담당자 승인으로 이관')}},
 '교육행정': {'education-records-disclosure-redaction-review': {'name': 'education-records-disclosure-redaction-review',
                                                            'title': '교육기록 정보공개·마스킹 검토',
                                                            'capability': 'public-record-disclosure-redaction-review',
                                                            'role': 'additional',
                                                            'reference_skills': (),
                                                            'boundary': 'draft-only',
                                                            'task_checks': ('학생·보호자·교직원 기록의 문서유형·정보항목·청구범위·부분공개 후보를 '
                                                                            '분리',
                                                                            '개인정보 원문을 저장하지 않고 공식 정보공개·기록관리 법령 '
                                                                            'URL·조회일·버전과 마스킹 근거를 보존',
                                                                            '비공개 사유·공개 범위·원문 마스킹·공개 결정은 정보공개 담당자 승인으로 '
                                                                            '이관')},
          'education-records-lifecycle-review': {'name': 'education-records-lifecycle-review',
                                                 'title': '교육기록 생애주기 검토',
                                                 'capability': 'public-records-lifecycle-review',
                                                 'role': 'additional',
                                                 'reference_skills': (),
                                                 'boundary': 'draft-only',
                                                 'task_checks': ('교육기록의 유형·업무기능·보존기산점·보존기간·이관 또는 폐기 후보를 분리',
                                                                 '국가기록원·교육부·법령 공식 URL·조회일·기준 버전과 근거 공백을 보존',
                                                                 '보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인으로 이관')}},
 '사회복지': {'welfare-policy-statistics-brief': {'name': 'welfare-policy-statistics-brief',
                                              'title': '복지정책 통계 근거 브리프',
                                              'capability': 'kosis-official-statistics',
                                              'role': 'additional',
                                              'reference_skills': (),
                                              'boundary': 'draft-only',
                                              'task_checks': ('복지 지표의 급여·서비스·지역·기간·대상 집단·분모·단위를 분리',
                                                              'KOSIS 통계표 코드·작성기관·수록기간·조회일·개정 상태와 결측을 보존',
                                                              '수급자격·지급액·정책효과·자원배분 판단은 복지 담당기관 검토로 이관')},
          'welfare-administrative-document-draft-review': {'name': 'welfare-administrative-document-draft-review',
                                                           'title': '복지행정 문서 초안 검토',
                                                           'capability': 'administrative-document-draft-review',
                                                           'role': 'additional',
                                                           'reference_skills': (),
                                                           'boundary': 'draft-only',
                                                           'task_checks': ('복지사업 안내·검토보고·회의자료별 목적·대상·근거·미확정 항목을 분리',
                                                                           '신청인 개인정보 원문을 제외하고 공식 법령·사업안내 URL·조회일·문서 '
                                                                           '버전을 보존',
                                                                           '수급자격·지급액·기관 서식 확정·결재·발송은 복지 담당자 승인으로 '
                                                                           '이관')}},
 '고용노동': {'labor-law-citation-evidence-review': {'name': 'labor-law-citation-evidence-review',
                                                 'title': '노동법 인용 근거 검토',
                                                 'capability': 'korean-legal-citation-verification',
                                                 'role': 'additional',
                                                 'reference_skills': (),
                                                 'boundary': 'draft-only',
                                                 'task_checks': ('법령·조문·시행일·사건 또는 행정해석 후보·기준시점을 분리',
                                                                 '국가법령정보 공식 URL·조문·시행일·인용문과 조회일을 보존',
                                                                 '근로자성·위법성·산재 인정·법률 해석·최종 인용은 노동·법무 담당자 승인으로 이관')},
          'workplace-safety-policy-evidence-pack': {'name': 'workplace-safety-policy-evidence-pack',
                                                    'title': '사업장 안전정책 근거 팩',
                                                    'capability': 'public-policy-evidence-pack',
                                                    'role': 'additional',
                                                    'reference_skills': (),
                                                    'boundary': 'draft-only',
                                                    'task_checks': ('업종·작업·위험요인·통제조치·교육·점검·증빙 공백을 분리',
                                                                    '고용노동부·안전보건공단·법령 공식 URL·조회일·문서 버전과 상충 근거를 구분',
                                                                    '사업장 위험도·작업중지·산재 인정·제재·계획 승인은 안전보건 담당자 검토로 이관')}},
 '보건의료': {'healthcare-civil-complaint-triage-draft': {'name': 'healthcare-civil-complaint-triage-draft',
                                                      'title': '보건의료 민원 분류·답변 초안',
                                                      'capability': 'civil-complaint-triage-draft',
                                                      'role': 'additional',
                                                      'reference_skills': (),
                                                      'boundary': 'draft-only',
                                                      'task_checks': ('시설·급여·예방·민원 유형과 요청사항·소관 후보를 비식별 상태로 분리',
                                                                      '환자 개인정보·증상 원문을 저장하지 않고 복지부·질병청·건보공단 공식 '
                                                                      'URL·조회일·버전을 보존',
                                                                      '진단·치료·급여·응급도·소관 확정·답변 발송은 의료전문가와 담당기관 승인으로 '
                                                                      '이관')},
          'healthcare-public-notice-multilingual-review': {'name': 'healthcare-public-notice-multilingual-review',
                                                           'title': '보건의료 공지 다국어 검토',
                                                           'capability': 'official-notice-multilingual-translation-review',
                                                           'role': 'additional',
                                                           'reference_skills': (),
                                                           'boundary': 'draft-only',
                                                           'task_checks': ('공지 대상·언어·시행일·의료 또는 행정 용어·행동요령을 문장 단위로 분리',
                                                                           '공식 원문 URL·공표일·조회일·문서 버전과 번역상 미확정 용어를 보존',
                                                                           '의학적 의미·공식 용어·언어별 감수·게시·발송은 보건의료 담당자와 전문 '
                                                                           '감수자 승인으로 이관')}},
 '식품의약': {'food-drug-labeling-guidance-evidence-review': {'name': 'food-drug-labeling-guidance-evidence-review',
                                                          'title': '식품·의약 표시기준 근거 검토',
                                                          'capability': 'public-policy-evidence-pack',
                                                          'role': 'additional',
                                                          'reference_skills': (),
                                                          'boundary': 'draft-only',
                                                          'task_checks': ('제품유형·원재료·알레르기·표시항목·적용기준·시행일을 주장 단위로 분리',
                                                                          '식약처·국가법령정보 공식 URL·조회일·고시 또는 안내서 버전과 상충·미수집 '
                                                                          '근거를 구분',
                                                                          '표시 적합성·위반·회수·행정처분·법적 적용 판단은 식품의약 담당자 검토로 '
                                                                          '이관')},
          'food-drug-public-notice-multilingual-review': {'name': 'food-drug-public-notice-multilingual-review',
                                                          'title': '식품·의약 공지 다국어 검토',
                                                          'capability': 'official-notice-multilingual-translation-review',
                                                          'role': 'additional',
                                                          'reference_skills': (),
                                                          'boundary': 'draft-only',
                                                          'task_checks': ('공지 대상·제품 또는 품목·언어·시행일·주의사항·행동요령을 문장 단위로 분리',
                                                                          '식약처 공식 원문 URL·공표일·조회일·문서 버전과 번역상 미확정 용어를 '
                                                                          '보존',
                                                                          '안전성·법적 의미·공식 용어·언어별 감수·게시·발송은 식품의약 담당자와 전문 '
                                                                          '감수자 승인으로 이관')}}}
NATIONAL_OPERATIONS_MINIMUM_FIVE_SKILLS = {'재정': {'fiscal-law-citation-evidence-review': {'name': 'fiscal-law-citation-evidence-review',
                                                'title': '재정법령 인용 근거 검토',
                                                'capability': 'korean-legal-citation-verification',
                                                'role': 'additional',
                                                'reference_skills': (),
                                                'boundary': 'draft-only',
                                                'task_checks': ('재정사업·세목·회계연도·행위별 적용 법령 후보와 기준시점을 분리',
                                                                '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 원문 개인정보를 포함하지 않음',
                                                                '법적 해석·예산 집행 적법성·지급 판단은 재정 담당자 검토로 이관')},
        'fiscal-budget-execution-evidence-pack': {'name': 'fiscal-budget-execution-evidence-pack',
                                                  'title': '재정 집행 근거 팩',
                                                  'capability': 'public-policy-evidence-pack',
                                                  'role': 'additional',
                                                  'reference_skills': (),
                                                  'boundary': 'draft-only',
                                                  'task_checks': ('사업·회계연도·세목·집행행위·금액·근거 주장을 분리',
                                                                  '공식 예산서·법령·지침 URL·조회일·문서 버전을 보존하고 원문 개인정보·비밀값을 제외',
                                                                  '예산 집행 적법성·지급·교부·정책 평가는 재정 담당자 승인으로 이관')}},
 '관세': {'customs-law-citation-evidence-review': {'name': 'customs-law-citation-evidence-review',
                                                 'title': '관세법령 인용 근거 검토',
                                                 'capability': 'korean-legal-citation-verification',
                                                 'role': 'additional',
                                                 'reference_skills': (),
                                                 'boundary': 'draft-only',
                                                 'task_checks': ('품목·신고유형·통관단계·행위별 적용 법령 후보와 기준시점을 분리',
                                                                 '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 신고인 개인정보 원문을 포함하지 '
                                                                 '않음',
                                                                 '품목분류·세액·통관 가능 여부·법적 해석은 관세 담당자 검토로 이관')},
        'customs-civil-complaint-triage-draft': {'name': 'customs-civil-complaint-triage-draft',
                                                 'title': '관세 민원 분류·답변 초안',
                                                 'capability': 'civil-complaint-triage-draft',
                                                 'role': 'additional',
                                                 'reference_skills': (),
                                                 'boundary': 'draft-only',
                                                 'task_checks': ('민원유형·수출입단계·품목·요청사항·처리기한을 비식별 상태로 분리',
                                                                 '신고인·수취인 개인정보와 신고서 원문을 저장하지 않고 관세청 공식 URL·조회일을 보존',
                                                                 '세액·통관·법률 해석·소관 확정·답변 발송은 관세 담당자 승인으로 이관')}},
 '감사': {'audit-legal-basis-citation-review': {'name': 'audit-legal-basis-citation-review',
                                              'title': '감사 법적근거 인용 검토',
                                              'capability': 'korean-legal-citation-verification',
                                              'role': 'additional',
                                              'reference_skills': (),
                                              'boundary': 'draft-only',
                                              'task_checks': ('감사유형·대상기관·지적사항·처분 후보별 적용 법령과 기준시점을 분리',
                                                              '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 제보자 개인정보 원문을 포함하지 않음',
                                                              '위법성·지적 확정·처분 요구·법적 해석은 감사 담당자 검토로 이관')},
        'audit-records-disclosure-redaction-review': {'name': 'audit-records-disclosure-redaction-review',
                                                      'title': '감사기록 정보공개·마스킹 검토',
                                                      'capability': 'public-record-disclosure-redaction-review',
                                                      'role': 'additional',
                                                      'reference_skills': (),
                                                      'boundary': 'draft-only',
                                                      'task_checks': ('청구범위·감사단계·문서유형·정보항목·부분공개 후보를 분리',
                                                                      '제보자·피감사자 개인정보 원문과 비공개 감사정보를 저장하지 않고 '
                                                                      '정보공개포털·국가기록원 공식 URL·조회일·문서 버전과 마스킹 근거를 보존',
                                                                      '비공개 사유·공개 범위·원문 마스킹·공개 결정은 감사 정보공개 담당자 승인으로 '
                                                                      '이관')}},
 '통계': {'statistics-civil-complaint-triage-draft': {'name': 'statistics-civil-complaint-triage-draft',
                                                    'title': '국가통계 민원 분류·답변 초안',
                                                    'capability': 'civil-complaint-triage-draft',
                                                    'role': 'additional',
                                                    'reference_skills': (),
                                                    'boundary': 'draft-only',
                                                    'task_checks': ('통계표·지표·기간·단위·요청사항·오류 주장·처리기한을 비식별 상태로 분리',
                                                                    '민원인 개인정보 원문을 저장하지 않고 KOSIS·작성기관 공식 '
                                                                    'URL·조회일·메타데이터를 보존',
                                                                    '통계 오류 확정·수정·공표·개별 답변 발송은 통계 담당기관 승인으로 이관')},
        'statistics-quality-evidence-pack': {'name': 'statistics-quality-evidence-pack',
                                             'title': '국가통계 품질 근거 팩',
                                             'capability': 'public-policy-evidence-pack',
                                             'role': 'additional',
                                             'reference_skills': (),
                                             'boundary': 'draft-only',
                                             'task_checks': ('통계표·작성주기·기준기간·모집단·방법론·품질 주장을 분리',
                                                             'KOSIS·작성기관 공식 자료 URL·조회일·문서 버전을 보존하고 조사대상자 개인정보 원문을 제외',
                                                             '통계 오류·품질 수준·수정·공표 판단은 통계 담당기관 승인으로 이관')}},
 '조달': {'procurement-law-citation-evidence-review': {'name': 'procurement-law-citation-evidence-review',
                                                     'title': '조달법령 인용 근거 검토',
                                                     'capability': 'korean-legal-citation-verification',
                                                     'role': 'additional',
                                                     'reference_skills': (),
                                                     'boundary': 'draft-only',
                                                     'task_checks': ('계약유형·계약방법·금액기준·절차단계별 적용 법령 후보와 기준시점을 분리',
                                                                     '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 업체 개인정보 원문을 '
                                                                     '포함하지 않음',
                                                                     '입찰자격·계약 적법성·제재·법적 해석은 조달 담당자 검토로 이관')},
        'procurement-records-disclosure-redaction-review': {'name': 'procurement-records-disclosure-redaction-review',
                                                            'title': '조달기록 정보공개·마스킹 검토',
                                                            'capability': 'public-record-disclosure-redaction-review',
                                                            'role': 'additional',
                                                            'reference_skills': (),
                                                            'boundary': 'draft-only',
                                                            'task_checks': ('청구범위·계약단계·문서유형·정보항목·부분공개 후보를 분리',
                                                                            '개인정보 원문·업체 영업비밀·평가 중 비공개 정보를 저장하지 않고 '
                                                                            '정보공개포털·국가기록원 공식 URL·조회일·문서 버전과 마스킹 근거를 '
                                                                            '보존',
                                                                            '비공개 사유·공개 범위·원문 마스킹·공개 결정은 조달 정보공개 담당자 '
                                                                            '승인으로 이관')}},
 '외교': {'diplomatic-policy-evidence-pack': {'name': 'diplomatic-policy-evidence-pack',
                                            'title': '외교정책 근거 팩',
                                            'capability': 'public-policy-evidence-pack',
                                            'role': 'additional',
                                            'reference_skills': (),
                                            'boundary': 'draft-only',
                                            'task_checks': ('대상국·외교사안·기준시점·정책 주장·근거·상충 여부를 분리',
                                                            '외교부·정부·조약 관련 공식 URL·조회일·문서 버전을 보존하고 영사사건 개인정보 원문·비공개 '
                                                            '외교정보를 제외',
                                                            '외교적 의미·정책 입장·대외 발표·문서 결재는 외교 담당자 승인으로 이관')},
        'diplomatic-treaty-law-citation-review': {'name': 'diplomatic-treaty-law-citation-review',
                                                  'title': '외교·조약 법령 인용 검토',
                                                  'capability': 'korean-legal-citation-verification',
                                                  'role': 'additional',
                                                  'reference_skills': (),
                                                  'boundary': 'draft-only',
                                                  'task_checks': ('조약·법령·비준절차·외교행위별 적용 근거와 기준시점을 분리',
                                                                  '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 영사사건 개인정보 원문을 '
                                                                  '포함하지 않음',
                                                                  '조약 해석·국내법적 효력·비준·외교적 판단은 외교·법무 담당자 검토로 이관')}},
 '통일': {'unification-law-citation-evidence-review': {'name': 'unification-law-citation-evidence-review',
                                                     'title': '통일정책 법령 인용 근거 검토',
                                                     'capability': 'korean-legal-citation-verification',
                                                     'role': 'additional',
                                                     'reference_skills': (),
                                                     'boundary': 'draft-only',
                                                     'task_checks': ('통일사업·지원유형·행위·대상별 적용 법령 후보와 기준시점을 분리',
                                                                     '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 북한이탈주민 개인정보 '
                                                                     '원문을 포함하지 않음',
                                                                     '지원자격·법적 의미·정책 적용 판단은 통일 담당기관 검토로 이관')},
        'unification-policy-statistics-brief': {'name': 'unification-policy-statistics-brief',
                                                'title': '통일정책 통계 근거 브리프',
                                                'capability': 'kosis-official-statistics',
                                                'role': 'additional',
                                                'reference_skills': (),
                                                'boundary': 'draft-only',
                                                'task_checks': ('지표·기간·지역·대상집단·분모·단위와 남북관계 기준시점을 분리',
                                                                'KOSIS·통일부 공식 통계표 코드·작성기관·조회일을 보존하고 개인 원문정보를 제외',
                                                                '북한·남북관계 현황 해석·정책 효과·지원 판단은 통일 담당기관 검토로 이관')}},
 '선거관리': {'election-law-citation-verification': {'name': 'election-law-citation-verification',
                                                 'title': '선거법령 인용 검증',
                                                 'capability': 'korean-legal-citation-verification',
                                                 'role': 'additional',
                                                 'reference_skills': (),
                                                 'boundary': 'draft-only',
                                                 'task_checks': ('선거유형·선거구·행위주체·행위·기준일별 적용 법령 후보를 분리',
                                                                 '국가법령정보센터의 조문·시행일·공식 URL·조회일을 보존하고 유권자·후보자 개인정보 원문을 '
                                                                 '포함하지 않음',
                                                                 '피선거권·위법성·제재·법적 해석은 선거관리위원회 담당자 검토로 이관')},
          'election-records-disclosure-redaction-review': {'name': 'election-records-disclosure-redaction-review',
                                                           'title': '선거기록 정보공개·마스킹 검토',
                                                           'capability': 'public-record-disclosure-redaction-review',
                                                           'role': 'additional',
                                                           'reference_skills': (),
                                                           'boundary': 'draft-only',
                                                           'task_checks': ('청구범위·선거유형·선거구·문서유형·정보항목·부분공개 후보를 분리',
                                                                           '정보공개포털·국가기록원 공식 URL·조회일·문서 버전을 보존하고 '
                                                                           '유권자·후보자 개인정보 원문과 비공개 선거정보를 제외',
                                                                           '비공개 사유·공개 범위·원문 마스킹·공개 결정은 선거관리 정보공개 담당자 '
                                                                           '승인으로 이관')}},
 '입법': {'legislative-records-disclosure-redaction-review': {'name': 'legislative-records-disclosure-redaction-review',
                                                            'title': '입법기록 정보공개·마스킹 검토',
                                                            'capability': 'public-record-disclosure-redaction-review',
                                                            'role': 'additional',
                                                            'reference_skills': (),
                                                            'boundary': 'draft-only',
                                                            'task_checks': ('청구범위·의안·위원회·회기·문서유형·정보항목·부분공개 후보를 분리',
                                                                            '개인정보 원문·비공개 협의정보·제3자 비밀을 저장하지 않고 '
                                                                            '정보공개포털·국가기록원 공식 URL·조회일·문서 버전과 마스킹 근거를 '
                                                                            '보존',
                                                                            '비공개 사유·공개 범위·원문 마스킹·공개 결정은 입법기관 정보공개 담당자 '
                                                                            '승인으로 이관')},
        'legislative-enacted-law-citation-review': {'name': 'legislative-enacted-law-citation-review',
                                                    'title': '제·개정 법령 인용 검토',
                                                    'capability': 'korean-legal-citation-verification',
                                                    'role': 'additional',
                                                    'reference_skills': (),
                                                    'boundary': 'draft-only',
                                                    'task_checks': ('법률안·공포법률·조문·시행일·개정연혁·기준시점을 분리',
                                                                    '국가법령정보센터의 조문·시행일·개정연혁·공식 URL·조회일을 보존하고 원문 개인정보를 '
                                                                    '포함하지 않음',
                                                                    '법적 효력·법률안 처리상태·입법 판단은 입법·법무 담당자 검토로 이관')}}}
LAW_SAFETY_WAVE_A_SKILL_CONTRACTS = {
    "사법": {
        "judicial-records-disclosure-redaction-review": {
            "name": "judicial-records-disclosure-redaction-review",
            "title": "사법 기록공개·비식별 검토",
            "capability": "public-record-disclosure-redaction-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "사건기록·판결문·등기 또는 행정기록의 공개대상·보유기관·식별자를 분리하고 원문 개인정보를 입력하지 않음",
                "정보공개포털(www.open.go.kr)·국가기록원(www.archives.go.kr) 공식 URL·문서번호·조회일·공개 또는 비공개 사유와 상충·미수집 근거를 보존",
                "공개 여부·비공개 범위·제공 결정·법적 효력은 사법 담당자와 정보공개 담당자 최종 검토로 이관",
            ),
        },
        "judicial-records-lifecycle-review": {
            "name": "judicial-records-lifecycle-review",
            "title": "사법 기록물 생애주기 검토",
            "capability": "public-records-lifecycle-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "사건기록·보존기간·이관·폐기 대상과 기록관리 기준일을 분리",
                "국가기록원(www.archives.go.kr)·기관 공식 기록관리 기준 URL·문서번호·조회일·개정 상태와 상충·미수집 근거를 구분하고 원문 개인정보를 포함하지 않음",
                "보존기간 책정·이관·폐기·열람 승인과 원문 기록 처리는 기록관리 담당자 승인으로 이관",
            ),
        },
    },
    "출입국": {
        "immigration-law-citation-evidence-review": {
            "name": "immigration-law-citation-evidence-review",
            "title": "출입국 법령 인용 근거 검토",
            "capability": "korean-legal-citation-verification",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "체류·출입국·비자 법령·조문·행정규칙·판례 식별자와 적용 시점·인용 위치를 분리",
                "국가법령정보(law.go.kr) 공식 원문 URL·공포일·시행일·조회일·개정 상태와 상충·미수집 근거를 보존하고 원문 개인정보를 포함하지 않음",
                "법률적 효력·체류자격·입국 허가·처분 여부는 출입국 담당기관과 법무 담당자 최종 검토로 이관",
            ),
        },
        "immigration-records-disclosure-redaction-review": {
            "name": "immigration-records-disclosure-redaction-review",
            "title": "출입국 기록공개·비식별 검토",
            "capability": "public-record-disclosure-redaction-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "출입국·체류 기록의 공개대상·보유기관·식별자를 분리하고 원문 개인정보를 입력하지 않음",
                "정보공개포털(www.open.go.kr)·국가기록원(www.archives.go.kr) 공식 URL·문서번호·조회일·공개 또는 비공개 사유와 상충·미수집 근거를 보존",
                "공개 여부·비공개 범위·제공 결정·체류 또는 처분 정보 해석은 출입국 담당기관 검토로 이관",
            ),
        },
    },
    "경찰": {
        "police-law-citation-evidence-review": {
            "name": "police-law-citation-evidence-review",
            "title": "경찰 법령 인용 근거 검토",
            "capability": "korean-legal-citation-verification",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "치안·수사·신고·경찰 법령·조문·행정규칙·판례 식별자와 적용 시점·인용 위치를 분리",
                "국가법령정보(law.go.kr) 공식 원문 URL·공포일·시행일·조회일·개정 상태와 상충·미수집 근거를 보존하고 원문 개인정보를 포함하지 않음",
                "법률적 효력·수사·처분·출동·신고 접수 여부는 경찰 담당기관과 법무 담당자 최종 검토로 이관",
            ),
        },
        "police-records-disclosure-redaction-review": {
            "name": "police-records-disclosure-redaction-review",
            "title": "경찰 기록공개·비식별 검토",
            "capability": "public-record-disclosure-redaction-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "112 신고·수사·보호 기록의 공개대상·보유기관·식별자를 분리하고 원문 개인정보를 입력하지 않음",
                "정보공개포털(www.open.go.kr)·국가기록원(www.archives.go.kr) 공식 URL·문서번호·조회일·공개 또는 비공개 사유와 상충·미수집 근거를 보존",
                "공개 여부·비공개 범위·제공 결정·수사 또는 신고 정보 해석은 경찰 담당기관 검토로 이관",
            ),
        },
    },
    "소방": {
        "fire-law-citation-evidence-review": {
            "name": "fire-law-citation-evidence-review",
            "title": "소방 법령 인용 근거 검토",
            "capability": "korean-legal-citation-verification",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "소방·화재·구조·구급 법령·조문·행정규칙·판례 식별자와 적용 시점·인용 위치를 분리",
                "국가법령정보(law.go.kr) 공식 원문 URL·공포일·시행일·조회일·개정 상태와 상충·미수집 근거를 보존하고 원문 개인정보를 포함하지 않음",
                "법률적 효력·적합성·현장 점검·출동·안전조치 여부는 소방 담당기관과 전문가 최종 검토로 이관",
            ),
        },
        "fire-records-disclosure-redaction-review": {
            "name": "fire-records-disclosure-redaction-review",
            "title": "소방 기록공개·비식별 검토",
            "capability": "public-record-disclosure-redaction-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "화재·구조·구급 출동 기록의 공개대상·보유기관·식별자를 분리하고 원문 개인정보를 입력하지 않음",
                "정보공개포털(www.open.go.kr)·국가기록원(www.archives.go.kr) 공식 URL·문서번호·조회일·공개 또는 비공개 사유와 상충·미수집 근거를 보존",
                "공개 여부·비공개 범위·제공 결정·현장 대응 또는 안전 정보 해석은 소방 담당기관 검토로 이관",
            ),
        },
    },
    "재난안전": {
        "disaster-law-citation-evidence-review": {
            "name": "disaster-law-citation-evidence-review",
            "title": "재난안전 법령 인용 근거 검토",
            "capability": "korean-legal-citation-verification",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "재난·안전·대피·재해 법령·조문·행정규칙·판례 식별자와 적용 시점·인용 위치를 분리",
                "국가법령정보(law.go.kr) 공식 원문 URL·공포일·시행일·조회일·개정 상태와 상충·미수집 근거를 보존하고 원문 개인정보를 포함하지 않음",
                "법률적 효력·경보발령·대피·출동·재난 대응 여부는 재난안전 담당기관과 법무 담당자 최종 검토로 이관",
            ),
        },
        "disaster-records-disclosure-redaction-review": {
            "name": "disaster-records-disclosure-redaction-review",
            "title": "재난안전 기록공개·비식별 검토",
            "capability": "public-record-disclosure-redaction-review",
            "role": "additional",
            "reference_skills": (),
            "boundary": "draft-only",
            "task_checks": (
                "재난상황·대응·피해 기록의 공개대상·보유기관·식별자를 분리하고 원문 개인정보를 입력하지 않음",
                "정보공개포털(www.open.go.kr)·국가기록원(www.archives.go.kr) 공식 URL·문서번호·조회일·공개 또는 비공개 사유와 상충·미수집 근거를 보존",
                "공개 여부·비공개 범위·제공 결정·피해 규모 또는 대응 우선순위 해석은 재난안전 담당기관 검토로 이관",
            ),
        },
    },
}
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
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


def _validate_instructions(root: Path, errors: list[str]) -> None:
    contracts = {
        "CLAUDE.md": {
            "max_lines": 80,
            "anchors": (
                "domains/<domain>/skills/<unique-slug>/SKILL.md",
                "top-level `skills/`",
                "catalog/domain-skills.json",
                "target_skills_per_domain",
                "enforced_minimum_skills_by_domain",
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
                "target_skills_per_domain",
                "python3 scripts/check.py",
            ),
        },
    }
    for name, contract in contracts.items():
        path = root / name
        if not path.is_file():
            errors.append(f"missing root instruction contract: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        if len(text.splitlines()) > contract["max_lines"]:
            errors.append(f"{name}: exceeds {contract['max_lines']} line budget")
        for anchor in contract["anchors"]:
            if anchor not in text:
                errors.append(f"{name}: missing required anchor {anchor!r}")
    for typo in ("Agent.md", "Cluade.md"):
        if (root / typo).exists():
            errors.append(f"non-standard instruction filename is forbidden: {typo}")


def _validate_capabilities(
    raw_capabilities: Any,
    root: Path,
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    if not isinstance(raw_capabilities, list):
        errors.append("shared_capabilities must be a list")
        return set(), {}
    if len(raw_capabilities) != 22:
        errors.append(f"catalog must contain 22 shared capabilities, got {len(raw_capabilities)}")
    slugs: set[str] = set()
    by_slug: dict[str, dict[str, Any]] = {}
    for index, capability in enumerate(raw_capabilities):
        if not isinstance(capability, dict):
            errors.append(f"shared_capabilities[{index}] must be an object")
            continue
        missing = CAPABILITY_REQUIRED_KEYS - set(capability)
        if missing:
            errors.append(f"shared_capabilities[{index}] missing keys: {sorted(missing)}")
            continue
        slug = capability["slug"]
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            errors.append(f"invalid shared capability slug: {slug}")
            continue
        if slug in slugs:
            errors.append(f"duplicate shared capability: {slug}")
        slugs.add(slug)
        by_slug[slug] = capability
        if capability["locale"] != "ko-KR" or capability["jurisdiction"] != "KR":
            errors.append(f"{slug}: locale/jurisdiction must be ko-KR/KR")
        if capability["credential_class"] not in CREDENTIAL_CLASSES:
            errors.append(f"{slug}: invalid credential_class")
        if capability["proxy_mode"] not in PROXY_MODES:
            errors.append(f"{slug}: invalid proxy_mode")
        if capability["side_effect_class"] not in SIDE_EFFECT_CLASSES:
            errors.append(f"{slug}: invalid side_effect_class")
        if capability["execution_status"] not in EXECUTION_STATUSES:
            errors.append(f"{slug}: invalid execution_status")
        if capability["live_smoke"] not in LIVE_SMOKE_STATUSES:
            errors.append(f"{slug}: invalid live_smoke")
        if capability["execution_status"] == "live-verified" and capability["live_smoke"] != "passed":
            errors.append(f"{slug}: live-verified requires live_smoke=passed")
        if capability["live_smoke"] == "passed" and capability["execution_status"] != "live-verified":
            errors.append(f"{slug}: live_smoke=passed requires live-verified")
        for contract, label in (
            (WAVE_TWO_CAPABILITY_CONTRACTS.get(slug), "wave-two"),
            (WAVE_SEVEN_CAPABILITY_CONTRACTS.get(slug), "wave-seven"),
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
                errors.append(f"{slug}: {label} capability contract mismatch")
        provenance = capability["source_provenance"]
        if not isinstance(provenance, list) or not provenance or not all(
            isinstance(url, str) and url.startswith("https://") for url in provenance
        ):
            errors.append(f"{slug}: source_provenance must contain HTTPS URLs")

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
                errors.append(f"{slug}: missing internal capability artifact {path.relative_to(root)}")
        if capability["execution_status"] == "live-verified":
            path = root / "docs" / "capabilities" / slug / "live-smoke.md"
            if not path.is_file():
                errors.append(f"{slug}: missing live smoke evidence {path.relative_to(root)}")
    return slugs, by_slug


def validate(data: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["catalog root must be a JSON object"]
    if data.get("schema_version") != 5:
        errors.append("schema_version must be 5")
    target_skills = data.get("target_skills_per_domain")
    if type(target_skills) is not int or target_skills != TARGET_SKILLS_PER_DOMAIN:
        errors.append("target_skills_per_domain must be integer 5")
    enforced_minimums = data.get("enforced_minimum_skills_by_domain")
    if not isinstance(enforced_minimums, dict):
        errors.append("enforced_minimum_skills_by_domain must be an object")
        enforced_minimums = {}
    domains = data.get("domains")
    if not isinstance(domains, list):
        return errors + ["domains must be a list"]
    if len(domains) != 60:
        errors.append(f"catalog must contain 60 domains, got {len(domains)}")

    capability_slugs, capability_by_slug = _validate_capabilities(data.get("shared_capabilities"), root, errors)
    seen_domains: set[str] = set()
    seen_names: set[str] = set()
    declared_entrypoints: set[Path] = set()

    for index, item in enumerate(domains):
        if not isinstance(item, dict):
            errors.append(f"domains[{index}] must be an object")
            continue
        missing = DOMAIN_REQUIRED_KEYS - set(item)
        if missing:
            errors.append(f"domains[{index}] missing keys: {sorted(missing)}")
            continue
        domain = item["domain"]
        evidence = item["evidence"]
        skills = item["skills"]
        if not isinstance(domain, str) or not domain:
            errors.append(f"domains[{index}]: invalid domain")
            continue
        if domain in seen_domains:
            errors.append(f"duplicate domain: {domain}")
        seen_domains.add(domain)
        if item["group"] not in GROUP_ORDER:
            errors.append(f"{domain}: invalid group {item['group']}")
        if evidence not in EVIDENCE:
            errors.append(f"{domain}: invalid evidence {evidence}")
        if not isinstance(skills, list) or not skills:
            errors.append(f"{domain}: skills must be a non-empty list")
            continue
        enforced_minimum = enforced_minimums.get(domain)
        if (
            type(enforced_minimum) is not int
            or not 1 <= enforced_minimum <= TARGET_SKILLS_PER_DOMAIN
        ):
            errors.append(f"{domain}: invalid enforced minimum {enforced_minimum!r}")
        elif len(skills) < enforced_minimum:
            errors.append(
                f"{domain}: requires at least {enforced_minimum} Skills "
                f"(target {TARGET_SKILLS_PER_DOMAIN}), got {len(skills)}"
            )
        wave_two_contract = WAVE_TWO_SKILL_CONTRACTS.get(domain)
        if wave_two_contract is not None:
            expected_name = wave_two_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                errors.append(f"{domain}/{expected_name}: wave-two contract mismatch")
            else:
                actual = matches[0]
                if not _skill_contract_matches(actual, wave_two_contract):
                    errors.append(f"{domain}/{expected_name}: wave-two contract mismatch")
        for wave_three_contract in WAVE_THREE_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_three_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                errors.append(f"{domain}/{expected_name}: wave-three contract mismatch")
            elif not _skill_contract_matches(matches[0], wave_three_contract):
                errors.append(f"{domain}/{expected_name}: wave-three contract mismatch")
        for wave_four_contract in WAVE_FOUR_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_four_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                errors.append(f"{domain}/{expected_name}: wave-four contract mismatch")
            elif not _skill_contract_matches(matches[0], wave_four_contract):
                errors.append(f"{domain}/{expected_name}: wave-four contract mismatch")
        for wave_five_contract in WAVE_FIVE_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_five_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                errors.append(f"{domain}/{expected_name}: wave-five contract mismatch")
            elif not _skill_contract_matches(matches[0], wave_five_contract):
                errors.append(f"{domain}/{expected_name}: wave-five contract mismatch")
        for wave_six_contract in WAVE_SIX_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_six_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                errors.append(f"{domain}/{expected_name}: wave-six contract mismatch")
            elif not _skill_contract_matches(matches[0], wave_six_contract):
                errors.append(f"{domain}/{expected_name}: wave-six contract mismatch")
        for wave_seven_contract in WAVE_SEVEN_SKILL_CONTRACTS.get(domain, ()):
            expected_name = wave_seven_contract["name"]
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1:
                errors.append(f"{domain}/{expected_name}: wave-seven contract mismatch")
            elif not _skill_contract_matches(matches[0], wave_seven_contract):
                errors.append(f"{domain}/{expected_name}: wave-seven contract mismatch")
        expected_social_skills = SOCIAL_SERVICE_MINIMUM_FIVE_SKILLS.get(domain, {})
        for expected_name, expected_contract in expected_social_skills.items():
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1 or not _skill_contract_matches(matches[0], expected_contract):
                errors.append(f"{domain}/{expected_name}: social-services minimum-five contract mismatch")
        expected_national_skills = NATIONAL_OPERATIONS_MINIMUM_FIVE_SKILLS.get(domain, {})
        for expected_name, expected_contract in expected_national_skills.items():
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1 or not _skill_contract_matches(matches[0], expected_contract):
                errors.append(f"{domain}/{expected_name}: national-operations minimum-five contract mismatch")
        expected_law_safety_skills = LAW_SAFETY_WAVE_A_SKILL_CONTRACTS.get(domain, {})
        for expected_name, expected_contract in expected_law_safety_skills.items():
            matches = [
                skill
                for skill in skills
                if isinstance(skill, dict) and skill.get("name") == expected_name
            ]
            if len(matches) != 1 or not _skill_contract_matches(matches[0], expected_contract):
                errors.append(f"{domain}/{expected_name}: law-safety-wave-a contract mismatch")
        primary_count = sum(isinstance(skill, dict) and skill.get("role") == "primary" for skill in skills)
        if primary_count != 1:
            errors.append(f"{domain}: requires exactly one primary Skill, got {primary_count}")
        for skill_index, skill in enumerate(skills):
            if not isinstance(skill, dict):
                errors.append(f"{domain}.skills[{skill_index}] must be an object")
                continue
            missing_skill = SKILL_REQUIRED_KEYS - set(skill)
            if missing_skill:
                errors.append(f"{domain}.skills[{skill_index}] missing keys: {sorted(missing_skill)}")
                continue
            name = skill["name"]
            capability = skill["capability"]
            role = skill["role"]
            boundary = skill["boundary"]
            references = skill["reference_skills"]
            task_checks = skill.get("task_checks")
            if not isinstance(name, str) or not SLUG.fullmatch(name):
                errors.append(f"{domain}: invalid Skill name {name}")
                continue
            if name in seen_names:
                errors.append(f"duplicate domain Skill name: {name}")
            seen_names.add(name)
            if role not in ROLES:
                errors.append(f"{domain}/{name}: invalid role {role}")
            if not isinstance(capability, str) or not SLUG.fullmatch(capability):
                errors.append(f"{domain}/{name}: invalid capability {capability}")
            elif capability not in capability_slugs:
                errors.append(f"{domain}/{name}: unknown capability {capability}")
            if boundary not in BOUNDARIES:
                errors.append(f"{domain}/{name}: invalid boundary {boundary}")
            capability_manifest = capability_by_slug.get(capability)
            if (
                boundary == "read-only"
                and capability_manifest is not None
                and capability_manifest.get("side_effect_class") == "draft-only"
            ):
                errors.append(
                    f"{domain}/{name}: read-only boundary is incompatible with draft-only capability"
                )
            if not isinstance(references, list) or not all(
                isinstance(value, str) and SLUG.fullmatch(value) for value in references
            ):
                errors.append(f"{domain}/{name}: invalid reference_skills")
                references = []
            if task_checks is not None and (
                not isinstance(task_checks, list)
                or not 1 <= len(task_checks) <= 8
                or not all(
                    isinstance(check, str) and check.strip() and len(check) <= 200
                    for check in task_checks
                )
            ):
                errors.append(f"{domain}/{name}: invalid task_checks")
            expected_task_checks = WAVE_ONE_TASK_CHECKS.get(name)
            if expected_task_checks is not None and tuple(task_checks or ()) != expected_task_checks:
                errors.append(f"{domain}/{name}: wave-one task_checks contract mismatch")
            if role == "primary":
                if evidence in {"direct", "adjacent"} and not references:
                    errors.append(f"{domain}: {evidence} evidence requires primary reference_skills")
                if evidence in {"new", "sensitive"} and references:
                    errors.append(f"{domain}: {evidence} evidence must not claim primary reference_skills")
                if evidence == "sensitive" and boundary != "manual-review-only":
                    errors.append(f"{domain}: sensitive evidence requires manual-review-only")
            declared_entrypoints.add(Path("domains") / domain / "skills" / name / "SKILL.md")

    minimum_domains = set(enforced_minimums)
    if minimum_domains != seen_domains:
        errors.append(
            "minimum Skill map/domain mismatch "
            f"missing={sorted(seen_domains - minimum_domains)} extra={sorted(minimum_domains - seen_domains)}"
        )
    domains_root = root / "domains"
    actual_domains = {path.name for path in domains_root.iterdir() if path.is_dir()} if domains_root.is_dir() else set()
    if actual_domains != seen_domains:
        errors.append(
            f"domain folder/catalog mismatch missing={sorted(seen_domains - actual_domains)} extra={sorted(actual_domains - seen_domains)}"
        )
    if (root / "skills").exists():
        errors.append("top-level skills/ is forbidden; public Skills must be owned by domains")

    actual_entrypoints = {path.relative_to(root) for path in domains_root.glob("*/skills/*/SKILL.md")}
    if actual_entrypoints != declared_entrypoints:
        errors.append(
            f"domain Skill/catalog mismatch missing={sorted(map(str, declared_entrypoints - actual_entrypoints))} "
            f"extra={sorted(map(str, actual_entrypoints - declared_entrypoints))}"
        )
    for gitkeep in domains_root.glob("*/.gitkeep"):
        errors.append(f"stale empty-domain marker is forbidden: {gitkeep.relative_to(root)}")

    used = collect_used_capabilities(domains)
    if used != capability_slugs:
        errors.append(
            f"declared/used capability mismatch unused={sorted(capability_slugs - used)} undeclared={sorted(used - capability_slugs)}"
        )
    try:
        expected_skills = expected_domain_skills(data, root)
    except (KeyError, TypeError) as exc:
        errors.append(f"cannot render domain Skills from catalog: {exc}")
        expected_skills = {}
    for path, expected in expected_skills.items():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if text != expected:
            errors.append(f"stale generated domain Skill: {path.relative_to(root)}")
        name_match = re.search(r"^name:\s*([^\s]+)\s*$", text, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)\s*$", text, re.MULTILINE)
        if not name_match or name_match.group(1) != path.parent.name:
            errors.append(f"{path.relative_to(root)}: frontmatter name must match directory")
        if not description_match:
            errors.append(f"{path.relative_to(root)}: missing frontmatter description")

    generated = root / "docs" / "domain-skill-candidates.md"
    try:
        expected_catalog = render_catalog(data)
    except (KeyError, TypeError) as exc:
        errors.append(f"cannot render generated catalog: {exc}")
    else:
        if not generated.is_file():
            errors.append("missing generated docs/domain-skill-candidates.md")
        elif generated.read_text(encoding="utf-8") != expected_catalog:
            errors.append("docs/domain-skill-candidates.md is stale; run scripts/render_catalog.py")

    _validate_instructions(root, errors)
    return errors


def main() -> int:
    catalog_path = ROOT / "catalog/domain-skills.json"
    if not catalog_path.is_file():
        print("ERROR missing catalog/domain-skills.json")
        return 1
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    counts = Counter(item["evidence"] for item in data["domains"])
    capabilities = collect_used_capabilities(data["domains"])
    domain_skills = sum(len(item["skills"]) for item in data["domains"])
    print(
        "PASS "
        f"domains={len(data['domains'])} domain_skills={domain_skills} capabilities={len(capabilities)} top_level_skills=0 "
        + " ".join(f"{name}={counts[name]}" for name in ("direct", "adjacent", "new", "sensitive"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
