# UPGRADE_PLAN_2026-07-23 — ai-project-system 시스템 고도화 목록

> `/aegis-upgrade-plan` 실측 실행 결과(2026-07-23). 모든 항목은 아래 실제 grep/read/wc 결과를
> 근거로 하며, 추정 항목은 없다. 요약: 아키텍처(헥사고날 경계·테스트 커버리지)는 건강하지만,
> **①영속화 계층이 설계 문서상 "Port/Adapter"로 그려진 것과 실제 코드가 불일치**하고,
> **②API에 인증·CORS·전역 예외 처리가 전무**하다는 두 가지가 P0급 발견 사항이다.

## 요약 (3~5문장)

`backend/domain/`은 `adapters`·`fastapi`·`sqlite3`를 import하지 않아 헥사고날 경계는 실제로
지켜지고 있고, God file도 없으며(최대 367줄), TODO/FIXME도 0건, 테스트 41개/모듈 82개로 커버리지
신호도 양호하다. 그러나 `backend/adapters/db/sqlite_adapter.py`(`SqliteProjectAdapter`)는
`save_project`/`get_project_status` 둘 다 `raise NotImplementedError`인 **미구현 스텁**이고,
실제 서비스 코드 어디에서도 import되지 않는다 — 실제 영속화는 전부
`backend/adapters/persistence/*.py`를 통한 **평문 JSON 파일**(`data/requirements_store.json`
등)이다. 즉 README/설계원칙 문서가 말하는 "SQLite → PostgreSQL 교체 시 어댑터만 교체" 서술은
`Project` 엔티티 한정 스텁에만 해당하고, 실제 요구사항/태스크 데이터의 저장 방식과는 무관하다 —
이 문서는 이 오류를 정정한다. API 계층은 인증·CORS·전역 예외 핸들러가 전무해 프로덕션 노출 시
가장 먼저 손봐야 할 지점이다.

---

## [기능 갭] — Phase 커버리지

| Phase | 설계상태(00_DESIGN_TOC.md) | 구현상태(실측) | 비고 |
|-------|---------------------------|---------------|------|
| Phase 0~2 | 완료 선언 | 코드 존재 확인(`backend/domain/chunking`, `extractors/`) | — |
| Phase 3 (graphify) | "스캐폴딩 완료" | `.graphify-out/` 디렉터리 존재 확인 | 기능 검증됨(문서 기준) |
| Phase 4 (본체·자율 오케스트레이션) | 4.1~4.3 "구현·검증 완료" | `task_manager.py`·`task_state_machine.py`·`task_lock_store.py` 존재, pytest 167건 언급 | 설계문서 자체가 상세 실측 로그(curl 확인 등) 포함 — 가장 신뢰도 높은 Phase |
| Phase 5 (검증 루프) | "1차 구현 완료" | — | 이번 스캔에서 미확인(범위 밖) |
| Phase 6 (자가진화) | "6.2·6.3 범위 제외 확정" | — | 의도적 범위축소 — 갭 아님 |

**[P1] 실제 파일 존재 확인은 했으나 Phase 4의 "curl 실측 확인" 로그는 설계문서 서술에만 의존** —
이번 세션에서 직접 재현하지 않음(§W-5: deferred). 재현 검증을 별도 태스크로 권장.

## [아키텍처 품질]

| 항목 | 심각도 | 증거 | 권고 |
|------|--------|------|------|
| 헥사고날 경계 위반 | 없음 | `grep "^import\|^from" backend/domain/` → adapters/fastapi/sqlite3 매치 0건 | 유지 — 회귀 방지용 lint rule화 고려(P2) |
| God file | 없음 | 최대 `requirements_api.py` 367줄 | — |
| TODO/FIXME | 없음 | grep 0건 | — |
| 테스트 커버리지(간이) | 양호 | `tests/test_*.py` 41개 vs `backend/*.py` 82개 (≈50%) | 정확한 라인 커버리지는 `pytest --cov` 실행 필요(미실행, deferred) |
| **DatabasePort/SqliteProjectAdapter 데드코드** | **P0** | `save_project`/`get_project_status` 둘 다 `NotImplementedError`; 실제 import처는 `sqlite_adapter.py` 자신 + `db_port.py` 뿐 — 서비스 코드에서 미참조. `tests/test_task_manager.py` 등에서는 **파일 경로 문자열**로만 등장(impact_scope 예시일 뿐, 실제 DB 계층 테스트 아님) | ① 이 스텁을 완성해 실제 영속화 계층으로 승격하거나 ② 사용 안 할 거면 제거하고 README/설계원칙의 "SQLite→PostgreSQL 교체" 서술을 실제 구조(JSON 파일 스토어)에 맞게 정정 |

