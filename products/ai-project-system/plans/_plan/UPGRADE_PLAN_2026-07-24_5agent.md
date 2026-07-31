# UPGRADE_PLAN_2026-07-24 — 5-agent 협업 고도화 진단

> `/aegis-upgrade-plan`(5-agent 협업 버전) 실행 결과. `aegis-qa000`(기능/추적성)·
> `aegis-architect000`(아키텍처/구조안정성)·`aegis-infra000`(성능/운영안정성)·
> `aegis-security000`(보안)·`aegis-dev000`(실현가능성 검토) 5개 역할이 각자 독립적으로
> 실측하고, dev000이 다른 4개 결과를 교차검증했다. **하나의 agent가 전부 훑지 않고
> 분야별로 깊게 파야 근본 문제를 놓치지 않는다**는 이번 재설계 원칙이 실제로
> 효과를 냈다 — dev000이 교차검증 과정에서 QA/아키텍처 후보 중 2건의 원래 서술이
> 실측과 어긋남을 발견해 우선순위를 바로잡았다(아래 §5 참조).

## 요약 (5문장)

기능 측면에서는 Phase 3(Graphify)의 존재 이유인 "요구사항↔코드 추적 검증"이 실제 API 경로에서
전혀 실행되지 않고(dead wiring), §5 영역코드 10종 중 9종이 실사용 데이터 0건이라 이 시스템의
핵심 목적을 증명할 라이브 데이터가 사실상 없다. 아키텍처는 domain 계층 경계는 건강하지만
application 계층이 Port 대신 concrete adapter를 직접 참조해 "포트만 보면 교체 가능"이라는
전제가 무너져 있고, 최근 만든 PostgreSQL 어댑터(578줄)는 어디서도 참조되지 않는 미검증 대기
코드다. 운영 측면은 `--workers` 금지가 실제 `threading.Lock` 코드 제약임이 확인됐고 백업·CI/CD·
프로세스 매니저가 전무해 SPOF다. **가장 심각한 것은 보안**이다 — API 전체에 인증이 없고,
`project_id`에 경로 순회(Path Traversal, CWE-22) 취약점이 실제로 존재해 임의 파일 읽기/쓰기로
이어질 수 있다. dev000의 실현가능성 재검토 결과, 경로 순회 2건은 즉시(반나절~1일) 수정 가능한
반면, 추적성 dead-wiring 수정은 겉보기와 달리 그래프 생성 파이프라인 부재로 인해 단순 배선이
아니라 별도 설계가 선행돼야 함이 드러났다.

---

## [기능 갭] — aegis-qa000 (요구사항↔산출물 추적성)

| Phase/항목 | 설계상태(문서) | 구현상태(실측) | 증거 |
|---|---|---|---|
| Phase 3 — IMPLEMENTS 추적 검증 | "sufficiency 판정에 그래프 실재 검증 포함" | **dead wiring** — `tasks_api.py:90`가 `create_or_update(task)`만 호출, `graph` 인자 미배선. `verify_task_requirement_links()`는 unit test에서만 실행됨 | `backend/adapters/api/tasks_api.py:90` |
| Phase 3 — 그래프 산출물 | "graph.json 병합 성공" | `.graphify-out/` 완전히 비어있음(파일 자체 없음) | `.graphify-out/`(빈 디렉터리) |
| §5 영역코드 실사용 | 10종 코드체계 확정 | 실데이터(REQ 11건) 중 `SEC` 1종만 등장, 9종 실사용 0건 | `data/requirements_store.json`(11건) |
| §5-A 문서유형 실사용 | 6종 확정 | `ENV`·`QA` 2종만 등장, 4종 실사용 0건 | 상동 |
| 다중 프로젝트(2026-07-22 "완료" 로그) | 완료 | `data/projects_registry.json` = `[]`, `data/projects/` 빈 디렉터리 — 코드는 있으나 실사용 0 | `data/projects_registry.json` |
| Postgres 어댑터 4종 + `search_all_adapter.py` | 문서화 없음 | 미문서화 죽은 코드(참조 0건) | `backend/adapters/db/postgres/*`, `aegis_bridge/search_all_adapter.py` |
| HWP 파서 | "5/6 포맷 실동작" | 긍정 경로(유효 .hwp) 미검증(문서 자인), 이미지 포맷은 어댑터 자체 부재 | `hwp_adapter.py` docstring |

