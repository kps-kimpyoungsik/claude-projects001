---
role: DESIGN_UPLOAD_PIPELINE
scope: 문서 업로드 → 청킹 → 분류 → 채번 파이프라인의 "입구" 신설 (Phase 2 청킹 검수 루프의 진입점)
status: 설계+구현 완료 (2026-07-21)
updated: 2026-07-21
---

# 09 — 문서 업로드 파이프라인 (청킹 검수 루프의 빠진 입구)

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 관련: [`02_PHASE2_ORCHESTRATION_PREVIEW.md`](./02_PHASE2_ORCHESTRATION_PREVIEW.md) §5·§6

## §1. 근본원인 진단 (정직하게, T98 AIP)

실측 결과(`grep -rn "UploadFile\|multipart\|/upload" backend/` → 0건) — 이 프로젝트에
**실제 사용자가 파일을 업로드해서 청킹을 트리거하는 경로가 단 한 번도 구현된 적이 없었다.**

왜 이렇게 됐는가를 정직하게 인정한다:

1. 이번 프로젝트의 지금까지의 세션들은 전부 "**이미 존재하는 요구사항**을 어떻게 처리할지"
   (분류 확신도 표시 → 미리보기 → 상태변경 → 재청킹 요청 → 문서 청크맵 시각화 → 배차)에만
   집중했다. 이 사이클들의 입력은 전부 테스트 픽스처(`tests/test_*.py`가 `RequirementStore.
   add_from_classification()`을 직접 호출) 또는 `frontend/data/*` 정적 스냅샷이었다.
2. `backend/adapters/parsers/router.py`(`FORMAT_STRATEGY`)와 `backend/adapters/parsers/
   docx_adapter.py`(`ParserPort` 실구현)가 있어 "파싱 엔진은 이미 있다"는 착시가 있었지만,
   실측하면 **이 두 자산이 서로 연결된 적이 없다** — `router.py`의 `IngestionRouter`는
   `Callable[[str], NormalizedDocument]` 어댑터 dict를 받는데, 실제로 그 dict를 채워 넣는
   코드가 어디에도 없다(`docx_adapter.py`는 `ParserPort` 인터페이스라 시그니처 자체가 다르다).
   즉 "파서가 있다"는 것과 "업로드 시 그 파서가 실제로 호출된다"는 것 사이의 배선이
   통째로 빠져 있었다.
3. `SPCEngine.process_document()`(청킹)·`extract_requirements_from_chunks()`(분류·채번)는
   함수로는 완성돼 있었지만, 이걸 "누가·언제" 호출하는지에 대한 HTTP 진입점이 없었다 —
   지금까지의 모든 사이클이 "그 다음 단계"(미리보기·상태변경·시각화)만 설계·구현했지,
   "제일 처음 문서가 시스템에 들어오는 순간"은 어느 사이클의 명시적 착수 항목도 아니었다.

**결론**: 기능 결손이 아니라 **파이프라인 조립 누락**이다 — 조각(파서·청커·분류기·저장소)은
다 있었고, 이를 하나의 흐름으로 묶어 HTTP로 노출하는 오케스트레이션 계층과 그 트리거(업로드
UI)가 없었다. 이 설계서가 그 배선을 완성한다.

## §2. 업로드 → 청킹 파이프라인 설계

### §2-1. 흐름

```
POST /documents/upload (multipart: file, actor)
  → 확장자 검증(router.py의 FORMAT_STRATEGY를 SSOT로 재사용, CRZ — technology_extractor.py와
    동일하게 import로 읽음, 신규 목록 발명 없음)
  → 지원 확장자 중 "실제 동작하는" 어댑터가 있는 것만 파싱 진행:
        .txt/.md → 신규 TextPassthroughAdapter (ParserPort 구현, 이번 신규)
        .docx    → 기존 DocxParserAdapter (ParserPort 구현, 이미 있음 — 그대로 재사용)
        .hwp/.pdf/.pptx/.png/.jpg/.jpeg/.wav/.mp3/.m4a → 확장자는 인지하되 파서 미구현
                   → 422 AEGIS-VALIDATION "미구현 포맷" (거짓 성공 응답 금지, T98 AIP)
  → doc_id 채번(`doc-{uuid4 hex 12자리}`, 신규 스킴 — 기존 테스트 픽스처의 임의 문자열
    doc_id와 충돌하지 않도록 접두사 고정)
  → DocumentStore.save(doc_id, markdown) — 기존 그대로 재사용(CRZ)
  → SPCEngine().process_document(markdown, context_label=파일명, doc_id=doc_id) — 기존 그대로
  → extract_requirements_from_chunks(chunks, store, doc_format=ext) — 기존 그대로
  → RequirementStore.export_json(frontend/data/requirements.json) — requirements.html·
    documents.html이 이미 이 정적 스냅샷을 fetch하는 기존 관례(§2-3 근거)를 그대로 따름
  → 응답: {doc_id, doc_filename, chunk_count, requirements_created:[...], unclassified_chunk_count}
```

