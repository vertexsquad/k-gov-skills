---
name: workplace-safety-policy-evidence-pack
description: "고용노동 업무의 사업장 안전정책 근거 팩 절차. 내부 public-policy-evidence-pack capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  domain: "고용노동"
  capability: "public-policy-evidence-pack"
  runtime_contract: "kgov/public-policy-evidence-pack/v1"
  operation: "kgov/public-policy-evidence-pack/build-pack/v1"
  role: "additional"
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 사업장 안전정책 근거 팩

- Domain: **고용노동**
- 내부 capability: `public-policy-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## Runtime binding

- Contract: `kgov/public-policy-evidence-pack/v1`
- Operation: `kgov/public-policy-evidence-pack/build-pack/v1`
- Fixed input: `{"argv": ["--fixture"]}`
- Output fields: `manual_review_required`, `accepted`, `jurisdiction`, `permitted_output`, `claims`, `status_counts`, `claim_count`, `as_of_date`, `basic_identifier_scan`, `receipt_assurance`, `source_kind_assurance`

<!-- kgov-runtime-binding:start -->
```json
{
  "binding": {
    "contract_id": "kgov/public-policy-evidence-pack/v1",
    "fixed_input": {
      "argv": [
        "--fixture"
      ]
    },
    "operation": "kgov/public-policy-evidence-pack/build-pack/v1"
  },
  "example_result": {
    "accepted": true,
    "as_of_date": "2026-07-15",
    "basic_identifier_scan": "no-match-not-proof-of-redaction",
    "claim_count": 3,
    "claims": [
      {
        "claim_id": "C1",
        "contradiction_detected": false,
        "evidence_count": 1,
        "retrieved_evidence_count": 1,
        "retrieved_official_primary_count": 1,
        "status": "structurally-supported-pending-human-review"
      },
      {
        "claim_id": "C2",
        "contradiction_detected": true,
        "evidence_count": 2,
        "retrieved_evidence_count": 2,
        "retrieved_official_primary_count": 2,
        "status": "conflict-detected-pending-human-review"
      },
      {
        "claim_id": "C3",
        "contradiction_detected": false,
        "evidence_count": 1,
        "retrieved_evidence_count": 1,
        "retrieved_official_primary_count": 0,
        "status": "insufficient-official-evidence"
      }
    ],
    "jurisdiction": "KR",
    "manual_review_required": true,
    "permitted_output": "evidence-pack-draft-only",
    "receipt_assurance": "input-declared-not-live-retrieval-proof",
    "source_kind_assurance": "input-declared-not-independently-verified",
    "status_counts": {
      "conflict-detected-pending-human-review": 1,
      "insufficient-official-evidence": 1,
      "structurally-supported-pending-human-review": 1
    }
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
  "module": "kgov_runtime.capabilities.public_policy_evidence_pack",
  "network_mode": "none",
  "output_schema": {
    "additionalProperties": false,
    "properties": {
      "accepted": {
        "const": true,
        "type": "boolean"
      },
      "as_of_date": {
        "format": "date",
        "type": "string"
      },
      "basic_identifier_scan": {
        "const": "no-match-not-proof-of-redaction",
        "type": "string"
      },
      "claim_count": {
        "minimum": 0,
        "type": "integer"
      },
      "claims": {
        "items": {
          "additionalProperties": false,
          "properties": {
            "claim_id": {
              "type": "string"
            },
            "contradiction_detected": {
              "type": "boolean"
            },
            "evidence_count": {
              "minimum": 0,
              "type": "integer"
            },
            "retrieved_evidence_count": {
              "minimum": 0,
              "type": "integer"
            },
            "retrieved_official_primary_count": {
              "minimum": 0,
              "type": "integer"
            },
            "status": {
              "enum": [
                "structurally-supported-pending-human-review",
                "conflict-detected-pending-human-review",
                "insufficient-official-evidence"
              ],
              "type": "string"
            }
          },
          "required": [
            "claim_id",
            "contradiction_detected",
            "evidence_count",
            "retrieved_evidence_count",
            "retrieved_official_primary_count",
            "status"
          ],
          "type": "object"
        },
        "type": "array"
      },
      "jurisdiction": {
        "const": "KR",
        "type": "string"
      },
      "manual_review_required": {
        "const": true,
        "type": "boolean"
      },
      "permitted_output": {
        "const": "evidence-pack-draft-only",
        "type": "string"
      },
      "receipt_assurance": {
        "const": "input-declared-not-live-retrieval-proof",
        "type": "string"
      },
      "source_kind_assurance": {
        "const": "input-declared-not-independently-verified",
        "type": "string"
      },
      "status_counts": {
        "additionalProperties": false,
        "properties": {
          "conflict-detected-pending-human-review": {
            "minimum": 0,
            "type": "integer"
          },
          "insufficient-official-evidence": {
            "minimum": 0,
            "type": "integer"
          },
          "structurally-supported-pending-human-review": {
            "minimum": 0,
            "type": "integer"
          }
        },
        "required": [
          "structurally-supported-pending-human-review",
          "conflict-detected-pending-human-review",
          "insufficient-official-evidence"
        ],
        "type": "object"
      }
    },
    "required": [
      "manual_review_required",
      "accepted",
      "jurisdiction",
      "permitted_output",
      "claims",
      "status_counts",
      "claim_count",
      "as_of_date",
      "basic_identifier_scan",
      "receipt_assurance",
      "source_kind_assurance"
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

- 업종·작업·위험요인·통제조치·교육·점검·증빙 공백을 분리
- 고용노동부·안전보건공단·법령 공식 URL·조회일·문서 버전과 상충 근거를 구분
- 사업장 위험도·작업중지·산재 인정·제재·계획 승인은 안전보건 담당자 검토로 이관

## 절차

1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `docs/capabilities/public-policy-evidence-pack/procedure.md`와 `docs/capabilities/public-policy-evidence-pack/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.public_policy_evidence_pack --fixture`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.
3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.
4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
5. 정책·법률·통계 판단과 문서 결재·발송은 담당 공무원 승인
6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
