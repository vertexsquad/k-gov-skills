# Runtime contract — `regulated-trade-procedure-precheck`

- 입력: exact JSON fields `case_id`, `review_type`, `summary`, `facts`, `source_refs`, `as_of_date`, `redaction_status`.
- 검토 유형: `customs-origin-document-precheck`, `trade-procedure-document-precheck`만 허용합니다.
- 개인정보: 비식별 합성 입력만 허용하며 direct-identifier no-match는 완전 마스킹 증명이 아닙니다.
- 출처: credential-free HTTPS와 exact host `www.customs.go.kr`, `unipass.customs.go.kr`만 허용합니다.
- 날짜: `retrieved_on <= as_of_date`; URL·본문·facts·case ID를 결과에 재출력하지 않습니다.
- 출력: count/status/check identifiers만 포함하는 `regulated-trade-review-draft-only` 초안 admission.
- side effect: 없음. 네트워크 조회, 원산지 판정, 신고, 제출, 통관, 제재 실행을 수행하지 않습니다.
- 증거 상태: `fixture-verified`; `live_smoke=not-run`이며 URL 도달과 실제 업무 성공을 구분합니다.
- 금지 판단: `origin-determination`, `customs-declaration-or-submission`, `clearance-or-enforcement-action`.
