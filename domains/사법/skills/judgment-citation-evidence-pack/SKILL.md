---
name: judgment-citation-evidence-pack
description: "사법 업무의 판결 인용 근거 팩 절차. 내부 korean-legal-citation-verification capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  domain: "사법"
  capability: "korean-legal-citation-verification"
  runtime_contract: "kgov/korean-legal-citation-verification/v1"
  operation: "kgov/korean-legal-citation-verification/verify-citations/v1"
  role: "additional"
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 판결 인용 근거 팩

- Domain: **사법**
- 내부 capability: `korean-legal-citation-verification`
- 실행 상태: `fixture-verified` / live smoke `blocked`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/korean-legal-citation-verification/v1`
- Operation: `kgov/korean-legal-citation-verification/verify-citations/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `as_of_date`, `permitted_output`, `execution_mode`, `verification_assurance`, `schema_valid`, `jurisdiction`, `admission_passed`, `verified_count`, `blocked_count`, `citations`, `source_receipts`, `verification_mode`, `fixture_contract_passed`, `matched_count`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/korean-legal-citation-verification/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/korean-legal-citation-verification/verify-citations/v1"
  },
  "example_result": {
    "admission_passed": false,
    "as_of_date": "2026-07-20",
    "blocked_count": 0,
    "citations": [
      {
        "citation_id": "LAW1",
        "effective_date": "2026-01-01",
        "kind": "statute",
        "mismatched_fields": [],
        "status": "synthetic-fixture-match"
      },
      {
        "citation_id": "PREC1",
        "kind": "precedent",
        "mismatched_fields": [],
        "quote_source_field": "판시사항",
        "status": "synthetic-fixture-match"
      }
    ],
    "execution_mode": "synthetic-fixture",
    "fixture_contract_passed": true,
    "jurisdiction": "KR",
    "manual_review_required": true,
    "matched_count": 2,
    "permitted_output": "fixture-validation-only",
    "schema_valid": true,
    "source_receipts": [
      {
        "call_kind": "law-search",
        "citation_id": "LAW1",
        "endpoint": "https://www.law.go.kr/DRF/lawSearch.do",
        "page": 1,
        "source_receipt": null
      },
      {
        "call_kind": "law-detail",
        "citation_id": "LAW1",
        "endpoint": "https://www.law.go.kr/DRF/lawService.do",
        "page": null,
        "source_receipt": null
      },
      {
        "call_kind": "precedent-detail",
        "citation_id": "PREC1",
        "endpoint": "https://www.law.go.kr/DRF/lawService.do",
        "page": null,
        "source_receipt": null
      }
    ],
    "verification_assurance": "Synthetic matching contract only; no live official record was retrieved.",
    "verification_mode": "synthetic-fixture",
    "verified_count": 2
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
  "module": "kgov_runtime.capabilities.korean_legal_citation_verification",
  "network_mode": "optional-live",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "admission_passed": {
        "type": "boolean"
      },
      "as_of_date": {
        "format": "date",
        "type": "string"
      },
      "blocked_count": {
        "minimum": 0,
        "type": "integer"
      },
      "citations": {
        "items": {
          "additionalProperties": false,
          "properties": {
            "citation_id": {
              "type": "string"
            },
            "effective_date": {
              "format": "date",
              "type": "string"
            },
            "kind": {
              "enum": [
                "statute",
                "precedent"
              ],
              "type": "string"
            },
            "mismatched_fields": {
              "items": {
                "enum": [
                  "law_name",
                  "law_id",
                  "quoted_text",
                  "serial_number",
                  "case_number",
                  "court",
                  "decision_date",
                  "decision_date_after_as_of_date",
                  "official_source"
                ],
                "type": "string"
              },
              "type": "array"
            },
            "quote_source_field": {
              "enum": [
                "판시사항",
                "판결요지",
                "판례내용"
              ],
              "type": "string"
            },
            "source_url": {
              "type": "string"
            },
            "status": {
              "enum": [
                "mismatch-blocked",
                "verified-official-live-match",
                "synthetic-fixture-match",
                "official-source-not-found",
                "ambiguous-candidates-manual-selection-required"
              ],
              "type": "string"
            },
            "verified_citation": {
              "type": "string"
            }
          },
          "required": [
            "citation_id",
            "kind",
            "mismatched_fields",
            "status"
          ],
          "type": "object"
        },
        "type": "array"
      },
      "execution_mode": {
        "enum": [
          "official-live",
          "synthetic-fixture"
        ],
        "type": "string"
      },
      "fixture_contract_passed": {
        "type": "boolean"
      },
      "jurisdiction": {
        "const": "KR",
        "type": "string"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "matched_count": {
        "minimum": 0,
        "type": "integer"
      },
      "permitted_output": {
        "enum": [
          "verified-citations-draft",
          "no-citations-admitted",
          "fixture-validation-only"
        ],
        "type": "string"
      },
      "schema_valid": {
        "const": true,
        "type": "boolean"
      },
      "source_receipts": {
        "items": {
          "additionalProperties": false,
          "properties": {
            "call_kind": {
              "enum": [
                "law-search",
                "law-detail",
                "precedent-search",
                "precedent-detail"
              ],
              "type": "string"
            },
            "citation_id": {
              "type": [
                "string",
                "null"
              ]
            },
            "endpoint": {
              "enum": [
                "https://www.law.go.kr/DRF/lawSearch.do",
                "https://www.law.go.kr/DRF/lawService.do"
              ],
              "type": "string"
            },
            "page": {
              "minimum": 1,
              "type": [
                "integer",
                "null"
              ]
            },
            "source_receipt": {
              "additionalProperties": false,
              "properties": {
                "operation_id": {
                  "const": "kgov/korean-legal-citation-verification/verify-citations/v1",
                  "type": "string"
                },
                "outcome": {
                  "const": "allowed",
                  "type": "string"
                },
                "policy_digest": {
                  "format": "sha256",
                  "type": "string"
                },
                "policy_id": {
                  "enum": [
                    "law-go-kr-drf-api"
                  ],
                  "type": "string"
                },
                "policy_revision": {
                  "minimum": 1,
                  "type": "integer"
                }
              },
              "required": [
                "operation_id",
                "policy_id",
                "policy_revision",
                "policy_digest",
                "outcome"
              ],
              "type": [
                "object",
                "null"
              ]
            }
          },
          "required": [
            "call_kind",
            "endpoint",
            "citation_id",
            "page",
            "source_receipt"
          ],
          "type": "object"
        },
        "type": "array"
      },
      "verification_assurance": {
        "type": "string"
      },
      "verification_mode": {
        "const": "synthetic-fixture",
        "type": "string"
      },
      "verified_count": {
        "minimum": 0,
        "type": "integer"
      }
    },
    "required": [
      "manual_review_required",
      "as_of_date",
      "permitted_output",
      "execution_mode",
      "verification_assurance",
      "schema_valid",
      "jurisdiction",
      "admission_passed",
      "verified_count",
      "blocked_count",
      "citations",
      "source_receipts"
    ],
    "type": "object"
  },
  "schema_status": "active",
  "source_output_mode": "link-only",
  "source_policy_ids": [
    "law-go-kr-drf-api"
  ]
}
```
<!-- kgov-runtime-binding:end -->

## 업무별 추가 체크

- 법원·사건번호·선고일·판례 원문 식별자와 정확한 인용 위치를 분리
- 국가법령정보 공식 원문 URL·조회일·적용 법령 버전과 불일치·복수 후보를 보존
- 법률적 효력·사안 적용·소송 제출 여부는 법무 담당자 최종 검토로 이관

## 절차

1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `docs/capabilities/korean-legal-citation-verification/procedure.md`와 `docs/capabilities/korean-legal-citation-verification/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.korean_legal_citation_verification --fixture`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.
3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.
4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
5. 법률적 판단·최종 인용·결재·발송은 담당 공무원 또는 법무 검토 승인
6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
