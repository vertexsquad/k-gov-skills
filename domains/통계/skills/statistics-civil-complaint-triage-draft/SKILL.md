---
name: statistics-civil-complaint-triage-draft
description: "통계 업무의 국가통계 민원 분류·답변 초안 절차. 내부 civil-complaint-triage-draft capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  domain: "통계"
  capability: "civil-complaint-triage-draft"
  runtime_contract: "kgov/civil-complaint-triage-draft/v1"
  operation: "kgov/civil-complaint-triage-draft/admit-draft/v1"
  role: "additional"
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 국가통계 민원 분류·답변 초안

- Domain: **통계**
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

- 통계표·지표·기간·단위·요청사항·오류 주장·처리기한을 비식별 상태로 분리
- 민원인 개인정보 원문을 저장하지 않고 KOSIS·작성기관 공식 URL·조회일·메타데이터를 보존
- 통계 오류 확정·수정·공표·개별 답변 발송은 통계 담당기관 승인으로 이관

## 절차

1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `docs/capabilities/civil-complaint-triage-draft/procedure.md`와 `docs/capabilities/civil-complaint-triage-draft/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.civil_complaint_triage_draft --fixture`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.
3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.
4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
5. 소관 확정·처분 판단·답변 발송은 담당 공무원 승인
6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
