# 법령 조문·판례 인용 검증

## 해결하려는 문제

- 보고서·민원 답변 초안에 존재하지 않거나 다른 조·항·호를 넣는 오류
- 검색되지 않거나 다른 사건인 판례번호를 근거처럼 쓰는 오류
- 검색 snippet·블로그·LLM 답변을 공식 원문으로 오인하는 오류

이 capability는 문장을 생성하는 도구가 아니라, 후보 인용을 국가법령정보 공식 record와 직접 대조하여 근거 없는 인용을 초안에서 차단하는 evidence gate입니다.

## 원칙

- caller는 후보만 제출합니다. 공식 원문 object, 조회 성공 선언, 원문 URL을 입력으로 받지 않습니다.
- 법령과 판례의 공식 조회는 verifier가 직접 수행합니다.
- 모든 후보가 통과해야 ledger 전체가 admission을 통과합니다.
- 검색 결과가 없거나 여러 개라는 사실을 모델이 추론으로 채우지 않습니다.
- 외부 Reference Skill은 탐색 절차 참고용이며 신뢰 근거는 국가법령정보 공식 응답입니다. 조사 근거와 채택 경계는 `design-references.md`에 고정 commit 기준으로 기록합니다.

## 절차

1. 초안에서 법률 판단이 필요한 주장과 인용 후보만 분리하고 당사자 이름·연락처·사건 원문을 제거합니다.
2. `LAW_OC`를 환경변수로만 설정합니다. 명령 인수·URL·fixture·로그·커밋에 넣지 않습니다.
3. 법령은 `--search-law --param query=...`로 탐색하고 정확한 법령명과 6자리 법령 ID를 확인합니다.
4. 법령 candidate에 `law_id`, 6자리 `JO`, 단순 항·호·목의 4자리 순번과 실제 인용문을 기록합니다. verifier가 항·호 순번을 공식 6자리 `HANG/HO`로, 목 순번을 한글 `MOK`로 바꾸고 기준일 이하의 최신 연혁과 해당 조문 단위를 직접 조회합니다.
5. 판례는 사건번호가 있으면 `nb`, 쟁점만 있으면 `query` 또는 `search=2`, 참조법령은 `JO`로 검색합니다.
6. 판례 검색이 2건 이상이면 `ambiguous-candidates-manual-selection-required` 상태에서 자동 선택하지 않습니다. 사건번호·법원·선고일을 보고 사람이 판례일련번호를 선택합니다.
7. 판례 candidate에 선택한 판례일련번호·사건번호·법원·선고일·실제 인용문을 기록합니다. verifier가 그 일련번호의 상세를 직접 재조회합니다.
8. `verified-official-live-match`만 초안의 근거표 후보로 사용할 수 있습니다. `admission_passed=false`이면 ledger의 어떤 citation도 본문에 넣지 않습니다.
9. 판결요지 등 공식 선택 필드가 비어 있으면 생성해 보완하지 않습니다. 실제 `판시사항`, `판결요지`, `판례내용` 중 반환된 필드를 사용하고 결과의 `quote_source_field`를 확인합니다.
10. 유리한 판례만 고르지 말고 동일 쟁점의 반대·제한 판례를 별도로 검색합니다. 이 검색의 완전성은 자동 gate가 보증하지 않으므로 검토 체크리스트에 남깁니다.
11. 공식 URL에서 원문 문맥과 최신 효력·후속 판례를 사람이 재확인한 뒤 최종 인용·결재·발송을 승인합니다.

## 실행 예시

합성 fixture:

```bash
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification --fixture
```

이 명령은 transport·schema·matching 회귀만 검사합니다. 출력은 `synthetic-fixture-match`와 `fixture_contract_passed`를 사용하며, `admission_passed`는 항상 `false`입니다.

법령 검색:

```bash
export LAW_OC='사용자 소유 인증값'
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
  --search-law --param 'query=개인정보 보호법' --param display=100
```

사건번호로 판례 검색:

```bash
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
  --search-precedent --param nb=2024다12345
```

선택한 판례일련번호의 안전한 metadata 조회:

```bash
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
  --precedent-id 228541
```

준비한 후보 ledger의 trusted live 검증:

```bash
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification citations.json
```

## 입력 예시

```json
{
  "as_of_date": "2026-07-20",
  "jurisdiction": "KR",
  "input_scope": "redacted-citations-only",
  "citations": [
    {
      "citation_id": "LAW1",
      "kind": "statute",
      "candidate": {
        "law_name": "개인정보 보호법",
        "law_id": "011357",
        "article_code": "001500",
        "paragraph_code": "0002",
        "item_code": "0001",
        "subitem_code": null,
        "quoted_text": "개인정보의 수집·이용 목적"
      }
    },
    {
      "citation_id": "PREC1",
      "kind": "precedent",
      "candidate": {
        "serial_number": "218239",
        "case_number": "2019다284889",
        "court": "대법원",
        "decision_date": "2020-12-30",
        "quoted_text": "공식 상세에서 발췌한 12자 이상의 실제 문장"
      }
    }
  ]
}
```

## 상태 해석

- `verified-official-live-match`: capability가 실행 중 공식 원문을 직접 조회해 식별자·기준일·locator·인용문을 확인했습니다. 법적 타당성은 별도 사람 검토가 필요합니다.
- `mismatch-blocked`: metadata, 기준일 또는 인용문이 공식 상세와 다릅니다.
- `official-source-not-found`: 공식 not-found 응답입니다. 존재하지 않는다고 즉시 단정하지 말고 입력 ID와 검색식을 다시 확인합니다.
- `ambiguous-candidates-manual-selection-required`: 자동 선택을 중단하고 사람이 후보를 확인해야 합니다.

## 금지

- 사건번호, 법령 ID, 조·항·호 code, 판결요지를 기억이나 유사 문서에서 보완 생성하지 않습니다.
- 판례일련번호와 사건번호, 법령 ID와 법령일련번호를 바꾸어 쓰지 않습니다.
- 검색 0건을 곧바로 “법령·판례 없음”으로 단정하지 않습니다.
- 인증 오류·API 오류를 not-found로 취급하지 않습니다.
- 법률자문, 처분 판단, 소송 전략, 승소 가능성을 확정하지 않습니다.
- 결재·제출·발송·전자소송 등 외부 mutation을 수행하지 않습니다.
