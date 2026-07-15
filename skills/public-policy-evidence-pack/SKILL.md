---
name: public-policy-evidence-pack
description: 공식자료·법령·통계의 근거 receipt를 주장별 content-light evidence pack으로 정리하고 모순·근거 부족·담당자 검토 필요성을 표시합니다.
---

# Public Policy Evidence Pack

## 사용 조건

- 한국 공공정책·행정 질문을 근거가 필요한 주장 단위로 분해할 때 사용합니다.
- 실제 개인정보·비공개 내부자료는 넣지 않고 synthetic 또는 비식별 입력만 사용합니다.
- 이 Skill은 orchestrator 절차와 local ledger validator를 제공합니다. stateful Agent runtime이 아닙니다.

## 절차

1. 질문의 기준일과 관할을 확인하고, 최종 정책·법률·통계 판단이 담당자에게 있음을 고정합니다.
2. 질문을 독립적으로 확인 가능한 `claim_id`와 statement로 분해합니다.
3. `official-source-research`, `korean-law-bill-research`, `kosis-official-statistics` 등 필요한 read-only capability만 각각의 credential·network 계약 아래 실행합니다.
4. source URL, 조회일, source kind, support/contradiction 관계, receipt 상태를 normalized ledger로 정리합니다.
5. `scripts/adapter.py`로 exact schema·개인정보·URL·충돌 상태를 검증합니다.
6. `insufficient-official-evidence`와 conflict 항목은 추가 확인 TODO로 남기고, evidence-backed outline만 `administrative-document-draft-review`의 별도 입력으로 전달할 수 있습니다.
7. 담당 공무원이 source kind, 최신성, 법률·통계 해석, 문서 결재·발송 여부를 최종 승인합니다.

## 상태 해석

- `structurally-supported-pending-human-review`: retrieved로 선언된 official-primary support가 있고 retrieved contradiction이 없습니다.
- `conflict-detected-pending-human-review`: retrieved로 선언된 official-primary support와 contradiction이 함께 있습니다.
- `insufficient-official-evidence`: retrieved official-primary support가 없습니다.

위 상태는 입력 구조에 대한 결정적 분류이며 사실 검증 결과가 아닙니다. source kind와 receipt는 입력 선언이고 adapter가 독립 조회·인증하지 않습니다.

## 금지

- 원 질문·주장·URL·raw response body를 결과에 재출력하지 않습니다.
- 법적 효력, 통계 인과관계, 정책 타당성, 기관 내부 규정 적합성을 자동 확정하지 않습니다.
- 결재·등록·발송·공개·업로드·메시지 전송·외부 시스템 mutation을 수행하지 않습니다.
- sibling adapter를 import/subprocess로 자동 실행하거나 credential을 수집하지 않습니다.
