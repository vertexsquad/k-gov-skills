# 입법 참고용 법령 검색 결과 확인

## 사용 범위
- `search-laws`는 국가법령정보 `lawSearch.do`의 `target=law`, `type=JSON` 검색 결과에서 법령명·법령 ID·시행일만 투영한다.
- 국회 의안·표결·개정 이력·조문 원문·판례·회의록의 조회나 검증은 제공하지 않는다.
- 현재 `law-go-kr-drf-api` 정책은 비활성·미검토 상태이며 기본 live transport도 `policy-disabled`로 차단된다. `LAW_OC` 설정만으로 조회할 수 없고 시험용 opener 주입은 live 증거가 아니다.

## 실행 경계
- 법률자문이나 사건 결과를 확정하지 않는다.
- 로그인·결제·소송 제출은 자동화하지 않는다.
- 현행성 확인 없는 블로그·요약문을 최종 근거로 쓰지 않는다.

## 절차
1. 관할, 기준일, 법령 검색어를 확정한다. 의안·표결 확인 요청은 별도 수동 조사로 구분한다.
2. `runtime-contract.md`의 고정 endpoint, 필수 `query`, 허용 parameter와 `LAW_OC` 환경변수 경계를 확인한다. 출처 정책·기본 transport 차단을 우회하지 않는다.
3. 검색 결과의 `effective_date`만으로 기준일의 효력·현행성·개정 이력을 확정하지 않는다.
4. 조문 원문·연혁·의안·표결 등 미제공 정보는 담당자가 국가법령정보·국회 등 공식 출처에서 별도로 확인한다.
5. runtime 검색 투영, 담당자의 별도 확인, 해석·미확인을 분리해 보고한다. 법률자문·소송 제출은 수동 전환한다.

## 출력 계약
- contract ID, execution mode, status, count, 최대 100건의 `law_name`·`law_id`·`effective_date`, metadata-only source receipt, manual-review flag
- 원문·개정 이력·표결 정보는 반환하지 않으며 source receipt만으로 실질 검증을 주장하지 않는다.
- 합성 fixture와 실제 조회를 구분하고 기준일 효력·원문 확인은 담당자 검토 사항으로 남긴다.

## 실행 도구

- fixture 검증: `python3 -m kgov_runtime.capabilities.korean_law_bill_research --fixture`
- live 경로: 현재 기본 transport는 차단됩니다. credential·endpoint·출처 정책 조건을 확인하더라도 이 절차만으로 활성화하지 않습니다.
- fixture 통과는 live endpoint 검증을 의미하지 않습니다.
