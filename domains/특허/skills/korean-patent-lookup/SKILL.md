---
name: korean-patent-lookup
description: "특허 업무의 KIPRIS 특허 조회 절차. 내부 patent-prior-art-evidence-pack capability를 사용하며 read-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "특허"
    capability: patent-prior-art-evidence-pack
    role: primary
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# KIPRIS 특허 조회

- Domain: **특허**
- 내부 capability: `patent-prior-art-evidence-pack`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `read-only`
- Reference Skill: `korean-patent-search`

## 업무별 추가 체크

- KIPRIS 검색 결과와 공개번호·공개일을 보존
- 청구항 요소별 관련 문헌·인용 위치를 구조화
- 신규성·진보성·침해 판단은 변리사 검토로 이관

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
