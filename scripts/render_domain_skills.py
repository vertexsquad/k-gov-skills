#!/usr/bin/env python3
"""Render domain-owned Agent Skill entrypoints from the catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERATED_MARKER = "<!-- generated from catalog/domain-skills.json; do not edit -->"


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def module_name(capability: str) -> str:
    return capability.replace("-", "_")


def render_domain_skill(
    domain: dict[str, Any],
    skill: dict[str, Any],
    capability: dict[str, Any],
) -> str:
    name = skill["name"]
    capability_slug = skill["capability"]
    description = (
        f"{domain['domain']} 업무의 {skill['title']} 절차. "
        f"내부 {capability_slug} capability를 사용하며 {skill['boundary']} 경계를 지킵니다."
    )
    references = skill["reference_skills"]
    reference_line = ", ".join(f"`{item}`" for item in references) if references else "없음"
    task_checks = skill.get("task_checks", [])
    procedure_path = f"docs/capabilities/{capability_slug}/procedure.md"
    contract_path = f"docs/capabilities/{capability_slug}/runtime-contract.md"
    command = f"python3 -m kgov_runtime.capabilities.{module_name(capability_slug)} --fixture"
    lines = [
        "---",
        f"name: {name}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "metadata:",
        "  kgov:",
        f"    domain: {json.dumps(domain['domain'], ensure_ascii=False)}",
        f"    capability: {capability_slug}",
        f"    role: {skill['role']}",
        "---",
        "",
        GENERATED_MARKER,
        "",
        f"# {skill['title']}",
        "",
        f"- Domain: **{domain['domain']}**",
        f"- 내부 capability: `{capability_slug}`",
        f"- 실행 상태: `{capability['execution_status']}` / live smoke `{capability['live_smoke']}`",
        f"- 실행 경계: `{skill['boundary']}`",
        f"- Reference Skill: {reference_line}",
        "",
    ]
    if task_checks:
        lines.extend(
            [
                "## 업무별 추가 체크",
                "",
                *(f"- {check}" for check in task_checks),
                "",
            ]
        )
    lines.extend(
        [
        "## 절차",
        "",
        f"1. 저장소 루트에서 `{procedure_path}`와 `{contract_path}`를 먼저 읽습니다.",
        f"2. `{command}`로 합성 fixture 계약을 검증합니다.",
        "3. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.",
        f"4. {capability['manual_handoff_gate']}",
        "5. fixture 성공, URL 도달, live 검증을 서로 다른 증거로 보고합니다.",
        "",
        "## 금지",
        "",
        "- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.",
        "- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.",
        "- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.",
        "",
        ]
    )
    return "\n".join(lines)


def expected_domain_skills(data: dict[str, Any], root: Path = ROOT) -> dict[Path, str]:
    capabilities = {item["slug"]: item for item in data["shared_capabilities"]}
    expected: dict[Path, str] = {}
    for domain in data["domains"]:
        for skill in domain["skills"]:
            path = root / "domains" / domain["domain"] / "skills" / skill["name"] / "SKILL.md"
            expected[path] = render_domain_skill(domain, skill, capabilities[skill["capability"]])
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when generated Skill entrypoints are missing or stale")
    args = parser.parse_args()
    data = load_catalog(ROOT / "catalog/domain-skills.json")
    expected = expected_domain_skills(data)
    stale = [path for path, content in expected.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if stale:
            for path in stale:
                print(f"ERROR stale domain Skill: {path.relative_to(ROOT)}")
            return 1
        print(f"PASS domain_skills={len(expected)}")
        return 0
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"rendered_domain_skills={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
