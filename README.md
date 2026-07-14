# k-gov-skills

한국 공무원의 **업무 분야(domain)**별 반복 업무를 안전한 Agent Skill로 패키징하는 독립 프로젝트입니다.

## 구조

```text
catalog/domain-skills.json          # 60개 domain과 Skill 후보의 단일 원본
skills/<shared-capability>/SKILL.md # 여러 domain이 공유하는 실행 계약
scripts/render_catalog.py           # 사람용 후보 문서 생성
scripts/validate_catalog.py         # taxonomy·catalog·Skill·문서 정합성 검증
scripts/check.py                    # 전체 deterministic 검증 진입점
kgov_runtime/                       # HTTPS·allowlist·응답크기 공통 안전 계층
docs/domain-skill-candidates.md     # 생성된 전체 후보표
domains/<한글 domain>/              # 업무 분야 taxonomy
```

`domain`은 법적 임용·직렬 분류가 아니라 실제 공무 수행 분야를 뜻합니다. 하나의 Skill은 여러 domain에서 공유할 수 있고, domain별 차이는 검증된 반복 업무가 생길 때 얇은 wrapper로 추가합니다.

Catalog schema v3에서 `shared_capability`는 domain의 기본 capability이고, 선택적 `additional_capabilities`는 기본 후보를 대체하지 않는 교차 domain workflow입니다. 추가 capability의 credential·side effect·manual handoff 경계는 공통 capability runtime manifest를 따릅니다.

## 현재 구현

현재 다음 9개 공통 capability와 read-only/draft-only adapter를 제공합니다.

- `public-document-hwpx`
- `korean-law-bill-research`
- `kosis-official-statistics`
- `public-procurement-research`
- `disaster-geospatial-brief`
- `welfare-health-safety-research`
- `land-housing-geospatial-research`
- `official-source-research`
- `civil-complaint-triage-draft`

60개 domain 후보는 `direct`, `adjacent`, `new`, `sensitive`로 구분합니다. 이는 구현 완료도가 아니라 **근거 강도와 도입 경계**입니다.

각 capability는 `scripts/adapter.py`, `tests/test_adapter.py`, `fixtures/sample.json`,
`references/runtime-contract.md`를 가집니다. 현재 상태는 credential이 필요한 6개 API adapter, HWPX,
민원 draft admission adapter가 `fixture-verified / live_smoke: not-run`, `official-source-research`가
`live-verified / live_smoke: passed`입니다. fixture 성공을 공식 endpoint·credential 검증으로 해석하지 않습니다.

```bash
# 네트워크·credential 없이 모든 adapter의 deterministic fixture 실행
python3 scripts/check.py

# capability 하나의 fixture 실행; live 전 runtime-contract.md를 검토
python3 skills/kosis-official-statistics/scripts/adapter.py --fixture
```

실제 조회는 각 runtime contract의 공식 endpoint, 환경변수, 필수 query parameter를
확인한 뒤 실행합니다. credential 값은 인자·fixture·로그·저장소에 기록하지 않습니다.

## 검증

```bash
python3 scripts/render_catalog.py
python3 scripts/validate_catalog.py
python3 -m unittest discover -s tests -v
python3 scripts/check.py
```

## 외부 reference 경계

- `mouseco/k-gov-skills`와 `NomaDamas/k-skill`은 별개 프로젝트이며 참고 자료로만 사용합니다.
- 외부 코드·프롬프트·문서를 복사하거나 미러링하지 않습니다.
- 실제 adapter 구현 전 공식 API, 이용약관, 인증정보 소유자, proxy, 개인정보, side effect를 다시 검증합니다.
- 예약·결제·제출·메시지·문서 원본 변경·민감 경호업무는 명시 승인과 manual handoff 없이는 자동화하지 않습니다.
