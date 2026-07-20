# Runtime contract — `korean-legal-citation-verification`

## 역할

- 국가법령정보의 현행·연혁 법령 목록, 조·항·호·목 상세, 판례 목록·상세 API를 read-only로 조회합니다.
- caller는 인용 후보만 입력합니다. `official`, 조회 성공 선언, 원문 URL은 입력할 수 없습니다.
- capability가 공식 응답을 직접 가져와 구조·기준일·locator·인용문을 대조합니다.
- 결과는 법률 판단이 아니라 초안에 인용을 넣어도 되는지를 판단하는 admission 결과입니다.

## 공식 API

- 법령 목록: `https://www.law.go.kr/DRF/lawSearch.do?target=eflaw`
- 법령 조·항·호·목: `https://www.law.go.kr/DRF/lawService.do?target=eflawjosub`
- 판례 목록: `https://www.law.go.kr/DRF/lawSearch.do?target=prec`
- 판례 상세: `https://www.law.go.kr/DRF/lawService.do?target=prec`
- 허용 host: 정확히 `law.go.kr`
- credential: 사용자 환경변수 `LAW_OC`; URL·CLI 인수·로그·fixture에 값을 기록하지 않습니다.
- endpoint override: 제공하지 않음
- redirect: 금지
- 응답 상한·DNS/public-IP 검증: 공통 `kgov_runtime.http` 계약 적용
- 검색 envelope는 `page`, `display`, `totalCnt`로 계산한 해당 page의 예상 record 수와 실제 수가 정확히 같아야 합니다. 법령 연혁 pagination은 page 사이 `totalCnt` 일치와 누적 record 고유성을 추가로 강제합니다.
- 출력 직전 현재 credential의 raw·URL-encoded·소문자 percent-escape 형태를 재귀 검사하고 반사가 있으면 전체를 fail-closed 처리합니다.

공식 가이드:

- 현행 법령 목록: `https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdListGuide`
- 현행 법령 본문: `https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdInfoGuide`
- 조·항·호·목: `https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=lsEfYdJoListGuide`
- 판례 목록: `https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precListGuide`
- 판례 상세: `https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=precInfoGuide`

## 검색 계약

### 법령

허용 parameter: `query`, `search`, `LID`, `display`, `page`.

- `display`: 1–100
- `page`: 1–10,000
- verifier는 `LID`로 연혁을 조회한 뒤 법령명이 정확히 같고 `시행일자 <= as_of_date`인 가장 최신 단일 version을 선택합니다.
- 같은 최신 시행일에 서로 다른 법령일련번호가 있으면 자동 선택하지 않습니다.

### 판례

허용 parameter: `query`, `search`, `display`, `page`, `sort`, `date`, `prncYd`, `nb`, `curt`, `org`, `JO`.

- `display`: 1–100
- 결과가 0건이면 `no-candidates`, 1건이면 `unique-candidate`, 2건 이상이면 `ambiguous-candidates-manual-selection-required`입니다.
- 목록 결과에는 사건명·raw envelope·API가 credential을 반사한 상세 링크를 출력하지 않습니다.
- 사건번호·법원·선고일·판례일련번호와 credential-free 공식 URL만 반환합니다.

## verifier 입력

Top-level exact fields:

- `as_of_date`: `YYYY-MM-DD`
- `jurisdiction`: `KR`
- `input_scope`: `redacted-citations-only`
- `citations`: 1–30개

공통 citation exact fields:

- `citation_id`: `^[A-Z][A-Z0-9_-]{0,31}$`, ledger 안에서 유일
- `kind`: `statute` 또는 `precedent`
- `candidate`: 종류별 후보 object

Statute candidate exact fields:

- `law_name`: 공식 법령명 후보
- `law_id`: 숫자 6자리 법령 ID
- `article_code`: 6자리 `JO`; 예: 제2조 `000200`, 제10조의2 `001002`
- `paragraph_code`: 단순 항의 4자리 순번 또는 `null`; runtime은 `0002`를 공식 6자리 `HANG=000200`으로 변환합니다.
- `item_code`: 단순 호의 4자리 순번 또는 `null`; paragraph 필수. runtime은 `0002`를 공식 6자리 `HO=000200`으로 변환합니다.
- `subitem_code`: 4자리 순번 또는 `null`; item 필수. runtime은 `0001/0002/0003`을 공식 `MOK=가/나/다`로 변환합니다.
- `quoted_text`: 정규화 후 12자 이상인 실제 인용 후보

