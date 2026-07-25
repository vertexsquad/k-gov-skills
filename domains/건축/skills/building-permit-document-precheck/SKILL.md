---
name: building-permit-document-precheck
description: "건축 업무의 건축 인허가 서류 사전점검 절차. 내부 building-permit-document-precheck capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "건축"
    capability: building-permit-document-precheck
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 건축 인허가 서류 사전점검

- Domain: **건축**
- 내부 capability: `building-permit-document-precheck`
- 실행 상태: `fixture-verified` / live smoke `blocked`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 건축물·행위·지역에 따른 서류 후보를 분리
- 세움터 도달 여부를 실제 민원 기능 성공으로 간주하지 않음
- 허가요건과 실제 제출은 건축사·허가권자 확인

## 절차

1. 저장소 루트에서 `docs/capabilities/building-permit-document-precheck/procedure.md`와 `docs/capabilities/building-permit-document-precheck/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.building_permit_document_precheck --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 허가 대상, 법정 요건, 도면 적합성과 실제 신청·제출은 건축사와 허가권자가 확인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
