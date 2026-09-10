# k-gov-skills

**한국 공무원의 문서 검토와 근거 정리를 돕는 업무 분야별 AI 에이전트 Skill 모음입니다.**

Claude Code와 Codex에서 업무에 맞는 Skill을 읽고, 연결된 Python 도구로 검토 절차를 실행합니다. Skill은 AI 에이전트가 참고하는 업무 지침과 실행 방법을 담은 `SKILL.md` 파일입니다.

60개 업무 분야에 **308개 Skill**이 있으며, 여러 분야가 **22개 공통 실행 기능**을 공유합니다. 308개의 독립 프로그램이나 모두 실시간 조회가 가능한 서비스라는 뜻은 아닙니다.

[빠른 시작](#빠른-시작) · [전체 Skill 목록](docs/domain-skill-candidates.md) · [Claude Code·Codex 설정](docs/client-quickstart.md) · [기여 안내](#기여하기)

> **현재 사용 범위**
>
> 합성 예제 실행과 지원되는 로컬 파일 검사를 시작할 수 있습니다. 공식 사이트 실시간 조회는 현재 활성화된 출처 정책이 없으며, 실시간 조회 검증을 통과한 기능도 없습니다. 최종 사실 확인·법률 판단·결재·제출·발송을 대신하지 않습니다.

## 무엇을 해결하나요

문서에서 무엇을 확인해야 하는지 정리하고, 자동 검사의 결과와 담당자가 직접 판단해야 할 부분을 구분합니다.

| 업무 | 제공하는 검토 절차와 현재 범위 |
|---|---|
| HWPX 문서를 검토하기 전 | 승인된 로컬 파일의 구역·문자 수와 기본 식별자 검사 상태 확인. 원문 출력·변환·수정은 하지 않음 |
| 공문·보고서 초안을 점검할 때 | 비식별 JSON 입력의 검토 플래그와 수동 확인 항목 제공. 완성된 초안이나 결재 문서를 출력하는 기능은 아님 |
| 법령·판례 인용을 확인할 때 | 공식 기록과 인용 후보의 대조 절차 제공. 현재는 합성 예제 검증만 가능하며 실시간 조회는 차단 |
| 통계·조달·복지 등 업무 근거를 정리할 때 | 분야별 출처·입력 조건·검토 순서 안내. 실제 조회 가능 여부와 증거 수준은 연결된 기능의 정책에 따름 |

## 빠른 시작

Git과 **Python 3.14**가 필요합니다. 재현 기준은 Python **3.14.6**이며, 다른 Python 버전의 동작을 보장하지 않습니다. 실행 코드는 Python 표준 라이브러리만 사용하므로 별도 패키지 설치 없이 저장소 루트에서 실행합니다.

```bash
git clone https://github.com/vertexsquad/k-gov-skills.git
cd k-gov-skills
python3 --version

# 합성 HWPX 예제로 동작 확인
python3 -m kgov_runtime.capabilities.public_document_hwpx --fixture
```

저장소를 내려받은 뒤 위 예제 실행에는 네트워크나 인증정보가 필요하지 않습니다. `--fixture`는 저장소에 포함된 **합성 테스트 데이터**로 입출력 계약을 확인하는 옵션입니다. 성공해도 실제 문서 검사나 공식 원문 조회가 완료된 것은 아닙니다.

출력에서 `text_emitted=false`와 `manual_review_required=true`를 확인할 수 있습니다. 원문을 출력하지 않고 담당자의 검토가 필요하다는 뜻입니다.

### Claude Code·Codex에서 사용하기

[클라이언트 빠른 시작](docs/client-quickstart.md)에 따라 사용할 Skill을 등록한 뒤, 클라이언트의 Skill 목록에서 이름을 확인하고 명시 호출합니다. 전체 저장소가 필요하므로 `SKILL.md` 하나만 복사하지 않습니다. 클라이언트에서 자동 탐색을 지원하지 않으면 같은 문서의 수동 파일 로딩 절차를 사용합니다.

HWPX Skill의 명시 호출 이름은 다음과 같습니다.

- Claude Code: `/government-document-hwpx-review`
- Codex: `$government-document-hwpx-review`

호출 후 다음처럼 요청합니다.

> 합성 `--fixture`만 실행하고 결과를 설명해 줘. 내 문서를 검사했다고 쓰지 말고, 사람이 확인해야 할 항목을 구분해 줘.

실제 로컬 파일 검사는 [HWPX 절차](docs/capabilities/public-document-hwpx/procedure.md) 또는 [행정문서 절차](docs/capabilities/administrative-document-draft-review/procedure.md)의 입력 조건을 먼저 확인하십시오. 인증정보·민원 원문·비공개 개인정보를 대화에 붙여 넣지 않습니다. 클라이언트 사용은 소속 기관의 보안·AI 이용 기준을 따릅니다.

## 내 업무 분야 Skill 찾기

`domains/<업무 분야>/skills/<이름>/SKILL.md`가 진입점입니다. 각 분야마다 최소 5개의 Skill이 있습니다.

| 그룹 | 업무 분야 |
|---|---|
| 국가운영 (11) | 행정 · 재정 · 세무 · 관세 · 감사 · 통계 · 조달 · 외교 · 통일 · 선거관리 · 입법 |
| 법무·치안 (7) | 사법 · 검찰 · 교정 · 보호관찰 · 출입국 · 경찰 · 해양경찰 |
| 안전·국방 (5) | 소방 · 재난안전 · 국방 · 군무 · 경호 |
| 사회서비스 (6) | 교육 · 교육행정 · 사회복지 · 고용노동 · 보건의료 · 식품의약 |
| 농림·해양·환경 (7) | 농업 · 축산 · 농촌지도 · 산림 · 해양수산 · 환경 · 기상 |
| 국토·산업 (7) | 국토교통 · 토목시설 · 건축 · 도시계획 · 산업 · 에너지 · 중소기업 |
| 과학·디지털 (5) | 과학기술 · 특허 · 정보통신 · 전산 · 사이버보안 |
| 문화·지식 (8) | 문화예술 · 체육 · 관광 · 문화유산 · 기록관리 · 도서관 · 학예연구 · 연구 |
| 지역·생활행정 (4) | 지방자치 · 지역개발 · 지방의회 · 우정 |

예를 들어 세무 담당자라면 `domains/세무/skills/` 아래에서 사업자·체납 안내 페이지 메타데이터 확인, 재산세 토지·주택 조회 차단 안내 등 10개 Skill을 볼 수 있습니다. 페이지 메타데이터 확인은 사업자 상태·체납 조회 API가 아니며 현재 출처 정책에 따라 차단됩니다.

308개 Skill 전체 목록과 분야별 매핑은 **[docs/domain-skill-candidates.md](docs/domain-skill-candidates.md)** 에 있습니다.

## 구조와 검증 상태

<details>
<summary>내부 용어와 22개 공통 실행 기능 목록</summary>

### 핵심 개념 4가지

이 저장소를 읽으려면 네 단어만 알면 됩니다.

**1. Domain (업무 분야)** — 단순 분류가 아니라 **Skill의 소유·배포 경계**입니다. 공개 Skill은 반드시 `domains/<domain>/skills/` 아래에 있어야 하고, top-level `skills/` 디렉터리는 만들지 않습니다.

**2. Capability (내부 실행 구현)** — 여러 domain이 공유하는 실제 동작 코드로, `kgov_runtime/capabilities/`에 **한 번만** 구현합니다. domain마다 adapter를 복제하지 않습니다. Skill이 얼굴이라면 capability는 엔진입니다.

**3. Boundary (실행 경계)** — 그 Skill이 어디까지 손대는지입니다.

| 값 | 의미 |
|---|---|
| `read-only` | 조회만 |
| `draft-only` | 초안·검토 결과만 생성, 원본 변경·제출 없음 |
| `manual-review-only` | 공개정보 기반 담당자 수동 검토만 지원 |

Capability의 `side_effect_class`는 Skill 경계와 별도입니다. `document-read`는 로컬 문서 읽기를 뜻하는 capability 분류이며 Skill 경계 값이 아닙니다.

**4. Evidence (근거 강도)** — domain의 `direct`/`adjacent`/`new`/`sensitive`는 **완성도가 아니라 근거 강도와 도입 경계**입니다. 현재 direct 35 · adjacent 16 · new 8 · sensitive 1.

여기에 **검증 상태**가 따로 있습니다. 현재 22개 capability 모두 `fixture-verified`입니다. `live_smoke`는 19개 `not-run`, 3개 `blocked`이며 현재 `passed`는 없습니다. Domain Skill은 연결된 capability보다 강한 검증 상태를 주장하지 않습니다.

### 공통 실행 기능 22개 목록

`Live`는 현재 catalog의 machine status입니다. `blocked`는 정책 또는 workflow 조건이 충족되지 않아 network 전에 차단됨을, `not-run`은 현재 증거가 없음을 뜻합니다. 과거 URL 도달 기록은 현재 `passed`로 승격하지 않습니다.

| Capability | 경계 | Credential | Live |
|---|---|---|---|
| `official-source-research` | read-only | none | blocked |
| `korean-legal-citation-verification` | draft-only | mixed | blocked |
| `public-document-hwpx` | document-read | none | not-run |
| `korean-law-bill-research` | read-only | mixed | not-run |
| `kosis-official-statistics` | read-only | user-held | not-run |
| `public-procurement-research` | read-only | mixed | not-run |
| `disaster-geospatial-brief` | read-only | mixed | not-run |
| `welfare-health-safety-research` | read-only | mixed | not-run |
| `land-housing-geospatial-research` | read-only | mixed | not-run |
| `patent-prior-art-evidence-pack` | read-only | none | not-run |
| `civil-complaint-triage-draft` | draft-only | none | not-run |
| `administrative-document-draft-review` | draft-only | none | not-run |
| `public-policy-evidence-pack` | draft-only | mixed | not-run |
| `public-ai-governance-review` | draft-only | none | not-run |
| `public-it-project-procedure-review` | draft-only | none | not-run |
| `public-record-disclosure-redaction-review` | draft-only | none | not-run |
| `local-ordinance-draft-review` | draft-only | none | not-run |
| `construction-standard-bim-compliance-precheck` | draft-only | none | not-run |
| `building-permit-document-precheck` | draft-only | none | blocked |
| `official-notice-multilingual-translation-review` | draft-only | none | not-run |
| `public-records-lifecycle-review` | draft-only | none | not-run |
| `regulated-trade-procedure-precheck` | draft-only | none | not-run |

각 capability의 입력 필드·종료 코드·공식 endpoint는 `docs/capabilities/<capability>/runtime-contract.md`에 있습니다.

</details>

## 예제: 법령·판례 인용 검증

[`public-administration-legal-citation-verification`](domains/행정/skills/public-administration-legal-citation-verification/SKILL.md)을 예로 전체 흐름을 봅니다. 현재 사용할 수 있는 것은 합성 fixture 계약 검증이며, 국가법령정보 공식 원문 조회는 reviewed policy가 활성화된 경우에만 가능한 draft-only evidence gate입니다.

<details>
<summary>합성 예제와 정책 승인 후의 실행 절차 보기</summary>

### 언제 쓰나요

- 보고서·민원 답변에 법령 조·항·호·목을 인용하기 전
- 판례번호·법원·선고일·판결요지가 실제 공식 판례와 같은지 확인할 때
- 특정 기준일에 적용되는 법령 연혁을 골라야 할 때
- LLM이나 검색 결과가 제시한 법적 근거를 공식 원문으로 재검증할 때

### 실행 순서

**1단계 — fixture로 계약 확인** (네트워크 불필요)

```bash
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification --fixture
```

아래 2~5단계는 **현재 catalog에서는 차단됩니다.** `law-go-kr-drf-api` policy가 reviewed evidence와 함께 활성화되기 전에는 credential을 읽거나 network를 호출하지 않고 exit `3`으로 종료합니다.

**2단계 — 정책 승인 뒤 인증값 설정.** 환경변수로만 설정하고 명령 인수·URL·fixture·로그·커밋에 넣지 않습니다.

```bash
export LAW_OC='사용자 소유 인증값'
```

**3단계 — 공식 목록에서 ID 찾기**

```bash
# 정확한 법령명과 6자리 법령 ID 확인
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
  --search-law --param 'query=개인정보 보호법' --param display=100

# 사건번호로 판례 후보 검색
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
  --search-precedent --param 'nb=2024다12345'

# 선택한 판례일련번호의 metadata 재조회
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification \
  --precedent-id 228541
```

**4단계 — 후보 ledger 작성.** 이름·연락처·민원 원문을 **제거한 뒤** `citations.json`을 준비합니다. 법령은 `law_id`·`article_code`·항·호·목 순번과 실제 인용문을, 판례는 판례일련번호·사건번호·법원·선고일과 실제 인용문을 기록합니다. 전체 JSON 예시는 [procedure 문서](docs/capabilities/korean-legal-citation-verification/procedure.md#입력-예시)에 있습니다.

**5단계 — live 검증 실행**

```bash
python3 -m kgov_runtime.capabilities.korean_legal_citation_verification citations.json
```

**6단계 — 결과 해석**

| 상태 | 조치 |
|---|---|
| `verified-official-live-match` (+ `admission_passed=true`) | 초안용 후보로 사용 가능 |
| `mismatch-blocked` | 자동 수정 금지 — 입력과 공식 원문을 사람이 재확인 |
| `official-source-not-found` | 추정 금지 — 검색 조건부터 재확인 |
| `ambiguous-candidates-manual-selection-required` | 사람이 후보를 직접 선택 |

### 무엇이 달라지나요

| 장점 | 실제로 달라지는 점 |
|---|---|
| 공식 1차 출처 직접 검증 | policy-authorized live 실행에서만 검색 snippet·블로그·LLM 주장 대신 국가법령정보 record를 조회 |
| 잘못된 인용 차단 | 법령 ID·기준일·조·항·호·목과 판례일련번호·사건번호·법원·선고일·인용문이 **함께** 맞아야 통과 |
| 기준일에 맞는 법령 선택 | `as_of_date` 이하 최신 단일 연혁을 선택해 현재법과 과거법을 섞는 위험 감소 |
| 그럴듯한 자동 보완 방지 | 검색 0건·복수 후보·API 오류·metadata 불일치를 추정으로 메우지 않고 fail-closed |
| 개인정보·credential 노출 축소 | 비식별 인용 후보만 입력, 직접 식별자·credential 반사 차단, raw 공식 본문 미출력 |
| 검토 가능한 결과 | 통과·불일치·미존재·모호성 상태와 credential-free 공식 URL을 분리 제공 |
| 모델 독립적 안전장치 | 특정 LLM의 자신감·기억에 의존하지 않는 deterministic 검증 절차 |

### 보증 범위

`verified-official-live-match`가 policy-authorized 실행에서 생성된 경우에만 **그 실행 시점에 조회한 공식 record와 후보 인용의 구조적 일치**를 뜻합니다. 현재 fixture 결과는 이 보증을 제공하지 않습니다.

보증하지 않는 것: 법률 해석, 사실관계 적용, 판례의 현재 효력, 반대·제한 판례 검색의 완전성, 최종 문서의 법적 적합성. 최종 인용·결재·제출·발송은 담당 공무원 또는 법무 검토자가 승인해야 합니다.

세부 입력 필드와 종료 코드는 [runtime contract](docs/capabilities/korean-legal-citation-verification/runtime-contract.md)를 참고하세요.

</details>

## 저장소 구조

```text
catalog/domain-skills.json                     # SSOT — 60 domain · 308 Skill · 22 capability
domains/<한글 domain>/skills/<slug>/SKILL.md   # 공개 Skill 진입점 (생성물)
kgov_runtime/capabilities/<module>.py          # domain 간 공유하는 내부 실행 구현
docs/capabilities/<capability>/                # 절차 · runtime contract · live 증거
docs/domain-skill-candidates.md                # Skill 전체 목록 (생성물)
tests/capabilities/                            # capability별 unit test
tests/fixtures/capabilities/                   # 합성 deterministic fixture
scripts/render_domain_skills.py                # domain Skill 생성기
scripts/render_catalog.py                      # 사람용 catalog 문서 생성기
scripts/validate_catalog.py                    # topology · catalog · instruction 검증기
scripts/check.py                               # 전체 deterministic 검증 진입점
CLAUDE.md                                      # canonical 저장소 작업 계약
AGENTS.md                                      # cross-runtime thin adapter
```

`SKILL.md`와 `docs/domain-skill-candidates.md`는 **생성물이므로 직접 편집하지 않습니다.** catalog를 고치고 renderer를 돌립니다.

## 개발·검증

Python 요구사항과 격리된 개발 도구 설치는 [개발·검증 환경](docs/development.md)을 따릅니다. 클라이언트 버전 요구사항과는 별개입니다.

```bash
# 네트워크·credential 없이 전체 검증
python3 scripts/check.py

# capability 하나의 합성 fixture 실행
python3 -m kgov_runtime.capabilities.kosis_official_statistics --fixture

# 생성물 drift 확인
python3 scripts/render_domain_skills.py --check
python3 scripts/render_catalog.py --check
```

Catalog를 변경했다면 이 순서로 생성물을 갱신합니다.

```bash
python3 scripts/render_domain_skills.py
python3 scripts/render_catalog.py
python3 scripts/check.py
```

실제 live 조회 전에는 `docs/capabilities/<capability>/runtime-contract.md`의 공식 endpoint·환경변수·필수 query parameter를 확인합니다. credential 값은 인자·fixture·로그·저장소에 기록하지 않습니다.

자세한 작업 계약은 [CLAUDE.md](CLAUDE.md)에 있습니다.

기존 개발 checkout에 보존된 `.omo/` 하위 Skill 심볼릭 링크가 있으면, 테스트가 통과해도 마지막 비밀값 검사에서 `secret scan incomplete`로 전체 검증이 중단될 수 있습니다. Git에서 무시하는 파일도 이 검사 대상입니다. 기존 증거를 삭제하거나 검사기를 완화하지 말고, 같은 변경 내용을 담은 깨끗한 checkout 또는 별도 worktree에서 검증하십시오. [검증 환경 제한](docs/development.md#기존-checkout의-검증-제한)을 참고하십시오.

## 기여하기

업무 절차의 누락, 재현 가능한 오류, 이해하기 어려운 설명을 [GitHub Issues](https://github.com/vertexsquad/k-gov-skills/issues)에 제안할 수 있습니다. 해당 Skill 이름, 기대한 결과, 실제 결과, 실행 환경을 함께 작성하십시오. 사례와 첨부 파일은 실제 민원 자료 대신 합성 데이터로 재현하고, 인증정보·개인정보·비공개 업무 자료는 올리지 않습니다.

코드를 변경할 때는 [개발·검증 환경](docs/development.md)과 [작업 계약](CLAUDE.md)을 먼저 확인합니다.

1. 변경하려는 업무 분야와 연결된 공통 실행 기능을 확인합니다.
2. 공개 Skill 변경은 `catalog/domain-skills.json`과 관련 계약에 반영하고 renderer로 생성합니다. 생성된 `SKILL.md`는 직접 수정하지 않습니다.
3. 동작 변경에는 재현 가능한 테스트를 함께 작성하고 `python3 scripts/check.py`를 실행합니다.
4. PR에 변경 이유·범위·실행한 검증을 적고, 합성 예제 통과와 실제 조회 성공을 구분합니다.

## 증거를 읽는 법

이 저장소는 다음 다섯 차원을 서로 대체하지 않습니다.

| 차원 | 확인하는 것 | 확인하지 않는 것 |
|---|---|---|
| Fixture contract | 합성 입력의 CLI·schema·exit 계약 | URL 도달, 실제 자료, 현재성 |
| URL reachability | 특정 시점의 HTTP 응답 | policy 승인, 내용의 정확성·이용허락 |
| Policy-authorized live retrieval | exact operation과 reviewed policy에 따른 조회 및 receipt | 법적 이용허락, 사실·법률 판단 |
| Substantive correctness | 담당자의 내용·맥락·최신성 검토 | 저작권·약관 승인 |
| Human/legal approval | 권한 있는 담당자의 이용·공개·제출 결정 | runtime이 대신할 수 있는 자동 판정 |

`robots.txt`는 접근에 관한 신호일 뿐 저작권이나 약관상 이용허락이 아닙니다. `source_receipt`도 operation·policy·응답 처리 이력을 기록할 뿐 법률 판단이나 cryptographic authenticity를 증명하지 않습니다. 자세한 기준은 [source usage policy](docs/source-usage-policy.md)를 확인하십시오.

## 안전 경계와 외부 reference

- 비밀값·인증정보·원문 개인정보를 소스·fixture·로그·결과에 저장하지 않습니다.
- 예약·결제·제출·메시지·문서 원본 변경·민감 경호업무는 명시 승인과 manual handoff 없이 자동화하지 않습니다.
- fixture 성공, URL 도달, live API 성공을 같은 증거로 표현하지 않습니다.
- 직접 식별자 scan의 no-match는 완전한 비식별 증명이 아닙니다.
- Runtime은 stdout redirection, downstream copy, backup, caller database를 지우거나 secure memory·SSD deletion을 보증할 수 없습니다.
- `mouseco/k-gov-skills`, `NomaDamas/k-skill`, `legalize-kr/agent-skills`, `Sungmin-Cho/skill-legal-kr`는 **별개 프로젝트**이며 참고 자료로만 사용합니다. 외부 코드·프롬프트·문서를 복사하거나 미러링하지 않습니다.
- adapter 변경 전 공식 API·이용약관·인증정보 소유자·proxy·개인정보·side effect를 재검증합니다.

## 라이선스

현재 저장소에는 라이선스 파일이 없습니다. **오픈소스로 배포하기 전에 라이선스와 적용 범위를 확정해야 합니다.** 저장소가 공개되어 있다는 사실만으로 사용·수정·재배포 권한이 부여되는 것은 아닙니다.

외부 공공자료의 이용조건은 이 저장소의 라이선스와 별개입니다. [외부 자료 이용 정책](docs/source-usage-policy.md)을 확인하십시오.

GitHub 저장소 소개란에 사용할 한글 문구와 추천 주제 태그는 [About 문안](docs/about.md)에 정리했습니다.
