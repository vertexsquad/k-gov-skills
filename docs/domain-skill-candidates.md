# Domain별 Skill

> 이 문서는 `catalog/domain-skills.json`에서 생성합니다. 직접 편집하지 마세요.
> 공개 Skill은 `domains/<domain>/skills/<unique-slug>/SKILL.md`만 소유합니다.
> 공통 구현은 `kgov_runtime/capabilities/`에 있고 top-level `skills/`는 금지합니다.

## 요약

- 전체 domain: **60개**
- domain-owned Skill: **308개** (primary 60 / additional 248)
- 직접 reference 확인: **35개**
- 인접 capability 활용: **16개**
- 신규 설계 필요: **8개**
- 민감업무 제한: **1개**
- 내부 공통 capability: **22개**
- Domain Skill의 live 검증 상태는 연결된 capability manifest보다 강하게 주장하지 않습니다.

## Evidence 등급

| 값 | 의미 |
|---|---|
| `direct` | 직접 reference 확인 |
| `adjacent` | 인접 capability 활용 |
| `new` | 신규 설계 필요 |
| `sensitive` | 민감업무 제한 |

## 내부 capability runtime manifest

| Capability | Credential | Proxy | Side effect | Execution | Live smoke |
|---|---|---|---|---|---|
| `public-document-hwpx` | `none` | `none` | `document-read` | `fixture-verified` | `not-run` |
| `korean-law-bill-research` | `mixed` | `optional` | `read-only` | `fixture-verified` | `not-run` |
| `kosis-official-statistics` | `user-held` | `optional` | `read-only` | `fixture-verified` | `not-run` |
| `public-procurement-research` | `mixed` | `optional` | `read-only` | `fixture-verified` | `not-run` |
| `disaster-geospatial-brief` | `mixed` | `optional` | `read-only` | `fixture-verified` | `not-run` |
| `welfare-health-safety-research` | `mixed` | `optional` | `read-only` | `fixture-verified` | `not-run` |
| `land-housing-geospatial-research` | `mixed` | `optional` | `read-only` | `fixture-verified` | `not-run` |
| `official-source-research` | `none` | `none` | `read-only` | `live-verified` | `passed` |
| `civil-complaint-triage-draft` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `administrative-document-draft-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `public-policy-evidence-pack` | `mixed` | `optional` | `draft-only` | `fixture-verified` | `not-run` |
| `korean-legal-citation-verification` | `mixed` | `optional` | `draft-only` | `live-verified` | `passed` |
| `public-ai-governance-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `public-it-project-procedure-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `public-record-disclosure-redaction-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `local-ordinance-draft-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `construction-standard-bim-compliance-precheck` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `building-permit-document-precheck` | `none` | `none` | `draft-only` | `fixture-verified` | `blocked` |
| `official-notice-multilingual-translation-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `patent-prior-art-evidence-pack` | `none` | `none` | `read-only` | `fixture-verified` | `not-run` |
| `public-records-lifecycle-review` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |
| `regulated-trade-procedure-precheck` | `none` | `none` | `draft-only` | `fixture-verified` | `not-run` |

