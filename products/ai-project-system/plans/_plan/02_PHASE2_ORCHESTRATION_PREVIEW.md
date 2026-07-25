---
role: DESIGN_PHASE2
scope: 청크 위치추적 + 원문 미리보기 + 영역×계층 기반 병렬 오케스트레이션
status: 게이트 2 PASS — **§1(위치추적)·미리보기 화면 뼈대 구현 완료(2026-07-18)**: `ingestion/chunking.py`(char_start/end+heading_path) + `ingestion/document_store.py` + `agent-view/preview.html`(분할뷰). **§3(영역×계층 그룹핑) 구현 완료(2026-07-19)**: `backend/domain/requirements/conflict_detection.py`의 `group_tasks_by_area_layer()` + `detect_conflicts_within_groups()`(이중 안전망) — `tests/test_task_manager.py` 3건 추가, 전체 51 pass. **§2-3(상태변경 액션)·§2-4(PII 클릭스루 게이트) 프론트-백엔드 연결 완료(2026-07-20)**: `frontend/views/requirements.html`(액션 열 3버튼)·`frontend/views/preview.html`(상태변경 버튼 + PII 게이트 오버레이)이 기존 `backend/adapters/api/requirements_api.py`의 `POST /requirements/{req_id}/status`·`GET /requirements/{req_id}/preview`를 root-absolute 상대경로(`/requirements/...`)로 직접 호출 — `backend/server.py`의 `StaticFiles("frontend")` 마운트가 같은 오리진으로 서빙한다는 사실을 실측(curl 스모크) 확인 후 그 경로 그대로 사용(신규 API 없음, 백엔드 코드 변경 없음, CRZ). **게이트 2-B PASS(설계만, 2026-07-20 추가)**: §5(청킹 검수 순환 루프 — 재청킹 요청 액션·`rechunk_queue.jsonl`)·§6(문서 전체 청크 경계 시각화 뷰) — 사용자가 "청크→분류→채번 요약만 있고 검수 순환·심층 시각화가 없다"고 지적한 것을 반영한 설계 보강, 구현 미착수. **§6 코드 구현 완료(2026-07-20) — documents.html 신규**: `backend/adapters/api/documents_api.py`(`GET /documents/{doc_id}/chunk-map` 신규 라우터, `requirements_api`의 envelope·에러코드·PII 게이트 로그 재사용)+`frontend/views/documents.html`(신규 — 문서 전체 렌더링 + 경계점 스윕 알고리즘으로 gap/overlap 일반해 계산, 블록 클릭 시 읽기전용 팝오버 + preview.html로 이동 링크, GNB/LNB 셸 적용) — §6-3 진입점은 (B) 신규 화면으로 확정(LNB "문서/청킹 관리" 준비중 항목을 이 화면으로 활성화하는 안은 shell-nav.html 소유 에이전트에게 위임, 이 세션에서 직접 수정하지 않음). `tests/test_documents_api.py` 4건 추가, 전체 123 pass, uvicorn 실기동 curl 스모크 확인.
**§5 코드 구현 완료(2026-07-20)**: `RequirementRecord.supersedes_req_id` 필드 +
`RequirementStore.request_rechunk()`(`set_status(REJECTED, reason="[RECHUNK] ...")` 재사용 +
`rechunk_queue.jsonl` append) + `POST /requirements/{req_id}/rechunk` API(기존 `.../status`와
동일 envelope·락 패턴) + `requirements.html`에 "재청킹 요청" 버튼 추가(셸 구조 무변경, 사유
prompt 입력 + suggested_char_start/end 파라미터 전달). 테스트 5건 추가, 전체 138 pass(§10
구현분 포함), uvicorn 실기동 curl 스모크 확인(rechunk 성공/사유누락 422/queue append 확인).
**§8 신규 설계 추가(2026-07-25, 구현 미착수)**: 좌표(bbox) 기반 페이지 이미지 시각화
오버레이 — `/aegis-oneshot-plan`으로 AskUserQuestion 확정(텍스트 배경블록 근사 기각, 실제
좌표+페이지 렌더링 선택) 후 PyMuPDF(기 설치) 단일 파이프라인 + LibreOffice 변환 브리지
아키텍처로 설계. **실측: 이 개발환경에 LibreOffice 미설치**(W4 착수 전 설치 필요, 사용자
승인 대기) — W1(PDF 뼈대)·W0(문장 하이라이트 배경→글자색 CSS 1줄)·W6(데이터필드 확장)은
LibreOffice 없이도 착수 가능. 코드 구현은 전부 미착수(설계만, 사용자 지시대로).
**전체 구현 완료(2026-07-25 후속 턴)**: W0·W1·W2·W3·W5·W6 병렬/직접 구현 완료(pytest
319 passed) + 원본 PDF 미저장 갭 해소(directive D-d65a28f2, `documents_raw/{doc_id}.pdf`
저장 배선, 321 passed) + **W4 LibreOffice 변환 브리지 완료**(평식 승인 → `winget install
TheDocumentFoundation.LibreOffice` → `backend/adapters/office_convert/libreoffice_bridge.py`
+ 실제 DOCX→PDF 변환 통합테스트로 검증, 324 passed). **DOCX/PPTX 라우팅 배선 완료(2026-07-25, 같은 턴 후속)**: `document_upload_service.
process_uploaded_file()`이 .docx/.pptx 업로드 시 LibreOffice로 PDF 변환을 먼저 시도하고
(성공 시 마크다운도 변환된 PDF에서 재추출 — char_start/char_end와 bbox가 항상 같은
텍스트 소스를 쓰게 해 오프셋 불일치 위험 원천 차단), 변환 실패는 네이티브 어댑터로 조용히
폴백(업로드 자체는 절대 안 막음). `documents_api.upload_document()`도 원본 확장자가
아니라 `UploadResult.pdf_bytes_for_page_render` 존재 여부로 `documents_raw/{doc_id}.pdf`
저장을 결정하도록 수정. **실통합 테스트로 검증**(mock 아님 — 실제 DOCX 생성→실제
LibreOffice 변환→실제 요구사항 채번→page_number/bbox 필드 실제로 채워짐까지 확인),
전체 회귀 325 passed. §8 설계~구현 전 과정 완결.
updated: 2026-07-25
---