## [성능/확장성]

| 항목 | 현재상태(실측) | 병목 조건 | 대안 |
|------|----------------|-----------|------|
| 영속화 계층 | JSON 파일(`data/requirements_store.json` 20KB, `data/projects/*` 디렉터리) — `requirement_store.py`(333줄)가 `json.load`/`json.dump`로 전체 파일 read-modify-write | 데이터가 지금(20KB)보다 수십~수백 배 커지면 매 쓰기마다 전체 파일 재직렬화 비용 증가, 동시 쓰기 시 `_write_lock`(README 언급) 병목 | 아래 [DB 전환 로드맵] 참조 — JSON→경량 DB(SQLite부터) 단계적 전환 |
| 단일 프로세스 제약 | README에 `--workers` 지정 금지 명시(`requirements_api._write_lock` 전제) | 동시접속 확장 시 프로세스 자체를 늘릴 수 없음(인메모리 락이 프로세스 경계를 못 넘음) | 락을 파일 기반(`task_lock_store.py`가 이미 이 패턴의 선례)이나 DB 트랜잭션으로 옮기면 멀티프로세스 가능 |
| 정적 export | `frontend/data/`에 JSON export 존재(요청 시 재확인 필요, 이번 스캔 범위 밖) | 데이터 증가 시 정적 JSON 재생성 비용 증가 가능 | 필요시 별도 스캔 |

## [보안/안정성]

| 항목 | 현재상태(실측) | 리스크 | 권고 |
|------|----------------|--------|------|
| CORS 설정 | `grep CORSMiddleware\|allow_origins backend/adapters/api/` → **매치 0건** | 브라우저 프론트가 별도 오리진에서 호출 시 차단되거나, 반대로 설정 없이 우회 접근 가능(현재는 동일 오리진 서빙이라 당장은 문제 낮음) | 향후 별도 프론트 배포 시 명시적 CORS 정책 필요 |
| 인증/인가 | `grep Depends(\|HTTPBearer\|APIKey\|authorization` → **매치 0건** | 로컬 개발 단계라 허용되나, README의 "비가역 작업 게이트"(실배포 시 평식 승인)를 API 레벨에서 강제하는 장치가 없음 | 배포 전 최소 API 키 또는 세션 기반 게이트 추가 |
| 전역 예외 처리 | `grep exception_handler` → **매치 0건** | 처리되지 않은 예외가 FastAPI 기본 500 응답으로 스택트레이스를 그대로 노출할 수 있음(디버그 모드 여부 별도 확인 필요) | `@app.exception_handler(Exception)` 추가 + 프로덕션에서 traceback 비노출 |
| 백업/복원 | `infrastructure/`에 이중화 설정 존재(README §"단일↔HA 전환"), 실제 백업 스크립트는 이번 스캔에서 미확인 | JSON 파일 손상 시 복구 수단 불명 | `config_loader.py` 검토 + 최소 정기 스냅샷 스크립트 필요성 검토(별도 태스크) |

## [DB 전환 로드맵] — 정정판 (JSON 파일 → SQLite/PostgreSQL)

> **정정**: 원래 계획(SQLite→PostgreSQL)은 전제가 틀렸다(위 데드코드 발견 참조). 실제 출발점은
> **JSON 파일 스토어**이며, `db_port.py`(Port)+`sqlite_adapter.py`(스텁 Adapter)는 이미 그려진
> 뼈대이되 `Project` 엔티티 1종에만 대응하고 완성되지 않았다는 점을 전제로 재설계한다.