## 국가운영

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 행정 | `direct` | `primary` | 공공문서·HWPX 검토 | `government-document-hwpx-review` | `public-document-hwpx` | `hwp`, `rhwp-edit` | `draft-only` |
| 행정 | `direct` | `additional` | 민원 분류·답변 초안 | `public-administration-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 행정 | `direct` | `additional` | 행정문서 초안·검토 | `public-administration-administrative-document-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 행정 | `direct` | `additional` | 정책 근거 묶음 | `public-administration-public-policy-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 행정 | `direct` | `additional` | 법령 조문·판례 인용 검증 | `public-administration-legal-citation-verification` | `korean-legal-citation-verification` | `korean-law-search`, `legalize-kr`, `legal-kr` | `draft-only` |
| 행정 | `direct` | `additional` | 공공 AI 영향평가 초안 검토 | `public-ai-impact-assessment-draft-review` | `public-ai-governance-review` | — | `draft-only` |
| 행정 | `direct` | `additional` | 공공 AI 위험관리계획 검토 | `public-ai-risk-management-plan-review` | `public-ai-governance-review` | — | `draft-only` |
| 행정 | `direct` | `additional` | 공공안내 다국어 번역 검토 | `official-notice-multilingual-translation-review` | `official-notice-multilingual-translation-review` | — | `draft-only` |
| 재정 | `adjacent` | `primary` | 예산·결산 비교 | `budget-settlement-comparison` | `kosis-official-statistics` | `kosis-stats`, `k-dart` | `read-only` |
| 재정 | `adjacent` | `additional` | 지방재정 근거 묶음 | `local-finance-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 재정 | `adjacent` | `additional` | 국고보조사업 근거 검토 | `national-subsidy-project-evidence-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 재정 | `adjacent` | `additional` | 재정법령 인용 근거 검토 | `fiscal-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 재정 | `adjacent` | `additional` | 재정 집행 근거 팩 | `fiscal-budget-execution-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 세무 | `direct` | `primary` | 사업자·체납 상태조회 | `business-tax-status-lookup` | `official-source-research` | `nts-business-registration`, `nts-tax-delinquency` | `read-only` |
| 세무 | `direct` | `additional` | 세법령·개정 의안 조사 | `tax-law-bill-research` | `korean-law-bill-research` | — | `read-only` |
| 세무 | `direct` | `additional` | 국세통계 조회 | `national-tax-statistics-lookup` | `kosis-official-statistics` | — | `read-only` |
| 세무 | `direct` | `additional` | 재산세 토지·주택 기초조사 | `property-tax-land-housing-research` | `land-housing-geospatial-research` | — | `read-only` |
| 세무 | `direct` | `additional` | 국세청·홈택스 공식안내·유권해석 검색 | `hometax-official-guidance-search` | `official-source-research` | — | `read-only` |
| 세무 | `direct` | `additional` | 지방세 조례·세율 검색 | `local-tax-ordinance-search` | `korean-law-bill-research` | — | `read-only` |
| 세무 | `direct` | `additional` | 세무 민원 분류·답변 초안 | `tax-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 세무 | `direct` | `additional` | 세무 행정문서 초안·검토 | `tax-administrative-document-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 세무 | `direct` | `additional` | 세정 정책 근거 묶음 | `tax-policy-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 세무 | `direct` | `additional` | 세무 공문서 HWPX 검토 | `tax-document-hwpx-review` | `public-document-hwpx` | — | `draft-only` |
| 관세 | `new` | `primary` | HS 품목·관세율 조사 | `tariff-hs-code-research` | `official-source-research` | — | `read-only` |
| 관세 | `new` | `additional` | 원산지 증빙서류 사전점검 | `customs-origin-document-precheck` | `regulated-trade-procedure-precheck` | — | `draft-only` |
| 관세 | `new` | `additional` | 관세 무역통계 브리프 | `customs-trade-statistics-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 관세 | `new` | `additional` | 관세법령 인용 근거 검토 | `customs-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 관세 | `new` | `additional` | 관세 민원 분류·답변 초안 | `customs-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 감사 | `adjacent` | `primary` | 감사 증빙 교차검증 | `audit-evidence-cross-check` | `official-source-research` | `biz-health-check`, `g2b-sanctioned-supplier` | `draft-only` |
| 감사 | `adjacent` | `additional` | 감사 지적사항 답변 초안 검토 | `audit-finding-response-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 감사 | `adjacent` | `additional` | 감사 조치계획 근거 검토 | `audit-action-plan-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 감사 | `adjacent` | `additional` | 감사 법적근거 인용 검토 | `audit-legal-basis-citation-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 감사 | `adjacent` | `additional` | 감사기록 정보공개·마스킹 검토 | `audit-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 통계 | `direct` | `primary` | KOSIS 공식통계 조회 | `kosis-statistics-lookup` | `kosis-official-statistics` | `kosis-stats` | `read-only` |
| 통계 | `direct` | `additional` | 공식통계 방법론 근거 검토 | `official-statistics-methodology-evidence-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 통계 | `direct` | `additional` | 통계 공표 근거 브리프 | `statistical-release-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 통계 | `direct` | `additional` | 국가통계 민원 분류·답변 초안 | `statistics-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 통계 | `direct` | `additional` | 국가통계 품질 근거 팩 | `statistics-quality-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 조달 | `direct` | `primary` | 나라장터 발주·제재 조회 | `public-procurement-plan-check` | `public-procurement-research` | `g2b-order-plan-search`, `g2b-sanctioned-supplier` | `read-only` |
| 조달 | `direct` | `additional` | AI 제품 조달 준비도 점검 | `ai-product-procurement-readiness-check` | `public-procurement-research` | — | `draft-only` |
| 조달 | `direct` | `additional` | 조달 규격서 HWPX 검토 | `procurement-specification-hwpx-review` | `public-document-hwpx` | — | `draft-only` |
| 조달 | `direct` | `additional` | 조달법령 인용 근거 검토 | `procurement-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 조달 | `direct` | `additional` | 조달기록 정보공개·마스킹 검토 | `procurement-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 외교 | `new` | `primary` | 공식 국가·외교 브리프 | `official-country-brief` | `official-source-research` | — | `draft-only` |
| 외교 | `new` | `additional` | 조약·외교문서 출처 점검 | `treaty-diplomatic-document-source-check` | `public-policy-evidence-pack` | — | `draft-only` |
| 외교 | `new` | `additional` | 해외안전 국가 브리프 | `overseas-safety-country-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 외교 | `new` | `additional` | 외교정책 근거 팩 | `diplomatic-policy-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 외교 | `new` | `additional` | 외교·조약 법령 인용 검토 | `diplomatic-treaty-law-citation-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 통일 | `new` | `primary` | 북한·통일정책 공식자료 검색 | `unification-policy-source-search` | `official-source-research` | — | `read-only` |
| 통일 | `new` | `additional` | 남북관계 정책연표 근거 팩 | `inter-korean-policy-timeline-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 통일 | `new` | `additional` | DMZ 정책 출처 브리프 | `dmz-policy-source-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 통일 | `new` | `additional` | 통일정책 법령 인용 근거 검토 | `unification-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 통일 | `new` | `additional` | 통일정책 통계 근거 브리프 | `unification-policy-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 선거관리 | `direct` | `primary` | 지방선거 후보자 조회 | `local-election-candidate-lookup` | `official-source-research` | `local-election-candidate-search` | `read-only` |
| 선거관리 | `direct` | `additional` | 선거법·절차 근거 검토 | `election-law-procedure-evidence-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 선거관리 | `direct` | `additional` | 선거결과 통계 근거 브리프 | `election-result-statistics-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 선거관리 | `direct` | `additional` | 선거법령 인용 검증 | `election-law-citation-verification` | `korean-legal-citation-verification` | — | `draft-only` |
| 선거관리 | `direct` | `additional` | 선거기록 정보공개·마스킹 검토 | `election-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 입법 | `direct` | `primary` | 국회 의안·표결 조회 | `assembly-bill-vote-lookup` | `korean-law-bill-research` | `assembly-bill-vote-search` | `read-only` |
| 입법 | `direct` | `additional` | 법안 비교·영향 근거 브리프 | `bill-comparison-impact-brief` | `korean-law-bill-research` | — | `draft-only` |
| 입법 | `direct` | `additional` | 상임위원회 회의록 근거 팩 | `committee-minutes-evidence-pack` | `korean-law-bill-research` | — | `draft-only` |
| 입법 | `direct` | `additional` | 입법기록 정보공개·마스킹 검토 | `legislative-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 입법 | `direct` | `additional` | 제·개정 법령 인용 검토 | `legislative-enacted-law-citation-review` | `korean-legal-citation-verification` | — | `draft-only` |

