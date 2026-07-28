---
name: customs-origin-document-precheck
description: "관세 업무의 원산지 증빙서류 사전점검 절차. 내부 regulated-trade-procedure-precheck capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "관세"
    capability: regulated-trade-procedure-precheck
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 원산지 증빙서류 사전점검

- Domain: **관세**
- 내부 capability: `regulated-trade-procedure-precheck`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 거래·품목·HS 코드·협정·원산지 기준·증빙서류·기준시점을 분리
- 관세청·UNI-PASS·FTA 포털 공식 URL·문서 식별자·발급 또는 조회일·유효기간과 누락·상충 근거를 구분
- 원산지 판정·특혜관세 적용·신고·제출·통관·제재 판단은 관세사와 세관 담당자 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/regulated-trade-procedure-precheck/procedure.md`와 `docs/capabilities/regulated-trade-procedure-precheck/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.regulated_trade_procedure_precheck --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 원산지 판정·특혜관세 적용·신고·제출·통관·제재 판단은 관세사와 세관 담당자가 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
