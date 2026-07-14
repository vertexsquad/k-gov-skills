#!/usr/bin/env python3
"""Render the machine-readable domain Skill candidate catalog as Markdown."""

from __future__ import annotations

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
    lines = [
        "# Domain별 Skill 후보",
        "",
        "> 이 문서는 `catalog/domain-skills.json`에서 생성합니다. 직접 편집하지 마세요.",
        "> 외부 reference의 코드·문서를 복사하지 않으며, 독립 구현을 위한 capability 근거로만 사용합니다.",
        "",
        "## 요약",
        "",
        f"- 전체 domain: **{len(domains)}개**",
        f"- 직접 reference 확인: **{counts['direct']}개**",
        f"- 인접 capability 활용: **{counts['adjacent']}개**",
        f"- 신규 설계 필요: **{counts['new']}개**",
        f"- 민감업무 제한: **{counts['sensitive']}개**",
        "- 구현 상태: 모든 domain 항목은 후보이며, 실제 API·인증·약관 검증 후 승격합니다.",
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
            "## 공통 capability runtime manifest",
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
                "| Domain | Evidence | Skill 후보 | 권장 slug | 공통 capability | Reference Skill | 실행 경계 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for item in domains:
            if item["group"] != group:
                continue
            references = ", ".join(f"`{name}`" for name in item["reference_skills"]) or "—"
            lines.append(
                "| {domain} | `{evidence}` | {candidate} | `{slug}` | `{shared_capability}` | {references} | `{boundary}` |".format(
                    **item, references=references
                )
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
            "- `sensitive` 후보는 공개정보 기반 manual-review만 허용하고 운영·보호 세부사항을 자동화하지 않습니다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "catalog" / "domain-skills.json"
    output = root / "docs" / "domain-skill-candidates.md"
    output.write_text(render_catalog(load_catalog(source)), encoding="utf-8")
    print(f"rendered={output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
