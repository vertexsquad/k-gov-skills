# Agent entrypoint

작업 전에 root `CLAUDE.md` 전체를 읽고 canonical 계약으로 따릅니다.

- 공개 Skill은 `domains/<domain>/skills/` 아래에서만 소유합니다.
- top-level `skills/` 생성·복구는 금지합니다.
- Catalog SSOT는 `catalog/domain-skills.json`입니다.
- 공통 구현은 `kgov_runtime/capabilities/`에 한 번만 둡니다.
- 생성된 domain `SKILL.md`는 renderer로만 갱신합니다.
- 비밀값·개인정보를 저장하지 않고 side effect는 명시적 승인 없이는 실행하지 않습니다.
- 완료 전 `python3 scripts/check.py`를 실행합니다.
