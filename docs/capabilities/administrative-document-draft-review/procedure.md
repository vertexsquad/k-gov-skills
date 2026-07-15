# 행정문서 초안·검토

## 사용 조건

- 입력 문서는 synthetic이거나 사용자 권한 아래 비식별 처리된 자료여야 합니다.
- 지원 유형은 `official-letter`, `report`, `meeting-material`, `press-release`입니다.
- 기관별 서식, 보안등급, 공개 범위와 결재선은 담당자가 별도로 확인합니다.

## 절차

1. 문서 유형·목적·예상 독자와 `redaction_status=redacted`를 확인합니다.
2. 제목·본문·목적에서 직접 식별자 잔존 여부를 검사합니다.
3. 핵심 주장과 수치, 법령·조례 표현, 출처 목록을 분리합니다.
4. 확인된 근거와 미확인 주장·인용 TODO를 구분해 초안 또는 검토 의견을 작성합니다.
5. 기관별 공식 서식, 개인정보, 공개 가능성, 법령·통계 해석을 검토 체크리스트로 남깁니다.
6. 담당 공무원이 원문과 공식 근거를 대조하고 결재·발송 여부를 결정하도록 handoff합니다.

## 금지사항

- 입력 원문을 adapter 결과나 오류에 재출력하지 않습니다.
- 기관별 공식 서식 준수, 법률 판단, 통계 해석, 사실 확인 완료를 자동으로 선언하지 않습니다.
- HWP/HWPX/PDF를 수정하거나 문서를 결재·등록·발송·게시하지 않습니다.
- AI 탐지 회피, 문체 위장, `humanizer` 기능을 제공하지 않습니다.

## 실행

```bash
python3 -m kgov_runtime.capabilities.administrative_document_draft_review --fixture
python3 -m kgov_runtime.capabilities.administrative_document_draft_review redacted-document.json
```

출력은 `draft-review-only`이며 항상 담당자 최종 검토가 필요합니다.
