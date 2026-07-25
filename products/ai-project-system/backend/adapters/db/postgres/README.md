# PostgreSQL 어댑터 (2026-07-24 신설)

> ⚠ **검증 미확정(unverified)**: 이 디렉터리의 어댑터는 실제 PostgreSQL 서버로 연결·CRUD·
> 회귀 테스트를 거치지 **않았다**(평식 지시 2026-07-24 — "코드만 작성, 검증은 미확정으로
> 명시"). 이 세션 환경에는 실행 중인 PostgreSQL이 없고(Docker Desktop 미기동), 실제
> 검증 없이 "작동함"이라 보고하는 것은 T98 AIP(§W-5 물증 원칙) 위반이다 — 그래서 이
> README와 각 파일 상단에 동일 경고를 반복한다.

## 배경 — 왜 이 어댑터가 필요한가

`UPGRADE_PLAN_2026-07-23.md`(고도화 목록) 진행 과정에서, `backend/application/ports/`의
`RequirementStorePort`·`TaskStorePort`·`ProjectStorePort` 3개 Port가 이미 JSON 파일
어댑터(`requirement_store.py`·`task_store.py`·`project_registry.py`)로 구현돼 있고,
`infrastructure/requirements.txt`에는 애초에 `psycopg2-binary`/`sqlalchemy`/`pgvector`가
"공식 선언"돼 있었음(과거 설계 의도)을 확인했다. 이 디렉터리는 그 선언을 실제 코드로
채우는 두 번째 어댑터 세트다 — **JSON 어댑터를 대체하지 않는다**(그대로 유지, CRZ). 호출부
(`requirements_api.py`/`tasks_api.py`/`projects_api.py`)가 이 Postgres 구현으로 전환하려면
각 API 모듈의 팩토리 함수(`get_requirement_store()` 등)만 바꾸면 된다 — 이것이
Port/Adapter 분리의 목적이다.

## 설계 원칙 — JSON 어댑터와 동일 동작, 저장 메커니즘만 교체

각 Postgres 어댑터는 대응하는 JSON 어댑터의 **비즈니스 로직(검증·상태전이·감사이력)을
재구현하지 않고 그대로 import해서 재사용**한다(CRZ — 로직 중복 = 두 곳에서 규칙이 갈라질
위험). 예를 들어 `PostgresRequirementStore`는 `requirement_store.py`의
`RequirementRecord`·`StatusChangeEvent`·`LIFECYCLE_STATUSES`·`REASON_REQUIRED_STATUSES`를
그대로 가져다 쓰고, "레코드를 어디서 읽고 어디에 쓰는가"만 JSON 파일 대신 PostgreSQL
테이블로 바꾼다.

**스키마 전략**: 각 도메인당 컬럼을 세세히 나누는 정규화 스키마 대신, `{id 컬럼} + data
JSONB` 하이브리드 테이블을 쓴다(`schema.sql` 참조) — JSON 어댑터의 레코드 구조가 이미
복잡하고(예: `RequirementRecord` 24개 필드 + 중첩 이력 배열) 자주 바뀌어 왔으므로(§2-3 등
반복 재설계 이력), 매 필드 변경마다 스키마 마이그레이션이 필요한 완전 정규화보다 안전하고
실제 검증 없이도 구조적으로 깨질 위험이 적다. `req_id`/`task_id`/`project_id`처럼 조회에
필수인 키만 실제 컬럼으로 두고 나머지는 JSONB 안에 그대로 보존한다.

## 파일 구성

| 파일 | 역할 |
|------|------|
| `connection.py` | `DATABASE_URL` 환경변수로 psycopg2 커넥션 생성(연결 정보는 이 세션에 없어 하드코딩 금지) |
| `schema.sql` | `requirements`/`tasks`/`task_locks`/`projects`/`rechunk_queue` 테이블 DDL |
| `postgres_requirement_store.py` | `RequirementStorePort` 완전 구현 + JSON 어댑터의 비-Port 공개 메서드(`set_design_draft_gate` 등)도 동일하게 제공(드롭인 교체 목적) |
| `postgres_task_store.py` | `TaskStorePort` 완전 구현 + `set_status`/`generate_task_id` 등 |
| `postgres_task_lock_store.py` | `TaskLockStore`(파일 기반)와 동일 공개 API를 제공하는 테이블 기반 락 |
| `postgres_project_store.py` | `ProjectStorePort` 완전 구현 |

## JSON/Postgres 이중구조 drift 관리 체크리스트 (2026-07-25, 5-agent 진단 P2 후속)

> `postgres_*` 어댑터는 로직을 재구현하지 않고 JSON 어댑터(`RequirementRecord`·`Task`)의
> dataclass를 그대로 import해 쓰므로, **필드 자체가 갈라질 위험은 낮다**(CRZ). 실제 drift
> 위험은 **실제 컬럼으로 분리해 둔 소수 필드**와 **인덱스/조건절**에서만 발생한다 — 아래
> 표에 없는 필드(예: `matched_keywords`·`design_draft_gate` 등)는 JSONB에 자동 포함되므로
> 스키마 변경이 필요 없다.

| dataclass 변경 유형 | schema.sql 갱신 필요? | 확인 위치 |
|---|---|---|
| `RequirementRecord`에 필드 추가/삭제(실제 컬럼 아닌 것) | 불필요 — `data JSONB`에 자동 포함 | — |
| `req_id`/`doc_type_code`/`area_code`/`lifecycle_status` 자체의 의미·타입 변경 | **필요** | `schema.sql:5-11`(requirements 테이블 컬럼+인덱스) |
| `Task`에 필드 추가/삭제(`task_id`/`status` 아닌 것) | 불필요 — `data JSONB`에 자동 포함 | — |
| `task_id`/`status` 자체의 의미·타입 변경 | **필요** | `schema.sql:21-27`(tasks 테이블 컬럼+인덱스) |
| `TaskLockStore` 공개 API(락 키 구조) 변경 | **필요** | `schema.sql:30-34`(task_locks) + `postgres_task_lock_store.py` |
| `lifecycle_status`/`status`로 필터링하는 새 조회 API 추가 | 인덱스 확인 필요 | 기존 `idx_requirements_lifecycle_status`/`idx_tasks_status` 재사용 가능한지 먼저 확인, 새 컬럼 조건이면 인덱스 추가 |

**갱신 절차**: ① JSON 어댑터 dataclass 변경 → ② 위 표에서 "실제 컬럼" 해당 여부 판정 → ③
해당 시 `schema.sql` + 대응 `postgres_*_store.py` 동시 수정 → ④ (검증 가능 시점부터) 두
어댑터에 동일 입력을 넣어 동일 출력을 대조. 이 프로젝트는 현재 Postgres 미배선(죽은 코드)
상태이므로 ④는 실제 배선 결정 시점에 일괄 수행하면 되고, 지금은 ①~③만 놓치지 않으면 된다.

## 사용 전 필요한 것 (미확정 상태를 벗어나려면)

1. 실행 중인 PostgreSQL(로컬 Docker든 외부 서버든) + `DATABASE_URL` 환경변수
2. `psql $DATABASE_URL -f backend/adapters/db/postgres/schema.sql`로 스키마 적용
3. 각 어댑터를 실제로 인스턴스화해 JSON 어댑터와 **동일 입력에 동일 출력**을 내는지 대조
   (지난 UPGRADE_PLAN 진행 기록의 "Phase C — 데이터 마이그레이션 + 이중검증" 그대로)
4. 이 README와 각 파일 상단의 "검증 미확정" 경고를 실제 검증 완료 후 제거/갱신
