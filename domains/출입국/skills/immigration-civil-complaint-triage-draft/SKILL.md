---
name: immigration-civil-complaint-triage-draft
description: "출입국 업무의 출입국 민원 분류·답변 초안 절차. 내부 civil-complaint-triage-draft capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "출입국"
    capability: civil-complaint-triage-draft
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 출입국 민원 분류·답변 초안

- Domain: **출입국**
- 내부 capability: `civil-complaint-triage-draft`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 체류·비자 민원 소관과 요청사항을 분리
- 체류자격·처분·입국 가능 여부를 자동 판단하지 않음
- 답변 발송은 출입국 담당자 승인

## 절차

1. 저장소 루트에서 `docs/capabilities/civil-complaint-triage-draft/procedure.md`와 `docs/capabilities/civil-complaint-triage-draft/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.civil_complaint_triage_draft --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 소관 확정·처분 판단·답변 발송은 담당 공무원 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
