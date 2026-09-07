---
name: ai-product-procurement-readiness-check
description: "조달 업무의 AI 제품 조달 준비도 점검 절차. 내부 public-procurement-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "조달"
    capability: public-procurement-research
    runtime_contract: "kgov/public-procurement-research/v1"
    operation: "kgov/public-procurement-research/query-order-plans/v1"
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# AI 제품 조달 준비도 점검

- Domain: **조달**
- 내부 capability: `public-procurement-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/public-procurement-research/v1`
- Operation: `kgov/public-procurement-research/query-order-plans/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `contract_id`, `execution_mode`, `status`, `count`, `records`, `source_receipt`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/public-procurement-research/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/public-procurement-research/query-order-plans/v1"
  },
  "example_result": {
    "contract_id": "kgov/public-procurement-research/v1",
    "count": 1,
    "execution_mode": "synthetic-fixture",
    "manual_review_required": true,
    "records": [
      {
        "business_name": "합성 정보화 사업",
        "ordering_agency": "합성기관",
        "plan_number": "PLAN-001",
        "planned_amount": "1000000",
        "planned_date": "20260101"
      }
    ],
    "source_receipt": {
      "endpoint": "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService",
      "operation_id": "kgov/public-procurement-research/query-order-plans/v1",
      "policy_id": "data-go-kr-order-plan-api"
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
  "module": "kgov_runtime.capabilities.public_procurement_research",
  "network_mode": "optional-live",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "contract_id": {
        "const": "kgov/public-procurement-research/v1",
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
            "business_name": {
              "type": "string"
            },
            "ordering_agency": {
              "type": "string"
            },
            "plan_number": {
              "type": "string"
            },
            "planned_amount": {
              "type": "string"
            },
            "planned_date": {
              "type": "string"
            }
          },
          "required": [
            "plan_number",
            "business_name",
            "ordering_agency",
            "planned_amount",
            "planned_date"
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
            "const": "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService",
            "type": "string"
          },
          "operation_id": {
            "const": "kgov/public-procurement-research/query-order-plans/v1",
            "type": "string"
          },
          "policy_id": {
            "const": "data-go-kr-order-plan-api",
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
    "data-go-kr-order-plan-api"
  ]
}
```
<!-- kgov-runtime-binding:end -->

## 업무별 추가 체크

- MAS·공고·자격·납품조건을 공식 근거에서 확인
- AI 기능·데이터 처리·성능검증 요구사항을 분리
- 투찰·계약·인증서 사용을 수행하지 않음

## 절차

1. 저장소 루트에서 `docs/capabilities/public-procurement-research/procedure.md`와 `docs/capabilities/public-procurement-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_procurement_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 투찰·계약·인증서 사용은 수동 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
