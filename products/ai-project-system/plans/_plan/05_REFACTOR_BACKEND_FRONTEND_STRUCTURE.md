---
role: DESIGN_REFACTOR
scope: 백엔드 헥사고날 통합 + 프론트엔드 폴더 통합 + plans/ T45 TLM 라이프사이클 도입
status: L4 DONE 확정(2026-07-19 사용자 승인) — backend/frontend 이동·import 수정·23개 pytest 회귀 0 확인. `plans/_done/refactor-hexagonal-2026-07-19/status.json` 참조(2026-07-22 재검토: "L4 DONE은 승인 대기"는 stale — 이미 승인·`_done/` 이관 완료 확인)
updated: 2026-07-22 (stale 상태표기 정정)
---

# 리팩토링 설계 — 헥사고날 백엔드 통합 + 프론트엔드 정리 + plans 라이프사이클

> 상위: [`00_INDEX.md`](./00_INDEX.md)

> **Stage 0 확정 사항(AskUserQuestion, 2026-07-19)**:
> 1. 백엔드 아키텍처 = **헥사고날 단일 통합**(이미 있는 `core_was_block`이 정본, 지금 플랫하게
>    흩어진 `graphify_engine`/`ingestion`/`orchestrator` 로직을 그 안의 domain/application/
>    adapters 3계층으로 재배치)
> 2. 이번 라운드 범위 = 백엔드 폴더 + 프론트엔드 폴더 + `plans/` T45 TLM 라이프사이클
>    **+ AEGIS 전문가 agent(아키텍처·개발) 활용해 실행하고 그 경험을 자율 성장 기반으로 축적**
> 3. 이번 턴 산출물 = **설계서만** — 실제 파일 이동은 사용자 승인 후 별도 턴

## §1. 왜 필요한가 — 실측 근거(추정 아님)

사용자 지적("그냥 한 파일에 만들고 있는거 같아요")을 실제 폴더 구조로 확인했다:

```
core_was_block/    ← Phase 1에서 만든 헥사고날 뼈대(domain/application/adapters) — 정본이지만 거의 비어있음
graphify_engine/   ← 청킹 이후 실제 로직 대부분이 여기 플랫하게 쌓임(6개 모듈)
ingestion/         ← 파싱·청킹·추출 로직이 여기 플랫하게 쌓임(5개 모듈 + parsers/)
orchestrator/      ← 태스크 관리가 여기 플랫하게 쌓임(1개 모듈)
```

**즉 헥사고날 뼈대(`core_was_block`)는 Phase 1 스캐폴딩 이후 한 번도 실제로 쓰이지 않았고**,
이후 세션들(이번 세션 포함)이 편의상 새 최상위 폴더를 계속 만들며 로직을 쌓아왔다 — 사용자
지적이 정확하다. `grep`으로 실제 cross-module import 17건을 전수 확인한 결과가 아래 §2의
매핑표 근거다(추정 없이 실측).

## §2. 백엔드 — 헥사고날 단일 통합 매핑표 (실측 import 그래프 기반)

### §2-1. 현재 실제 의존 관계(전수 grep 결과)

```
core_was_block/adapters/db/sqlite_adapter.py     → core_was_block.application.ports.db_port
                                                  → core_was_block.domain.entities.project
core_was_block/application/ports/db_port.py      → core_was_block.domain.entities.project
ingestion/parsers/docx_adapter.py                → core_was_block.application.ports.parser_port
graphify_engine/classifier.py                    → graphify_engine.codes
graphify_engine/extractors/{ast,semantic}.py     → graphify_engine.domain
graphify_engine/pipeline.py                      → graphify_engine.domain
graphify_engine/project_config.py                → graphify_engine.codes
graphify_engine/requirement_store.py             → graphify_engine.classifier, graphify_engine.requirements
graphify_engine/requirements.py                  → graphify_engine.codes, graphify_engine.domain
ingestion/requirement_extractor.py               → graphify_engine.classifier, graphify_engine.requirement_store, ingestion.chunking
orchestrator/task_manager.py                     → graphify_engine.codes, graphify_engine.requirements
```

