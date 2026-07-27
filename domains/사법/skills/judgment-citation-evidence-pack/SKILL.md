---
name: judgment-citation-evidence-pack
description: "사법 업무의 판결 인용 근거 팩 절차. 내부 korean-legal-citation-verification capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "사법"
    capability: korean-legal-citation-verification
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 판결 인용 근거 팩

- Domain: **사법**
- 내부 capability: `korean-legal-citation-verification`
- 실행 상태: `live-verified` / live smoke `passed`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 법원·사건번호·선고일·판례 원문 식별자와 정확한 인용 위치를 분리
- 국가법령정보 공식 원문 URL·조회일·적용 법령 버전과 불일치·복수 후보를 보존
- 법률적 효력·사안 적용·소송 제출 여부는 법무 담당자 최종 검토로 이관

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
