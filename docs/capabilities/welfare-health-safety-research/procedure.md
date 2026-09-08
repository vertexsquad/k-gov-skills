# 복지·보건·안전 조회 차단 안내

## 사용 범위
- `blocked-dataset-query`는 복지·연금·지원사업, 응급실·검진·장기요양기관, 식품·의약품 정보 조회를 현재 제공하지 않는다.
- exact dataset endpoint·source policy·parameter schema·credential contract·semantic projector가 선언되기 전에는 네트워크를 호출하지 않는다.
- 합성 fixture는 빈 projected-record 계약과 차단 상태만 확인한다. 실제 검색 결과나 가용 병상·기관 운영 정보가 아니다.

## 실행 경계
- 복지 수급자격, 의학적 진단, 복약·치료를 확정하지 않는다.
- 주민번호·건강정보·처방정보를 저장하거나 출력하지 않는다.
- 긴급 상황은 공식 긴급전화와 의료진 판단으로 전환한다.

## 절차
1. 지역, 대상자 범주, 기준일, 필요한 정보 범위를 최소화한다.
2. runtime의 조회 차단 상태를 보고한다. 범용 공공데이터 URL이나 임의 parameter로 우회하지 않는다.
3. 최신 안내·지원조건·운영시간·기관상태·안전주의는 담당자가 공식 기관에 별도로 확인하도록 이관한다.
4. 개인 상황에 적용하려면 담당기관 확인이 필요한 항목을 표시한다. fixture로 그 확인을 대신하지 않는다.
5. runtime 차단 결과, 담당자의 별도 확인, 상담·진단 영역을 분리해 보고한다.

## 출력 계약
- fixture: `execution_mode=synthetic-fixture`, `status=live-operation-blocked`, `count=0`, `records=[]`, null policy ID·endpoint, `manual_review_required=true`
- 빈 records는 실제 검색 0건이 아니며 조건·기관·연락처·안전정보 요약을 반환하지 않는다.
- fixture 없는 CLI는 exit `3`으로 차단되며 자격·진단·복약 판단과 긴급전환은 위 수동 경계를 따른다.

## 실행 도구

- fixture 검증: `python3 -m kgov_runtime.capabilities.welfare_health_safety_research --fixture`
- live 조회는 현재 미제공입니다. `runtime-contract.md`의 exact dataset profile 선언과 정책·인증·이용허락 검토를 이 절차나 fixture로 대체하지 않습니다.
- fixture 통과는 live endpoint 검증을 의미하지 않습니다.
