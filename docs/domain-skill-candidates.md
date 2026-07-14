# Domain별 Skill 후보

> 이 문서는 `catalog/domain-skills.json`에서 생성합니다. 직접 편집하지 마세요.
> 외부 reference의 코드·문서를 복사하지 않으며, 독립 구현을 위한 capability 근거로만 사용합니다.

## 요약

- 전체 domain: **60개**
- 직접 reference 확인: **35개**
- 인접 capability 활용: **16개**
- 신규 설계 필요: **8개**
- 민감업무 제한: **1개**
- 구현 상태: 모든 domain 항목은 후보이며, 실제 API·인증·약관 검증 후 승격합니다.

## Evidence 등급

| 값 | 의미 |
|---|---|
| `direct` | 직접 reference 확인 |
| `adjacent` | 인접 capability 활용 |
| `new` | 신규 설계 필요 |
| `sensitive` | 민감업무 제한 |

## 공통 capability runtime manifest

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

## 국가운영

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 행정 | `direct` | 공공문서·HWPX 검토 | `government-document-hwpx-review` | `public-document-hwpx` | `hwp`, `rhwp-edit` | `draft-only` |
| 재정 | `adjacent` | 예산·결산 비교 | `budget-settlement-comparison` | `kosis-official-statistics` | `kosis-stats`, `k-dart` | `read-only` |
| 세무 | `direct` | 사업자·체납 상태조회 | `business-tax-status-lookup` | `official-source-research` | `nts-business-registration`, `nts-tax-delinquency` | `read-only` |
| 관세 | `new` | HS 품목·관세율 조사 | `tariff-hs-code-research` | `official-source-research` | — | `read-only` |
| 감사 | `adjacent` | 감사 증빙 교차검증 | `audit-evidence-cross-check` | `official-source-research` | `biz-health-check`, `g2b-sanctioned-supplier` | `draft-only` |
| 통계 | `direct` | KOSIS 공식통계 조회 | `kosis-statistics-lookup` | `kosis-official-statistics` | `kosis-stats` | `read-only` |
| 조달 | `direct` | 나라장터 발주·제재 조회 | `public-procurement-plan-check` | `public-procurement-research` | `g2b-order-plan-search`, `g2b-sanctioned-supplier` | `read-only` |
| 외교 | `new` | 공식 국가·외교 브리프 | `official-country-brief` | `official-source-research` | — | `draft-only` |
| 통일 | `new` | 북한·통일정책 공식자료 검색 | `unification-policy-source-search` | `official-source-research` | — | `read-only` |
| 선거관리 | `direct` | 지방선거 후보자 조회 | `local-election-candidate-lookup` | `official-source-research` | `local-election-candidate-search` | `read-only` |
| 입법 | `direct` | 국회 의안·표결 조회 | `assembly-bill-vote-lookup` | `korean-law-bill-research` | `assembly-bill-vote-search` | `read-only` |

## 법무·치안

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 사법 | `direct` | 법령·법원공고·등기 조사 | `law-court-registry-research` | `korean-law-bill-research` | `korean-law-search`, `court-auction-notice-search`, `iros-registry-automation`, `court-payment-order-assistant` | `read-only` |
| 검찰 | `adjacent` | 검찰업무 법적 근거 조사 | `prosecution-legal-basis-research` | `korean-law-bill-research` | `korean-law-search` | `read-only` |
| 교정 | `new` | 교정 관련 규정 검색 | `corrections-regulation-search` | `korean-law-bill-research` | — | `read-only` |
| 보호관찰 | `new` | 보호관찰 처분·준수사항 검색 | `probation-compliance-search` | `korean-law-bill-research` | — | `read-only` |
| 출입국 | `new` | 체류·비자 절차 검색 | `immigration-procedure-search` | `official-source-research` | — | `read-only` |
| 경찰 | `direct` | LOST112 유실물 조회 | `police-lost-property-lookup` | `official-source-research` | `subway-lost-property` | `read-only` |
| 해양경찰 | `adjacent` | 해양기상·안전상황 브리프 | `maritime-safety-brief` | `disaster-geospatial-brief` | `korea-weather`, `han-river-water-level` | `draft-only` |

