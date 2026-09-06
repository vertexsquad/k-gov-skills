# Runtime contract — `korean-law-bill-research`

- contract: `kgov/korean-law-bill-research/v1`
- operation: `kgov/korean-law-bill-research/search-laws/v1`
- source policy: `law-go-kr-drf-api`
- runtime registry: endpoint, contract/policy ID, allowed/required params, credential env/param, record limit, fixed defaults와 projector/validator module+qualname은 승인된 literal과 일치해야 합니다. callable에는 immutable parameter copy만 전달하고 validator 반환 후 다시 검사합니다.
- exact endpoint: `https://www.law.go.kr/DRF/lawSearch.do`; 사용자 endpoint override는 금지합니다.
- params: `query` 필수, `search`, `LID`, `display`, `page`만 허용합니다. `target=law`, `type=JSON`은 고정됩니다.
- credential: `LAW_OC` 환경변수만 `OC`로 주입하며 URL·출력·fixture에 보존하지 않습니다.
- parameter bounds: `query`는 1~200자, `LID`는 ASCII 숫자 6자리, `display`는 1~100, `page`는 1~10000입니다. `totalCnt`와 요청 page/display로 계산한 현재 페이지 건수가 일치해야 합니다.
- output safety: Unicode NFKC와 control 제거 후 key/value 모두에서 금지 key, direct identifier, credential 및 소문자 percent-encoding 반사를 검사하며 오류에 값을 노출하지 않습니다. projected records는 exact list-of-dicts와 유한 JSON primitive/list/dict만 허용합니다.
- projection: `law_name`, `law_id`, `effective_date`만 최대 100건 반환합니다. 한 건이라도 envelope·필수 필드·타입 계약을 위반하면 전체 실패합니다.
- output: contract ID, execution mode, status, count, projected records, metadata-only source receipt, manual-review flag만 포함합니다. `raw`와 원문 fallback은 없습니다.
- fixture: `python3 -m kgov_runtime.capabilities.korean_law_bill_research --fixture`; synthetic fixture 통과는 live 검증이 아닙니다.
- side effect: 조회 전용이며 결과는 담당자가 검토합니다.
