---
description: ai-project-system 실측 기반 시스템 고도화 목록 생성 — 기능커버리지·아키텍처품질·성능확장성·보안안정성 + SQLite→PostgreSQL 점진 전환 로드맵
argument-hint: "[영역 필터, 예: backend | frontend | db] (생략 시 전체)"
---

# /aegis-upgrade-plan — ai-project-system 고도화 목록

이 커맨드는 이 프로젝트(`00_PROJECT_CONSTITUTION.md` 기준: 요구사항 문서 → 구조화 →
영역별 태스크 관리 시스템)의 **현재 코드/문서 상태를 실측**해서 고도화(업그레이드) 항목을
뽑아낸다. 추정으로 항목을 만들지 말 것 — 모든 항목은 `file:line` 또는 실행한 명령 결과를
근거로 제시한다 (CFD 실측 우선 원칙).

인자 `$ARGUMENTS`가 있으면 해당 영역(backend/frontend/db 등)만 다루고, 없으면 아래
4관점 + DB 전환 로드맵을 전부 수행한다.

---

## Step 0 — 기준 문서 확인

다음을 먼저 읽어 "현재 설계상 의도"를 확정한다 (없으면 그 사실 자체를 보고):
- `00_PROJECT_CONSTITUTION.md` §1(핵심 목표) · §4(드리프트 체크리스트) · §5(영역코드)
- `00_DESIGN_TOC.md` (Phase별 설계 목차 — 어디까지 구현/설계만 되어 있는지)
- `README.md` (현재 단계 선언 — 예: "Phase 3은 설계만")

## Step 1 — 기능/요구사항 커버리지 갭

- `00_DESIGN_TOC.md`의 Phase 목록을 표로 뽑는다.
- 각 Phase가 실제로 `backend/application/services/`·`backend/adapters/api/`에
  구현되어 있는지 `grep`/`Glob`으로 대조한다 (설계만 된 Phase vs 구현된 Phase).
- `00_PROJECT_CONSTITUTION.md` §5 영역코드 중 실제 요구사항 데이터(`backend/adapters/persistence/`,
  `data/`)에 등장하지 않는 코드가 있는지 확인.
- 산출: **[기능 갭]** 표 — Phase/영역코드 · 설계상태 · 구현상태 · 증거(file:line).

## Step 2 — 아키텍처/코드 품질

- 헥사고날 경계 위반 점검: `backend/domain/` 안에서 `import` 문에 `adapters`나
  `fastapi`/`sqlite3` 같은 I/O 라이브러리가 등장하는지 grep (경계 위반 = 순수 로직에
  기술 의존 유입).
- God file 탐지: `backend/` 하위 `.py` 파일 라인수 상위 10개 (`wc -l` 또는 Glob+Read).
- `TODO`/`FIXME`/`XXX` grep → 미해결 항목 목록.
- 테스트 커버리지: `tests/` 파일 수 대비 `backend/` 모듈 수 비율(간이 지표), 최근
  `pytest` 결과 유무.
- 산출: **[아키텍처 품질]** 표 — 항목 · 심각도 · 증거 · 권고.

## Step 3 — 성능/확장성

- `backend/adapters/db/sqlite_adapter.py`를 읽고: 커넥션 관리 방식(요청마다 재연결?
  커넥션 풀?), WAL 모드 여부, 인덱스 존재 여부, 트랜잭션 범위를 확인.
- `README.md`에 명시된 `--workers` 금지 제약(`requirements_api._write_lock` 전제,
  단일 프로세스)을 실제 코드에서 재확인 — 이 제약이 향후 동시접속 확장에 병목이 되는지
  판단.
- `frontend/data/`에 정적 JSON export 방식이 데이터 증가 시 확장성 한계가 있는지 파일
  크기로 가늠 (`ls -la` 크기).
- 산출: **[성능/확장성]** 표 — 항목 · 현재상태(실측) · 병목 조건 · 대안.

## Step 4 — 보안/안정성

- `backend/adapters/api/`의 엔드포인트에서 인증/인가 유무, CORS 설정, 입력 검증
  (Pydantic 등) 존재 여부 grep.
- 에러 핸들링 패턴(전역 예외 핸들러 존재 여부), 로그에 민감정보 노출 여부(`server.log`
  샘플 확인).
- 백업/복원 정책 유무 — `infrastructure/`에 이중화·백업 설정이 실제로 존재하는지,
  아니면 문서상 계획만인지 (README §"비가역 작업 게이트" 참고).
- 산출: **[보안/안정성]** 표 — 항목 · 현재상태 · 리스크 · 권고.

## Step 5 — SQLite → PostgreSQL 점진 전환 로드맵 (항상 포함)

현재 `backend/application/ports/db_port.py`(Port)와
`backend/adapters/db/sqlite_adapter.py`(Adapter)가 이미 Port/Adapter로 분리되어
있음을 실제 코드로 확인한 뒤, 이 경계를 근거로 **가역적 단계별** 전환 계획을 세운다.
한 번에 컷오버하지 말고 아래 순서로 제안한다:

1. **Phase A — 계약 고정**: `db_port.py`의 메서드 시그니처가 SQLite 전용 가정(예:
   `sqlite3.Row`, `?` 플레이스홀더 노출)을 담고 있지 않은지 점검 → 있으면 먼저
   PostgreSQL에서도 동작하는 순수 계약으로 정리(이 자체가 가역적 리팩토링).
2. **Phase B — PostgreSQL Adapter 신규 구현**: `sqlite_adapter.py`를 건드리지 않고
   `postgres_adapter.py`를 같은 Port 계약으로 병행 구현 (기존 동작 무영향, CRZ).
3. **Phase C — 데이터 마이그레이션 + 이중검증**: 현재 SQLite 데이터를 PostgreSQL로
   이관하는 스크립트 + 두 어댑터로 동일 쿼리 실행해 결과 diff 검증(§W-5 물증 확보).
4. **Phase D — 컷오버 + 롤백 경로**: `infrastructure/config_loader.py`(README에
   "단일↔HA 전환" 담당으로 명시됨)에 어댑터 선택 스위치를 추가해 설정값 하나로
   SQLite/PostgreSQL 전환·롤백 가능하게 함. 실제 트래픽 전환은 **비가역 작업이므로
   사용자 명시 승인 전 실행 금지**.

산출: **[DB 전환 로드맵]** 표 — Phase · 내용 · 선행조건 · 가역성 · 완료 기준.

## Step 6 — 결과 저장 + 우선순위

모든 항목을 모아 `plans/_plan/UPGRADE_PLAN_{YYYY-MM-DD}.md`에 저장한다(디렉터리 없으면
`plans/_plan/` 확인 후 생성). 각 항목에 우선순위(P0 긴급~P3 여유)와 근거를 표시하고,
문서 맨 위에 3~5문장 요약을 둔다. 마지막에 다음 표를 포함한다:

```
| 차원 | 현재 상태 | 고도화 방향 | 비고 |
|------|----------|-------------|------|
| 기능 커버리지 | ... | ... | ... |
| 아키텍처/코드품질 | ... | ... | ... |
| 성능/확장성 | ... | ... | ... |
| 보안/안정성 | ... | ... | ... |
| DB(SQLite→PG) | ... | ... | ... |
```

## Step 7 — 보고

사용자에게 저장 경로와 P0 항목 개수만 짧게 요약해서 알린다. 전체 목록은 파일을 열어
보게 안내한다.