## [아키텍처/구조적 안정성] — aegis-architect000

| 항목 | 심각도 | 증거 | 권고 |
|---|---|---|---|
| domain 계층 경계 | 없음(양호) | adapters/fastapi/sqlite3/psycopg2 import 0건 전수 확인 | 유지 |
| **application→adapter 직접결합** | 중간 | `document_upload_service.py:22-30` 등 다수, `task_dispatch_service.py:44`가 `TaskStorePort` 아닌 `TaskStore` concrete 타입힌트 | 시그니처만 Port로 교체(TaskStore쪽은 D2, DocumentStore는 Port 자체가 없어 신설 필요 — dev000 재확인) |
| **postgres/·persistence/ 이중구조** | 높음(알려진 리스크) | postgres 어댑터 578줄, 참조 0건, README 자체가 "검증 미확정" 명시 | JSON 어댑터 필드 변경 시 postgres_* 동시 갱신 체크리스트화 |
| DocumentStore Port 누락 | 낮음 | `DocumentStorePort` grep 0건(3개 Port만 존재) | 시급성 낮음, 향후 DB 전환 대상이면 신설 |
| God file / 순환의존 | 없음 | 최대 367줄, 순환 0건 | — |
| 과거 구조문제 이력 | 이미 해결 | `05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md`(L4 DONE), SqliteProjectAdapter 데드코드도 2026-07-24 해소 확인 | 잔존 리스크 없음(단 postgres/ 이중구조가 동일 패턴 새 버전) |

## [성능/운영안정성] — aegis-infra000

| 항목 | 현재상태(실측) | 병목조건 | 대안 |
|---|---|---|---|
| 프로세스 모델 | `requirements_api.py:37` `threading.Lock`가 `--workers` 금지의 실제 근거(멀티프로세스 경합 방지 불가) | 단일 코어만 사용, 확장 불가 | 락을 파일락/DB락으로 교체 또는 `topology.md` WAS 이중화 경로(`.env` 전환) |
| DB 커넥션 관리 | `postgres/connection.py`가 매 호출 신규 커넥션, 풀링·헬스체크 없음 | 부하 증가 시 커넥션 오버헤드·`max_connections` 소진 | Connection pool + 헬스체크 도입 (단, 현재 미배선이라 우선순위 낮음) |
| JSON 스토어 | 현재 최대 18KB로 소규모, read-modify-write 전체 재직렬화 패턴 | 요구사항 건수 증가 시 지연시간 선형 증가 | Postgres 전환(코드는 있으나 미검증), 전환 전 T38 PAP 기준선 측정 필수 |
| SPOF | 백업 스크립트 0건, CI/CD 파일 0건, 프로세스 매니저 설정 0건 | 크래시 시 자동복구 없음, 배포 전 회귀게이트 없음 | pm2/systemd 자동재기동 + T84 IBP 백업 정책 도입 |

## [보안] — aegis-security000 ⚠ 최우선 확인 필요

| 항목 | 현재상태(실측) | 리스크 | 권고 |
|---|---|---|---|
| **인증/인가** | `backend/adapters/api/*.py` 전체에서 `Depends`/인증 미들웨어 grep 0건 | 높음 — 전 엔드포인트 무제한 접근, `actor`는 자기신고 문자열 | API Key/세션 인증 도입 |
| **`project_id` 경로 순회** | `project_scope.py:17-20` — 검증 없이 경로 조합. Windows pathlib 절대경로 대체 특성상 임의 경로 read/write 가능 | **치명적(CWE-22)** — 인증 부재와 결합 시 임의 파일 쓰기로 확장 가능 | `ProjectRegistry.get(project_id)` 화이트리스트 검증(이미 존재하는 registry 재사용) |
| **`doc_id` 경로 순회** | `document_store.py:33-38` 동일 패턴 | 중간(CWE-22) | 안전 문자셋 정규식(`^[A-Za-z0-9_-]+$`) 검증 |
| CORS | `server.py:40-46` — 명시적 2개 오리진, 와일드카드 아님 | 낮음(양호) | 운영 배포 시 도메인 재설정만 확인 |
| 전역 예외 핸들러 | `server.py:49-63` — T99 AIOS envelope로 스택트레이스 비노출 | 낮음(양호) | 유지 |
| PII 스캔 | dev000 재검증 결과 **기존 서술은 과장** — description 기반 게이트가 이미 존재하며 `/preview`와 동일한 기존 패턴(설계상 일관성 있음). 진짜 갭은 `confirm_pii`가 서버측 인가 없는 클라이언트 bool이라는 점 | 낮음(재평가) | 단독 수정 대신 앱 전체 PII 게이트 일관성 재검토로 스코프 확대 필요(이번엔 착수 보류) |
| 비밀정보 하드코딩 / `DATABASE_URL` | 하드코딩 0건, fail-fast 확인 | 낮음(양호) | 유지 |

