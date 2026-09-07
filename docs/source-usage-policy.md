# Source usage and evidence policy

이 문서는 외부 자료의 접근·검증·이용허락을 서로 다른 증거로 관리하기 위한 공통 경계입니다. 법률 자문이나 개별 자료의 이용허락 판정이 아닙니다.

## 현재 machine status

Catalog가 정본입니다. 현재 22개 capability는 모두 `fixture-verified`이며 `live_smoke`는 19개 `not-run`, 3개 `blocked`입니다. 활성화된 source policy와 `passed` live smoke는 없습니다.

과거 URL 도달 또는 policy 도입 전 실행 기록은 historical observation으로만 보존합니다. 현재 live evidence로 승격하지 않습니다.

## 다섯 evidence dimension

| 차원 | 필요한 증거 | 보증하지 않는 것 |
|---|---|---|
| Fixture contract | 합성·결정적 입력, expected CLI/schema/exit, network-disabled 성공 | URL 도달, 실제 자료 조회, 자료의 현재성 |
| URL reachability | 조회 시각, exact URL, HTTP 결과와 제한된 metadata | policy 승인, 내용의 진실성, 약관·저작권 허가 |
| Policy-authorized live retrieval | exact operation ID, reviewed policy revision/digest, 허용된 projected fields, enforcer-issued receipt | cryptographic authenticity, 법적 이용허락, substantive correctness |
| Substantive correctness | 담당자의 원문·기준일·맥락·상충자료 검토 | 저작권·약관 준수나 최종 행정 판단 |
| Human/legal approval | 권한 있는 담당자의 공개·복제·변형·제출 결정과 필요한 법무 검토 | runtime 또는 receipt가 대신하는 자동 승인 |

한 차원의 성공을 다른 차원의 성공으로 표현하지 않습니다.

## Live smoke admission

`live_smoke=passed`는 다음 항목을 한 evidence record에서 모두 확인한 경우에만 기록합니다.

1. 실행 날짜와 exact operation ID
2. 실행 당시 reviewed policy revision과 digest
3. Policy-authorized retrieval의 enforcer-issued source receipt
4. 실제로 반환한 projected field 목록
5. Credential·raw body·직접 식별자가 출력되지 않았다는 확인
6. 결과를 확인한 수동 검토자와 검토 범위

URL `200`, robots 허용, fixture 성공, injected transport 성공 중 하나만으로는 `passed`가 아닙니다.

## Robots, terms, copyright and data licenses

- `robots.txt`는 자동 접근에 관한 사이트 운영자의 신호입니다. 저작권, 이용약관, 데이터 라이선스 또는 재배포 허가가 아닙니다.
- 약관 검토와 라이선스 검토는 robots 판정과 별도로 수행합니다.
- 공공누리 표시는 저작물별 유형과 조건을 확인해야 합니다. 출처표시, 상업 이용, 변경 허용 여부가 유형마다 다릅니다.
- 공공데이터포털 자료도 제3자 권리가 포함될 수 있습니다. Dataset별 이용조건과 공공누리 유형을 확인하고 필요한 별도 허락을 확보합니다.
- 국가법령정보센터의 official record라는 사실은 출처 식별에 도움이 되지만, runtime이 법적 해석이나 재이용 허가를 판단했다는 뜻이 아닙니다.

공식 확인 URL:

- 국가법령정보센터: https://law.go.kr/main.html
- 공공누리 유형과 이용조건: https://www.kogl.or.kr/info/license.do
- 공공데이터포털 이용정책: https://www.data.go.kr/ugs/selectPortalPolicyView.do

## Receipt boundary

`source_receipt`는 runtime이 기록한 integrity/provenance metadata입니다. Operation ID, policy ID/revision/digest와 처리 outcome을 연결하지만 다음을 증명하지 않습니다.

- 응답 발행자의 cryptographic identity
- 내용의 진실성·완전성·최신성
- 법률 해석이나 개별 사안 적용
- 저작권·약관·라이선스상 이용허락
- 담당자의 공개·제출·의사결정 승인

문서에서 receipt를 `authentic`, `법적 증명`, `이용허락`으로 부르지 않습니다. 필요한 경우 `enforcer-issued receipt` 또는 `runtime integrity/provenance record`로 표현합니다.

## Privacy and deletion boundary

직접 식별자 scanner는 알려진 형식의 일부를 탐지하는 보조 gate입니다. `no-match`는 비식별 완료나 개인정보 부재의 증명이 아닙니다. 원문은 승인된 환경에서 담당자가 별도로 검토해야 합니다.

Runtime은 자신의 반환값과 관리하는 제한된 state만 통제합니다. 다음 사본을 발견하거나 purge할 수 없습니다.

- Shell stdout/stderr redirection과 terminal scrollback
- Downstream process·clipboard·temporary file
- Backup, snapshot, swap, crash dump
- Caller가 저장한 database·log·object storage
- 이미 복제·전송된 자료

Python 객체 해제는 secure memory wipe가 아니며 filesystem 삭제는 SSD의 물리적 secure deletion을 보증하지 않습니다. 민감 원문을 runtime에 입력하지 않는 것이 우선입니다.

## 담당자 체크리스트

1. Fixture, reachability, authorized retrieval, substantive review, approval 중 어떤 차원의 증거인지 표시합니다.
2. Catalog policy가 disabled·expired·unreviewed이면 live 실행을 중단합니다.
3. Source별 robots, terms, license와 dataset/저작물별 공공누리 조건을 각각 확인합니다.
4. Receipt에서 raw body나 credential을 복원하려 하지 않습니다.
5. 직접 식별자 no-match만으로 공개·제출하지 않습니다.
6. 최종 인용, 복제, 변형, 재배포, 결재, 제출은 권한 있는 담당자가 승인합니다.
