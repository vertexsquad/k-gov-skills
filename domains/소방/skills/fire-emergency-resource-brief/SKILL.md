---
name: fire-emergency-resource-brief
description: "소방 업무의 응급실·재난자원 브리프 절차. 내부 disaster-geospatial-brief capability를 사용하며 draft-only 경계를 지킵니다."
metadata:
  kgov:
    domain: "소방"
    capability: disaster-geospatial-brief
    role: primary
---

<!-- generated from catalog/domain-skills.json; do not edit -->

# 응급실·재난자원 브리프

- Domain: **소방**
- 내부 capability: `disaster-geospatial-brief`
- 실행 상태: `fixture-verified` / live smoke `not-run`
- 실행 경계: `draft-only`
- Reference Skill: `emergency-room-beds`, `korea-weather`

## 절차

1. 저장소 루트에서 `docs/capabilities/disaster-geospatial-brief/procedure.md`와 `docs/capabilities/disaster-geospatial-brief/runtime-contract.md`를 먼저 읽습니다.
2. `python3 -m kgov_runtime.capabilities.disaster_geospatial_brief --fixture`로 합성 fixture 계약을 검증합니다.
3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.
4. 출동·대피·의료판단은 공식기관으로 전환
5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.

## 금지

- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.
- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.
- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.
