---
name: food-drug-recall-evidence-brief
description: "식품의약 업무의 식품·의약품 회수 근거 브리프 절차. 내부 welfare-health-safety-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "식품의약"
    capability: welfare-health-safety-research
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 식품·의약품 회수 근거 브리프

- Domain: **식품의약**
- 내부 capability: `welfare-health-safety-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 제품명·업체·품목 식별자·회수 등급·대상 제조번호·유통기한을 분리
- 식약처·공공데이터 응답의 공식 endpoint·조회일·공표일·정정 상태와 미확인 항목을 보존
- 복약·섭취 중단·행정처분·현장 회수 집행은 식약처·전문가·담당자 확인으로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/welfare-health-safety-research/procedure.md`와 `docs/capabilities/welfare-health-safety-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.welfare_health_safety_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 수급자격·진단·복약 판단은 담당기관으로 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
