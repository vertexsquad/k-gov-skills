# Live smoke evidence — `official-source-research`

## 2026-09-08: 승인된 root pilot의 정책 검토 보류 (#67)

- 대상: `https://www.gov.kr/` 한 URL, 단일 caller.
- operation: `kgov/official-source-research/inspect-page/v1`.
- 검토 기준: `e8dff5d377abf0ce9c6bea1cd34dbac5a49a2d89`.
- 실행 승인: 주인님은 공개 정책 검토 후 허용되는 경우에만 단발 조회하도록 승인했습니다. 자동 retry, redirect 추적, 다른 target, blanket enablement는 포함하지 않습니다.
- 기술 검토자: OmO. 주인님의 조건부 실행 승인은 출처 운영자의 이용허락이나 실제 결과에 대한 수동 검토를 대신하지 않습니다.

### 확인한 공개 정책

| 근거 | 관측과 적용 범위 |
|---|---|
| [robots.txt](https://www.gov.kr/robots.txt) | `User-agent: *`, `Disallow: /`와 `Allow: /$`를 함께 확인했습니다. 기존 matcher는 terminal `$`를 지원하므로 root를 robots 금지로 판정하지 않습니다. 이는 별도 이용허락이 아닙니다. |
| [현행 이용약관](https://plus.gov.kr/portal/scrtycntr/utztntrms) | 공식 공지 페이지가 연결하는 약관이며 시행일은 2026-03-09입니다. 제14조·제16조에는 자동 로그인, IP 변경/CAPTCHA 우회, 운영 방해 제한이 있습니다. 이 조항을 비로그인 공개 GET 전체의 금지로 확대 해석하지 않습니다. 제16조·제17조의 정보 이용·재배포 조건도 별도로 고려해야 합니다. |
| [저작권보호정책](https://www.gov.kr/portal/cpyrhtPrtc) | 복제·배포 및 영리 이용 조건, 외부 사이트 링크의 통지 조건, 개별 표시된 자유이용 저작물의 예외를 확인했습니다. 이번 metadata/link-only 출력에 대한 조건 적용·충족 근거를 확정하지 못했습니다. |
| [2017년 약관 변경 공지](https://www.gov.kr/portal/ntcItm/43717) | 현행 전체 약관 대신 사용하지 않았습니다. 현재 약관과 저작권 정책의 공식 링크를 확인하는 데 사용했습니다. |

정책 참고자료 조회는 pilot target GET이나 enforcer-issued receipt가 아닙니다. `plus.gov.kr`의 약관을 읽었다고 pilot 대상 origin을 변경한 것도 아닙니다.

### 판정과 실제 실행 증거

이용조건이 확인됐다는 긍정적인 license 승인을 만들지 않았습니다. 이는 root metadata 조회가 법적으로 금지된다는 판단이 아니라, 이번 실행의 정책 승인 근거가 완성되지 않았다는 판단입니다.

- catalog: `gov-kr-web` revision `1`, `enabled=false`; robots/terms/license/rate/response는 기존 `unreviewed`를 유지합니다. 승인된 rate 수치나 review 날짜·만료일을 임의로 만들지 않았습니다.
- 실제 CLI: `python3 -m kgov_runtime.capabilities.official_source_research 'https://www.gov.kr/'`. 비밀값·profile을 상속하지 않는 환경에서 한 번 실행해 exit `3`, stderr `ERROR policy-disabled`, stdout 없음으로 종료했습니다.
- registry 승인 검사가 state 초기화와 DNS/opener보다 먼저 실행되므로 **pilot target GET은 실행되지 않았습니다**. 이는 접근 후 HTTP 403이나 robots 거부를 관측했다는 뜻이 아닙니다.
- 실제 target response와 projected fields는 없고 enforcer-issued receipt도 없습니다. 실행 당시의 reviewed revision/digest나 성공 receipt를 만들어 기록하지 않았습니다.
- 예정 projection은 query 없는 URL, status, content type, title, content length, SHA-256 및 실행/receipt/manual-review metadata뿐입니다. 반환된 target 원문은 없으며 retention은 `raw_content=none`, `receipts=metadata-only`를 유지합니다.
- 동일 CLI의 `--fixture`는 exit `0`, `synthetic-fixture`, null receipt로 성공했습니다. fixture의 HTTP 200은 실제 target 응답이 아닙니다.
- 결과: `fixture-verified` / `live_smoke=blocked` 유지. 원문 재이용·링크 조건의 적용과 충족 여부를 권한 있는 검토자가 확정한 뒤에만 같은 exact operation의 재개를 검토합니다. 운영자 통지나 외부 게시를 대신 수행하지 않았습니다.

정책을 활성화하지 않아 shipped-disabled 전제의 기존 테스트와 synthetic 성공·거부 대조는 변경하지 않았습니다. #59/#61/#65는 이미 main에 반영돼 코드·파일 인계 조건은 충족됐으며, #68은 이번 작업에 포함하지 않았습니다.

## Historical reachability observation

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
