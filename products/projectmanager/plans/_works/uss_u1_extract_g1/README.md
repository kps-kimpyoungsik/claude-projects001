# USS U1 비정형 추출기 + G1 사용이력 — 작업 문서

착수·완료 2026-09-23 | 상태: **구현 완료 (테스트 5/5, 전체 회귀 0)**
설계 정본: `plans/_opens/universal_structuring_system/00_뼈대설계서.md` §5 L2 · `01_단계지도.md` · `20_데이터셋_관계그래프.md` §9 G1

---

## 1. 왜 이 작업인가 — 설계 검토 결과

요청: 문서·이미지·음성·텍스트 같은 비정형 자료를 공통/특화, 분야·영역·관계 기준으로 지식화하기.
**비정형 업로드를 정형 데이터로 바꾸는 부분**을 보완한다.

실측(2026-09-23):

| 항목 | 설계 | 코드 |
|---|---|---|
| 업로드 입구 | L2 EXTRACT — 어떤 파일이든 조각 + 원본 좌표 | `UploadService`는 **`.xlsx`만** 받음 (`:65`) |
| `source_fragment` / `locator` | 불변식 I1(출처 없는 값 금지)의 기반 | **0건** |
| `case_usage` (G1) | "지금 안 쌓으면 과거 복원 불가" — 최우선 1인일 | **0건** |
| 음성 | **설계에 없음** | — |
| 이미지 | "OCR 보류" 한 줄 | — |

### 1.1 단계지도 정정 — U1은 기준 문서가 없어도 진행할 수 있다

`01_단계지도.md` §3은 `U2 → U1`("무엇을 채울지 알아야 추출 결과를 쓸 데가 있다")을
강제 의존으로 두었다. 그 결과 U1은 **기준 문서 미확보(5턴 연속)** 에 함께 묶였다.

그러나 **U1의 통과 기준**(§14: 같은 내용의 xlsx·docx·pptx·txt에서 동일 항목과 좌표가 나오는지)은
기준 문서 없이도 검증할 수 있다. U2에 의존하는 쪽은 U1이 아니라 **U3(정형화)** 이다.
→ 의존 관계를 `U1 ∥ U2 → U3`로 정정했다(01번 §3에 반영).

### 1.2 이미지·음성 — 받되 지어내지 않는다

OCR/STT 없이 텍스트를 채우면 "출처는 있는데 틀린 근거"가 된다(뼈대 §12).
그렇다고 입구를 막으면 원본을 받지 못해 나중에 엔진이 붙어도 처리할 대상이 없다.
→ **원본은 보관하고 조각 1개**(`kind=image|audio|binary`, `text=NULL`, `confidence=0`)만 남긴다.
나중에 추출 엔진이 붙으면 이 조각들이 처리 대상 목록(작업 큐)이 된다.

---

## 2. 무엇을 만들었나

| 파일 | 내용 |
|---|---|
| `backend/.../source/Extractor.java` | L2 추출기. xlsx(셀)·docx(문단·표)·pptx(도형·표)·txt/md/csv(줄) → `Fragment(locator, kind, text, confidence)`. 이미지·음성·pdf는 원본 조각 1개 |
| `backend/.../source/SourceService.java` | 원본 보관 + sha256 중복 제거(T115) + 조각 적재 + `case_usage` 기록. 실패 시 저장 파일 삭제 |
| `backend/.../source/SourceController.java` | `POST /api/sources` · `GET /api/sources` · `GET /api/sources/{docId}/fragments` |
| `backend/.../resources/schema.sql` | `source_doc` · `source_fragment` · `case_usage` 3개 추가 (**기존 테이블 변경 0**) |
| `backend/.../upload/UploadService.java` | G1 — 엑셀 업로드가 만든 데이터셋·Core 영역을 `case_usage(output)`로 기록. `assertDecodableName` public 전환(재사용) |
| `backend/src/test/.../source/SourceExtractTest.java` | 테스트 5개 (아래) |

### locator 규약 (ADR U-A3 — 문자열 1개)

```
sheet:견적!C5      docx:p12      docx:t1.r3.c2      pptx:s2.sh4      pptx:s2.sh4.r1.c1
txt:L7   md:L7     image:whole   audio:whole        pdf:whole
```

### 입력 거절 (깨진 채 저장하지 않는다)

- 파일명 `U+FFFD` → 거절 (기존 `assertDecodableName` 재사용)
- 텍스트가 UTF-8이 아님(CP949 등) → 거절 (UTF-8로 읽으면 바이트를 버리므로 복원할 수 없다)
- 오피스 3종인데 ZIP 시그니처가 아님 → 거절
- 지원하지 않는 확장자 → 거절(허용 목록을 안내)

---

## 3. 검증 (실측)

`./mvnw test` → **93 run / 0 fail / 0 error** (신규 5 포함, 기존 88 회귀 0). 신규 5건은 이후 단독 재실행에서도 5/5.

| 테스트 | 무엇을 막나 |
|---|---|
| 네 형식에서 같은 항목과 좌표가 나온다 | **U1 통과 기준 그대로.** 빈 문단·빈 줄이 조각이 되지 않는지도 확인 |
| 이미지·음성은 텍스트를 지어내지 않는다 | OCR 없이 `text`가 채워지는 회귀 |
| 적재·중복 제거·사용이력 | 같은 sha256 재업로드 시 조각이 두 벌 생기지 않고, 사용 이력은 2건 남는다 |
| 기존 엑셀 업로드도 사용이력을 남긴다 | G1이 기존 경로에서 빠지는 회귀 |
| 깨진 입력은 거절한다 | CP949 텍스트, 가짜 docx, exe |

---

## 4. 하지 않은 것 (다음 단계)

| 항목 | 이유 | 착수 조건 |
|---|---|---|
| U3 정형화 (조각 → `struct_fact`) | U2(표준)가 있어야 채울 필드가 정해진다 | U2 — **기준 문서 실물 1건** (여전히 차단) |
| OCR/STT/PDF 추출 | 한국어 정확도를 실측하기 전에 붙이면 틀린 근거가 생긴다 | 이미지·음성 원본이 `source_fragment`에 실제로 쌓인 뒤 비중을 측정 (`SELECT kind, COUNT(*) FROM source_fragment GROUP BY kind`) |
| 추출 엔진 포트(interface) | 엔진이 아직 하나도 없다 | 첫 OCR/STT/PDFBox 엔진이 붙을 때 `Extractor`의 해당 분기를 포트로 분리 |
| 화면 (`/data/sources` 연결) | 이번 범위는 백엔드 입구까지 | U4 검토 화면과 함께 (좌: 폼 / 우: 원본 하이라이트 — locator로 점프) |
| 6축 분류(분야·영역·관계) | 단계지도 §4 보류 — 데이터셋 9개 규모 | 데이터셋 30개 이상 |
| U5-min 측정 루프 | 차단은 없으나 이번 범위 밖 | 다음 착수 후보 1순위 |
