---
name: education-civil-complaint-triage-draft
description: "교육 업무의 교육 민원 분류·답변 초안 절차. 내부 civil-complaint-triage-draft capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "교육"
    capability: civil-complaint-triage-draft
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 교육 민원 분류·답변 초안

- Domain: **교육**
- 내부 capability: `civil-complaint-triage-draft`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 민원 목적·대상기관·학교급·요청사항·처리기한을 비식별 상태로 분리
- 교육부·교육청·국가법령정보 공식 URL·조회일·문서 버전과 근거 공백을 보존
- 소관 확정·학생 또는 학교 판단·처분·답변 발송은 교육 담당자 승인으로 이관

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