# 2차 설계 — 위치추적 미리보기 + 병렬 오케스트레이션

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 이전: [`01_PHASE1_DATA_MODEL.md`](./01_PHASE1_DATA_MODEL.md) | 다음: [`03_PHASE3_AGENT_GRAPHIFY.md`](./03_PHASE3_AGENT_GRAPHIFY.md)

> **전제**: 1차 게이트 통과분(6축 데이터 모델)이 이미 있다는 가정 위에서 설계한다. 최초
> 초안 시점엔 `layer_code` 코드값·철회 사유 필드가 미확정이었으나, 2026-07-18 보강
> 라운드에서 1차 설계 §2-1·§2-3-A로 전부 해소됐다(`01_PHASE1_DATA_MODEL.md` 참조) — 이
> 문서의 나머지 설계는 그 해소된 확정값을 그대로 전제로 삼는다.

## §1. 청크 위치추적(location tracking) 설계

### §1-1. 현재 상태(실측) — 무엇이 없는가

`ingestion/chunking.py`의 `Chunk` 데이터클래스는 현재 `chunk_id`·`content`·`parent_id`·
`global_context`만 가진다. **원본 문서 내 정확한 위치(페이지/좌표/타임스탬프) 정보가 없다** —
`source_ref`가 사실상 `chunk_id`(`{doc_id}::child:{i}`)를 재사용하는 수준이라, "이 요구사항이
원문서 몇 페이지 몇 번째 문단에서 나왔는가"를 사람이 원문을 다시 뒤져야 확인 가능한 상태다.
이번 요청("요구사항 번호 클릭 → 미리보기 → 해당 위치")의 전제조건이 비어있다는 뜻 — 이걸
메우는 것이 2차의 핵심.

### §1-2. 신규 `SourceLocation` 구조 (문서 포맷별 좌표계)

문서 포맷마다 "위치"의 의미가 다르므로 하나의 통합 구조에 포맷별 좌표를 선택적으로 담는다:

```python
@dataclass
class SourceLocation:
    doc_id: str
    doc_filename: str
    doc_format: str  # ".docx" / ".pdf" / ".pptx" / ".txt" / ".md" / "audio"
    heading_path: list[str] = field(default_factory=list)  # 마크다운 변환 후 헤딩 경로 (모든 포맷 공통, DOCX/PDF도 마크다운화되므로 1차 구현 대상)
    char_start: int | None = None   # 정규화된 마크다운 내 문자 오프셋
    char_end: int | None = None
    page_number: int | None = None       # PDF/PPTX — 슬라이드=페이지로 취급 (2차 이후, 원본 바이너리 좌표 필요)
    timestamp_start_ms: int | None = None  # 녹음(오디오) 전용
    timestamp_end_ms: int | None = None
```

`heading_path` + `char_start/end`는 **모든 포맷 공통**으로 즉시 구현 가능하다 — 어차피
`ingestion/router.py`가 모든 입력을 마크다운으로 정규화하기 때문에, 정규화된 마크다운
기준 좌표만 잡으면 DOCX/PDF/TXT를 구분할 필요가 없다. `page_number`(원본 PDF 페이지)·
`timestamp_*`(오디오)는 **원본 바이너리를 다시 참조해야 하는 좌표**라 구현 난이도가 높다.

### §1-3. 단계적 범위 제한 (과잉설계 회피, T57 PVS)

| 범위 | 구현 시점 | 근거 |
|---|---|---|
| `heading_path` + `char_start/end` (정규화 마크다운 기준) | **2차 즉시 구현 대상** | 이미 있는 마크다운 정규화 파이프라인 위에 오프셋만 추가하면 됨 |
| `page_number`(PDF/PPTX 원본 좌표) | **2차 설계에는 포함, 구현은 3차 이후** | 마크다운 변환 시 페이지 경계 정보가 현재 파서(`docx_adapter.py`)에 없음 — 파서 자체 확장 필요(별도 착수 단위) |
| `timestamp_*`(녹음) | **3차 이후 별도 착수 단위로 분리** | 녹음은 STT(음성인식) 자체가 아직 미구현(ingestion/router.py의 `vision_describe`/`unstructured_parse` 전략에 음성 라인 없음) — 이번 재설계로 신규 전략(`speech_to_text`) 추가만 설계하고 구현은 후속 |

## §2. 원문 미리보기 UI 설계

### §2-1. 상호작용 흐름

```
agent-view/requirements.html 테이블의 REQ ID 클릭
  → 모달 오픈 (agent-view/preview-modal — 신규 컴포넌트)
  → source_location.doc_id로 정규화된 마크다운 원문 fetch
  → char_start~char_end 구간을 스크롤+하이라이트(노란 배경, tokens.css --warn 연하게)
  → heading_path를 breadcrumb으로 상단에 표시("문서명 > 2장 > 보안 요건")
```

### §2-2. 1차 게이트 지적사항 반영 — 시각화 인지 포인트 확장

이전 세션에서 만든 `requirements.html`의 "시각화 인지 포인트"(색상 배지·신뢰도 막대바) 원칙을
그대로 계승해 미리보기 모달에도 적용한다:
- 하이라이트 색상은 `doc_type_confidence`·`area_confidence`가 낮을수록(§1차 설계 classifier
  결과) 더 옅은 경고색으로 표시 — "이 위치가 맞는지 사람이 특히 더 확인해야 함"을 색으로 전달
