# 요구사항 기반 AI 개발 태스크 관리 시스템 — 설계 목차

> **최우선 참조**: [`00_PROJECT_CONSTITUTION.md`](./00_PROJECT_CONSTITUTION.md) — 이 프로젝트의
> 진짜 목표와 스코프. 아래 Phase는 그 헌법 §3 기준으로 재해석된 것이며, 헌법과 충돌 시 헌법이 우선.
>
> 근거: `D:\projects\products\workbase` 검토 결과 재사용 자산 반영 (CRZ — 재발명 금지).
> 아키텍처: 헥사고날(Hexagonal) — Domain 순수 로직 / Ports 인터페이스 / Adapters 기술구현.
> 모든 Phase는 비판적 검증 루프(다관점 + 외부검증)로 감싼다.
>
> **[경로 안내 — 2026-07-19 리팩토링]** 아래 본문의 `graphify_engine/`·`ingestion/`·
> `orchestrator/`·`core_was_block/`·`agent-view/` 경로는 **그 시점의 실제 경로를 보존한
> 역사적 기록**이다(T39 CRZ — 과거 기록 소급 치환 금지). 지금 실제 코드는
> `plans/_plan/05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md` 설계대로 `backend/domain·
> application·adapters`(백엔드)·`frontend/{views,styles,data}`(프론트)로 재배치됐다 —
> 최신 경로 매핑은 그 설계서와 `README.md`의 디렉터리 구조 참조.

## workbase 검토 요약 (재사용 대상)

| workbase 자산 | 위치 | ai-project-system 재사용 방식 |
|---|---|---|
| Go 단일 바이너리 + SQLite(WAL) | `backend/main.go`, `internal/db/db.go` | `core_was_block/adapters/db` SQLite 어댑터 패턴 참조 |
| CORS/헬스체크 핸들러 | `backend/internal/handlers/{cors,health}.go` | `core_was_block/adapters/api` 표준 envelope(T99 AIOS) 뼈대에 이식 |
| 서버 실행 정책(SEP-1~5) | `_governance/SERVER-EXECUTION_POLICY.md` | `governance/workflows/SERVER-EXECUTION_POLICY.md`로 승격, 포트 충돌 사전점검 절차 그대로 채용 |
| 시맨틱 CSS 토큰 (`variables.css` + 테마별 오버라이드) | `frontend/common/css/variables.css` | `frontend/styles/tokens.css`로 확장(`--accent/--ok/--warn/--danger` 네이밍 계승) |
| 공통 JS 로드 순서 고정(config→workflows→api→state→history) | `frontend/common/js/*` | Agent-View 프런트 모듈 로드 순서 설계에 CONTEXT-CHAIN 원칙으로 계승 |

재사용 판단: workbase는 단일 프로젝트용 CRUD 서버(비-이중화, 비-헥사고날)라 구조 자체를 그대로 가져올 수는 없으나, **CSS 토큰 체계·서버 실행 안전정책·CORS/health 패턴은 검증된 자산**이므로 신규 발명 없이 계승한다.

---

## Phase 0 — 환경 설정 및 제약사항 확립
- 0.1 프로젝트 도메인·언어·스택 확정 (AskUserQuestion) — 영역코드 체계(§5) 확정 완료(2026-07-17)
- 0.2 시스템 헌법(Constitution) 로드 ✅ 완료 — `00_PROJECT_CONSTITUTION.md` 작성 + `CLAUDE.md`
  프로젝트 진입점 등록으로 모든 세션이 착수 전 자동 참조하도록 앵커링
- 0.3 개발 샌드박스(workbase 패턴) 초기화

