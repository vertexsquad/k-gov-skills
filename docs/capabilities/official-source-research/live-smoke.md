# Historical reachability observation — `official-source-research`

> 현재 catalog 상태는 `fixture-verified` / `live_smoke=blocked`입니다. 아래 기록은 policy registry와 receipt admission 계약 도입 전의 URL 도달 관측이며 현재 `passed` live evidence가 아닙니다.

- 실행 시각: `2026-07-14 21:41:20 KST`
- 당시 명령(구조 이관 전): `python3 skills/official-source-research/scripts/adapter.py 'https://www.gov.kr/'`
- 현재 module 경로(정책 차단됨): `python3 -m kgov_runtime.capabilities.official_source_research 'https://www.gov.kr/'`
- exit code: `0`
- HTTP status: `200`
- title: `정부24`
- content length: `242`
- SHA-256: `21ef1f2305cd29043100d7aec8e08b966b63ab028522c91d962932295ce9c0e4`
- 범위: 공개 GET 응답의 metadata/hash 검증만 수행했습니다. 로그인·제출·페이지 action은 실행하지 않았습니다.
- 주의: 이 결과는 다른 capability의 live endpoint·credential 검증을 대신하지 않습니다.

이 기록에는 현재 요구되는 exact operation, reviewed policy revision/digest, enforcer-issued receipt, projected field 목록과 수동 검토자 evidence가 없습니다. 따라서 [source usage policy](../../source-usage-policy.md)의 live smoke admission을 충족하지 않습니다.
