# KIPRIS 선행기술 근거 묶음

## 사용 범위
- 공개 KIPRIS/KIPO 문헌 URL의 bounded GET 조회와 응답 metadata/hash 확인
- 합성·비식별 입력의 `patent-prior-art-evidence-pack` 검토 초안 admission
- 공식 근거 URL과 조회일을 보존한 담당자 검토용 체크리스트

## 절차
1. KIPRIS/KIPO 공개문헌 URL을 read-only lookup으로 확인합니다.
2. 원문 개인정보를 제거하고 `redaction_status=redacted`로 준비합니다.
3. `prior-art-evidence-pack, claim-element-mapping` 중 하나의 검토 유형을 선택합니다.
4. 공식 출처와 조회일을 근거별로 기록합니다.
5. adapter가 반환한 required checks와 evidence gap을 담당자가 검토합니다.
6. 최종 판단·승인·제출·게시·발송은 수행하지 않습니다.

## 실행
- fixture: `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack --fixture`
- local input: `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack <redacted.json>`
- official lookup: `python3 -m kgov_runtime.capabilities.patent_prior_art_evidence_pack --lookup-url <KIPRIS-or-KIPO-HTTPS-URL>`
- fixture PASS는 URL 도달이나 live workflow 성공을 의미하지 않습니다.
