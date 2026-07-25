# 자치법규안 초안 검토

## 사용 범위
- 합성·비식별 입력의 `local-ordinance-draft-review` 검토 초안 admission
- 공식 근거 URL과 조회일을 보존한 담당자 검토용 체크리스트

## 절차
1. 원문 개인정보를 제거하고 `redaction_status=redacted`로 준비합니다.
2. `ordinance-draft-review, legal-basis-review` 중 하나의 검토 유형을 선택합니다.
3. 공식 출처와 조회일을 근거별로 기록합니다.
4. adapter가 반환한 required checks와 evidence gap을 담당자가 검토합니다.
5. 최종 판단·승인·제출·게시·발송은 수행하지 않습니다.

## 실행
- fixture: `python3 -m kgov_runtime.capabilities.local_ordinance_draft_review --fixture`
- local input: `python3 -m kgov_runtime.capabilities.local_ordinance_draft_review <redacted.json>`
- fixture PASS는 URL 도달이나 live workflow 성공을 의미하지 않습니다.
