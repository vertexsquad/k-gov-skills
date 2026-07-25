# Runtime contract

## Input

JSON object with exactly these fields:

- `document_type`: `official-letter`, `report`, `meeting-material`, `press-release`,
  `audit-response`, `council-agenda`, or `education-notice`
- `title`: non-empty string, at most 200 characters
- `body`: non-empty string, at most 30,000 characters
- `purpose`: non-empty string, at most 500 characters
- `source_refs`: at most 20 credential-free HTTPS URLs on the exact administrative-source host allowlist; query strings and fragments are forbidden
- `redaction_status`: literal `redacted`

The direct-identifier scan covers common Korean mobile-number, resident-registration-number-shaped, and email patterns. A no-match is not proof of complete redaction.

## Execution boundary

- Local JSON validation only; no network, credential, proxy, or file-format mutation.
- Unsupported document types, unknown or missing fields, oversized values, non-allowlisted or credential-bearing source references, unredacted input, and detected direct identifiers fail closed.
- Fixture data is synthetic and contains no actual administrative or personal data.

## Output

The adapter returns document type, character counts, source-reference count, deterministic review flags, `draft-review-only`, and `manual_review_required=true`. It never returns the input title, body, purpose, or source URL values.

Institution-specific format compliance, legal or statistical conclusions, approval, registration, publication, and sending remain manual handoff responsibilities.
