# k-gov-skills

한국 공무원의 **업무 분야(domain)**별 반복 업무를 안전한 Agent Skill로 패키징하는 독립 프로젝트입니다.

## 구조

```text
CLAUDE.md                                      # canonical 저장소 작업 계약
AGENTS.md                                      # cross-runtime thin adapter
catalog/domain-skills.json                     # 60 domain·168 Skill·22 capability SSOT
domains/<한글 domain>/skills/<slug>/SKILL.md   # 공개 Skill 진입점
kgov_runtime/capabilities/<module>.py           # domain 간 공유하는 내부 실행 구현
docs/capabilities/<capability>/                 # 절차·runtime contract·live 증거
tests/capabilities/                             # capability별 unit test
tests/fixtures/capabilities/                    # 합성 deterministic fixture
scripts/render_domain_skills.py                 # domain Skill 생성기
scripts/render_catalog.py                       # 사람용 catalog 문서 생성기
scripts/validate_catalog.py                     # topology·catalog·instruction 검증기
scripts/check.py                                # 전체 deterministic 검증 진입점
```

`domain`은 단순 taxonomy가 아니라 **Skill 소유·배포 경계**입니다. 공개 Skill은 반드시
`domains/<domain>/skills/` 하위에 있어야 하며 별도 top-level `skills/`는 허용하지 않습니다.
공통 adapter 코드는 `kgov_runtime/capabilities/`에서 한 번만 구현하고 domain Skill이 이를 호출합니다.

Catalog schema v5의 domain `skills[]`는 `primary` 하나와 선택적 `additional` Skill을 명시합니다.
모든 `name`은 저장소 전체에서 고유합니다. 60개 domain에 primary 60개와 additional 108개,
총 168개 domain-owned Skill 진입점이 있습니다. 모든 domain의 목표는 최소 5개이며,
`target_skills_per_domain`과 `enforced_minimum_skills_by_domain`으로 단계적 확대 상태를 검증합니다.
현재 국가운영 9개 domain과 교육·교육행정·사회복지·고용노동·보건의료·식품의약을 포함한 18개 domain이 목표를 충족합니다.

## 현재 capability

다음 22개 read-only/document-read/draft-only 내부 capability를 제공합니다.

- `public-document-hwpx`
- `korean-law-bill-research`
- `kosis-official-statistics`
- `public-procurement-research`
- `disaster-geospatial-brief`
- `welfare-health-safety-research`
- `land-housing-geospatial-research`
- `official-source-research`
- `civil-complaint-triage-draft`
- `administrative-document-draft-review`
- `public-policy-evidence-pack`
- `korean-legal-citation-verification`
- `public-ai-governance-review`
- `public-it-project-procedure-review`
- `public-record-disclosure-redaction-review`
- `local-ordinance-draft-review`
- `construction-standard-bim-compliance-precheck`
- `building-permit-document-precheck`
- `official-notice-multilingual-translation-review`
- `patent-prior-art-evidence-pack`
- `public-records-lifecycle-review`
- `regulated-trade-procedure-precheck`

Domain의 `direct`, `adjacent`, `new`, `sensitive`는 구현 완료도가 아니라 **근거 강도와 도입 경계**입니다.
20개 capability는 `fixture-verified`이고 `official-source-research`와
`korean-legal-citation-verification`은 `live-verified / live_smoke: passed`입니다. Domain Skill은 연결된 capability보다 강한 검증 상태를
주장하지 않습니다.

## 법령·판례 인용 검증 Skill 사용법

[`public-administration-legal-citation-verification`](domains/행정/skills/public-administration-legal-citation-verification/SKILL.md)은 보고서·민원 답변·정책 검토 초안에 넣을 **법령 조문과 판례 인용 후보**를 국가법령정보 공식 원문과 대조하는 행정 Domain Skill입니다. 문장을 대신 작성하거나 법률 판단을 내리는 도구가 아니라, 존재하지 않는 판례번호·잘못된 조항·다른 항목의 문구가 근거처럼 들어가는 것을 막는 draft-only evidence gate입니다.

### 언제 사용하나요?

- 보고서나 민원 답변에 법령 조·항·호·목을 인용하기 전
- 판례번호·법원·선고일·판결요지 인용이 실제 공식 판례와 같은지 확인할 때
- 특정 기준일 당시 적용되는 법령 연혁을 골라야 할 때
- LLM이나 검색 결과가 제시한 법적 근거를 그대로 믿지 않고 공식 원문으로 재검증할 때

Agent에게는 다음처럼 요청할 수 있습니다.

> `public-administration-legal-citation-verification` Skill을 사용해서 이 초안의 법령·판례 인용 후보만 검증해 줘. 원문 개인정보는 입력하지 말고, 공식 원문과 일치한 인용만 초안용 근거표로 정리해 줘. 불일치나 복수 후보는 자동 보완하지 말고 차단 상태로 알려 줘.

### 빠른 시작

1. 합성 fixture로 로컬 실행 계약을 먼저 확인합니다. fixture 성공은 live 원문 검증 성공을 뜻하지 않습니다.

   ```bash
   python3 -m kgov_runtime.capabilities.korean_legal_citation_verification --fixture
   ```

