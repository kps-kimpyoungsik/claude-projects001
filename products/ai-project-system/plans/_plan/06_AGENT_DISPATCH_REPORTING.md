---
role: DESIGN_PHASE3_EXT
scope: 요구사항→전문가 agent 배차 + 우선순위 오케스트레이션 + 작업상태·완료보고
status: 2026-07-22 재검토 정정 — "설계 확정 — 구현은 별도 턴(사용자 승인 후)"는 stale —
  §1~§9(agent_dispatch_resolver·task_dispatch_service·completion_report_service·
  agent_role_usage_log)는 이미 2026-07-19 구현·사용자 승인·`plans/_done/
  agent-dispatch-impl-2026-07-19/`로 L4 DONE 확정 완료(실측 확인). **§10(요구사항별 작업상태+배정agent
  노출, 설계만) 추가(2026-07-20)** — 사용자 지적("요구사항별 작업 진행상태 확인 불가·배정
  agent 안 보임") 반영, `RequirementRecord.assigned_agent_command`/`work_status` 신규 필드
  설계 + API·UI 노출 설계. **§10 코드 구현 완료(2026-07-20)**: `RequirementRecord`에
  `assigned_agent_command`/`work_status`/`work_status_updated_at` 필드 추가 +
  `RequirementStore.set_work_status()` + `task_dispatch_service.sync_requirement_work_status()`
  (§10-2 집계 우선순위 BLOCKED>IN_PROGRESS>DISPATCHED>DONE>NOT_DISPATCHED 그대로 구현) +
  `GET /requirements`(목록)·`GET /requirements/{req_id}`(단건) API 신설(설계 시점엔 두 API가
  존재한다고 가정했으나 실측 결과 없었음 — 이번 구현에서 신설, 하위호환 유지) +
  `requirements.html`에 "배정 agent"·"작업상태" 컬럼 추가(셸 구조 무변경). 테스트 15건 추가,
  전체 138 pass, uvicorn 실기동 curl 스모크 확인(GET 목록/단건·집계 로직 3분기 검증).
updated: 2026-07-20
---

# 요구사항 → 전문가 Agent 배차 + 오케스트레이션 + 완료보고 설계

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 관련: [`03_PHASE3_AGENT_GRAPHIFY.md`](./03_PHASE3_AGENT_GRAPHIFY.md)(§3 AI Agent 프롬프트 생성 파이프라인의 구체화)

> **Stage 0 확정(AskUserQuestion, 2026-07-19)**: ①전문가 agent는 **AEGIS 전역 agent를 그대로
> 재사용**(신규 agent 정의 안 함 — 00_PROJECT_CONSTITUTION.md §1 "AEGIS는 도구로만" 원칙과
> 정합) ②이번 턴 산출물 = **설계서만**, 실제 코드/실행은 사용자 승인 후 별도 턴.

## §1. 왜 필요한가 (사용자 원 요청)

"요구사항 하나하나 또는 그룹으로 분야별·영역별 전문가 agent가 등록되어 있어야 하고, 우선순위
오케스트레이션과 작업상태 확인이 되며, 완료 시 요구사항별 상태 업데이트 + 어느 파일이 어떤
내용으로 수정됐는지 보고서가 나와야 한다." — 이미 있는 조각(1차 데이터모델·Phase 4 Task
엔티티)을 실제로 연결하는 마지막 고리다.

## §2. 이미 있는 것 (실측, 재사용 대상)

| 필요 기능 | 이미 구현된 자산 |
|---|---|
| 요구사항 항목 + 영역코드 | `backend/domain/requirements/codes.py`(DOMAIN_CODES) + `backend/adapters/persistence/requirement_store.py`(RequirementRecord) |
| 태스크 + 충돌탐지 | `backend/domain/entities/task.py`(Task) + `backend/domain/requirements/conflict_detection.py`(detect_area_conflicts, §PCM 프로젝트 로컬 적용) |
| 태스크 영속화 | `backend/adapters/persistence/task_store.py`(TaskStore.create_or_update — 이미 `revision` 증가·`updated_at` 갱신 보유) |
| AEGIS 지식·스킬 검색 | `/recall`(graphify·hmrecall·error_kb·acn 4채널 통합 조회, 이미 이 세션이 매 턴 쓰고 있음) |
| AEGIS 전문가 agent | `aegis-dev000`·`aegis-architect000`·`aegis-design000`·`aegis-infra000`·`aegis-security000`·`aegis-troubleshooting000`·`aegis-secretary000`(governance/agents 또는 AEGIS 전역 등록, `/aegis-dev` 등 슬래시 명령으로 실행) |

