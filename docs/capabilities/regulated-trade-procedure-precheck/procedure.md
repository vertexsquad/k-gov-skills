# 관세 원산지·통관 증빙서류 사전점검

## 사용 범위
- 합성·비식별 입력의 원산지 또는 무역절차 증빙서류 검토 초안 admission
- 관세청 FTA 포털과 UNI-PASS 공식 근거 URL을 사용한 담당자 검토용 체크리스트

## 절차
1. 거래 당사자와 연락처 등 직접식별자를 제거하고 `redaction_status=redacted`로 준비합니다.
2. `customs-origin-document-precheck` 또는 `trade-procedure-document-precheck`를 선택합니다.
3. 품목·HS 코드·협정·원산지 기준·증빙서류·기준시점을 구분해 비식별 facts로 기록합니다.
4. credential-free 관세청 또는 UNI-PASS 공식 URL과 조회일을 기록합니다.
5. adapter가 반환한 required checks와 evidence gap을 관세사 또는 세관 담당자가 검토합니다.
6. 원산지 판정·특혜관세 적용·신고·제출·통관·제재 판단은 수행하지 않습니다.

## 실행
- fixture: `python3 -m kgov_runtime.capabilities.regulated_trade_procedure_precheck --fixture`
- local input: `python3 -m kgov_runtime.capabilities.regulated_trade_procedure_precheck <redacted.json>`
- fixture PASS는 URL 도달, 원산지 판정 또는 실제 통관 성공을 의미하지 않습니다.
