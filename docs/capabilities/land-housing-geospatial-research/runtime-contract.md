# Runtime contract — `land-housing-geospatial-research`

- contract / declared operation: `kgov/land-housing-geospatial-research/v1` / `kgov/land-housing-geospatial-research/blocked-dataset-query/v1`
- live status: **blocked**. exact dataset endpoint, source policy, parameter schema, credential contract, semantic projector가 선언되기 전에는 네트워크를 호출하지 않습니다.
- generic `apis.data.go.kr` base URL, host-level endpoint override, arbitrary parameter, raw response fallback은 지원하지 않습니다.
- fixture: `python3 -m kgov_runtime.capabilities.land_housing_geospatial_research --fixture`; 빈 projected-record 계약과 차단 상태만 합성 검증합니다.
- live CLI는 policy-blocked exit code `3`으로 종료합니다.
- side effect: 조회 전용이며 결과는 담당자가 검토합니다.