`core_was_block`은 이미 `ingestion/parsers/docx_adapter.py`가 `ParserPort`를 참조하고 있어
**부분적으로는 이미 정본 역할**을 하고 있다 — 완전히 방치된 게 아니라 "일부만 연결되고
나머지는 병렬로 자라난" 상태다.

### §2-2. 목표 구조 (`backend/` 단일 루트, 헥사고날 3계층)

```
backend/
├── domain/                          ← 순수 로직(외부 I/O 없음, 이 계층은 어떤 프레임워크도 모른다)
│   ├── entities/
│   │   ├── project.py               ← core_was_block/domain/entities/project.py (이동)
│   │   ├── requirement.py           ← graphify_engine/domain.py의 Node/Edge(REQUIREMENT 종류) 재정리
│   │   └── task.py                  ← orchestrator/task_manager.py의 Task 데이터클래스만 분리
│   ├── graph/
│   │   └── entities.py              ← graphify_engine/domain.py(Node/Edge 4종, NodeKind/EdgeKind)
│   ├── requirements/
│   │   ├── codes.py                 ← graphify_engine/codes.py (SSOT, 그대로 이동)
│   │   ├── id_format.py             ← graphify_engine/requirements.py의 parse_req_id/build_req_id
│   │   ├── classifier.py            ← graphify_engine/classifier.py (순수 키워드 매칭, I/O 없음)
│   │   └── conflict_detection.py    ← orchestrator/task_manager.py의 detect_area_conflicts·check_sufficiency
│   └── chunking/
│       ├── chunk.py                 ← ingestion/chunking.py의 Chunk 데이터클래스
│       └── heading_splitter.py      ← ingestion/chunking.py의 HeadingBoundarySplitter·SemanticBoundarySplitter
│
├── application/                     ← 유스케이스(도메인 조합 + 포트 호출, 여기도 구체 기술 모름)
│   ├── ports/                       ← core_was_block/application/ports/ (그대로 이동 — 이미 정본)
│   │   ├── db_port.py
│   │   ├── parser_port.py
│   │   ├── requirement_store_port.py   ← 신규(§2-3 근거)
│   │   └── task_store_port.py          ← 신규
│   └── services/
│       ├── requirement_extraction_service.py  ← ingestion/requirement_extractor.py(오케스트레이션)
│       ├── graph_pipeline_service.py          ← graphify_engine/pipeline.py(merge_into_graph)
│       └── context_service.py                 ← graphify_engine/context_manager.py
│
└── adapters/                        ← 구체 기술(파일 I/O·DB·파서) — 여기만 "어떻게 저장하는지" 안다
    ├── db/
    │   └── sqlite_adapter.py        ← core_was_block/adapters/db/ (그대로 이동)
    ├── api/
    │   └── health.py                ← core_was_block/adapters/api/ (그대로 이동)
    ├── persistence/                 ← JSON 파일 기반 스토어들(신규 그룹핑 — 전부 같은 패턴이었음, CRZ)
    │   ├── requirement_store.py     ← graphify_engine/requirement_store.py
    │   ├── task_store.py            ← orchestrator/task_manager.py의 TaskStore
    │   ├── document_store.py        ← ingestion/document_store.py
    │   └── project_config_store.py  ← graphify_engine/project_config.py의 ProjectConfigStore
    ├── parsers/
    │   ├── router.py                ← ingestion/router.py
    │   └── docx_adapter.py          ← ingestion/parsers/docx_adapter.py
    ├── extractors/
    │   ├── ast_extractor.py         ← graphify_engine/extractors/ast_extractor.py
    │   └── semantic_extractor.py    ← graphify_engine/extractors/semantic_extractor.py
    └── error_log.py                 ← ingestion/error_log.py
```

**`infrastructure/`는 이동하지 않는다** — 배포 설정(env·nginx·topology)은 헥사고날 3계층
어디에도 속하지 않는 별도 관심사(인프라)라 그대로 최상위에 남긴다(과잉 정리 회피).

### §2-3. 새로 필요한 것 — Port 인터페이스 2개 (T102 NTM 원칙)

지금은 `RequirementStore`·`TaskStore`가 구체 구현(JSON 파일)에 직접 의존되고 있어 "나중에
DB로 바꾸려면 이 두 클래스를 쓰는 모든 코드를 다시 손대야" 한다. 이미 있는
`DatabasePort`/`ParserPort` 패턴(core_was_block/application/ports/)을 그대로 따라 포트
인터페이스를 2개 추가한다 — 새 아키텍처 패턴 발명이 아니라 **이미 있는 패턴을 미적용
영역까지 넓히는 것**(CRZ):

