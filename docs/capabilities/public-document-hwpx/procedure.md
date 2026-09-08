# 공공문서·HWPX

## 사용 범위

- 합성 또는 승인된 HWPX의 section 수와 문자 수 확인
- 문서 원문을 공개 출력하지 않는 기본 식별자 scan
- 후속 검토 가능 여부를 metadata와 수동 검토 상태로 판단

## 실행 경계

- 원본 파일은 읽기만 하며 덮어쓰기, 추출 저장, cache 생성, 전자문서시스템 제출을 하지 않는다.
- 추출 text는 process 내부에서 문자 수 계산과 식별자 scan에만 일시 사용한다.
- stdout과 error에는 문서 text, raw XML, archive bytes, 경로, 일치 식별자 값을 포함하지 않는다.
- 기본 scan 미검출은 비식별화 완료를 증명하지 않으며 모든 결과에 사람 검토가 필요하다.

## 절차

전체 저장소를 checkout하고 `kgov_runtime/`, `docs/`, `tests/`가 있는 루트에서 실행한다. Skill 디렉터리만 복사한 환경은 지원하지 않는다.

1. 실제 개인정보가 없는 합성 fixture로 `python3 -m kgov_runtime.capabilities.public_document_hwpx --fixture`를 실행한다.
2. fixture 결과가 section 수, 최대 100개 section metadata, 전체 추출 문자 수, 식별자 scan 상태, `text_emitted=false`, `manual_review_required=true`만 포함하는지 확인한다.
3. 승인된 로컬 문서만 `python3 -m kgov_runtime.capabilities.public_document_hwpx <path.hwpx>`로 검사한다.
4. 종료 코드 `0`이면 metadata를 기록하고 원문·개인정보·서식 정확성을 사람이 별도로 검토한다.
5. 종료 코드 `1` 또는 `identifier_scan_status=match-detected-review-blocked`이면 후속 처리를 중단하고 원문을 안전한 승인 환경에서 비식별화 담당자가 검토한다. 출력에서 식별자 값을 찾거나 복원하려 하지 않는다.
6. 종료 코드 `2`이면 archive 형식, local header offset·range overlap, warning, entry 이름 encoding, 허용 압축 method, section index 이름, 전체 entry CRC/integrity, 손상, 암호화, traversal, entry 수·크기·압축률, XML encoding·형식을 안전한 로컬 환경에서 점검한다. CLI error에 원문이나 경로를 추가하지 않는다.

## 출력 계약

- 공개 가능: `section_count`, bounded `section_metadata`, `extracted_character_count`, `identifier_scan_status`, `text_emitted`, `manual_review_required`
- 공개 금지: text/body/raw 필드, section entry 이름, raw XML, archive bytes, 입력 경로, 일치 식별자 값
- 원본 변경/제출: 수행하지 않음
- 최종 판단: 수동 검토 필수

## 실제 로컬 파일 실행

```bash
# 저장소 루트에서, 사용자가 읽기를 승인한 HWPX의 실제 경로로 바꾼다.
python3 -m kgov_runtime.capabilities.public_document_hwpx "/absolute/path/document.hwpx"
```

`PATH` 위치에는 로컬 HWPX 파일 경로를 전달하며 `--fixture`를 붙이지 않는다. HWP/PDF 변환이나 원문 출력 기능은 아니다. 경로가 없거나 파일을 읽을 수 없으면 실패를 보고하고 합성 fixture 결과로 대체하지 않는다.

Skill의 `fixed_input`, `fixture_argv`, 예시 결과는 합성 fixture 전용 계약이다. 실제 파일 실행 결과는 별도의 로컬 입력 검사 증거이며, fixture 통과·공식 원문 live 조회·비식별 완료와 구분한다.

## 실행 도구

- fixture 검증: `python3 -m kgov_runtime.capabilities.public_document_hwpx --fixture`
- 상세 입력·제한·종료 코드는 `runtime-contract.md`를 따른다.
- fixture 통과는 실제 문서 검증 또는 개인정보 제거 완료를 의미하지 않는다.
