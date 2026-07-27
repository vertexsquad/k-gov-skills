---
name: bill-comparison-impact-brief
description: "입법 업무의 법안 비교·영향 근거 브리프 절차. 내부 korean-law-bill-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "입법"
    capability: korean-law-bill-research
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 법안 비교·영향 근거 브리프

- Domain: **입법**
- 내부 capability: `korean-law-bill-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 법안·대안·수정안별 의안번호·기준일·처리단계·조문 차이를 분리
- 국가법령정보·국회 공개정보의 공식 URL·조회일·문서 버전을 보존
- 법적 효력·정책 영향·채택 여부 판단은 입법·법무 담당자 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/korean-law-bill-research/procedure.md`와 `docs/capabilities/korean-law-bill-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.korean_law_bill_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 법률자문·소송 제출은 수동 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
