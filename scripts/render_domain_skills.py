#!/usr/bin/env python3
"""Render domain-owned Agent Skill entrypoints from the catalog."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kgov_runtime.contracts import (  # noqa: E402
    ContractId,
    ContractError,
    OperationId,
    RuntimeContract,
    parse_contracts,
)
from kgov_runtime.json_adapter import strict_json_loads  # noqa: E402

GENERATED_MARKER = "<!-- generated from catalog/domain-skills.json; do not edit -->"
BINDING_START = "<!-- kgov-runtime-binding:start -->"
BINDING_END = "<!-- kgov-runtime-binding:end -->"


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def module_name(capability: str) -> str:
    return capability.replace("-", "_")


@cache
def fixture_receipt(
    module: str, argv: tuple[str, ...]
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.offline_fixture", module, *argv],
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=30,
        env=os.environ | {"PYTHONIOENCODING": "utf-8"},
    )


def render_domain_skill(
    domain: dict[str, Any],
    skill: dict[str, Any],
    capability: dict[str, Any],
    contract: RuntimeContract,
    example: dict[str, Any],
) -> str:
    name = skill["name"]
    capability_slug = skill["capability"]
    description = (
        f"{domain['domain']} 업무의 {skill['title']} 절차. "
        f"내부 {capability_slug} capability를 사용하며 {skill['boundary']} 경계를 지킵니다."
    )
    references = skill["reference_skills"]
    reference_line = (
        ", ".join(f"`{item}`" for item in references) if references else "없음"
    )
    task_checks = skill.get("task_checks", [])
    binding = skill["runtime_binding"]
    operation = next(
        item for item in contract.operations if item.id == binding["operation"]
    )
    fixed_input = binding["fixed_input"]
    fixture_argv = list(operation.fixture_argv or ())
    procedure_path = f"docs/capabilities/{capability_slug}/procedure.md"
    contract_path = f"docs/capabilities/{capability_slug}/runtime-contract.md"
    command = shlex.join(["python3", "-m", contract.module, *fixture_argv])
    machine_contract = {
        "binding": binding,
        "module": contract.module,
        "schema_status": operation.schema_status,
        "network_mode": contract.network_mode,
        "source_policy_ids": list(operation.source_policy_ids),
        "source_output_mode": operation.source_output_mode,
        "fixture_argv": fixture_argv,
        "input_schema": operation.input_schema.document(),
        "output_schema": operation.output_schema.document(),
        "exit_codes": asdict(contract.exit_codes),
        "example_result": example,
    }
    output_fields = ", ".join(
        f"`{name}`" for name, _ in operation.output_schema.properties
    )
    lines = [
        "---",
        f"name: {name}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "metadata:",
        f"  domain: {json.dumps(domain['domain'], ensure_ascii=False)}",
        f"  capability: {json.dumps(capability_slug)}",
        f"  runtime_contract: {json.dumps(contract.id)}",
        f"  operation: {json.dumps(operation.id)}",
        f"  role: {json.dumps(skill['role'])}",
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
        "## Runtime binding",
        "",
        f"- Contract: `{contract.id}`",
        f"- Operation: `{operation.id}`",
        f"- Fixed input: `{json.dumps(fixed_input, ensure_ascii=False, sort_keys=True)}`",
        f"- Output fields: {output_fields}",
        "",
        BINDING_START,
        "```json",
        json.dumps(machine_contract, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        BINDING_END,
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
            f"1. 전체 저장소 checkout이 필요합니다. Skill 디렉터리만 복사해서 실행하지 않습니다. 클라이언트와 모든 명령은 `kgov_runtime/`, `docs/`, `tests/`가 있는 저장소 루트에서 실행하고, 루트 기준 `{procedure_path}`와 `{contract_path}`를 먼저 읽습니다.",
            f"2. `{command}`로 합성 fixture 계약을 검증합니다. 이는 사용자가 제공한 파일을 읽거나 검증한 결과가 아닙니다.",
            "3. 제공된 로컬 입력은 procedure의 실제 입력 절차와 제한에 따라 별도로 검사합니다. 파일이 없거나 읽을 수 없으면 차단 상태를 보고하고 fixture로 대신 검증했다고 주장하지 않습니다.",
            "4. live 실행은 capability manifest의 credential·proxy·허용 host 경계를 충족할 때만 수행합니다.",
            f"5. {capability['manual_handoff_gate']}",
            "6. fixture 성공, 로컬 입력 검사, URL 도달, live 검증을 서로 다른 증거로 보고합니다.",
            "",
        ]
    )
    if capability_slug in {
        "public-document-hwpx", "administrative-document-draft-review"
    }:
        lines.extend(
            [
                "## 실제 로컬 입력",
                "",
                f"저장소 루트에서 `python3 -m {contract.module} PATH`를 실행합니다. `PATH`는 사용자가 제공하고 읽기를 승인한 로컬 파일 경로로 바꾸고, 공백이 있으면 따옴표로 감쌉니다. `--fixture`와 함께 쓰지 않습니다. 입력 형식과 제한은 위 procedure를 따릅니다.",
                "위 Runtime binding의 `fixed_input`과 예시는 합성 fixture 전용 계약이며, 실제 파일 검사 결과가 아닙니다.",
                "",
            ]
        )
    lines.extend(
        [
            "## 금지",
            "",
            "- 이 Skill을 근거로 원본 변경·제출·결재·발송을 자동 수행하지 않습니다.",
            "- 비밀값이나 원문 개인정보를 로그·결과·fixture에 남기지 않습니다.",
            "- 내부 capability를 별도 top-level `skills/` 제품 표면으로 복제하지 않습니다.",
            "",
        ]
    )
    return "\n".join(lines)


def fixture_examples(
    data: dict[str, Any],
    contracts: tuple[RuntimeContract, ...],
) -> dict[OperationId, dict[str, Any]]:
    by_id = {contract.id: contract for contract in contracts}
    commands: dict[
        tuple[ContractId, OperationId],
        tuple[RuntimeContract, tuple[str, ...]],
    ] = {}
    for domain in data["domains"]:
        for skill in domain["skills"]:
            binding = skill["runtime_binding"]
            contract_id = ContractId(binding["contract_id"])
            operation_id = OperationId(binding["operation"])
            contract = by_id[contract_id]
            operation = next(
                item for item in contract.operations if item.id == operation_id
            )
            if operation.fixture_argv is None:
                raise ContractError("binding-without-fixture", operation_id)
            operation.input_schema.validate(binding["fixed_input"])
            fixed_argv = tuple(binding["fixed_input"]["argv"])
            if fixed_argv != operation.fixture_argv:
                raise ContractError("binding-fixture-mismatch", operation_id)
            commands[(contract_id, operation_id)] = (
                contract,
                operation.fixture_argv,
            )
    examples: dict[OperationId, dict[str, Any]] = {}
    for (_, operation_id), (contract, argv) in commands.items():
        receipt = fixture_receipt(contract.module, argv)
        if receipt.returncode != contract.exit_codes.success or receipt.stderr:
            raise subprocess.CalledProcessError(
                receipt.returncode,
                receipt.args,
                output=receipt.stdout,
                stderr=receipt.stderr,
            )
        output = strict_json_loads(receipt.stdout)
        if not isinstance(output, dict):
            raise TypeError(operation_id)
        contract.validate_output(operation_id, output)
        examples[operation_id] = output
    return examples


def expected_domain_skills(data: dict[str, Any], root: Path = ROOT) -> dict[Path, str]:
    capabilities = {item["slug"]: item for item in data["shared_capabilities"]}
    contracts = parse_contracts(data)
    contracts_by_id = {contract.id: contract for contract in contracts}
    examples = fixture_examples(data, contracts)
    expected: dict[Path, str] = {}
    for domain in data["domains"]:
        for skill in domain["skills"]:
            path = (
                root
                / "domains"
                / domain["domain"]
                / "skills"
                / skill["name"]
                / "SKILL.md"
            )
            binding = skill["runtime_binding"]
            contract = contracts_by_id[ContractId(binding["contract_id"])]
            operation_id = OperationId(binding["operation"])
            expected[path] = render_domain_skill(
                domain,
                skill,
                capabilities[skill["capability"]],
                contract,
                examples[operation_id],
            )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when generated Skill entrypoints are missing or stale",
    )
    args = parser.parse_args()
    data = load_catalog(ROOT / "catalog/domain-skills.json")
    expected = expected_domain_skills(data)
    stale = [
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != content
    ]
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
