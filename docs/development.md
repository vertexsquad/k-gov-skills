# Development and verification

The supported development series is Python 3.14. The reproducible baseline is
CPython **3.14.6**, uv **0.12.5**, and Ruff **0.15.10**. Setup and lint were tested
on macOS arm64; other Python versions and the Linux CI runner are not locally
verified. `pyproject.toml` declares the Python series and pinned development
tools. The standard-library runtime runs directly from the checkout; it is not
built or installed as a package. Ruff retains its default E4, E7, E9 and F rules.

## Isolated setup

Install Python 3.14.6, then run from the repository root in a POSIX shell.
Package installation needs access to the Python package index; fixture checking
does not need live-source access or credentials.

```sh
python3 --version  # Must report Python 3.14.6.
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

Keep the venv and caches outside the checkout. The checker rejects unexpected
symlinks, including venv interpreter links. This installation uses neither
`uv sync` nor a lockfile and does not create a repository `.venv`.

## Verification

Run these commands from the repository root with the venv still active:

```sh
python3 -m ruff check .
python3 scripts/check.py
```

`scripts/check.py` is the canonical verification interface: it checks generated
files, catalog contracts, unittest suites, capability fixtures, compilation,
secret patterns and diff whitespace. No separate fixture-runner CLI is needed.

Catalog regression tests copy Git-indexed paths using working-tree contents
(the #58 contract). New input files, especially runtime modules and tests, must
be added to the Git index before full verification; untracked files are not
copied. Stage only the intended paths when staging is authorized. CI checks a
committed checkout, where those files are already indexed.

Fixture execution uses a Python-level DNS/socket guard. It is **not an OS,
native-code, or subprocess sandbox** and is not safe for executing untrusted
code. Fixture success is not evidence of live API access or URL reachability.

`.github/workflows/check.yml` uses the same setup and verification commands on
Ubuntu with read-only repository permissions and no stored checkout credentials.
Publishing or activating this new remote CI, triggering runs, and changing
repository protection settings require separate user approval.
