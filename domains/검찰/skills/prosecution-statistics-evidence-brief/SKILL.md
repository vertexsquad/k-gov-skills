---
name: prosecution-statistics-evidence-brief
description: "검찰 업무의 검찰 통계 근거 브리프 절차. 내부 kosis-official-statistics capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "검찰"
    capability: kosis-official-statistics
    runtime_contract: "kgov/kosis-official-statistics/v1"
    operation: "kgov/kosis-official-statistics/query-statistics/v1"
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 검찰 통계 근거 브리프

- Domain: **검찰**
- 내부 capability: `kosis-official-statistics`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/kosis-official-statistics/v1`
- Operation: `kgov/kosis-official-statistics/query-statistics/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `contract_id`, `execution_mode`, `status`, `count`, `records`, `source_receipt`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/kosis-official-statistics/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/kosis-official-statistics/query-statistics/v1"
  },
  "example_result": {
    "contract_id": "kgov/kosis-official-statistics/v1",
    "count": 1,
    "execution_mode": "synthetic-fixture",
    "manual_review_required": true,
    "records": [
      {
        "category": "전국",
        "item": "인구",
        "period": "2025",
        "table_name": "합성 인구 통계",
        "value": "100"
      }
    ],
    "source_receipt": {
      "endpoint": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
      "operation_id": "kgov/kosis-official-statistics/query-statistics/v1",
      "policy_id": "kosis-statistics-api"
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
  "module": "kgov_runtime.capabilities.kosis_official_statistics",
  "network_mode": "optional-live",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "contract_id": {
        "const": "kgov/kosis-official-statistics/v1",
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
            "category": {
              "type": "string"
            },
            "item": {
              "type": "string"
            },
            "period": {
              "type": "string"
            },
            "table_name": {
              "type": "string"
            },
            "value": {
              "type": "string"
            }
          },
          "required": [
            "table_name",
            "period",
            "category",
            "item",
            "value"
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
            "const": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            "type": "string"
          },
          "operation_id": {
            "const": "kgov/kosis-official-statistics/query-statistics/v1",
            "type": "string"
          },
          "policy_id": {
            "const": "kosis-statistics-api",
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
    "kosis-statistics-api"
  ]
}
```
<!-- kgov-runtime-binding:end -->

## 업무별 추가 체크

- 검찰 지표·기준기간·분모·단위를 분리
- 공식 통계표 코드·작성기관·공표일·조회일·개정 상태를 보존
- 검찰 추세·인과관계·정책효과 판단은 담당기관 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/kosis-official-statistics/procedure.md`와 `docs/capabilities/kosis-official-statistics/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.kosis_official_statistics --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 통계 해석·정책 판단은 수동 검토
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