## Phase 1 — 고가용성 인프라 및 핵심 뼈대 구축 (Scaffolding) ✅ 뼈대 완료
- 1.1 이중화 인프라 토폴로지 설계 (WEB-WAS-DB) — `infrastructure/topology.md` 상세 완료(포트 확정: WEB 8080/8081, WAS 8790/8791, workbase 8787과 충돌 회피), 실배포는 C등급 게이트로 유지
- 1.2 헥사고날 아키텍처 폴더 구조 구현 (Core/Ports/Adapters) — `core_was_block/` 완료
- 1.3 전역 디자인 시스템 토큰 체계 구축 (workbase 토큰 계승) — `frontend/styles/tokens.css` 완료
- 1.4 시스템 상태 관제(Agent-View) 대시보드 뼈대 — `agent-view/index.html`(현 `frontend/views/dispatch-dashboard.html`) 정적 뼈대 완료. **2026-07-23 재확인: fetch 연동도 완료** — `GET /requirements` 실 데이터 연동(`work_status`/`assigned_agent_command` 집계), 실서버(8899) curl 200 + 실데이터 11건 확인, pytest 43 passed(회귀 0)

## Phase 2 — 비정형 데이터 Ingestion 및 정규화 파이프라인 ✅ 핵심 파이프라인 구현·검증 완료
- 2.1 멀티모달 파서 엔진 — `ingestion/router.py` 라우터 완료 + **`ingestion/parsers/docx_adapter.py`
  가 표준라이브러리(zipfile+xml.etree)만으로 실제 동작하는 DOCX→Markdown 변환기**(단락·표 추출,
  합성 .docx로 smoke test 통과: 단락 텍스트 + 2x2 표 → 마크다운 표 정확 변환 확인). 사용자 제안
  코드는 `return "## Extracted Content...\n..."` placeholder였으나 실제 파싱 로직으로 교체함
  (T98 AIP — "동작하는 척" 금지). **2026-07-22 추가**: `backend/adapters/parsers/pptx_adapter.py`
  (python-pptx, 기설치 라이브러리 사용 — 슬라이드·표·speaker notes 추출)·`pdf_adapter.py`
  (`pdfplumber` 신규 설치 — 페이지 텍스트+표 추출) 실동작 구현, `document_upload_service.py`
  `_ADAPTERS`에 등록 완료. 합성 pptx/pdf(python-pptx/reportlab로 생성) smoke test 통과 +
  신규 pytest 13건(`test_pptx_adapter.py`3·`test_pdf_adapter.py`3·`test_document_upload_service.py`7).
  **HWP/이미지는 여전히 미구현**(HWP: OLE 바이너리 포맷이라 stdlib·python-pptx류 라이브러리로
  불가, olefile만으로는 실제 텍스트 추출 로직 별도 필요 — 후속 과제로 남김. 이미지는
  vision_describe 전략 자체가 미착수)
- 2.2 의미보존 청킹(SPC) — `ingestion/chunking.py`에 **`SPCEngine` + `HeadingBoundarySplitter`
  실동작 구현**(마크다운 헤딩 기준 결정론적 경계 분할 + Parent/Child 계층 + 맥락헤더 주입,
  smoke test로 3-섹션 문서 분할·주입 확인). 진짜 "LLM이 주제 전환을 판단"하는 의미분할은
  `SemanticBoundarySplitter`로 분리 유지(미구현 스텁, 과장 금지) — 결정론 대체재로 우선 커버
- 2.3 Vector/Graph DB 스키마 — `infrastructure/database/schema.py` 완료(의존성 미설치 상태 유지)
- **파싱 실패 기록** — `ingestion/error_log.py`: **AEGIS 관리자 error_kb에 직접 쓰지 않고**
  프로젝트 로컬 JSONL에만 기록(T64 KAAG — 상품 프로젝트의 관리자 영역 무승인 직접쓰기 금지).
  AEGIS error_kb 승격은 `hmsav`/`assetize`("자산화 승인") 경로로만 — 사용자 제안의
  "Error KB 노드 자동 생성"을 그대로 구현하면 T64 KAAG 위반이라 경로를 분리했다.
- **재사용 근거**: `/recall` 조회 결과 KH-2026-0674(도메인 인제스트·적응형 청킹 설계) 참조 유지

