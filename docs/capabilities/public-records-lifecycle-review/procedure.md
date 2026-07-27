# 공공기록물 생애주기 검토

## 사용 범위
- 합성·비식별 입력의 `public-records-lifecycle-review` 검토 초안 admission
- 기록물계열·업무기능·보존기간 근거·이관/폐기 gate를 담당자가 검토하기 위한 체크리스트

## 절차
1. 원문 개인정보와 실제 기록물 원문을 제거하고 `redaction_status=redacted`로 준비합니다.
2. `retention-schedule-review, transfer-disposal-precheck` 중 하나의 검토 유형을 선택합니다.
3. 국가기록원·국가법령정보센터의 공식 근거 URL과 조회일을 기록합니다.
4. adapter가 반환한 required checks와 근거 공백을 기록물관리 담당자가 검토합니다.
5. 보존기간 확정·평가·이관·폐기·원본 변경은 수행하지 않습니다.

## 실행
- fixture: `python3 -m kgov_runtime.capabilities.public_records_lifecycle_review --fixture`
- local input: `python3 -m kgov_runtime.capabilities.public_records_lifecycle_review <redacted.json>`
- fixture PASS는 공식 URL의 현재 도달성이나 실제 기록관리시스템 연동 성공을 의미하지 않습니다.