2. 국가법령정보 사용자 소유 인증값을 환경변수로만 설정합니다. 값은 명령 인수·URL·fixture·로그·커밋에 넣지 않습니다.

   ```bash
   export LAW_OC='사용자 소유 인증값'
   ```

3. 공식 목록에서 법령 ID 또는 판례일련번호를 찾습니다.

   ```bash
   # 정확한 법령명과 6자리 법령 ID 확인
   python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
     --search-law --param 'query=개인정보 보호법' --param display=100

   # 사건번호로 판례 후보 검색
   python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
     --search-precedent --param 'nb=2024다12345'

   # 선택한 판례일련번호의 안전한 metadata 재조회
   python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
     --precedent-id 228541
   ```

4. 이름·연락처·민원 원문을 제거한 뒤 후보 ledger를 `citations.json`으로 준비합니다. 법령은 `law_id`, `article_code`, 항·호·목 순번과 실제 인용문을, 판례는 판례일련번호·사건번호·법원·선고일과 실제 인용문을 기록합니다. 전체 JSON 예시는 [procedure 문서](docs/capabilities/korean-legal-citation-verification/procedure.md#입력-예시)에 있습니다.

5. trusted live 검증을 실행합니다.

   ```bash
   python3 -m kgov_runtime.capabilities.korean_legal_citation_verification citations.json
   ```

6. `admission_passed=true`이면서 항목 상태가 `verified-official-live-match`인 인용만 **초안용 후보**로 사용합니다. `mismatch-blocked`, `official-source-not-found`, `ambiguous-candidates-manual-selection-required`는 자동으로 고쳐 쓰거나 추정하지 말고 입력과 공식 원문을 사람이 다시 확인합니다.

### 사용했을 때의 장점

| 장점 | 실제로 달라지는 점 |
|---|---|
| 공식 1차 출처 직접 검증 | 검색 snippet·블로그·LLM의 주장 대신 실행 중 국가법령정보 원문을 다시 조회합니다. |
| 잘못된 인용 차단 | 법령 ID·기준일·조·항·호·목과 판례일련번호·사건번호·법원·선고일·인용문이 함께 맞아야 통과합니다. |
| 기준일에 맞는 법령 선택 | `as_of_date` 이하의 정확한 법령명 중 최신 단일 연혁을 선택해 현재법과 과거 시점의 법을 섞는 위험을 줄입니다. |
| 그럴듯한 자동 보완 방지 | 검색 0건, 복수 후보, API/schema 오류, metadata 불일치를 추정으로 메우지 않고 fail-closed 처리합니다. |
| 개인정보·credential 노출 축소 | 원문 대신 비식별 인용 후보만 받고, 직접 식별자와 credential 반사를 차단하며 raw 공식 본문을 결과에 내보내지 않습니다. |
| 검토 가능한 결과 | 통과·불일치·미존재·모호성 상태와 credential-free 공식 URL을 분리해 담당자가 최종 문맥을 확인할 수 있습니다. |
| 모델 독립적 안전장치 | 특정 LLM의 자신감이나 기억에 의존하지 않고 같은 deterministic 검증 절차를 적용합니다. |

이 Skill이 보증하는 것은 **실행 시점에 조회한 공식 record와 후보 인용의 구조적 일치**입니다. 법률 해석, 사실관계 적용, 판례의 현재 효력, 반대·제한 판례 검색의 완전성, 최종 문서의 법적 적합성은 보증하지 않습니다. 최종 인용·결재·제출·발송은 담당 공무원 또는 법무 검토자가 승인해야 합니다. 세부 입력 필드와 종료 코드는 [runtime contract](docs/capabilities/korean-legal-citation-verification/runtime-contract.md)를 참고하세요.

## 개발·검증

```bash
# capability 하나의 합성 fixture 실행
python3 -m kgov_runtime.capabilities.kosis_official_statistics --fixture

# 생성물 drift 확인
python3 scripts/render_domain_skills.py --check
python3 scripts/render_catalog.py --check

# 네트워크·credential 없이 전체 검증
python3 scripts/check.py
```

Catalog를 변경한 경우 다음 순서로 생성물을 갱신합니다.

```bash
python3 scripts/render_domain_skills.py
python3 scripts/render_catalog.py
python3 scripts/check.py
```

실제 조회 전 `docs/capabilities/<capability>/runtime-contract.md`의 공식 endpoint, 환경변수,
필수 query parameter를 확인합니다. credential 값은 인자·fixture·로그·저장소에 기록하지 않습니다.

## 외부 reference 경계

- `mouseco/k-gov-skills`, `NomaDamas/k-skill`, `legalize-kr/agent-skills`,
  `Sungmin-Cho/skill-legal-kr`는 별개 프로젝트이며 참고 자료로만 사용합니다.
- 외부 코드·프롬프트·문서를 복사하거나 미러링하지 않습니다.
- 실제 adapter 변경 전 공식 API, 이용약관, 인증정보 소유자, proxy, 개인정보, side effect를 재검증합니다.
- 예약·결제·제출·메시지·문서 원본 변경·민감 경호업무는 명시 승인과 manual handoff 없이는 자동화하지 않습니다.