## §3. 도메인코드 → AEGIS 전문가 agent 실시간 조회 (정적 매핑표 폐기, 2026-07-19 재설계)

> **사용자 명시 거부(2026-07-19)**: "agent 맵핑표가 필요한게 아니고 aegis 시스템을통해서
> 실시간 추가되거나 변경되는 정보를 동기화 할수 있도록 해줘 aegis 시스템에서도 agents 역할
> 목록 검색 할수 있도록 해서 제공 가능 구성해줘" — 아래 이전 버전의 10줄 하드코딩 표는
> **폐기**한다. AEGIS 쪽에 전문가 agent가 추가·변경돼도 이 프로젝트가 파일을 손으로 고칠
> 필요가 없어야 한다는 것이 핵심 요구다.

### §3-1. 실측 확인 (이 세션에서 직접 호출, 추정 아님)

`mcp__aegis__list_tools`/`search_tools`/`get_tool_spec`을 먼저 호출해봤으나, 이 경로는
AEGIS **Vault 도구**(cf_worker·jsonl_async·kakao_sender·mail_sender·monitor_claude·
scheduler·token_usage_analyzer·tunnel_manager 8종)만 인덱싱한다 — 전문가 agent(`/aegis-dev`
등)는 여기 없다. `get_tool_spec("aegis-security")`도 `NOT_FOUND`로 실측 확인.

