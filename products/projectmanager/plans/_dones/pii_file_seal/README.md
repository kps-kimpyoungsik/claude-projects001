# 업로드 원본 파일 봉인 + 원본 자료 조각 치환 — 작업 문서

착수·완료 2026-09-24 | 상태: **구현·운영 적용 완료 (테스트 119/119)** | 설계 정본: `plans/_opens/pii_protection/00_설계서.md` §8

---

## 1. 무엇을 했나

| 대상 | 전 | 후 |
|---|---|---|
| 새 업로드 원본 (`data/uploads`) | 평문 xlsx 보관 | 적재 후 **봉인**(`.sealed`) · 평문 삭제 · `upload_batch.stored_path` 갱신 |
| 새 원본 자료 (`data/sources`) | 평문 보관 | 추출 후 봉인 · `source_doc.stored_path` 갱신 |
| 원본 자료 조각 본문 (`source_fragment.text`) | 평문 (치환 대상 누락) | 금고 인물 → 토큰 (적재·전환 모두) |
| 기존 원본 19개 (5.7MB) | 평문 | 전환 API 가 봉인 · 평문은 `data/_backup/pre-seal/uploads/` 로 **보류**(개인키 사본 확인 전 복구 경로) |
| 파일명 복구(`FilenameRepair`) | `.xlsx` 만 후보 | `.xlsx.sealed` 도 후보 |

원본은 적재·추출 후 **다시 읽는 코드가 없다**(실측) — 봉인해도 기능 영향 0.

## 2. 형식 — 스트리밍 봉인

`PIIF1` + 감싼키 길이(u16) + RSA-OAEP(AES키) + IV(12) + AES-256-GCM 스트림. 문자열 봉투(base64)는 30MB 파일에서 힙에
원문·암호문·base64·UTF-16 이 동시에 올라가 쓰지 않는다. 개인키가 있으면 **복원해 SHA-256 이 같을 때만** 평문을 지운다.
복원: `java backend/src/main/java/com/aegis/pm/pii/PiiCrypto.java unseal <개인키> <x.sealed> <출력>` (두 형식 자동 판별).

## 3. 운영 적용 검증

- 전환 API: `sealed_files: 19`
- **독립 검증**(단일 파일 도구 + 실제 개인키로 복원 → 보류 평문과 `cmp`): **19/19 일치**.
  첫 시도는 18/19 — 불일치 1건은 이름이 깨진(mojibake) 파일을 명령행 인자로 넘기다 `Path.of` 가 실패한 **검사 도구 쪽**
  문제였다. 영문 임시 이름으로 복사해 재검증 → 일치.
- `upload_batch` 5행 중 4행 경로 갱신 — 나머지 1행은 원래 파일이 없는 이관 기록(경로 칸에 메모).

## 4. 사고와 재발 방지 — 테스트가 실제 원본을 봉인했다

테스트가 전환 폴더를 임시 경로로 바꾸려고 `migration.uploadsDir = …` 로 **필드를 직접** 바꿨다. `PiiMigrationService` 는
`@Transactional` 이라 주입된 것은 **프록시**이고, 필드는 프록시에만 바뀌었다 — 실제 객체는 기본값 `data/uploads` 로 돌았다.
결과: 실제 원본 19개가 **테스트 키**로 봉인됨(실제 개인키로 못 엶). 평문은 보류 폴더로 옮겨지는 경로라 **손실 0** —
19/19 zip 무결성 확인 후 원위치, 잘못된 봉인 파일 삭제.

- 폴더를 **설정값**(`pm.pii.uploads-dir`·`sources-dir`·`hold-dir`)으로만 받게 바꿈 — 테스트는 `@DynamicPropertySource` 로 지정
- `PiiFlowTest @AfterAll` 안전 검사: 실제 `data/uploads` 에 `.sealed` 가 생기거나 실제 보류 폴더가 생기면 실패
- 전체 테스트 전후 실제 `data/uploads` 해시 동일 확인

## 5. 남은 것

| 항목 | 착수 조건 |
|---|---|
| 보류 평문 폐기 (`data/_backup/pre-seal/`, DB 백업 3개) | **개인키 오프라인 사본 확보 확인** |
| 설정 엑셀 원본 3개(프로젝트 루트) | 사용자가 엑셀로 직접 편집하는 작업 파일 — 봉인하면 작업 방식이 깨진다. `wbs.source: db` 전환 후 적재용으로만 쓰면 그때 봉인 가능 |
| 새 업로드 경로의 실서버 E2E | 운영 DB 에 적재가 일어나므로 이번엔 단위 테스트(`sealStored`)로 대신함 — 다음 실제 업로드 때 `sealed: true` 응답 확인 |
