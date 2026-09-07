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
- 허용 origin: 정확히 `https://www.law.go.kr`
- credential: 사용자 환경변수 `LAW_OC`; URL·CLI 인수·로그·fixture에 값을 기록하지 않습니다.
- endpoint override: 제공하지 않음
- redirect: 금지
- 응답 상한·DNS/public-IP 검증: 공통 `kgov_runtime.http` 계약 적용
- 검색 envelope는 `page`, `display`, `totalCnt`로 계산한 해당 page의 예상 record 수와 실제 수가 정확히 같아야 합니다. 법령 연혁 pagination은 page 사이 `totalCnt` 일치와 누적 record 고유성을 추가로 강제합니다.
- 출력 직전 요청 credential의 raw·기본 slash-safe `quote`·전체 `quote`·`quote_plus` 형태를 재귀 검사합니다. 양쪽 문자열의 유효한 `%XX` escape를 strict UTF-8로 정확히 한 번만 해석하여 literal/encoded 혼합 및 혼합 대소문자 반사를 차단하며, 중첩 `%25`는 재귀 해석하지 않습니다.

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
- schema·parameter·credential 오류는 `2`, 정책 차단은 `3`, upstream·transport·공식 API schema 오류는 `4`입니다.
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

## Policy-enforced execution (Issue #31)

All four public library entrypoints accept `runtime: LegalRuntime | None`, not
legacy `opener`/`resolver` overrides. Tests inject `HttpTransport` beneath the real
`HttpPolicyEnforcer`; production leaves its transport at the pinned-TLS default.
`LegalRuntime` binds the exact registry-owned `law-go-kr-drf-api` policy, enforcer,
and `execution_mode` (`official-live` or `synthetic-fixture`).

Every `SourceRequest` uses the one registered aggregate operation:
`kgov/korean-legal-citation-verification/verify-citations/v1`.
The following closed capability-local call kinds are metadata, not operation IDs:

| call_kind | Fixed path | Fixed target |
| --- | --- | --- |
| `law-search` | `/DRF/lawSearch.do` | `eflaw` |
| `law-detail` | `/DRF/lawService.do` | `eflawjosub` |
| `precedent-search` | `/DRF/lawSearch.do` | `prec` |
| `precedent-detail` | `/DRF/lawService.do` | `prec` |

All requests fix `type=JSON`. Search values must be nonempty strings or integers,
never booleans, at most 200 characters, without controls or direct identifiers.
Caller `OC`, `target`, `type`, unknown keys and duplicate CLI parameters are denied.
Identifier scanning uses the string representation of both integer and string
values. The direct `LegalSession.fetch` seam also rejects `OC`, `target` and
`type` case-insensitively before credential/state/transport work; fixed routing
values cannot be overridden through a `LegalCall`.
Standalone `get_precedent` also scans its normalized serial string for direct
identifiers before runtime construction; numeric phone/RRN shapes are not valid
lookup identifiers merely because they consist of digits.

Input validation finishes before runtime construction. Production loads the
unchanged catalog with `date.today()` (not the historical citation `as_of_date`),
authorizes before state creation, credential access or DNS, and reuses one runtime
for the entire batch. Each call rechecks registry-owned policy identity before
reading `LAW_OC`. The current disabled catalog stops all live modes without
network access or persistent-state initialization.

The durable state-path precedence is `KGOV_POLICY_STATE_PATH`, then
`$XDG_STATE_HOME/k-gov-skills/policy-state.sqlite3`, then
`~/.local/state/k-gov-skills/policy-state.sqlite3`. All call kinds share the same
policy/digest budget. State failures, digest conflicts and excessive waits fail
closed; no retry, automatic purge or capability-specific budget reset occurs.

## Projectors, receipts and partial failures

Raw official envelopes and citable text are transient **inside enforcer
projectors only**. Search projectors emit safe metadata. Detail projectors select
the exact unit, verify identities and match quotes before returning metadata or
the verification result. Recognized official not-found is a typed projected
value, not an exception crossing the enforcer boundary; it retains its receipt.
API errors, malformed envelopes and identity mismatches remain upstream errors.
PII-bearing discarded fields never become output; projected metadata is scanned
for Unicode/identifier hazards and reflected credential encodings.

Every successful projected source fetch appends an ordered `source_receipts`
entry containing:

- `call_kind`, fixed query-free `endpoint`, validated `citation_id` or `null`,
  and search `page` (including default page 1) or `null` for detail;
