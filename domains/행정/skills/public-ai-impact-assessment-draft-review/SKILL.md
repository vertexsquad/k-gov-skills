---
name: public-ai-impact-assessment-draft-review
description: "행정 업무의 공공 AI 영향평가 초안 검토 절차. 내부 public-ai-governance-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "행정"
    capability: public-ai-governance-review
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 공공 AI 영향평가 초안 검토

- Domain: **행정**
- 내부 capability: `public-ai-governance-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 영향 대상·목적·데이터 범위를 명시
- 권리·안전·차별·개인정보 영향을 근거별 분리
- 완화조치·이의제기·중단조건을 담당자에게 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/public-ai-governance-review/procedure.md`와 `docs/capabilities/public-ai-governance-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_ai_governance_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 영향·위험 등급, 운영 중단, 이의제기, 최종 승인 판단은 기관 책임자가 수행
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