```python
# backend/application/ports/requirement_store_port.py (설계만 — 시그니처는 기존 클래스 그대로 추출)
class RequirementStorePort(Protocol):
    def add_from_classification(self, ...) -> RequirementRecord | None: ...
    def set_status(self, ...) -> RequirementRecord: ...
    def list_all(self) -> list[RequirementRecord]: ...
```

## §3. 프론트엔드 — 단일 `frontend/` 루트로 통합

현재 `agent-view/`(화면 4개+데이터)와 `frontend/styles/`(토큰 CSS)가 분리돼 있다 —
이름 때문에 혼동 소지("agent-view"가 뭘 의미하는지 신규 참여자가 알기 어려움).

```
frontend/
├── styles/tokens.css        ← 그대로(이미 frontend/ 아래 있음, 이동 없음)
├── views/                   ← agent-view/*.html 이동(디렉터리명만 변경)
│   ├── index.html
│   ├── requirements.html
│   ├── preview.html
│   └── project-setup.html
└── data/                    ← agent-view/data/ 이동
    ├── requirements.json
    └── documents/
```

`styles/tokens.css`를 참조하는 상대경로(`../frontend/styles/tokens.css`)가
`views/*.html` 기준으로는 그대로 유지된다(`agent-view/`→`frontend/views/`로 이동해도 형제
관계는 동일 — `../frontend/`가 `../`(한 단계 위) 기준이라 `frontend/views/x.html`에서
`../styles/tokens.css`로 **한 단계 얕아짐**, 실제 이동 시 상대경로 수정 필요 지점으로 표시).

## §4. `plans/` — T45 TLM 라이프사이클 실제 도입

사용자 지적: "plans 폴더를 만든 이유가 작업수행 관리를 위해서". 실측 확인 결과
`plans/_open`·`plans/_done`·`plans/_archived`가 **전부 빈 폴더**다(폴더만 있고 파일 0개) —
지금까지 이 프로젝트의 모든 작업은 `plans/_plan/`(설계 문서)에만 쌓였고, 실제 작업
진행상태를 추적하는 T45 TLM 라이프사이클(L1 DESIGN → L2 ACTIVE → L3 REVIEW → L4 DONE)은
한 번도 가동되지 않았다.

### §4-1. 확정 매핑

| T45 TLM 단계 | 이 프로젝트 폴더 | 지금 상태 | 이번 설계 적용 |
|---|---|---|---|
| L1 DESIGN | `plans/_plan/` | 사용 중(0~5차 설계서 6개) | 유지 — 새 기능 설계는 계속 여기 |
| L2 ACTIVE | `plans/_open/<task_id>/` | **빈 폴더** | 이번 리팩토링부터 실제 사용 시작 — 실행 턴에 `plans/_open/refactor-hexagonal-2026-07-19/status.json` 생성 |
| L3 REVIEW | (별도 `_review/` 폴더 없음 — T45 원문 기준 필요 시 생성) | 없음 | 이번 리팩토링 완료 후 검증 단계에서 필요 시 도입(과잉 생성 회피 — 필요할 때) |
| L4 DONE | `plans/_done/` | **빈 폴더** | 리팩토링 완료 + **사용자 명시 승인 후에만** 이동(T45 §3 — LLM 단독 이동 금지) |

### §4-2. 실행 턴에 만들 `status.json` 스키마(설계만, 지금 생성 안 함)

```json
{
  "task_id": "refactor-hexagonal-2026-07-19",
  "status": "in_progress",
  "design_ref": "plans/_plan/05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md",
  "impact_scope": ["graphify_engine/", "ingestion/", "orchestrator/", "core_was_block/", "agent-view/", "frontend/"],
  "steps": [
    {"id": "backend-domain", "status": "pending"},
    {"id": "backend-application", "status": "pending"},
    {"id": "backend-adapters", "status": "pending"},
    {"id": "frontend-merge", "status": "pending"},
    {"id": "import-fix-verify", "status": "pending"}
  ]
}
```

