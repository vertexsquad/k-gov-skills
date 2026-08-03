---
name: food-drug-labeling-guidance-evidence-review
description: "식품의약 업무의 식품·의약 표시기준 근거 검토 절차. 내부 public-policy-evidence-pack capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "식품의약"
    capability: public-policy-evidence-pack
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 식품·의약 표시기준 근거 검토

- Domain: **식품의약**
- 내부 capability: `public-policy-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 제품유형·원재료·알레르기·표시항목·적용기준·시행일을 주장 단위로 분리
- 식약처·국가법령정보 공식 URL·조회일·고시 또는 안내서 버전과 상충·미수집 근거를 구분
- 표시 적합성·위반·회수·행정처분·법적 적용 판단은 식품의약 담당자 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/public-policy-evidence-pack/procedure.md`와 `docs/capabilities/public-policy-evidence-pack/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_policy_evidence_pack --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 정책·법률·통계 판단과 문서 결재·발송은 담당 공무원 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
