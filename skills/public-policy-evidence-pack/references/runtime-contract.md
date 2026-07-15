# Runtime contract

## 역할 분리

- `SKILL.md`는 질문 분해와 기존 read-only capability 조합 절차를 안내합니다.
- `scripts/adapter.py`는 caller가 준비한 normalized evidence ledger만 local에서 검증합니다.
- adapter는 source를 조회·인증하지 않으며 sibling adapter를 import하거나 subprocess로 실행하지 않습니다.

## 입력

Top-level exact fields:

- `question`: 1–1,000자, 비식별 정책 질문
- `as_of_date`: 유효한 `YYYY-MM-DD`
- `jurisdiction`: `KR`
- `redaction_status`: `redacted`
- `claims`: 1–50개

Claim exact fields:

- `claim_id`: `^[A-Z][A-Z0-9_-]{0,31}$`, pack 안에서 유일
- `statement`: 1–2,000자
- `evidence`: 0–20개

Evidence exact fields:

- `source_url`: 1–2,048자 credential-free HTTPS URL
- `source_kind`: `official-primary`, `official-secondary`, `non-official`
- `retrieved_on`: 유효한 `YYYY-MM-DD`
- `relationship`: `supports`, `contradicts`, `context`
- `receipt_status`: `retrieved`, `not-retrieved`

입력 파일은 최대 250,000 bytes입니다. output에 노출되는 claim ID와 question, statement, source URL 전체(path/query/fragment 포함)에 지원되는 직접 식별자 패턴이 있으면 fail-closed로 거부합니다. `retrieved_on`은 pack의 `as_of_date` 이후일 수 없습니다. scanner의 no-match는 완전한 비식별 증명이 아닙니다.

## 결정적 상태

- retrieved official-primary support와 contradiction이 모두 있으면 `conflict-detected-pending-human-review`
- retrieved official-primary support만 있으면 `structurally-supported-pending-human-review`
- 그 외에는 `insufficient-official-evidence`

official-secondary·non-official 또는 `not-retrieved` evidence는 official-primary support gate를 충족하지 않습니다. 상태는 input-declared receipt 구조의 분류이며 source authenticity 또는 factual truth를 증명하지 않습니다.

## 출력·비노출

출력은 claim ID, evidence/retrieved count, retrieved official-primary count, contradiction flag, 상태별 count, 기준일, 수동검토·draft-only flag만 포함합니다. question, statement, source URL, raw source body는 정상·오류 출력에 포함하지 않습니다.

## 실행·side effect

- local-only adapter
- adapter network: none
- adapter credential/proxy: none
- optional retrieval lanes: 각 dependency의 credential/proxy 계약 유지
- output: `evidence-pack-draft-only`
- manual review: required
- 실제 정책판단·법률판단·통계해석·결재·등록·발송·공개·업로드: forbidden
- fixture evidence: synthetic/redacted, deterministic
- live composite evidence: not run