- **청크→요구사항 자동분류·채번 연결(2026-07-18)** — 지금까지 Phase 2(청킹)와 Phase 3(그래프
  등록)·Phase 4(태스크)가 "req_id는 어딘가에서 이미 주어진다"는 전제로만 동작하던 갭을 메움:
  `graphify_engine/classifier.py`(결정론적 키워드 매칭으로 문서유형코드§5-A·영역코드§5 추정,
  애매하면 `needs_review=True`로 정직 표기 — LLM 의미판단 아님, 과장 금지) +
  `graphify_engine/requirement_store.py`(REQ ID 채번+JSON 영속, PENDING_REVIEW 상태는 사람
  확인 전까지 자동 승격 안 됨) + `ingestion/requirement_extractor.py`(SPCEngine 청크를 위
  분류기·스토어에 연결). smoke test로 실제 다중 도메인 문서 1건에서 REQ-QA-SEC-001 등 3건 채번,
  키워드 매칭 실패 4건은 조용히 버리지 않고 "미분류"로 카운트됨을 확인.
  **알려진 한계**: 순수 사업/인터뷰성 내용처럼 §5 기술영역 키워드가 전혀 없는 청크는 area_code가
  안 잡혀 REQ 채번 자체가 안 됨(§5가 기술영역 한정 목록이라 발생하는 구조적 한계 — 과장 금지로
  정직 기록, 일반영역 코드 추가 여부는 §5가 이미 사용자 확정 사항이라 임의 추가하지 않고 후속
  논의 대상으로 남김).
- **요구사항 관리 화면(2026-07-18)** — `agent-view/requirements.html`: 위 파이프라인 산출물
  (`agent-view/data/requirements.json`)을 표로 렌더링. 관리 포인트(전체/검토대기 요약카드,
  문서유형·영역·상태 필터, 검색, 정렬)와 시각화 인지 포인트(문서유형·영역·상태별 색상 배지,
  신뢰도 막대바 — tokens.css `--ok/--warn/--danger` 재사용)를 반영. **검증 한계**: JSON
  fetch·JS 구문(`node --check`)·정적 서버 200 응답까지 확인했으나, 실제 브라우저 렌더링(픽셀
  단위 확인)은 이 세션 도구로는 수행하지 못함 — 로컬에서 `python -m http.server`로 열어 직접
  확인 필요(README 참고).

## 범용 방법론 — `/recall` 통합 루프
- 문서: `governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md`
- 원칙: 신규 검색엔진 발명 없이 기존 `/recall`(graphify+hmrecall+error_kb+acn) 스킬을 작업 루프(착수·검증·오류수정)에 의무 호출로 문서화

## Phase 3 — 지식 그래프(Graphify) 구축 및 Context 관리 ✅ 스캐폴딩 완료(기능 검증됨)
- 3.1 노드/엣지 추출 로직 — `graphify_engine/domain.py`(Node/Edge 4종) +
  `extractors/ast_extractor.py`(**Deterministic, 실동작 확인**: 자기 자신을 AST 파싱해
  함수 2개·CALLS 엣지 1개 추출 성공) + `extractors/semantic_extractor.py`(LLM 판단 콜백
  인터페이스, 실제 LLM 연동은 미구현 — `NotImplementedError`)
- 3.2 Context Manager — `graphify_engine/context_manager.py`: `TaskStateStore`(JSON 영속)
  + `prune_context()`(Decision Record만 유지). error_log 조회는 신규 검색엔진 없이
  기존 error_kb grep 재사용(RECALL_UNIVERSAL_SEARCH_GUIDE.md 원칙과 동일)
- 3.3 지식 신경망 매핑 파이프라인 — `graphify_engine/pipeline.py`: `merge_into_graph()`가
  `.graphify-out/graph.json`에 노드/엣지 병합 + `parity_check()`(정책 위배 시 병합 거부,
  현재 `governance/constitution/` 비어있어 "정책 없음—통과") + god-node 후보 플래그
  (임계 50, 자동 클러스터링/분할은 **미구현** — 표시만). **실동작 검증**: pipeline.py
  자체를 파싱해 graph.json 병합까지 end-to-end 성공(테스트 산출물은 정리 후 삭제)
