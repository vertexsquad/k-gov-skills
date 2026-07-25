---
name: ai-product-procurement-readiness-check
description: "조달 업무의 AI 제품 조달 준비도 점검 절차. 내부 public-procurement-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "조달"
    capability: public-procurement-research
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# AI 제품 조달 준비도 점검

- Domain: **조달**
- 내부 capability: `public-procurement-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- MAS·공고·자격·납품조건을 공식 근거에서 확인
- AI 기능·데이터 처리·성능검증 요구사항을 분리
- 투찰·계약·인증서 사용을 수행하지 않음

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
