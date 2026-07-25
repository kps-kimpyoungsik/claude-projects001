---
role: DESIGN_PHASE3
scope: AI agent 작업 프롬프트 생성 + graphify 프로젝트 도메인 최신화 (사용자가 "제일 중요"라 명시한 항목)
status: 게이트 3 PASS — 사람용 실시간 알림(§3-5, NATS+WebSocket)을 2026-07-18 최신기술 보강 라운드로 추가 — 구현 미착수. §3-1/§3-2 프롬프트 조립 공식 보강 부분구현 완료(2026-07-19, dispatch_execution_planner.build_execution_prompts에 Requirement 원문+solution_stack 추가). §2 ProjectDomainSnapshot — 1번째 청크(프로젝트 구조) 구현 완료(2026-07-19, `backend/application/services/project_domain_snapshot_service.py` + `backend/adapters/persistence/project_domain_snapshot_store.py`). §2 환경 청크(2/5) 구현 완료(2026-07-19, `backend/adapters/extractors/environment_extractor.py` — infrastructure/ 하위 `.env.*.example`(키 이름만, 값 미추출)·`.md`(첫 heading)·`.conf.example`(존재+크기)만 단순 텍스트 스캔). §2 프로세스 청크(3/5) 구현 완료(2026-07-19, `backend/adapters/extractors/process_extractor.py` — `governance/workflows/*.md`(SERVER-EXECUTION_POLICY.md 등) 실측 확인 후 제목(첫 heading)+섹션 목록(heading 전체)만 단순 텍스트 스캔). **§2 ProjectDomainSnapshot 5/5 청크 전부 구현 완료(2026-07-19)** — 공통화(`commonization_extractor.py`, solution_stack 집계 — 순수 집계, 파일 스캔 아님)·기술(`technology_extractor.py`, `router.py`의 `FORMAT_STRATEGY`를 importlib로 실제 import해 읽음 + 공통화 집계 병합) 신규 구현, `build_project_domain_snapshot()`에 `requirements`/`tasks`/`router_module_path` 선택적 파라미터 추가(하위호환). 남은 이월 항목: 이력(diff) 관리(§2-2)뿐.
updated: 2026-07-19
---

# 3차 설계 — AI Agent 프롬프트 생성 + graphify 프로젝트 도메인 최신화

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 이전: [`02_PHASE2_ORCHESTRATION_PREVIEW.md`](./02_PHASE2_ORCHESTRATION_PREVIEW.md)

> **전제**: 최초 초안 시점엔 1·2차 게이트의 이월 항목(계층코드 재검증·철회사유·행위자
> 기록·문서 접근제어)이 미결이었으나, 2026-07-18 보강 라운드에서 `01_PHASE1_DATA_MODEL.md`·
> `02_PHASE2_ORCHESTRATION_PREVIEW.md`·`04_PHASE0_PROJECT_REGISTRATION.md`로 전부 해소됐다
> (§5 인덱스 표 참조). 이 문서는 그 해소된 확정값을 전제로 이어서 설계한다.

## §1. 사용자가 명시한 "가장 중요한 기능"

> "제일 중요한 기능이 실측된 현재 만들어진 프로젝트 구조, 기능, 환경, 프로세스, 공통화, 기술
> 입니다. 이런 중요성 높은 것은 graphify에 저장해서 해당 프로젝트 특정 도메인 정보를 최신화
> 관리 될 수 있도록 해주세요."

이걸 최우선으로 놓고 설계한다 — 나머지(AI agent 프롬프트 생성)는 이 위에서 동작한다.

## §2. graphify 프로젝트 도메인 최신화 설계

### §2-1. 현재 상태(실측) — 이미 있는 것

`graphify_engine/pipeline.py`의 `merge_into_graph()`가 이미 노드/엣지를 `.graphify-out/
graph.json`에 병합하는 기능을 갖고 있다(Phase 3 스캐폴딩, 검증됨). 지금까지는 이걸 요구사항
(Requirement 노드)에만 썼다. 이번 요청은 그 대상을 **프로젝트 자체의 실측 정보**로 넓히는
것이다:

