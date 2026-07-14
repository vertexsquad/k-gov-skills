#!/usr/bin/env python3
"""Validate the domain taxonomy, Skill candidate catalog, and generated documentation."""

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

REQUIRED_KEYS = {
    "domain",
    "group",
    "evidence",
    "candidate",
    "slug",
    "shared_capability",
    "reference_skills",
    "boundary",
}
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
CREDENTIAL_CLASSES = {"none", "user-held", "operator-held", "mixed"}
PROXY_MODES = {"none", "optional", "required", "mixed"}
SIDE_EFFECT_CLASSES = {"read-only", "document-read", "draft-only"}
EXECUTION_STATUSES = {"planned", "fixture-verified", "live-verified", "blocked"}
LIVE_SMOKE_STATUSES = {"not-run", "passed", "failed", "blocked"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def collect_used_capabilities(domains: list[dict[str, Any]]) -> set[str]:
    capabilities = {
        item["shared_capability"]
        for item in domains
        if isinstance(item.get("shared_capability"), str)
    }
    for item in domains:
        additional_capabilities = item.get("additional_capabilities", [])
        if isinstance(additional_capabilities, list):
            capabilities.update(value for value in additional_capabilities if isinstance(value, str))
    return capabilities


def validate(data: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    domains = data.get("domains")
    if data.get("schema_version") != 3:
        errors.append("schema_version must be 3")
    if not isinstance(domains, list):
        return errors + ["domains must be a list"]
    if len(domains) != 60:
        errors.append(f"catalog must contain 60 domains, got {len(domains)}")

    raw_capabilities = data.get("shared_capabilities")
    if not isinstance(raw_capabilities, list):
        return errors + ["shared_capabilities must be a list"]
    if len(raw_capabilities) != 9:
        errors.append(f"catalog must contain 9 shared capabilities, got {len(raw_capabilities)}")

    capability_slugs: set[str] = set()
    capability_by_slug: dict[str, dict[str, Any]] = {}
    for index, capability in enumerate(raw_capabilities):
        missing = CAPABILITY_REQUIRED_KEYS - set(capability)
        if missing:
            errors.append(f"shared_capabilities[{index}] missing keys: {sorted(missing)}")
            continue
        slug = capability["slug"]
        if slug in capability_slugs:
            errors.append(f"duplicate shared capability: {slug}")
        capability_slugs.add(slug)
        capability_by_slug[slug] = capability
        if not SLUG.fullmatch(slug):
            errors.append(f"invalid shared capability slug: {slug}")
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

    seen_domains: set[str] = set()
    seen_slugs: set[str] = set()
    for index, item in enumerate(domains):
        missing = REQUIRED_KEYS - set(item)
        if missing:
            errors.append(f"domains[{index}] missing keys: {sorted(missing)}")
            continue
        domain = item["domain"]
        slug = item["slug"]
        evidence = item["evidence"]
        references = item["reference_skills"]
        additional_capabilities = item.get("additional_capabilities", [])
        if domain in seen_domains:
            errors.append(f"duplicate domain: {domain}")
        seen_domains.add(domain)
        if slug in seen_slugs:
            errors.append(f"duplicate candidate slug: {slug}")
        seen_slugs.add(slug)
        if item["group"] not in GROUP_ORDER:
            errors.append(f"{domain}: invalid group {item['group']}")
        if evidence not in EVIDENCE:
            errors.append(f"{domain}: invalid evidence {evidence}")
        if item["boundary"] not in BOUNDARIES:
            errors.append(f"{domain}: invalid boundary {item['boundary']}")
        if not SLUG.fullmatch(slug):
            errors.append(f"{domain}: invalid candidate slug {slug}")
        if not SLUG.fullmatch(item["shared_capability"]):
            errors.append(f"{domain}: invalid shared capability {item['shared_capability']}")
        elif item["shared_capability"] not in capability_slugs:
            errors.append(f"{domain}: unknown shared capability {item['shared_capability']}")
        if not isinstance(additional_capabilities, list) or not all(
            isinstance(value, str) and SLUG.fullmatch(value) for value in additional_capabilities
        ):
            errors.append(f"{domain}: invalid additional_capabilities")
            additional_capabilities = []
        elif len(additional_capabilities) != len(set(additional_capabilities)):
            errors.append(f"{domain}: duplicate additional capability")
        for additional in additional_capabilities:
            if additional == item["shared_capability"]:
                errors.append(f"{domain}: additional capability {additional} duplicates primary capability")
            elif additional not in capability_slugs:
                errors.append(f"{domain}: unknown additional capability {additional}")
        if not isinstance(references, list) or not all(isinstance(value, str) and SLUG.fullmatch(value) for value in references):
            errors.append(f"{domain}: invalid reference_skills")
        if evidence in {"direct", "adjacent"} and not references:
            errors.append(f"{domain}: {evidence} evidence requires reference_skills")
        if evidence in {"new", "sensitive"} and references:
            errors.append(f"{domain}: {evidence} evidence must not claim reference_skills")
        if evidence == "sensitive" and item["boundary"] != "manual-review-only":
            errors.append(f"{domain}: sensitive evidence requires manual-review-only")

    actual_domains = {path.name for path in (root / "domains").iterdir() if path.is_dir()}
    if actual_domains != seen_domains:
        errors.append(
            f"domain folder/catalog mismatch missing={sorted(actual_domains - seen_domains)} extra={sorted(seen_domains - actual_domains)}"
        )

    capabilities = collect_used_capabilities(domains)
    if capabilities != capability_slugs:
        errors.append(
            f"declared/used capability mismatch unused={sorted(capability_slugs - capabilities)} "
            f"undeclared={sorted(capabilities - capability_slugs)}"
        )
    for capability in sorted(capabilities):
        skill_path = root / "skills" / capability / "SKILL.md"
        if not skill_path.is_file():
            errors.append(f"missing shared capability Skill: {skill_path.relative_to(root)}")
            continue
        skill_text = skill_path.read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*([^\s]+)\s*$", skill_text, re.MULTILINE)
        description_match = re.search(r"^description:\s*(.+)\s*$", skill_text, re.MULTILINE)
        if not name_match or name_match.group(1) != capability:
            errors.append(f"{skill_path.relative_to(root)}: frontmatter name must be {capability}")
        if not description_match:
            errors.append(f"{skill_path.relative_to(root)}: missing frontmatter description")
        manifest = capability_by_slug.get(capability)
        if manifest and manifest["execution_status"] in {"fixture-verified", "live-verified"}:
            required_paths = [
                skill_path.parent / "scripts" / "adapter.py",
                skill_path.parent / "tests" / "test_adapter.py",
                skill_path.parent / "fixtures" / "sample.json",
                skill_path.parent / "references" / "runtime-contract.md",
            ]
            for required_path in required_paths:
                if not required_path.is_file():
                    errors.append(f"{capability}: missing verified artifact {required_path.relative_to(root)}")
            if manifest["execution_status"] == "live-verified":
                live_evidence = skill_path.parent / "references" / "live-smoke.md"
                if not live_evidence.is_file():
                    errors.append(f"{capability}: missing live smoke evidence {live_evidence.relative_to(root)}")

    generated = root / "docs" / "domain-skill-candidates.md"
    expected = render_catalog(data)
    if not generated.is_file():
        errors.append("missing generated docs/domain-skill-candidates.md")
    elif generated.read_text(encoding="utf-8") != expected:
        errors.append("docs/domain-skill-candidates.md is stale; run scripts/render_catalog.py")
    return errors


def main() -> int:
    catalog_path = ROOT / "catalog" / "domain-skills.json"
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
    print(
        "PASS "
        f"domains={len(data['domains'])} capabilities={len(capabilities)} "
        + " ".join(f"{name}={counts[name]}" for name in ("direct", "adjacent", "new", "sensitive"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