### §2-2. 동기 vs 비동기 판단 (근거와 함께 결정, 과잉설계 회피)

**동기 처리로 결정**. 근거:

- `HeadingBoundarySplitter.split_with_spans()`와 `classify_chunk()`는 둘 다 정규식/문자열
  매칭 기반 결정론적 CPU 연산이며 LLM 호출이 없다(`SemanticBoundarySplitter`는 여전히
  `NotImplementedError` 스텁 — 이번 파이프라인은 기본 스플리터만 사용).
- `DocxParserAdapter`도 표준 라이브러리(`zipfile`+`xml.etree`)만 쓰는 순수 CPU 파싱이라
  네트워크 I/O·외부 API 대기가 없다.
- 00_PROJECT_CONSTITUTION.md·07_API_SERVER_ARCHITECTURE.md가 이미 이 서버를 "로컬 세션
  단위 단일 프로세스"로 규정했다(`--workers` 지정 금지) — 이런 소규모 로컬 도구에서
  업로드마다 별도 큐·워커·폴링 상태머신을 두는 것은 이 프로젝트 규모에 과한 설계다(T57 PVS).
- STT(`speech_to_text` 전략)처럼 실제로 오래 걸리는 미구현 경로는 애초에 이번 범위에서
  422로 명시 거부하므로, 비동기가 필요한 무거운 경로 자체가 지금은 없다.

### §2-3. 업로드 가능 포맷 제한 (§5-A 문서유형과 연결)

| 확장자 | FORMAT_STRATEGY 전략 | 실제 어댑터 상태 | 업로드 결과 |
|---|---|---|---|
| `.txt`, `.md` | text_passthrough | **신규 구현**(TextPassthroughAdapter) | 200 성공 |
| `.docx` | unstructured_parse | 기존 구현(DocxParserAdapter) | 200 성공 |
| `.hwp`, `.pdf` | unstructured_parse | 미구현 | 422(명시 거부) |
| `.pptx` | slide_parse | 미구현 | 422 |
| `.png`, `.jpg`, `.jpeg` | vision_describe | 미구현 | 422 |
| `.wav`, `.mp3`, `.m4a` | speech_to_text | 엔진 연결은 있으나 콜백 미주입(스캐폴딩) | 422 |
| 그 외 | — | `FORMAT_STRATEGY`에 없음 | 415/422 미지원 확장자 |

과장 없이 "지금 실제로 되는 것만" 200을 반환한다(T98 AIP) — 나머지는 향후 각 파서
어댑터가 실구현되면 이 표의 라우팅 테이블(§3 참조)에 한 줄만 추가하면 확장된다.

## §3. 청킹 확정 워크플로우 통합 (§5 재청킹과 연결)

```
[0] 업로드 (신규, 이 설계) ──▶ [1] 청킹 실행 ──▶ [2] 분류·채번 ──▶ lifecycle_status=
    POST /documents/upload    SPCEngine          classify_chunk +   CLASSIFIED 또는
                                                  add_from_          UNDER_REVIEW
                                                  classification
                                                       │
                                                       ▼
                                    [3] requirements.html/documents.html에 노출
                                    (export_json 스냅샷 갱신 — §2-1 마지막 단계)
                                                       │
                                                       ▼
                                    [4] 사람 판단 (기존 §5-1 그대로)
                          ┌────────────┼──────────────────────┐
                          ▼            ▼                      ▼
                    "맞음"          "분류만 틀림"        "청킹 경계 자체가 틀림"
                    ACCEPTED        REJECTED             재청킹 요청(POST .../rechunk,
                    (기존)          (기존)                기존 §5-2 그대로) → WITHDRAWN +
                                                          rechunk_queue.jsonl
```

이 설계가 채우는 것은 오직 **[0]** 단계 — [1]~[4]는 이미 구현·검증된 기존 자산을 그대로
재사용한다(CRZ, 신규 상태값·신규 큐·신규 렌더링 로직 0). 업로드는 "새 문서 등록" 트리거일
뿐이고, 그 다음부터는 기존 순환 루프에 자연스럽게 편입된다.

