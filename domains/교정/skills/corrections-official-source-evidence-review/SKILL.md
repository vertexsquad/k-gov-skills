---
name: corrections-official-source-evidence-review
description: "교정 업무의 교정 공식자료 검색 절차. 내부 official-source-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "교정"
    capability: official-source-research
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 교정 공식자료 검색

- Domain: **교정**
- 내부 capability: `official-source-research`
- 실행 상태: `live-verified` / live smoke `passed`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 교정 업무 대상·기관·기준일·검색 범위를 분리
- 공식 원문 URL·발행기관·공표일·조회일과 근거 공백을 보존
- 교정 사실 확정·자격·허가·운영 판단은 담당기관 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/official-source-research/procedure.md`와 `docs/capabilities/official-source-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.official_source_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 로그인·제출·민감업무는 수동 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
