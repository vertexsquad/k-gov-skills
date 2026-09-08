#!/usr/bin/env python3
"""Run deterministic repository checks without network access or credentials."""

from __future__ import annotations

import json
import os
import re
import stat
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


def check_diff_whitespace() -> None:
    result = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    detail = f"{result.stdout}{result.stderr}"
    if "mmap failed: Resource deadlock avoided" not in detail:
        raise SystemExit(detail.strip() or "git diff --check failed")

    # iCloud-backed checkouts can fail before Git reads the diff index. Keep the
    # whitespace gate fail-closed by checking every modified tracked file
    # directly, while preserving any other Git failure as a hard error.
    listed = subprocess.run(
        ["git", "ls-files", "-m", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    bad: list[str] = []
    for raw_path in listed.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = ROOT / os.fsdecode(raw_path)
        try:
            body = path.read_bytes()
        except OSError as exc:
            raise SystemExit(f"cannot read modified file for whitespace check: {path}: {exc}") from exc
        if any(line.rstrip(b" \t") != line for line in body.splitlines()):
            bad.append(str(path.relative_to(ROOT)))
    if bad:
        raise SystemExit(f"trailing whitespace: {', '.join(sorted(bad))}")
    print("WARN git diff --check unavailable on iCloud index; direct modified-file check passed", file=sys.stderr)

def scan_secrets() -> None:
    def walk_error(error: OSError) -> None:
        relative = Path(error.filename or ROOT).relative_to(ROOT)
        raise SystemExit(f"secret scan incomplete: {relative}") from None

    hits: list[str] = []
    excluded = {".git", ".ruff_cache", "__pycache__"}
    for directory, dirs, files in os.walk(ROOT, onerror=walk_error, followlinks=False):
        dirs[:] = [name for name in dirs if name not in excluded]
        for name in sorted(dirs + files):
            if name in excluded:
                continue
            path = Path(directory) / name
            relative = path.relative_to(ROOT)
            try:
                mode = path.lstat().st_mode
                if stat.S_ISDIR(mode):
                    continue
                if not stat.S_ISREG(mode):
                    raise SystemExit(f"secret scan incomplete: {relative}")
                body = path.read_bytes()
            except OSError:
                raise SystemExit(f"secret scan incomplete: {relative}") from None
            if any(pattern.search(body) for pattern in SECRET_PATTERNS):
                hits.append(str(relative))
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
        check_diff_whitespace()
    print(
        f"CHECK PASS root_suites={root_suites} capability_suites={capability_suites} "
        f"fixtures={capability_suites} domain_skills={sum(len(item['skills']) for item in data['domains'])} secret_hits=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