| 실측 대상 (사용자 명시) | 어떻게 실측하는가 (기존 자산 재사용) |
|---|---|
| 프로젝트 구조 | `graphify_engine/extractors/ast_extractor.py`(이미 자기 자신 파싱 검증됨) — 파일/함수/모듈 구조를 Function/Variable 노드로 |
| 기능 | Requirement↔Task IMPLEMENTS 엣지(이미 구현됨, `requirements.py`) — "이 기능이 실제 뭘 구현했는지"는 이미 추적 가능 |
| 환경 | `infrastructure/topology.md`·`infrastructure/database/schema.py` 등 설정 파일을 파싱해 Policy/노드로 등록(신규 extractor 필요 — §2-2) |
| 프로세스 | `governance/workflows/*.md`(예: SERVER-EXECUTION_POLICY.md) — 정책 문서를 Policy 노드로(이미 `parity_check()`가 정책 위배 검증 기능을 가짐, 현재 "정책 없음—통과" 상태였던 것을 실제로 채우는 작업) |
| 공통화 | 1차 설계의 `solution_stack` 태그(프레임워크 사용 현황) — 어떤 프레임워크가 몇 개 요구사항/태스크에 걸쳐 재사용되는지 그래프로 집계 |
| 기술(스택) | `ingestion/router.py`의 `FORMAT_STRATEGY` 처럼 이미 있는 기술 목록 + 1차 `solution_stack` 태그를 합쳐 "이 프로젝트가 실제 쓰는 기술 스택 전체 목록"을 그래프 노드로 |

### §2-2. 신규 — `ProjectDomainSnapshot` 추출기 (설계만, 구현은 승인 후)

```python
# graphify_engine/project_domain_snapshot.py (3차 승인 후 구현 예정 스텁 설계)
def build_project_domain_snapshot(project_root: Path) -> dict:
    """AST(구조) + Policy 문서(프로세스) + solution_stack 집계(공통화·기술)를 한 스냅샷으로.

    "최신화 관리"의 의미: 이 함수를 실행할 때마다 그 시점의 실측값으로 그래프를 갱신한다.
    이전 스냅샷과 diff해서 "무엇이 바뀌었는지"도 함께 남긴다(변경 이력 — T39 CRZ 잔재 관리와
    같은 원칙, 덮어쓰기만 하고 이력을 버리지 않는다).
    """
```

