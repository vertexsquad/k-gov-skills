#!/usr/bin/env python3
"""Render the machine-readable domain-owned Skill catalog as Markdown."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

GROUP_ORDER = [
    "국가운영",
    "법무·치안",
    "안전·국방",
    "사회서비스",
    "농림·해양·환경",
    "국토·산업",
    "과학·디지털",
    "문화·지식",
    "지역·생활행정",
]
EVIDENCE_LABELS = {
    "direct": "직접 reference 확인",
    "adjacent": "인접 capability 활용",
    "new": "신규 설계 필요",
    "sensitive": "민감업무 제한",
}


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_catalog(data: dict[str, Any]) -> str:
    domains = data["domains"]
    counts = Counter(item["evidence"] for item in domains)
    skills = [skill for domain in domains for skill in domain["skills"]]
    role_counts = Counter(skill["role"] for skill in skills)
    lines = [
        "# Domain별 Skill",
        "",
        "> 이 문서는 `catalog/domain-skills.json`에서 생성합니다. 직접 편집하지 마세요.",
        "> 공개 Skill은 `domains/<domain>/skills/<unique-slug>/SKILL.md`만 소유합니다.",
        "> 공통 구현은 `kgov_runtime/capabilities/`에 있고 top-level `skills/`는 금지합니다.",
        "",
        "## 요약",
        "",
        f"- 전체 domain: **{len(domains)}개**",
        f"- domain-owned Skill: **{len(skills)}개** (primary {role_counts['primary']} / additional {role_counts['additional']})",
        f"- 직접 reference 확인: **{counts['direct']}개**",
        f"- 인접 capability 활용: **{counts['adjacent']}개**",
        f"- 신규 설계 필요: **{counts['new']}개**",
        f"- 민감업무 제한: **{counts['sensitive']}개**",
        f"- 내부 공통 capability: **{len(data['shared_capabilities'])}개**",
        "- Domain Skill의 live 검증 상태는 연결된 capability manifest보다 강하게 주장하지 않습니다.",
        "",
        "## Evidence 등급",
        "",
        "| 값 | 의미 |",
        "|---|---|",
    ]
    for key in ("direct", "adjacent", "new", "sensitive"):
        lines.append(f"| `{key}` | {EVIDENCE_LABELS[key]} |")

    lines.extend(
        [
            "",
            "## 내부 capability runtime manifest",
            "",
            "| Capability | Credential | Proxy | Side effect | Execution | Live smoke |",
            "|---|---|---|---|---|---|",
        ]
    )
    for capability in data["shared_capabilities"]:
        lines.append(
            "| `{slug}` | `{credential_class}` | `{proxy_mode}` | `{side_effect_class}` | "
            "`{execution_status}` | `{live_smoke}` |".format(**capability)
        )

    for group in GROUP_ORDER:
        lines.extend(
            [
                "",
                f"## {group}",
                "",
                "| Domain | Evidence | Role | Skill | Slug | Capability | Reference Skill | 경계 |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for domain in domains:
            if domain["group"] != group:
                continue
            for skill in domain["skills"]:
                references = ", ".join(f"`{name}`" for name in skill["reference_skills"]) or "—"
                lines.append(
                    f"| {domain['domain']} | `{domain['evidence']}` | `{skill['role']}` | {skill['title']} | "
                    f"`{skill['name']}` | `{skill['capability']}` | {references} | `{skill['boundary']}` |"
                )

    source = data["research_source"]
    lines.extend(
        [
            "",
            "## 근거와 경계",
            "",
            f"- Wiki authority: `{source['wiki_authority']}`",
            f"- Evidence-only source map: `{source['wiki_source_map']}`",
            f"- Live reference repository: {source['reference_repository']}",
            f"- 확인한 reference HEAD: `{source['reference_head']}`",
            "- Reference Skill 이름은 capability 존재 근거일 뿐이며 코드·프롬프트를 가져오지 않습니다.",
            "- `sensitive` domain은 공개정보 기반 manual-review만 허용하고 운영·보호 세부사항을 자동화하지 않습니다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when generated Markdown is missing or stale")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "catalog/domain-skills.json"
    output = root / "docs/domain-skill-candidates.md"
    expected = render_catalog(load_catalog(source))
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != expected:
            print(f"ERROR stale generated document: {output.relative_to(root)}")
            return 1
        print(f"PASS generated={output.relative_to(root)}")
        return 0
    output.write_text(expected, encoding="utf-8")
    print(f"rendered={output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
