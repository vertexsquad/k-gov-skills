# 공식출처 페이지 메타데이터 확인

## 사용 범위
- `inspect-page`는 승인된 정부24 공개 HTTPS URL 한 페이지의 제목·메타데이터를 확인한다.
- 웹 검색·본문 추출·공공데이터 API나 사업자 상태·체납 조회는 제공하지 않는다.
- 현재 `gov-kr-web` 정책은 비활성·미검토 상태이므로 실제 URL 요청은 네트워크 전에 exit `3` (`policy-disabled`)으로 차단된다.

## 실행 경계
- 비공개 시스템, 로그인 뒤 개인정보, 유료·제출 기능에 접근하지 않는다.
- 공식 출처가 없으면 일반 웹 추론을 사실처럼 승격하지 않는다.
- 민감업무는 공개정보와 manual-review 범위로 제한한다.

## 절차
1. 질문, 관할기관, 기준일, 필요한 산출물을 정의한다.
2. 담당자가 제공한 URL이 `runtime-contract.md`의 exact source policy 범위에 속하는지 확인한다. 임의 기관 URL로 대체하지 않는다.
3. 정책의 robots·약관·라이선스·rate 조건이 승인되기 전에는 차단 상태를 보고하고 수동 확인으로 이관한다. 로그인·제출·민감업무는 자동 수행하지 않는다.
4. 승인된 실행의 출력도 페이지 제목·메타데이터에 한정한다. 발행일·갱신일·원문 인용이나 사업자 상태·체납 사실은 담당자가 별도로 확인한다.
5. fixture, 페이지 메타데이터 확인, 내용의 정확성·현재성 검토를 서로 다른 증거로 보고한다.

## 출력 계약
- 승인된 실행: query를 제외한 URL, HTTP status, content type, title, 길이, SHA-256, execution mode, source receipt, manual-review flag
- 본문·headers·credential은 반환하지 않으며 receipt는 내용의 정확성이나 이용허락을 증명하지 않는다.
- 합성 fixture: `synthetic-fixture`, null source receipt. 실제 문서나 세무 상태 확인 결과가 아니다.

## 실행 도구

- fixture 검증: `python3 -m kgov_runtime.capabilities.official_source_research --fixture`
- 상세 입력·권한·중단 조건은 `runtime-contract.md`를 따릅니다.
- fixture 통과는 live endpoint 또는 실제 문서 검증을 의미하지 않습니다.