**최신화 트리거(2026-07-18 보강 라운드 — 미결 #5 해소, 하이브리드로 확정)**:
workbase `_design/DB_SCHEMA.md`의 "API 이력 우선 + localStorage 폴백" 이중 경로 원칙을
그대로 벤치마킹한다 — **자동 경로 하나만 믿지 않고, 항상 수동 강제 재생성 명령을 폴백으로
둔다**:

1. **자동(주경로)**: Task의 `lifecycle_status`가 `IMPLEMENTED`/`VERIFIED`로 바뀌는 시점에
   그 Task의 `impact_scope` 파일만 부분 재추출(`ast_extractor.py`를 영향받은 파일에만
   재실행 — 전체 재빌드 아님, T38 PAP 대용량 회피 원칙 재사용) + 그 Task의 `source_req_ids`
   Requirement 노드 갱신. 트리거 지점은 기존 `task_manager.TaskStore.create_or_update()`
   내부(이미 있는 함수에 후처리 훅만 추가, 신규 이벤트 시스템 발명 없음).
2. **수동(폴백)**: `build_project_domain_snapshot(project_root, full=True)` — 자동 경로가
   놓친 부분(§2-3의 4-2 프로세스·환경 문서 등 Task와 직접 연결 안 되는 실측 대상)까지
   전체 재스캔. 사람이 `/aegis-oneshot-plan`·`/autobuild` 완료 시점이나 세션 시작 시 수동
   실행 가능.
3. 순수 주기적(cron 유사) 방식은 **채택하지 않음** — 이 프로젝트는 상시 실행 서비스가
   아니라 세션 단위로 LLM이 작업하는 구조라, "다음 세션 시작 시 자동 확인"(위 2번의 변형)이
   진짜 주기 스케줄러보다 이 프로젝트 실행 모델에 더 맞는다(과잉설계 회피, 헌법 §4 "AEGIS류
   인프라를 도구로만" 판정에서도 `aegis-growth-schedule`처럼 상시 서비스가 필요한 패턴은
   이 프로젝트 목적에 비해 무겁다고 판단).

**미결 #5 — 해소 완료**.

### §2-3. 헌법 §4 드리프트 체크리스트 자가 판정 (이 설계 자체에 적용)

00_PROJECT_CONSTITUTION.md §4에 따라 이 기능 자체를 점검한다:

1. "요구사항 문서 → 구조화된 요구사항 항목" 경로에 기여하는가? → **부분 YES**: 프로젝트
   실측 스냅샷은 요구사항이 아니라 "이 프로젝트가 지금 어떤 상태인지"를 담아, Phase 4 AI
   agent가 태스크를 만들 때 "이미 있는 구조를 다시 만들지 않도록" 근거로 쓰인다 — 간접 기여.
2. 영역/분야별 번호로 추적 가능한가? → 스냅샷 자체는 REQ 번호 대상이 아니라 **Policy/구조
   노드**로 그래프에 남는다(별도 트랙, 타당함 — 모든 산출물이 REQ일 필요는 없음).
3. "AI가 수행할 태스크" 또는 "그 관리 정보"인가? → YES — 태스크 생성 시 참조하는 **컨텍스트
   정보**.
4. 범용 AEGIS 인프라를 도구로만 쓰는가? → **주의 필요**: graphify 자체가 AEGIS 범용 자산이다.
   이 설계는 "이 프로젝트 전용 도메인 그래프"(`.graphify-out/graph.json`, 프로젝트 로컬)만
   다루고 AEGIS 전역 그래프에는 쓰지 않는다 — §1 헌법 취지에 맞게 **도구로만** 사용.

**판정: 통과** — 최초 초안 시점엔 §2-2(최신화 트리거 방식)가 미결이었으나, 위 §2-2 본문에서
이미 자동+수동 이중 경로로 확정했으므로 더 이상 AskUserQuestion 대상이 아니다.

## §3. AI Agent 작업 프롬프트 생성 파이프라인

### §3-1. 목표

"설계서 기반 AI agent가 작업수행을 위한 프롬프트를 만들면서 프로젝트를 수행"(사용자 원 요청
최종 목표) — 이미 있는 `orchestrator/task_manager.py`의 `Task` 데이터클래스가 이 프롬프트의
**입력 재료**가 된다. 신규 생성기는 다음을 합성한다:

```
프롬프트 = Task(title, description, acceptance_criteria)
         + source_req_ids로 연결된 Requirement 전문(원문 발췌, source_location 포함)
         + solution_stack(이 태스크가 어떤 프레임워크 기반이어야 하는지 — 1차 설계 §2-4)
         + §2 ProjectDomainSnapshot에서 관련 부분만 발췌(이미 있는 구조를 중복 재구현하지 않도록)
         + area_code/layer_code (§PCM-6 DAA 분배 힌트 — 어느 agent가 맡을지)
```

### §3-2. 기존 자산 재사용 지점

- 프롬프트 조립 자체는 신규 로직이지만, **입력 데이터는 전부 이미 설계된 필드**(1·2차 설계)를
  재사용 — 새 데이터 모델 발명 없음
- 프롬프트를 실제 agent에 태우는 방식은 이 세션(Claude Code)의 `Agent`/`Workflow` 툴을 그대로
  씀(신규 오케스트레이션 엔진 발명 금지 — 00_PROJECT_CONSTITUTION.md §1 "AEGIS류 인프라는
  도구로만" 원칙)

### §3-3. `buildProjectContextBlock` 벤치마킹 — 프롬프트 자동 컨텍스트 주입 (보강)

`plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md` §4에서 확인한 workbase
`project-context.js:591 buildProjectContextBlock(cfg)` 패턴을 그대로 이식한다. workbase는
마법사 설정(cfg)을 요약해 모든 프롬프트 앞에 붙이고, 기존 시스템 컨텍스트 MD가 있으면
"작업 사전 분석 지시" 블록까지 강제 삽입한다 — 이 프로젝트의 프롬프트 생성기도 동일 구조:

```python
def build_task_prompt(task: Task, requirements: list[RequirementRecord],
                       snapshot: dict, events: list[dict]) -> str:
    """workbase buildProjectContextBlock과 동일한 구조 — 컨텍스트 블록을 프롬프트 앞에 강제 삽입.

    1. ■ 프로젝트 컨텍스트 블록 (0차 마법사 §2에서 확정한 분야·프레임워크·접근정책 요약)
    2. ■ 이 태스크가 근거로 삼는 요구사항 원문 발췌(source_location 포함, 2차 설계 §1)
    3. ■ 기존 프로젝트 실측 컨텍스트(§2 ProjectDomainSnapshot에서 이 Task의 impact_scope와
       겹치는 부분만 발췌 — workbase의 "기존 시스템 컨텍스트 MD 주입, 첨부 시에만"과 동일 원칙)
    4. ■ 작업 사전 분석 지시(workbase 패턴 그대로: "아래 순서를 작업 시작 전에 반드시 수행")
    5. ■ 요구사항 변경 재확인 지시 (§3-4, 신규 — Critical 미결 #6 해소)
    """
```

### §3-4. 요구사항 상시 변경과 진행 중 태스크의 정합 (Critical 미결 #6 — 해소 확정)

사용자 요청: "프로젝트 하나에는 요구사항을 수시로 추가, 변경, 삭제 가능하도록". 게이트3에서
발견한 Critical 공백("진행 중 AI agent에게 요구사항 변경을 실시간으로 알릴 경로가 없음")을
**실시간 푸시가 아니라 재확인(reconcile) 방식**으로 해소한다 — 새 웹소켓/SSE 인프라를
발명하지 않고, 이 세션(Claude Code) 자체가 이미 쓰는 원칙(T101 SOSC "행동 전 재확인")과
workbase의 "API 우선 폴백" 이중 경로 사고를 그대로 적용:

```
plans/_plan_runtime/requirement_change_events.jsonl   ← 신규 append-only 이벤트 로그
  {req_id, affected_task_ids, from_status, to_status, actor, ts}
```

1. **기록 시점**: `RequirementStore.set_status()`(1차 §2-3-A)가 상태를 바꿀 때마다, 그
   REQ를 `source_req_ids`로 참조하는 모든 Task ID를 `task_manager`에서 역조회해 이 이벤트
   로그에 append(신규 저장방식 발명 없음 — `ingestion/error_log.py`의 JSONL append 패턴과
   완전히 동일 구조, CRZ).
2. **소비 시점(§3-3의 5번 블록)**: `build_task_prompt()`가 프롬프트를 만들 때마다
   `requirement_change_events.jsonl`에서 이 Task의 `source_req_ids`와 관련된, 아직 확인 안 된
   이벤트가 있는지 먼저 조회 → 있으면 프롬프트 맨 앞에 **"⚠ 요구사항 변경 감지"** 블록을
   강제 삽입("이 태스크의 근거 REQ-BIZ-SEC-002가 WITHDRAWN 되었다 — 계속 진행 전 재확인
   필요").
3. **한계를 정직하게 명시**: 이 방식은 "다음 프롬프트가 생성되는 시점"에만 통지되는
   **풀(pull) 기반**이다 — 이미 실행 중인 agent 프로세스 안에서 즉시 인터럽트되는 진짜
   실시간(푸시)은 아니다. 하지만 이 프로젝트의 실행 모델(LLM 세션이 Task 단위로 프롬프트를
   받아 작업하는 구조, Phase 4 본체)에서는 "다음 Task 착수 시점 재확인"이 곧 실질적인 통지
   시점과 같다 — 진짜 실시간 인터럽트가 필요한 것은 "이미 시작된 단일 Task 실행 도중"인데,
   그 경우는 Task 자체를 잘게 쪼개는 것(§PCM-6 DAA의 난이도 분배 원칙)으로 리스크를 줄이는
   것이 인프라를 새로 만드는 것보다 이 프로젝트 규모에 맞다.

**미결 #6(Critical) — 해소 완료**(풀 기반 재확인으로, 새 실시간 인프라 발명 없이).

### §3-5. 실시간 웹소켓 알림 — 이중화 환경 팬아웃 (2026-07-18 최신기술 보강, 사용자 명시 지시)

> **범위 정정**: §3-4는 유지한다 — **AI agent(LLM 세션)에게는 여전히 풀 기반이 유일한
> 경로**다(구조적 한계: LLM은 프롬프트를 "받는" 시점에만 정보를 인지하지, 소켓으로 push되는
> 이벤트를 실행 도중 자발적으로 인지할 수 없다 — 이건 인프라를 더 넣어도 안 바뀌는 사실이라
> 과장하지 않는다, T98 AIP). 이번 보강은 **사람이 보는 화면**(`agent-view/requirements.html`,
> 2차 설계의 미리보기 모달)에 진짜 실시간(push)을 추가하는 것 — §3-4(pull, agent용)와
> §3-5(push, 사람용)는 **서로 다른 소비자를 위한 병행 경로**이지 하나가 다른 하나를 대체하지
> 않는다.

**최신기술 조사(WebSearch, 2025-2026 자료 기준) 요약** — 근거: Ably·oneuptime.com·
websocket.org·python-socketio 공식문서·HAProxy 공식 블로그:
- **팬아웃 표준 패턴**: 각 서버 노드는 자신에게 붙은 WS 연결만 갖고, 이벤트 발행은 공유
  브로커(Redis Pub/Sub·NATS·Kafka)로 발행 → 모든 노드가 구독해 자기 로컬 클라이언트에게만
  중계. 노드 간 직접 연결 불필요(origin 노드와 delivery 노드 완전 분리).
- **LB 처리**: WS는 업그레이드된 장수명 TCP라 완전한 무상태는 불가 — `least_conn`(라운드로빈
  대신, 연결이 짧지 않으므로) + 확장된 tunnel timeout + `Connection: Upgrade` 헤더 통과가
  표준. 브로커 팬아웃을 쓰면 굳이 sticky session이 없어도 "재연결이 다른 노드에 붙어도
  안전"(상태가 노드 로컬이 아니므로).
- **Python 구현체**: `python-socketio`의 `AsyncRedisManager`가 이 팬아웃을 몇 줄 설정으로
  제공(서버 프로세스마다 같은 Redis를 가리키면 자동 중계) — 직접 릴레이 코드를 짤 필요 없음.

**이 프로젝트에 대한 확정 설계**:

| 구성요소 | 선택 | 근거 |
|---|---|---|
| 브로커(백플레인) | **NATS**(제안 확정 — 단일 경량 바이너리, 이 프로젝트에 아직 Redis가 없어 "필요한 만큼만" 원칙에 더 맞음) | Kafka/RabbitMQ는 2노드 내부도구엔 과함(조사결과 4번 항목). Redis를 캐시·벡터검색 용도로 이미 도입하기로 하면 그때 Redis Pub/Sub으로 교체 가능(백플레인 교체는 Port/Adapter 경계라 가역, T102 NTM 원칙과 정합) |
| WAS 노드별 WS 엔드포인트 | `WAS-1(8790)`·`WAS-2(8791)` 각각 `/ws/requirements` 라우트(FastAPI+`websockets`, `infrastructure/topology.md`에 이미 있는 "Python/FastAPI(예정)" 그대로 재사용) | 신규 프레임워크 도입 없음 |
| 발행 지점 | `RequirementStore.set_status()`(1차 §2-3-A)가 상태 변경 시 **이중 기록**: ①기존 JSONL 감사로그(§3-4, 그대로 유지) + ②NATS subject `req.status_changed`로 동일 payload 발행(신규) | JSONL은 "확인 안 된 이벤트가 있는가"(pull) 그대로 담당, NATS는 "지금 보고 있는 화면 즉시 갱신"(push) 담당 — 이중 경로가 서로의 폴백(한쪽 죽어도 다른 쪽으로 결국 확인됨) |
| LB 설정(topology.md §미결 사항 갱신) | `least_conn` + WS tunnel timeout 연장 + Upgrade 헤더 통과. 브로커 팬아웃 덕에 **sticky session 불필요** | 이전 topology.md "로드밸런서 선택 미결"에 첫 구체 권고 제공 |
| 클라이언트(브라우저) | 네이티브 `WebSocket` API + 지수백오프 재연결 + 재연결 시 재구독 | 신규 클라이언트 라이브러리 의존 없음(vanilla JS 원칙 유지, 기존 requirements.html과 동일 기조) |

**신규 의존성 명시(T98 AIP 정직 표기)**: 이 설계는 이 프로젝트에 **처음으로 NATS라는 신규
인프라 의존성**을 도입한다 — 지금까지는 Python stdlib + JSON 파일 저장(무의존성)이었다.
이건 사용자가 명시적으로 "이중화 환경 웹소켓 실시간 알림"을 지시했기 때문에 받아들이는
트레이드오프이며, 이전 라운드의 "인프라 발명 없이" 원칙과 모순되지 않는다 — 그때는 필요성이
낮다고 **판단**해서 안 넣었고, 이번엔 사용자가 필요성을 **명시**했으므로 KH-2026-0652
"직접 지시 우선" 원칙대로 즉시 반영한다.

**§3-5 품질검토 (경량 — 전면 게이트 아닌 보강 검토)**:
- **개발**: `python-socketio` 도입 시 릴레이 코드 직접 작성 불필요, 구현 난이도 낮음(D2)
- **운영**: NATS 단일 바이너리 → 이중화 노드 2대와 별개로 NATS 자체도 최소 이중화(클러스터
  모드) 필요 여부는 **미결**(NATS 단일 인스턴스 장애 시 실시간 알림만 끊기고 §3-4 폴백은
  살아있음 — 단일장애점이어도 "완전 통지 불가"로 이어지지 않음을 확인, 리스크 낮음)
- **정보안정성**: WS payload에 원문 발췌를 담지 않고 req_id/status만 전송(PII 노출 표면
  최소화 — 화면은 그 req_id로 다시 REST/fetch해서 상세를 가져오는 구조 권장)
- **헌법정합**: 00_PROJECT_CONSTITUTION.md §4 판정 — "AI 태스크 관리"라는 목적에 직접
  기여하진 않지만 "그 관리 정보를 실시간으로 보여주는" 도구적 확장이라 §4 통과
- **검증**: 구현 후 두 브라우저 탭을 WAS-1/WAS-2 각각에 붙여 한쪽에서 상태변경 시 반대쪽
  탭도 즉시 갱신되는지가 이 설계의 최소 스모크 테스트(팬아웃 자체의 검증)

## §4. 품질검토 게이트 3 — 최종 비판적 다관점 검토 (E2E 워크스루)

### 시나리오: "보안 요구사항 문서가 새로 첨부되고, 기존 SEC 태스크가 진행 중이던 상황"

1. 사용자가 신규 사업계획서(BIZ)를 첨부 → 청킹 → 분류기가 `doc_type=BIZ, area=SEC,
   layer=SYS`로 자동분류(1차) → `lifecycle_status=RECEIVED`
2. 미리보기 화면(2차)에서 사람이 확인 후 `ACCEPTED`로 전이 → `REQ-BIZ-SEC-004` 확정
3. 이미 `REQ-BIZ-SEC-002`를 참조하는 Task가 `IN_PROGRESS`인 상태에서, 사람이 원본 문서
   재검토 중 `REQ-BIZ-SEC-002`를 `WITHDRAWN`으로 철회(요구사항이 바뀜)
4. → **2026-07-18 보강 라운드에서 해소**: §3-4의 `requirement_change_events.jsonl` +
   `build_task_prompt()`의 "⚠ 요구사항 변경 감지" 블록이 이 시나리오를 처리한다 — 다음에
   그 Task를 위한 프롬프트가 생성되는 시점(재시작·재확인 시점)에 반드시 이 경고가 먼저
   보이도록 설계됨. 실시간 인터럽트가 아니라 풀 기반이라는 한계는 §3-4에 정직하게 남겨둠.

| 관점 | 검토 결과 |
|---|---|
| 개발 | 프롬프트 생성 자체는 기존 필드 조합이라 구현 난이도 낮음. 이벤트 로그 append도 `error_log.py`와 동일 패턴이라 신규 구현 부담 낮음 |
| 설계 | §3-4로 Critical 해소 — 단, "이미 실행 중인 단일 Task 도중" 실시간 인터럽트는 여전히 안 됨(설계상 의도적 한계, §3-4 3번에 근거 명시) |
| 운영 | §2-2에서 "자동(부분 재추출) + 수동(전체 재스캔) 이중 경로"로 확정 — 운영 부담이 워크베이스의 "API 우선+localStorage 폴백"과 동일한 이중화 구조라 예측 가능 |
| 정보안정성 | `04_PHASE0_PROJECT_REGISTRATION.md` §3에서 미리보기 단계의 PII 게이트는 이미 해소됐으나, 프롬프트 조립 시점(§3-3의 2번 블록)에 그 발췌가 실제로 PII 게이트를 거쳤는지 재확인하는 로직은 **아직 설계에 반영되지 않음** — §5 #7로 명시적 이월(추정으로 "반영됨"이라 쓰지 않음) |
| 헌법정합 | §2-3에서 자가판정 통과 — AEGIS 범용 인프라(graphify)를 도구로만 쓰는 원칙 유지 확인됨. §2-2의 "주기적 스케줄러 미채택" 판단도 같은 원칙 적용 |
| 검증 | E2E 시나리오 워크스루 자체가 검증 방법 — 실제 구현 후 이 시나리오를 스모크 테스트로 그대로 재현 권장(이번 라운드에도 실행 코드는 없음 — 문서 검토 수준) |
| 책임 | 1차 §2-3-A `status_history(actor, reason)`가 "누가 철회했는지"를 남기고, §3-4 이벤트 로그가 "그 철회가 관련 Task 프롬프트에 실제로 노출됐는지"까지 남겨 책임 추적성 공백이 닫힘 |

**게이트 3 결론(2026-07-18 보강 라운드 갱신)**: **PASS** — Critical 1건 포함 전체 미결
해소. 단, §3-3/§3-4 어디에도 아직 **실행 코드는 없다**(설계 문서로만 확정) — 실제
`build_task_prompt()`·이벤트 append 로직·PII 재확인 로직 구현은 사용자가 구현 착수를
승인한 뒤 별도 턴에서 진행.

## §5. 이월 미결 총괄 — 2026-07-18 보강 라운드 해소 현황

지난 라운드에서 이월했던 6건 전부 이번 라운드에서 설계 확정으로 해소했다(추정이 아니라
구체적 메커니즘·자료구조·코드 시그니처까지 명시). 아래는 그 총괄과, 각 해소가 어느 문서
어느 절에 있는지의 인덱스다:

| # | 항목 | 해소 방식 요약 | 해소 위치 |
|---|---|---|---|
| 1 | `layer_code` 코드값 | `SEC`와 문자열 자체가 겹치지 않도록 `SECU`로 확정 + UI 축 라벨 병기 규칙 | `01_PHASE1_DATA_MODEL.md` §2-1 |
| 2 | REQ 철회 사유 | `status_history`(통합 감사로그)에 `reason` 필드로 흡수, WITHDRAWN/REJECTED 시 필수 검증 | `01_PHASE1_DATA_MODEL.md` §2-3-A |
| 3 | 상태변경 행위자 | 위와 동일한 `status_history`의 `actor` 필드로 통합 해소(별도 필드 아님, CRZ) | `01_PHASE1_DATA_MODEL.md` §2-3-A, `02_PHASE2...md` §2-3 |
| 4 | 문서 접근제어(PII) | workbase `DATA_TYPES_DEF.pii` 벤치마킹 → `contains_pii` 플래그 + 클릭스루 게이트 + 접근로그 | `04_PHASE0_PROJECT_REGISTRATION.md` §3, `02_PHASE2...md` §2-4 |
| 5 | 그래프 최신화 트리거 | 자동(부분 재추출, Task 완료 시 후처리 훅) + 수동(전체 재스캔) 이중 경로, 순수 주기 스케줄러는 미채택 | `03_PHASE3...md`(본 문서) §2-2 |
| 6 | **[Critical]** 진행 중 agent 변경통지 | AI agent용은 풀 기반(`requirement_change_events.jsonl` + 프롬프트 재확인 블록) 그대로 유지 — LLM 세션의 구조적 한계로 실시간 인터럽트는 여전히 불가. **사람이 보는 화면용은 2026-07-18 최신기술 보강으로 NATS 백플레인 + WebSocket 실시간 push 추가**(§3-5, 신규 NATS 의존성 도입) | `03_PHASE3...md`(본 문서) §3-4(agent용 pull) · §3-5(사람용 push, 신규) |

**이번 라운드에서 새로 발견된 후속 확인 사항(신규, 다음 라운드나 구현 착수 시 재확인)**:

| # | 항목 | 발생 근거 |
|---|---|---|
| 7 | §3-3 컨텍스트 블록 생성 시 원문 발췌가 PII 게이트를 통과한 발췌인지 재확인하는 로직 | §4 게이트3 "정보안정성" 재검토에서 신규 발견 |
| 8 | 0차 마법사가 SQLite 대신 JSON 스토어를 쓰기로 확정했는데, 이게 향후 다중 사용자 동시 편집(파일 락 경합)까지 견디는지는 미검증 | `04_PHASE0...md` §6 "검증" 관점 검토에서 신규 발견, 현재는 단일 세션·순차 작업 전제라 당장은 문제 아님(정직 기록) |

이 두 건은 Critical이 아니라 **구현 단계에서 자연히 확인될 성격**이라 별도 AskUserQuestion
없이 구현 착수 시 실측으로 확인하면 된다(0-N 원칙 — 근본해결로 채워지는 경우이지 사용자
재질의가 필요한 경우가 아님).