## §5. AEGIS 전문가 agent 활용 실행 계획 (사용자 지시 반영 — 실행은 다음 턴)

사용자가 명시적으로 요청한 "aegis 시스템 개발 agent, 아키텍처 agent 등 전문가 agent를
활용해서 작업하면서 경험을 자율 성장 기반 사용"을 다음 실행 턴에 이렇게 적용한다:

| 단계 | 담당 | 산출물 |
|---|---|---|
| 구조 검증 | `/aegis-architect` (아키텍처 전문가 agent) | §2-2 목표 구조가 헥사고날 원칙(의존성 역전·계층 분리)을 실제로 지키는지 착수 전 재검토 |
| 파일 이동 + import 수정 | `/aegis-dev` (개발 전문가 agent) | §2-1 매핑표대로 파일 이동 + 17건 import 경로 일괄 수정 |
| 인프라 영향 확인 | `/aegis-infra` (인프라 전문가 agent) | `infrastructure/config_loader.py` 등이 새 backend/ 경로를 참조해야 하는 곳이 있는지 확인 |
| 실행 후 검증 | 기존 smoke test 전체 재실행(신규 검증 도구 발명 없음) | 회귀 0 확인(T53 VIP) |
| 경험 축적 | `ao_experience_record.py`(T81 SDUP) | `--command refactor-hexagonal --difficulty D4 --dist "3agent-sequential"` 로 기록 — 다음에 유사 폴더 리팩토링 시 이 경험을 recall이 자동 인지 |

**순서가 중요한 이유(§PAW-3 집약파일 순차화)**: 파일 이동은 전형적인 "집약 지점" 작업이라
병렬화하지 않는다 — domain→application→adapters 순으로 **하나씩** 옮기고 그때마다 import를
고쳐 확인한 뒤 다음 계층으로 넘어간다(§0-6-4 순차완결 원칙, 한 계층 이동 중 세션이 끊겨도
그 계층까지는 확정 완료 상태를 유지하기 위함).

## §6. 리스크·품질검토 (MPCR 7관점)

| 관점 | 검토 결과 |
|---|---|
| 개발 | 17건 import 수정은 기계적이라 난이도 낮음(D2 수준 개별 건) — 다만 파일 수(20+)가 많아 전체로는 D4(뼈대 변경) |
| 설계 | `core_was_block`이 이미 부분적으로 정본 역할 중이라 완전 새 구조가 아니라 "확장"에 가까움 — 재발명 아님(CRZ) |
| 운영 | 이번 세션에서 만든 smoke test(6축 분류·상태전이·위치추적 3종)가 이동 후 회귀 검증의 유일한 근거 — 고정 pytest가 없다는 기존 한계가 이번에도 그대로 적용됨(구현 턴에서 최소한 이 스모크들을 스크립트화 권고) |
| 정보안정성 | 해당 없음(구조 변경, 데이터 없음) |
| 헌법정합 | 00_PROJECT_CONSTITUTION.md §1 "AEGIS류 인프라를 도구로만" 원칙과 별개 축 — 이건 이 프로젝트 자체의 코드 구조 문제라 헌법과 충돌 없음 |
| 검증 | §5 표의 "실행 후 검증"이 유일한 검증 계획 — 구현 턴에서 반드시 전체 smoke test 재실행 후 결과를 보고할 것 |
| 책임 | 파일 이동은 git 이력으로 추적 가능(`git mv` 사용 시 rename 감지 유지 권장 — 구현 턴 메모) |

**게이트 결론**: **PASS** — 실측 기반 매핑표 확정, 실행은 사용자 승인 후 별도 턴.

## §7. 다음 턴에 확인할 것 (구현 착수 전 최종 확인)

1. `plans/_open/refactor-hexagonal-2026-07-19/status.json` 생성해도 되는지(T45 TLM 실사용 시작점)
2. §2-2 구조안 그대로 진행할지, 세부 파일명(예: `conflict_detection.py`)에 이견 있는지
3. `git mv` 사용 여부 — **실측 확인 완료(2026-07-19)**: `git rev-parse --is-inside-work-tree` = `true`, git 저장소 맞음 → 구현 턴에서 `git mv`로 이동해 rename 이력 보존 권장
