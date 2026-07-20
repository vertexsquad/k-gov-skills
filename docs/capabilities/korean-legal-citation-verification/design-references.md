# Design references — `korean-legal-citation-verification`

## 조사 범위

2026-07-20에 다음 공개 저장소의 기본 브랜치를 고정 commit 기준으로 읽기 전용 조사했습니다.

- `legalize-kr/agent-skills@0ce6ce596e755d7a65aa4c41a3cc09a1dab3fdf8`
  - https://github.com/legalize-kr/agent-skills/tree/0ce6ce596e755d7a65aa4c41a3cc09a1dab3fdf8
- `Sungmin-Cho/skill-legal-kr@b4dc9bcffd7fa2a85c083a41dbb82ec80b524d60`
  - https://github.com/Sungmin-Cho/skill-legal-kr/tree/b4dc9bcffd7fa2a85c083a41dbb82ec80b524d60
- `NomaDamas/k-skill@4b4b4b392165abe65baa3eac695724ddb9bce304`
  - https://github.com/NomaDamas/k-skill/tree/4b4b4b392165abe65baa3eac695724ddb9bce304

외부 코드는 실행 경로에 포함하지 않았고, 프롬프트·문서·구현을 복사하거나 미러링하지 않았습니다.

## 비교

| 항목 | legalize-kr/agent-skills | Sungmin-Cho/skill-legal-kr | NomaDamas/k-skill |
|---|---|---|---|
| 기본 자료 경로 | Legalize-KR Git mirror를 CLI·MCP·clone·GitHub 중 작업에 맞게 선택 | 로컬 `precedent-kr`에서 사건명 → 참조조문 → 본문 키워드로 확장 | hosted proxy를 통해 국가법령정보 `prec` 목록 → `ID` 상세의 2단계 조회 |
| 출처 식별 | repository path·commit 등 재현 가능한 식별자를 강조 | 대법원 우선, 표준 판례 인용 형식을 강조 | 공식 API의 판례일련번호와 상세조회 흐름을 명시 |
| 0건·오류 | 접근수단을 바꾸고 탐색 범위를 조정 | 검색어·참조조문·본문으로 단계 확장 | 0건, 본문 없음, API 장애를 구분하는 절차가 구체적 |
| 반대·제한 판례 | 명시적 자동 gate 없음 | 양면 검토를 가장 분명하게 요구 | 명시적 자동 gate 없음 |
| 사건번호 역검증 | 필수 admission 단계로 명시하지 않음 | 필수 admission 단계로 명시하지 않음 | 검색 결과와 상세 metadata를 다시 대조하는 강제 gate는 없음 |

세 구현 모두 유용한 탐색 절차가 있지만, **caller가 적은 사건번호·조문 locator와 공식 상세 record를 runtime이 다시 결합 검증하는 필수 admission gate는 공통적으로 비어 있었습니다.**

## 채택한 설계 원칙

- 목록과 상세를 분리하고, 상세 식별자를 다시 조회합니다.
- 검색 0건·복수 후보·API 오류를 서로 다른 상태로 취급합니다.
- 판례일련번호와 사건번호를 구분합니다.
- 표준 인용 형식을 만들되 공식 metadata와 인용문이 모두 일치한 뒤에만 출력합니다.
- 유리한 판례만 선택하지 않도록 반대·제한 판례를 사람 검토 체크리스트에 둡니다.
- source URL·version identifier·기준일을 남겨 재현성을 확보합니다.

## 추가한 안전 경계

외부 reference보다 강하게 다음을 runtime에서 강제합니다.

- caller-supplied `official`, 조회 성공 선언, source URL 금지
- 법령 `LID → 기준일 이하 최신 exact-name version → MST/efYd/JO/HANG/HO + subitem ordinal→MOK` trusted retrieval
- 판례 `serial_number → PrecService` trusted retrieval
- 조·항·호·목 단위 text 귀속 검사
- 판례 metadata·인용 field·미래 선고일 검사
- 모든 citation이 통과해야 ledger admission 성공
- NFKC 후 직접 식별자 검사, Unicode control/line/bidi 차단
- raw 법령·판례 본문과 credential 반사 링크 비출력

## 채택하지 않은 것

- 외부 hosted proxy를 신뢰 경로로 사용하지 않습니다.
- Git mirror·검색 snippet·LLM 요약을 공식 원문 대체물로 사용하지 않습니다.
- 모델의 자신감이나 다수결로 citation을 승인하지 않습니다.
- 반대 판례 검색의 완전성을 자동 보증한다고 주장하지 않습니다.
