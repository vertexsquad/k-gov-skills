---
name: healthcare-public-notice-multilingual-review
description: "보건의료 업무의 보건의료 공지 다국어 검토 절차. 내부 official-notice-multilingual-translation-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "보건의료"
    capability: official-notice-multilingual-translation-review
    runtime_contract: "kgov/official-notice-multilingual-translation-review/v1"
    operation: "kgov/official-notice-multilingual-translation-review/review-case/v1"
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 보건의료 공지 다국어 검토

- Domain: **보건의료**
- 내부 capability: `official-notice-multilingual-translation-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/official-notice-multilingual-translation-review/v1`
- Operation: `kgov/official-notice-multilingual-translation-review/review-case/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `fact_count`, `source_ref_count`, `review_type`, `receipt_assurance`, `source_output_mode`, `basic_identifier_scan`, `manual_review_reasons`, `prohibited_decisions`, `required_checks`, `source_assurance_levels`, `accepted`, `status`, `permitted_output`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/official-notice-multilingual-translation-review/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/official-notice-multilingual-translation-review/review-case/v1"
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
    "permitted_output": "translation-review-draft-only",
    "prohibited_decisions": [
      "automatic-publication",
      "legal-meaning-certification",
      "medical-meaning-certification"
    ],
    "receipt_assurance": "caller-declared-not-live-retrieval-proof",
    "required_checks": [
      "meaning-and-official-terms",
      "numbers-dates-contact-consistency",
      "language-specialist-review-route"
    ],
    "review_type": "multilingual-translation-review",
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
  "module": "kgov_runtime.capabilities.official_notice_multilingual_translation_review",
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
        "const": "translation-review-draft-only",
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
          "multilingual-translation-review",
          "terminology-consistency-review"
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

- 공지 대상·언어·시행일·의료 또는 행정 용어·행동요령을 문장 단위로 분리
- 공식 원문 URL·공표일·조회일·문서 버전과 번역상 미확정 용어를 보존
- 의학적 의미·공식 용어·언어별 감수·게시·발송은 보건의료 담당자와 전문 감수자 승인으로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/official-notice-multilingual-translation-review/procedure.md`와 `docs/capabilities/official-notice-multilingual-translation-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.official_notice_multilingual_translation_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 공식 용어, 법적 의미, 언어별 감수와 게시·발송은 기관 담당자와 전문 감수자가 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
