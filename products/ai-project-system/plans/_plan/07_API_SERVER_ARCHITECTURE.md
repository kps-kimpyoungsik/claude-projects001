---
role: DESIGN_API_ARCHITECTURE
scope: 프론트엔드(frontend/views/*.html) ↔ 백엔드(backend/ 헥사고날 도메인/응용/어댑터) 연결 API 서버 아키텍처 결정
status: 설계 검토완료 + 최소 구현 완료(2026-07-19) — §DRL 참조. **실제 프로세스로 상시
  기동한 적은 없음 — 수동 기동 명령(`uvicorn backend.server:app`)만 문서화.**
updated: 2026-07-19
---

# API 서버 아키텍처 설계

> 상위: [`00_INDEX.md`](./00_INDEX.md)
> 이 문서는 **설계 결정 문서**다. `backend/adapters/api/` 등 실제 서버 코드를 만들지 않는다.
> 다음 사이클에서 사용자가 이 문서를 승인한 뒤에만 구현에 착수한다(T59 CFD — 실측 우선
> 설계, 가정 기반 구현 금지 원칙을 이 문서 자체에도 적용: 아래 근거는 전부 실측이다).

## §0. 배경 — 왜 지금 필요한가

`plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md` §2-3(상태변경 액션)과 §2-4(PII 접근제어
게이트)는 프론트엔드가 `RequirementStore.set_status()` / 문서 원문 접근을 **직접 함수
호출이 아니라 어떤 경계를 거쳐서** 호출해야 하는 설계다. 지금까지 프론트엔드는
`python -m http.server`로 정적 HTML만 서빙했고, `backend/`의 실제 도메인/응용 로직은
`tests/`(pytest)에서만 호출되어 왔다 — 브라우저가 이 로직을 부를 방법이 없다.
`06_AGENT_DISPATCH_REPORTING.md`에서 설계한 `task_dispatch_service.dispatch_tasks()`도
동일하게 순수 Python 함수로만 존재하고 HTTP로 노출되지 않은 상태다.

이 문서는 그 경계(API 서버)를 **무엇으로 만들지** 결정한다.

## §1. 실측 — 현재 백엔드 구조

`backend/` 디렉터리 실측(Glob, 2026-07-19):

```
backend/
├── domain/                         # 순수 도메인 (엔티티·규칙, 외부 의존 없음)
│   ├── entities/{project,requirement,task}.py
│   ├── requirements/{codes,id_format,classifier,conflict_detection}.py
│   ├── chunking/{chunk,heading_splitter}.py
│   └── graph/entities.py
├── application/                    # 응용 서비스 (도메인 조합, 유스케이스)
│   ├── services/{context_service, requirement_extraction_service,
│   │              graph_pipeline_service, agent_dispatch_resolver,
│   │              completion_report_service, task_dispatch_service,
│   │              dispatch_execution_planner}.py
│   └── ports/{db_port, parser_port, requirement_store_port, task_store_port}.py
└── adapters/                       # 구체 기술 (JSON 파일 저장·파서·DB)
    ├── persistence/{document_store, project_config_store,
    │                requirement_store, task_store, agent_role_usage_log}.py
    ├── parsers/{router, docx_adapter}.py
    ├── extractors/{ast_extractor, semantic_extractor}.py
    ├── db/sqlite_adapter.py
    ├── aegis_bridge/search_all_adapter.py
    ├── error_log.py
    └── api/health.py               # ← 이미 존재. envelope 뼈대만, 라우팅 없음
```

핵심 관찰:
- **`backend/adapters/api/health.py`가 이미 존재한다** — `health_envelope(version)` 하나만
  있고 실제 HTTP 서버(FastAPI/Flask 앱, 라우터)는 없다. 즉 "API 어댑터 계층"이라는 자리는
  이미 헥사고날 구조상 예비되어 있었고, 이번 설계는 그 빈 자리를 채우는 것이지 새 계층을
  발명하는 게 아니다(CRZ).
- `health_envelope()`은 이미 T99 AIOS 공통 envelope(`{ok, data, error, meta}`)을 반환한다 —
  이번 설계의 모든 신규 엔드포인트도 이 envelope을 그대로 재사용한다(신규 포맷 발명 없음).
- 포트(`requirement_store_port.py`, `task_store_port.py`)가 이미 ABC로 존재 — API 라우터는
  구체 클래스(`RequirementStore`)가 아니라 이 포트 타입에 의존하도록 설계하면 헥사고날
  의존 방향(adapters → domain, API도 adapters의 일종)이 깨지지 않는다.
- `RequirementStore.set_status(req_id, status, actor, reason=None)`은 이미 확정된 시그니처
  (`plans/_plan/01_PHASE1_DATA_MODEL.md` §2-3-A) — API가 그대로 감싸기만 하면 된다. 신규
  파라미터 설계 불필요.

## §2. 프레임워크 선택

### §2-1. 실측 — 이미 설치된 패키지

`pip list` 실측 결과(2026-07-19), 신규 설치 없이 이미 사용 가능한 패키지:

```
fastapi        0.135.3
starlette      0.52.1
uvicorn        0.41.0
pydantic       2.12.5 / pydantic-settings 2.13.1
Flask          3.1.3
```

**FastAPI와 Flask 둘 다 이미 설치돼 있다.** `infrastructure/requirements.txt`에는
`sqlalchemy`/`psycopg2-binary`/`pgvector`만 명시돼 있어 이 셋이 이 프로젝트가 "공식
선언한" 의존성 목록이지만, 실행 환경에는 FastAPI 계열이 이미 존재한다 — 이는 AEGIS
공유 Python 환경(다른 프로젝트가 이미 설치)에서 온 것으로 추정되며, 이 프로젝트 전용
가상환경이 별도로 없다는 뜻이기도 하다(실측 사실로만 기록, 원인은 이 설계 범위 밖).

### §2-2. 결정 — FastAPI

| 후보 | 판정 | 근거 |
|---|---|---|
| **FastAPI** | **채택** | ①이미 설치됨(신규 의존성 0, §2-1 실측) ②`RequirementRecord`·`Task` 등 이 프로젝트 전체가 이미 `@dataclass` 기반 — Pydantic 모델로의 변환 비용이 낮고, 특히 T99 AIOS §4 "경계검증"이 요구하는 "malformed 입력 → 4xx, 200+degraded 금지"가 Pydantic의 자동 422 검증으로 **별도 코드 없이** 충족됨(실측: `graphify-hub/intelligence`가 이미 Pydantic 422로 이 표준을 만족한다고 CLAUDE.md T99에 명시) ③OpenAPI 스키마 자동 생성 — §2-3 엔드포인트 계약을 코드가 자체 문서화 |
| Flask | 기각 | 더 가볍지만 요청 바디 검증을 직접 짜야 함 — T99 AIOS 경계검증 요건을 수동 구현해야 하므로 이 프로젝트 규모(소규모, 세션 단위)에 비해 개발 비용이 오히려 더 든다 |
| 순수 `http.server` 확장 | 기각 | 신규 의존성은 0이 되지만, JSON 바디 파싱·라우팅·검증을 전부 손으로 구현해야 함 — 이미 FastAPI가 설치돼 있는 상황에서 "의존성 최소화"라는 이유만으로 이 선택지를 택하는 것은 실측(§2-1)을 무시한 과도한 보수화. 헌법 §4 "AEGIS류 인프라를 도구로만" 원칙은 AEGIS MCP/스킬류 무거운 인프라에 해당하는 것이지, 표준 Python 웹 프레임워크 채택 여부와는 다른 판단축이다 |

**결론**: FastAPI. 신규 `pip install` 불필요(§2-1 실측이 그 근거) — `infrastructure/requirements.txt`에
`fastapi`·`uvicorn`만 추가 문서화하면 된다(이번 사이클에서는 문서 언급만, 실제 파일 수정은
구현 승인 후).

## §3. 실행 모델 — 로컬 세션 단위 vs 상시 서비스

`plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §2-2(전례, 실측 인용)에서 이미 "이 프로젝트는
상시 실행 서비스가 아니라 세션 단위로 LLM이 작업하는 구조"라고 판정하고, `aegis-growth-schedule`
같은 상시 서비스 패턴을 "이 프로젝트 목적에 비해 무겁다"고 기각한 전례가 있다.

**이번 결정도 그 판정과 일관성을 유지한다**: API 서버 자체는 "떠 있어야만 프론트엔드가
동작하는 상시 프로세스"이지만, 이는 "AEGIS류 상시 스케줄러/모니터링 인프라"와는 다른
층위다 — API 서버가 없으면 §2-3/§2-4 기능 자체가 성립하지 않는 **이 재설계의 필수 실행체**
이지, 부가적인 자동화 인프라가 아니다. 따라서:

- **로컬, 필요할 때만 기동** — `python -m backend.server`(또는 `uvicorn backend.adapters.api.app:app`)
  형태로 사용자가 작업 세션을 시작할 때 수동 기동. 백그라운드 상시 서비스(Windows 서비스·pm2
  상시 프로세스)로 등록하지 않는다.
- 지금까지 정적 파일 서빙에 썼던 `python -m http.server`는 FastAPI 앱이 `StaticFiles`
  마운트로 흡수한다(§5 참고) — 프로세스를 2개 띄우지 않고 하나로 통합, 오히려 기동 단계가
  단순해진다.
- 이 판단은 03_PHASE3 §2-2와 동일 축("세션 단위 vs 상시 서비스")의 연장선이며 모순되지
  않는다 — API 서버의 "상시성"은 "한 세션 동안 계속 떠 있음"이지 "재부팅 후에도 자동
  기동하는 배포된 서비스"가 아니다.

## §4. 최소 엔드포인트 설계

범위 판단(작업 지시 §3): task_dispatch_service/dispatch_execution_planner 노출은 이번
문서에서 **제외**한다 — §2-3/§2-4에 직접 필요한 최소 엔드포인트만 설계한다(범위 확장은
별도 사이클 판단 대상, 헌법 §4 자문 "직접 기여하는가?" 기준 미충족).

### §4-1. `POST /requirements/{req_id}/status`

§2-3(상태변경 액션)을 구현하는 유일한 엔드포인트. `RequirementStore.set_status()`를 그대로 감싼다.

**요청**
```jsonc
{
  "status": "ACCEPTED",       // LIFECYCLE_STATUSES 중 하나 (필수)
  "actor": "hong.gildong",    // 로그인 사용자 식별자 (필수, 02_PHASE2 §2-3 — 이 API는 인증 자체를 구현하지 않고 프론트가 넘긴 식별자를 그대로 status_history에 기록만 함)
  "reason": "중복 요구사항"    // REJECTED/WITHDRAWN이면 필수, 그 외 선택
}
```

**응답 (T99 AIOS envelope)**

성공 200:
```jsonc
{ "ok": true, "data": { "req_id": "REQ-...", "lifecycle_status": "ACCEPTED", "status_history": [...] },
  "error": null, "meta": { "degraded": false, "stub": false } }
```

실패 4xx (Pydantic 검증 실패 → 422, 도메인 규칙 위반 → 409):
```jsonc
{ "ok": false, "data": null,
  "error": { "code": "AEGIS-VALIDATION", "message": "WITHDRAWN 전이는 reason이 필수다", "details": {} },
  "meta": { "degraded": false, "stub": false } }
```
`RequirementStore.set_status()`가 던지는 `ValueError`(미등록 status·reason 누락)는 422,
`KeyError`(존재하지 않는 req_id)는 404로 매핑 — 신규 예외 타입 발명 없이 기존 예외를
그대로 HTTP 상태코드에 매핑만 한다.

### §4-2. `GET /requirements/{req_id}/preview`

§2-4(PII 게이트 포함 원문 미리보기)를 구현. `DocumentStore` + `SourceLocation`(§1-2, 2차
설계) 조회를 감싸고, PII 게이트를 API 레벨에서 강제한다(§6 참조).

**요청 쿼리 파라미터**: `?actor=hong.gildong&confirm_pii=false`
(`confirm_pii`는 `contains_pii=true`인 청크에 대해 사용자가 "민감정보 열람 확인" 클릭스루를
통과했는지를 프론트가 전달하는 플래그)

**응답 200 (PII 아니거나 confirm_pii=true인 경우)**
```jsonc
{ "ok": true, "data": {
    "req_id": "REQ-...", "doc_id": "...", "doc_filename": "...",
    "heading_path": ["2장", "보안 요건"], "char_start": 1204, "char_end": 1532,
    "content_excerpt": "...(정규화 마크다운 중 char_start~char_end 구간)...",
    "contains_pii": false, "doc_type_confidence": 0.82, "area_confidence": 0.91
  }, "error": null, "meta": { "degraded": false, "stub": false } }
```

**응답 200 — PII 게이트 대기 (contains_pii=true 이고 confirm_pii=false)**
```jsonc
{ "ok": true, "data": { "requires_pii_confirmation": true, "req_id": "REQ-..." },
  "error": null, "meta": { "degraded": false, "stub": false } }
```
(원문 `content_excerpt`는 이 응답에 포함하지 않는다 — §6에서 근거 설명)

이 두 번째 호출(`confirm_pii=true`)이 성공하면 서버가 `preview_access_log.jsonl`에
`{req_id, actor, ts, granted:true}`를 append(02_PHASE2 §2-4에서 이미 확정된 로그 포맷 그대로,
신규 로깅 포맷 발명 없음).

## §5. 정적 파일 서빙 통합

`frontend/views/*.html`은 FastAPI의 `StaticFiles` 마운트로 흡수한다:
```python
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```
지금까지 `python -m http.server`로 띄우던 것을 대체 — 프로세스 하나로 통합되므로 오히려
기동 절차가 단순해진다(포트 2개 → 1개). 이 통합 자체는 §4 엔드포인트와 직접 관련은 없지만
"API 서버를 만드는 김에 기존 정적 서빙을 어떻게 할지"를 명시하지 않으면 실행 모델(§3)이
불완전하므로 함께 결정해둔다.

## §6. 정보안정성 — PII 게이트의 API 레벨 강제

작업 지시 §5 확인 사항: "프론트엔드가 직접 원문 파일에 접근하지 못하고 반드시 이 API를
거치도록 하는 구조인가."

**실측 근거**: 현재 원문 문서는 `backend/adapters/persistence/document_store.py`가 관리하는
경로에 있고, 이 경로는 `frontend/`(FastAPI `StaticFiles` 마운트 대상, §5) 트리 밖에 있다.
즉 **원문 저장 위치와 정적 서빙 루트가 이미 분리돼 있어**, 프론트엔드가 `fetch("/원문파일경로")`
형태로 직접 접근할 수 있는 구조 자체가 아니다 — `GET /requirements/{req_id}/preview` API가
**유일한 경로**로 남는다(우회 가능한 정적 링크가 없음). 이것이 "API 레벨에서 우회 불가능"의
근거다.

추가로 §4-2 설계에서 `contains_pii=true`이고 `confirm_pii=false`인 응답에는 `content_excerpt`
자체를 아예 포함하지 않는다 — 게이트를 "프론트 UI가 모달을 안 띄우는 것"에만 의존하지 않고,
**서버가 원문을 내려보내지 않는 것**으로 강제한다(프론트 코드를 신뢰하지 않는 방어 — 클라이언트
측 우회 시나리오까지 막는다).

## §7. 명세 요약 표

| 항목 | 결정 |
|---|---|
| 프레임워크 | FastAPI (+ uvicorn, StaticFiles) — 신규 설치 없음(이미 설치됨, §2-1 실측) |
| 배치 위치 | `backend/adapters/api/`(기존 `health.py` 옆, 헥사고날 어댑터 계층) |
| 실행 모델 | 로컬 세션 단위 수동 기동 (`python -m backend.server`) — 상시 서비스 아님 |
| 엔드포인트 수 | 2개 (`POST /requirements/{req_id}/status`, `GET /requirements/{req_id}/preview`) + 기존 `GET /health` |
| 응답 포맷 | T99 AIOS 공통 envelope 재사용 (신규 포맷 없음) |
| PII 게이트 강제 지점 | API 서버(원문 저장소가 정적 서빙 루트 밖에 있어 API가 유일한 접근 경로) |
| 배차 서비스(§06) 노출 | 이번 문서 범위 제외(§4 판단) |

## §8. MPCR 7관점 품질검토

| 관점 | 검토 결과 |
|---|---|
| 개발 | FastAPI가 이미 설치돼 있어(§2-1 실측) 신규 의존성 설치 없이 바로 착수 가능 — 구현 난이도 낮음(D2). 기존 `health.py` envelope·기존 포트(ABC)·기존 `set_status` 시그니처를 그대로 재사용해 신규 코드는 라우팅 계층에 국한됨 |
| 설계 | `backend/adapters/api/` 자리가 이미 헥사고날 구조상 예비돼 있었다(`health.py` 존재) — 이번 설계는 빈 계층을 채우는 것이지 새 계층 발명이 아님(CRZ). 라우터는 구체 클래스가 아니라 포트(ABC) 타입에 의존하도록 설계해 의존 방향 유지 |
| 운영 | 로컬 세션 단위 기동은 03_PHASE3 §2-2 전례와 일관 — 상시 서비스 인프라(모니터링·재기동 정책) 추가 부담 없음. 정적 서빙과 API를 한 프로세스로 통합해 오히려 기동 절차 단순화(§5) |
| 정보안정성 | PII 게이트를 "서버가 원문을 안 보낸다"는 방식으로 강제(§6) — 클라이언트 신뢰에 의존하지 않음. 단, 로그인/역할 인증 자체는 02_PHASE2 §2-4에서 이미 범위 밖으로 확정된 사항을 그대로 계승(actor는 프론트가 넘긴 식별자를 신뢰) |
| 헌법정합 | 00_PROJECT_CONSTITUTION.md §4 자문 4항목 모두 통과 — 이 API는 "요구사항 상태 전이/미리보기"라는 이미 확정된 기능(§2-3/§2-4)을 실행 가능하게 만드는 도구이지 그 자체가 목적화되지 않음(엔드포인트를 §4 범위로 의도적으로 제한한 것이 이 판단의 실행 근거) |
| 검증 | 이번 문서는 설계만 — 구현 단계에서 pytest(FastAPI `TestClient`)로 §4-1/§4-2 각각 정상/실패 케이스 검증 필요(다음 사이클 항목으로 남김, 이번 문서에서 실행하지 않음) |
| 책임 | actor 필드는 02_PHASE2 §2-3에서 이미 확정된 감사 패턴(`status_history`)을 그대로 따름 — 이 설계에서 신규 책임 추적 방식을 만들지 않음 |

**게이트 결론**: PASS — Critical 없음. 유일한 한계는 "구현 후 실측 검증이 아직 없다"는 점이며,
이는 설계 문서 단계의 정상적인 한계로 남긴다(추정을 확정처럼 포장하지 않음, T98 AIP).

## §9. 다음 사이클(구현) 전 확인 필요 사항

- `infrastructure/requirements.txt`에 `fastapi`·`uvicorn` 명시 추가 여부(문서화 vs 실제 고정 버전 pin) — 사용자 판단 필요
- `backend/server.py`(또는 `backend/adapters/api/app.py`) 진입점 파일 위치 — 헥사고날 구조상 `adapters/api/` 하위가 자연스러우나 최종 파일명은 구현 사이클에서 확정
- 이 문서는 **설계만**이며, 위 결정에 대한 사용자 승인 후에만 구현 사이클을 시작한다.

## §DRL 재검토(2026-07-19) — 사용자 승인 후 구현 착수 사이클

> §8 MPCR 검토(2026-07-19 작성분)를 유지한 채, 사용자가 "심층적 설계검토 → 통과 시 구현"을
> 명시 지시해 이번 사이클에서 실제 코드 작성까지 진행한다. 아래는 그 직전 비판적 재검토다.

### DRL-1. 동시성/경합 — Critical, 보강 필요 (해소함)

**실측**: `RequirementStore._save_all`/`RequirementRecord`는 `json.loads` 전체 로드 →
메모리에서 수정 → `json.dumps` 전체 저장(read-modify-write, 파일 락 없음). `backend`
전체(`document_store.py` 포함)에 `Lock`/`fcntl`/`msvcrt` 등 락 패턴이 전혀 없음(grep 실측,
0건). §3에서 "로컬 세션 단위 수동 기동"이라고만 되어 있고, **uvicorn을 worker 몇 개로
띄울지, 같은 프로세스 내 동시 요청 시 이 read-modify-write가 깨질 수 있다는 위험은 설계서에
명시돼 있지 않았다** — 이 재검토에서 Critical로 판정.

FastAPI/uvicorn 동시성 모델(로컬 코드·주석 수준 확인, 외부 웹 검색 없이 판단): uvicorn은
기본적으로 `--workers` 미지정 시 **단일 프로세스**로 뜨고, FastAPI의 동기(`def`, `async`
아님) 경로 핸들러는 스레드풀(`anyio` worker thread, 기본 상한 40)에서 실행된다 — 즉 같은
프로세스 안에서도 **여러 요청이 서로 다른 스레드에서 동시에** `RequirementStore.set_status()`
를 호출할 수 있어 read-modify-write 경합이 발생할 수 있다(멀티 프로세스 worker가 아니어도
발생 가능한 위험이므로 "단일 worker로 실행"만으로는 완전히 해소되지 않음).

**보강 결정**: 신규 락 엔진이나 파일 락 라이브러리를 도입하지 않고(CRZ — 과잉설계 회피,
이 프로젝트는 로컬 세션 단위 단일 사용자 도구), **API 라우터 계층에 `threading.Lock()`
하나를 두어 스토어에 대한 쓰기 경로(상태 변경·PII 열람 로그 append)를 직렬화**한다. 이는
"이 프로세스 안에서 최소한 무결성 있는 read-modify-write"를 보장하는 최소 완화책이며,
`RequirementStore`/`DocumentStore` 자체는 손대지 않는다(기존 클래스 계약 불변, CRZ).
추가로 실행 가이드에 **"`uvicorn --workers` 지정 없이(기본값=1) 단일 프로세스로만 기동"**
을 명시해 프로세스 간 경합(락이 막지 못하는 범위)까지 배제한다. 다중 사용자·다중 프로세스로
스케일해야 하는 시점이 오면 파일 락 또는 DB 백엔드 전환이 필요하다는 한계를 그대로 남긴다
(과장 금지, T98 AIP — 지금 보강은 "단일 프로세스 내 스레드 경합"까지만 막는다).

### DRL-2. 에러 처리 — 이미 충분, 보강 불필요

§4-1에 `ValueError`→422, `KeyError`→404 매핑이 이미 명시돼 있고, §4-2도 req_id 미존재를
같은 방식으로 다룰 수 있다(§4-2에 404 매핑이 문장으로는 없었으나 §4-1과 동일 원칙 적용이
자명하므로 구현 시 그대로 따름 — 별도 설계 변경 아님). 이 항목은 재검토 결과 원 설계 그대로
유지.

**신규 발견(Critical)**: §4-2 응답 예시가 `contains_pii`·`doc_filename` 필드를
`RequirementRecord`가 이미 가진 것처럼 서술하지만, 실측(`backend/adapters/persistence/
requirement_store.py` 실제 `@dataclass` 필드 목록, grep `contains_pii` 전체 0건) 결과
**`RequirementRecord`에는 `contains_pii`도 `doc_filename`도 존재하지 않는다** —
`02_PHASE2_ORCHESTRATION_PREVIEW.md §1-2`가 설계한 `SourceLocation`(contains_pii 포함)이
`RequirementRecord`에 `doc_id`/`heading_path`/`char_start`/`char_end`까지만 부분 흡수되고
`contains_pii`는 흡수되지 않은 상태로 남아 있었다(구버전/미완성 데이터 갭 — 작업 지시가
확인하라고 한 "contains_pii 필드가 없을 때" 케이스가 실제로 존재).

**보강 결정**: `RequirementRecord`에 신규 필드를 추가하지 않는다(데이터 모델 변경은 이번
작업 지시 범위 밖 — "신규 비즈니스 로직 발명 금지", `ProjectDomainSnapshot` 외 청크도 건드리지
말라는 제약과 같은 축). 대신 API 레벨에서 `getattr(record, "contains_pii", False)`로 안전하게
기본값을 취한다 — 이는 "PII 게이트를 우회시키는 위험한 기본값"이 아니라 **현재 실제로
어디에도 PII 자동탐지가 구현돼 있지 않다는 사실을 정직하게 반영**한 것이다(지금 이 필드가
없다고 게이트가 새로 뚫리는 게 아니라, 애초에 이 필드가 시스템 어디에도 없었다). 이 한계를
코드 주석과 아래 §7 명세 표에 정직하게 남긴다(과장 금지, T98 AIP) — `doc_filename`도 동일하게
실제 존재하는 `DocumentStore` 파일 명명 규칙(`{doc_id}.md`)에서 그대로 유도해 신규 필드
없이 채운다.

### DRL-3. T99 AIOS 표준 envelope — 이미 충분, 보강 불필요

§4-1/§4-2 응답 예시 모두 `health_envelope()`과 동일한 `{ok, data, error, meta}` 4키 구조를
이미 따르고 있다(실측: `health.py` 재확인). 구현 시 공통 헬퍼(`envelope(ok, data, error)` 형태)
하나만 `requirements_api.py` 또는 `health.py`에 추가해 두 엔드포인트가 재사용하면 되고, 이는
신규 포맷 발명이 아니라 기존 뼈대의 함수화이므로 이 재검토에서 추가 보강 불필요.

### DRL 결론

Critical 2건(DRL-1 동시성, DRL-2 contains_pii/doc_filename 필드 갭) 모두 위 보강으로 해소.
구현 사이클(Part 2) 착수 조건 충족 — 진행.