- breadcrumb 옆에 신뢰도 배지 병기 → 미리보기 자체가 "요구사항 신뢰도를 명확히 하는" 사용자
  원 목적(§1 원요청 3번)을 직접 구현

### §2-3. 관리 포인트 — 사람이 확인 후 상태를 바꾸는 액션

기존 `requirements.html`은 읽기 전용이었다(직전 세션 §다음작업 3번 미결). 이번 2차 설계에서
"미리보기로 확인 후 그 자리에서 확정" 액션을 붙인다:

```
미리보기 모달 하단: [수용(ACCEPTED)] [반려(REJECTED, 사유 필수입력)] [철회(WITHDRAWN, 사유 필수입력)] [보류]
  → RequirementStore.set_status(req_id, status, actor=현재_로그인_사용자, reason=사유입력값)
    (1차 설계 §2-3-A에서 확정된 시그니처 그대로 — 신규 API 설계 없음)
```

이 액션이 붙어야 라이프사이클 상태(1차 §2-3)가 실제로 전이될 수 있다 — 1차 설계의
`RECEIVED→...→ACCEPTED/REJECTED/WITHDRAWN` 전이는 이 미리보기 화면의 사람 확인 액션이
유일한 진입점. **행위자(actor) 기록 미결(이전 라운드 미결 #3)은 1차 §2-3-A의
`status_history`로 해소 완료** — 이 화면은 로그인 사용자 식별자를 `actor`로 그대로
넘기기만 하면 된다(별도 설계 불필요).

### §2-4. 문서 접근제어(PII) — 미리보기 게이트 (이전 라운드 미결 #4 해소)

`plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md` §3에서 확정한 `contains_pii` 플래그와
클릭스루 게이트를 이 미리보기 모달이 그대로 구현한다:

```
모달 오픈 요청
  → source_location.contains_pii == true?
      YES → "민감정보 열람 확인" 확인창 먼저 표시(workbase DATA_TYPES_DEF의 pii ⚠ 패턴)
            → 확인 클릭 시 preview_access_log.jsonl에 {req_id, actor, ts, granted:true} 기록
            → 그 다음에만 §1의 하이라이트 렌더링 진행
      NO  → 바로 §1 렌더링
```

이 게이트는 0차 마법사(§5 정보 접근 정책)에서 고른 기본 정책(개인별/역할별/전체공유)에 따라
"확인창만으로 충분"(전체공유)인지 "역할 재확인까지 필요"(역할별)인지 갈리지만, **역할 인증
자체의 구현(로그인 시스템)은 이 재설계 범위 밖**이다(00_PROJECT_CONSTITUTION.md §1 — 이
프로젝트는 인증 시스템을 만드는 프로젝트가 아님, 헌법 §4 드리프트 체크리스트 판정: NO이면
범위 밖 — 여기선 "정책을 반영할 지점 설계"까지만 하고 인증 자체 구현은 하지 않는 것이 맞음).

**PII 게이트 실제 활성화 완료(2026-07-19)** — `RequirementRecord.contains_pii`가 그동안
필드 자체가 없어 `requirements_api.py`의 `getattr(record, "contains_pii", False)`가 항상
기본값(False)만 반환하는 사실상 no-op이었다(실 결함). `backend/domain/requirements/
pii_detector.py`(정규식+키워드 기반 결정론적 스캔, classifier.py와 동일 스타일)를 추가해
`RequirementStore.add_from_classification()` 시점에 실제로 채우도록 수정했다. 한계: 정규식/
키워드 매칭이라 문맥을 이해하지 못하며, 미탐(false negative)보다 오탐(false positive)을
허용하는 비대칭 설계(관대한 판정) — 완전한 PII 탐지는 범위 밖이고 사람의 최종 확인이 여전히
필요하다.

## §3. 영역(area)×계층(layer) 기반 병렬 오케스트레이션

### §3-1. 기존 충돌탐지 확장

`orchestrator/task_manager.py`의 `detect_area_conflicts()`는 현재 `impact_scope`(파일 경로)
교집합만 본다. 이번 요청("각각 영역에서 나눠서 병렬로 진행")을 위해 **Task 그룹핑 기준**을
추가한다 — 충돌탐지 로직 자체(파일 교집합)는 바꾸지 않고, 그 위에 **그룹핑 레이어**를 얹는다:

```python
def group_tasks_by_area_layer(tasks: list[Task]) -> dict[tuple[str, str], list[Task]]:
    """(area_code, layer_code) 조합별로 태스크를 묶는다 — §PCM-6 DAA의 "분야별 agent 배정" 근거표.
    같은 조합 안에서도 impact_scope 교집합이 있으면 여전히 detect_area_conflicts()로 순차화.
    """
```

이렇게 하면 예: `(area=WEB, layer=UXENV)` 그룹은 agent-1이, `(area=SEC, layer=SYS)` 그룹은
agent-2가 병렬로 가져가되, 두 그룹 사이에 파일 교집합이 생기면(예: 공용 설정 파일) 여전히
`detect_area_conflicts()`가 그 지점만 순차화 대상으로 잡아낸다 — **이중 안전망**(그룹 분리 +
파일단위 충돌탐지).

### §3-2. §PCM 시뮬레이션 (품질검토 게이트 2 필수 항목)

실제 구현 전, 가상의 요구사항 세트로 그룹핑이 의도대로 동작하는지 표 형태로 미리 검증한다
(2차 승인 후 구현 단계에서 스크립트로 실행):

| 그룹 | 예상 Task 수 | impact_scope 예시 | 다른 그룹과 교집합 |
|---|---|---|---|
| (WEB, UXENV) | N1 | `frontend/*` | 없음(예상) |
| (SEC, SYS) | N2 | `core_was_block/adapters/db/*` | (DB, SYS)와 교집합 가능성 — 실측 필요 |
| (DB, SYS) | N3 | `core_was_block/adapters/db/*` | 위와 동일 파일 — **순차화 대상 후보** |

→ 이 표는 설계 단계의 **예시**이며 실제 그룹핑 결과는 구현 후 `detect_area_conflicts()`
실행으로 대체(추정을 확정처럼 쓰지 않음).

## §4. 품질검토 게이트 2 — MPCR 7관점 + §PCM 시뮬레이션

| 관점 | 검토 결과 |
|---|---|
| 개발 | `char_start/end` 방식은 마크다운 정규화가 이미 있어 구현 난이도 낮음(D2). `page_number`/`timestamp`는 파서 확장이 필요해 별도 착수 단위(D3)로 분리한 것이 적절 |
| 설계 | 미리보기 모달의 상태변경 액션(§2-3)이 1차 설계의 라이프사이클 전이(§2-3)의 유일한 진입점이 되므로, 이 화면 없이는 1차 설계가 "종이 위 상태머신"에 그침 — **2차가 1차를 실제로 살리는 필수 단계**임을 확인 |
| 운영 | 그룹핑 레이어가 기존 충돌탐지를 대체하지 않고 감싸는 방식이라, 그룹핑이 잘못되어도 최종 안전망(파일단위 충돌탐지)이 남아있어 운영 리스크 낮음 |
| 정보안정성 | §2-4에서 PII 클릭스루 게이트 + 접근로그로 해소(2026-07-18 보강) — 단, 역할 인증 자체는 범위 밖으로 명시적 제외(헌법 §4 판정) |
| 헌법정합 | 00_PROJECT_CONSTITUTION.md §3 "Phase 4가 본체"라는 원칙과 정합 — 병렬 오케스트레이션은 그 본체를 실행 가능하게 하는 확장 |
| 검증 | §PCM 시뮬레이션 표는 예시일 뿐 실측이 아님을 명시(추정≠확정) — 구현 단계에서 실측 대체 필수 |
| 책임 | §2-3에서 1차 §2-3-A `status_history(actor, reason)`로 해소(2026-07-18 보강) — 이 화면은 로그인 사용자 식별자만 전달 |

**게이트 2 결론(2026-07-18 보강 라운드 갱신)**: **PASS** — 문서 접근제어·행위자 기록 모두
해소. 남은 것은 §PCM 시뮬레이션의 "예시=실측 아님" 한계뿐이며, 이는 애초에 구현 단계에서만
해소 가능한 성격이라 설계 단계의 정상적인 한계로 남긴다(추정을 확정처럼 포장하지 않음).

## §5. 청킹 검수 순환 루프 명시화 (2026-07-20 보강 — 사용자 심층 지적 반영)

> **지적 원문 요지**: "문서 등록 → 청킹 → 결과 출력 → 맞으면 저장, 틀리면 다시 청킹"이라는
> **순환** 구조가 지금까지 문서에 한 줄로만("청크→분류→채번") 요약돼 있고, 이 순환이 실제로
> 어떻게 도는지(특히 "틀리면 다시 청킹" 쪽)가 없었다. §2-3에 이미 있던 "확정/반려/철회/보류"
> 액션은 **REQ 개별 건의 승인 여부**만 다뤘을 뿐, "청킹 경계 자체가 틀렸다"는 판단과 그에 따른
> **재청킹 트리거**는 별도로 다룬 적이 없다 — 이 절이 그 빠진 고리를 메운다.

### §5-1. 전체 순환 흐름 (문서 등록 → 청킹 → 확인 → 저장/재청킹)

```
[1] 문서 등록 (ingestion/router.py 업로드)
      ↓
[2] 청킹 실행 (ingestion/chunking.py) → Chunk(char_start/end, heading_path) 생성
      ↓
[3] 분류기 실행 (classifier.py) → RequirementRecord 생성
      lifecycle_status = RECEIVED → CLASSIFIED 또는 UNDER_REVIEW(확신 낮으면, §2-3 그대로)
      ↓
[4] 화면 출력 — requirements.html(목록) + preview.html(원문 하이라이트, §1~§2)
      "사람이 맞는지 확인 대기" 상태를 lifecycle_status 배지로 그대로 노출(신규 상태값 없음)
      ↓
[5] 사람 판단 (미리보기 모달 액션, §2-3 버튼 확장)
      ├─ "맞음"  → set_status(ACCEPTED, actor, reason=None)         ← 기존 §2-3 그대로
      ├─ "청킹 경계는 맞으나 분류가 틀림" → set_status(REJECTED, actor, reason="분류 오류: ...")
      │                                     ← 기존 §2-3 그대로 (재청킹 불필요, 분류만 재검토 대상)
      └─ "청킹 경계 자체가 틀림"(예: 두 요구사항이 한 청크로 합쳐짐/문장이 중간에 잘림)
             → **신규 액션 "재청킹 요청"** (§5-2)
```

핵심: 5번 분기 중 마지막 하나(청킹 경계 오류)만 §2-3의 기존 REJECTED로는 표현이 안 된다 —
REJECTED는 "이 요구사항 후보 자체를 기각"이라는 뜻이지 "청킹을 다시 하라"는 뜻이 아니기
때문이다. 이 둘을 섞으면 반려 사유 로그에 "재청킹 필요"와 "이 내용 자체가 요구사항이
아님"이 뒤섞여 감사 불가능해진다(§2-3-A `status_history` 설계 원칙과 충돌) — 그래서
별도 액션으로 분리한다.

### §5-2. "재청킹 요청" 액션 설계 (신규, 기존 자산 재사용 최대화)

```python
# 설계만 — RequirementStore에 추가할 함수 (set_status()와 동일 시그니처 패턴, CRZ)
def request_rechunk(req_id: str, actor: str, reason: str,
                     suggested_char_start: int | None = None,
                     suggested_char_end: int | None = None) -> None:
    """청킹 경계 오류 신고. 기존 set_status() 재사용 + 재청킹 큐에 append만 추가.

    1) set_status(req_id, "REJECTED", actor, reason=f"[RECHUNK] {reason}")
       → 기존 REJECTED 상태·status_history를 그대로 재사용(신규 상태값 미도입, CRZ).
         reason 접두사 "[RECHUNK]"로 "청킹 재검토" 사유만 구분(단순 반려와 필터링 가능).
    2) rechunk_queue.jsonl에 {req_id, doc_id, actor, reason, suggested_char_start,
       suggested_char_end, requested_at} 1줄 append — §9-2(agent_role_usage.json)와
       동일한 "ground-truth 이벤트 로그" 패턴 재사용(신규 큐 엔진 발명 없음).
    """
```

**재청킹 실행(설계만 — 자동화 범위 밖 명시)**: `rechunk_queue.jsonl`을 소비해 실제로
`ingestion/chunking.py`를 재실행하는 것은 **이번 설계 범위 밖**이다 — 자동 재청킹(경계를
LLM이 알아서 다시 판단)은 오탐 시 무한 반복 위험이 있어(T98 AIP 정직성), 운영자/agent가
큐를 확인하고 `suggested_char_start/end` 힌트를 참고해 **수동으로 재실행 트리거**하는 것을
1차 설계로 채택한다. 재실행 결과로 생성되는 새 REQ는 원본과의 연결을 위해 아래 필드를 쓴다:

```python
# RequirementRecord에 추가할 설계 필드 (신규, 2026-07-20)
supersedes_req_id: str | None = None   # 이 REQ가 재청킹으로 대체한 이전 REQ의 req_id
```

원본 REQ는 `lifecycle_status=WITHDRAWN`(기존 §2-3 상태 재사용)으로 전이하며
`status_history`에 `to_status="WITHDRAWN", reason="[RECHUNK] 재청킹으로 대체됨 → {새 req_id}"`를
남긴다 — 물리 삭제 없이 이력 보존(§2-3-A 원칙 그대로).

### §5-3. UI 반영 (설계만 — `preview.html` 기존 버튼 그룹 확장)

§2-3의 `[수용][반려][철회][보류]` 버튼 그룹에 **[재청킹 요청]** 버튼을 추가하고, 클릭 시
사유 입력 + (선택) 하이라이트 드래그로 `suggested_char_start/end`를 사람이 직접 보정 지정할
수 있게 한다 — 이미 §1의 `char_start/end` 하이라이트 렌더링이 있으므로, 그 위에 "드래그로
범위 재지정" 인터랙션만 얹으면 된다(신규 렌더링 엔진 없음, CRZ).

## §6. 청킹 시각화 심화 — 문서 전체 청크 경계 뷰 (2026-07-20 보강, 신규 절)

> **지적 원문 요지**: "청킹 시각화 영역도 '이 구분이 청킹되었습니다' 해당 문서를
> 미리보기해서 '그 문서 여기가 해당 요구사항이에요' 이렇게 더 심층적으로" — 기존 §1~§2
> 미리보기는 이미 확정된 **REQ 1건**의 위치를 문서 안에서 하이라이트하는 "REQ 중심" 뷰였다.
> 이 절은 그와 **관계는 있지만 다른 뷰**를 추가한다 — 문서 1건 전체를 열어 **그 문서에서
> 나온 모든 청크의 경계를 한 화면에서** 색 블록으로 구분해 보여주는 "문서 중심" 뷰다.

### §6-1. 기존 §2 미리보기와의 관계 (명시적 구분)

| 구분 | §2 기존 미리보기 모달 | §6 신규 문서 청크맵 뷰 |
|---|---|---|
| 진입점 | `requirements.html`에서 **REQ ID** 클릭 | `documents.html`(문서 목록, 기존 자산 — 없으면 신규 진입점 필요)에서 **문서명** 클릭 |
| 보여주는 범위 | 그 REQ 1건의 `char_start~char_end` 구간만 하이라이트 | 그 문서에서 나온 **모든 REQ의 청크 경계**를 문서 전체에 걸쳐 동시에 표시 |
| 목적 | "이 요구사항이 맞는지"(§2-3 확인) | "이 문서가 전체적으로 잘 청킹됐는지"(경계 누락·중복·과대 청크 발견) |
| 상호작용 | 확정/반려/철회/재청킹(§5) 액션 | 블록 클릭 → 그 블록이 어느 REQ가 됐는지 보여주는 팝오버(읽기 전용, 상태변경은 §2 모달로 위임 — 중복 액션 UI 금지) |

### §6-2. 청크맵 렌더링 설계

```
GET /requirements?doc_id={doc_id} → 그 문서에서 나온 RequirementRecord 전체를
                                     char_start 오름차순 정렬
  → 정규화된 마크다운 원문(§1과 동일 fetch 경로) 위에 각 REQ의 [char_start, char_end)
    구간을 순서대로 다른 배경색 블록으로 렌더링(예: 짝수/홀수 REQ 번갈아 파스텔 톤 —
    tokens.css 기존 팔레트 재사용, 신규 색상 시스템 발명 없음)
  → 각 블록 위에 작은 배지: "REQ-BIZ-SEC-003" (요약 라벨, hover 시 전체 설명 tooltip)
  → 블록과 블록 "사이"에 아무 REQ도 커버하지 않는 구간(gap)이 있으면
    빗금(hatched) 회색으로 별도 표시 — "이 구간은 어느 요구사항으로도 청킹되지 않았다"는
    진단 신호(청킹 누락 발견용, 사용자가 요구한 "이 구분이 청킹되었습니다"의 반대 신호까지
    포함해야 완전한 심층 시각화라고 판단)
  → 블록끼리 char 구간이 겹치면(중복 청킹) 겹침 구간을 사선 패턴 + 경고 배지로 표시
```

### §6-3. 신규 진입점 필요성 (미확정 — 사용자 확인 필요 항목)

§6-1 표의 "문서명 클릭" 진입점은 현재 `frontend/views/`에 문서 목록 화면 자체가 없다면
신설이 필요하다(실측 필요 — 이번 설계 세션에서는 `frontend/` 수정이 금지돼 있어 실제
파일 존재 여부를 직접 열람하지 않았다, 추정하지 않음). 다음 중 하나로 해소한다:

- (A) `requirements.html` 상단에 "문서별 보기" 토글을 추가해 이미 있는 화면 안에서 진입
- (B) 신규 `documents.html` 화면을 만든다

**이번 설계는 (A)를 1차 권고안으로 제시**한다 — 신규 화면 파일을 늘리지 않고 기존
`requirements.html`의 그룹핑 축(이미 area/layer 배지 그룹핑이 있음, §2-1)에 "문서별 그룹핑"
모드를 하나 더 추가하는 편이 화면 증식을 피할 수 있다(T57 PVS 과잉설계 회피). 최종 채택은
구현 착수 시 사용자 확인 후 확정.

## §7. 품질검토 게이트 2-B — §5·§6 보강분 MPCR 7관점 (2026-07-20)

| 관점 | 검토 결과 |
|---|---|
| 개발 | §5는 기존 `set_status()`·`status_history`·이벤트로그 패턴(§9-2와 동일) 재사용이라 구현 난이도 낮음(D2). §6은 신규 렌더링 로직(구간 정렬·gap/overlap 계산)이 필요해 D3 — 별도 착수 단위 |
| 설계 | §5는 "반려(내용 문제)"와 "재청킹(경계 문제)"을 사유 접두사로 구분해 감사 로그 오염을 막았고, §6은 §2 모달과 액션을 중복시키지 않도록 읽기전용으로 역할을 분리 |
| 운영 | 재청킹은 자동 실행하지 않고 큐+수동 트리거로 설계해 오탐 무한반복 리스크를 차단(§5-2) |
| 정보안정성 | §6도 §2-4 PII 게이트를 그대로 상속해야 함 — 문서 전체를 펼치는 뷰이므로 PII 문서는 §2-4 클릭스루 게이트를 문서맵 진입 시점에도 동일하게 적용(신규 예외 없음) |
| 헌법정합 | `supersedes_req_id`·`rechunk_queue.jsonl` 모두 신규 상태값·신규 엔진 최소화 원칙(CRZ) 준수 |
| 검증 | §6-3 진입점은 미확정으로 정직하게 남김(추정 금지, T98 AIP) — 구현 단계에서 실측·사용자 확인 필요 |
| 책임 | 재청킹 이력이 `status_history`(WITHDRAWN 사유에 새 req_id 링크) + `rechunk_queue.jsonl`(요청 시점 근거) 이중으로 남아 "누가 왜 재청킹을 요청했고 무엇으로 대체됐는지" 추적 가능 |

**게이트 2-B 결론**: **PASS(조건부)** — §6-3 진입점 선택만 사용자 확인 후 확정, 나머지는
기존 게이트 2 통과 자산 위의 순수 확장이라 재검토 불필요.

## §8. 좌표 기반 페이지 이미지 시각화 오버레이 (2026-07-25 신규 설계, 구현 미착수)

> **AskUserQuestion 확정 사항(2026-07-25)**: ①영역 표시=실제 좌표(bbox) 기반 이미지 오버레이
> (텍스트 배경블록 아님) ②이미지출처=실제 페이지를 이미지로 렌더링(다운로드 링크 아님)
> ③문장 하이라이트=배경색(mark.hit) 대신 글자색(font-color) 방식으로 교체 ④범위=신규 인프라
> 포함 전체 요구사항 **설계까지만** 이번 턴 진행, 구현은 별도 승인 후.

### §8-1. 문제 — 현재 한계(§1·§2 대비)

§1·§2가 구현한 위치추적은 **평면 텍스트 오프셋**(`char_start`/`char_end`) 기반이다 — 이는
문서를 markdown 유사 텍스트로 평탄화한 뒤의 좌표라, **원본 문서의 시각적 레이아웃(페이지·
좌표·이미지)과는 무관**하다. 그 결과:
- "영역을 사각형으로 표시" — 평탄화된 텍스트에는애초에 x/y 좌표가 없어 불가능(현재는 배경색
  블록으로만 근사 가능, §8-0의 사용자 선택으로 이 근사는 기각됨).
- "이미지 출처 페이지 미리보기" — `RequirementRecord`에 `page_number`/이미지 자체가 없다
  (`source_is_image=True`인 문서는 `preview.html:287`에서 "미구현" 경고만 표시하고 종료).

### §8-2. 아키텍처 결정 — PDF 통합 파이프라인(CRZ, 신규 인프라 최소화)

**실측(2026-07-25)**: 이 프로젝트에는 이미 `pymupdf 1.28.0`이 설치돼 있으나 `pdf_adapter.py`는
`pdfplumber`만 쓴다(`pdf2image`는 미설치). PyMuPDF는 텍스트+bbox 추출과 페이지 래스터화
(`page.get_pixmap()`)를 **별도 시스템 의존성(poppler 등) 없이 단일 라이브러리로 동시 처리**
할 수 있다 — 이것이 유일하게 신규 설치가 필요 없는 경로다.

```
[모든 문서 포맷] → (PDF 아니면) LibreOffice headless 변환 → 표준 PDF
                                                              ↓
                                          PyMuPDF 단일 파이프라인
                                   (텍스트+bbox 추출 · 페이지→PNG 래스터화)
                                                              ↓
                                   RequirementRecord.page_number/bbox 채움
                                   + data/page_images/{doc_id}/{page}.png 캐시
```

- **DOCX/PPTX**: python-docx/python-pptx는 페이지 레이아웃 개념이 없거나(docx) bbox는 있어도
  래스터화 기능이 없다(pptx) — 별도 포맷별 렌더러를 만들지 않고(T57 PVS over-eng 회피) 표준
  변환 도구(LibreOffice `soffice --headless --convert-to pdf`)로 PDF화한 뒤 **위 PDF 파이프라인
  하나만 재사용**한다(CRZ — 렌더링 로직 1곳).
- **HWP**: 기존 `hwp_adapter.py`가 이미 "검증 미확정" 상태(README 자인) — 이번 §8 범위에서
  제외(뼈대 우선순위, §8-4). HWP→PDF 변환기(hwp5 등)가 붙으면 동일 파이프라인에 자연 편입.
- **순수 텍스트/스캔이미지 문서**(TXT, 이미지형): 페이지 개념 자체가 없거나(txt) 이미 이미지
  자체(스캔본)이므로 별도 경로(§8-5) — bbox 파이프라인과 충돌 없음.

### §8-3. 데이터 모델 확장 (`RequirementRecord`, `backend/adapters/persistence/requirement_store.py`)

| 신규 필드 | 타입 | 의미 |
|---|---|---|
| `page_number` | `int \| None` | 원본 문서 기준 1-based 페이지 번호(변환 후 PDF 기준) |
| `bbox` | `list[float] \| None` | `[x0, y0, x1, y1]` — PDF 포인트 좌표계(PyMuPDF 기본 단위) |
| `page_image_ready` | `bool` | 해당 페이지 이미지가 `data/page_images/`에 캐시됐는지(지연 렌더링 여부 판단) |

**하위 호환**: 이 3필드는 전부 옵셔널(`None`/`False` 기본값) — 기존 레코드(§1·§2 생성분)는
그대로 두고(재처리 강제 없음, CRZ), `preview.html`은 `bbox is None`이면 **기존 텍스트
하이라이트로 폴백**한다(§8-6). 즉 신규 파이프라인 도입 전 이미 존재하는 요구사항은 깨지지
않는다 — 점진 확장(T47 PFE).

### §8-4. 백엔드 신규 컴포넌트

| 컴포넌트 | 위치(신규) | 역할 |
|---|---|---|
| `backend/adapters/parsers/pdf_bbox_adapter.py` | 신규 | PyMuPDF로 텍스트+bbox+페이지 추출(기존 `pdf_adapter.py`의 `ParserPort` 구현은 유지 — 이 신규 어댑터가 char_start/end와 함께 bbox까지 채우는 **상위 확장판**, 기존 계약 위반 없음) |
| `backend/adapters/office_convert/libreoffice_bridge.py` | 신규 | `soffice --headless --convert-to pdf` subprocess 래퍼(ENV-047 타임아웃 가드 패턴 재사용 — §0-5 Pre-Q 그대로 적용) |
| `backend/application/services/page_render_service.py` | 신규 | `page_number` → PNG 렌더링(PyMuPDF `get_pixmap`) + `data/page_images/{doc_id}/` 캐시 |
| `GET /documents/{doc_id}/page/{page_number}.png` | `documents_api.py`에 라우터 추가(기존 파일 확장, CRZ) | 캐시 hit면 즉시 서빙, miss면 `page_render_service` 호출 후 서빙 — PII 게이트는 기존 `documents_api`의 `confirm_pii` 파라미터·로그 패턴 그대로 재사용 |

**뼈대 우선순위(§3-A 원칙 적용)**: PDF 경로(§8-2 하단 절반)가 **뼈대** — DOCX/PPTX는 이
뼈대에 "LibreOffice 변환"이라는 전처리 1단계만 얹는 **의존 관계**이지 별도 구현이 아니다.
즉 작업 순서는 반드시 PDF 파이프라인 완성 → 변환 브리지 연결 순이며, 거꾸로(변환 브리지부터)
진행하면 재작업이 발생한다.

### §8-5. 프론트엔드 신규 컴포넌트 (`preview.html` 확장)

- **모드 토글**: 기존 텍스트 뷰(`#doc-view`)는 유지하고, `bbox`가 있는 레코드를 선택하면
  **이미지 오버레이 모드**로 자동 전환(사용자가 매번 수동 토글하지 않아도 되게 — 레코드
  유무로 자동 판단, §8-3 폴백 원칙과 대칭).
- **렌더링 구조**: `<div class="page-frame">` 안에 `<img src=".../page/{n}.png">` + 절대위치
  `<div class="bbox-overlay">`(bbox를 이미지 렌더 크기에 맞춰 %로 환산해 `left/top/width/height`
  지정, 반투명 배경 `background: color-mix(in srgb, var(--color-brand-primary) 25%, transparent)`)
  — Canvas가 아니라 **absolute-positioned div**를 쓰는 이유: 기존 `mark.hit`류 DOM 오버레이
  패턴과 기술 스택 일관성 유지(CRZ, 신규 렌더링 기술 도입 최소화 — Canvas는 클릭 이벤트·접근성
  처리가 더 필요해 이 규모에는 과함, T57 PVS).
- **이미지 출처 페이지**: `source_is_image=True`인 레코드는 `page_number`만 있으면(bbox 없어도)
  페이지 이미지 자체를 표시(현재 `preview.html:287`의 "미구현" 경고를 대체) — bbox는 없지만
  페이지 렌더링 인프라(§8-4)는 동일하게 재사용.
- **문장 하이라이트 방식 변경(확정 사항 ③, 별도 저위험 작업)**: `mark.hit { background: ... }`
  →`mark.hit { background: none; color: var(--color-brand-primary); font-weight: 700; }`로
  1줄 CSS 교체 — bbox 파이프라인과 **완전히 독립**이라 먼저 착수 가능(D1, `components.css`
  또는 `preview.html` 인라인 스타일 1곳만 수정).

### §8-6. 폴백·마이그레이션 원칙

- `bbox is None` → 기존 텍스트 하이라이트 뷰 그대로(§8-3 하위호환).
- `source_is_image=True` and `page_number is None` → 현재의 "미구현" 경고 문구 유지(이 경우만
  진짜 미지원 — 스캔 이미지 자체의 OCR 없이는 bbox도 페이지도 만들 수 없음).
- 기존 요구사항을 일괄 재처리(re-chunk)해 bbox를 소급 채우는 것은 **이번 §8 범위 밖**(별도
  배치 작업, 대량 재생성 성격이라 T100 §3 절대하한 — 평식 승인 필요).

### §8-7. 작업 단위 전략 분해 (Stage 5 — /aegis-oneshot-plan 요청사항)

| WORK | 분야(Domain) | 역할(R) | 복잡도 | 기술 | 영역(Scope) | 의존 |
|---|---|---|---|---|---|---|
| **W0. 문장 하이라이트 배경→글자색 전환** | frontend | R2 구현 | SIMPLE(D1) | CSS | `preview.html`(`mark.hit` 스타일 1곳) | 없음 — 즉시 착수 가능 |
| **W1. PDF bbox+페이지 추출 어댑터** | backend/parser | R3설계→R2구현→R5검증 | COMPLEX(D3~4) | Python/PyMuPDF | `backend/adapters/parsers/pdf_bbox_adapter.py`(신규), `requirement_extraction_service.py`(bbox 필드 배선) | **뼈대** — 아래 전부가 의존 |
| **W2. 페이지 PNG 렌더+캐시 서비스** | backend/service | R2구현→R5검증 | MEDIUM(D3) | Python/PyMuPDF | `page_render_service.py`(신규) | W1 |
| **W3. 페이지 이미지 서빙 엔드포인트** | backend/api | R2구현 | SIMPLE(D2) | FastAPI | `documents_api.py`(라우터 추가) | W2 |
| **W4. LibreOffice 변환 브리지** | backend/adapter | R3설계→R2구현→R5검증(타임아웃 실측 필수, §0-5 Pre-Q) | COMPLEX(D3~4) | subprocess/LibreOffice | `libreoffice_bridge.py`(신규) | W1(변환 결과가 W1 파이프라인으로 들어감) |
| **W5. 프론트 이미지 오버레이 모드** | frontend | R3설계→R2구현→R5검증(다관점: 반응형 %환산 정확도) | COMPLEX(D3) | JS/CSS | `preview.html`(모드 토글+오버레이 렌더) | W1+W3 |
| **W6. RequirementRecord 필드 확장** | backend/domain | R2구현 | SIMPLE(D1~2) | Python dataclass | `requirement_store.py`(3필드 추가, 옵셔널 기본값) | 없음 — W1보다 먼저 또는 동시 가능 |

**§PCM 분류**: W0·W6은 서로 CLEAR(다른 파일) — 즉시 병렬/순차 무관 착수 가능(D1~2, 승인
없이도 진행 가능한 범위로 판단되나 사용자가 "설계까지만" 명시했으므로 이번 턴엔 착수 안 함).
W1(뼈대)→{W2→W3, W4}→W5 순서 강제(의존관계, §3-A 뼈대 우선순위) — W2/W4는 W1 완료 후 병렬
가능(서로 다른 파일, CLEAR).

### §8-8. 품질검토 — MPCR 7관점 (착수 전 예비 검토, §4·§7과 동일 패턴)

| 관점 | 검토 결과 |
|---|---|
| 개발 | PyMuPDF가 이미 설치돼 있어 신규 의존성은 LibreOffice(시스템 바이너리)뿐 — **실측 확인(2026-07-25): 이 개발 환경에 LibreOffice 미설치**(`where soffice` 실패, 기본 설치 경로 부재). W1(PDF 뼈대)은 이 설치와 무관하게 착수 가능하나, **W4(DOCX/PPTX 변환 브리지)는 LibreOffice 설치가 선결조건** — 신규 소프트웨어 설치는 코드 변경이 아니라 환경 변경이므로 착수 전 사용자 승인 필요(설치 자체는 비가역은 아니나 개발 환경 구성 변경) |
| 설계 | PDF를 뼈대로 삼아 DOCX/PPTX를 "변환 후 재사용"하는 구조는 포맷별 파서 3개를 만드는 것보다 유지보수 단일화(CRZ) |
| 운영 | 페이지 이미지 캐시(`data/page_images/`)가 무한 증가할 수 있음 — T84 IBP 백업 정책·용량 정리 정책은 이번 설계 범위 밖(후속 갭으로 정직 표기) |
| 정보안정성 | 페이지 이미지 서빙도 §2-4 PII 게이트를 그대로 통과해야 함(§8-4에 명시) — 원문 텍스트보다 이미지가 오히려 더 민감할 수 있어(스캔본에 개인정보 그대로 노출) 게이트 우회 절대 금지 |
| 헌법정합 | 신규 필드 전부 옵셔널 기본값(§8-3) — 00_PROJECT_CONSTITUTION §4 드리프트 체크리스트("구조화된 요구사항 항목에 기여하는가") 충족, 청크 신뢰도 검증(원 목표 §3)의 직접 강화 |
| 검증 | LibreOffice 변환 타임아웃(대용량 문서 hang 가능성, DES-027 계열 리스크)은 W4 구현 시 §0-5 Pre-Q 가드 필수 적용 대상으로 미리 표시 |
| 책임 | 폴백 원칙(§8-6)이 있어 W1~W5 중 일부만 완료돼도 기존 기능(§1·§2)이 회귀하지 않음 — 점진 배포 가능 |

**게이트 결론**: **PASS(조건부)** — LibreOffice 설치 여부(개발환경 실측 필요)와 페이지이미지
캐시 정리 정책(후속 갭)만 표기, 나머지는 기존 자산 재사용 원칙(CRZ)으로 설계 완결.
