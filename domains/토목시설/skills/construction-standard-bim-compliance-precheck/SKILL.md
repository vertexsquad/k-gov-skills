---
name: construction-standard-bim-compliance-precheck
description: "토목시설 업무의 건설기준·BIM 적합성 사전점검 절차. 내부 construction-standard-bim-compliance-precheck capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "토목시설"
    capability: construction-standard-bim-compliance-precheck
    runtime_contract: "kgov/construction-standard-bim-compliance-precheck/v1"
    operation: "kgov/construction-standard-bim-compliance-precheck/review-case/v1"
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 건설기준·BIM 적합성 사전점검

- Domain: **토목시설**
- 내부 capability: `construction-standard-bim-compliance-precheck`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/construction-standard-bim-compliance-precheck/v1`
- Operation: `kgov/construction-standard-bim-compliance-precheck/review-case/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `fact_count`, `source_ref_count`, `review_type`, `receipt_assurance`, `source_output_mode`, `basic_identifier_scan`, `manual_review_reasons`, `prohibited_decisions`, `required_checks`, `source_assurance_levels`, `accepted`, `status`, `permitted_output`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/construction-standard-bim-compliance-precheck/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/construction-standard-bim-compliance-precheck/review-case/v1"
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
    "permitted_output": "engineering-precheck-draft-only",
    "prohibited_decisions": [
      "engineering-approval",
      "structural-safety-decision",
      "completion-certification"
    ],
    "receipt_assurance": "caller-declared-not-live-retrieval-proof",
    "required_checks": [
      "standard-version-and-scope",
      "model-drawing-item-ledger",
      "deviation-and-evidence-gap"
    ],
    "review_type": "construction-standard-precheck",
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
  "module": "kgov_runtime.capabilities.construction_standard_bim_compliance_precheck",
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
        "const": "engineering-precheck-draft-only",
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
          "bim-precheck",
          "construction-standard-precheck"
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

- 기준 버전·적용 범위·도면/모델 항목을 분리
- KCSC 근거 URL과 조회일을 보존
- 공학적 적합성·안전 판단은 기술자 승인

## 절차

1. 저장소 루트에서 `docs/capabilities/construction-standard-bim-compliance-precheck/procedure.md`와 `docs/capabilities/construction-standard-bim-compliance-precheck/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.construction_standard_bim_compliance_precheck --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 설계 적합성, 구조·시공 안전성과 준공 판단은 자격 있는 기술자와 발주기관이 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
