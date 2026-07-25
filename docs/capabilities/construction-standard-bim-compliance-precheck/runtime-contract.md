# Runtime contract — `construction-standard-bim-compliance-precheck`

- 입력: exact JSON fields `case_id`, `review_type`, `summary`, `facts`, `source_refs`, `as_of_date`, `redaction_status`.
- 개인정보: 비식별 합성 입력만 허용하며 direct-identifier no-match는 완전 마스킹 증명이 아닙니다.
- 출처: credential-free HTTPS와 capability별 exact host allowlist만 허용합니다.
- 날짜: `retrieved_on <= as_of_date`; URL·본문·facts를 결과에 재출력하지 않습니다.
- 출력: count/status/check identifiers만 포함하는 `engineering-precheck-draft-only` 초안 admission.
- side effect: 없음. 네트워크 조회, 원본 변경, 제출, 게시, 발송을 수행하지 않습니다.
- 증거 상태: `fixture-verified`; live smoke는 catalog manifest 값을 따릅니다.
- 금지 판단: `engineering-approval, structural-safety-decision, completion-certification`.