| Phase | 내용 | 선행조건 | 가역성 | 완료 기준 |
|-------|------|---------|--------|----------|
| A — 스텁 완성 또는 폐기 결정 | `SqliteProjectAdapter`를 실제로 완성해 `Project` 저장에 쓸지, 아니면 제거하고 문서를 정정할지 **먼저 결정**(현재 어느 쪽도 아닌 애매한 상태가 가장 나쁨) | 없음 | 완전 가역(문서·주석 수정) | 결정 기록(ADR 1줄이라도) |
| B — Requirement/Task Port 신규 정의 | `requirement_store.py`/`task_store.py`가 이미 하는 일을 `RequirementStorePort`/`TaskStorePort`(이미 `application/ports/`에 존재 확인됨 — `requirement_store_port.py`, `task_store_port.py`)로 계약 고정 — **이 부분은 이미 되어 있을 가능성 높음, 실제 JSON 어댑터가 그 Port를 구현하는지만 확인** | Phase A 결정 | 가역(계약 확인뿐) | 계약-구현 일치 확인 완료 |
| C — SQLite 어댑터 병행 구현 | JSON과 동일 Port를 구현하는 `sqlite_requirement_store.py` 신규 작성(JSON 어댑터는 그대로 둠, CRZ) | Phase B | 가역(신규 파일 추가만) | 동일 인터페이스로 read/write 성공 |
| D — 이중검증 + 컷오버 | 두 어댑터로 동일 연산 실행해 결과 diff 검증 → `config_loader.py`에 스위치 추가 → 실제 전환은 **사용자 승인 후** | Phase C | 컷오버 자체는 비가역(승인 필요) | diff 0 + 승인 기록 |

---

## 우선순위 요약

| 우선순위 | 항목 |
|----------|------|
| **P0** | DatabasePort/SqliteProjectAdapter 데드코드 vs 문서 서술 불일치 정정 (착각 상태 방치가 가장 위험) |
| **P0** | API 인증·전역 예외 처리 부재(배포 전 필수) |
| **P1** | CORS 정책 명시(별도 프론트 배포 시) |
| **P1** | Phase 4 curl 실측 로그 재현 검증(문서 신뢰도 확인) |
| **P2** | 헥사고날 경계 위반을 잡는 lint rule 추가(회귀 방지) |
| **P2** | `pytest --cov`로 정확한 커버리지 수치 확보 |
| **P3** | JSON→SQLite 전환 로드맵 Phase A 착수(현재는 규모상 시급하지 않음 — data 20KB) |

## 진행 기록 (2026-07-23 후속)

- **1번(P0) 착수**: `RequirementStore`→`RequirementStorePort`, `TaskStore`→`TaskStorePort` 명시적
  상속 추가(`backend/adapters/persistence/requirement_store.py`, `task_store.py`) — Port 계약이
  이제 코드로 강제됨(향후 PostgreSQL 어댑터가 이 계약을 안 지키면 인스턴스화 시점에 즉시 실패).
  `SqliteProjectAdapter`(Project 전용 미사용 스텁)는 이번엔 손대지 않음 — Requirement/Task
  경로와 별개 이슈로 남겨둠(별도 결정 필요).
- **2번(P0) 착수**: `backend/server.py`에 CORS 미들웨어 + 전역 예외 핸들러(T99 AIOS envelope) 추가.
- **검증**: 변경 전 베이스라인 `pytest tests/` 288 passed → 변경 후 재실행 **288 passed, 0 failed**
  (회귀 0 확인, §W-5 물증).
- **미완(다음 단계)**: 실제 `postgres_requirement_store.py`/`postgres_task_store.py` 작성은
  실 PostgreSQL 인프라 도입이 전제라 이번 스코프 밖(D4급 결정 필요, 별도 승인 권장). API 인증
  게이트도 이번엔 다루지 않음(CORS+예외처리만).

## 진행 기록 (2026-07-24 후속 — 1번 완성 + Project 저장소 기능 확장)

- **1번 완성 방향 확정**: `SqliteProjectAdapter`/`db_port.py`는 실제 `ProjectRegistry` API와
  메서드명조차 다른 가상 계약임을 확인 → 스텁을 채우는 대신 **삭제**하고, 실제 사용 중인
  `ProjectRegistry`를 Requirement/Task와 동일한 패턴으로 `ProjectStorePort`(신규)에 편입.
  이제 Requirement/Task/Project 3개 저장소가 전부 동일한 Port/Adapter 패턴 — PostgreSQL 전환 시
  3개를 같은 방식으로 스왑 가능.
- **기능 개선(폭넓게)**: `Project.status`(WAITING/IMPLEMENTING/VERIFIED)가 생성 후 전이 수단이
  전혀 없던 기능 갭을 `ProjectRegistry.update_status()` + `PATCH /projects/{id}/status` API로 메움
  (허용값 검증 + 존재하지 않는 프로젝트 거부 + DEFAULT_PROJECT_ID 가상 프로젝트 구체화 처리).
- **검증**: 기능 스모크 4케이스(정상 갱신/기본프로젝트 구체화/잘못된 값 거부/미존재 ID 거부)
  전부 통과 + 전체 회귀 `pytest tests/` **288 passed, 0 failed**(변경 전과 동일 건수, 회귀 0).
- **미완(다음 단계)**: 프론트(project-setup.html 등)에 상태 변경 UI 연결은 이번 범위 밖(백엔드만).

