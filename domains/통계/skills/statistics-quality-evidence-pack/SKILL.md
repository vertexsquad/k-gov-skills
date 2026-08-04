---
name: statistics-quality-evidence-pack
description: "통계 업무의 국가통계 품질 근거 팩 절차. 내부 public-policy-evidence-pack capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "통계"
    capability: public-policy-evidence-pack
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 국가통계 품질 근거 팩

- Domain: **통계**
- 내부 capability: `public-policy-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 통계표·작성주기·기준기간·모집단·방법론·품질 주장을 분리
- KOSIS·작성기관 공식 자료 URL·조회일·문서 버전을 보존하고 조사대상자 개인정보 원문을 제외
- 통계 오류·품질 수준·수정·공표 판단은 통계 담당기관 승인으로 이관

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