## 안전·국방

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 소방 | `adjacent` | 응급실·재난자원 브리프 | `fire-emergency-resource-brief` | `disaster-geospatial-brief` | `emergency-room-beds`, `korea-weather` | `draft-only` |
| 재난안전 | `direct` | 기상·수위·대기 재난브리프 | `disaster-situation-brief` | `disaster-geospatial-brief` | `korea-weather`, `fine-dust-location`, `han-river-water-level`, `emergency-room-beds` | `draft-only` |
| 국방 | `direct` | 국방조달 공개공고 조회 | `defense-procurement-notice-search` | `public-procurement-research` | `d2b-notice-search` | `read-only` |
| 군무 | `new` | 군무 관련 규정 검색 | `civilian-military-regulation-search` | `official-source-research` | — | `read-only` |
| 경호 | `sensitive` | 공개행사 안전점검 | `public-event-security-review` | `official-source-research` | — | `manual-review-only` |

## 사회서비스

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 교육 | `direct` | 교육 공공데이터·장학 조회 | `education-public-data-search` | `official-source-research` | `k-schoollunch-menu`, `korean-scholarship-search` | `read-only` |
| 교육행정 | `direct` | 학교장터 공고·학교정보 조회 | `education-procurement-notice-search` | `public-procurement-research` | `s2b-notice-search`, `k-schoollunch-menu` | `read-only` |
| 사회복지 | `direct` | 복지·연금·지원정보 조회 | `welfare-pension-support-search` | `welfare-health-safety-research` | `national-pension-workplace`, `donation-place-search`, `korean-scholarship-search` | `read-only` |
| 고용노동 | `direct` | 채용공고·노동법 조사 | `labor-job-law-research` | `official-source-research` | `job-posting-match`, `daangn-jobs-search`, `korean-law-search` | `read-only` |
| 보건의료 | `direct` | 응급실·검진·장기요양기관 조회 | `healthcare-facility-search` | `welfare-health-safety-research` | `emergency-room-beds`, `nhis-care-checkup-search` | `read-only` |
| 식품의약 | `direct` | 식품·의약 안전정보 확인 | `food-drug-safety-check` | `welfare-health-safety-research` | `mfds-food-safety`, `mfds-drug-safety` | `read-only` |

## 농림·해양·환경

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 농업 | `adjacent` | 농업통계·기상 조회 | `agriculture-weather-statistics` | `kosis-official-statistics` | `kosis-stats`, `korea-weather` | `read-only` |
| 축산 | `adjacent` | 가축질병·축산통계 조회 | `livestock-disease-statistics` | `kosis-official-statistics` | `kosis-stats`, `korea-weather` | `read-only` |
| 농촌지도 | `adjacent` | 영농지도 근거 브리프 | `rural-extension-brief` | `kosis-official-statistics` | `kosis-stats`, `korea-weather` | `draft-only` |
| 산림 | `direct` | 산림휴양·기상 조회 | `forest-recreation-weather` | `disaster-geospatial-brief` | `foresttrip-vacancy`, `korea-weather` | `read-only` |
| 해양수산 | `adjacent` | 해양기상·수산통계 조회 | `fisheries-weather-statistics` | `kosis-official-statistics` | `kosis-stats`, `korea-weather`, `han-river-water-level` | `read-only` |
| 환경 | `direct` | 대기·수위·폐기물 정보 조회 | `environment-air-water-waste` | `disaster-geospatial-brief` | `fine-dust-location`, `han-river-water-level`, `household-waste-info`, `korea-weather` | `read-only` |
| 기상 | `direct` | 기상청 예보 조회 | `kma-weather-forecast` | `disaster-geospatial-brief` | `korea-weather` | `read-only` |

## 국토·산업

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 국토교통 | `direct` | 대중교통·지도 경로 조사 | `public-transit-map-research` | `land-housing-geospatial-research` | `korean-transit-route`, `kakao-map` | `read-only` |
| 토목시설 | `adjacent` | 공사·시설점검 자료 조사 | `civil-facility-project-review` | `land-housing-geospatial-research` | `kakao-map`, `gongsijiga-search` | `draft-only` |
| 건축 | `direct` | 토지·등기·공공주택 조사 | `land-building-housing-research` | `land-housing-geospatial-research` | `gongsijiga-search`, `iros-registry-automation`, `lh-notice-search`, `sh-notice-search` | `read-only` |
| 도시계획 | `direct` | 혼잡도·토지·주택 조사 | `urban-planning-density-land` | `land-housing-geospatial-research` | `seoul-density`, `gongsijiga-search`, `lh-notice-search`, `sh-notice-search` | `read-only` |
| 산업 | `direct` | 기업공시·산업정보 조회 | `corporate-industry-information` | `official-source-research` | `k-dart`, `fsc-corporate-info` | `read-only` |
| 에너지 | `direct` | 유가·에너지통계 조회 | `fuel-energy-statistics` | `kosis-official-statistics` | `cheap-gas-nearby`, `kosis-stats` | `read-only` |
| 중소기업 | `direct` | 창업지원·사업자 실사 | `sme-startup-due-diligence` | `official-source-research` | `kstartup-search`, `biz-health-check`, `nts-business-registration` | `read-only` |

