---
name: official-country-brief
description: "외교 업무의 공식 국가·외교 브리프 절차. 내부 official-source-research capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "외교"
    capability: official-source-research
    runtime_contract: "kgov/official-source-research/v1"
    operation: "kgov/official-source-research/inspect-page/v1"
    role: primary
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 공식 국가·외교 브리프

- Domain: **외교**
- 내부 capability: `official-source-research`
- 실행 상태: `fixture-verified` / live smoke `blocked`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/official-source-research/v1`
- Operation: `kgov/official-source-research/inspect-page/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `url`, `content_type`, `title`, `sha256`, `execution_mode`, `status`, `content_length`, `source_receipt`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/official-source-research/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/official-source-research/inspect-page/v1"
  },
  "example_result": {
    "content_length": 0,
    "content_type": "text/html",
    "execution_mode": "synthetic-fixture",
    "manual_review_required": true,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "source_receipt": null,
    "status": 200,
    "title": "정부24",
    "url": "https://www.gov.kr/"
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
  "module": "kgov_runtime.capabilities.official_source_research",
  "network_mode": "optional-live",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "content_length": {
        "minimum": 0,
        "type": "integer"
      },
      "content_type": {
        "type": "string"
      },
      "execution_mode": {
        "enum": [
          "official-live",
          "synthetic-fixture"
        ],
        "type": "string"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "sha256": {
        "format": "sha256",
        "type": "string"
      },
      "source_receipt": {
        "additionalProperties": false,
        "properties": {
          "operation_id": {
            "const": "kgov/official-source-research/inspect-page/v1",
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
              "gov-kr-web"
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
      },
      "status": {
        "minimum": 0,
        "type": "integer"
      },
      "title": {
        "type": "string"
      },
      "url": {
        "type": "string"
      }
    },
    "required": [
      "manual_review_required",
      "url",
      "content_type",
      "title",
      "sha256",
      "execution_mode",
      "status",
      "content_length",
      "source_receipt"
    ],
    "type": "object"
  },
  "schema_status": "active",
  "source_output_mode": "link-only",
  "source_policy_ids": [
    "gov-kr-web"
  ]
}
```
<!-- kgov-runtime-binding:end -->

## 절차

1. 저장소 루트에서 `docs/capabilities/official-source-research/procedure.md`와 `docs/capabilities/official-source-research/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.official_source_research --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 로그인·제출·민감업무는 수동 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
