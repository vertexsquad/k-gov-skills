# Claude Code·Codex 빠른 시작

두 클라이언트가 같은 `domains/<domain>/skills/<slug>/SKILL.md`를 읽고 같은 Python 모듈을 실행합니다. 클라이언트별 adapter, hook, 버전 분기는 없습니다. frontmatter의 `metadata`는 Agent Skills 규격에 맞춘 문자열 키·문자열 값 map입니다.

특정 클라이언트 버전을 필수 조건으로 고정하지 않습니다. 설치된 클라이언트에서 native Skill 탐색·명시 호출을 확인하고, 해당 기능이 없으면 아래 수동 파일 로딩을 사용합니다. 모든 과거·미래 릴리스에서 native 동작을 보장한다는 뜻은 아닙니다. 아래 설정 안내 자체는 실제 클라이언트 QA 통과 증거가 아닙니다. Python 요구사항과 개발 도구 설치는 별도 [개발·검증 환경](development.md)을 따릅니다.

## 1. 전체 checkout 준비

```bash
git clone https://github.com/vertexsquad/k-gov-skills.git
cd k-gov-skills
repo="$(pwd -P)"
```

이미 clone했다면 그 저장소 루트에서 `repo="$(pwd -P)"`만 설정합니다. 이후 명령은 같은 셸에서 실행합니다. `kgov_runtime/`, `docs/`, `tests/`, `catalog/`가 필요하므로 Skill 디렉터리만 다운로드하거나 복사하지 않습니다. checkout을 이동하면 등록 링크도 새 절대 경로로 다시 연결해야 합니다.

## 2. 사용자 수준 등록: 사용할 클라이언트만 선택

다음은 사용자가 직접 실행하는 선택적 설정 명령입니다. checkout **밖**의 사용자 디렉터리에 두 대표 Skill의 **디렉터리 symlink**를 만듭니다. `SKILL.md` 자체를 링크하거나 전체 `domains/`를 한 Skill처럼 등록하지 않습니다. 같은 이름이 이미 있으면 기존 대상을 먼저 확인하고 중복 등록·덮어쓰기를 하지 마세요. 다른 Skill도 catalog의 canonical 디렉터리를 같은 방식으로 연결합니다.

### Claude Code

```bash
mkdir -p "$HOME/.claude/skills"
ln -s "$repo/domains/행정/skills/government-document-hwpx-review" "$HOME/.claude/skills/"
ln -s "$repo/domains/행정/skills/public-administration-administrative-document-draft-review" "$HOME/.claude/skills/"
cd "$repo"
claude
```

새 세션에서 `/` 명령 목록에 이름이 나타나는지 확인하고 `/government-document-hwpx-review` 또는 `/public-administration-administrative-document-draft-review`로 명시 호출합니다. 목록에 보이지 않으면 실제 링크 대상과 설치된 클라이언트의 Skill 탐색 설정을 확인합니다. 발견되지 않은 Skill을 이름만 언급한 응답은 native 로딩 증거가 아닙니다.

### Codex

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$repo/domains/행정/skills/government-document-hwpx-review" "$HOME/.agents/skills/"
ln -s "$repo/domains/행정/skills/public-administration-administrative-document-draft-review" "$HOME/.agents/skills/"
cd "$repo"
codex
```

Skill 선택 목록에서 이름을 확인하고 `$government-document-hwpx-review` 또는 `$public-administration-administrative-document-draft-review`로 명시 호출합니다. 등록 후 반영되지 않으면 새 세션에서 탐색을 확인합니다.

현재 공식 사용자 경로는 `~/.agents/skills`입니다. **설치된 Codex의 실제 탐색 결과가 legacy `~/.codex/skills` 사용을 입증할 때만** 그 경로를 대신 사용합니다. 두 경로에 같은 Skill을 중복 등록하지 않습니다. 탐색 경로를 확인할 수 없으면 여러 위치에 무작정 복제하지 말고 수동 로딩을 사용합니다.

### checkout 안에 프로젝트 등록 링크를 두지 않는 이유

클라이언트는 프로젝트 수준 Skill 경로도 제공하지만, 이 저장소의 fail-closed scanner는 checkout 안의 예상하지 못한 symlink를 읽지 않고 검증을 중단합니다. `.claude/skills/`나 `.agents/skills/` 아래의 프로젝트 등록 symlink도 충돌합니다. scanner를 완화하거나 제외 규칙을 추가하지 말고 위 사용자 수준 경로를 checkout 밖에 둡니다. 두 클라이언트 모두 **전체 checkout 루트에서** 시작해야 합니다.

## 3. fixture와 실제 입력을 구분해 요청

등록한 Skill을 명시 호출한 뒤 입력 종류를 함께 알려 주세요.

- 계약 확인: “합성 `--fixture`만 실행하고 fixture 증거로 보고해 줘. 내 파일을 검증했다고 쓰지 마.”
- 실제 HWPX: “읽기를 승인한 로컬 HWPX 경로를 제공할게. 전체 checkout 루트에서 procedure를 읽고 해당 파일만 검사해 줘. fixture로 대체하거나 원문을 출력하지 마.”
- 실제 행정문서: “비식별 JSON 파일 경로를 제공할게. procedure의 입력 제한에 따라 로컬 검사를 실행하고 검토 플래그만 보고해 줘. 초안 내용의 정확성·결재 완료를 선언하지 마.”

실제 파일은 `--fixture` 없이 기존 CLI에 경로를 전달합니다. 아래 경로는 예시이므로 승인된 실제 파일 경로로 바꿉니다.

```bash
python3 -m kgov_runtime.capabilities.public_document_hwpx "/absolute/path/document.hwpx"
python3 -m kgov_runtime.capabilities.administrative_document_draft_review "/absolute/path/redacted-document.json"
```

[HWPX 절차](capabilities/public-document-hwpx/procedure.md)와 [행정문서 절차](capabilities/administrative-document-draft-review/procedure.md)의 형식·차단 조건을 먼저 확인합니다. 파일이 없거나 읽을 수 없으면 그 실패를 보고합니다. Skill의 fenced runtime binding, `fixed_input`, 예시 결과는 합성 fixture 계약으로 유지되며 실제 입력 검사 결과가 아닙니다. 로컬 검사 성공은 공식 원문 live 조회, 완전한 비식별, 최종 내용 승인과도 다릅니다.

## 4. native 탐색이 없을 때: 명시적 수동 파일 로딩

이는 **native Skill 등록·자동 발견·명령 호출이 아니라 일반 파일 읽기를 통한 fallback**입니다. 저장소 파일을 읽고 명령을 실행할 수 있는 클라이언트를 checkout 루트에서 시작한 뒤 다음처럼 요청합니다.

> `CLAUDE.md`와 `domains/행정/skills/government-document-hwpx-review/SKILL.md`를 직접 읽어 줘. Skill 본문의 경로는 전체 checkout 루트 기준으로 해석하고 연결된 procedure와 runtime contract도 읽어 줘. 이번에는 합성 fixture만 실행하고 수동 파일 로딩으로 수행했다고 밝혀 줘.

행정문서는 위 경로를 `domains/행정/skills/public-administration-administrative-document-draft-review/SKILL.md`로 바꿉니다. 실제 입력은 승인된 파일 경로를 별도로 제공하며 fixture 요청과 섞지 않습니다. 파일 읽기나 명령 실행 권한이 없다면 실행했다고 주장하지 말고 사용자가 루트에서 CLI를 직접 실행합니다.

## 공식 기준

- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Codex Skills](https://developers.openai.com/codex/skills)
- [Agent Skills specification](https://agentskills.io/specification)
