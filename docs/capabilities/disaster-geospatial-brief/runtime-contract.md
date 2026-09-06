# Runtime contract — `disaster-geospatial-brief`

- contract / operation: `kgov/disaster-geospatial-brief/v1` / `kgov/disaster-geospatial-brief/query-village-forecast/v1`
- source policy / exact endpoint: `data-go-kr-village-forecast-api` / `https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst`; endpoint override는 금지합니다.
- runtime registry: endpoint, contract/policy ID, allowed/required params, credential env/param, record limit, fixed defaults와 projector/validator module+qualname은 승인된 literal과 일치해야 합니다. callable에는 immutable parameter copy만 전달하고 validator 반환 후 다시 검사합니다.
- params: `pageNo`, `numOfRows`, `base_date`, `base_time`, `nx`, `ny`만 허용하고 모두 필수입니다. `dataType=JSON`은 고정됩니다.
- credential: `KMA_OPEN_API_KEY` 환경변수만 `serviceKey`로 주입합니다.
- parameter bounds: page는 1~10000, page size는 1~100, 기준일은 유효한 YYYYMMDD, 기준시각은 기상청 발표시각, 격자 x/y는 각각 1~149/1~253입니다. 응답 total/page/page-size와 현재 페이지 건수가 일치해야 합니다.
- output safety: Unicode NFKC와 control 제거 후 key/value 모두에서 금지 key, direct identifier, credential 및 소문자 percent-encoding 반사를 검사하며 오류에 값을 노출하지 않습니다. projected records는 exact list-of-dicts와 유한 JSON primitive/list/dict만 허용합니다.
- projection: 예보 분류·일자·시각·값·격자 좌표만 최대 100건 반환합니다. upstream status, envelope, 필수 필드, 타입, 한도 오류는 전체 실패합니다.
- output에는 metadata-only source receipt만 포함하고 raw response, credential, direct identifier를 포함하지 않습니다.
- fixture: `python3 -m kgov_runtime.capabilities.disaster_geospatial_brief --fixture`; live와 구분되는 synthetic 검증입니다.
- side effect: 조회 전용이며 결과는 담당자가 검토합니다.
