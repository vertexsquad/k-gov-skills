"""Generated Skill runtime-binding and real fixture parity."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Final

from kgov_runtime.contracts import ContractId, OperationId, load_contracts
from kgov_runtime.json_adapter import strict_json_loads
from scripts.validate_catalog import validate

ROOT: Final = Path(__file__).resolve().parents[1]
CATALOG: Final = ROOT / "catalog/domain-skills.json"
BLOCK: Final = re.compile(
    r"<!-- kgov-runtime-binding:start -->\n"
    r"```json\n(?P<document>.*?)\n```\n"
    r"<!-- kgov-runtime-binding:end -->",
    re.DOTALL,
)


class GeneratedSkillContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG.read_bytes())

    def test_every_skill_binds_an_active_runtime_operation(self) -> None:
        # Given all catalog Skills and runtime operations.
        contracts = {
            contract["id"]: contract for contract in self.catalog["runtime_contracts"]
        }
        skills = [
            skill for domain in self.catalog["domains"] for skill in domain["skills"]
        ]

        # When resolving every declared binding.
        resolved = []
        for skill in skills:
            binding = skill["runtime_binding"]
            contract = contracts[binding["contract_id"]]
            operation = next(
                item
                for item in contract["operations"]
                if item["id"] == binding["operation"]
            )
            resolved.append((skill, contract, operation))

        # Then all 308 Skills bind their capability to an active operation.
        self.assertEqual(308, len(resolved))
        self.assertTrue(
            all(
                skill["capability"] == contract["capability_slug"]
                and operation["schema_status"] == "active"
                for skill, contract, operation in resolved
            )
        )

    def test_metadata_is_a_flat_map_of_json_quoted_strings(self) -> None:
        for domain in self.catalog["domains"]:
            for skill in domain["skills"]:
                path = (
                    ROOT
                    / "domains"
                    / domain["domain"]
                    / "skills"
                    / skill["name"]
                    / "SKILL.md"
                )
                frontmatter = path.read_text().split("---\n", 2)[1]
                metadata = frontmatter.split("metadata:\n", 1)[1].splitlines()
                self.assertEqual(5, len(metadata), path)
                for line in metadata:
                    self.assertRegex(line, r'^  [a-z_]+: ".*"$', path)
                    self.assertIsInstance(json.loads(line.split(": ", 1)[1]), str)

    def test_rendered_machine_blocks_match_all_catalog_bindings(self) -> None:
        # Given catalog bindings and generated Skill entrypoints.
        contracts = {
            contract["id"]: contract for contract in self.catalog["runtime_contracts"]
        }

        # When parsing each machine-consumed runtime block.
        documents = []
        for domain in self.catalog["domains"]:
            for skill in domain["skills"]:
                path = (
                    ROOT
                    / "domains"
                    / domain["domain"]
                    / "skills"
                    / skill["name"]
                    / "SKILL.md"
                )
                text = path.read_text()
                match = BLOCK.search(text)
                self.assertIsNotNone(match, path)
                document = strict_json_loads(match["document"].encode())
                binding = skill["runtime_binding"]
                operation = next(
                    item
                    for item in contracts[binding["contract_id"]]["operations"]
                    if item["id"] == binding["operation"]
                )
                self.assertEqual(binding, document["binding"])
                self.assertEqual(operation["fixture_argv"], document["fixture_argv"])
                self.assertEqual(operation["input_schema"], document["input_schema"])
                self.assertEqual(operation["output_schema"], document["output_schema"])
                self.assertEqual(
                    {
                        "domain": domain["domain"],
                        "capability": skill["capability"],
                        "runtime_contract": binding["contract_id"],
                        "operation": binding["operation"],
                        "role": skill["role"],
                    },
                    {
                        key: json.loads(value)
                        for key, value in re.findall(
                            r'^  ([a-z_]+): (".*")$',
                            text.split("---\n", 2)[1],
                            re.MULTILINE,
                        )
                    },
                )
                documents.append(document)

        # Then every generated Skill exposes one exact binding sentinel.
        self.assertEqual(308, len(documents))

    def test_unique_bound_fixtures_match_declared_schemas_offline(self) -> None:
        # Given the 308 bindings deduplicated to reviewed fixture argv.
        contracts = load_contracts()
        by_id = {contract.id: contract for contract in contracts}
        skills = [
            (domain["domain"], skill)
            for domain in self.catalog["domains"]
            for skill in domain["skills"]
        ]
        commands = dict.fromkeys(
            (
                by_id[ContractId(skill["runtime_binding"]["contract_id"])].module,
                tuple(skill["runtime_binding"]["fixed_input"]["argv"]),
                OperationId(skill["runtime_binding"]["operation"]),
            )
            for domain in self.catalog["domains"]
            for skill in domain["skills"]
        )

        # When each unique fixture is executed with network disabled.
        self.assertEqual(22, len(commands))
        for module, argv, operation_id in commands:
            receipt = subprocess.run(
                [sys.executable, "-m", "scripts.offline_fixture", module, *argv],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Then it emits one schema-valid JSON object and quiet stderr.
            contract = next(
                item
                for item in contracts
                if operation_id in {operation.id for operation in item.operations}
            )
            self.assertEqual(contract.exit_codes.success, receipt.returncode)
            self.assertEqual("", receipt.stderr)
            output = strict_json_loads(receipt.stdout.encode())
            self.assertIsInstance(output, dict)
            contract.validate_output(operation_id, output)
            domain, skill = next(
                item
                for item in skills
                if item[1]["runtime_binding"]["operation"] == operation_id
            )
            path = ROOT / "domains" / domain / "skills" / skill["name"] / "SKILL.md"
            document = strict_json_loads(
                BLOCK.search(path.read_text())["document"].encode()
            )
            self.assertEqual(output, document["example_result"])
            output["unknown_output"] = True
            with self.assertRaises(ValueError):
                contract.validate_output(operation_id, output)

    def test_binding_and_active_schema_mutations_fail_closed(self) -> None:
        # Given one otherwise valid bound catalog.
        cases = (
            (
                ("domains", 0, "skills", 0, "runtime_binding", "contract_id"),
                "kgov/unknown/v1",
                "V6_UNKNOWN_REFERENCE",
            ),
            (
                ("domains", 0, "skills", 0, "runtime_binding", "operation"),
                "kgov/public-document-hwpx/unknown/v1",
                "V6_UNKNOWN_REFERENCE",
            ),
            (
                ("domains", 0, "skills", 0, "runtime_binding", "fixed_input"),
                {"unknown": "value"},
                "V6_INVALID_VALUE",
            ),
            (
                (
                    "runtime_contracts",
                    0,
                    "operations",
                    0,
                    "output_schema",
                    "properties",
                    "raw",
                ),
                {"type": "string"},
                "V6_CONTRACT_INVARIANT",
            ),
            (
                (
                    "runtime_contracts",
                    1,
                    "operations",
                    0,
                    "source_policy_ids",
                ),
                ["unknown-policy"],
                "V6_UNKNOWN_REFERENCE",
            ),
        )
        for path, value, code in cases:
            with self.subTest(path=path):
                candidate = deepcopy(self.catalog)
                target = candidate
                for member in path[:-1]:
                    target = target[member]
                target[path[-1]] = value

                # When mutating an identity, fixed field, output key, or policy.
                errors = validate(candidate, ROOT)

                # Then the validator rejects the altered machine contract.
                self.assertTrue(any(error.startswith(code) for error in errors), errors)
