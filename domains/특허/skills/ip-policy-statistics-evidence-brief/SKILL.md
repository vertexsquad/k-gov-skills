---
name: ip-policy-statistics-evidence-brief
description: "특허 업무의 지식재산 정책통계 근거 브리프 절차. 내부 public-policy-evidence-pack capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "특허"
    capability: public-policy-evidence-pack
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 지식재산 정책통계 근거 브리프

- Domain: **특허**
- 내부 capability: `public-policy-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 권리유형·정책 또는 사업·기준기간·출원인 범주·지역·건수·분모·단위를 분리
- 공식 자료로 입력된 특허청·KIPRIS URL·보고서 또는 통계표 식별자·공표일·조회일·개정 상태와 결측을 구분
- 인과관계·정책효과·산업경쟁력·지원 또는 규제 우선순위 판단은 지식재산 담당자 검토로 이관

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
