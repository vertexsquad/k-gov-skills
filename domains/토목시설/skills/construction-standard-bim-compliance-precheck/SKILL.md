---
name: construction-standard-bim-compliance-precheck
description: "토목시설 업무의 건설기준·BIM 적합성 사전점검 절차. 내부 construction-standard-bim-compliance-precheck capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "토목시설"
    capability: construction-standard-bim-compliance-precheck
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 건설기준·BIM 적합성 사전점검

- Domain: **토목시설**
- 내부 capability: `construction-standard-bim-compliance-precheck`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 기준 버전·적용 범위·도면/모델 항목을 분리
- KCSC 근거 URL과 조회일을 보존
- 공학적 적합성·안전 판단은 기술자 승인

## 절차

1. 저장소 루트에서 `docs/capabilities/construction-standard-bim-compliance-precheck/procedure.md`와 `docs/capabilities/construction-standard-bim-compliance-precheck/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.construction_standard_bim_compliance_precheck --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 설계 적합성, 구조·시공 안전성과 준공 판단은 자격 있는 기술자와 발주기관이 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
