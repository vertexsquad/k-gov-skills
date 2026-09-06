"""Source-policy engine contract tests.

# noqa: SIZE_OK -- Issue #24 explicitly owns one engine module and one matching test module;
# splitting this behavioral contract would exceed the issue's two-path file boundary.
"""

from __future__ import annotations

import copy
import importlib
import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path
from typing import TypeAlias

JSONValue: TypeAlias = "None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]"

try:
    source_policy = importlib.import_module("kgov_runtime.source_policy")
except ModuleNotFoundError:
    source_policy = None


def reviewed_catalog() -> dict[str, JSONValue]:
    policy = {
        "id": "example-api",
        "revision": 1,
        "enabled": True,
        "institution": "Example",
        "channel": "api",
        "scope": {"origins": ["https://api.example.go.kr"], "path_rules": [
            {"match": "prefix", "path": "/v1/items"},
            {"match": "exact", "path": "/v1/items/health"},
        ], "methods": ["GET"]},
        "review": {"reviewed_on": "2026-09-01", "expires_on": "2026-10-01",
                   "evidence_urls": ["https://example.go.kr/review"]},
        "robots": {"status": "documented-api-exemption", "evidence_url": "https://example.go.kr/robots"},
        "terms": {"status": "allowed", "url": "https://example.go.kr/terms"},
        "rate_limit": {"status": "reviewed", "requests": 2, "per_seconds": 60,
                       "burst": 1, "max_wait_seconds": 3},
        "response": {"status": "reviewed", "max_bytes": 1000, "media_types": ["application/json"]},
        "license": {"status": "reviewed", "url": "https://example.go.kr/license",
                    "allowed_output_modes": ["projected-records"], "redistribution": "link-only"},
        "retention": {"raw_content": "none", "receipts": "metadata-only"},
    }
    operation = {"id": "kgov/example/query/v1", "schema_status": "declared",
                 "source_policy_ids": ["example-api"], "source_output_mode": "projected-records",
                 "fixture_argv": ["--fixture"]}
    contract = {
        "id": "kgov/example/v1",
        "capability_slug": "example",
        "module": "kgov_runtime.capabilities.example",
        "kind": "retrieval",
        "network_mode": "optional-live",
        "default_operation_id": "kgov/example/query/v1",
        "operations": [operation],
        "exit_codes": {"success": 0, "review_blocked": 1, "input_error": 2,
                       "policy_blocked": 3, "upstream_error": 4},
        "forbidden_output_keys": ["authorization", "body", "cookie", "credential",
                                  "headers", "raw", "text"],
    }
    capability = {"slug": "example", "source_policy_ids": ["example-api"],
                  "runtime_contract_id": "kgov/example/v1"}
    return {"schema_version": 6, "source_policies": [policy], "runtime_contracts": [contract],
            "shared_capabilities": [capability]}