## §5 — dev000 실현가능성 교차검증 결과 (agent 간 교차 언급으로 우선순위 재조정)

| # | 후보 | 실현가능성 | 소요 | 리스크 | 비고 |
|---|---|---|---|---|---|
| 1 | project_id 경로순회 수정 | 가능 | 작음(반나절) | 낮음 | 기존 `ProjectRegistry.get()` 재사용만으로 해결 |
| 2 | doc_id 경로순회 수정 | 가능 | 작음(1일 이내) | 낮음 | 정규식 검증 1개 함수 추가 |
| 3 | PII 스캔 관련 | **후보 자체가 과장** | — | — | 재평가 결과 기존 게이트 존재 확인, 단독 수정 비권장 |
| 4 | API 인증 도입 | 가능 | 중간(수일) | 중간 | 미들웨어보다 프론트 fetch 전수 배선이 더 큼 |
| 5 | Port 타입 시그니처 교체 | 조건부 | 파일별 상이 | 낮음~중간 | TaskStore쪽은 작음, DocumentStore는 Port 신설 선행 필요 |
| 6 | graph 인자 배선 | **겉보기와 달리 위험 큼** | 중간(수일) | **높음** | graph.json을 채우는 파이프라인 자체가 없어, 단순 배선 시 전체 Task가 강제 DRAFT로 회귀(설계 선행 필요) |
| 7 | Postgres 커넥션 풀링 | 가능하나 저우선 | 중간 | 낮음 | 현재 미배선 죽은 코드라 배선 결정 시점에 함께 |

## 최종 우선순위

