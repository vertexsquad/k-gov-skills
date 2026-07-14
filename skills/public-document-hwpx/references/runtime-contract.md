# Runtime contract — `public-document-hwpx`

- 입력: 로컬 `.hwpx` ZIP/XML 문서 한 개
- credential/proxy/network: 없음
- side effect: 문서 읽기만 수행하며 원본을 추출·수정·덮어쓰지 않는다.
- bounds: archive entry 2,000개, 총 비압축 크기 50 MB 이하
- fixture 검증: `python3 skills/public-document-hwpx/scripts/adapter.py --fixture`
- 실제 문서 검증: `python3 skills/public-document-hwpx/scripts/adapter.py <path.hwpx>`
- 원본 변경·제출·결재는 이 adapter 범위 밖이며 수동 전환한다.
