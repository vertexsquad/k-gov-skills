---
name: judicial-records-lifecycle-review
description: "사법 업무의 사법 기록물 생애주기 검토 절차. 내부 public-records-lifecycle-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  domain: "사법"
  capability: "public-records-lifecycle-review"
  runtime_contract: "kgov/public-records-lifecycle-review/v1"
  operation: "kgov/public-records-lifecycle-review/review-case/v1"
  role: "additional"
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 사법 기록물 생애주기 검토

- Domain: **사법**
- 내부 capability: `public-records-lifecycle-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/public-records-lifecycle-review/v1`
- Operation: `kgov/public-records-lifecycle-review/review-case/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `fact_count`, `source_ref_count`, `review_type`, `receipt_assurance`, `source_output_mode`, `basic_identifier_scan`, `manual_review_reasons`, `prohibited_decisions`, `required_checks`, `source_assurance_levels`, `accepted`, `status`, `permitted_output`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/public-records-lifecycle-review/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/public-records-lifecycle-review/review-case/v1"
  },
  "example_result": {
    "accepted": true,
    "basic_identifier_scan": "no-match-not-proof-of-redaction",
    "fact_count": 1,
    "manual_review_reasons": [
      "caller-declared-source",
      "license-unverified",
      "redistribution-link-only"
    ],
    "manual_review_required": true,
    "permitted_output": "records-lifecycle-review-draft-only",
    "prohibited_decisions": [
      "final-retention-period",
      "source-record-mutation",
      "automatic-transfer-or-disposal"
    ],
    "receipt_assurance": "caller-declared-not-live-retrieval-proof",
    "required_checks": [
      "records-series-and-business-function",
      "retention-basis-and-trigger",
      "transfer-disposal-and-approval-gate"
    ],
    "review_type": "retention-schedule-review",
    "source_assurance_levels": [
      "caller-declared"
    ],
    "source_output_mode": "link-only",
    "source_ref_count": 1,
    "status": "admitted-pending-human-review"
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
  "module": "kgov_runtime.capabilities.public_records_lifecycle_review",
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
      "fact_count": {
        "minimum": 0,
        "type": "integer"
      },
      "manual_review_reasons": {
        "items": {
          "enum": [
            "caller-declared-source",
            "policy-outcome-manual-review",
            "license-unverified",
            "redistribution-link-only"
          ],
          "type": "string"
        },
        "type": "array"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "permitted_output": {
        "const": "records-lifecycle-review-draft-only",
        "type": "string"
      },
      "prohibited_decisions": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "receipt_assurance": {
        "enum": [
          "policy-matched-not-cryptographic-authenticity-proof",
          "caller-declared-not-live-retrieval-proof"
        ],
        "type": "string"
      },
      "required_checks": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "review_type": {
        "enum": [
          "retention-schedule-review",
          "transfer-disposal-precheck"
        ],
        "type": "string"
      },
      "source_assurance_levels": {
        "items": {
          "enum": [
            "caller-declared",
            "policy-verified-not-authenticity-proof"
          ],
          "type": "string"
        },
        "type": "array"
      },
      "source_output_mode": {
        "enum": [
          "projected-records",
          "link-only"
        ],
        "type": "string"
      },
      "source_ref_count": {
        "minimum": 0,
        "type": "integer"
      },
      "status": {
        "const": "admitted-pending-human-review",
        "type": "string"
      }
    },
    "required": [
      "manual_review_required",
      "fact_count",
      "source_ref_count",
      "review_type",
      "receipt_assurance",
      "source_output_mode",
      "basic_identifier_scan",
      "manual_review_reasons",
      "prohibited_decisions",
      "required_checks",
      "source_assurance_levels",
      "accepted",
      "status",
      "permitted_output"
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

- 사건기록·보존기간·이관·폐기 대상과 기록관리 기준일을 분리
- 국가기록원(www.archives.go.kr)·기관 공식 기록관리 기준 URL·문서번호·조회일·개정 상태와 상충·미수집 근거를 구분하고 원문 개인정보를 포함하지 않음
- 보존기간 책정·이관·폐기·열람 승인과 원문 기록 처리는 기록관리 담당자 승인으로 이관

## 절차

1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `docs/capabilities/public-records-lifecycle-review/procedure.md`와 `docs/capabilities/public-records-lifecycle-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_records_lifecycle_review --fixture`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.
3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.
4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
5. 보존기간 확정·평가·이관·폐기·원본 변경은 기록물관리 담당자 승인
6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
