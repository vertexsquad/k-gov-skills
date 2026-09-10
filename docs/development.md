# 개발·검증 환경

지원하는 개발 환경은 Python 3.14 계열입니다. 재현 기준은 CPython **3.14.6**,
uv **0.12.5**, Ruff **0.15.10**입니다. 설치와 린트는 macOS arm64에서 검증했으며,
다른 Python 버전과 Linux CI 실행 환경은 로컬에서 검증하지 않았습니다.
`pyproject.toml`에 Python 버전 범위와 개발 도구의 고정 버전을 선언합니다.
실행 코드는 표준 라이브러리만 사용하며, 패키지로 빌드하거나 설치하지 않고
전체 저장소의 루트에서 직접 실행합니다. Ruff는 기본 E4, E7, E9, F 규칙을 유지합니다.

## 격리된 개발 환경 설치

Python 3.14.6을 설치한 뒤 POSIX 셸에서 저장소 루트를 기준으로 실행합니다.
개발 도구 설치에는 Python 패키지 인덱스 접근이 필요하지만,
합성 테스트 데이터(fixture) 검증에는 외부 자료 조회나 인증정보가 필요하지 않습니다.

```sh
python3 --version  # Python 3.14.6인지 확인합니다.
dev_dir=$(mktemp -d "${TMPDIR:-/tmp}/kgov-dev.XXXXXX")
python3 -m venv "$dev_dir/venv"
. "$dev_dir/venv/bin/activate"
export PIP_CACHE_DIR="$dev_dir/pip-cache"
export UV_CACHE_DIR="$dev_dir/uv-cache"
export RUFF_CACHE_DIR="$dev_dir/ruff-cache"
python3 -m pip install 'uv==0.12.5'
uv pip install --group dev
uv --version
python3 -m ruff --version
```

가상환경과 캐시는 저장소 밖에 둡니다. 검사기는 가상환경의 인터프리터 링크를
포함해 예상하지 못한 심볼릭 링크가 있으면 검증을 중단합니다.
이 설치 절차는 `uv sync`나 잠금 파일을 사용하지 않으며 저장소 안에 `.venv`를 만들지 않습니다.

## 검증

가상환경을 활성화한 상태에서 저장소 루트를 기준으로 실행합니다.

```sh
python3 -m ruff check .
python3 scripts/check.py
```

`scripts/check.py`는 정본 검증 명령입니다. 생성물, catalog 계약, unittest 테스트,
공통 실행 기능의 합성 예제, 컴파일, 비밀값 패턴, diff 공백을 검사합니다.
별도의 fixture 실행 명령을 추가할 필요는 없습니다.

Catalog 회귀 테스트는 Git 인덱스에 등록된 경로를 현재 작업 파일 내용으로 복사합니다
(#58 계약). 새 입력 파일, 특히 실행 모듈과 테스트는 전체 검증 전에 Git 인덱스에
등록해야 합니다. 추적되지 않는 파일은 복사되지 않습니다.
스테이징이 승인된 경우에만 의도한 경로를 등록하십시오.
CI는 파일이 이미 인덱스에 등록된 커밋 상태를 검사합니다.

Fixture 실행은 Python 수준의 DNS·소켓 차단 장치를 사용합니다.
**운영체제·네이티브 코드·하위 프로세스를 격리하는 샌드박스가 아니므로**
신뢰할 수 없는 코드를 실행하는 용도로 사용하지 않습니다.
Fixture 성공은 실제 API 접근이나 URL 도달의 증거가 아닙니다.

`.github/workflows/check.yml`은 Ubuntu에서 같은 설치·검증 명령을 사용하도록
정의되어 있습니다. 저장소 권한은 읽기 전용이며 checkout 인증정보를 보존하지 않습니다.
원격 CI 게시·활성화·실행 요청과 저장소 보호 설정 변경은 별도 승인이 필요합니다.

## 기존 checkout의 검증 제한

2026-09-10 로컬 검증에서는 테스트와 합성 예제가 통과한 뒤, 기존
`.omo/wave3-dual-client-20260908/` 아래 보존된 Skill 심볼릭 링크 때문에
비밀값 검사가 `secret scan incomplete`로 중단됐습니다.
Git에서 무시하는 `.omo/` 경로도 정본 검사기의 검사 대상이며, 이 결과는 전체 검증 통과가 아닙니다.

기존 증거 파일을 지우거나 검사 제외 규칙을 추가하지 않습니다.
같은 변경 내용을 담은 깨끗한 checkout 또는 별도 worktree에서 정본 검증을 실행하고,
원래 checkout의 차단 결과와 구분해 보고하십시오. 가상환경·클라이언트 등록 링크·검증 기록은
검증할 checkout 밖에 두어야 합니다.
