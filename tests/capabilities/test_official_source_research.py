from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from kgov_runtime.capabilities import official_source_research as adapter
from kgov_runtime.http import HttpPolicyEnforcer, HttpTransport, ReadOnlyHttpError
from kgov_runtime.policy_state import PolicyState
from kgov_runtime.source_policy import SourcePolicyRegistry
from tests.test_read_only_http import Response, reviewed_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "capabilities" / "official-source-research.json"
)


class AdapterTest(unittest.TestCase):
    def test_fixture_is_explicitly_synthetic_and_contains_no_live_receipt(self) -> None:
        result = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            ("synthetic-fixture", None, True),
            (
                result["execution_mode"],
                result["source_receipt"],
                result["manual_review_required"],
            ),
        )

    def test_current_catalog_policy_blocks_before_transport(self) -> None:
        registry = SourcePolicyRegistry.from_catalog(
            json.loads((REPO_ROOT / "catalog/domain-skills.json").read_text()),
            on_date=date(2026, 9, 6),
        )
        policy = next(item for item in registry.policies if item.id == "gov-kr-web")
        touched: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            state = PolicyState(
                Path(directory) / "state.sqlite3",
                clock=lambda: 0.0,
                sleeper=lambda _seconds: None,
            )
            enforcer = HttpPolicyEnforcer(
                registry,
                state,
                HttpTransport(
                    lambda *_a, **_k: touched.append("open"),
                    lambda _host: touched.append("dns") or ["1.1.1.1"],
                    10.0,
                ),
            )
            with self.assertRaisesRegex(ReadOnlyHttpError, "^policy-disabled$"):
                adapter.inspect_source(
                    "https://www.gov.kr/portal/main", policy, enforcer
                )
        self.assertEqual([], touched)

    def test_synthetic_reviewed_policy_returns_only_metadata_and_exact_receipt(
        self,
    ) -> None:
        catalog = reviewed_catalog(robots="documented-api-exemption")
        catalog["source_policies"][0]["id"] = "gov-kr-web"
        catalog["source_policies"][0]["scope"]["origins"] = ["https://www.gov.kr"]
        catalog["runtime_contracts"][0]["operations"][0]["id"] = adapter.OPERATION_ID
        catalog["runtime_contracts"][0]["operations"][0]["source_policy_ids"] = [
            "gov-kr-web"
        ]
        contract = catalog["runtime_contracts"][0]
        contract["id"] = "kgov/official-source-research/v1"
        contract["capability_slug"] = "official-source-research"
        contract["module"] = "kgov_runtime.capabilities.official_source_research"
        contract["default_operation_id"] = adapter.OPERATION_ID
        capability = catalog["shared_capabilities"][0]
        capability["slug"] = "official-source-research"
        capability["source_policy_ids"] = ["gov-kr-web"]
        capability["runtime_contract_id"] = "kgov/official-source-research/v1"
        registry = SourcePolicyRegistry.from_catalog(catalog, on_date=date(2026, 9, 6))
        body = b"<html><head><title> \xec\xa0\x95\xeb\xb6\x80 \xec\x84\x9c\xeb\xb9\x84\xec\x8a\xa4 </title></head><body>public</body></html>"
        with tempfile.TemporaryDirectory() as directory:
            state = PolicyState(
                Path(directory) / "state.sqlite3",
                clock=lambda: 0.0,
                sleeper=lambda _seconds: None,
            )
            enforcer = HttpPolicyEnforcer(
                registry,
                state,
                HttpTransport(
                    lambda *_a, **_k: Response(body), lambda _host: ["1.1.1.1"], 10.0
                ),
            )
            result = adapter.inspect_source(
                "https://www.gov.kr/page?discard=1", registry.policies[0], enforcer
            )
        self.assertEqual(
            (
                "정부 서비스",
                hashlib.sha256(body).hexdigest(),
                "https://www.gov.kr/page",
            ),
            (result["title"], result["sha256"], result["url"]),
        )
        self.assertEqual(
            {
                "url",
                "status",
                "content_type",
                "title",
                "content_length",
                "sha256",
                "execution_mode",
                "source_receipt",
                "manual_review_required",
            },
            set(result),
        )
        self.assertEqual(
            (adapter.OPERATION_ID, "gov-kr-web", "allowed"),
            (
                result["source_receipt"]["operation_id"],
                result["source_receipt"]["policy_id"],
                result["source_receipt"]["outcome"],
            ),
        )

    def test_cli_fixture_succeeds_and_current_live_policy_exits_three(self) -> None:
        fixture = subprocess.run(
            [
                sys.executable,
                "-m",
                "kgov_runtime.capabilities.official_source_research",
                "--fixture",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        blocked = subprocess.run(
            [
                sys.executable,
                "-m",
                "kgov_runtime.capabilities.official_source_research",
                "https://www.gov.kr/",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, fixture.returncode)
        self.assertEqual(
            (3, "ERROR policy-disabled\n"), (blocked.returncode, blocked.stderr)
        )

    def test_state_initialization_failure_exits_three_without_reflecting_path(
        self,
    ) -> None:
        catalog = reviewed_catalog(robots="documented-api-exemption")
        policy = catalog["source_policies"][0]
        policy["id"] = "gov-kr-web"
        policy["scope"]["origins"] = ["https://www.gov.kr"]
        contract = catalog["runtime_contracts"][0]
        contract.update(
            id="kgov/official-source-research/v1",
            capability_slug="official-source-research",
            module="kgov_runtime.capabilities.official_source_research",
            default_operation_id=adapter.OPERATION_ID,
        )
        contract["operations"][0].update(
            id=adapter.OPERATION_ID, source_policy_ids=["gov-kr-web"]
        )
        capability = catalog["shared_capabilities"][0]
        capability.update(
            slug="official-source-research",
            source_policy_ids=["gov-kr-web"],
            runtime_contract_id="kgov/official-source-research/v1",
        )
        marker = "private-state-marker"
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            stderr = io.StringIO()
            with (
                patch.object(adapter, "CATALOG", catalog_path),
                patch.object(
                    adapter, "date", **{"today.return_value": date(2026, 9, 7)}
                ),
                patch.dict(
                    os.environ,
                    {"KGOV_POLICY_STATE_PATH": f"/dev/null/{marker}/state.sqlite3"},
                    clear=False,
                ),
                patch.object(
                    sys, "argv", ["official-source-research", "https://www.gov.kr/page"]
                ),
                patch.object(sys, "stderr", stderr),
                self.assertRaises(SystemExit) as raised,
            ):
                adapter.main()
        self.assertEqual(3, raised.exception.code)
        self.assertEqual("ERROR budget-exhausted\n", stderr.getvalue())
        self.assertNotIn(marker, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