## 과학·디지털

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 과학기술 | `adjacent` | 과학기술 특허·동향 조사 | `science-technology-trend-search` | `official-source-research` | `korean-patent-search`, `kosis-stats` | `draft-only` |
| 특허 | `direct` | KIPRIS 특허 조회 | `korean-patent-lookup` | `official-source-research` | `korean-patent-search` | `read-only` |
| 정보통신 | `adjacent` | WHOIS·정보통신 정책 조사 | `ict-policy-domain-research` | `official-source-research` | `kr-whois-lookup`, `korean-privacy-terms` | `read-only` |
| 전산 | `new` | 공공시스템 운영점검 | `public-it-operations-check` | `official-source-research` | — | `draft-only` |
| 사이버보안 | `adjacent` | 개인정보·보안기준 검토 | `privacy-security-baseline-review` | `official-source-research` | `korean-privacy-terms` | `draft-only` |

## 문화·지식

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 문화예술 | `direct` | 공연예술·시설 조회 | `performance-arts-search` | `official-source-research` | `kopis-performance-search` | `read-only` |
| 체육 | `direct` | 경기결과·체육정보 조회 | `sports-results-facility-search` | `official-source-research` | `kbo-results`, `kbl-results`, `kleague-results`, `korean-marathon-schedule` | `read-only` |
| 관광 | `direct` | 공공 관광정보 조사 | `public-tourism-information` | `official-source-research` | `foresttrip-vacancy`, `kakao-map`, `myrealtrip-search` | `read-only` |
| 문화유산 | `direct` | 문화유산 공식자료 검색 | `cultural-heritage-source-search` | `official-source-research` | `joseon-sillok-search` | `read-only` |
| 기록관리 | `adjacent` | 기록물분류·HWPX 검토 | `records-classification-hwpx` | `public-document-hwpx` | `hwp`, `rhwp-edit`, `joseon-sillok-search` | `draft-only` |
| 도서관 | `direct` | 공공도서관 소장자료 조회 | `public-library-holdings-search` | `official-source-research` | `library-book-search` | `read-only` |
| 학예연구 | `adjacent` | 유물·자료 출처 조사 | `museum-object-provenance-research` | `official-source-research` | `joseon-sillok-search`, `library-book-search` | `draft-only` |
| 연구 | `direct` | 공식출처 연구 브리프 | `official-research-brief` | `official-source-research` | `kosis-stats`, `k-dart`, `naver-news-search`, `daishin-report-search` | `draft-only` |

## 지역·생활행정

| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |
|---|---|---|---|---|---|---|
| 지방자치 | `direct` | 지방행정 인허가·생활정보 조회 | `local-government-business-status` | `official-source-research` | `localdata-business-status`, `local-election-candidate-search`, `kakao-map` | `read-only` |
| 지역개발 | `direct` | 주택·토지·혼잡도 개발정보 조회 | `regional-development-housing-land` | `land-housing-geospatial-research` | `lh-notice-search`, `sh-notice-search`, `gongsijiga-search`, `seoul-density` | `read-only` |
| 지방의회 | `adjacent` | 회의록·조례안 조사 | `local-council-minutes-ordinance` | `korean-law-bill-research` | `assembly-bill-vote-search`, `korean-law-search` | `read-only` |
| 우정 | `direct` | 우편번호·배송조회 | `postal-code-delivery-tracking` | `official-source-research` | `delivery-tracking`, `zipcode-search` | `read-only` |

## 근거와 경계

- Wiki authority: `domains/harness-engineering/korea-local-agent-skillpack-runtime-contract.md`
- Evidence-only source map: `raw/2026-05-28-nomadamas-k-skill-source-map.md`
- Live reference repository: https://github.com/NomaDamas/k-skill
- 확인한 reference HEAD: `0c1bcdc9288545297897b0eee349d30ab2e1b230`
- Reference Skill 이름은 capability 존재 근거일 뿐이며 코드·프롬프트를 가져오지 않습니다.
- `sensitive` 후보는 공개정보 기반 manual-review만 허용하고 운영·보호 세부사항을 자동화하지 않습니다.
