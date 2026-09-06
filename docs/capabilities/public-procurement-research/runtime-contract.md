# Runtime contract — `public-procurement-research`

- contract / operation: `kgov/public-procurement-research/v1` / `kgov/public-procurement-research/query-order-plans/v1`
- source policy / exact endpoint: `data-go-kr-order-plan-api` / `https://apis.data.go.kr/1230000/ao/OrderPlanSttusService`; endpoint override는 금지합니다.
- runtime registry: endpoint, contract/policy ID, allowed/required params, credential env/param, record limit, fixed defaults와 projector/validator module+qualname은 승인된 literal과 일치해야 합니다. callable에는 immutable parameter copy만 전달하고 validator 반환 후 다시 검사합니다.
- params: `pageNo`, `numOfRows`, `inqryDiv`, `inqryBgnDt`, `inqryEndDt`만 허용하고 모두 필수입니다.
- credential: `DATA_GO_KR_API_KEY` 환경변수만 `serviceKey`로 주입합니다.
- parameter bounds: page는 1~10000, page size는 1~100, 조회구분은 1/2, 조회기간은 유효한 YYYYMMDD 순서입니다. 응답 total/page/page-size와 현재 페이지 건수가 일치해야 합니다.
- output safety: Unicode NFKC와 control 제거 후 key/value 모두에서 금지 key, direct identifier, credential 및 소문자 percent-encoding 반사를 검사하며 오류에 값을 노출하지 않습니다. projected records는 exact list-of-dicts와 유한 JSON primitive/list/dict만 허용합니다.
- projection: 발주계획 번호·사업명·수요기관·계획금액·계획일만 최대 100건 반환합니다. upstream status, envelope, 필수 필드, 타입, 한도 오류는 전체 실패합니다.
- output에는 metadata-only source receipt만 포함하고 raw response, credential, direct identifier를 포함하지 않습니다.
- fixture: `python3 -m kgov_runtime.capabilities.public_procurement_research --fixture`; live와 구분되는 synthetic 검증입니다.
- side effect: 조회 전용이며 적격·인증·성능을 자동 판정하지 않습니다.