- **온톨로지 검증 강화(2026-07-17)** — 중복 엣지 거부(`(source,target,kind)` 조합 동일 시
  `rejected_edges`로 이동, 사유 기록) + 중복 노드 후보 표시(`kind+label` 동일·id 다름 →
  `duplicate_node_candidates`, 자동 병합은 하지 않음 — 오판단 시 데이터 손실 위험 회피).
  smoke test로 실제 중복 엣지 거부·중복 노드 후보 검출 확인.
- **Requirement↔Task 추적성 연결(2026-07-17)** — `graphify_engine/requirements.py`:
  `make_requirement_node()`(REQ 코드를 Requirement 노드로, source_ref 없으면 생성 거부 —
  "추정 요구사항 생성 금지") + `make_implements_edge()`(Task→Requirement IMPLEMENTS 엣지,
  Deterministic) + `verify_task_requirement_links()`(Task의 source_req_ids가 그래프상
  실재 Requirement 노드인지 확인, orchestrator/task_manager.py의 sufficiency 체크보다
  더 강한 근거 검증). smoke test로 실재/가짜 REQ 코드 판별 확인.
- **task_manager 통합(2026-07-17)** — `orchestrator/task_manager.py`의 `check_sufficiency()`/
  `TaskStore.create_or_update()`에 선택적 `graph` 인자 추가: 넘기면 `verify_task_requirement_links()`로
  source_req_ids의 그래프 실재 여부까지 sufficiency 판정에 포함(그래프 없는 REQ 참조 → 부족 사유로
  자동 추가). graph 미전달 시 기존 동작 그대로(하위호환). smoke test로 grounded/missing 양쪽 확인.

**§AISI 드리프트 판정 (2026-07-17, 사용자 확인)**: 원 요청의 "10ms 신경망 소환·
Builder/Verifier/Curator 자동 스킬 승격 루프"는 00_PROJECT_CONSTITUTION.md §4 드리프트
체크리스트에 걸려 **범위에서 제외**(요구사항→태스크 관리가 아닌 범용 AEGIS류 자율성장
엔진 재구축이라 판단, 사용자 확인 완료) — 대신 온톨로지 검증(중복방지)과 Requirement
추적성 연결만 헌법 §3 범위 안에서 구현함.

**Phase 3 리스크 대응(사용자 제공 비판검증 반영)**:
- 그래프 복잡도 폭증(Community Detection) → **구현 완료(2026-07-25, D-0993d22f)**.
  `backend/domain/graph/community_detection.py::detect_communities()` — AEGIS 자체
  `graphify` 스킬이 쓰는 god-node 완화 개념(밀집 클러스터 그룹핑)을 networkx의 검증된
  Louvain 구현(모듈성 최적화, seed 고정으로 재현성 보장)으로 실제 구현. `merge_into_graph()`가
  매 병합 시 전체 그래프에 대해 재계산해 `graph["communities"]`(node_id → community_id)로
  기록. pytest 4건(고립노드 개별클러스터·밀집클러스터 분리·재현성·broken_ref 방어).
- 악의적 지식 주입 방지(Parity Check) → `parity_check()` 뼈대 구현, 실제 헌법 파일이
  아직 없어 텍스트 매칭 수준 최소 구현.
- 지식 수명 관리(Recency 가중치) → **구현 완료(2026-07-25, D-0993d22f)**.
  `backend/domain/graph/recency.py::compute_recency_weight()` — 생성 시각 기준 지수감쇠
  (기본 반감기 30일), 삭제가 아니라 순위 가중치만 낮춤(자산 손실 0). `merge_into_graph()`가
  신규 노드에 `metadata["created_at"]`을 최초 1회만 스탬프(재병합 시 보존)하고, 전체 노드에
  대해 `graph["node_recency_weights"]`를 재계산. pytest 4건(타임스탬프 부재 중립값·신규노드
  가중치1.0·반감기 정확도·미래타임스탬프 클램핑) + merge_into_graph 배선 pytest 2건.

