#!/usr/bin/env python3
"""Run deterministic repository checks without network access or credentials."""

from __future__ import annotations

import json
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
        if not path.is_file() or any(part in {".git", ".ruff_cache", "__pycache__"} for part in path.parts):
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
    run([python, "scripts/render_domain_skills.py", "--check"])
    run([python, "scripts/render_catalog.py", "--check"])
    run([python, "scripts/validate_catalog.py"])

    root_suites = 0
    for test_file in sorted((ROOT / "tests").glob("test_*.py")):
        run([python, "-m", "unittest", f"tests.{test_file.stem}", "-v"])
        root_suites += 1

    data = json.loads((ROOT / "catalog/domain-skills.json").read_text(encoding="utf-8"))
    capability_suites = 0
    for capability in sorted(data["shared_capabilities"], key=lambda item: item["slug"]):
        slug = capability["slug"]
        module = slug.replace("-", "_")
        run([python, "-m", "unittest", f"tests.capabilities.test_{module}", "-v"])
        run([python, "-m", f"kgov_runtime.capabilities.{module}", "--fixture"], quiet=True)
        capability_suites += 1

    run([python, "-m", "compileall", "-q", "kgov_runtime", "scripts", "tests"])
    scan_secrets()
    if (ROOT / ".git").exists():
        run(["git", "diff", "--check"])
    print(
        f"CHECK PASS root_suites={root_suites} capability_suites={capability_suites} "
        f"fixtures={capability_suites} domain_skills={sum(len(item['skills']) for item in data['domains'])} secret_hits=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