- `source_receipt`: unchanged enforcer fields `operation_id`, `policy_id`,
  `policy_revision`, `policy_digest`, `outcome=allowed` for live-mode retrieval.

Every history page and repeated fetch remains in order; receipts are never
deduplicated by policy. Verification with a supplied precedent serial makes no
precedent-search call and invents no corresponding receipt. Standalone searches
and detail retrieval return one receipt. Robots HTTP exchanges consume budget
but have no separate source receipt in the shared API. A failed fetch/projection
has no allowed receipt.

`LegalExecutionError` carries a stable `status`, completed `source_receipts`, and
safe `failed_call` metadata (or `null` for cross-page consistency failures).
The CLI writes these to stderr, with no partial admission on stdout. It never
prints raw exceptions, credentials, query values or source content.
One request-local `LegalSession` boundary protects projected values (including
not-found), appended receipts, complete public outputs and library exception
traces. It captures credential material only after authorization. Conflicting
caller `citation_id` values become `null` in boundary-owned copies, including
successful citation results; caller input and authentic receipt fields are never
rewritten. Any remaining credential collision in a value or field name fails
closed as `response-invalid`, with empty `source_receipts` and
`failed_call=null`. The CLI only serializes already-safe library errors and exits
`4`; it never prints a successful result whose receipt would expose a credential.
Synthetic fixture outputs and errors never consult `LAW_OC`; fixture errors omit
their trace.

Credential comparison builds a bounded set of semantic views from the raw
string. Percent decoding, HTML entity decoding, and NFKC are each applied at
most once, in every ordering needed to mirror actual metadata transformations;
percent decoding also has a query-form view for `+`-encoded spaces. Every
intermediate view is bounded to 250,000 UTF-8 bytes and percent decoding is
strict UTF-8. This catches fullwidth credentials transformed to ASCII,
entity-split reflections, and one-pass percent/entity compositions. A transform
cannot be applied twice, so `%2540` can become `%40` but never `@`. Safe returned
metadata retains its original spelling.

Direct-identifier scanning uses the same semantic views, followed only by the
contracted control, dash, whitespace, and separator comparison forms. Mapping
keys and values are scanned. String values and JSON spellings of integer,
finite-float, and boolean scalars are covered, so an identifier-shaped
`total_count` cannot bypass screening by becoming an integer. Invalid UTF-8,
oversized views, non-finite values, encoded email/phone/resident identifiers,
and composed percent/entity/fullwidth forms fail before an allowed receipt.
Authentic earlier receipts are retained without rewriting; a failing fetch does
not receive a receipt.

Stable protocol status tokens, such as `response-invalid` and
`upstream-403-manual`, are implementation constants selected by runtime control
flow, not credential-derived reflection. If `LAW_OC` happens to equal such a
token, the necessary error status and its stable exit code remain present.
Caller metadata, authentic receipt fields and upstream material remain subject
to the credential boundary; equality does not permit them to be emitted or a
receipt to be falsified. Tests distinguish the mandatory protocol status from
credential-bearing payload/trace material rather than trying to hide constants.

Statutory labels must full-match simple numeric, NFKC-normalized circled-number,
or Korean-letter forms, optionally followed by `.` or `)`. Prefix parsing is
forbidden: branch labels such as `1의2.`, `①의2` or `가의2.` and other suffixes
fail closed rather than matching a simple item/paragraph/subitem locator.
Quote normalization likewise requires `.` or `)` after a numeric list prefix,
and that delimiter must not be followed by another digit. A numeric `.` marker
must additionally not be followed by another dot after NFKC: `1…5%` and
`1..5%` retain their first endpoint and cannot match `9…5%`, `9..5%` or `.5%`.
Complete identical dot/ellipsis ranges still match. Bare leading digits
and decimal integer parts remain substantive text: official `1.5%` cannot match
candidate `9.5%` in either statute or precedent verification. Legitimate `1. `
prefixes and no-space `1.문장` list forms remain supported. Circled structural markers are
recognized before NFKC removes their distinction, and Korean-letter list forms
are preserved. Thus `1. 1000000원을...` cannot verify `5000000원을...`, while
the identical amount can still match after removing only the structural prefix.

