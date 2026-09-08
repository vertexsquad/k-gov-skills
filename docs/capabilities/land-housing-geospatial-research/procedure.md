# 토지·주택·공간 조회 차단 안내

## 사용 범위
- `blocked-dataset-query`는 공시지가·등기·LH/SH 공고, 교통·주소·좌표·혼잡도, 도시계획·시설 자료 조회를 현재 제공하지 않는다.
- exact dataset endpoint·source policy·parameter schema·credential contract·semantic projector가 선언되기 전에는 네트워크를 호출하지 않는다.
- 합성 fixture는 빈 projected-record 계약과 차단 상태만 확인한다. 실제 토지·주택 기초자료 조회나 자료 비교가 아니다.

## 실행 경계
- 감정평가, 법적 권리, 투자수익을 확정하지 않는다.
- 등기 발급·결제·청약·계약을 자동 수행하지 않는다.
- 주소와 필지, 공고일과 기준연도 차이를 숨기지 않는다.

## 절차
1. 주소·필지·좌표와 기준시점을 확정한다.
2. runtime의 조회 차단 상태를 보고한다. 범용 공공데이터 URL이나 임의 parameter로 우회하지 않는다.
3. 공식 토지·주택·교통 자료, 공간 식별자, 공고·등기 상태는 담당자가 별도로 확인하도록 이관한다.
4. 담당자가 확보한 관측값·공시값·법적 효력이 있는 문서를 구분하며 fixture로 이를 확인했다고 주장하지 않는다.
5. runtime 차단 결과와 별도 수동 확인 사항을 보고한다. 지도·사실표를 runtime 산출물로 제시하지 않는다.

## 출력 계약
- fixture: `execution_mode=synthetic-fixture`, `status=live-operation-blocked`, `count=0`, `records=[]`, null policy ID·endpoint, `manual_review_required=true`
- 빈 records는 실제 검색 0건이 아니며 공간 식별자·공시값·권리관계·지도·사실표를 반환하지 않는다.
- fixture 없는 CLI는 exit `3`으로 차단되며 거래·발급·청약·계약·감정평가는 위 수동 경계를 따른다.

## 실행 도구

- fixture 검증: `python3 -m kgov_runtime.capabilities.land_housing_geospatial_research --fixture`
- live 조회는 현재 미제공입니다. `runtime-contract.md`의 exact dataset profile 선언과 정책·인증·이용허락 검토를 이 절차나 fixture로 대체하지 않습니다.
- fixture 통과는 live endpoint 검증을 의미하지 않습니다.
