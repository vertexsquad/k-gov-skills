# Runtime contract — `public-document-hwpx`

## 입력과 실행 경계

- 입력: 로컬 `.hwpx` ZIP/XML 문서 한 개
- credential/proxy/network: 없음
- side effect: 문서 읽기만 수행하며 원본을 추출·수정·덮어쓰거나 cache에 저장하지 않는다.
- fixture 검증: `python3 -m kgov_runtime.capabilities.public_document_hwpx --fixture`
- 실제 문서 검증: `python3 -m kgov_runtime.capabilities.public_document_hwpx <path.hwpx>`

## 공개 출력

성공 및 식별자 차단 결과는 다음 최소 메타데이터만 JSON으로 반환한다.

- `section_count`: 확인한 section XML 수
- `section_metadata`: 최대 100개 section의 1-based `ordinal`과 `character_count`, 공개 한도 `limit`, 생략 여부 `truncated`
- `extracted_character_count`: 각 outermost `<t>` 내부의 descendant text와 tail을 문서 순서대로 한 번만 포함한 모든 section의 추출 문자 수 합계
- `identifier_scan_status`: `no-match-not-proof-of-redaction` 또는 `match-detected-review-blocked`
- `text_emitted`: 항상 `false`
- `manual_review_required`: 항상 `true`

문서 text, raw XML, archive bytes, 입력 경로, 일치한 식별자 값은 stdout과 error에 반환하지 않는다. `no-match-not-proof-of-redaction`은 비식별화 완료 증명이 아니다. `match-detected-review-blocked`는 사람이 원문과 비식별화 상태를 검토하기 전 후속 사용을 중단하는 상태다.

## 입력 제한과 거부

- archive entry: 최대 2,000개
- 개별 entry 비압축 크기: 최대 10 MB
- 총 비압축 크기: 최대 50 MB
- entry 압축률: 최대 200:1
- 허용 압축 방식: `ZIP_STORED`, `ZIP_DEFLATED`; BZIP2, LZMA, 알 수 없는 method는 압축 해제 전에 거부한다.
- section 공개 metadata: 최대 100개; 전체 section 수와 전체 추출 문자 수는 계속 집계한다.
- section 이름 suffix: 최대 10자리 ASCII decimal만 index로 변환하며 동일 index의 다른 표기(예: `1`, `01`)는 거부한다.
- XML text traversal은 single pass이며 outermost `<t>`를 만나면 `itertext()`로 한 번만 수집하고 해당 subtree를 다시 순회하지 않는다.
- local header offset은 entry마다 고유해야 하며 고정 header와 압축 payload로 계산 가능한 최소 range가 다음 local header와 겹치면 testzip 전에 거부한다.
- bounds 검사 후 모든 entry의 CRC/integrity와 DEFLATE stream을 확인한다. section이 아닌 attachment의 손상이나 압축 해제 오류도 input error로 거부한다.
- archive 생성·testzip·read 중 `UserWarning`은 boundary 내부에서 exception으로 승격하고 archive-controlled warning payload를 출력하지 않는다.
- UTF-8로 표시된 entry 이름을 decode할 수 없는 archive는 input error로 거부한다.
- traversal/절대경로/Windows 경로, 중복 entry, 암호화 entry, HWPX가 아닌 ZIP, 손상된 archive, 알 수 없는 XML encoding, DTD/entity 선언, malformed XML은 input error로 거부한다.
- ZIP과 XML은 process 내부에서만 읽고 임시 디렉터리에 풀지 않는다. context manager 종료 시 archive handle을 결정적으로 닫는다.

## 종료 코드와 수동 전환

- `0`: metadata 산출 완료, 식별자 기본 scan 미검출
- `1`: 식별자 기본 scan 검출, 후속 처리 차단 및 수동 검토 필요
- `2`: 인자 또는 입력 archive 오류

원본 변경·제출·결재와 식별자 scan 이후의 마스킹 판단은 이 adapter 범위 밖이며 수동 전환한다. 메모리 wipe 또는 secure-delete는 보증하지 않는다.
