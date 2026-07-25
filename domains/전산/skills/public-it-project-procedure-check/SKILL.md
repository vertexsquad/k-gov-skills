---
name: public-it-project-procedure-check
description: "전산 업무의 공공 정보화사업 절차 점검 절차. 내부 public-it-project-procedure-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "전산"
    capability: public-it-project-procedure-review
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 공공 정보화사업 절차 점검

- Domain: **전산**
- 내부 capability: `public-it-project-procedure-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 기획·사전검토·조달·구축·검수·운영 단계 식별
- 단계별 필수 산출물과 승인 주체 확인
- 기관별 적용 규정의 최신성을 담당자가 재확인

## 절차

1. 저장소 루트에서 `docs/capabilities/public-it-project-procedure-review/procedure.md`와 `docs/capabilities/public-it-project-procedure-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_it_project_procedure_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 기관별 적용 규정, 사업 단계 확정, 결재와 조달 착수는 담당 공무원이 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
