# Live smoke — `korean-legal-citation-verification`

- 실행 시각(UTC): `2026-07-20T03:40:16Z`
- 공식 endpoint: 국가법령정보 공동활용 `lawSearch.do`, `lawService.do`
- 인증: 공식 가이드의 공개 예제 값 `LAW_OC=test`; 사용자 소유 비밀값 사용·기록 없음
- side effect: read-only GET

## 실행 범위

### 법령

1. `target=eflaw`, 법령 ID `011357`의 연혁을 조회했습니다.
2. 기준일 `2026-07-20` 이하에서 정확한 법령명 `개인정보 보호법`의 최신 시행 version `2025-10-02`를 선택했습니다.
3. `target=eflawjosub`, `MST=270351`, `efYd=20251002`, `JO=001500`, `HANG=000200`, `HO=000100`으로 조문 단위를 직접 조회했습니다.
4. 법령명·ID·시행일·제15조 제2항 제1호 귀속과 실제 인용문을 확인했습니다.

### 판례

1. `target=prec`, 검색어 `손해배상`, `display=1`, 선고일 범위 `20200101~20201231`로 목록을 조회했습니다.
2. 숫자형 판례일련번호 `218239`로 상세를 다시 조회했습니다.
3. 판례일련번호·사건번호·법원·선고일과 `판시사항`의 실제 인용문을 확인했습니다.

## 관측 결과

- trusted admission: `true`
- verified: 2, blocked: 0
- 법령: `개인정보 보호법 제15조 제2항 제1호`, `verified-official-live-match`
- 판례: `대법원 2020-12-30 선고 2019다284889 판결`, `verified-official-live-match`
- 판례 quote source: `판시사항`
- 목 locator 추가 smoke: 건축법 `MST=193412`, `efYd=20171019`, 제2조 제1항 제11호 가목. 입력 순번을 `HANG=000100`, `HO=001100`, `MOK=가`로 변환한 trusted admission이 `true`였습니다.
- API 응답의 raw envelope, 사건명, 법령 담당 전화번호, 판례 본문, credential 반사 링크는 결과에 포함되지 않았습니다.
- 법령 source URL은 exact 연혁 `lsiSeq=270351`, 조문 `joNo=0015`, 가지번호 `joBrNo=00`을 포함하며, 판례 URL과 함께 각각 `HTTP 200`, `text/html`, 최종 host `www.law.go.kr`를 확인했습니다.

## 보증하지 않는 것

- 모든 검색 파라미터·모든 법령 연혁·모든 판례의 완전성
- 법률 해석, 사실관계 적용, 후속 개정·변경·폐기 여부의 법적 판단
- 반대·제한 판례 검색의 완전성
- 최종 보고서·민원 답변에서의 인용 적합성

fixture 검증과 live smoke는 서로 대체하지 않습니다. 실제 운영에서는 사용자 소유 `LAW_OC`와 담당 공무원 또는 법무 검토자의 원문 확인이 필요합니다.