## Phase 4 — 자율 오케스트레이션 및 멀티 에이전트 협업 (이 프로젝트의 본체 — 헌법 §3)
- 4.1 태스크 관리 코어 ✅ 구현·검증 완료 — `orchestrator/task_manager.py`:
  - `Task` 도메인 모델(도메인코드 §5 10종 강제, `source_req_ids`로 REQ 추적성 보유)
  - `check_sufficiency()` — 설명 길이·완료기준·impact_scope·요구사항추적 4항목 미달 시
    `needs_escalation=True` + 부족사유 반환 → **호출 세션이 `/aegis-oneshot-plan`으로
    설계를 구체화해야 함을 스스로 표시**(자동 호출은 세션 레벨 Skill이라 모듈이 직접
    실행하지 않음 — 과장 금지)
  - `TaskStore.create_or_update()` — 불충분한 태스크는 `status="DRAFT"`에 강제 고정,
    충분해지면 승격 가능. 갱신마다 `revision` 증가(변경 이력 추적)
  - `detect_area_conflicts()` — 태스크 간 `impact_scope` 교집합을 N×N으로 확인(§PCM 원칙의
    프로젝트 로컬 적용). **실동작 검증**: SEC 태스크와 DB 태스크가 같은 파일
    (`sqlite_adapter.py`)을 건드리는 교차도메인 충돌을 정확히 검출, 독립 WEB 태스크는
    clear로 분류됨을 smoke test로 확인
- 4.2 에이전트 통신 프로토콜(MCP) + 상태 머신 ✅ 구현 완료(2026-07-21) — `Task.status`가
  지금까지 docstring 주석으로만 표현되던 전이 규칙(DRAFT→READY→IN_PROGRESS→DONE/BLOCKED)을
  실제로 강제하는 코드가 없었던 갭(실측 확인)을 메움: `backend/domain/requirements/
  task_state_machine.py`(전이 그래프 검증, RequirementRecord.set_status() 패턴 CRZ 재사용)
  + `TaskStore.set_status()`(검증 통과분만 status_history 감사로그와 함께 반영) +
  `POST /tasks/{task_id}/status` API(배차된 agent/세션이 진행상황을 보고하는 통신 경로 — MCP
  프로토콜 자체를 새로 만든 게 아니라 기존 HTTP API 패턴으로 "에이전트→시스템 통신"을 구현,
  과장 금지 T98 AIP). 신규 pytest 18건(state machine 7·store 5·api 6) + 기존 138건 전부
  pass(회귀 0, 총 156), uvicorn 실기동으로 DRAFT→DONE 직행 거부·사유없는 BLOCKED 거부·
  정상 전이 반영을 curl로 실측 확인.
- 4.3 병렬 작업 통제 + Distributed Lock ✅ 구현 완료(2026-07-21) — `detect_area_conflicts()`는
  배차 "계획" 단계에서 impact_scope 겹침을 감지만 할 뿐 실행을 막지 않는 갭(실측 확인:
  계획을 무시하고 겹치는 두 Task를 동시에 IN_PROGRESS로 전이시켜도 막을 코드가 없었음)을
  메움: `backend/adapters/persistence/task_lock_store.py`(파일 기반 배타 락 — AEGIS 자체
  `claim_llm_task.py`의 claim registry와 동일 원칙을 프로젝트 로컬 스코프로 재구현, 관리자
  영역 도구를 직접 import하지 않음) + `TaskStore.set_status()`에 배선(IN_PROGRESS 진입 시
  impact_scope 점유 시도 → 충돌 시 거부(부분 반영 없음), IN_PROGRESS 이탈 시 자동 해제).
  부수 보완: `POST /tasks` API 신설(지금까지 Task 생성이 코드 레벨에서만 가능했던 갭 — REQ ID
  채번과 동일 원칙으로 `TASK-{도메인코드}-{일련번호}` 서버 채번). 신규 pytest 11건(lock store
  4·상태전이 락 배선 3·API 생성 4) + 기존 156건 전부 pass(회귀 0, 총 167), uvicorn 실기동으로
  겹치는 impact_scope 두 Task 생성 → 하나 IN_PROGRESS 성공 → 다른 하나 IN_PROGRESS 시도
  422 거부 → 첫 Task DONE 처리 후 락 해제 → 두 번째 Task IN_PROGRESS 성공까지 전 과정을
  curl로 실측 확인.

