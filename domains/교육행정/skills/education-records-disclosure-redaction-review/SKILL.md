---
name: education-records-disclosure-redaction-review
description: "교육행정 업무의 교육기록 정보공개·마스킹 검토 절차. 내부 public-record-disclosure-redaction-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "교육행정"
    capability: public-record-disclosure-redaction-review
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 교육기록 정보공개·마스킹 검토

- Domain: **교육행정**
- 내부 capability: `public-record-disclosure-redaction-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 학생·보호자·교직원 기록의 문서유형·정보항목·청구범위·부분공개 후보를 분리
- 개인정보 원문을 저장하지 않고 공식 정보공개·기록관리 법령 URL·조회일·버전과 마스킹 근거를 보존
- 비공개 사유·공개 범위·원문 마스킹·공개 결정은 정보공개 담당자 승인으로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/public-record-disclosure-redaction-review/procedure.md`와 `docs/capabilities/public-record-disclosure-redaction-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_record_disclosure_redaction_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 비공개 사유, 공개 범위, 원문 마스킹과 공개 결정은 정보공개 담당자가 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
