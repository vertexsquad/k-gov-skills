#!/usr/bin/env python3
"""Run deterministic repository checks without network access or credentials."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def run(command: list[str], *, quiet: bool = False) -> None:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL if quiet else None,
    )
    if result.returncode:
        raise SystemExit(result.returncode)


def scan_secrets() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            body = path.read_bytes()
        except OSError:
            continue
        if any(pattern.search(body) for pattern in SECRET_PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    if hits:
        raise SystemExit(f"secret pattern hits: {', '.join(sorted(hits))}")


def main() -> int:
    python = sys.executable
    run([python, "scripts/validate_catalog.py"])
    run([python, "-m", "unittest", "discover", "-s", "tests", "-v"])
    suites = 0
    for skill_dir in sorted((ROOT / "skills").iterdir()):
        test_file = skill_dir / "tests" / "test_adapter.py"
        if not test_file.is_file():
            continue
        run([python, "-m", "unittest", "discover", "-s", str(test_file.parent), "-v"])
        run([python, str(skill_dir / "scripts" / "adapter.py"), "--fixture"], quiet=True)
        suites += 1
    run([python, "-m", "compileall", "-q", "kgov_runtime", "scripts", "tests", "skills"])
    scan_secrets()
    if (ROOT / ".git").exists():
        run(["git", "diff", "--check"])
    print(f"CHECK PASS root_suite=1 adapter_suites={suites} fixtures={suites} secret_hits=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
