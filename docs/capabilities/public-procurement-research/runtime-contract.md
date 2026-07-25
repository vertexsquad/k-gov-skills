# Runtime contract — `public-procurement-research`

- 서비스: 나라장터 발주계획 공개 API
- 기본 endpoint: `https://apis.data.go.kr/1230000/ao/OrderPlanSttusService`
- 허용 host: `apis.data.go.kr`, `g2b.go.kr`, `d2b.go.kr`, `s2b.kr`
- credential: 사용자 환경변수 `DATA_GO_KR_API_KEY`; 저장소·로그·fixture에 값을 기록하지 않는다.
- proxy: 선택 사항이며 endpoint override는 허용 host와 HTTPS/public-IP 검증을 통과해야 한다.
- side effect: 조회 전용. 제출·예약·계약·원본 변경을 실행하지 않는다.
- fixture 검증: `python3 -m kgov_runtime.capabilities.public_procurement_research --fixture`
- live 검증: 필요한 query parameter와 사용자 소유 credential을 준비한 뒤에만 실행한다.
- 상태 표기: fixture PASS와 live smoke PASS를 서로 대체하지 않는다.
- AI 제품 readiness는 공개 조회 결과를 담당자가 검토하는 절차 확장일 뿐 적격·인증·성능을 자동 판정하지 않는다.
