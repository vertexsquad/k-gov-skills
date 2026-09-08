# Runtime contract — `patent-prior-art-evidence-pack`

- 입력: exact JSON fields `case_id`, `review_type`, `summary`, `facts`, `source_refs`, `as_of_date`, `redaction_status`.
- 개인정보: 비식별 합성 입력만 허용하며 direct-identifier no-match는 완전 마스킹 증명이 아닙니다.
- 출처: credential-free HTTPS와 capability별 exact host allowlist만 허용합니다.
- 날짜: `retrieved_on <= as_of_date`; URL·본문·facts를 결과에 재출력하지 않습니다.
- lookup 입력: KIPRIS 또는 지식재산처의 legacy KIPO 공개 HTTPS URL. 명시적 base-host allowlist, 공개 IP 확인, bounded response, redirect 거부, credential query/fragment 거부를 적용합니다.
- 출력: lookup은 title/status/content-type/길이/hash, admission은 count/status/check identifiers만 반환하며 입력 case ID·URL·본문·facts를 재출력하지 않습니다.
- side effect: GET 조회만 허용합니다. 원본 변경, 제출, 게시, 발송을 수행하지 않습니다.
- 증거 상태: `fixture-verified`; live smoke는 catalog manifest 값을 따릅니다.
- 금지 판단: `novelty-decision, inventive-step-decision, infringement-or-registration-opinion`.

## Separate local admission and policy-enforced lookup

`review_case(payload)` remains a call to the shared local admission validator.
It never constructs an enforcer, initializes policy state, resolves DNS or opens
a URL. `--fixture` and local input-file mode follow this same network-free path.
The synthetic fixture includes KIPRIS and legacy KIPO declarations with the
current disabled policies' `manual-review` receipts. These admit only a draft pending
human review, never an official lookup or substantive patent judgment.

`inspect_patent_source(url, policy, enforcer)` accepts the exact registry-owned
policy object and a real `HttpPolicyEnforcer`. Transport injection belongs under
the enforcer via `HttpTransport`, not a capability-level opener/resolver bypass.
Every lookup uses the registered operation
`kgov/patent-prior-art-evidence-pack/inspect-source/v1`:

| Exact host | Registry-owned policy | Current attribution |
| --- | --- | --- |
| `www.kipris.or.kr` | `kipris-web` | KIPRIS |
| `www.kipo.go.kr` | `kipo-web` | 지식재산처 |

Wrong policy objects, clones, parent-domain/subdomain substitutions and
credential-bearing URLs cannot authorize a lookup. Live construction validates
input, loads the current catalog with `date.today()`, and authorizes before
state creation or DNS. The current disabled catalog therefore stops lookup mode
before network or persistent state. Default transport preserves DNS-pinned TLS,
proxy rejection, robots checks, bounded reads, no redirects and no retries.
Before policy lookup, URL paths are strict-percent/UTF-8 decoded and NFKC
normalized, then checked for direct identifiers and Unicode controls. Malformed
percent escapes/UTF-8, remaining percent signs (including nested encodings),
encoded path separators and traversal forms fail with non-reflecting input
errors. Safe paths are re-encoded canonically before policy, state or transport
work. Thus `%40` email paths and their nested variants cannot reach lookup.

State-path precedence is `KGOV_POLICY_STATE_PATH`, then
`$XDG_STATE_HOME/k-gov-skills/policy-state.sqlite3`, then
`~/.local/state/k-gov-skills/policy-state.sqlite3`. Policy budgets/cooldowns remain
durable and shared; state failures or digest conflicts never reset the budget.

## Metadata and receipt boundary

Only the enforcer projector sees page text. Lookup returns exactly `url`
(scheme/host/path, no query), `status`, normalized `content_type`, `title`, UTF-8
`content_length`, `sha256`, `execution_mode=official-live`,
`manual_review_required=true`, and `source_receipt`.
The enforcer-issued source receipt retains `operation_id`, `policy_id`,
`policy_revision`, `policy_digest`, and `outcome=allowed`. There is one receipt
per successfully projected source page, not per wire exchange. Required robots
requests reserve budget separately but return no source receipt; failed
fetches/projections likewise produce none.
Titles are HTML-unescaped and NFKC-normalized inside the projector. Unicode
`C*`, `Zl` and `Zp` characters (including bidi controls and ESC) are rejected
before whitespace normalization or receipt creation, with non-reflecting
`response-invalid` errors.
Before receipt creation, titles reuse the legal capability's pure bounded
semantic-view identifier scanner. Percent decoding, HTML entity decoding, and
NFKC are each allowed exactly once, including their one-pass compositions, so
percent-to-entity identifiers and fullwidth ampersand entities are rejected for
both KIPRIS and KIPO. Invalid encoded UTF-8 and any intermediate view over
250,000 UTF-8 bytes fail as `response-invalid`. Neither a lookup result nor an
allowed receipt is returned for those failures. Views are never written back:
nested `%2540` becomes only `%40`, not `@`, while safe title spelling and
enforcer-issued receipt fields remain unchanged. Importing this pure scanner
performs no credential, policy-state, or network work; local admission remains
local.

Only HTML/XHTML pages can be projected. PDF, image, SVG, drawing, binary and
other attachment media are rejected even when a broad reviewed response policy
permits that media type. Lookup does not follow links, download drawings or
extract attachments. Permission for a parent page grants no child attachment
rights, redistribution license or admission assurance.

