---
name: disaster-records-disclosure-redaction-review
description: "재난안전 업무의 재난안전 기록공개·비식별 검토 절차. 내부 public-record-disclosure-redaction-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "재난안전"
    capability: public-record-disclosure-redaction-review
    runtime_contract: "kgov/public-record-disclosure-redaction-review/v1"
    operation: "kgov/public-record-disclosure-redaction-review/review-case/v1"
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 재난안전 기록공개·비식별 검토

- Domain: **재난안전**
- 내부 capability: `public-record-disclosure-redaction-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/public-record-disclosure-redaction-review/v1`
- Operation: `kgov/public-record-disclosure-redaction-review/review-case/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `fact_count`, `source_ref_count`, `review_type`, `receipt_assurance`, `source_output_mode`, `basic_identifier_scan`, `manual_review_reasons`, `prohibited_decisions`, `required_checks`, `source_assurance_levels`, `accepted`, `status`, `permitted_output`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/public-record-disclosure-redaction-review/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/public-record-disclosure-redaction-review/review-case/v1"
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
    "permitted_output": "disclosure-review-draft-only",
    "prohibited_decisions": [
      "final-nondisclosure-decision",
      "source-record-mutation",
      "automatic-publication"
    ],
    "receipt_assurance": "caller-declared-not-live-retrieval-proof",
    "required_checks": [
      "disclosure-ground-ledger",
      "redaction-region-review",
      "record-integrity-and-appeal-route"
    ],
    "review_type": "disclosure-redaction-review",
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
  "module": "kgov_runtime.capabilities.public_record_disclosure_redaction_review",
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
        "const": "disclosure-review-draft-only",
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
          "disclosure-redaction-review",
          "partial-disclosure-review"
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

- 재난상황·대응·피해 기록의 공개대상·보유기관·식별자를 분리하고 원문 개인정보를 입력하지 않음
- 정보공개포털(www.open.go.kr)·국가기록원(www.archives.go.kr) 공식 URL·문서번호·조회일·공개 또는 비공개 사유와 상충·미수집 근거를 보존
- 공개 여부·비공개 범위·제공 결정·피해 규모 또는 대응 우선순위 해석은 재난안전 담당기관 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/public-record-disclosure-redaction-review/procedure.md`와 `docs/capabilities/public-record-disclosure-redaction-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_record_disclosure_redaction_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 비공개 사유, 공개 범위, 원문 마스킹과 공개 결정은 정보공개 담당자가 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
