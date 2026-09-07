# Runtime contract — `official-source-research`

- operation: `kgov/official-source-research/inspect-page/v1`
- source policy: registry-owned `gov-kr-web` exact object only
- 입력: 정책 scope에 일치하는 공개 HTTPS URL
- credential/proxy: 없음
- authorization order: registry authorization and exact policy identity checks run before DNS, policy-state reservation, or opener invocation.
- current catalog: `gov-kr-web` is disabled/unreviewed, so live use exits `3` with `policy-disabled` before network access.
- network safety: credentials, fragments, non-HTTPS targets, non-canonical authorities/paths, and non-public resolved addresses fail closed.
- robots: required policies fetch the policy origin's `/robots.txt` once under a separate rate reservation. HTTP 404/410 allows access only when terms are reviewed `allowed`; invalid robots data and every other missing/error response fail closed. Reviewed exact API exemptions do not fetch robots.
- rate/Retry-After: SQLite state reserves before each opener. A valid `Retry-After` is persisted without retry; no automatic retry loop exists.
- state failures: directory creation and SQLite initialization failures map to non-reflecting `budget-exhausted`; configured paths are never emitted.
- response: only reviewed media types and bounded 2xx bodies are accepted. UTF-8/JSON parsing is strict; duplicate keys, non-finite values, CAPTCHA, unsafe projection keys, and direct identifiers fail closed.
- output: title and metadata/hash only. Body, headers, query, credential material, and raw content are discarded before return.
- compatibility seam: an explicitly injected opener is a private test seam and is not live evidence; absent an opener, `safe_urlopen` returns `policy-disabled` before DNS or network. The package-level pure `normalize_records` API remains unchanged; its `raw` field is never used by the enforced HTTP API and is not an allowed enforced output.
- receipt: successful policy-authorized use emits operation ID, policy ID/revision/digest, and `outcome: allowed`. 이 enforcer-issued record는 cryptographic authenticity, 내용의 정확성 또는 법적 이용허락을 증명하지 않습니다.
- fixture 검증: `python3 -m kgov_runtime.capabilities.official_source_research --fixture`
- fixture output is explicitly `synthetic-fixture` with a null source receipt and cannot be represented as live evidence.
- 로그인·제출·민감정보·페이지 내 action은 실행하지 않는다.

Fixture, URL 도달, policy-authorized retrieval, substantive correctness와 human/legal approval은 별도 차원입니다. 공통 robots·license·receipt·삭제 한계는 [source usage policy](../../source-usage-policy.md)를 따릅니다.

Stable failures map to catalog exits:

- input (`invalid-request`): `2`
- policy (`policy-disabled`, `policy-expired`, `robots-denied`, `terms-unverified`, `license-unverified`, `budget-exhausted`): `3`
- upstream/response (`response-invalid`, `upstream-403-manual`, `upstream-429-manual`, `upstream-unavailable`): `4`