전문가 agent 7종(`aegis-architect000`·`aegis-design000`·`aegis-dev000`·`aegis-infra000`·
`aegis-secretary000`·`aegis-security000`·`aegis-troubleshooting000`, 실제 디렉터리
`D:\aegis\agents\aegis-*000\`로 존재 확인)은 대신 `mcp__aegis__search_all`에서
**`type: "command"`**로 잡힌다 — 소스는 `D:\aegis\base\05_commands\slash\aegis-{name}.md`
이고, 각 파일 frontmatter의 **`trigger:` 키워드 목록**이 실제 매칭 근거다. 예:

```
aegis-security.md → trigger: 보안·위협 모델링·threat model·보안 감사·security audit·취약점·...
aegis-infra.md     → trigger: 인프라 작업·서비스 운영·배포 파이프라인·관측·헬스체크·...
aegis-design.md    → trigger: 디자인 작업·UI/UX 설계·화면 설계·퍼블리싱·HTML/CSS·...
aegis-dev.md       → trigger: 개발 작업·구현·스캐폴딩·빌드·리팩터링·디버깅·아키텍처 구성·...
aegis-architect.md → trigger: 아키텍처 설계·시스템 설계도·ADR·기술 스택 선택·...
aegis-troubleshooting.md → trigger: 트러블슈팅·오류해결·장애대응·왜 안되는지·회귀원인·...
aegis-secretary.md → trigger: 비서·secretary·AEGIS 설명·시스템 가이드·최신 정보 검색·리서치·...
```

이 `trigger:` 목록은 **AEGIS 쪽 파일**이라 새 전문가 agent가 추가되거나 트리거가 바뀌면
이 프로젝트는 아무것도 하지 않아도 다음 조회부터 즉시 반영된다 — 이것이 "실시간 동기화"의
실제 메커니즘이다(신규 동기화 데몬 없음, CRZ).

**실측 정확도(중요 — 낙관하지 않는다)**: `search_all`은 통합검색이라 헌법·메모리·정책·
스킬·워크스페이스 파일도 함께 반환하고, 노이즈 항목 점수(0.54~0.61)가 정답 command 항목
점수(0.56~0.60)와 겹친다. 예컨대 "SEC 보안 영역 담당 agent" 질의는 `aegis-security`
(0.56)를 7위로, "DB 데이터베이스 스키마 이중화 담당 agent"·"LLM 연계 python 개발 담당
agent"·"RPT 보고서 산출물 담당 agent" 질의는 **상위 6건 안에 해당 command가 전혀 나타나지
않았다**(pptx-builder 스킬 문서 등 무관 항목이 상위 차지). 반면 "인프라 게이트웨이 이중화
부하분산 전문가"(→ `aegis-infra` 1위, 0.56)나 "WEB 프론트엔드 UI 설계 담당 agent"
(→ `aegis-design` 3위, 0.60)는 잘 맞았다. **결론: 영역코드 문자열(GRID/DB/LLM/RPT 등)을
그대로 질의에 넣으면 신뢰할 수 없고, 00_PROJECT_CONSTITUTION.md §5 표의 한국어 설명(예:
"이중화(부하분산/이중화)")을 질의에 녹여야 명중률이 오른다.**

### §3-2. 배차 시점 실시간 조회 함수 (설계만 — `backend/application/services/agent_dispatch_resolver.py`, 신규 파일 예정)

```python
# 설계만 — 구현은 별도 턴. 신규 AEGIS 인프라 발명 없음, 기존 search_all 재사용만.
from dataclasses import dataclass

DOMAIN_QUERY_HINT = {
    # §5 표의 "영역 설명" 그대로 사용 — 코드 문자열 단독 질의 금지(§3-1 실측 근거)
    "WEB": "프론트엔드 웹 UI 화면 설계 구현",
    "WAS": "애플리케이션 서버 백엔드 로직 구현",
    "DB": "데이터베이스 스키마 쿼리 구현",
    "SEC": "암호화 솔루션 SSL 보안",
    "GRID": "그리드 부하분산 이중화 인프라",
    "A11Y": "웹접근성 UI 디자인",
    "VULN": "소스코드 취약성 점검 보안 감사",
    "GW": "중계서버 게이트웨이 인프라",
    "LLM": "LLM 연계 python 개발 구현",
    "RPT": "보고서 산출물 비서 작성",
}

@dataclass
class AgentResolution:
    domain_code: str
    agent_command: str | None   # 예: "/aegis-security" — None이면 미확정
    source: str                  # "search_all" | "fallback_default" | "cache"
    score: float | None
    resolved_at: str


def resolve_agent_for_domain(domain_code: str) -> AgentResolution:
    """배차 시점마다 호출 — 정적 테이블 참조 금지.

    1) 캐시 확인(§3-3 TTL) → 있으면 source="cache"로 즉시 반환
    2) mcp__aegis__search_all(query=DOMAIN_QUERY_HINT[domain_code], limit=8) 호출
    3) 결과 중 path가 `05_commands/slash/aegis-*.md`이고 type == "command"인 항목만 필터
       (헌법·메모리·스킬 노이즈 제거 — §3-1에서 실측된 유일한 결정적 필터)
    4) 필터 결과가 1건 이상이면 점수 최상위를 채택, source="search_all"
    5) 필터 결과가 0건이면 §3-4 폴백 기본값 사용, source="fallback_default"
       (조회 실패가 곧 배차 실패로 이어지지 않도록 — 가용성 우선)
    """
```

### §3-3. 모호·다건 판단 기준

- **결정적 필터 우선**: 점수만으로 판단하지 않는다(§3-1에서 노이즈 점수가 정답과 겹치는 것을
  실측했기 때문). `type == "command"` + 경로가 `05_commands/slash/aegis-*.md`인 것만 후보로
  인정하고, 그 안에서만 점수 비교.
- **동점·복수 매칭**: 후보 command의 `trigger:` 필드에 §5 표의 영역 한국어 설명 키워드가
  직접 포함된 것을 우선(예: DB 스키마 변경 태스크 → trigger에 "스키마"가 있는 command 우선,
  DB 이중화 태스크 → trigger에 "인프라"가 있는 command 우선). 이는 §3 구버전의 "DB=dev(스키마)
  vs infra(이중화)" 분기 판단을 정적 표 대신 trigger 텍스트 매칭으로 재현한 것.
- **0건(미확정)**: §3-4 폴백 기본값을 쓰고, 배차 로그에 `resolution_source=fallback_default`로
  남겨 이후 감사 가능(T98 AIP 정직성 — "실시간 조회로 확정"과 "폴백"을 응답에서 구분).

### §3-4. 폴백 기본값 (조회 실패 시에만 사용 — 매 배차의 1차 경로 아님)

구버전 §3 매핑표는 폐기하되, **AEGIS 조회가 실패(네트워크·MCP 미가용 등)했을 때만** 쓰는
최후 안전망으로 동일 값을 코드 상수(`_FALLBACK_DEFAULT`)로 유지한다 — 단, 이것이 "정적
매핑표"와 다른 점은 **정상 조회가 되는 한 절대 우선 참조되지 않는다는 것**(§3-2 흐름 5번
에서만 도달)이다.

### §3-5. 캐싱 (TTL — "정적 표"와의 차이 명시)

- 배차마다 MCP 호출은 낭비이므로 `(domain_code) → AgentResolution` 인메모리 캐시, **TTL
  15분**을 둔다(T38 PAP 성능 고려, 신규 캐시 엔진 발명 없이 dict + timestamp면 충분).
- 정적 테이블과의 차이: 캐시는 시간이 지나면 자동 무효화되어 다음 조회 시 AEGIS 최신 agent
  로스터를 다시 반영한다 — 사람이 파일을 고쳐야 갱신되는 하드코딩 표가 아니다.
- 미확정 사항: AEGIS 쪽에 "agent 목록 변경" 이벤트를 push로 받는 채널은 이번 실측에서
  확인하지 못했다(`acn_publish`는 발행 전용, 구독 채널은 미확인) — 즉시 반영이 아니라
  **최대 15분 지연 반영**이라는 한계를 정직하게 명시한다(T98 AIP).

### §3-6. 구현 결과 — 실시간 search_all HTTP 어댑터 실측 (2026-07-19)

`search_fn` 포트를 실제로 채울 HTTP 어댑터가 있는지 실측했다(`backend/adapters/aegis_bridge/search_all_adapter.py`
모듈 docstring에 전문 기록). 결론:

- `search_all`은 aegis-mcp-go(Go stdio MCP 서버)의 `harness.Search()`를 쓴다 — stdio MCP
  도구라 이 프로젝트의 Python 프로세스에서 직접 호출 불가(§3-2 절대 금지 그대로).
- graphify-hub HTTP `/search`(GET·POST)·`/mentions`(포트 8000)는 **라이브로 확인**됐다
  (`GET /health` → 200). 그러나 별개 백엔드(`Hub.asearch()`)라 05_commands/slash/aegis-*.md
  슬래시 커맨드 인덱스가 없다 — 실측 질의(`POST /search {"query":"보안 취약점 점검 감사"}`,
  `GET /mentions?q=aegis-security`) 둘 다 빈 배열을 반환해 확인했다.
- 따라서 이번 구현 범위에서는 실시간 어댑터 대신 `StaticFallbackAdapter`(`_FALLBACK_DEFAULT`를
  감싸지 않고 항상 빈 리스트를 반환해 `resolve_agent_for_domain()`의 내장
  `source="fallback_default"` 분기로 정직하게 위임)만 제공한다. 실시간 HTTP 어댑터는
  aegis-mcp-go가 HTTP 게이트웨이를 열거나 graphify-hub 인덱스에 슬래시 커맨드가 추가되면
  `build_search_fn()` 내부만 교체하면 되도록 포트-어댑터 경계를 유지했다.

## §4. 우선순위 오케스트레이션 (신규 로직 최소화 — 기존 자산 조합)

```python
# 설계만 — backend/application/services/task_dispatch_service.py (구현 예정, 신규 파일)
def compute_priority(task: Task, all_requirements: list[RequirementRecord]) -> int:
    """우선순위 점수 — 낮을수록 먼저 처리. 신규 알고리즘 발명 없이 이미 있는 신호만 조합:
    1) lifecycle_status가 ACCEPTED인 REQ를 참조하는 태스크가 UNDER_REVIEW REQ 참조보다 먼저
       (1차 설계 §2-3 lifecycle_status 그대로 재사용 — 사람이 확정한 요구사항이 우선)
    2) needs_escalation=True(불충분)면 후순위(설계 구체화 먼저 필요 — task.py 기존 필드)
    3) detect_area_conflicts() 결과 다른 태스크와 겹치는 impact_scope가 있으면 순차화
       대상이라 그 그룹의 첫 번째만 먼저 착수(§PCM 원칙 그대로, conflict_detection.py 재사용)
    """
```

배차 흐름:
```
TaskStore.list_all() → compute_priority()로 정렬 → detect_area_conflicts()로 그룹핑
  → CLEAR 그룹은 §3-2 resolve_agent_for_domain()으로 실시간 조회한 agent로 병렬 배차,
    OVERLAP 그룹은 순차 배차(§PAW-3)
  → 각 배차는 Agent(subagent_type=조회된 AEGIS agent_command, prompt=해당 REQ+Task 컨텍스트)
```

**구현 결과 (2026-07-19)**: `dispatch_tasks()`는 위 배차 계획(dict 리스트)까지만 반환한다 —
"각 배차는 Agent(...)"의 실제 호출은 이 프로세스가 할 수 없어(§3 판단과 동일 이유)
`backend/application/services/dispatch_execution_planner.py`의 `build_execution_prompts()`가
배차 계획을 받아 "Agent(subagent_type=X, prompt=Y)로 호출하라"는 완전한 프롬프트 텍스트만
조립해 반환한다. 실제 Agent() 호출/슬래시 커맨드 실행은 이 출력을 소비하는 LLM 세션 또는
사람의 몫으로 명시적으로 분리했다.

## §5. 작업상태 확인 (기존 필드 재사용 — 신규 폴링 엔진 발명 안 함)

Task는 이미 `status`(DRAFT→READY→IN_PROGRESS→DONE/BLOCKED)와 `revision`·`updated_at`을
갖고 있다(§2 표 참조). "작업상태 확인 agent"는 새 프로세스가 아니라, **배차받은 agent 자신이
작업 종료 시 `TaskStore.create_or_update(task, status="DONE")`를 호출하는 것**이 유일하게
정확한 상태 갱신 경로다(외부에서 추측하지 않음 — T98 AIP 정직성). 오케스트레이터(§4)는 주기적
으로 `TaskStore.list_all()`을 다시 읽어 상태 변화를 감지하기만 한다(폴링, 신규 엔진 없음).

## §6. 완료 보고서 (요구사항별 상태 + 파일별 변경 내역)

```python
# 설계만 — backend/application/services/completion_report_service.py (구현 예정)
@dataclass
class CompletionReport:
    task_id: str
    source_req_ids: list[str]          # 이 작업이 어느 요구사항을 처리했는지
    files_changed: list[dict]          # [{"path": str, "change_type": "added|modified|deleted", "summary": str}]
    requirement_status_updates: dict   # {req_id: 새 lifecycle_status} — 1차 §2-3-A status_history에 그대로 기록
    generated_at: str
```

`files_changed`는 **git diff를 직접 파싱**해서 채운다(추측·자가보고 아님) —
`git diff --stat <impact_scope 경로들>`을 태스크 착수 전/후로 비교해 실제 변경분만 추출.
이미 이번 세션에서 여러 번 `git status`/`git diff`로 변경 확인을 해온 패턴 그대로 재사용
(신규 diff 파서 발명 없음).

## §7. AEGIS 노하우 상속 (신규 메커니즘 없음 — `/recall` 그대로)

"AEGIS 시스템 노하우를 전수받아 상속받아 작업을 수행" — 이미 이 세션의 모든 `/ao`·`/autobuild`
호출이 착수 전 `/recall`(graphify+hmrecall+error_kb+acn)로 관련 KH·error_kb를 조회하는 것과
동일한 메커니즘이다. §4 배차 시 각 AEGIS agent 프롬프트에 "착수 전 `/recall <해당 REQ 영역>`
먼저 수행" 지시를 포함시키는 것으로 충분 — 새 지식상속 파이프라인을 만들 필요 없음.

## §9. AEGIS 시스템에서 이 프로젝트의 agent 역할 목록 역방향 검색 (2026-07-19 신규)

> 사용자 요구 2 — "aegis 시스템에서도 agents 역할 목록 검색 할수 있도록 해서 제공 가능
> 구성해줘." 신규 공유 데몬·DB를 만들지 않고, **이미 검증된 채널로 이 사실을 실측**했다.

### §9-1. 실측 근거 — 이 프로젝트 자산은 이미 AEGIS search_all에서 검색된다

`search_all(query="ai-project-system 00_PROJECT_CONSTITUTION 영역코드")` 호출 결과,
`D:\aegis\base\04_memory\knowhow\_reports\2026-07-17_ai-project-system_자산화계획.md`가
그대로 반환되었다 — 이는 **이전 세션에서 이 프로젝트를 `/assetize`(T64 KAAG 경로)로 자산화한
결과물이 이미 AEGIS 관리자 영역에 등재되어 검색 가능한 상태**라는 것을 뜻한다(가정이 아니라
직접 조회로 확인). 즉 "이 프로젝트 → AEGIS 검색 가능"이라는 채널은 **이미 존재하고 동작
중**이다 — 새로 만들 것은 채널이 아니라 **그 채널에 실릴 콘텐츠(agent 역할 사용 목록)**뿐이다.

### §9-2. 채택 방법 — 신규 인프라 없이 기존 자산화 경로에 콘텐츠만 추가

T64 KAAG는 이 프로젝트(상품 프로젝트)가 `base/04_memory/`에 **직접 쓰기 금지**라고 못박는다.
따라서 아래 순서를 따른다(신규 파일은 이 프로젝트 폴더 안에만 생성):

1. 이 프로젝트 폴더 안에 `backend/domain/requirements/agent_role_usage.json`(구현 단계에서
   생성 예정, 신규 데몬 아님 — 단순 로그 파일)을 두고, §3-2 `resolve_agent_for_domain()`이
   호출될 때마다 `{domain_code, agent_command, resolution_source, resolved_at}`를 append.
   이것이 "이 프로젝트가 실제로 어떤 AEGIS agent 역할을 어떤 영역에 쓰고 있는지"의 ground
   truth 기록이다(자가보고 아님 — 실제 배차 이벤트 로그).
2. 세션 종료 시점 또는 사용자의 "자산화 승인" 발화 시, 기존에 이미 쓰고 있는 `/assetize`
   워크플로가 이 로그를 요약해 `D:\aegis\base\04_memory\knowhow\_reports\` 아래
   보고서로 흡수한다 — **§9-1에서 실측된 것과 동일한 경로**(신규 파이프라인 0).
3. 결과적으로 AEGIS 쪽에서 "ai-project-system이 SEC 영역에 어떤 agent를 쓰는지" 같은 질문을
   `search_all`로 던지면, 위 보고서가 검색된다 — 이것이 사용자가 말한 "AEGIS 시스템에서도
   agents 역할 목록 검색 가능"의 구현이다.

### §9-3. 검토했으나 채택하지 않은 대안 (근거 남김)

- **AEGIS `base/04_memory/`에 이 프로젝트가 직접 write**: T64 KAAG 정면 위반 — 기각.
- **신규 실시간 sync 데몬(push)**: `acn_publish`는 이벤트 발행은 가능하나(event_type
  whitelist에 `agent_role_usage`류가 없음 — `tool_call|git_commit|guard_block|
  build_failed|session_start|session_stop|error_pattern|internal`만 확인됨), 구독·소비
  측이 실제로 이 프로젝트의 agent 역할을 재구성하는지는 이번 세션에서 검증하지 못했다 —
  **미확정으로 남기고, §9-2의 이미 검증된 assetize 경로를 1차안으로 채택**한다(추측으로
  신규 엔진이 필요하다고 결론짓지 않음, T59 CFD).

## §8. 품질검토 (MPCR 7관점)

| 관점 | 검토 결과 |
|---|---|
| 개발 | 신규 파일: `agent_dispatch_resolver.py`(§3-2)·`task_dispatch_service.py`(§4)·`completion_report_service.py`(§6)·`agent_role_usage.json` 로그(§9-2) — 로직은 대부분 기존 MCP 도구(search_all) 재사용 |
| 설계 | §3 정적 표를 실시간 조회로 대체, `type=="command"` 경로 필터를 결정적 근거로 채택(§3-1 실측) — 단 caching TTL 15분은 "즉시 반영"은 아니라는 한계를 §3-5에 명시 |
| 운영 | 폴링 기반 상태 확인(§5)은 여전히 실시간 아님 — 03_PHASE3 §3-4와 동일한 한계 인정. §3-2 조회도 MCP 가용성에 의존(폴백 §3-4로 완화) |
| 정보안정성 | 완료보고서 files_changed는 git diff 기반 ground-truth(§6). agent_role_usage.json(§9-2)도 자가보고가 아닌 실제 배차 이벤트 로그 |
| 헌법정합 | AEGIS 전역 agent 재사용 + 신규 agent 미생성(00_PROJECT_CONSTITUTION §1·§4 PASS) + T64 KAAG(§9 직접쓰기 금지 준수, 기존 assetize 경로만 사용) + CRZ(신규 동기화 엔진 미발명) |
| 검증 | §3-1 실측 결과 검증 완료(list_tools/search_tools/get_tool_spec/search_all 실제 호출·응답 확인). §9-1도 실측 완료. `resolve_agent_for_domain()`·git diff 파싱·assetize 흡수 자동화는 구현 단계에서 스모크 테스트 필요 |
| 책임 | agent_role_usage.json이 "어느 도메인코드가 어느 agent로, 어떤 근거(search_all/fallback)로 배차됐는지"까지 감사 가능하게 기록 — requirement_status_updates(§6)와 함께 추적성 확보 |

**게이트 결론**: **PASS** — 미확정 2건을 정직하게 이월: ①§3-5 AEGIS agent 로스터 변경의
push 기반 즉시 반영 채널 미확인(현재는 TTL 15분 지연 허용) ②§9-3 `acn_publish` 구독측의
실제 재구성 여부 미검증(현재는 assetize 경로를 1차안으로 채택, push 방식은 후속 검증 대상).

## §10. 요구사항별 "작업상태 + 배정 agent" 노출 설계 (2026-07-20 보강 — 사용자 심층 지적 반영)

> **지적 원문 요지**: "각각 요구사항에 필요한 작업 agent가 있어야되는데 그것도 없다" —
> §3(배차 실시간 조회)·§4(우선순위 오케스트레이션)가 이미 구현돼 있지만(`agent_dispatch_
> resolver.py`·`task_dispatch_service.py`, 실측 확인), 그 결과가 **요구사항 화면에서 사람이
> 볼 수 있는 형태로 노출되지 않는다** — `dispatch_tasks()`가 반환하는 배차 계획은 Task 단위
> dict일 뿐 `RequirementRecord`에 저장되지 않고, `requirements.html`에도 배정 agent·작업상태
> 컬럼이 없다(실측: `requirement_store.py`의 `RequirementRecord`에 `assigned_agent_command`·
> `work_status` 류 필드 자체가 없음을 코드 직접 열람으로 확인). 이 절이 그 노출 고리를 메운다.

### §10-1. 왜 `lifecycle_status`(§2-3)만으로는 부족한가

`lifecycle_status`는 "사람이 이 요구사항을 승인했는가"(RECEIVED→...→ACCEPTED/REJECTED/
WITHDRAWN)를 다루는 축이고, Task의 `status`(DRAFT→READY→IN_PROGRESS→DONE/BLOCKED)는
"그 요구사항을 구현하는 작업이 코드 관점에서 어디까지 왔는가"를 다루는 **별개 축**이다.
지금은 후자가 요구사항 화면에 전혀 반영되지 않는다 — REQ가 `ACCEPTED`여도 그걸 처리할
Task가 아직 배차조차 안 됐는지, 이미 어떤 agent가 작업 중인지, 이미 끝났는지를 요구사항
목록에서 확인할 방법이 없다. 이번 절은 **세 번째 축(`work_status`)** 을 신설한다(신규
lifecycle 상태값을 늘리는 대신 별개 축으로 분리 — §2-1의 "축을 늘려도 번호는 그대로"
원칙과 동일하게, `lifecycle_status`를 오염시키지 않음, CRZ).

### §10-2. `RequirementRecord` 확장 필드 (설계만 — 신규 필드 2개)

```python
# 설계만 — backend/adapters/persistence/requirement_store.py에 추가할 필드
# (기존 68개 필드 뒤에 추가, 기존 필드 변경 없음)
assigned_agent_command: str | None = None   # 예: "/aegis-security" — §3-2 AgentResolution.agent_command 그대로 복사
work_status: str = "NOT_DISPATCHED"         # NOT_DISPATCHED | DISPATCHED | IN_PROGRESS | DONE | BLOCKED
work_status_updated_at: str = ""            # 마지막 갱신 시각(감사용, status_history와 동일 패턴)
```

`work_status` 값 집합은 §4에서 이미 쓰는 Task.status(DRAFT→READY→IN_PROGRESS→DONE/BLOCKED)를
요구사항 관점으로 재해석한 것이지 새 상태기계를 발명한 게 아니다:

| work_status | 대응하는 Task 신호 |
|---|---|
| `NOT_DISPATCHED` | 이 REQ를 `source_req_ids`로 참조하는 Task가 아직 없거나, `dispatch_tasks()` 계획에 아직 오르지 않음 |
| `DISPATCHED` | `dispatch_tasks()` 계획에 올라 `agent_resolution`이 확정됐으나 Task.status가 아직 `DRAFT`/`READY` |
| `IN_PROGRESS` | 참조 Task 중 하나 이상이 `Task.status == "IN_PROGRESS"` |
| `DONE` | 참조 Task **전부**가 `Task.status == "DONE"` (부분 완료는 `IN_PROGRESS` 유지 — 낙관적으로 앞당기지 않음, T98 AIP) |
| `BLOCKED` | 참조 Task 중 하나 이상이 `Task.status == "BLOCKED"` (다른 Task가 IN_PROGRESS여도 BLOCKED 우선 표시 — 문제 은폐 방지) |

여러 Task가 같은 REQ를 참조할 때의 집계 우선순위(정직성 우선): **BLOCKED > IN_PROGRESS >
DISPATCHED > DONE(전부 완료 시에만) > NOT_DISPATCHED**.

### §10-3. 갱신 경로 (신규 폴링 엔진 발명 없음 — 기존 §5 폴링 재사용)

```python
# 설계만 — backend/application/services/task_dispatch_service.py에 추가할 함수
def sync_requirement_work_status(
    requirement_store, task_store, dispatch_plan: list[dict]
) -> None:
    """§5(작업상태 확인)의 기존 폴링 지점에서 함께 호출 — 신규 폴링 루프 없음(CRZ).

    dispatch_plan(§4 dispatch_tasks() 반환값)과 TaskStore.list_all()의 최신 Task.status를
    조합해 각 REQ의 work_status·assigned_agent_command를 §10-2 집계 규칙으로 재계산하고,
    RequirementStore.set_work_status(req_id, work_status, assigned_agent_command)로 반영.
    (set_status()와 동일한 얇은 setter 패턴 재사용 — 신규 이력 구조 발명 없음)
    """
```

### §10-4. API 확장 설계 (`backend/adapters/api/requirements_api.py`, 코드 변경 없음 — 설계만)

`GET /requirements/{req_id}` 응답 JSON에 아래 2개 필드만 추가(기존 응답 필드는 그대로,
하위호환 — 기존 프론트 소비자가 깨지지 않음):

```json
{
  "req_id": "REQ-BIZ-SEC-003",
  "...(기존 필드 전부 동일)...": "...",
  "assigned_agent_command": "/aegis-security",
  "work_status": "IN_PROGRESS"
}
```

`GET /requirements`(목록) 응답도 각 항목에 동일 2필드를 포함 — 목록 화면에서 컬럼으로
바로 렌더링 가능하게(§10-5).

### §10-5. UI 확장 설계 (`frontend/views/requirements.html` — 설계만, 이번 세션 실제 수정 금지)

목록 테이블에 기존 배지 컬럼(영역·계층·유형·라이프사이클) 뒤에 2개 컬럼 추가:

```
| REQ ID | 영역 | 계층 | 유형 | 라이프사이클 | 배정 agent | 작업상태 |
|---|---|---|---|---|---|---|
| REQ-BIZ-SEC-003 | SEC | SECU | NFUNC | ACCEPTED | /aegis-security | 🟡 IN_PROGRESS |
```

- "배정 agent" 컬럼: `assigned_agent_command`가 `None`이면 "미배정"(회색 텍스트)
- "작업상태" 컬럼: `work_status`별 색 배지(NOT_DISPATCHED=회색·DISPATCHED=파랑·
  IN_PROGRESS=노랑·DONE=초록·BLOCKED=빨강) — §2-1의 "축 이름 병기" 원칙과 동일하게
  배지 자체에 상태명을 그대로 표기(아이콘만으로 대체하지 않음, 접근성 고려)
- 클릭 시 §6 청크맵 뷰 또는 §2 미리보기 모달로 이동하는 기존 진입점과 별도 충돌 없음
  (배지는 정보 표시 전용, 신규 액션 없음)

### §10-6. 품질검토 (MPCR 3관점 — 근본원인·대안·재발방지, 버그수정형 보강이므로 T83 MDR 3관점 기준 적용)

| 관점 | 검토 결과 |
|---|---|
| 근본원인 | §3·§4가 배차 "계획"만 만들고 그 결과를 `RequirementRecord`에 되먹임(write-back)하는 경로가 없었던 것이 근본원인 — 배차 로직 자체는 이미 정상 동작(실측 확인) |
| 대안 | (A) 채택안: REQ에 2필드만 추가해 배차 결과를 되먹임 / (B) 기각안: Task 화면을 새로 만들어 거기서만 보여줌 — REQ 중심 요청("요구사항에 필요한 작업 agent")과 어긋나 기각 / (C) 기각안: REQ와 Task를 완전히 병합 — 기존 6+1축 데이터모델(§5 인덱스, 임의 변경 금지 지시)을 건드리게 되어 기각 |
| 재발방지 | §10-3 `sync_requirement_work_status()`를 기존 §5 폴링 지점에 강제로 함께 호출하도록 설계해, "로직은 있는데 화면에 안 보인다"는 동일 패턴의 재발을 구조적으로 차단(배차 로직 추가 시 되먹임 누락 여부를 리뷰 체크리스트에 남길 근거) |

**결론**: 설계만 — 구현은 사용자 승인 후 별도 턴(00_PROJECT_CONSTITUTION.md §1 원칙 그대로).