| 우선순위 | 항목 | 근거 |
|---|---|---|
| **P0** | `project_id`/`doc_id` 경로순회 수정(#1+#2) | 실현가능성 확인·소요 작음·리스크 낮음, 보안 임팩트 큼 |
| **P0** | API 인증 도입 검토(#4) | 로컬 전용이라도 노출 전 필수, 범위만 정확히(프론트 포함) 산정 |
| **P1(설계 필요로 재분류)** | graph.json 채우는 파이프라인 설계(#6) | dev000 재검토로 "단순 배선"에서 "선행 설계 필요"로 격상 — 근거 없이 P0/P1로 올리면 회귀 유발 |
| **P1** | application→Port 시그니처 정리(#5, TaskStore쪽만 우선) | 작고 안전한 부분부터 |
| **P2** | postgres/persistence 이중구조 drift 관리 체크리스트 | 지금 당장 문제는 아님 |
| **P2** | 백업/CI/CD/프로세스매니저 도입 | Phase 1 설계 단계 특성상 당장 급하지 않으나 운영 전환 전 필수 |
| **P3** | §5 영역코드 실사용 확대(라이브 데이터 축적) | 코드 문제가 아니라 실사용 데이터 축적의 문제 |
| **보류** | PII 게이트 재설계(#3) | 앱 전체 스코프 확대 필요, 이번엔 착수 안 함 |

### 진행 기록 — 2026-07-30 (`/autolp` 세션, 실측 기반 상태 갱신 — T101 SOSC reconcile-first)

> **[중요]** 아래 항목들은 **이 문서 작성 이후 다른 세션이 이미 해결**했음을 git log·코드·테스트
> 실측으로 확인했다(같은 종류의 문서 드리프트가 이 세션에서만 2회째 재발 — 앞으로 이 표 갱신을
> 습관화한다).

| 항목 | 상태 | 근거 |
|---|---|---|
| graph.json 파이프라인 설계+배선(#6) | **완료** | `tasks_api.py:111` `create_or_update(task, graph=_load_graph(project_id))` + `merge_into_graph()`로 TASK 노드·IMPLEMENTS 엣지 실제 병합(commit `4adc9ea`, `40379a6`). `tests/test_tasks_api.py::test_create_task_merges_task_node_and_implements_edge_into_graph` 통과로 검증됨(전체 회귀 포함). |
| application→Port 시그니처 정리(#5, TaskStore) | **완료** | `task_dispatch_service.py:44` 이미 `task_store: TaskStorePort` 타입힌트(concrete `TaskStore` 아님). |
| 백업/pm2 프로세스 매니저 | **완료** | `ecosystem.config.js`(boot_preflight 회로차단기 포함) + `backup/`(`BACKUP_HISTORY.jsonl`+`VERSIONS/`, T84 IBP) 이미 존재(commit `4e6a541`). |
| CI/CD | **이번 세션 신설** | `.github/workflows/tests.yml` + `requirements.txt`(이전엔 의존성 매니페스트 자체가 없어 CI 구성이 구조적으로 불가능했음) 신규 추가. |
| postgres/persistence 이중구조 drift 체크리스트 | **보류 유지** | 사용자 명시 DEFER(`D-c92bd806`, AEGIS 시스템 이전·배포전략 수립 후) — 이번 세션 착수 안 함. |
| §5 영역코드 실사용 확대 | **보류 유지** | 코드 문제가 아닌 실사용 데이터 축적 문제, 그대로 유효. |

---

## 진행 기록 — 2026-07-24 (사용자 지시: "다음작업진행 안정적, 평식승인 3번은 더 심층적 영향도 검토")

### 완료 — P0 #1+#2 경로순회 수정 (실행)

3개소 수정 + 신규 회귀테스트(§W-5 원문 확인):
- `backend/adapters/persistence/project_scope.py` — `resolve_project_data_dir()`에
  `_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")` 검증 추가, 위반 시 `InvalidProjectIdError`.
  이 함수가 유일한 SSOT(모든 API가 여기로만 경로를 얻음)라 한 곳 수정으로 전 엔드포인트 방어.
- `backend/adapters/persistence/document_store.py` — `save()`/`load()` 진입부에
  `_validate_doc_id()` 추가, 위반 시 `InvalidDocIdError`. `export_for_preview()`는
  내부에서 `load()`를 거치므로 자동 방어.
- `backend/server.py` — `InvalidProjectIdError`/`InvalidDocIdError` 전용 exception
  handler 추가 → 500(내부오류 노출) 대신 400 + `{"code": "AEGIS-VALIDATION"}`(T99 AIOS
  경계검증 envelope)로 응답.
- `tests/test_path_traversal_protection.py`(신규 13건) + 기존 전체 스위트 재실행 —
  `python -m pytest -q` **수정 전 288 passed** → 신규 13건 추가 후 전체 재실행
  **"301 passed, 2 warnings in 75.12s"**(§W-5 원문 확인, 회귀 0건).

### 진행 — P0 #4 API 인증 도입 (설계만, 미구현 — 스코프 산정)

실측 결과 인증이 전혀 없는 엔드포인트는 `requirements_api`·`tasks_api`·`documents_api`·
`projects_api`·`doc_types_api`·`analytics_api` 6개 라우터 전체(2026-07-24 5-agent 진단
재확인). 이번엔 코드 변경 없이 스코프만 산정한다(비가역·설계결정 성격이 커 이번 턴에
바로 구현하지 않음 — 사용자가 "안정적으로"라 명시했으므로 검증 안 된 인증 방식을 그 자리에서
바로 밀어넣지 않는 것이 안전 우선 판단):

- 백엔드: FastAPI `Depends()` 기반 API Key 미들웨어 1곳(`server.py`) 추가가 최소 변경.
- **프론트엔드가 더 큰 스코프**: `frontend/*.html`이 fetch 호출 시 헤더를 전혀 안 붙임 —
  `requirements.html`·`documents.html`·`tasks.html` 등 전 화면의 fetch 호출부에 인증
  헤더 주입이 필요해, "백엔드 미들웨어 1줄"보다 훨씬 큰 작업(프론트 파일 수 × fetch 호출 수).
- **로컬 전용 배포 특성 고려**: 현재 CORS가 `127.0.0.1:8899`/`localhost:8899`로 고정된
  로컬 전용 구성이라, "지금 당장" 위험도는 프로덕션 노출 대비 낮음 — 그러나 이 프로젝트가
  다른 사용자·네트워크로 노출될 계획이 있는지가 우선순위를 바꾸는 결정 변수(설계 결정,
  평식 확인 필요).
- **다음 단계 제안**: 별도 턴에서 ①API Key 방식(단순, 로컬 다중사용자 정도만 방어) vs
  ②세션 기반 로그인(더 무겁지만 감사로그·사용자별 actor 신뢰성 개선) 중 배포 계획에 맞는
  방식을 먼저 확정한 뒤 구현 — 이번엔 구현 착수 안 함(§0-5 명확성 원칙: 설계결정 없이
  코드부터 밀어넣지 않음).

### 완료 — P1 #6 graph.json 파이프라인 심층 영향도 검토 (사용자 지시대로 실행 대신 분석)

**핵심 발견 — dev000의 "회귀 위험" 경고를 코드 레벨로 재확인**:

`backend/domain/requirements/conflict_detection.py:24` `check_sufficiency(task, graph=None)`는
`graph` 인자가 **`None`이면 그래프 검증 자체를 건너뛴다**(50번째 줄 `elif graph is not None:`).
반면 `backend/adapters/persistence/task_store.py:62`
`create_or_update(task, graph: dict | None = None)`에 **실제 dict**(설령 빈 그래프라도)를
넘기면, `id_format.py:57` `verify_task_requirement_links()`가
`req_node_ids = {n["node_id"] for n in graph.get("nodes", []) if n.get("kind") == "REQUIREMENT"}`를
계산한다 — `.graphify-out/graph.json`이 존재하지 않거나(현재 상태, QA agent 확인) 존재해도
Requirement 종류 노드가 하나도 없으면 `req_node_ids`는 **항상 빈 집합**이 되고, 모든
`source_req_ids`가 "그래프에 없는 요구사항 참조"로 `missing` 처리되어
`check_sufficiency()`가 **False**를 반환한다. 그 결과
`task_store.py:65-66`이 `task.status`를 **강제로 "DRAFT"**로 고정한다 — 즉 지금
`tasks_api.py:90`가 `graph` 인자를 아예 안 넘기는(`None` 암묵 기본값) 현재 상태는 "미완성"이
아니라 **"그래프가 텅 비어 있는 현재 시점에는 유일하게 안전한 선택"**이었다는 것이 실측으로
확인됐다 — dev000의 경고가 코드 레벨에서 정확히 재현된다.

**올바른 구현 순서 (선행 설계 3단계, 이번엔 착수 안 함)**:
1. **선행 필수**: Requirement 레코드(`requirements_store.json`)가 생성/갱신될 때마다
   `backend/application/services/graph_pipeline_service.py`의 `merge_into_graph()`를 호출해
   `Node(kind=REQUIREMENT, node_id=req_id, ...)`를 `.graphify-out/graph.json`에 동기화하는
   연결부가 **먼저** 있어야 한다(현재 이 호출부 자체가 어디에도 없음 — QA agent가 확인한
   "빈 `.graphify-out/`"의 직접 원인). 후보 삽입 지점: `requirements_api.py`의
   `create_requirement_manual()`과 문서 업로드 파이프라인(`document_upload_service.py`)의
   요구사항 채번 직후.
2. **동시성 리스크(신규 발견, infra agent 소견과 연결)**: `graph.json`은 현재 어떤 락으로도
   보호되지 않는다(`requirements_api._write_lock`은 `requirements_store.json`만 보호) — 1번
   연결부를 추가하면 `graph.json`도 동일한 read-modify-write 경합 대상이 되므로, 기존
   `_write_lock` 재사용 또는 별도 락 필요(신규 동시성 버그 표면 — dev000이 지적한 "겉보기와
   달리 위험 큼"이 여기서 한 번 더 확인됨).
3. **그 다음에만** `tasks_api.py:90`에 `graph=json.loads(graph_path.read_text()) if
   graph_path.exists() else None`을 배선한다 — **`graph_path.exists()`가 False일 때 빈
   dict가 아니라 반드시 `None`을 넘겨야** 함(1번이 아직 없는 프로젝트에서도 회귀가 나지 않게
   하는 안전장치).

**결론**: #6은 "설계 필요"가 아니라 정확히는 **"선행 배선(1번) 없이 3번만 단독으로 하면
100% 회귀"**임이 코드로 확정됐다 — P1 유지하되, 착수 시 반드시 1→2→3 순서를 지킬 것(순서
뒤바뀜 방지가 이번 심층 검토의 핵심 산출물).

## 진행 기록 — 2026-07-24 (사용자 지시: "다음작업 api 인증 방식 다른 작업 안정화후 진행 배포전 작업 예약 으로 3번 은 바로 진행")

### 예약(보류) — P0 #4 API 인증 도입 → 배포 전 작업으로 directive 등재

`D-b83768b2`(`llm_directive.py add`, target=claude)로 등재 — 다른 작업(특히 위 #6
graph.json 파이프라인) 안정화 후, **배포 직전**에 착수하는 것으로 예약. RCA: 방식(API Key
vs 세션)이 배포 계획(로컬전용 유지 vs 외부 노출)에 의존하는 설계결정이라 지금 확정하면
근거 없이 고르는 것이 됨 — 부실 보류 방지 원칙(§0-5)에 따라 "왜 지금 안 하는지"를 위 조건과
함께 명시. 재검토 조건: 배포계획 확정 시 또는 사용자가 직접 방식을 지정할 때.

### 완료 — P1 #5 application→Port 시그니처 정리 (TaskStore쪽, 즉시 실행)

`backend/application/services/task_dispatch_service.py` — `dispatch_tasks()` 파라미터
타입힌트를 concrete `TaskStore`(adapters 계층 직접 import)에서 `TaskStorePort`(application
계층 추상 포트)로 교체(§W-5: Edit 성공 확인). `list_all()`만 사용하고 이는 이미
`TaskStorePort`에 정의돼 있어 순수 타입힌트 교체(런타임 동작 변화 없음, 회귀 위험 최소).
`python -m pytest tests/test_task_dispatch_service.py tests/test_dispatch_execution_planner.py
tests/test_completion_report_service.py -q` → **"23 passed"** + 전체 스위트 재실행
**"301 passed, 2 warnings in 60.07s"**(§W-5 원문 확인, 회귀 0건).

---

*생성: 2026-07-24 · 실행: `/aegis-upgrade-plan`(5-agent 협업 버전, aegis-qa000·aegis-architect000·
aegis-infra000·aegis-security000·aegis-dev000) · 전부 general-purpose agent에 각 SPECIALIST.md
역할을 지정해 병렬 실행(KH-2026-0790 제약으로 원 subagent_type 직접 호출 불가, 대체 경로 사용)*

## 진행 기록 — 2026-07-25 (다른 세션이 이어가다 종료된 P1 #6 배선 — 회귀 발견·수정, `/ao` 세션이 이어서 검증)

### 발견 — 직전 세션(오늘자 "[2026-07-25 고도화]" docstring)이 P1 #6 3단계 배선을 실제로 완료했으나, 전체 테스트로 검증하지 못한 채 세션 종료됨

`requirements_api.py`(`_graph_path`·`sync_requirement_to_graph`, `_write_lock` 내부 호출)와
`tasks_api.py`(`_load_graph`, `create_task`의 `graph=_load_graph(project_id)` 배선)에
docstring `[2026-07-25 고도화]`로 기록된 변경이 이미 존재 — §5 표 #6("올바른 구현 순서
1→2→3")이 실제로 코드화됨. 그러나 이 배선 이후 전체 스위트를 재실행한 흔적이 없었음(직전
기록은 여전히 "301 passed" 기준 P1 #5까지만 언급).

### 재현 — 전체 스위트 실행 결과 `tests/test_e2e_task_lifecycle.py` 3건 회귀(298 passed, 3 failed)

원인(코드 추적으로 확정): 이 e2e 테스트 파일의 `client` fixture가 `tasks_api.get_task_store`만
monkeypatch하고 `project_scope.resolve_project_data_dir`는 격리하지 않음(같은 저장소의
`test_manual_requirement_creation.py`는 이미 이 패턴을 씀) — 그 결과 `tasks_api._load_graph()`가
실제 `data/.graphify-out/graph.json`(다른 테스트·실사용이 채운, 이 e2e 테스트의
`REQ-TECH-WEB-001`을 포함하지 않는 그래프)을 읽어 `check_sufficiency()`가 "그래프에 없는
요구사항"으로 오판정 → 태스크가 DRAFT에 강제 고정 → `READY→IN_PROGRESS` 전이가 422로 거부됨.
5-agent 진단에서 dev000이 경고한 "겉보기와 달리 위험 큼"이 테스트 격리 누락이라는 형태로
실제 발현한 사례.

### 수정 — 테스트 파일만 변경(B등급, 프로덕션 코드 무변경)

`tests/test_e2e_task_lifecycle.py`의 `client` fixture에 `test_manual_requirement_creation.py`와
동일한 격리 패턴(`monkeypatch.setattr(project_scope, "resolve_project_data_dir", lambda
project_id: tmp_path / project_id)`) 추가. 검증(§W-5 원문 확인): 파일 단독 재실행
`3 passed`(수정 전 `1 failed, ... assert 422==200`) → 전체 스위트 재실행 **"301 passed, 2
warnings in 95.05s"**(회귀 0, 신규 실패 0).

### 미착수 — `data/.graphify-out/graph.json` 로컬 오염(untracked, gitignore 대상 아님)

`data/`는 git 미추적 로컬 런타임 상태로 이번 세션이 만든 것이 아니며(사전 존재 가능성),
전체 테스트가 이미 통과하므로 이번 스코프에서는 정리하지 않음 — 다른 테스트가 격리 없이
실제 `data/`를 오염시키는지는 별도 확인 필요(발견만 기록, §PAW-DOP: 이번 세션 목표 외
정리 착수 안 함).

*이어감: `/ao`(claude, 2026-07-25) — "다른 세션에서 진행하던 코드 중 멈춘 것" 검토 지시로
발견·재현·수정·전체회귀검증까지 완결. git 커밋은 명시 지시 없이 수행하지 않음(전역 규칙).*

## 진행 기록 — 2026-07-25 (이어서, "다음 작업 진행" — 오염 근본원인 전수 확산 수정)

### 발견 — `_graph_path` 격리 누락이 e2e 테스트 1개소만이 아니라 5개 테스트 파일에 공통

`TestClient(app)` 사용 + `requirements_api.get_requirement_store`류 팩토리는 격리하면서
`_graph_path`(신규, 2026-07-25 배선)는 누락한 파일 5건 확인:
`test_requirements_api.py`·`test_tasks_api.py`·`test_documents_upload_api.py`·
`test_analytics_api.py`·`test_documents_api.py`. 실측: `data/.graphify-out/graph.json`에
`REQ-ENV-SEC-001` 노드가 실제로 남아있었음(어느 격리 안 된 테스트가 실행 중 실데이터를
오염시킨 직접 증거).

### 수정 — 5개 파일 모두 동일 패턴(기존 팩토리 monkeypatch 옆에 한 줄 추가, CRZ)

`test_requirements_api.py`/`test_documents_upload_api.py`/`test_analytics_api.py`/
`test_documents_api.py`는 `requirements_api._graph_path`를, `test_tasks_api.py`는
(이미 `test_e2e_task_lifecycle.py`에 적용한 것과 동일하게) `project_scope.
resolve_project_data_dir`를 tmp_path로 monkeypatch. 프로덕션 코드 무변경(B등급).

### 검증(§W-5 원문 확인) — 오염 파일 삭제 후 재실행으로 재발 0 실증

`data/.graphify-out/graph.json` 삭제 → 전체 스위트 재실행 **"301 passed, 2 warnings in
66.38s"** → 재실행 후 `data/.graphify-out/` 재확인 결과 **파일 재생성 없음(빈 디렉터리
유지)** — 어떤 테스트도 더 이상 실데이터를 쓰지 않음을 직접 확증(표본 추정 아닌 전수 재현
후 결과 확인).

*이어감: `/ao`(claude, 2026-07-25, "다음 작업 진행") — 직전 턴이 남긴 [다음 작업] 3번 항목을
0-G 기본동작으로 선택해 완결. 1번(커밋)·2번(타 프로젝트 조사)은 착수하지 않음(사용자 재지시
대기, §0-G-5).*