An HTTP `source_receipt` is **not** a local-admission `policy_receipt`; lookup
never promotes one into the other. Local admission checks receipt metadata
against its exact source URL/date and current policy. Reusing an unchanged
parent-page receipt for a child attachment fails. Even matching local metadata
is non-cryptographic and does not prove live retrieval, authenticity or licensing.

| Exit | Meaning |
| --- | --- |
| `0` | Successful page lookup or accepted local draft pending human review |
| `2` | Invalid mode/input/URL, credential-bearing URL or unreadable input |
| `3` | Disabled/stale policy, robots/terms/license denial, rate/state failure |
| `4` | Upstream failure, 401/403/429/CAPTCHA or invalid response/projection |

`1` is the shared review-blocked exit, but the existing local admission validator
either accepts a human-review draft or raises an input error; merely requiring
human review does not produce exit `1`. Errors use stable non-reflecting output.
Stable protocol status tokens are implementation constants selected by runtime
control flow, not credential-derived reflection. Coincidental equality with a
credential does not remove the necessary status or change its exit code;
receipt, caller and upstream material must still remain suppressed when unsafe.
Fixture and injected-transport success do not establish live-source success.

Fixture, URL reachability, policy-authorized retrieval, substantive correctness와 human/legal approval은 별도 차원입니다. 공통 robots·license·receipt·삭제 한계는 [source usage policy](../../source-usage-policy.md)를 따릅니다.

## 2026-09-08 출처 identity·이용조건 검토 (#68)

공개 정책·기관 페이지를 검토했으며 runtime의 `inspect-source` live 실행은
하지 않았습니다. 아래 관측은 enforcer-issued receipt나 실행·재이용 허가가 아닙니다.

| 공식 근거 | 관측과 한계 |
| --- | --- |
| [legacy root](https://www.kipo.go.kr/), [legacy MainApp.do](https://www.kipo.go.kr/ko/MainApp.do), [현행 root](https://www.moip.go.kr/) | 지식재산처 표기와 MOIP footer를 확인했습니다. 현행 root의 fetch 최종 경로는 `/ko/MainApp.do`였습니다. 기존 origin 전체가 사라졌다는 근거는 아닙니다. |
| [Main.do](https://www.kipo.go.kr/ko/Main.do), [확장자 없는 MainApp](https://www.kipo.go.kr/ko/MainApp) | 페이지를 찾을 수 없다는 안내와 MOIP URL을 확인했습니다. 정상 페이지를 제공하는 `.do` 경로와 구분하며 특정 경로의 결과를 host 전체 장애로 확대하지 않습니다. |
| [KIPO robots](https://www.kipo.go.kr/robots.txt), [MOIP robots](https://www.moip.go.kr/robots.txt) | Googlebot에 대한 일부 경로 제한을 확인했습니다. 이를 모든 agent의 전면 차단 또는 저작물 재이용 허가로 취급하지 않습니다. |
| [KIPRIS robots](https://www.kipris.or.kr/robots.txt) | wildcard `Disallow: /`와 이름 지정 검색봇의 예외를 확인했습니다. `k-gov-skills`는 해당 예외가 아니며 검색봇으로 가장하지 않습니다. |
| [KIPRIS 이용약관](https://www.kipris.or.kr/khome/member/rules/terms.do) | 2026-07-21 시행 약관입니다. 제공기관을 특허정보원으로 명시하며, 제12조제8호는 허용 범위 밖 자동화 접속·수집과 보호조치 우회를 제한합니다. 제16조의 권리 귀속·영리 재이용 조건은 별도로 적용됩니다. |
| [KIPRIS 저작권정책](https://kipris.or.kr/khome/member/rules/copyright.do) | 정당한 범위의 인용·출처표시와 국가가 권리를 전부 보유한 저작물의 자유이용 범위를 설명합니다. 모든 자료나 자동수집에 대한 일괄 허가가 아닙니다. |
| [지식재산처 저작권정책](https://www.moip.go.kr/kipo/kipoContentView.do?menuCd=SCD0200538) | 공공누리 표시·유형별 이용조건·출처표시 및 표시 없는 자료의 사전협의 조건을 확인했습니다. 페이지 관측만으로 개별 첨부물의 권리를 판단하지 않습니다. |
| [지식재산처 누리집 이용안내](https://www.moip.go.kr/ko/kpoContentView.do?menuCd=SCD0201249) | 이메일 무단수집 거부와 이용안내를 확인했습니다. 독립적인 전체 이용약관 정본은 이번 검토에서 확정하지 못했으며, 이용안내를 그 대용으로 취급하지 않습니다. |

이 근거에 따라 `kipo-web`의 현행 기관 표기를 지식재산처로 정정하고 revision을
`2`로 올렸습니다. 기존 ID·origin·exact host mapping은 유지하며 MOIP나 특허로
host를 추가하지 않습니다. KIPRIS 정책의 identity와 revision은 유지합니다.

KIPO 합성 fixture는 현재 정책 institution·revision·digest와 일치하도록 갱신합니다.
그 fixture의 기존 날짜는 유지하며 새 실제 조회를 주장하지 않습니다. 이전
revision/digest의 receipt를 현행 정책의 증거로 재사용하지 않습니다.
기존 local admission과 lookup 분리, `manual-review` receipt 의미도 유지합니다.

두 정책의 `enabled=false`와 실행 검토 범주의 `unreviewed`는 그대로입니다.
이번 기관·정책 문헌 검토는 활성화 가능한 robots·terms·license·rate·response
승인 묶음을 확정한 것이 아니며 `live_smoke=not-run`을 변경하지 않습니다.
