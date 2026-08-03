---
name: food-drug-public-notice-multilingual-review
description: "식품의약 업무의 식품·의약 공지 다국어 검토 절차. 내부 official-notice-multilingual-translation-review capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "식품의약"
    capability: official-notice-multilingual-translation-review
    role: additional
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 식품·의약 공지 다국어 검토

- Domain: **식품의약**
- 내부 capability: `official-notice-multilingual-translation-review`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: 없음

## 업무별 추가 체크

- 공지 대상·제품 또는 품목·언어·시행일·주의사항·행동요령을 문장 단위로 분리
- 식약처 공식 원문 URL·공표일·조회일·문서 버전과 번역상 미확정 용어를 보존
- 안전성·법적 의미·공식 용어·언어별 감수·게시·발송은 식품의약 담당자와 전문 감수자 승인으로 이관

## 절차

1. 저장소 루트에서 `docs/capabilities/official-notice-multilingual-translation-review/procedure.md`와 `docs/capabilities/official-notice-multilingual-translation-review/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.official_notice_multilingual_translation_review --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 공식 용어, 법적 의미, 언어별 감수와 게시·발송은 기관 담당자와 전문 감수자가 승인
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
