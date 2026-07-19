---
name: tax-office-procurement-notice-check
description: "세무 업무의 세무관서 조달 공고 조회 절차. 내부 public-procurement-research capability를 사용하며 read-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "세무"
    capability: public-procurement-research
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 세무관서 조달 공고 조회

- Domain: **세무**
- 내부 capability: `public-procurement-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `read-only`
- Reference Skill: 없음

## 절차

1. 저장소 루트에서 `docs/capabilities/public-procurement-research/procedure.md`와 `docs/capabilities/public-procurement-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_procurement_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 투찰·계약·인증서 사용은 수동 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
