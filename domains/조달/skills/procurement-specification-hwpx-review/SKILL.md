---
name: procurement-specification-hwpx-review
description: "조달 업무의 조달 규격서 HWPX 검토 절차. 내부 public-document-hwpx capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "조달"
    capability: public-document-hwpx
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 조달 규격서 HWPX 검토

- Domain: **조달**
- 내부 capability: `public-document-hwpx`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- HWPX를 읽기 전용으로 추출
- 누락 항목·특정규격·검수조건 후보를 표시
- 원본 수정·공고·계약은 조달 담당자 승인

## 절차

1. 저장소 루트에서 `docs/capabilities/public-document-hwpx/procedure.md`와 `docs/capabilities/public-document-hwpx/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_document_hwpx --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 원본 변경·제출·결재는 별도 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
