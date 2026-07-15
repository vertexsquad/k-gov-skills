#!/usr/bin/env python3
"""Validate the domain-owned Skill topology, capability runtime, and generated docs."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_catalog import GROUP_ORDER, render_catalog  # noqa: E402
from render_domain_skills import expected_domain_skills  # noqa: E402

DOMAIN_REQUIRED_KEYS = {"domain", "group", "evidence", "skills"}
SKILL_REQUIRED_KEYS = {"name", "title", "capability", "role", "reference_skills", "boundary"}
CAPABILITY_REQUIRED_KEYS = {
    "slug",
    "locale",
    "jurisdiction",
    "service",
    "credential_class",
    "proxy_mode",
    "side_effect_class",
    "manual_handoff_gate",
    "source_provenance",
    "execution_status",
    "live_smoke",
}
EVIDENCE = {"direct", "adjacent", "new", "sensitive"}
BOUNDARIES = {"read-only", "draft-only", "manual-review-only"}
ROLES = {"primary", "additional"}
CREDENTIAL_CLASSES = {"none", "user-held", "operator-held", "mixed"}
PROXY_MODES = {"none", "optional", "required", "mixed"}
SIDE_EFFECT_CLASSES = {"read-only", "document-read", "draft-only"}
EXECUTION_STATUSES = {"planned", "fixture-verified", "live-verified", "blocked"}
LIVE_SMOKE_STATUSES = {"not-run", "passed", "failed", "blocked"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def collect_used_capabilities(domains: list[dict[str, Any]]) -> set[str]:
    used: set[str] = set()
    for domain in domains:
        skills = domain.get("skills", [])
        if not isinstance(skills, list):
            continue
        used.update(
            skill["capability"]
            for skill in skills
            if isinstance(skill, dict) and isinstance(skill.get("capability"), str)
        )
    return used


def _validate_instructions(root: Path, errors: list[str]) -> None:
    contracts = {
        "CLAUDE.md": {
            "max_lines": 80,
            "anchors": (
                "domains/<domain>/skills/<unique-slug>/SKILL.md",
                "top-level `skills/`",
                "catalog/domain-skills.json",
                "python3 scripts/check.py",
                "비밀값",
                "명시적 승인",
            ),
        },
        "AGENTS.md": {
            "max_lines": 20,
            "anchors": (
                "CLAUDE.md",
                "domains/<domain>/skills/",
                "top-level `skills/`",
                "python3 scripts/check.py",
            ),
        },
    }
    for name, contract in contracts.items():
        path = root / name
        if not path.is_file():
            errors.append(f"missing root instruction contract: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        if len(text.splitlines()) > contract["max_lines"]:
            errors.append(f"{name}: exceeds {contract['max_lines']} line budget")
        for anchor in contract["anchors"]:
            if anchor not in text:
                errors.append(f"{name}: missing required anchor {anchor!r}")
    for typo in ("Agent.md", "Cluade.md"):
        if (root / typo).exists():
            errors.append(f"non-standard instruction filename is forbidden: {typo}")


def _validate_capabilities(
    raw_capabilities: Any,
    root: Path,
    errors: list[str],
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    if not isinstance(raw_capabilities, list):
        errors.append("shared_capabilities must be a list")
        return set(), {}
    if len(raw_capabilities) != 11:
        errors.append(f"catalog must contain 11 shared capabilities, got {len(raw_capabilities)}")
    slugs: set[str] = set()
    by_slug: dict[str, dict[str, Any]] = {}
    for index, capability in enumerate(raw_capabilities):
        if not isinstance(capability, dict):
            errors.append(f"shared_capabilities[{index}] must be an object")
            continue
        missing = CAPABILITY_REQUIRED_KEYS - set(capability)
        if missing:
            errors.append(f"shared_capabilities[{index}] missing keys: {sorted(missing)}")
            continue
        slug = capability["slug"]
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            errors.append(f"invalid shared capability slug: {slug}")
            continue
        if slug in slugs:
            errors.append(f"duplicate shared capability: {slug}")
        slugs.add(slug)
        by_slug[slug] = capability
        if capability["locale"] != "ko-KR" or capability["jurisdiction"] != "KR":
            errors.append(f"{slug}: locale/jurisdiction must be ko-KR/KR")
        if capability["credential_class"] not in CREDENTIAL_CLASSES:
            errors.append(f"{slug}: invalid credential_class")
        if capability["proxy_mode"] not in PROXY_MODES:
            errors.append(f"{slug}: invalid proxy_mode")
        if capability["side_effect_class"] not in SIDE_EFFECT_CLASSES:
            errors.append(f"{slug}: invalid side_effect_class")
        if capability["execution_status"] not in EXECUTION_STATUSES:
            errors.append(f"{slug}: invalid execution_status")
        if capability["live_smoke"] not in LIVE_SMOKE_STATUSES:
            errors.append(f"{slug}: invalid live_smoke")
        if capability["execution_status"] == "live-verified" and capability["live_smoke"] != "passed":
            errors.append(f"{slug}: live-verified requires live_smoke=passed")
        if capability["live_smoke"] == "passed" and capability["execution_status"] != "live-verified":
            errors.append(f"{slug}: live_smoke=passed requires live-verified")
        provenance = capability["source_provenance"]
        if not isinstance(provenance, list) or not provenance or not all(
            isinstance(url, str) and url.startswith("https://") for url in provenance
        ):
            errors.append(f"{slug}: source_provenance must contain HTTPS URLs")

        module = slug.replace("-", "_")
        required_paths = [
            root / "kgov_runtime" / "capabilities" / f"{module}.py",
            root / "tests" / "capabilities" / f"test_{module}.py",
            root / "tests" / "fixtures" / "capabilities" / f"{slug}.json",
            root / "docs" / "capabilities" / slug / "procedure.md",
            root / "docs" / "capabilities" / slug / "runtime-contract.md",
        ]
        for path in required_paths:
            if not path.is_file():
                errors.append(f"{slug}: missing internal capability artifact {path.relative_to(root)}")
        if capability["execution_status"] == "live-verified":
            path = root / "docs" / "capabilities" / slug / "live-smoke.md"
            if not path.is_file():
                errors.append(f"{slug}: missing live smoke evidence {path.relative_to(root)}")
    return slugs, by_slug


def validate(data: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 4:
        errors.append("schema_version must be 4")
    domains = data.get("domains")
    if not isinstance(domains, list):
        return errors + ["domains must be a list"]
    if len(domains) != 60:
        errors.append(f"catalog must contain 60 domains, got {len(domains)}")

    capability_slugs, capability_by_slug = _validate_capabilities(data.get("shared_capabilities"), root, errors)
    seen_domains: set[str] = set()
    seen_names: set[str] = set()
    declared_entrypoints: set[Path] = set()
    total_skills = 0

    for index, item in enumerate(domains):
        if not isinstance(item, dict):
            errors.append(f"domains[{index}] must be an object")
            continue
        missing = DOMAIN_REQUIRED_KEYS - set(item)
        if missing:
            errors.append(f"domains[{index}] missing keys: {sorted(missing)}")
            continue
        domain = item["domain"]
        evidence = item["evidence"]
        skills = item["skills"]
        if not isinstance(domain, str) or not domain:
            errors.append(f"domains[{index}]: invalid domain")
            continue
        if domain in seen_domains:
            errors.append(f"duplicate domain: {domain}")
        seen_domains.add(domain)
        if item["group"] not in GROUP_ORDER:
            errors.append(f"{domain}: invalid group {item['group']}")
        if evidence not in EVIDENCE:
            errors.append(f"{domain}: invalid evidence {evidence}")
        if not isinstance(skills, list) or not skills:
            errors.append(f"{domain}: skills must be a non-empty list")
            continue
        total_skills += len(skills)
        primary_count = sum(isinstance(skill, dict) and skill.get("role") == "primary" for skill in skills)
        if primary_count != 1:
            errors.append(f"{domain}: requires exactly one primary Skill, got {primary_count}")
        for skill_index, skill in enumerate(skills):
            if not isinstance(skill, dict):
                errors.append(f"{domain}.skills[{skill_index}] must be an object")
                continue
            missing_skill = SKILL_REQUIRED_KEYS - set(skill)
            if missing_skill:
                errors.append(f"{domain}.skills[{skill_index}] missing keys: {sorted(missing_skill)}")
                continue
            name = skill["name"]
            capability = skill["capability"]
            role = skill["role"]
            boundary = skill["boundary"]
            references = skill["reference_skills"]
            if not isinstance(name, str) or not SLUG.fullmatch(name):
                errors.append(f"{domain}: invalid Skill name {name}")
                continue
            if name in seen_names:
                errors.append(f"duplicate domain Skill name: {name}")
            seen_names.add(name)
            if role not in ROLES:
                errors.append(f"{domain}/{name}: invalid role {role}")
            if not isinstance(capability, str) or not SLUG.fullmatch(capability):
                errors.append(f"{domain}/{name}: invalid capability {capability}")
            elif capability not in capability_slugs:
                errors.append(f"{domain}/{name}: unknown capability {capability}")
            if boundary not in BOUNDARIES:
                errors.append(f"{domain}/{name}: invalid boundary {boundary}")
            if not isinstance(references, list) or not all(
                isinstance(value, str) and SLUG.fullmatch(value) for value in references
            ):
                errors.append(f"{domain}/{name}: invalid reference_skills")
                references = []
            if role == "primary":
                if evidence in {"direct", "adjacent"} and not references:
                    errors.append(f"{domain}: {evidence} evidence requires primary reference_skills")
                if evidence in {"new", "sensitive"} and references:
                    errors.append(f"{domain}: {evidence} evidence must not claim primary reference_skills")
                if evidence == "sensitive" and boundary != "manual-review-only":
                    errors.append(f"{domain}: sensitive evidence requires manual-review-only")
            declared_entrypoints.add(Path("domains") / domain / "skills" / name / "SKILL.md")

    if total_skills != 66:
        errors.append(f"catalog must declare 66 domain Skills, got {total_skills}")
    domains_root = root / "domains"
    actual_domains = {path.name for path in domains_root.iterdir() if path.is_dir()} if domains_root.is_dir() else set()
    if actual_domains != seen_domains:
        errors.append(
            f"domain folder/catalog mismatch missing={sorted(seen_domains - actual_domains)} extra={sorted(actual_domains - seen_domains)}"
        )
    if (root / "skills").exists():
        errors.append("top-level skills/ is forbidden; public Skills must be owned by domains")

    actual_entrypoints = {path.relative_to(root) for path in domains_root.glob("*/skills/*/SKILL.md")}
    if actual_entrypoints != declared_entrypoints:
        errors.append(
            f"domain Skill/catalog mismatch missing={sorted(map(str, declared_entrypoints - actual_entrypoints))} "
            f"extra={sorted(map(str, actual_entrypoints - declared_entrypoints))}"
        )
    for gitkeep in domains_root.glob("*/.gitkeep"):
        errors.append(f"stale empty-domain marker is forbidden: {gitkeep.relative_to(root)}")

    used = collect_used_capabilities(domains)
    if used != capability_slugs:
        errors.append(
            f"declared/used capability mismatch unused={sorted(capability_slugs - used)} undeclared={sorted(used - capability_slugs)}"
        )
    try:
        expected_skills = expected_domain_skills(data, root)
    except (KeyError, TypeError) as exc:
        errors.append(f"cannot render domain Skills from catalog: {exc}")
        expected_skills = {}
    for path, expected in expected_skills.items():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if text != expected:
            errors.append(f"stale generated domain Skill: {path.relative_to(root)}")
        name_match = re.search(r"^name:\s*([^\s]+)\s*$", text, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)\s*$", text, re.MULTILINE)
        if not name_match or name_match.group(1) != path.parent.name:
            errors.append(f"{path.relative_to(root)}: frontmatter name must match directory")
        if not description_match:
            errors.append(f"{path.relative_to(root)}: missing frontmatter description")

    generated = root / "docs" / "domain-skill-candidates.md"
    try:
        expected_catalog = render_catalog(data)
    except (KeyError, TypeError) as exc:
        errors.append(f"cannot render generated catalog: {exc}")
    else:
        if not generated.is_file():
            errors.append("missing generated docs/domain-skill-candidates.md")
        elif generated.read_text(encoding="utf-8") != expected_catalog:
            errors.append("docs/domain-skill-candidates.md is stale; run scripts/render_catalog.py")

    _validate_instructions(root, errors)
    return errors


def main() -> int:
    catalog_path = ROOT / "catalog/domain-skills.json"
    if not catalog_path.is_file():
        print("ERROR missing catalog/domain-skills.json")
        return 1
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    counts = Counter(item["evidence"] for item in data["domains"])
    capabilities = collect_used_capabilities(data["domains"])
    domain_skills = sum(len(item["skills"]) for item in data["domains"])
    print(
        "PASS "
        f"domains={len(data['domains'])} domain_skills={domain_skills} capabilities={len(capabilities)} top_level_skills=0 "
        + " ".join(f"{name}={counts[name]}" for name in ("direct", "adjacent", "new", "sensitive"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
