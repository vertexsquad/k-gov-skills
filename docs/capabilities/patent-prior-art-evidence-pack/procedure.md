# 특허 선행기술 근거 입력 검토 접수

## 사용 범위
- 기본 binding인 `review-case`는 사용자가 제공한 합성·비식별 근거 입력의 로컬 admission이며 네트워크·정책 state를 사용하지 않는다.
- 별도 `inspect-source`는 승인된 KIPRIS 또는 지식재산처의 legacy KIPO URL 한 페이지의 bounded GET 메타데이터 확인이다. 현재 `kipris-web`·`kipo-web` 정책 비활성으로 네트워크·state 생성 전에 차단된다.
- 어느 경로도 특허 검색 엔진이 아니며 문헌·청구항·선행기술의 실질 검증이나 근거표 자동 작성을 제공하지 않는다.

## 절차
1. 담당자가 확보한 근거를 로컬 검토 입력으로 준비합니다. URL lookup은 admission의 선행 단계나 필수 조건이 아닙니다.
2. 원문 개인정보를 제거하고 `redaction_status=redacted`로 준비합니다.
3. `prior-art-evidence-pack, claim-element-mapping` 중 하나의 검토 유형을 선택합니다.
4. `runtime-contract.md`의 exact 입력 필드와 출처 URL·조회일·발행일·라이선스·재배포·receipt 조건을 지킵니다. 호출자가 선언한 출처와 정책 metadata 대조는 실제 조회·진본성·이용허락 증명이 아닙니다.
5. 로컬 admission 결과의 `required_checks`에 따라 공개번호·공개일, 청구항별 인용 위치, 중복·누락을 담당자가 검토합니다. runtime은 이 항목들의 실질 검토 결과를 반환하지 않습니다.
6. 신규성·진보성·침해·등록가능성 판단과 출원·심판 제출은 변리사 또는 담당자에게 이관하며 최종 판단·승인·제출·게시·발송은 수행하지 않습니다.

## 출력 경계
- 로컬 admission은 count·status·check identifiers·assurance·manual-review 정보를 반환하며 입력 case ID·URL·본문·facts를 재출력하지 않습니다. `admitted-pending-human-review`는 초안 검토 접수이지 특허 판단이나 조회 성공이 아닙니다.
- 별도 lookup은 승인된 경우에만 query 없는 URL·HTTP status·content type·title·길이·hash와 source receipt를 반환합니다. 본문·도면·첨부 추출·링크 추적은 제공하지 않습니다.
- lookup의 `source_receipt`를 admission의 `policy_receipt`로 승격하거나 페이지 접근 승인을 첨부물 이용허락으로 간주하지 않습니다. robots·약관·라이선스·rate·exact host 정책 게이트를 유지합니다.

## 실행
- fixture: `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack --fixture`
- local input: `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack <redacted.json>`
- 별도 URL lookup (현재 정책 차단, exit `3`): `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack --lookup-url <KIPRIS-or-KIPO-HTTPS-URL>`
- fixture PASS는 URL 도달이나 live workflow 성공을 의미하지 않습니다.

## 출처 정체성

- 현행 기관 표기는 지식재산처이며 `kipo-web`은 기존 `www.kipo.go.kr` origin을 식별하는 안정된 policy ID입니다. 기관명 정정으로 `www.moip.go.kr`이나 특허로를 새로 허용하지 않습니다.
- KIPRIS는 서비스 명칭을 유지합니다. 공식 약관은 제공기관을 특허정보원으로 명시하며 지식재산처와의 권리·이용관계도 설명합니다.
- 기관명·policy revision·합성 receipt의 정합성은 출처 정책 활성화나 실제 조회 증거가 아닙니다. 경로별 관측과 이용조건은 `runtime-contract.md`의 2026-09-08 검토 기록을 따릅니다.
