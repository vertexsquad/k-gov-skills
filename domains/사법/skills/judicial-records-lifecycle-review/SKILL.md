---
name: judicial-records-lifecycle-review
description: "사법 업무의 사법 기록물 생애주기 검토 절차. 내부 public-records-lifecycle-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "사법"
    capability: public-records-lifecycle-review
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 사법 기록물 생애주기 검토

- Domain: **사법**
- 내부 capability: `public-records-lifecycle-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 사건기록·보존기간·이관·폐기 대상과 기록관리 기준일을 분리
- 국가기록원(www.archives.go.kr)·기관 공식 기록관리 기준 URL·문서번호·조회일·개정 상태와 상충·미수집 근거를 구분하고 원문 개인정보를 포함하지 않음
- 보존기간 책정·이관·폐기·열람 승인과 원문 기록 처리는 기록관리 담당자 승인으로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/public-records-lifecycle-review/procedure.md`와 `docs/capabilities/public-records-lifecycle-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_records_lifecycle_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
