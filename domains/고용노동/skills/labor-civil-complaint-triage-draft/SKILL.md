---
name: labor-civil-complaint-triage-draft
description: "고용노동 업무의 고용노동 민원 분류·답변 초안 절차. 내부 civil-complaint-triage-draft capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "고용노동"
    capability: civil-complaint-triage-draft
    runtime_contract: "kgov/civil-complaint-triage-draft/v1"
    operation: "kgov/civil-complaint-triage-draft/admit-draft/v1"
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 고용노동 민원 분류·답변 초안

- Domain: **고용노동**
- 내부 capability: `civil-complaint-triage-draft`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/civil-complaint-triage-draft/v1`
- Operation: `kgov/civil-complaint-triage-draft/admit-draft/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `accepted`, `permitted_output`, `basic_identifier_scan`, `input_characters`, `title_characters`, `workflow_steps`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/civil-complaint-triage-draft/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/civil-complaint-triage-draft/admit-draft/v1"
  },
  "example_result": {
    "accepted": true,
    "basic_identifier_scan": "no-match-not-proof-of-redaction",
    "input_characters": 25,
    "manual_review_required": true,
    "permitted_output": "draft-only",
    "title_characters": 11,
    "workflow_steps": [
      "민원 요약과 요청사항 분리",
      "관련 법령·공식 안내·소관 후보 확인",
      "답변 초안과 불확실성 작성",
      "담당 공무원 검토 후 발송 여부 결정"
    ]
  },
  "exit_codes": {
    "input_error": 2,
    "policy_blocked": 3,
    "review_blocked": 1,
    "success": 0,
    "upstream_error": 4
  },
  "fixture_argv": [
    "--fixture"
  ],
  "input_schema": {
    "additionalProperties": false,
    "properties": {
      "argv": {
        "items": {
          "type": "string"
        },
        "type": "array"
      }
    },
    "required": [
      "argv"
    ],
    "type": "object"
  },
  "module": "kgov_runtime.capabilities.civil_complaint_triage_draft",
  "network_mode": "none",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "accepted": {
        "const": true,
        "type": "boolean"
      },
      "basic_identifier_scan": {
        "const": "no-match-not-proof-of-redaction",
        "type": "string"
      },
      "input_characters": {
        "minimum": 0,
        "type": "integer"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "permitted_output": {
        "const": "draft-only",
        "type": "string"
      },
      "title_characters": {
        "minimum": 0,
        "type": "integer"
      },
      "workflow_steps": {
        "items": {
          "type": "string"
        },
        "type": "array"
      }
    },
    "required": [
      "manual_review_required",
      "accepted",
      "permitted_output",
      "basic_identifier_scan",
      "input_characters",
      "title_characters",
      "workflow_steps"
    ],
    "type": "object"
  },
  "schema_status": "active",
  "source_output_mode": "none",
  "source_policy_ids": []
}
```
<!-- kgov-runtime-binding:end -->

## 업무별 추가 체크

- 임금·산재·근로관계 요청사항을 분리
- 위법·근로자성·산재 인정 여부를 자동 판단하지 않음
- 법적 판단과 답변 발송은 담당기관 승인

## 절차

1. 저장소 루트에서 `docs/capabilities/civil-complaint-triage-draft/procedure.md`와 `docs/capabilities/civil-complaint-triage-draft/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.civil_complaint_triage_draft --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 소관 확정·처분 판단·답변 발송은 담당 공무원 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