Both verification paths use the same numeric-token-aware containment helper.
An excerpt may occur anywhere in official text, but neither end may fall inside
a signed numeric token, grouped/decimal number, Korean amount (including scale
words and won), or percentage token. This blocks `11.5%` -> `1.5%`, `1.5%` ->
`5%`, and `5000000원` -> `000000원` truncations. All occurrences are considered:
a later complete occurrence can match even if an earlier partial one cannot.
Leading-dot decimals, explicit signs, scientific exponents, fractions and
connected numeric ranges/expressions are also complete tokens: `.5%`, `−1.5%`,
`1e5원`, `1/5` and `1~5%` cannot be verified by taking an interior suffix or
prefix. Optional spaces around signs/connectors are included in the token.
Recognized connectors include slash/colon, hyphen/tilde, arithmetic symbols,
ellipsis, `to`/`through`, and `부터`/`까지`/`내지`/`에서`; they join tokens only
when followed by another numeric atom. This deliberately rejects ambiguous
partial-range excerpts rather than choosing an endpoint automatically.
Spaces immediately around Korean scale components and before `원` are part of
the same numeric atom. Thus `1억 5000만원`, `1억 원`, and multi-component amounts
cannot be matched by an interior component. This rule consumes only recognized
scale/currency syntax or a following numeric component; it does not join numbers
across ordinary conjunctions or prose such as `및` or `지원금과 별도로`.

Normalization is textual, not numerical evaluation. Quote comparison does
not apply broad NFKC. It selectively folds fullwidth ASCII and space plus the
explicitly contracted dash, sign, slash, colon, tilde, ellipsis, and Korean-dot
forms. Compatibility fractions, parenthesized forms, square/cubic units, and
other compatibility characters retain their source structure and cannot expand
into matchable fragments.

A stdlib `HTMLParser` renders the supported block, inline, `wbr`, `sup`, and
`sub` tags, including supported tags with attributes. Block tags create
whitespace; inline and `wbr` tags create no boundary. Entity references are
decoded exactly once as text, so entity-escaped literal tags remain literal and
are never reparsed. Unknown markup, comments, declarations, processing
instructions, nested/unbalanced script tags, and self-closing script markup fail
closed. Parser-owned provenance delimiters are rejected in literal or
entity-decoded source text. Adjacent same-kind HTML and Unicode script runs merge
into one provenance marker. Individual and merged payloads are non-empty and at
most 64 characters, so invalid runs fail before boundary scanning. Script runs
remain distinct from baseline digits and letters.

Both verification paths share one conservative quantitative-token grammar.
Protected tokens include abbreviated/full dotted dates and ranges, Korean
`년월일` dates, grouped spaces and NBSPs, mixed and `분의` fractions,
compatibility fractions, bounded Korean-word/Arabic scaled won amounts,
superscript/subscript values, spaced percent/per-mille and numeric units,
nine-dot/ellipsis ranges, ASCII or Unicode inequalities, roots, scientific
notation, and the contracted arithmetic/range connectors. One shared operator
prefix and quantity atom apply to numeric and Korean-word amounts alike, and
range connectors compose every atom pairing. Thus `일억 오천만원` cannot match
`오천만원`; `<`, `>`, `<=`, `>=`, `≤`, `≥`, signs, and roots cannot be dropped;
and a Korean-amount range cannot verify only its final endpoint.

Exact excerpt occurrences are found before quantitative scanning. Only fixed
256-character windows around each start and end boundary are scanned; no regex
receives source-wide text. Quantitative expressions use bounded repetitions and
atomic or possessive matching. If a possible run reaches a window edge while
covering the inspected boundary, comparison fails closed. Complete forms and
ordinary prose excerpts remain valid; unrelated prose is never joined into a
quantity. Numeric and Korean list markers are still removed only in their
contracted leading forms, after date recognition, preserving `1. 문장`,
`1.문장`, list-marker-before-amount, decimals, and ellipsis ranges.

Synthetic fixture execution uses only an in-memory reviewed registry, offline
transport and unique temporary SQLite state. It does not read or mutate
`LAW_OC`, does not enable any catalog policy, and returns `source_receipt=null`
on every synthetic call entry. No live citation or source URL is admitted.

| Exit | Meaning |
| --- | --- |
| `0` | Successful retrieval, fully matched verification, passing fixture contract |
| `1` | Verification mismatch, not-found, history ambiguity, failing fixture match |
| `2` | Invalid input/mode/parameters or credential missing after authorization |
| `3` | Disabled/stale policy, robots/terms/license denial, rate/state failure |
| `4` | Upstream failure, 401/403/429/CAPTCHA, invalid media/JSON/envelope/projection |

An ambiguous standalone search still exits `0` with manual-selection metadata.
Offline tests/fixtures are not evidence of live official verification or legal
relevance, completeness, current precedent validity, or permission to publish.
