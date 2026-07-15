# Runtime contract — `official-source-research`

- 입력: 공개 한국 공공기관 HTTPS URL
- 허용 도메인: adapter의 명시적 `ALLOWED_HOSTS`에 등록된 정부·공공기관 host와 그 하위 host만 허용한다. TLD suffix만으로 공식성을 간주하지 않는다.
- credential/proxy: 없음
- 네트워크 안전: 사용자정보 포함 URL, 비HTTPS, 비공인 IP, 비허용 host를 거부한다.
- side effect: GET 조회와 응답 metadata/hash 계산만 수행한다.
- fixture 검증: `python3 -m kgov_runtime.capabilities.official_source_research --fixture`
- 로그인·제출·민감정보·페이지 내 action은 실행하지 않는다.
