---
name: cyber-incident-response-plan-evidence-review
description: "사이버보안 업무의 사이버 침해사고 대응계획 근거 검토 절차. 내부 public-policy-evidence-pack capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "사이버보안"
    capability: public-policy-evidence-pack
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 사이버 침해사고 대응계획 근거 검토

- Domain: **사이버보안**
- 내부 capability: `public-policy-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 사고유형·시스템경계·자산·담당역할·보고경로·격리·복구·로그보존 항목을 분리
- 공식 자료로 입력된 KISA·국가 또는 기관 보안기준 URL·문서버전·시행일·조회일과 상충·미수집 근거를 구분
- 사고등급·차단·격리·포렌식·외부신고·현장대응 실행은 보안책임자와 관할기관 검토로 이관

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
