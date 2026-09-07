---
name: welfare-pension-support-search
description: "사회복지 업무의 복지·연금·지원정보 조회 절차. 내부 welfare-health-safety-research capability를 사용하며 read-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "사회복지"
    capability: welfare-health-safety-research
    runtime_contract: "kgov/welfare-health-safety-research/v1"
    operation: "kgov/welfare-health-safety-research/blocked-dataset-query/v1"
    role: primary
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 복지·연금·지원정보 조회

- Domain: **사회복지**
- 내부 capability: `welfare-health-safety-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `read-only`
- Reference Skill: `national-pension-workplace`, `donation-place-search`, `korean-scholarship-search`

## Runtime binding

- Contract: `kgov/welfare-health-safety-research/v1`
- Operation: `kgov/welfare-health-safety-research/blocked-dataset-query/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `contract_id`, `execution_mode`, `status`, `count`, `records`, `source_receipt`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/welfare-health-safety-research/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/welfare-health-safety-research/blocked-dataset-query/v1"
  },
  "example_result": {
    "contract_id": "kgov/welfare-health-safety-research/v1",
    "count": 0,
    "execution_mode": "synthetic-fixture",
    "manual_review_required": true,
    "records": [],
    "source_receipt": {
      "endpoint": null,
      "operation_id": "kgov/welfare-health-safety-research/blocked-dataset-query/v1",
      "policy_id": null
    },
    "status": "live-operation-blocked"
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
  "module": "kgov_runtime.capabilities.welfare_health_safety_research",
  "network_mode": "blocked",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "contract_id": {
        "const": "kgov/welfare-health-safety-research/v1",
        "type": "string"
      },
      "count": {
        "const": 0,
        "type": "integer"
      },
      "execution_mode": {
        "const": "synthetic-fixture",
        "type": "string"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "records": {
        "items": {
          "additionalProperties": false,
          "properties": {},
          "required": [],
          "type": "object"
        },
        "maxItems": 0,
        "type": "array"
      },
      "source_receipt": {
        "additionalProperties": false,
        "properties": {
          "endpoint": {
            "type": "null"
          },
          "operation_id": {
            "const": "kgov/welfare-health-safety-research/blocked-dataset-query/v1",
            "type": "string"
          },
          "policy_id": {
            "type": "null"
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
        "const": "live-operation-blocked",
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
  "source_output_mode": "none",
  "source_policy_ids": []
}
```
<!-- kgov-runtime-binding:end -->

## 절차

1. 저장소 루트에서 `docs/capabilities/welfare-health-safety-research/procedure.md`와 `docs/capabilities/welfare-health-safety-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.welfare_health_safety_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 수급자격·진단·복약 판단은 담당기관으로 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
