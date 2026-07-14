# Runtime contract — `kosis-official-statistics`

- 서비스: KOSIS OpenAPI
- 기본 endpoint: `https://kosis.kr/openapi/Param/statisticsParameterData.do`
- 허용 host: `kosis.kr`
- credential: 사용자 환경변수 `KOSIS_API_KEY`; 저장소·로그·fixture에 값을 기록하지 않는다.
- proxy: 선택 사항이며 endpoint override는 허용 host와 HTTPS/public-IP 검증을 통과해야 한다.
- side effect: 조회 전용. 제출·예약·계약·원본 변경을 실행하지 않는다.
- fixture 검증: `python3 skills/kosis-official-statistics/scripts/adapter.py --fixture`
- live 검증: 필요한 query parameter와 사용자 소유 credential을 준비한 뒤에만 실행한다.
- 상태 표기: fixture PASS와 live smoke PASS를 서로 대체하지 않는다.