## §4. 구현 상세 (실제 코드, 2026-07-21)

- `backend/adapters/parsers/text_passthrough_adapter.py`(신규) — `ParserPort` 구현.
  UTF-8 우선 디코딩 시도 → 실패 시 CP949(EUC-KR 상위호환) 폴백. 두 인코딩 모두 실패하면
  `UnicodeDecodeError`를 그대로 전파(추정 디코딩 금지 — 깨진 텍스트를 조용히 만들지 않음).
- `backend/application/services/document_upload_service.py`(신규) — §2-1 오케스트레이션.
  `ParserPort` 어댑터 레지스트리(`_ADAPTERS = [TextPassthroughAdapter(), DocxParserAdapter()]`)
  를 직접 들고 `can_handle()`로 선택 — `router.py`의 `IngestionRouter`(`NormalizedDocument`
  dataclass 계약)는 실제 동작 어댑터가 하나도 배선된 적 없는 별도 계약이라 이번 신규
  배선에는 쓰지 않고, `FORMAT_STRATEGY` dict만 "확장자가 인지된 포맷인가"의 SSOT로
  재사용한다(§1의 근본원인 그대로 — 두 계약을 섞으면 오히려 또 하나의 배선 누락을 만든다).
- `backend/adapters/api/documents_api.py`(기존 파일 확장) — `POST /documents/upload`
  (multipart `UploadFile` + `Form(actor)`), 기존 `requirements_api`의 envelope·에러코드
  재사용(CRZ).
- `frontend/views/documents.html`(기존 파일 확장) — 왼쪽 문서 목록 패널 상단에 업로드
  폼(`<input type="file">` + 버튼 + 진행 상태 텍스트 + 결과 요약 카드) 추가. 셸 구조
  (`ai-shell`/`ai-gnb-slot`/`ai-lnb-slot`)는 그대로 유지, 컨텐츠 영역 내부만 수정.
  업로드 성공 시 방금 만든 doc_id를 그 자리에서 바로 `selectDocument()`로 열어 청크맵을
  보여주고, "요구사항 목록에서 확인 →" 링크(`requirements.html`)를 함께 노출한다.

## §5. 품질검토 게이트 — MPCR 7관점

| 관점 | 검토 결과 |
|---|---|
| 개발 | 신규 어댑터 1개(txt/md, D1)·오케스트레이션 서비스 1개(D2, 기존 함수 호출만 조합)·API 1개(D2) — 난이도 낮음. `.docx` 업로드도 기존 `DocxParserAdapter` 재사용이라 추가 구현 없음 |
| 설계 | §1에서 인정한 "파서-트리거 배선 누락"의 재발을 막기 위해, 이번 서비스가 유일한 조립 지점임을 문서화(다음에 새 포맷 어댑터를 추가하는 사람은 이 파일의 `_ADAPTERS` 리스트에 등록하면 된다는 확장 지점을 명시) |
| 운영 | 동기 처리 + 단일 프로세스 전제(§2-2)라 별도 워커·큐 운영 부담 없음. 실패(미지원 포맷·파싱 오류)는 전부 4xx로 즉시 응답, 서버 크래시 유발 없음 |
| 정보안정성 | 업로드된 원문도 기존 `DocumentStore`(§DRL-2 규칙 — `frontend/` StaticFiles 마운트 밖)에 저장되고, 분류 시점에 기존 `pii_detector.scan_for_pii()`가 그대로 적용되어 §2-4 PII 게이트가 새 문서에도 동일하게 걸린다(신규 예외 없음) |
| 헌법정합 | 00_PROJECT_CONSTITUTION.md §1 핵심 목표("요구사항 문서 → 청킹·구조화")의 **입구**를 완성하는 작업이라 헌법 §4 드리프트 체크리스트 4문항 전부 YES(구조화된 요구사항 경로에 직접 기여·REQ 번호로 추적 가능·AI 태스크 관리 정보 생성·범용 인프라 비대화 없음) |
| 검증 | §6 실측 curl E2E로 실제 파이프라인 실행 확인(가짜 응답 아님) + `pytest tests/` 전체 회귀 0 |
| 책임 | 업로드 시점 actor를 받아두지만(향후 감사로그 확장 지점), 이번 1차 구현은 별도 업로드 이력 로그까지는 만들지 않음(range 축소, 필요 시 후속) — 정직하게 한계로 남김 |

**게이트 결론**: PASS.