## 법무·치안

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 사법 | `direct` | `primary` | 법령·법원공고·등기 조사 | `law-court-registry-research` | `korean-law-bill-research` | `korean-law-search`, `court-auction-notice-search`, `iros-registry-automation`, `court-payment-order-assistant` | `read-only` |
| 사법 | `direct` | `additional` | 판결 인용 근거 팩 | `judgment-citation-evidence-pack` | `korean-legal-citation-verification` | — | `draft-only` |
| 사법 | `direct` | `additional` | 법원 통계 근거 브리프 | `court-statistics-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 사법 | `direct` | `additional` | 사법 기록공개·비식별 검토 | `judicial-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 사법 | `direct` | `additional` | 사법 기록물 생애주기 검토 | `judicial-records-lifecycle-review` | `public-records-lifecycle-review` | — | `draft-only` |
| 검찰 | `adjacent` | `primary` | 검찰업무 법적 근거 조사 | `prosecution-legal-basis-research` | `korean-law-bill-research` | `korean-law-search` | `read-only` |
| 검찰 | `adjacent` | `additional` | 검찰 공식자료 검색 | `prosecution-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 검찰 | `adjacent` | `additional` | 검찰 통계 근거 브리프 | `prosecution-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 검찰 | `adjacent` | `additional` | 검찰 행정문서 검토 | `prosecution-administrative-document-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 검찰 | `adjacent` | `additional` | 검찰 정책·민원 브리프 | `prosecution-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 교정 | `new` | `primary` | 교정 관련 규정 검색 | `corrections-regulation-search` | `korean-law-bill-research` | — | `read-only` |
| 교정 | `new` | `additional` | 교정 공식자료 검색 | `corrections-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 교정 | `new` | `additional` | 교정 통계 근거 브리프 | `corrections-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 교정 | `new` | `additional` | 교정 행정문서 검토 | `corrections-administrative-document-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 교정 | `new` | `additional` | 교정 정책·민원 브리프 | `corrections-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 보호관찰 | `new` | `primary` | 보호관찰 처분·준수사항 검색 | `probation-compliance-search` | `korean-law-bill-research` | — | `read-only` |
| 보호관찰 | `new` | `additional` | 보호관찰 공식자료 검색 | `probation-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 보호관찰 | `new` | `additional` | 보호관찰 통계 근거 브리프 | `probation-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 보호관찰 | `new` | `additional` | 보호관찰 행정문서 검토 | `probation-administrative-document-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 보호관찰 | `new` | `additional` | 보호관찰 정책·민원 브리프 | `probation-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 출입국 | `new` | `primary` | 체류·비자 절차 검색 | `immigration-procedure-search` | `official-source-research` | — | `read-only` |
| 출입국 | `new` | `additional` | 출입국 민원 분류·답변 초안 | `immigration-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 출입국 | `new` | `additional` | 출입국 통계·정책 근거 브리프 | `immigration-statistics-policy-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 출입국 | `new` | `additional` | 출입국 법령 인용 근거 검토 | `immigration-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 출입국 | `new` | `additional` | 출입국 기록공개·비식별 검토 | `immigration-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 경찰 | `direct` | `primary` | LOST112 유실물 조회 | `police-lost-property-lookup` | `official-source-research` | `subway-lost-property` | `read-only` |
| 경찰 | `direct` | `additional` | 경찰 민원 분류·답변 초안 | `police-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 경찰 | `direct` | `additional` | 경찰 범죄통계 브리프 | `police-crime-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 경찰 | `direct` | `additional` | 경찰 법령 인용 근거 검토 | `police-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 경찰 | `direct` | `additional` | 경찰 기록공개·비식별 검토 | `police-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 해양경찰 | `adjacent` | `primary` | 해양기상·안전상황 브리프 | `maritime-safety-brief` | `disaster-geospatial-brief` | `korea-weather`, `han-river-water-level` | `draft-only` |
| 해양경찰 | `adjacent` | `additional` | 해양경찰 공식자료 검색 | `coast-guard-official-source-evidence-review` | `disaster-geospatial-brief` | — | `draft-only` |
| 해양경찰 | `adjacent` | `additional` | 해양경찰 통계 근거 브리프 | `coast-guard-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 해양경찰 | `adjacent` | `additional` | 해양경찰 행정문서 검토 | `coast-guard-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 해양경찰 | `adjacent` | `additional` | 해양경찰 정책·민원 브리프 | `coast-guard-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |

## 안전·국방

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 소방 | `adjacent` | `primary` | 응급실·재난자원 브리프 | `fire-emergency-resource-brief` | `disaster-geospatial-brief` | `emergency-room-beds`, `korea-weather` | `draft-only` |
| 소방 | `adjacent` | `additional` | 소방안전 기준 근거 팩 | `fire-safety-standard-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 소방 | `adjacent` | `additional` | 소방 대응통계 브리프 | `fire-response-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 소방 | `adjacent` | `additional` | 소방 법령 인용 근거 검토 | `fire-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 소방 | `adjacent` | `additional` | 소방 기록공개·비식별 검토 | `fire-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 재난안전 | `direct` | `primary` | 기상·수위·대기 재난브리프 | `disaster-situation-brief` | `disaster-geospatial-brief` | `korea-weather`, `fine-dust-location`, `han-river-water-level`, `emergency-room-beds` | `draft-only` |
| 재난안전 | `direct` | `additional` | 재난 공공안내문 초안 검토 | `disaster-public-message-draft-review` | `disaster-geospatial-brief` | — | `draft-only` |
| 재난안전 | `direct` | `additional` | 재난 대응계획 근거 검토 | `disaster-response-plan-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 재난안전 | `direct` | `additional` | 재난안전 법령 인용 근거 검토 | `disaster-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 재난안전 | `direct` | `additional` | 재난안전 기록공개·비식별 검토 | `disaster-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 국방 | `direct` | `primary` | 국방조달 공개공고 조회 | `defense-procurement-notice-search` | `public-procurement-research` | `d2b-notice-search` | `read-only` |
| 국방 | `direct` | `additional` | 국방 공식자료 검색 | `defense-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 국방 | `direct` | `additional` | 국방 통계 근거 브리프 | `defense-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 국방 | `direct` | `additional` | 국방 행정문서 검토 | `defense-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 국방 | `direct` | `additional` | 국방 정책·민원 브리프 | `defense-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 군무 | `new` | `primary` | 군무 관련 규정 검색 | `civilian-military-regulation-search` | `official-source-research` | — | `read-only` |
| 군무 | `new` | `additional` | 군무 공식자료 검색 | `military-civil-service-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 군무 | `new` | `additional` | 군무 통계 근거 브리프 | `military-civil-service-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 군무 | `new` | `additional` | 군무 행정문서 검토 | `military-civil-service-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 군무 | `new` | `additional` | 군무 정책·민원 브리프 | `military-civil-service-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 경호 | `sensitive` | `primary` | 공개행사 안전점검 | `public-event-security-review` | `official-source-research` | — | `manual-review-only` |
| 경호 | `sensitive` | `additional` | 경호 공식자료 검색 | `security-protection-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 경호 | `sensitive` | `additional` | 경호 통계 근거 브리프 | `security-protection-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 경호 | `sensitive` | `additional` | 경호 행정문서 검토 | `security-protection-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 경호 | `sensitive` | `additional` | 경호 정책·민원 브리프 | `security-protection-policy-evidence-brief` | `public-policy-evidence-pack` | — | `manual-review-only` |

## 사회서비스

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 교육 | `direct` | `primary` | 교육 공공데이터·장학 조회 | `education-public-data-search` | `official-source-research` | `k-schoollunch-menu`, `korean-scholarship-search` | `read-only` |
| 교육 | `direct` | `additional` | 교육통계 근거 브리프 | `education-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 교육 | `direct` | `additional` | 학교 정책문서 검토 | `school-policy-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 교육 | `direct` | `additional` | 교육 민원 분류·답변 초안 | `education-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 교육 | `direct` | `additional` | 교육정책 근거 팩 | `education-policy-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 교육행정 | `direct` | `primary` | 학교장터 공고·학교정보 조회 | `education-procurement-notice-search` | `public-procurement-research` | `s2b-notice-search`, `k-schoollunch-menu` | `read-only` |
| 교육행정 | `direct` | `additional` | 교육행정 문서 초안 검토 | `education-administrative-document-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 교육행정 | `direct` | `additional` | 학교시설 안전계획 검토 | `school-facility-safety-plan-review` | `administrative-document-draft-review` | — | `draft-only` |
| 교육행정 | `direct` | `additional` | 교육기록 정보공개·마스킹 검토 | `education-records-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 교육행정 | `direct` | `additional` | 교육기록 생애주기 검토 | `education-records-lifecycle-review` | `public-records-lifecycle-review` | — | `draft-only` |
| 사회복지 | `direct` | `primary` | 복지·연금·지원정보 조회 | `welfare-pension-support-search` | `welfare-health-safety-research` | `national-pension-workplace`, `donation-place-search`, `korean-scholarship-search` | `read-only` |
| 사회복지 | `direct` | `additional` | 복지 민원 분류·답변 초안 | `welfare-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 사회복지 | `direct` | `additional` | 복지 자격요건 근거 사전점검 | `welfare-eligibility-evidence-check` | `public-policy-evidence-pack` | — | `draft-only` |
| 사회복지 | `direct` | `additional` | 복지정책 통계 근거 브리프 | `welfare-policy-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 사회복지 | `direct` | `additional` | 복지행정 문서 초안 검토 | `welfare-administrative-document-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 고용노동 | `direct` | `primary` | 채용공고·노동법 조사 | `labor-job-law-research` | `official-source-research` | `job-posting-match`, `daangn-jobs-search`, `korean-law-search` | `read-only` |
| 고용노동 | `direct` | `additional` | 고용노동 민원 분류·답변 초안 | `labor-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 고용노동 | `direct` | `additional` | 산업재해 통계 근거 브리프 | `industrial-accident-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 고용노동 | `direct` | `additional` | 노동법 인용 근거 검토 | `labor-law-citation-evidence-review` | `korean-legal-citation-verification` | — | `draft-only` |
| 고용노동 | `direct` | `additional` | 사업장 안전정책 근거 팩 | `workplace-safety-policy-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 보건의료 | `direct` | `primary` | 응급실·검진·장기요양기관 조회 | `healthcare-facility-search` | `welfare-health-safety-research` | `emergency-room-beds`, `nhis-care-checkup-search` | `read-only` |
| 보건의료 | `direct` | `additional` | 보건의료 정책통계 브리프 | `healthcare-policy-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 보건의료 | `direct` | `additional` | 급여기준 근거 팩 | `medical-benefit-criteria-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 보건의료 | `direct` | `additional` | 보건의료 민원 분류·답변 초안 | `healthcare-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 보건의료 | `direct` | `additional` | 보건의료 공지 다국어 검토 | `healthcare-public-notice-multilingual-review` | `official-notice-multilingual-translation-review` | — | `draft-only` |
| 식품의약 | `direct` | `primary` | 식품·의약 안전정보 확인 | `food-drug-safety-check` | `welfare-health-safety-research` | `mfds-food-safety`, `mfds-drug-safety` | `read-only` |
| 식품의약 | `direct` | `additional` | 식품·의약품 회수 근거 브리프 | `food-drug-recall-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 식품의약 | `direct` | `additional` | 식품의약 규제고시 비교 검토 | `regulatory-notice-comparison-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 식품의약 | `direct` | `additional` | 식품·의약 표시기준 근거 검토 | `food-drug-labeling-guidance-evidence-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 식품의약 | `direct` | `additional` | 식품·의약 공지 다국어 검토 | `food-drug-public-notice-multilingual-review` | `official-notice-multilingual-translation-review` | — | `draft-only` |

## 농림·해양·환경

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 농업 | `adjacent` | `primary` | 농업통계·기상 조회 | `agriculture-weather-statistics` | `kosis-official-statistics` | `kosis-stats`, `korea-weather` | `read-only` |
| 농업 | `adjacent` | `additional` | 농업 공식자료 검색 | `agriculture-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 농업 | `adjacent` | `additional` | 농업 통계 근거 브리프 | `agriculture-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 농업 | `adjacent` | `additional` | 농업 행정문서 검토 | `agriculture-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 농업 | `adjacent` | `additional` | 농업 정책·민원 브리프 | `agriculture-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 축산 | `adjacent` | `primary` | 가축질병·축산통계 조회 | `livestock-disease-statistics` | `kosis-official-statistics` | `kosis-stats`, `korea-weather` | `read-only` |
| 축산 | `adjacent` | `additional` | 축산 공식자료 검색 | `livestock-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 축산 | `adjacent` | `additional` | 축산 통계 근거 브리프 | `livestock-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 축산 | `adjacent` | `additional` | 축산 행정문서 검토 | `livestock-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 축산 | `adjacent` | `additional` | 축산 정책·민원 브리프 | `livestock-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 농촌지도 | `adjacent` | `primary` | 영농지도 근거 브리프 | `rural-extension-brief` | `kosis-official-statistics` | `kosis-stats`, `korea-weather` | `draft-only` |
| 농촌지도 | `adjacent` | `additional` | 농촌지도 공식자료 검색 | `rural-extension-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 농촌지도 | `adjacent` | `additional` | 농촌지도 통계 근거 브리프 | `rural-extension-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 농촌지도 | `adjacent` | `additional` | 농촌지도 행정문서 검토 | `rural-extension-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 농촌지도 | `adjacent` | `additional` | 농촌지도 정책·민원 브리프 | `rural-extension-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 산림 | `direct` | `primary` | 산림휴양·기상 조회 | `forest-recreation-weather` | `disaster-geospatial-brief` | `foresttrip-vacancy`, `korea-weather` | `read-only` |
| 산림 | `direct` | `additional` | 산림 공식자료 검색 | `forestry-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 산림 | `direct` | `additional` | 산림 통계 근거 브리프 | `forestry-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 산림 | `direct` | `additional` | 산림 행정문서 검토 | `forestry-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 산림 | `direct` | `additional` | 산림 정책·민원 브리프 | `forestry-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 해양수산 | `adjacent` | `primary` | 해양기상·수산통계 조회 | `fisheries-weather-statistics` | `kosis-official-statistics` | `kosis-stats`, `korea-weather`, `han-river-water-level` | `read-only` |
| 해양수산 | `adjacent` | `additional` | 해양수산 공식자료 검색 | `marine-fisheries-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 해양수산 | `adjacent` | `additional` | 해양수산 통계 근거 브리프 | `marine-fisheries-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 해양수산 | `adjacent` | `additional` | 해양수산 행정문서 검토 | `marine-fisheries-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 해양수산 | `adjacent` | `additional` | 해양수산 정책·민원 브리프 | `marine-fisheries-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 환경 | `direct` | `primary` | 대기·수위·폐기물 정보 조회 | `environment-air-water-waste` | `disaster-geospatial-brief` | `fine-dust-location`, `han-river-water-level`, `household-waste-info`, `korea-weather` | `read-only` |
| 환경 | `direct` | `additional` | 환경 공식자료 검색 | `environment-official-source-evidence-review` | `disaster-geospatial-brief` | — | `draft-only` |
| 환경 | `direct` | `additional` | 환경 통계 근거 브리프 | `environment-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 환경 | `direct` | `additional` | 환경 행정문서 검토 | `environment-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 환경 | `direct` | `additional` | 환경 정책·민원 브리프 | `environment-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |
| 기상 | `direct` | `primary` | 기상청 예보 조회 | `kma-weather-forecast` | `disaster-geospatial-brief` | `korea-weather` | `read-only` |
| 기상 | `direct` | `additional` | 기상 공식자료 검색 | `meteorology-official-source-evidence-review` | `disaster-geospatial-brief` | — | `draft-only` |
| 기상 | `direct` | `additional` | 기상 통계 근거 브리프 | `meteorology-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 기상 | `direct` | `additional` | 기상 행정문서 검토 | `meteorology-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 기상 | `direct` | `additional` | 기상 정책·민원 브리프 | `meteorology-policy-evidence-brief` | `welfare-health-safety-research` | — | `draft-only` |