## 진행 기록 (2026-07-24 후속2 — 프론트 상태변경 UI 연결)

- GNB 프로젝트 선택기(`frontend/partials/shell-nav.html` · `frontend/js/shell-loader.js`) 옆에
  상태(WAITING/IMPLEMENTING/VERIFIED) 드롭다운을 신규 추가 — 변경 시 `PATCH /projects/{id}/status`
  호출(값 목록은 `PROJECT_STATUSES` 파이썬 SSOT를 수동 미러링, project-setup.html의
  AREA_CODES/LAYER_CODES와 동일한 기존 CRZ 패턴).
- **검증**: `node --check`로 JS 구문 확인 + 실제 서버 기동(uvicorn) 후 curl로 `GET /projects`·
  `PATCH .../status`(정상값 VERIFIED 적용·잘못된 값 BOGUS 거부)·`GET /partials/shell-nav.html`
  (신규 select 마크업 서빙 확인)까지 실 HTTP로 확인(§W-5). 스모크 테스트가 남긴 실데이터
  변경(`data/projects_registry.json`)은 테스트 후 원상복구(`[]`)했고 테스트 서버도 종료함.

## 진행 기록 (2026-07-24 후속3 — PostgreSQL 어댑터 코드 작성, 평식 승인·검증 미확정)

- **배경**: 평식이 "다음작업 2번(PostgreSQL 인프라 도입) 진행"을 승인. 단, 이 세션엔 실행 중인
  PostgreSQL이 없고(Docker Desktop 미기동) 실제 연결 정보도 없어, AskUserQuestion으로 확인한
  결과 **"코드만 작성, 검증은 미확정으로 명시"** 방향으로 진행.
- **신규 파일**: `backend/adapters/db/postgres/`에 `connection.py`(DATABASE_URL 기반, 미설정 시
  즉시 RuntimeError) · `schema.sql`(requirements/tasks/task_locks/projects/rechunk_queue,
  `{id + data JSONB}` 하이브리드 스키마) · `postgres_requirement_store.py`·`postgres_task_store.py`·
  `postgres_task_lock_store.py`·`postgres_project_store.py`(3개 Port 전부 구현 + Port 외 공개
  메서드도 동일 제공, JSON 어댑터와 완전 드롭인 교체 가능하도록 설계) · `README.md`(검증 미확정
  경고 + 사용 전 필요 절차).
- **설계 원칙**: 비즈니스 로직(REQ ID 채번·PII 스캔·상태전이 검증·서킷브레이커·배타락)은
  JSON 어댑터가 이미 쓰는 domain 함수·dataclass를 그대로 import해 재사용 — 저장 메커니즘만
  교체(CRZ, 로직 중복 0).
- **검증(정직 표기)**: ①모든 모듈 import 성공 ②3개 클래스 전부 해당 Port(ABC)의
  `issubclass()` True(추상 메서드 누락 없음, 정적 계약 검증) ③`DATABASE_URL` 미설정 시
  `get_connection()`이 조용히 실패하지 않고 명시적 RuntimeError 확인 ④기존 회귀 `pytest tests/`
  **288 passed, 0 failed**(신규 파일이 기존 동작에 영향 없음). **실제 PostgreSQL 서버로 연결·
  CRUD·회귀 테스트는 하지 않았다 — SQL 구문·타입 매핑의 실제 정확성은 미확정(deferred)**,
  README.md와 각 파일 상단에 이 사실을 명시.
- **미완(다음 단계)**: 실 PostgreSQL(로컬 Docker 또는 외부 서버)로 `schema.sql` 적용 후 JSON
  어댑터와 동일 입력에 동일 출력을 내는지 이중검증(원래 UPGRADE_PLAN Phase C) — 사용자가 인프라를
  준비하면 후속 세션에서 진행.

## 보류 (2026-07-24 — 평식 명시)

두 후속 항목(①로컬 Docker PostgreSQL 검증 ②외부 PostgreSQL 검증) 모두 **AEGIS 시스템 이전
작업 완료 후 진행 예정** — 현재는 배포 전략을 수립 중이라는 명시적 지시로 보류. directive
`D-c92bd806`로 durable 기록(세션 간 유실 방지). 재검토 조건: AEGIS 시스템 이전 완료 + 배포
전략 확정 시.

*생성: 2026-07-23 · 실행: `/aegis-upgrade-plan`(로컬본) 실측 기반 · 다음 실행 시 이 파일에 diff 추가 권장*
