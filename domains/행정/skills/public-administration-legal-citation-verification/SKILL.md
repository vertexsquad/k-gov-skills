---
name: public-administration-legal-citation-verification
description: "행정 업무의 법령 조문·판례 인용 검증 절차. 내부 korean-legal-citation-verification capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "행정"
    capability: korean-legal-citation-verification
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 법령 조문·판례 인용 검증

- Domain: **행정**
- 내부 capability: `korean-legal-citation-verification`
- 실행 상태: `live-verified` / live smoke `passed`
- 실행 경계: `draft-only`
- Reference Skill: `korean-law-search`, `legalize-kr`, `legal-kr`

## 절차

1. 저장소 루트에서 `docs/capabilities/korean-legal-citation-verification/procedure.md`와 `docs/capabilities/korean-legal-citation-verification/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.korean_legal_citation_verification --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 법률적 판단·최종 인용·결재·발송은 담당 공무원 또는 법무 검토 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
