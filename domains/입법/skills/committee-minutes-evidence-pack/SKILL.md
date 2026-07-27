---
name: committee-minutes-evidence-pack
description: "입법 업무의 상임위원회 회의록 근거 팩 절차. 내부 korean-law-bill-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "입법"
    capability: korean-law-bill-research
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 상임위원회 회의록 근거 팩

- Domain: **입법**
- 내부 capability: `korean-law-bill-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 위원회·회기·안건·회의일·의결 결과를 문서 단위로 분리
- 공식 회의록·심사보고서·의안정보 URL·공개일·조회일을 보존
- 발언 취지·정치적 평가·의결 해석은 입법 담당자 검토로 이관

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