## Phase 5 — 증거 기반 검증 루프 및 자동화 테스트 ✅ 1차 구현 완료(2026-07-21)
- 5.1 E2E 테스트 자동화 ✅ — `tests/test_e2e_task_lifecycle.py`: Task 생성→READY→IN_PROGRESS
  (락 획득)→완료보고서 조립(`completion_report_service` 재사용)→DONE(락 해제) 전체 생애주기를
  실제 HTTP API(TestClient)로 관통 검증 + 겹치는 impact_scope 두 Task 병렬 통제 시나리오.
  **"Verifier 에이전트"는 자율 에이전트로 구현하지 않음**(과장 금지 T98 AIP) — pytest E2E
  스위트가 그 역할의 결정론적 축소판
- 5.2 비판적 다관점 검증(정적분석) ✅ — `tests/test_task_state_machine_exhaustive.py`:
  TASK_STATUSES×TASK_STATUSES 5x5=25개 조합 전수 순회로 `validate_transition()` 판정이
  `ALLOWED_TRANSITIONS`와 정확히 일치하는지 확인(실수로 열어둔/막은 전이 0건 보장) +
  자기전이 불가·DONE terminal·전 상태 커버리지 불변식. **"Red Teaming"은 실제 공격 시뮬레이션이
  아니라 전이 그래프의 정적 완전성 검증**(과장 금지)
- 5.3 HITL 승인 게이트 + 서킷 브레이커 ✅ — `backend/domain/requirements/task_state_machine.py`
  (`BLOCKED_CIRCUIT_BREAKER_THRESHOLD=3`, `check_circuit_breaker()`) + `TaskStore.set_status()`에
  배선: 같은 Task가 BLOCKED에 3회 도달하면 `needs_escalation=True`로 트립되어
  `override_escalation=True`(사람 검토 확인) 없이는 어떤 전이도 거부. `POST /tasks/{id}/status`에
  `override_escalation` 파라미터 노출. 신규 pytest 38건(unit 6·exhaustive matrix 28·store 통합 1·
  E2E 3), `pytest tests/` 205개 전부 pass(회귀 0). uvicorn 실기동으로 3회 BLOCKED→트립→
  override 없는 전이 422 거부→override 승인→해제까지 전 과정 curl(스크립트) 실측 확인.

## Phase 6 — 자가 진화 및 지식 자산화 (Growth DNA) — 6.2·6.3 범위 제외 확정

> **✅ 드리프트 판정 확정(2026-07-21, 사용자 명시 확인)**: `00_PROJECT_CONSTITUTION.md §1`이
> "자가진화 Growth DNA"를 명시적 반예시로 든다(§4 Q1·Q4 NO — 2026-07-17 Phase 3 배제 판정과
> 동일 패턴). 6.1은 그 위험을 피해 **읽기전용 분석·표면화**로 좁게 스코프해 구현 완료했으나,
> **6.2(해결 패턴 → 스킬/규칙 자동변환 + 업스트림 배포)·6.3(지속적 정본 승격)은 이 프로젝트와
> 맞지 않는다고 사용자가 명시 확인 — 이 프로젝트 범위에서 최종 제외한다.** 향후 세션은 이
> 판정을 재론하지 않는다(T39 CRZ 감사 이력 — 재논의 필요 시 이 판정 자체를 먼저 재검토).