## 국토·산업

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 국토교통 | `direct` | `primary` | 대중교통·지도 경로 조사 | `public-transit-map-research` | `land-housing-geospatial-research` | `korean-transit-route`, `kakao-map` | `read-only` |
| 국토교통 | `direct` | `additional` | 교통정책·사업 근거 팩 | `transport-policy-project-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 국토교통 | `direct` | `additional` | 교통안전 통계 근거 브리프 | `traffic-safety-statistics-brief` | `kosis-official-statistics` | — | `draft-only` |
| 국토교통 | `direct` | `additional` | 국토교통 절차·근거 검토 | `land-transport-procedure-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 국토교통 | `direct` | `additional` | 국토교통 통계·성과 브리프 | `land-transport-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 토목시설 | `adjacent` | `primary` | 공사·시설점검 자료 조사 | `civil-facility-project-review` | `land-housing-geospatial-research` | `kakao-map`, `gongsijiga-search` | `draft-only` |
| 토목시설 | `adjacent` | `additional` | 건설기준·BIM 적합성 사전점검 | `construction-standard-bim-compliance-precheck` | `construction-standard-bim-compliance-precheck` | — | `draft-only` |
| 토목시설 | `adjacent` | `additional` | 기반시설 유지관리 근거 검토 | `infrastructure-maintenance-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 토목시설 | `adjacent` | `additional` | 토목시설 절차·근거 검토 | `infrastructure-procedure-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 토목시설 | `adjacent` | `additional` | 토목시설 통계·성과 브리프 | `infrastructure-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 건축 | `direct` | `primary` | 토지·등기·공공주택 조사 | `land-building-housing-research` | `land-housing-geospatial-research` | `gongsijiga-search`, `iros-registry-automation`, `lh-notice-search`, `sh-notice-search` | `read-only` |
| 건축 | `direct` | `additional` | 건축 인허가 서류 사전점검 | `building-permit-document-precheck` | `building-permit-document-precheck` | — | `draft-only` |
| 건축 | `direct` | `additional` | 건축기준 조문 인용 점검 | `building-code-citation-check` | `korean-legal-citation-verification` | — | `draft-only` |
| 건축 | `direct` | `additional` | 건축 절차·근거 검토 | `architecture-procedure-evidence-review` | `building-permit-document-precheck` | — | `draft-only` |
| 건축 | `direct` | `additional` | 건축 통계·성과 브리프 | `architecture-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 도시계획 | `direct` | `primary` | 혼잡도·토지·주택 조사 | `urban-planning-density-land` | `land-housing-geospatial-research` | `seoul-density`, `gongsijiga-search`, `lh-notice-search`, `sh-notice-search` | `read-only` |
| 도시계획 | `direct` | `additional` | 도시계획 공식자료 검색 | `urban-planning-official-source-evidence-review` | `land-housing-geospatial-research` | — | `draft-only` |
| 도시계획 | `direct` | `additional` | 도시계획 통계 근거 브리프 | `urban-planning-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 도시계획 | `direct` | `additional` | 도시계획 행정문서 검토 | `urban-planning-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 도시계획 | `direct` | `additional` | 도시계획 정책·민원 브리프 | `urban-planning-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 산업 | `direct` | `primary` | 기업공시·산업정보 조회 | `corporate-industry-information` | `official-source-research` | `k-dart`, `fsc-corporate-info` | `read-only` |
| 산업 | `direct` | `additional` | 산업 공식자료 검색 | `industry-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 산업 | `direct` | `additional` | 산업 통계 근거 브리프 | `industry-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 산업 | `direct` | `additional` | 산업 행정문서 검토 | `industry-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 산업 | `direct` | `additional` | 산업 정책·민원 브리프 | `industry-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 에너지 | `direct` | `primary` | 유가·에너지통계 조회 | `fuel-energy-statistics` | `kosis-official-statistics` | `cheap-gas-nearby`, `kosis-stats` | `read-only` |
| 에너지 | `direct` | `additional` | 에너지 공식자료 검색 | `energy-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 에너지 | `direct` | `additional` | 에너지 통계 근거 브리프 | `energy-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 에너지 | `direct` | `additional` | 에너지 행정문서 검토 | `energy-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 에너지 | `direct` | `additional` | 에너지 정책·민원 브리프 | `energy-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 중소기업 | `direct` | `primary` | 창업지원·사업자 실사 | `sme-startup-due-diligence` | `official-source-research` | `kstartup-search`, `biz-health-check`, `nts-business-registration` | `read-only` |
| 중소기업 | `direct` | `additional` | 중소기업 공식자료 검색 | `sme-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 중소기업 | `direct` | `additional` | 중소기업 통계 근거 브리프 | `sme-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 중소기업 | `direct` | `additional` | 중소기업 행정문서 검토 | `sme-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 중소기업 | `direct` | `additional` | 중소기업 정책·민원 브리프 | `sme-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |

## 과학·디지털

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 과학기술 | `adjacent` | `primary` | 과학기술 특허·동향 조사 | `science-technology-trend-search` | `official-source-research` | `korean-patent-search`, `kosis-stats` | `draft-only` |
| 과학기술 | `adjacent` | `additional` | 국가 R&D 사업 근거 브리프 | `national-rd-program-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 과학기술 | `adjacent` | `additional` | 과학기술 영향 근거 팩 | `technology-impact-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 과학기술 | `adjacent` | `additional` | 과학기술 절차·근거 검토 | `science-technology-procedure-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 과학기술 | `adjacent` | `additional` | 과학기술 통계·성과 브리프 | `science-technology-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 특허 | `direct` | `primary` | KIPRIS 특허 조회 | `korean-patent-lookup` | `patent-prior-art-evidence-pack` | `korean-patent-search` | `read-only` |
| 특허 | `direct` | `additional` | 특허 청구항 인용 근거 검토 | `patent-claim-citation-evidence-review` | `patent-prior-art-evidence-pack` | — | `draft-only` |
| 특허 | `direct` | `additional` | 지식재산 정책통계 근거 브리프 | `ip-policy-statistics-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 특허 | `direct` | `additional` | 특허 절차·근거 검토 | `patent-procedure-evidence-review` | `patent-prior-art-evidence-pack` | — | `draft-only` |
| 특허 | `direct` | `additional` | 특허 통계·성과 브리프 | `patent-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 정보통신 | `adjacent` | `primary` | WHOIS·정보통신 정책 조사 | `ict-policy-domain-research` | `official-source-research` | `kr-whois-lookup`, `korean-privacy-terms` | `read-only` |
| 정보통신 | `adjacent` | `additional` | 정보통신 공식자료 검색 | `ict-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 정보통신 | `adjacent` | `additional` | 정보통신 통계 근거 브리프 | `ict-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 정보통신 | `adjacent` | `additional` | 정보통신 행정문서 검토 | `ict-administrative-document-review` | `public-it-project-procedure-review` | — | `draft-only` |
| 정보통신 | `adjacent` | `additional` | 정보통신 정책·민원 브리프 | `ict-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 전산 | `new` | `primary` | 공공시스템 운영점검 | `public-it-operations-check` | `official-source-research` | — | `draft-only` |
| 전산 | `new` | `additional` | 공공 정보화사업 절차 점검 | `public-it-project-procedure-check` | `public-it-project-procedure-review` | — | `draft-only` |
| 전산 | `new` | `additional` | 공공 정보시스템 보안 체크리스트 검토 | `public-it-security-checklist-review` | `public-it-project-procedure-review` | — | `draft-only` |
| 전산 | `new` | `additional` | 전산 절차·근거 검토 | `public-it-procedure-evidence-review` | `public-it-project-procedure-review` | — | `draft-only` |
| 전산 | `new` | `additional` | 전산 통계·성과 브리프 | `public-it-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 사이버보안 | `adjacent` | `primary` | 개인정보·보안기준 검토 | `privacy-security-baseline-review` | `official-source-research` | `korean-privacy-terms` | `draft-only` |
| 사이버보안 | `adjacent` | `additional` | 개인정보 영향평가 근거 검토 | `privacy-impact-evidence-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 사이버보안 | `adjacent` | `additional` | 사이버 침해사고 대응계획 근거 검토 | `cyber-incident-response-plan-evidence-review` | `public-policy-evidence-pack` | — | `draft-only` |
| 사이버보안 | `adjacent` | `additional` | 사이버보안 절차·근거 검토 | `cybersecurity-procedure-evidence-review` | `public-it-project-procedure-review` | — | `draft-only` |
| 사이버보안 | `adjacent` | `additional` | 사이버보안 통계·성과 브리프 | `cybersecurity-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |

