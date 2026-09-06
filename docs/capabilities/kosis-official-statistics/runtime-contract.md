# Runtime contract — `kosis-official-statistics`

- contract / operation: `kgov/kosis-official-statistics/v1` / `kgov/kosis-official-statistics/query-statistics/v1`
- source policy / exact endpoint: `kosis-statistics-api` / `https://kosis.kr/openapi/Param/statisticsParameterData.do`; endpoint override는 금지합니다.
- runtime registry: endpoint, contract/policy ID, allowed/required params, credential env/param, record limit, fixed defaults와 projector/validator module+qualname은 승인된 literal과 일치해야 합니다. callable에는 immutable parameter copy만 전달하고 validator 반환 후 다시 검사합니다.
- params: `orgId`, `tblId`, `itmId`, `objL1`, `prdSe`, `startPrdDe`, `endPrdDe` 필수, `newEstPrdCnt` 선택입니다. JSON 조회 형식은 고정됩니다.
- credential: `KOSIS_API_KEY` 환경변수만 `apiKey`로 주입합니다.
- parameter bounds: 식별자는 1~80자, 기간 구분은 Y/H/Q/M/D, 기간값은 Y=`YYYY`, H=`YYYY01..02`, Q=`YYYY01..04`, M=calendar-valid `YYYYMM`, D=calendar-valid `YYYYMMDD` 형식과 순서를 지켜야 하며 `newEstPrdCnt`는 1~100입니다.
- output safety: Unicode NFKC와 control 제거 후 key/value 모두에서 금지 key, direct identifier, credential 및 소문자 percent-encoding 반사를 검사하며 오류에 값을 노출하지 않습니다. projected records는 exact list-of-dicts와 유한 JSON primitive/list/dict만 허용합니다.
- projection: `table_name`, `period`, `category`, `item`, `value`만 최대 100건 반환합니다. envelope·필수 필드·타입·한도 오류는 전체 실패합니다.
- output에는 metadata-only source receipt만 포함하고 raw response, credential, direct identifier를 포함하지 않습니다.
- fixture: `python3 -m kgov_runtime.capabilities.kosis_official_statistics --fixture`; live와 구분되는 synthetic 검증입니다.
- side effect: 조회 전용이며 결과는 담당자가 검토합니다.
