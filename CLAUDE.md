# k-gov-skills 프로젝트 계약

이 문서는 저장소 작업의 canonical agent instruction입니다. `AGENTS.md`는 이 문서를 가리키는 얇은 adapter입니다.

## 권위와 경로

- Catalog SSOT: `catalog/domain-skills.json`
- Public Skill entrypoint: `domains/<domain>/skills/<unique-slug>/SKILL.md`
- 내부 공통 구현: `kgov_runtime/capabilities/`
- Capability 문서 root: `docs/capabilities/`
- 전체 검증 entrypoint: `python3 scripts/check.py`

## Domain 소유 규칙

1. 모든 공개 Skill은 해당 업무 domain의 `skills/` 하위에 둡니다.
2. 별도 top-level `skills/` 제품 표면을 만들거나 복구하지 않습니다.
3. 공통 실행 코드는 내부 runtime에서 한 번만 구현하고 domain마다 adapter 코드를 복제하지 않습니다.
4. 모든 Skill frontmatter `name`은 저장소 전체에서 고유해야 합니다.
5. `domains/*/.gitkeep` 같은 빈 domain placeholder를 두지 않습니다.

## 변경 절차

1. 먼저 catalog의 domain `skills[]`와 capability manifest를 수정합니다.
2. `python3 scripts/render_domain_skills.py`와 `python3 scripts/render_catalog.py`로 생성물을 갱신합니다.
3. 생성된 `SKILL.md`와 `docs/domain-skill-candidates.md`는 직접 편집하지 않습니다.
4. capability adapter·fixture·test·procedure·runtime contract를 함께 변경합니다.
5. fixture 성공, URL 도달, live API 성공을 같은 증거로 표현하지 않습니다.
6. 외부 reference 이름은 capability 근거일 뿐이며 코드·프롬프트 복사 허가가 아닙니다.

## 안전 경계

- 비밀값, 인증정보, 원문 개인정보를 소스·fixture·로그·결과에 저장하지 않습니다.
- 원본 변경, 제출, 결재, 발송, 계약, 투찰 등 side effect는 주인님의 명시적 승인 없이 실행하지 않습니다.
- live 실행은 manifest의 credential·proxy·허용 host·manual handoff 경계를 유지합니다.
- `sensitive` domain은 공개정보 기반 manual-review-only 경계를 약화하지 않습니다.

## 허용·금지 표면

- Allowed writes: 현재 작업 범위의 catalog, domain Skill 생성물, internal runtime, tests, docs, verifier.
- Forbidden reads: credential 값, 비공개 개인정보 원문, 승인되지 않은 외부 저장소의 비밀·운영 데이터.
- GitHub push·PR·merge·배포는 별도 명시 승인이 없는 한 수행하지 않습니다.

## 완료 전 검증

```bash
python3 scripts/render_domain_skills.py --check
python3 scripts/render_catalog.py --check
python3 scripts/check.py
python3 -m ruff check .
git diff --check
```

Validator 오류를 무시하거나 instruction 문구만 바꾸어 우회하지 않습니다.
