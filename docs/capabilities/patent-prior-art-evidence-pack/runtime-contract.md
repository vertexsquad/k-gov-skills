# Runtime contract — `patent-prior-art-evidence-pack`

- 입력: exact JSON fields `case_id`, `review_type`, `summary`, `facts`, `source_refs`, `as_of_date`, `redaction_status`.
- 개인정보: 비식별 합성 입력만 허용하며 direct-identifier no-match는 완전 마스킹 증명이 아닙니다.
- 출처: credential-free HTTPS와 capability별 exact host allowlist만 허용합니다.
- 날짜: `retrieved_on <= as_of_date`; URL·본문·facts를 결과에 재출력하지 않습니다.
- lookup 입력: KIPRIS/KIPO 공개 HTTPS URL. 명시적 base-host allowlist, 공개 IP 확인, bounded response, redirect 거부, credential query/fragment 거부를 적용합니다.
- 출력: lookup은 title/status/content-type/길이/hash, admission은 count/status/check identifiers만 반환하며 입력 case ID·URL·본문·facts를 재출력하지 않습니다.
- side effect: GET 조회만 허용합니다. 원본 변경, 제출, 게시, 발송을 수행하지 않습니다.
- 증거 상태: `fixture-verified`; live smoke는 catalog manifest 값을 따릅니다.
- 금지 판단: `novelty-decision, inventive-step-decision, infringement-or-registration-opinion`.
