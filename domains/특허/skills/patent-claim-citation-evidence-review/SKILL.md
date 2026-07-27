---
name: patent-claim-citation-evidence-review
description: "특허 업무의 특허 청구항 인용 근거 검토 절차. 내부 patent-prior-art-evidence-pack capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "특허"
    capability: patent-prior-art-evidence-pack
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 특허 청구항 인용 근거 검토

- Domain: **특허**
- 내부 capability: `patent-prior-art-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 출원번호·공개번호·등록번호·청구항 버전·청구항 요소·인용 문헌번호·인용 위치를 분리
- KIPRIS·특허청 공식 URL·공개일·조회일·공개 또는 등록 상태와 미확인·복수 후보를 보존
- 신규성·진보성·침해·유효성·출원전략 판단은 변리사와 특허 담당자 검토로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/patent-prior-art-evidence-pack/procedure.md`와 `docs/capabilities/patent-prior-art-evidence-pack/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 신규성·진보성·침해·등록가능성 판단과 출원·심판 제출은 변리사 또는 담당자가 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
