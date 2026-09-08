---
name: food-drug-safety-check
description: "식품의약 업무의 식품·의약 안전정보 확인 절차. 내부 welfare-health-safety-research capability를 사용하며 read-only 경계를 지킵니다."
metadata:
  domain: "식품의약"
  capability: "welfare-health-safety-research"
  runtime_contract: "kgov/welfare-health-safety-research/v1"
  operation: "kgov/welfare-health-safety-research/blocked-dataset-query/v1"
  role: "primary"
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 식품·의약 안전정보 확인

- Domain: **식품의약**
- 내부 capability: `welfare-health-safety-research`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `read-only`
- Reference Skill: `mfds-food-safety`, `mfds-drug-safety`

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

1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `docs/capabilities/welfare-health-safety-research/procedure.md`와 `docs/capabilities/welfare-health-safety-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.welfare_health_safety_research --fixture`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.
3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.
4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
5. 수급자격·진단·복약 판단은 담당기관으로 전환
6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
