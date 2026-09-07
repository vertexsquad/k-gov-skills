---
name: prosecution-legal-basis-research
description: "검찰 업무의 검찰업무 법적 근거 조사 절차. 내부 korean-law-bill-research capability를 사용하며 read-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "검찰"
    capability: korean-law-bill-research
    runtime_contract: "kgov/korean-law-bill-research/v1"
    operation: "kgov/korean-law-bill-research/search-laws/v1"
    role: primary
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 검찰업무 법적 근거 조사

- Domain: **검찰**
- 내부 capability: `korean-law-bill-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `read-only`
- Reference Skill: `korean-law-search`

## Runtime binding

- Contract: `kgov/korean-law-bill-research/v1`
- Operation: `kgov/korean-law-bill-research/search-laws/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `contract_id`, `execution_mode`, `status`, `count`, `records`, `source_receipt`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/korean-law-bill-research/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/korean-law-bill-research/search-laws/v1"
  },
  "example_result": {
    "contract_id": "kgov/korean-law-bill-research/v1",
    "count": 1,
    "execution_mode": "synthetic-fixture",
    "manual_review_required": true,
    "records": [
      {
        "effective_date": "20260101",
        "law_id": "000001",
        "law_name": "합성법률"
      }
    ],
    "source_receipt": {
      "endpoint": "https://www.law.go.kr/DRF/lawSearch.do",
      "operation_id": "kgov/korean-law-bill-research/search-laws/v1",
      "policy_id": "law-go-kr-drf-api"
    },
    "status": "fixture-validated"
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
  "module": "kgov_runtime.capabilities.korean_law_bill_research",
  "network_mode": "optional-live",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "contract_id": {
        "const": "kgov/korean-law-bill-research/v1",
        "type": "string"
      },
      "count": {
        "minimum": 0,
        "type": "integer"
      },
      "execution_mode": {
        "enum": [
          "synthetic-fixture",
          "official-live"
        ],
        "type": "string"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "records": {
        "items": {
          "additionalProperties": false,
          "properties": {
            "effective_date": {
              "type": "string"
            },
            "law_id": {
              "type": "string"
            },
            "law_name": {
              "type": "string"
            }
          },
          "required": [
            "law_name",
            "law_id",
            "effective_date"
          ],
          "type": "object"
        },
        "maxItems": 100,
        "type": "array"
      },
      "source_receipt": {
        "additionalProperties": false,
        "properties": {
          "endpoint": {
            "const": "https://www.law.go.kr/DRF/lawSearch.do",
            "type": "string"
          },
          "operation_id": {
            "const": "kgov/korean-law-bill-research/search-laws/v1",
            "type": "string"
          },
          "policy_id": {
            "const": "law-go-kr-drf-api",
            "type": "string"
          }
        },
        "required": [
          "operation_id",
          "policy_id",
          "endpoint"
        ],
        "type": "object"
      },
      "status": {
        "enum": [
          "fixture-validated",
          "records-retrieved"
        ],
        "type": "string"
      }
    },
    "required": [
      "manual_review_required",
      "contract_id",
      "execution_mode",
      "status",
      "count",
      "records",
      "source_receipt"
    ],
    "type": "object"
  },
  "schema_status": "active",
  "source_output_mode": "projected-records",
  "source_policy_ids": [
    "law-go-kr-drf-api"
  ]
}
```
<!-- kgov-runtime-binding:end -->

## 절차

1. 저장소 루트에서 `docs/capabilities/korean-law-bill-research/procedure.md`와 `docs/capabilities/korean-law-bill-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.korean_law_bill_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 법률자문·소송 제출은 수동 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
