---
name: kosis-official-statistics
description: KOSIS 등 한국 공식 통계에서 표·지표를 찾아 단위·시점·분류를 보존한 조회 결과를 만들 때 사용한다.
---

# KOSIS 공식통계

## 사용 범위
- 인구·재정·고용·농림·환경·산업 통계 조회
- 통계표 메타데이터와 관측값 추출
- 서로 다른 시계열·지역·분류의 비교

## 실행 경계
- 출처가 다른 수치를 단위 확인 없이 합산하지 않는다.
- 잠정치·확정치·계절조정 여부를 숨기지 않는다.
- 분석적 해석은 관측값과 분리한다.

## 절차
1. 지표, 지역, 기간, 단위, 분류를 명시한다.
2. 공식 통계표와 메타데이터를 함께 찾는다.
3. 표 ID, 제공기관, 갱신일, 단위, 주석을 보존한다.
4. 값의 누락·개편·시계열 단절을 점검한다.
5. 원자료와 계산값을 분리해 재현 가능한 표로 출력한다.

## 출력 계약
- 통계표 ID와 공식 출처
- 필터 조건·단위·기준시점
- 원자료와 계산식
- 주석·누락·비교 제한

## 실행 도구

- fixture 검증: `python3 skills/kosis-official-statistics/scripts/adapter.py --fixture`
- live 조회: `references/runtime-contract.md`의 credential·endpoint 조건을 확인한 뒤 실행합니다.
- fixture 통과는 live endpoint 검증을 의미하지 않습니다.
