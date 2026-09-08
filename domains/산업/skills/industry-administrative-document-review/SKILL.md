---
name: industry-administrative-document-review
description: "산업 업무의 산업 행정문서 검토 절차. 내부 administrative-document-draft-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  domain: "산업"
  capability: "administrative-document-draft-review"
  runtime_contract: "kgov/administrative-document-draft-review/v1"
  operation: "kgov/administrative-document-draft-review/review-draft/v1"
  role: "additional"
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 산업 행정문서 검토

- Domain: **산업**
- 내부 capability: `administrative-document-draft-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/administrative-document-draft-review/v1`
- Operation: `kgov/administrative-document-draft-review/review-draft/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `accepted`, `permitted_output`, `review_checks`, `document_type`, `basic_identifier_scan`, `body_characters`, `purpose_characters`, `source_ref_count`, `title_characters`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/administrative-document-draft-review/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/administrative-document-draft-review/review-draft/v1"
  },
  "example_result": {
    "accepted": true,
    "basic_identifier_scan": "no-match-not-proof-of-redaction",
    "body_characters": 36,
    "document_type": "report",
    "manual_review_required": true,
    "permitted_output": "draft-review-only",
    "purpose_characters": 18,
    "review_checks": {
      "institution_template": "required",
      "legal_authority": "required",
      "numeric_claims": "required",
      "privacy": "manual-confirmation-required",
      "source_traceability": "provided-review-required"
    },
    "source_ref_count": 1,
    "title_characters": 14
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
  "module": "kgov_runtime.capabilities.administrative_document_draft_review",
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
      "body_characters": {
        "minimum": 0,
        "type": "integer"
      },
      "document_type": {
        "enum": [
          "audit-response",
          "council-agenda",
          "education-notice",
          "meeting-material",
          "official-letter",
          "press-release",
          "report"
        ],
        "type": "string"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "permitted_output": {
        "const": "draft-review-only",
        "type": "string"
      },
      "purpose_characters": {
        "minimum": 0,
        "type": "integer"
      },
      "review_checks": {
        "additionalProperties": false,
        "properties": {
          "institution_template": {
            "const": "required",
            "type": "string"
          },
          "legal_authority": {
            "enum": [
              "required",
              "not-detected"
            ],
            "type": "string"
          },
          "numeric_claims": {
            "enum": [
              "required",
              "not-detected"
            ],
            "type": "string"
          },
          "privacy": {
            "const": "manual-confirmation-required",
            "type": "string"
          },
          "source_traceability": {
            "enum": [
              "provided-review-required",
              "required"
            ],
            "type": "string"
          }
        },
        "required": [
          "institution_template",
          "legal_authority",
          "numeric_claims",
          "privacy",
          "source_traceability"
        ],
        "type": "object"
      },
      "source_ref_count": {
        "minimum": 0,
        "type": "integer"
      },
      "title_characters": {
        "minimum": 0,
        "type": "integer"
      }
    },
    "required": [
      "manual_review_required",
      "accepted",
      "permitted_output",
      "review_checks",
      "document_type",
      "basic_identifier_scan",
      "body_characters",
      "purpose_characters",
      "source_ref_count",
      "title_characters"
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

- 산업 대상·적용 기준·시행일·문서 상태·증빙을 분리
- 공식 법령·지침·문서 URL과 조회일·버전을 보존
- 산업 적합성·승인·제출·집행 판단은 담당자 검토로 이관

## 절차

1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `docs/capabilities/administrative-document-draft-review/procedure.md`와 `docs/capabilities/administrative-document-draft-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.administrative_document_draft_review --fixture`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.
3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.
4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
5. 기관 서식·근거 확정·결재·발송은 담당 공무원 승인
6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 실제 로컬 입력

저장소 루트에서 `python3 -m kgov_runtime.capabilities.administrative_document_draft_review PATH`를 실행합니다. `PATH`는 사용자가 제공하고 읽기를 승인한 로컬 파일 경로로 바꾸고, 공백이 있으면 따옴표로 감쌉니다. `--fixture`와 함께 쓰지 않습니다. 입력 형식과 제한은 위 procedure를 따릅니다.
위 Runtime binding의 `fixed_input`과 예시는 합성 fixture 전용 계약이며, 실제 파일 검사 결과가 아닙니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
