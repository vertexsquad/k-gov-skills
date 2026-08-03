---
name: welfare-administrative-document-draft-review
description: "사회복지 업무의 복지행정 문서 초안 검토 절차. 내부 administrative-document-draft-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "사회복지"
    capability: administrative-document-draft-review
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 복지행정 문서 초안 검토

- Domain: **사회복지**
- 내부 capability: `administrative-document-draft-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 복지사업 안내·검토보고·회의자료별 목적·대상·근거·미확정 항목을 분리
- 신청인 개인정보 원문을 제외하고 공식 법령·사업안내 URL·조회일·문서 버전을 보존
- 수급자격·지급액·기관 서식 확정·결재·발송은 복지 담당자 승인으로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/administrative-document-draft-review/procedure.md`와 `docs/capabilities/administrative-document-draft-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.administrative_document_draft_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 기관 서식·근거 확정·결재·발송은 담당 공무원 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