Precedent candidate exact fields:

- `serial_number`: 목록 결과의 숫자형 판례일련번호
- `case_number`, `court`, `decision_date`, `quoted_text`
- `decision_date`: `YYYY-MM-DD`

입력 파일은 최대 250,000 bytes입니다. capability는 네트워크 호출 전에 전체 schema·PII·control-character 검사를 완료합니다. 모든 입력 문자열은 NFKC 정규화 후 `C*`, `Zl`, `Zp` 문자를 거부합니다. 식별자 검사는 control 제거, Unicode dash 통일, 연속 공백 축약, 구분자 주변 공백 제거, 공백·dash 제거형을 포함한 canonical 검사본에도 적용합니다.

## trusted admission

### 법령

1. `law_id`로 공식 연혁을 조회합니다.
2. 기준일 이하의 정확한 법령명 중 최신 version을 고릅니다.
3. 해당 `MST`, `efYd`, 6자리 `JO/HANG/HO`와 한글 한 글자 `MOK`로 `eflawjosub`를 직접 조회합니다.
4. 반환된 법령명·ID·시행일·조문 locator를 확인합니다.
5. 인용문은 요청한 조·항·호·목의 text 안에서만 확인합니다. 다른 항·호에 있는 문구는 통과하지 않습니다.

현재 입력 계약은 `제N항`, `제N호`처럼 가지번호 없는 항·호만 지원합니다. `제N호의M` 같은 locator는 임의로 축약하지 말고 지원 범위 밖으로 처리합니다.

### 판례

1. 입력된 판례일련번호로 공식 상세를 직접 조회합니다.
2. 응답의 판례일련번호·사건번호·법원·선고일을 확인합니다.
3. `선고일 <= as_of_date`를 강제합니다.
4. 인용문이 실제 `판시사항`, `판결요지`, `판례내용` 중 어디에서 일치했는지 `quote_source_field`로 반환합니다.

공식 not-found만 항목 차단 상태로 처리합니다. 인증 오류·API 오류·빈/변경된 envelope는 not-found로 오인하지 않고 실행 자체를 fail-closed로 중단합니다.

## 출력과 종료 코드

- 모든 citation이 통과해야 `admission_passed=true`, `permitted_output=verified-citations-draft`입니다.
- 하나라도 차단되면 `admission_passed=false`, `permitted_output=no-citations-admitted`이며 CLI 종료 코드는 `1`입니다.
- schema·credential·transport·공식 API schema 오류는 CLI 종료 코드 `2`입니다.
- 통과 항목 상태: `verified-official-live-match`
- 불일치: `mismatch-blocked`
- 공식 미존재: `official-source-not-found`
- 법령 version 모호성: `ambiguous-candidates-manual-selection-required`
- 차단 항목에는 `verified_citation`을 만들지 않습니다.
- 결과에는 candidate 인용문, raw 법령/판례 본문, 원응답 envelope, 사건명, 연락처를 출력하지 않습니다.
- `source_url`은 capability가 공식 식별자에서 credential-free로 생성합니다.

## 보증 경계

- 보증: 실행 시점에 직접 조회한 공식 record와 식별자·기준일·locator·인용문이 구조적으로 일치함
- 보증하지 않음: 법률 해석, 사실관계 적용, 판례의 현재 효력, 반대·제한 판례 검색 완전성, 최종 문서 적합성
- `manual_review_required=true`; 최종 인용·결재·발송은 담당 공무원 또는 법무 검토자가 승인합니다.
- 제출·결재·발송·업로드·전자소송·원본 변경은 금지합니다.
- fixture는 합성·결정적·credential-free이며 live 진위 확인을 대신하지 않습니다. fixture 출력은 항상 `verification_mode=synthetic-fixture`, `admission_passed=false`, `permitted_output=fixture-validation-only`입니다. 합성 matching 계약이 맞으면 `fixture_contract_passed=true`, 항목 상태는 `synthetic-fixture-match`이고 CLI만 성공 코드 `0`을 반환합니다.