- 6.1 실패 패턴 기반 "자가학습" ✅ 구현 완료(2026-07-21, 좁은 재해석) — 실제로는 자율 자기수정이
  아니라 **읽기전용 집계 리포트**: `backend/application/services/failure_pattern_analysis_
  service.py`(`analyze_requirement_review_patterns()` — UNDER_REVIEW 요구사항을 doc_type_code×
  area_code로 집계, `analyze_task_escalation_patterns()` — needs_escalation Task를 domain_code×
  reason으로 집계) + `GET /analytics/failure-patterns` API(신규). **분류기·태스크 판정 로직을
  자동으로 고쳐 쓰지 않는다** — 사람이 리포트를 보고 `codes.py` 키워드 등을 개선할지 판단하는
  것까지가 이 시스템 책임(과장 금지 T98 AIP). 신규 pytest 8건(서비스 5·API 3), `pytest tests/`
  214개 전부 pass(회귀 0). 개발 중 실측 버그 2건 발견·수정: ①`analytics_api.py`가 `from X import
  get_xxx_store`로 함수 객체를 직접 가져와 테스트의 `monkeypatch.setattr(모듈, ...)`이 반영되지
  않던 문제(모듈 참조로 변경해 해결) ②테스트 헬퍼의 `reasons or [기본값]`이 빈 리스트도 falsy로
  처리해 placeholder 테스트를 무력화하던 문제. uvicorn 실기동으로 불충분 Task 생성 → 5가지 부족
  사유 전부 정확히 집계·표면화 확인.
- 6.2 해결 패턴 → 스킬/규칙 자동 변환 + 업스트림 배포 — **❌ 범위 제외 확정(2026-07-21, 사용자
  명시)**: "이 프로젝트와 맞지 않는 내용"으로 확인. §1 위배(자율 코드/스킬 자기수정)가 근거.
- 6.3 지속적 정본 승격(Canonical Promotion) 프로세스 — **❌ 범위 제외 확정(2026-07-21, 사용자
  명시)**. 이 프로젝트 안에 "정본" 개념 자체가 없어(요구사항/태스크뿐) 원안이 이 도구에 부적합.

## 부수 완료 — 배차 현황 대시보드 구현(2026-07-21, §10 마지막 잔여 항목)

`06_AGENT_DISPATCH_REPORTING.md §10`의 `work_status`·`assigned_agent_command` 필드·API·
`requirements.html` 컬럼 노출은 2026-07-20에 이미 구현됐으나, "전체 집계 대시보드" 화면만
`shell-nav.html`에 "준비중" 배지로 남아있었다. `frontend/views/dispatch-dashboard.html`
신설 — 신규 API·필드 없이 기존 `GET /requirements`(라이브)의 `work_status`/
`assigned_agent_command`만 집계(요약카드 5종 + 배정agent별 분포 테이블). `shell-nav.html`의
"준비중" 배지를 활성 링크로 전환. `node --check` 구문 확인 + uvicorn 실기동으로 200 응답 +
요구사항 1건(work_status=IN_PROGRESS, agent=/aegis-security) 생성 후 `GET /requirements`가
정확한 데이터를 반환함을 확인(대시보드가 소비할 데이터 경로 실측 검증, 브라우저 렌더링
자체는 이 세션 도구로 미확인 — 기존 화면들과 동일한 한계). `pytest tests/` 214개 전부
pass(회귀 0, 백엔드 변경 없음).

**Phase 6 최종 상태**: 6.1(읽기전용 실패패턴 분석)만 구현 — 이것으로 Phase 6 종료. 이 프로젝트의
Phase 0~6 로드맵은 이제 전부 확정 상태(구현완료 또는 명시적 범위제외)다.

---

## 비판적 검토 (선순환 구조 확인)

인프라 → 데이터 → 지능 → 자율검증 → 진화로 이어지는 구조. Phase 1에서 디자인 토큰과 인프라를 분리해
프론트 테마(다크/라이트)가 독립적으로 확장 가능함을 workbase 실사례(app-A/app-B 이중 테마)로 이미 검증.

**리스크**: Phase 1.1 이중화(WEB-WAS-DB)는 실제 서비스 배포(C등급)에 해당하므로, 본 스캐폴딩
단계에서는 **폴더 구조·인터페이스 뼈대만** 만들고 실제 다중 서버 배포·방화벽 설정은 평식 게이트 대상.
