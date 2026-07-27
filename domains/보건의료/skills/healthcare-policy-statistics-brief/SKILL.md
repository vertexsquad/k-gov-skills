---
name: healthcare-policy-statistics-brief
description: "보건의료 업무의 보건의료 정책통계 브리프 절차. 내부 kosis-official-statistics capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "보건의료"
    capability: kosis-official-statistics
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 보건의료 정책통계 브리프

- Domain: **보건의료**
- 내부 capability: `kosis-official-statistics`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 지표명·지역·기간·기관 또는 질환 범주·분모·단위·집계 기준을 분리
- KOSIS 통계표 코드·작성기관·수록기간·조회일·개정 상태와 결측을 보존
- 진단·치료·기관 서열화·정책 효과 판단은 보건의료 담당기관 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/kosis-official-statistics/procedure.md`와 `docs/capabilities/kosis-official-statistics/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.kosis_official_statistics --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 통계 해석·정책 판단은 수동 검토
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