## 문화·지식

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 문화예술 | `direct` | `primary` | 공연예술·시설 조회 | `performance-arts-search` | `official-source-research` | `kopis-performance-search` | `read-only` |
| 문화예술 | `direct` | `additional` | 문화예술 공식자료 검색 | `arts-culture-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 문화예술 | `direct` | `additional` | 문화예술 통계 근거 브리프 | `arts-culture-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 문화예술 | `direct` | `additional` | 문화예술 행정문서 검토 | `arts-culture-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 문화예술 | `direct` | `additional` | 문화예술 정책·민원 브리프 | `arts-culture-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 체육 | `direct` | `primary` | 경기결과·체육정보 조회 | `sports-results-facility-search` | `official-source-research` | `kbo-results`, `kbl-results`, `kleague-results`, `korean-marathon-schedule` | `read-only` |
| 체육 | `direct` | `additional` | 체육 공식자료 검색 | `sports-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 체육 | `direct` | `additional` | 체육 통계 근거 브리프 | `sports-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 체육 | `direct` | `additional` | 체육 행정문서 검토 | `sports-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 체육 | `direct` | `additional` | 체육 정책·민원 브리프 | `sports-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 관광 | `direct` | `primary` | 공공 관광정보 조사 | `public-tourism-information` | `official-source-research` | `foresttrip-vacancy`, `kakao-map`, `myrealtrip-search` | `read-only` |
| 관광 | `direct` | `additional` | 관광 공식자료 검색 | `tourism-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 관광 | `direct` | `additional` | 관광 통계 근거 브리프 | `tourism-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 관광 | `direct` | `additional` | 관광 행정문서 검토 | `tourism-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 관광 | `direct` | `additional` | 관광 정책·민원 브리프 | `tourism-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 문화유산 | `direct` | `primary` | 문화유산 공식자료 검색 | `cultural-heritage-source-search` | `official-source-research` | `joseon-sillok-search` | `read-only` |
| 문화유산 | `direct` | `additional` | 문화유산 공식자료 검색 | `cultural-heritage-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 문화유산 | `direct` | `additional` | 문화유산 통계 근거 브리프 | `cultural-heritage-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 문화유산 | `direct` | `additional` | 문화유산 행정문서 검토 | `cultural-heritage-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 문화유산 | `direct` | `additional` | 문화유산 정책·민원 브리프 | `cultural-heritage-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 기록관리 | `adjacent` | `primary` | 기록물분류·HWPX 검토 | `records-classification-hwpx` | `public-document-hwpx` | `hwp`, `rhwp-edit`, `joseon-sillok-search` | `draft-only` |
| 기록관리 | `adjacent` | `additional` | 공공기록 공개·마스킹 검토 | `public-record-disclosure-redaction-review` | `public-record-disclosure-redaction-review` | — | `draft-only` |
| 기록관리 | `adjacent` | `additional` | 기록물 보존기간표 검토 | `records-retention-schedule-review` | `public-records-lifecycle-review` | — | `draft-only` |
| 기록관리 | `adjacent` | `additional` | 기록관리 절차·근거 검토 | `records-management-procedure-evidence-review` | `public-records-lifecycle-review` | — | `draft-only` |
| 기록관리 | `adjacent` | `additional` | 기록관리 통계·성과 브리프 | `records-management-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 도서관 | `direct` | `primary` | 공공도서관 소장자료 조회 | `public-library-holdings-search` | `official-source-research` | `library-book-search` | `read-only` |
| 도서관 | `direct` | `additional` | 도서관 공식자료 검색 | `library-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 도서관 | `direct` | `additional` | 도서관 통계 근거 브리프 | `library-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 도서관 | `direct` | `additional` | 도서관 행정문서 검토 | `library-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 도서관 | `direct` | `additional` | 도서관 정책·민원 브리프 | `library-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 학예연구 | `adjacent` | `primary` | 유물·자료 출처 조사 | `museum-object-provenance-research` | `official-source-research` | `joseon-sillok-search`, `library-book-search` | `draft-only` |
| 학예연구 | `adjacent` | `additional` | 학예연구 공식자료 검색 | `museum-research-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 학예연구 | `adjacent` | `additional` | 학예연구 통계 근거 브리프 | `museum-research-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 학예연구 | `adjacent` | `additional` | 학예연구 행정문서 검토 | `museum-research-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 학예연구 | `adjacent` | `additional` | 학예연구 정책·민원 브리프 | `museum-research-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 연구 | `direct` | `primary` | 공식출처 연구 브리프 | `official-research-brief` | `official-source-research` | `kosis-stats`, `k-dart`, `naver-news-search`, `daishin-report-search` | `draft-only` |
| 연구 | `direct` | `additional` | 연구 공식자료 검색 | `research-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 연구 | `direct` | `additional` | 연구 통계 근거 브리프 | `research-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 연구 | `direct` | `additional` | 연구 행정문서 검토 | `research-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 연구 | `direct` | `additional` | 연구 정책·민원 브리프 | `research-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |

## 지역·생활행정

| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |
|---|---|---|---|---|---|---|---|
| 지방자치 | `direct` | `primary` | 지방행정 인허가·생활정보 조회 | `local-government-business-status` | `official-source-research` | `localdata-business-status`, `local-election-candidate-search`, `kakao-map` | `read-only` |
| 지방자치 | `direct` | `additional` | 민원 분류·답변 초안 | `local-government-civil-complaint-triage-draft` | `civil-complaint-triage-draft` | — | `draft-only` |
| 지방자치 | `direct` | `additional` | 행정문서 초안·검토 | `local-government-administrative-document-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 지방자치 | `direct` | `additional` | 정책 근거 묶음 | `local-government-public-policy-evidence-pack` | `public-policy-evidence-pack` | — | `draft-only` |
| 지방자치 | `direct` | `additional` | 자치법규안 초안 검토 | `local-ordinance-draft-review` | `local-ordinance-draft-review` | — | `draft-only` |
| 지역개발 | `direct` | `primary` | 주택·토지·혼잡도 개발정보 조회 | `regional-development-housing-land` | `land-housing-geospatial-research` | `lh-notice-search`, `sh-notice-search`, `gongsijiga-search`, `seoul-density` | `read-only` |
| 지역개발 | `direct` | `additional` | 지역개발 공식자료 검색 | `regional-development-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 지역개발 | `direct` | `additional` | 지역개발 통계 근거 브리프 | `regional-development-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 지역개발 | `direct` | `additional` | 지역개발 행정문서 검토 | `regional-development-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 지역개발 | `direct` | `additional` | 지역개발 정책·민원 브리프 | `regional-development-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |
| 지방의회 | `adjacent` | `primary` | 회의록·조례안 조사 | `local-council-minutes-ordinance` | `korean-law-bill-research` | `assembly-bill-vote-search`, `korean-law-search` | `read-only` |
| 지방의회 | `adjacent` | `additional` | 지방의회 의안·상정안 초안 검토 | `local-council-agenda-draft-review` | `administrative-document-draft-review` | — | `draft-only` |
| 지방의회 | `adjacent` | `additional` | 지방의회 예산안 비교 브리프 | `local-council-budget-bill-comparison` | `public-policy-evidence-pack` | — | `draft-only` |
| 지방의회 | `adjacent` | `additional` | 지방의회 절차·근거 검토 | `local-council-procedure-evidence-review` | `administrative-document-draft-review` | — | `draft-only` |
| 지방의회 | `adjacent` | `additional` | 지방의회 통계·성과 브리프 | `local-council-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 우정 | `direct` | `primary` | 우편번호·배송조회 | `postal-code-delivery-tracking` | `official-source-research` | `delivery-tracking`, `zipcode-search` | `read-only` |
| 우정 | `direct` | `additional` | 우정 공식자료 검색 | `postal-official-source-evidence-review` | `official-source-research` | — | `draft-only` |
| 우정 | `direct` | `additional` | 우정 통계 근거 브리프 | `postal-statistics-evidence-brief` | `kosis-official-statistics` | — | `draft-only` |
| 우정 | `direct` | `additional` | 우정 행정문서 검토 | `postal-administrative-document-review` | `administrative-document-draft-review` | — | `draft-only` |
| 우정 | `direct` | `additional` | 우정 정책·민원 브리프 | `postal-policy-evidence-brief` | `public-policy-evidence-pack` | — | `draft-only` |

## 근거와 경계

- Wiki authority: `domains/harness-engineering/korea-local-agent-skillpack-runtime-contract.md`
- Evidence-only source map: `raw/2026-05-28-nomadamas-k-skill-source-map.md`
- Live reference repository: https://github.com/NomaDamas/k-skill
- 확인한 reference HEAD: `0c1bcdc9288545297897b0eee349d30ab2e1b230`
- Reference Skill 이름은 capability 존재 근거일 뿐이며 코드·프롬프트를 가져오지 않습니다.
- `sensitive` domain은 공개정보 기반 manual-review만 허용하고 운영·보호 세부사항을 자동화하지 않습니다.
