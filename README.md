# k-gov-skills

한국 공무원의 **업무 분야(domain)**별 반복 업무를 안전한 Agent Skill로 패키징하는 독립 프로젝트입니다.

## 구조

```text
catalog/domain-skills.json                     # 60 domain·66 Skill·11 capability SSOT
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

Catalog schema v4의 domain `skills[]`는 `primary` 하나와 선택적 `additional` Skill을 명시합니다.
모든 `name`은 저장소 전체에서 고유합니다. 60개 domain에 primary 60개와 additional 6개,
총 66개 domain-owned Skill 진입점이 있습니다.

## 현재 capability

다음 11개 read-only/document-read/draft-only 내부 capability를 제공합니다.

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

Domain의 `direct`, `adjacent`, `new`, `sensitive`는 구현 완료도가 아니라 **근거 강도와 도입 경계**입니다.
10개 capability는 `fixture-verified / live_smoke: not-run`이고 `official-source-research`만
`live-verified / live_smoke: passed`입니다. Domain Skill은 연결된 capability보다 강한 검증 상태를
주장하지 않습니다.

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

- `mouseco/k-gov-skills`와 `NomaDamas/k-skill`은 별개 프로젝트이며 참고 자료로만 사용합니다.
- 외부 코드·프롬프트·문서를 복사하거나 미러링하지 않습니다.
- 실제 adapter 변경 전 공식 API, 이용약관, 인증정보 소유자, proxy, 개인정보, side effect를 재검증합니다.
- 예약·결제·제출·메시지·문서 원본 변경·민감 경호업무는 명시 승인과 manual handoff 없이는 자동화하지 않습니다.
