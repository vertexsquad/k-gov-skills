# Runtime contract — `civil-complaint-triage-draft`

- 입력: 비식별 처리된 민원 JSON 한 개. 필수 필드는 `title`, `body`, `channel`, `received_at`, `redaction_status`다.
- credential/proxy/network: 없음. adapter는 로컬 파일만 읽고 외부 요청을 하지 않는다.
- side effect: 입력 admission과 검토용 workflow metadata 출력만 수행한다. 답변 작성·등록·발송은 하지 않는다.
- bounds: 입력 파일 100 KB, 제목 200자, 본문 20,000자, 채널 50자 이하.
- redaction gate: `redaction_status`가 `redacted`가 아니면 거부하고, 전화번호·주민등록번호·이메일 형태가 남아 있어도 거부한다.
- 한계: 기본 식별자 패턴이 검출되지 않았다는 결과는 완전한 비식별 증거가 아니다. 담당자가 원문을 별도로 검토해야 한다.
- 출력 privacy: 제목·본문·received_at을 되돌려 출력하거나 hash로 보존하지 않는다.
- fixture 검증: `python3 -m kgov_runtime.capabilities.civil_complaint_triage_draft --fixture`
- 로컬 입력 검사: `python3 -m kgov_runtime.capabilities.civil_complaint_triage_draft <redacted-input.json>`
- 소관 확정, 처분·수급·허가·제재 판단, 답변 등록·발송은 이 adapter 범위 밖이며 담당 공무원에게 수동 전환한다.
- fixture 성공은 실제 민원 데이터, 기관 업무망, 국민신문고 연계 또는 개인정보 검증 완료를 의미하지 않는다.