class SourcePolicyTest(unittest.TestCase):
    def registry(self, catalog: dict[str, JSONValue] | None = None):
        self.assertIsNotNone(source_policy, "source policy API must exist")
        return source_policy.SourcePolicyRegistry.from_catalog(
            reviewed_catalog() if catalog is None else catalog, on_date=date(2026, 9, 6)
        )

    def test_catalog_parses_to_immutable_typed_models(self) -> None:
        policy = self.registry().policies[0]
        classes = (source_policy.SourcePolicy, source_policy.PolicyEvidence, source_policy.SourceScope,
                   source_policy.RobotsPolicy, source_policy.TermsPolicy, source_policy.RateLimitPolicy,
                   source_policy.ResponsePolicy, source_policy.LicensePolicy, source_policy.RetentionPolicy)
        values = (policy, policy.review, policy.scope, policy.robots, policy.terms, policy.rate_limit,
                  policy.response, policy.license, policy.retention)
        self.assertTrue(all(isinstance(value, model) for value, model in zip(values, classes, strict=True)))
        with self.assertRaises(FrozenInstanceError):
            policy.enabled = False

    def test_canonical_digest_is_key_order_independent_and_sensitive(self) -> None:
        catalog = reviewed_catalog()
        reordered = copy.deepcopy(catalog)
        policy = reordered["source_policies"][0]
        reordered["source_policies"][0] = dict(reversed(list(policy.items())))
        changed = copy.deepcopy(catalog)
        changed["source_policies"][0]["revision"] = 2
        digest = self.registry(catalog).policies[0].digest
        self.assertEqual(digest, self.registry(reordered).policies[0].digest)
        self.assertNotEqual(digest, self.registry(changed).policies[0].digest)
        self.assertEqual(64, len(digest))

    def test_live_schema_v6_catalog_parses_without_network(self) -> None:
        catalog = json.loads(Path("catalog/domain-skills.json").read_text(encoding="utf-8"))
        registry = self.registry(catalog)
        decision = registry.authorize("https://www.law.go.kr/DRF/lawSearch.do",
                                      "kgov/korean-law-bill-research/search-laws/v1")
        self.assertEqual(7, len(registry.policies))
        self.assertEqual("policy-disabled", decision.code)

    def test_exact_origin_port_and_segment_boundary(self) -> None:
        registry = self.registry()
        allowed = registry.authorize("https://API.EXAMPLE.GO.KR:443/v1/items/42?x=1", "kgov/example/query/v1")
        self.assertEqual(source_policy.AccessDecision(True, "allowed", "example-api", allowed.policy_digest), allowed)
        for url in ("https://sub.api.example.go.kr/v1/items/42",
                    "https://api.example.go.kr/v1/itemsets"):
            with self.subTest(url=url):
                self.assertEqual("missing-policy", registry.authorize(url, "kgov/example/query/v1").code)
        self.assertEqual("invalid-url", registry.authorize(
            "https://api.example.go.kr:444/v1/items/42", "kgov/example/query/v1").code)

    def test_unsafe_and_encoded_paths_are_rejected(self) -> None:
        registry = self.registry()
        urls = ("https://user@api.example.go.kr/v1/items/42",
                "https://api.example.go.kr/v1/items/42#fragment",
                "https://api.example.go.kr/v1/items%2Fsecret",
                "https://api.example.go.kr/v1/items%5csecret",
                "https://api.example.go.kr/v1/items%00secret",
                "https://api.example.go.kr/v1/items/../secret",
                "https://api.example.go.kr/v1/items/%2e%2e/secret",
                "https://api.example.go.kr/v1/items/%252fsecret",
                "https://api.example.go.kr/v1/items/%25252e%25252e/secret",
                "https://api.example.go.kr/v1/items/%252525252e%252525252e/secret",
                "https://api.example.go.kr/v1/items/%25",
                "https://api.example.go.kr/v1/items/%25a",
                "https://api.example.go.kr/v1/items/%25zz",
                "https://api.example.go.kr/v1/items/%2525zz",
                "https://api.example.go.kr/v1/items/%C0%AFsecret",
                "https://api.example.go.kr/v1/items/%E2%82",
                "https://api.example.go.kr/v1/items/%ED%A0%80",
                "https://api.example.go.kr/v1/items/%80",
                "https://api.example.go.kr/v1/items/%01hidden",
                "https://api.example.go.kr/v1/items/%7fhidden",
                "https://api.example.go.kr/v1/items/secret\x7fchild",
                f"https://api.example.go.kr/v1/items/{'x' * 4096}")
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(source_policy.AccessDecision(False, "invalid-url", None, None),
                                 registry.authorize(url, "kgov/example/query/v1"))

    def test_catalog_url_and_path_contract_rejects_controls_nesting_and_unbounded_values(self) -> None:
        mutations = (
            ("DEL evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review\x7fhidden")),
            ("encoded C0 evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%01hidden")),
            ("encoded DEL evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%7fhidden")),
            ("overlong UTF-8 evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%C0%AF")),
            ("truncated UTF-8 evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%E2%82")),
            ("surrogate UTF-8 evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%ED%A0%80")),
            ("nested evidence escape", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%252fhidden")),
            ("decoded dangling evidence escape", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%25")),
            ("decoded truncated evidence escape", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%25a")),
            ("decoded malformed evidence escape", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%25zz")),
            ("deeper malformed evidence escape", lambda policy: policy["review"]["evidence_urls"].append(
                "https://example.go.kr/review%2525zz")),
            ("DEL policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items\x7fhidden"})),
            ("encoded C0 policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%01hidden"})),
            ("encoded DEL policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%7fhidden"})),
            ("overlong UTF-8 policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%C0%AF"})),
            ("truncated UTF-8 policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%E2%82"})),
            ("surrogate UTF-8 policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%ED%A0%80"})),
            ("decoded dangling policy escape", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%25"})),
            ("decoded truncated policy escape", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%25a"})),
            ("decoded malformed policy escape", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%25zz"})),
            ("deeper malformed policy escape", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%2525zz"})),
            ("nested traversal", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%25252e%25252e"})),
            ("deeper nested traversal", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": "/v1/items/%252525252e%252525252e"})),
            ("unbounded evidence URL", lambda policy: policy["review"]["evidence_urls"].append(
                f"https://example.go.kr/{'x' * 4096}")),
            ("unbounded policy path", lambda policy: policy["scope"]["path_rules"].append(
                {"match": "prefix", "path": f"/v1/items/{'x' * 4096}"})),
        )
        for label, mutate in mutations:
            with self.subTest(case=label):
                catalog = reviewed_catalog()
                mutate(catalog["source_policies"][0])
                with self.assertRaises(source_policy.SourcePolicyError):
                    self.registry(catalog)

    def test_exact_path_rule_rejects_child_path(self) -> None:
        catalog = reviewed_catalog()
        catalog["source_policies"][0]["scope"]["path_rules"] = [
            {"match": "exact", "path": "/v1/items/health"}
        ]
        registry = self.registry(catalog)

        child = registry.authorize("https://api.example.go.kr/v1/items/health/details",
                                   "kgov/example/query/v1")

        self.assertEqual(source_policy.AccessDecision(False, "missing-policy", None, None), child)

    def test_missing_duplicate_and_ambiguous_policy_fail_closed(self) -> None:
        self.assertEqual("missing-policy", self.registry().authorize(
            "https://other.example.go.kr/v1/items", "kgov/example/query/v1").code)
        duplicate = reviewed_catalog()
        duplicate["source_policies"].append(copy.deepcopy(duplicate["source_policies"][0]))
        with self.assertRaisesRegex(source_policy.SourcePolicyError, "duplicate-policy"):
            self.registry(duplicate)
        ambiguous = reviewed_catalog()
        second = copy.deepcopy(ambiguous["source_policies"][0])
        second["id"] = "second-api"
        ambiguous["source_policies"].append(second)
        ambiguous["runtime_contracts"][0]["operations"][0]["source_policy_ids"].append("second-api")
        ambiguous["shared_capabilities"][0]["source_policy_ids"].append("second-api")
        decision = self.registry(ambiguous).authorize("https://api.example.go.kr/v1/items/42",
                                                      "kgov/example/query/v1")
        self.assertEqual("ambiguous-policy", decision.code)

    def test_unknown_or_unlinked_operation_is_blocked(self) -> None:
        registry = self.registry()
        unknown = registry.authorize("https://api.example.go.kr/v1/items", "kgov/example/missing/v1")
        catalog = reviewed_catalog()
        catalog["runtime_contracts"][0]["operations"][0]["source_policy_ids"] = []
        catalog["runtime_contracts"][0]["network_mode"] = "blocked"
        catalog["shared_capabilities"][0]["source_policy_ids"] = []
        unlinked = self.registry(catalog).authorize("https://api.example.go.kr/v1/items",
                                                   "kgov/example/query/v1")
        self.assertEqual("unknown-operation", unknown.code)
        self.assertEqual("missing-policy", unlinked.code)

    def test_future_review_is_rejected_during_catalog_parsing(self) -> None:
        catalog = reviewed_catalog()
        catalog["source_policies"][0]["review"]["reviewed_on"] = "2026-09-07"

        with self.assertRaises(source_policy.SourcePolicyError):
            self.registry(catalog)

    def test_review_dates_require_exact_extended_calendar_spelling(self) -> None:
        cases = (("reviewed_on", "20260901"), ("reviewed_on", "2026-W36-2"),
                 ("expires_on", "20261001"), ("expires_on", "2026-W40-4"))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                catalog = reviewed_catalog()
                catalog["source_policies"][0]["review"][field] = value
                with self.assertRaises(source_policy.SourcePolicyError):
                    self.registry(catalog)

    def test_policy_origins_reject_noncanonical_authority_delimiters(self) -> None:
        origins = ("https://api.example.go.kr?", "https://api.example.go.kr#",
                   "https://api.example.go.kr:", "https://api.example.go.kr:?",
                   "https://api.example.go.kr:#", "https://api.example.go.kr:0443",
                   "https://api.example.go.kr::", "https://[api.example.go.kr]")
        for origin in origins:
            with self.subTest(origin=origin):
                catalog = reviewed_catalog()
                catalog["source_policies"][0]["scope"]["origins"] = [origin]
                with self.assertRaises(source_policy.SourcePolicyError) as caught:
                    self.registry(catalog)
                self.assertNotIn(origin, str(caught.exception))

    def test_request_authority_rejects_empty_or_normalized_away_ports(self) -> None:
        registry = self.registry()
        urls = ("https://api.example.go.kr:/v1/items",
                "https://api.example.go.kr:?/v1/items",
                "https://api.example.go.kr:?query",
                "https://api.example.go.kr:#fragment",
                "https://api.example.go.kr:0443/v1/items",
                "https://api.example.go.kr::443/v1/items",
                "https://[api.example.go.kr]/v1/items")
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(source_policy.AccessDecision(False, "invalid-url", None, None),
                                 registry.authorize(url, "kgov/example/query/v1"))

    def test_disabled_stale_and_missing_review_are_blocked(self) -> None:
        for field, value, code in (("enabled", False, "policy-disabled"),
                                   ("review", None, "review-required")):
            with self.subTest(field=field):
                catalog = reviewed_catalog()
                catalog["source_policies"][0].pop(field) if value is None else catalog["source_policies"][0].update({field: value})
                decision = self.registry(catalog).authorize("https://api.example.go.kr/v1/items",
                                                            "kgov/example/query/v1")
                self.assertEqual(code, decision.code)
        stale = reviewed_catalog()
        stale["source_policies"][0]["review"]["expires_on"] = "2026-09-05"
        self.assertEqual("review-stale", self.registry(stale).authorize(
            "https://api.example.go.kr/v1/items", "kgov/example/query/v1").code)

    def test_terms_and_license_review_states_are_explicitly_blocked(self) -> None:
        cases = (("terms", {"status": "prohibited", "url": "https://example.go.kr/terms"}, "terms-prohibited"),
                 ("terms", {"status": "manual-review", "url": "https://example.go.kr/terms"}, "terms-manual-review"),
                 ("license", {"status": "manual-review", "url": "https://example.go.kr/license"}, "license-manual-review"))
        for field, value, code in cases:
            with self.subTest(field=field, code=code):
                catalog = reviewed_catalog()
                catalog["source_policies"][0][field] = value
                self.assertEqual(code, self.registry(catalog).authorize(
                    "https://api.example.go.kr/v1/items", "kgov/example/query/v1").code)

    def test_all_unreviewed_prerequisites_fail_closed(self) -> None:
        expected = {"robots": "robots-review-required", "terms": "terms-review-required",
                    "rate_limit": "rate-limit-review-required", "response": "response-review-required",
                    "license": "license-review-required"}
        for field, code in expected.items():
            with self.subTest(field=field):
                catalog = reviewed_catalog()
                catalog["source_policies"][0][field] = {"status": "unreviewed"}
                self.assertEqual(code, self.registry(catalog).authorize(
                    "https://api.example.go.kr/v1/items", "kgov/example/query/v1").code)

    def test_operation_license_mismatch_is_blocked(self) -> None:
        catalog = reviewed_catalog()
        catalog["runtime_contracts"][0]["operations"][0]["source_output_mode"] = "link-only"
        decision = self.registry(catalog).authorize("https://api.example.go.kr/v1/items",
                                                    "kgov/example/query/v1")
        self.assertEqual("license-operation-mismatch", decision.code)
        self.assertFalse(decision.allowed)

    def test_catalog_shape_and_policy_values_are_strictly_parsed(self) -> None:
        cases = (("unknown field", lambda policy: policy.update({"guessed_rights": True})),
                 ("invalid method", lambda policy: policy["scope"].update({"methods": ["POST"]})),
                 ("invalid retention", lambda policy: policy["retention"].update({"raw_content": "forever"})),
                 ("invalid evidence", lambda policy: policy["review"].update({"evidence_urls": []})))
        for label, mutate in cases:
            with self.subTest(case=label):
                catalog = reviewed_catalog()
                mutate(catalog["source_policies"][0])
                with self.assertRaises(source_policy.SourcePolicyError):
                    self.registry(catalog)

    def test_runtime_contract_and_operation_shapes_match_schema_v6(self) -> None:
        contract_fields = ("id", "capability_slug", "module", "kind", "network_mode",
                           "default_operation_id", "operations", "exit_codes",
                           "forbidden_output_keys")
        operation_fields = ("id", "schema_status", "source_policy_ids", "source_output_mode")
        mutations = [(f"missing contract {field}", "contract", field) for field in contract_fields]
        mutations.extend((f"missing operation {field}", "operation", field)
                         for field in operation_fields)
        mutations.extend((("unknown contract field", "contract", "guessed"),
                          ("unknown operation field", "operation", "guessed")))
        for label, level, field in mutations:
            with self.subTest(case=label):
                catalog = reviewed_catalog()
                node = catalog["runtime_contracts"][0]
                if level == "operation":
                    node = node["operations"][0]
                if field == "guessed":
                    node[field] = True
                else:
                    node.pop(field)
                with self.assertRaises(source_policy.SourcePolicyError):
                    self.registry(catalog)

    def test_operation_enums_reject_every_non_string_without_type_error(self) -> None:
        for field in ("schema_status", "source_output_mode"):
            for value in ([], {}, 1, False, None):
                with self.subTest(field=field, value=value):
                    catalog = reviewed_catalog()
                    catalog["runtime_contracts"][0]["operations"][0][field] = value
                    with self.assertRaises(source_policy.SourcePolicyError):
                        self.registry(catalog)

    def test_runtime_identity_and_manifest_invariants_fail_closed(self) -> None:
        mutations = (
            ("relabel capability", lambda catalog, contract, operation: contract.update(
                {"capability_slug": "other"})),
            ("contract id", lambda catalog, contract, operation: contract.update(
                {"id": "kgov/other/v1"})),
            ("module", lambda catalog, contract, operation: contract.update(
                {"module": "kgov_runtime.capabilities.other"})),
            ("kind", lambda catalog, contract, operation: contract.update({"kind": "other"})),
            ("network", lambda catalog, contract, operation: contract.update(
                {"network_mode": "other"})),
            ("default", lambda catalog, contract, operation: contract.update(
                {"default_operation_id": "kgov/example/other/v1"})),
            ("exit map", lambda catalog, contract, operation: contract["exit_codes"].update(
                {"policy_blocked": 0})),
            ("forbidden list", lambda catalog, contract, operation: contract.update(
                {"forbidden_output_keys": ["raw"]})),
            ("operation id", lambda catalog, contract, operation: operation.update(
                {"id": "kgov/other/query/v1"})),
            ("fixture", lambda catalog, contract, operation: operation.update(
                {"fixture_argv": ["--live"]})),
            ("declared schema", lambda catalog, contract, operation: operation.update(
                {"input_schema": {"type": "null"}})),
            ("policy union", lambda catalog, contract, operation: catalog["shared_capabilities"][0].update(
                {"source_policy_ids": []})),
            ("optional network without policy", lambda catalog, contract, operation: (
                operation.update({"source_policy_ids": []}),
                catalog["shared_capabilities"][0].update({"source_policy_ids": []}))),
            ("none network with policy", lambda catalog, contract, operation: contract.update(
                {"network_mode": "none"})),
        )
        for label, mutate in mutations:
            with self.subTest(case=label):
                catalog = reviewed_catalog()
                contract = catalog["runtime_contracts"][0]
                operation = contract["operations"][0]
                mutate(catalog, contract, operation)
                with self.assertRaises(source_policy.SourcePolicyError):
                    self.registry(catalog)

    def test_operation_order_schema_and_output_invariants_fail_closed(self) -> None:
        object_schema = {"type": "object", "required": [], "properties": {},
                         "additionalProperties": False}
        active = reviewed_catalog()
        active_operation = active["runtime_contracts"][0]["operations"][0]
        active_operation.update({"schema_status": "active", "input_schema": object_schema,
                                 "output_schema": copy.deepcopy(object_schema)})
        self.registry(active)
        mutations = (
            ("active missing schema", lambda catalog, contract, operation: operation.pop("output_schema")),
            ("active open schema", lambda catalog, contract, operation: operation["input_schema"].update(
                {"additionalProperties": True})),
            ("active unknown keyword", lambda catalog, contract, operation: operation["input_schema"].update(
                {"guessed": True})),
            ("active forbidden output", lambda catalog, contract, operation: operation["output_schema"].update(
                {"required": ["raw"], "properties": {"raw": {"type": "string"}}})),
            ("active unlinked output", lambda catalog, contract, operation: (
                operation.update({"source_policy_ids": []}),
                catalog["shared_capabilities"][0].update({"source_policy_ids": []}))),
            ("default not first", lambda catalog, contract, operation: contract["operations"].insert(
                0, {"id": "kgov/example/local/v1", "schema_status": "declared",
                    "source_policy_ids": [], "source_output_mode": "none"})),
        )
        for label, mutate in mutations:
            with self.subTest(case=label):
                catalog = copy.deepcopy(active)
                contract = catalog["runtime_contracts"][0]
                operation = contract["operations"][0]
                mutate(catalog, contract, operation)
                with self.assertRaises(source_policy.SourcePolicyError):
                    self.registry(catalog)


if __name__ == "__main__":
    unittest.main()
