---
role: CONSTITUTION
scope: ai-project-system 전체 (최상위 정본 — 다른 모든 설계 문서보다 우선 참조)
status: 확정 — 이후 모든 Phase 설계·구현은 이 문서 기준으로 방향 이탈 여부를 점검한다
updated: 2026-07-17
---

# ai-project-system 프로젝트 방향 헌법

> **이 문서가 최우선이다.** `00_DESIGN_TOC.md`의 Phase 1~6, `graphify_engine/`, `ingestion/` 등
> 모든 구현은 **이 헌법이 정의하는 목표에 복무할 때만** 유효하다. 새 기능·Phase를 추가하기 전에
> 반드시 §4 드리프트 체크리스트로 자기 검증한다.

## §1. 핵심 목표 (변경 불가 — 이것이 프로젝트의 존재 이유)

> **사업 착수 전 생산되는 요구사항 관련 문서 일체를 구조화된 근거로 삼아, AI(LLM)에게 개발을
> 맡기기 전에 "무엇을, 어느 영역에서, 어떤 순서로" 할지를 명확히 확정하고, 그 확정된 태스크를
> 충돌 없이 뼈대→점진 확장 방식으로 AI가 수행하도록 관리하는 프로젝트 수행 관리 시스템.**

이 시스템은 다음 **한 문장**으로 요약된다:

```
요구사항 문서 입력 → 청킹·구조화 → 영역/분야별 요구사항 분류·번호관리(산출물)
    → AI 개발 태스크 뼈대 생성(충돌 방지) → LLM 태스크 수행 → 진행 관리·추적
```

**이 시스템 자체가 "범용 자율 성장형 AI 운영체제"를 만드는 프로젝트가 아니다.** 범용 AEGIS류
인프라(헥사고날 뼈대, 에이전트 스웜, 자가진화 Growth DNA 등)는 **이 목표를 위한 도구**로만
채택하며, 목적이 되어서는 안 된다 — 이것이 지금까지의 방향 이탈 우려의 핵심이다.

## §2. 입력 문서 스코프 (SSOT — 명확히 한정)

이 시스템이 다루는 입력은 **범용 비정형 문서가 아니라, 사업 착수 전 단계에서 생성되는 아래
문서군으로 한정**한다:

| 분류 | 문서 예시 |
|---|---|
| 사업 문서 | 제안서, 사업계획서, 수행계획서, 착수보고서 |
| 정성 정보 | 이해관계자 인터뷰(음성/텍스트) |
| 구축 환경 스펙 | WEB/WAS/DB 구성, 암호화 솔루션, SSL, 그리드(부하분산), 웹접근성 기준 |
| 품질·보안 요건 | 소스코드 취약성 점검 기준, 보안 감사 요건 |
| 기술 스택 요건 | Frontend/Backend 언어, 중계서버(Gateway) 언어, LLM 연계 방식(Python) |
| 산출물 요건 | 보고서 양식·주기 |

Phase 2(Ingestion/SPC)가 다루는 "PDF/HWP/PPTX/이미지"는 **이 문서군을 입력받기 위한 수단**이지,
"아무 문서나 처리하는 범용 인제스트 엔진을 만드는 것" 자체가 목적이 아니다. 코드베이스 AST
분석(Phase 3.1 Deterministic 추출)도 "요구사항이 실제 코드로 구현됐는지(IMPLEMENTS 추적)"를
검증하기 위한 수단이지, 범용 코드 그래프 구축이 목적이 아니다.

## §3. 처리 파이프라인 재정의 (Phase 1~6을 이 목적으로 재해석)

| 기존 Phase | 이 헌법 기준 목적 재확인 |
|---|---|
| Phase 0 환경설정 | 프로젝트 도메인·스택을 **요구사항 문서에서 추출한 값**으로 확정(임의 가정 금지) |
| Phase 1 인프라 뼈대 | 요구사항 관리 시스템 자체의 WEB/WAS/DB 뼈대 — **관리 대상 프로젝트의 인프라가 아님**(혼동 주의) |
| Phase 2 Ingestion+SPC | **화면 입력/업로드된 사업 문서**를 청킹해 "영역/분야별 요구사항 항목"으로 정규화하는 것이 유일한 목적. 문서 파서(DOCX 등)는 이 목적을 위한 수단 |
| Phase 3 Graphify | 그래프의 핵심 노드는 **Requirement**(요구사항)와 **Policy**(제약조건)이며, Function/Variable 노드는 "요구사항이 실제 코드에 구현됐는가(IMPLEMENTS 추적)"를 검증하는 보조 수단일 뿐 — 그래프 구축 자체가 목적이 아님 |
| Phase 4 멀티 에이전트 협업 | **영역/분야별로 번호 관리된 태스크**를 LLM에게 배정·실행시키는 것 — 이것이 "AI 개발 태스크 관리 시스템"의 본체 |
| Phase 5 검증 루프 | 각 태스크가 **원 요구사항 항목(번호)**을 충족했는지 추적·검증 |
| Phase 6 자가진화 | 실패 패턴 학습은 "다음 프로젝트에서 동일 유형 요구사항을 더 정확히 태스크화"하기 위함 |

## §4. 드리프트 체크리스트 (신규 기능·Phase 착수 전 자문)

새 설계·구현을 추가하기 전에 아래 질문에 **모두 YES**가 아니면 착수하지 않는다(0-N No-Skip 원칙과 동일):

1. 이 기능은 **"요구사항 문서 → 구조화된 요구사항 항목"** 경로에 직접 기여하는가?
2. 산출물이 **문서유형·영역별 번호(예: `REQ-BIZ-SEC-003`, `REQ-ENV-WEB-011`)로 추적 가능한 형태**인가?
3. 이 기능이 만드는 것이 **"AI가 수행할 태스크"** 또는 **"그 태스크의 관리 정보"**인가?
4. 범용 AEGIS류 인프라(에이전트 스웜, Growth DNA 등)를 가져온다면, 그것이 **§1의 목적을 위한 도구**로만 쓰이는가(그 자체가 목적으로 비대해지지 않는가)?

하나라도 NO면: 그 기능은 이 프로젝트 범위 밖이거나, 범위를 명확히 좁혀야 한다 —
AskUserQuestion으로 재확인 후 진행.

## §5. 영역/분야 코드 체계 (요구사항 산출물 번호 관리 — 초안, §6에서 확정 필요)

| 코드 | 영역 |
|---|---|
| `WEB` | 프론트엔드/웹 |
| `WAS` | 애플리케이션 서버/백엔드 |
| `DB` | 데이터베이스 |
| `SEC` | 암호화 솔루션·SSL·보안 |
| `GRID` | 그리드(부하분산/이중화) |
| `A11Y` | 웹접근성 |
| `VULN` | 소스코드 취약성 점검 |
| `GW` | 중계서버(Gateway) |
| `LLM` | LLM 연계(Python) |
| `RPT` | 보고서 산출물 |

## §5-A. 문서유형 코드 (첨부 문서 종류별 분류 — 2026-07-18 추가)

§2의 "입력 문서 스코프" 표를 코드화한다. **영역코드(§5)가 "요구사항이 어느 기술 영역에
속하는가"라면, 문서유형코드는 "그 요구사항이 어떤 종류의 원본 문서에서 나왔는가"** —
서로 다른 축이며 하나의 REQ 번호에 함께 표기한다.

| 코드 | 문서 유형 (§2 대응) |
|---|---|
| `BIZ` | 사업 문서 (제안서/사업계획서/수행계획서/착수보고서) |
| `ITV` | 정성 정보 (이해관계자 인터뷰) |
| `ENV` | 구축 환경 스펙 (WEB/WAS/DB 구성·암호화·SSL·그리드) |
| `QA` | 품질·보안 요건 (소스코드 취약성 점검·보안 감사) |
| `TECH` | 기술 스택 요건 (Frontend/Backend/Gateway 언어·LLM 연계) |
| `OUT` | 산출물 요건 (보고서 양식·주기) |

정본: `graphify_engine/codes.py`(`DOC_TYPE_CODES`) — 이 표와 그 파일이 항상 동기화되어야
한다(CRZ). 코드 문자열 자체는 실사용 문서를 보며 조정 가능한 **제안값**이다.

번호 형식: **`REQ-{문서유형코드}-{영역코드}-{3자리 일련번호}`** (예: `REQ-BIZ-SEC-003` —
"사업계획서에서 나온 보안 영역 요구사항 3번"). 각 요구사항 항목은 청킹된 원문 출처
(문서명·페이지/섹션)를 `source_ref`로 반드시 보유한다(추정 요구사항 생성 금지).
검증·채번: `graphify_engine/requirements.py`의 `parse_req_id()`/`build_req_id()`.

## §6. 확정/미확정 사항

- ✅ **확정(2026-07-17, 사용자 승인)**: §5 영역 코드 체계(WEB/WAS/DB/SEC/GRID/A11Y/VULN/GW/LLM/RPT)는
  이대로 사용한다.
- ✅ **확정(2026-07-18, 사용자 승인)**: 요구사항 번호에 문서유형코드(§5-A)를 별도 축으로 추가하고,
  번호 형식 자체에 포함한다 — `REQ-{문서유형코드}-{영역코드}-{번호}`. §5-A 표의 구체 코드 값
  (BIZ/ITV/ENV/QA/TECH/OUT)은 제안값이며 실사용 문서 확인 후 조정 여지 있음(구조는 확정, 값은 미확정).
- ✅ **확정(2026-07-21, 사용자 확인)**: 프론트엔드는 처음부터 React로 설계된 적이 없다(grep
  전수 검색으로 확인 — `tests/test_dispatch_execution_planner.py`의 `solution_stack` 예시
  더미값 1건 외 매칭 0). 현재 vanilla HTML/CSS/JS 구조를 **POC 단계 동안 그대로 유지**하고,
  React 등 프레임워크 도입은 **POC 이후 리팩토링 단계에서 재검토**한다(지금 전환 착수 안 함).
- 미확정(다음 세션에서 사용자 확인 필요 — 추정으로 채우지 않음):
  - 화면 입력 UI의 구체 형태(파일 업로드 전용인지, 폼 입력 병행인지)
  - 요구사항 항목의 승인 워크플로(누가 확정하는가 — PM? 담당자?)
  - "인터뷰" 입력을 텍스트로만 받는지, 음성 인식까지 포함하는지

남은 미확정 사항은 **AskUserQuestion으로 명확화 후** 설계에 반영한다(0-N No-Skip 원칙).

- 🔶 **설계 완료 + 1차(데이터모델) 뼈대 구현 착수(2026-07-18)**: 요구사항 데이터 모델 6축
  확장 설계(`plans/_plan/` 0~3차)에 이어, 1차(데이터 모델) 스켈레톤을 실제로 구현했다 —
  `graphify_engine/codes.py`(LAYER_CODES·REQUIREMENT_TYPES 추가)·`classifier.py`(계층·유형
  키워드 분류 추가)·`requirement_store.py`(`lifecycle_status` 9값 + `status_history` 감사로그
  + `set_status(actor, reason)`)·`orchestrator/task_manager.py`(`solution_stack` 필수화) +
  `agent-view/requirements.html`(계층·유형 배지 반영). smoke test로 6축 분류·상태전이(reason
  필수 검증 포함) 실동작 확인. §5(영역코드)·§5-A(문서유형코드)는 변경하지 않음.
  **0차(등록 마법사)도 구현 완료(2026-07-18)** — `graphify_engine/project_config.py`
  (검증·영속화) + `agent-view/project-setup.html`(6단계 마법사), smoke test로 위저드 JSON과
  python 스토어 스키마 호환 확인. **2차 §1(위치추적)·미리보기 화면도 구현 완료(2026-07-18)**
  — `ingestion/chunking.py`(char_start/end·heading_path 오프셋 추적) + `ingestion/
  document_store.py`(원문 영속화, Windows CRLF 오프셋 불일치 버그 발견·수정) + `agent-view/
  preview.html`(분할뷰: 좌측 요구사항 목록 클릭 → 우측 원문 하이라이트 즉시 표시). 2차의
  상태변경 액션·PII 게이트·병렬 그룹핑, 3차(agent 프롬프트·graphify 최신화)는 여전히 설계만.

- ✅ **헥사고날 백엔드+프론트엔드 통합 리팩토링 완료(2026-07-19)**: 사용자 지적("그냥
  한파일에 만들고 있다")에 따라 `plans/_plan/05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md`
  설계대로 실행 — 위에서 언급된 `graphify_engine/`·`ingestion/`·`orchestrator/`·
  `core_was_block/`(4개 최상위 패키지)를 **전부 제거**하고 `backend/domain·application·
  adapters` 3계층으로 통합, `agent-view/`+`frontend/styles/`를 `frontend/{views,styles,
  data}`로 병합. `orchestrator/task_manager.py`는 순수 로직(`backend/domain/task.py`)과
  JSON 영속화(`backend/adapters/persistence/task_store.py`)로 실제 분리(단순 이동이
  아닌 코드 분할). `tests/`(23개 pytest, 직전 라운드 신설분)로 리팩토링 전후 회귀 0
  확인 + 정적서버로 프론트 4화면 전부 200 재확인. `plans/_open/refactor-hexagonal-
  2026-07-19/status.json`(T45 TLM L3 REVIEW) 생성 — L4 DONE 이동은 사용자 승인 대기.
  **위 §6 항목들의 `graphify_engine/`·`ingestion/`·`agent-view/` 등 구 경로 언급은
  당시 기록으로 보존**(T39 CRZ 소급 치환 금지) — 최신 경로는 05번 설계서·README 참조.

- 🔶 **디자인 시안 게이트 재정의 — 설계만(2026-07-19)**: 사용자 지적("MANDATORY 요구사항
  마다 매번 게이트가 걸리는 것처럼 읽힌다") 반영해 `01_PHASE1_DATA_MODEL.md` §5를
  §5-1(`ProjectConfig.project_design_draft_confirmed` 프로젝트 전역 플래그)·
  §5-2(확정 시 개별 요구사항 게이트 자동 스킵 + `design_draft_gate_override` 수기
  예외)로 보강, `04_PHASE0_PROJECT_REGISTRATION.md` §7-A(플래그를 세우는 STEP 6 단계)
  추가. 코드 미변경(설계만).

- ✅ **API 서버 설계 심층재검토(DRL) + 최소 구현 완료(2026-07-19)**: `plans/_plan/
  07_API_SERVER_ARCHITECTURE.md`를 동시성·에러처리·T99 envelope 관점에서 재검토(§DRL) —
  read-modify-write 경합(Critical) 발견, `threading.Lock` 직렬화 + 단일 프로세스 기동
  가이드로 보강 / `RequirementRecord`에 `contains_pii`·`doc_filename` 필드가 실제로는
  없다는 갭(Critical) 발견, `getattr` 안전 기본값(False)으로 해소하고 정직하게 한계
  기록. 이어서 `backend/adapters/api/requirements_api.py`(2개 엔드포인트)·
  `backend/server.py`(FastAPI 앱 조립, StaticFiles 마운트) 구현 — 서버 프로세스는
  실행하지 않음(코드만). `tests/test_requirements_api.py`(8개, TestClient) 신설,
  `pytest tests/` 69개 전부 pass(기존 61 + 신규 8, 회귀 0).

- ✅ **agent 배차·오케스트레이션·완료보고 구현 완료(2026-07-19)**: `plans/_plan/
  06_AGENT_DISPATCH_REPORTING.md` 설계대로 `agent_dispatch_resolver.py`(§3, search_fn
  의존성 주입 포트)·`task_dispatch_service.py`(§4, 우선순위+CLEAR/OVERLAP 배차계획)·
  `completion_report_service.py`(§6, git diff --stat 파싱)·`agent_role_usage_log.py`(§9-2,
  append-only 로그)를 신규 구현, `tests/`에 14개 테스트 추가(기존 23개 + 신규 14개 = 37개
  전부 pass). 실제 `search_all` 연동·§9-2 assetize 자동 흡수·§4 실제 Agent() 호출은 이번
  범위 밖(`plans/_open/agent-dispatch-impl-2026-07-19/status.json` §excluded_from_scope
  참조). T45 TLM L3 REVIEW — L4 DONE 이동은 사용자 승인 대기.

- ✅ **영역×계층 기반 병렬 오케스트레이션 그룹핑 구현 완료(2026-07-19)**: `plans/_plan/
  02_PHASE2_ORCHESTRATION_PREVIEW.md` §3-1대로 `backend/domain/requirements/
  conflict_detection.py`에 `group_tasks_by_area_layer()`(domain_code×layer_code로
  Task 묶기) + `detect_conflicts_within_groups()`(그룹별 `detect_area_conflicts()` 재적용,
  §3-2 "이중 안전망") 추가. layer_code는 Task가 아닌 Requirement 쪽 필드라서(실측:
  `RequirementRecord.layer_code`) domain 계층이 adapters(RequirementStore)를 역참조하지
  않도록 `layer_by_req_id` dict를 호출자가 주입하는 방식으로 구체화(설계서 원안보다
  헥사고날 경계를 더 엄격히 지킴). `tests/test_task_manager.py`에 3건 추가, 전체 51개
  pytest 전부 pass(회귀 0).

- ✅ **§3-1/§3-2 프롬프트 조립 공식 보강 부분구현 완료(2026-07-19)**:
  `dispatch_execution_planner.build_execution_prompts()`가 배차계획(domain_code/
  agent_command)만 조립하던 것에 Requirement 원문 발췌(source_location 포함)와
  solution_stack(Task+Requirement 병합)을 추가로 조립하도록 확장. 조회는
  `requirement_lookup` 콜러블 주입 방식(직전 사이클 패턴과 일관, 미제공 시 하위호환
  유지)으로 처리, `task_dispatch_service.dispatch_tasks()`의 배차계획 dict에도
  `source_req_ids`/`solution_stack`을 함께 실어 보냄. `§2 ProjectDomainSnapshot`(AST
  추출기)은 별도 설계 결정 필요로 이번 사이클 범위 밖 — 미구현. `tests/`에 5건 추가,
  전체 56개 pytest 전부 pass(회귀 0).

- ✅ **§2 ProjectDomainSnapshot — 1번째 청크(프로젝트 구조만) 구현 완료(2026-07-19)**:
  `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §2-2 설계대로 `backend/application/
  services/project_domain_snapshot_service.py`(`build_project_domain_snapshot()`,
  기존 `ast_extractor.extract_functions_and_calls()` 재사용해 `backend/` 하위 .py를
  스캔·집계, 파일 수 상한(`max_files`)으로 대용량 hang 회피)와 `backend/adapters/
  persistence/project_domain_snapshot_store.py`(`TaskStore`/`ProjectConfigStore`와
  동일 JSON 스토어 패턴)를 신규 구현. §2-1 표의 나머지 5개 실측 대상(기능·환경·프로세스·
  공통화·기술)은 반환 dict에 `NOT_IMPLEMENTED` 상태만 채우고 실제 추출은 다음 청크로
  명시 이월, 이전 스냅샷과의 diff/이력비교 로직도 다음 청크로 이월(과잉설계 회피).
  `tests/test_project_domain_snapshot_service.py` 5건 추가, 전체 61개 pytest 전부
  pass(회귀 0). 남은 청크: 환경·프로세스·공통화·기술.

- ✅ **§2 ProjectDomainSnapshot — 환경 청크(2/5) 구현 완료(2026-07-19)**:
  `backend/adapters/extractors/environment_extractor.py`(`extract_environment_config()`)
  신규 구현 — `infrastructure/` 하위 설정파일을 정교한 파서 없이 단순 텍스트 스캔:
  `.env.*.example`은 `^([A-Z_]+)=` 정규식으로 **키 이름만**(값 절대 미추출, T99 AIOS 보안
  원칙) 추출, `.md`는 첫 heading 한 줄만, `.conf.example`은 존재+크기(bytes)만. 그 외 파일
  (`schema.py`·`requirements.txt` 등)은 `type=other`로 경로만 정직하게 기록(조용히 누락
  금지, T98 AIP). `project_domain_snapshot_service.build_project_domain_snapshot()`의
  `environment` 키가 이 결과로 채워지도록 연결(기존 `NOT_IMPLEMENTED` 대체), 프로세스·
  공통화·기술 3개는 여전히 `NOT_IMPLEMENTED`. `tests/test_project_domain_snapshot_
  service.py`에 4건 추가(값 비노출 보안 테스트 포함), 전체 72개 pytest 전부 pass(회귀 0).
  남은 청크: 프로세스·공통화·기술.

- ✅ **PII 게이트 실제 결함 수정 완료(2026-07-19)**: 직전 DRL 재검토가 `getattr` 기본값으로만
  "정직하게 기록"해뒀던 갭이 실제로는 게이트가 **항상 통과(no-op)** 하는 결함이었음을 확인 —
  `RequirementRecord`에 `contains_pii`·`doc_filename` 필드를 실제로 추가하고, `backend/
  domain/requirements/pii_detector.py`(classifier.py와 동일한 결정론적 키워드/정규식 스타일,
  신규 ML/외부 API 없음)를 신설해 `RequirementStore.add_from_classification()` 시점에
  `contains_pii`/`pii_scan_matched`를 실제로 채우도록 수정. `doc_filename`은 `DocumentStore`의
  `{doc_id}.md` 규칙대로 저장 시점에 유도(API 레이어의 `getattr` 폴백은 구버전 데이터 호환용
  으로만 유지). 한계: 정규식/키워드 매칭이라 문맥 이해 불가, 미탐(false negative)보다
  오탐(false positive)을 허용하는 비대칭 설계 — 완전한 PII 탐지가 아니며 사람의 최종 확인이
  여전히 필요(정직하게 기록, T98 AIP). `tests/test_pii_detector.py` 신설(6건) +
  `tests/test_requirement_store.py`(3건)·`tests/test_requirements_api.py`(1건 교체 포함)
  보강, 전체 82개 pytest 전부 pass(기존 69 + 신규 13, 회귀 0).

- ✅ **`getattr` 폴백 전수감사 완료(2026-07-19)**: 위 PII 게이트 결함이 반복 가능한 패턴인지
  `backend/` 전체(제외: `adapters/extractors/`·`project_domain_snapshot_service.py`, 병렬
  작업 중)를 `getattr(` 호출 기준으로 전수 스캔 — 총 3건 확인
  (`requirements_api.py:114` `contains_pii`, `requirements_api.py:136` `doc_filename`,
  `dispatch_execution_planner.py:39` `_resolution_field`). 3건 모두 대상 클래스에 필드가
  **실제로 존재**함을 확인(`RequirementRecord.contains_pii`/`doc_filename`은 직전 라운드에서
  이미 실필드화됨, `AgentResolution`의 `agent_command`/`source`/`score`도 실필드) — 잠재
  결함 0건, 신규 수정 없음. 앞의 두 건은 구버전 JSON 스토어 파일 호환용 의도된 폴백(저위험,
  건드리지 않음), 세 번째는 dict/dataclass 겸용 조회를 위한 의도된 다형성 처리(저위험).
  `pytest tests/` 82개 전부 pass(회귀 0, 신규 테스트 없음 — 수정 사항 없어 T98 AIP상 과잉
  테스트 작성 회피).

- ✅ **§2 ProjectDomainSnapshot — 프로세스 청크(3/5) 구현 완료(2026-07-19)**: 설계서
  §2-1 "프로세스" 행이 가정한 `governance/workflows/` 디렉터리가 이 프로젝트에 실제로
  존재함을 Glob으로 실측 확인(`SERVER-EXECUTION_POLICY.md`·`RECALL_UNIVERSAL_SEARCH_GUIDE.md`)
  — 대체 후보 없이 설계서 그대로 `backend/adapters/extractors/process_extractor.py`
  (`extract_process_docs()`) 신규 구현, `governance/workflows/*.md`를 단순 텍스트 스캔해
  제목(첫 heading)·섹션 목록(전체 heading 줄)만 추출(본문 내용 미추출,
  environment_extractor.py와 동일한 단순 스캔 원칙). `project_domain_snapshot_service.
  build_project_domain_snapshot()`의 `process` 키가 이 결과로 채워지도록 연결(기존
  `NOT_IMPLEMENTED` 대체), 공통화·기술 2개는 여전히 `NOT_IMPLEMENTED`.
  `tests/test_project_domain_snapshot_service.py`에 2건 추가(회귀 테스트 1건 조정 포함),
  전체 84개 pytest 전부 pass(회귀 0). 남은 청크: 공통화·기술.

- 🔶 **7번째 축(디자인 시안 선행 게이트) 설계 추가(2026-07-19, 설계만 — 코드 미변경)**:
  `plans/_plan/01_PHASE1_DATA_MODEL.md` §2-5~§2-7·§5·§6(신규 `design_draft_gate` 필드
  — MANDATORY/NOT_MANDATORY/STRATEGIC_MANDATORY, classifier 자동판정 의사코드,
  `status_history` 패턴 재사용한 수동 override, 뼈대 단계 게이트 전략) +
  `04_PHASE0_PROJECT_REGISTRATION.md` §7(STEP 6 완료화면 배너 체크포인트, §6-A와 레벨
  구분 명시) 추가. `backend/` 구현·`classifier.py`/`requirement_store.py` 수정은 이번
  사이클 범위 밖(사용자 지시 — 설계만).

- ℹ️ **AEGIS 전역 명령어 0-G절 추가(2026-07-19, 사용자 명시 승인)**: 이 프로젝트 세션에서
  AEGIS 전역 인프라(`D:\aegis\base\05_commands\slash\ao.md`·`autobuild.md`·`autolp.md` +
  `D:\aegis\.claude\agents\autonomous-orchestrator.md`)를 수정 — 목적 미명시 슬래시 호출 시
  직전 출력 기반 충돌검토+뼈대우선 기본착수(0-G) 원칙 추가. 이 프로젝트 자체 헌법·설계는
  변경 없음(로그 기록만, 범위는 위 4개 AEGIS 파일 한정).

- ✅ **REC(녹음) STT 실제 엔진 연결 완료(2026-07-20)**: `voiceAW`(별도 프로젝트,
  읽기 전용 조사)의 `batch_stt.py` 패턴을 참고(코드 복사 아님)해
  `backend/adapters/parsers/faster_whisper_engine.py` 신규 — `speech_to_text_adapter.py`의
  `stt_engine` 콜백을 실제 faster-whisper(tiny 모델, 로컬 세션 전제로 voiceAW의
  large-v3-turbo와 다르게 축소, 과잉설계 회피)로 구현. VAD 파라미터(`min_silence_duration_
  ms=300`·`speech_pad_ms=200`)는 voiceAW 실측값 그대로 채택. 실제 오디오 end-to-end는
  미검증(모델 다운로드 필요, `@pytest.mark.skip` 테스트로만 존재). 전체 113개 pytest pass
  + 1 skip, 회귀 0. 상세: `plans/_plan/08_RECORDING_STT_STRATEGY.md` §7.

- ✅ **§2 ProjectDomainSnapshot 5/5 청크 전부 구현 완료(2026-07-19)**: 남은 2개(공통화·기술)
  구현. 공통화: `backend/adapters/extractors/commonization_extractor.py`
  (`extract_solution_stack_usage()`) 신규 — 파일 스캔이 아니라 호출자가 주입한
  `RequirementRecord.solution_stack`/`Task.solution_stack`(이미 메모리에 있는 데이터)의
  재사용 빈도를 순수 집계. 기술: `backend/adapters/extractors/technology_extractor.py`
  (`extract_technology_stack()`) 신규 — `backend/adapters/parsers/router.py`의
  `FORMAT_STRATEGY`를 텍스트 스캔이 아니라 `importlib`로 실제 모듈을 import해 읽음(dict
  literal 재파싱보다 정확·근거는 해당 모듈 docstring) + 공통화 집계를 합쳐 기술 스택 목록
  생성. `project_domain_snapshot_service.build_project_domain_snapshot()`에 `requirements`/
  `tasks`/`router_module_path` 선택적 파라미터(기본값 None/실제 경로) 추가해 하위호환
  유지, `commonization`·`technology` 키가 `NOT_IMPLEMENTED` 대신 실값으로 채워짐.
  `tests/test_project_domain_snapshot_service.py`에서 옛 "NOT_IMPLEMENTED" 회귀 테스트를
  "5/5 구현 완료 + NO_DATA 정직 처리" 테스트로 교체하고 4건 신규 추가, 전체 87개 pytest
  전부 pass(기존 84 + 신규 3, 회귀 0). 이제 이월 항목은 이력(diff) 관리뿐(§2-2).

- ✅ **design_draft_gate 코드 구현 완료(2026-07-19)**: `plans/_plan/01_PHASE1_DATA_MODEL.md`
  §2-5~§2-7·§5-1·§5-2와 `plans/_plan/04_PHASE0_PROJECT_REGISTRATION.md` §7·§7-A 설계를
  그대로 구현. `backend/domain/requirements/classifier.py`에 `DESIGN_GATE_KEYWORDS` +
  `classify_design_gate()`(MANDATORY/NOT_MANDATORY/STRATEGIC_MANDATORY 3지 판정, 동시매칭
  시 STRATEGIC_MANDATORY 상향) 추가, `ClassificationResult`에 `design_draft_gate`/
  `_confidence` 필드 추가. `RequirementRecord`(requirement_store.py)에
  `design_draft_gate`/`_confidence`/`_history`/`_override` 필드 + `set_design_draft_gate()`/
  `set_design_draft_gate_override()` 추가(기존 `status_history` 이력 패턴 재사용, 신규
  이력클래스 발명 없음). `ProjectConfig`(project_config_store.py)에
  `project_design_draft_confirmed`/`_by`/`_at` 추가. §5-2 게이트 판정 순수함수는 신규 파일
  `backend/domain/requirements/design_gate.py`의 `evaluate_design_draft_gate()`로 분리
  배치(conflict_detection.py는 Task 충분성/충돌이라는 별개 관심사라 혼재 방지). 신규 테스트
  14건 포함 전체 101개 pytest 전부 pass(회귀 0).

- ✅ **REC(녹음) STT ingestion 스캐폴딩 완료(2026-07-19)**: sibling 프로젝트
  `D:\projects\products\chatAW`·`chatAWV2`를 읽기 전용 조사(수정 없음) — chatAWV2는
  음성 관련 코드가 전무(grep 매치는 전부 오탐), chatAW는 브라우저 Web Speech API의
  얇은 래퍼일 뿐 서버측 STT 파이프라인이 없고 오디오도 저장하지 않음(실제 엔진은 별도
  프로젝트 `voiceAW`에 있으나 이번 사이클 조사 범위 밖으로 명시적으로 남김). 이 프로젝트
  Python 환경에 `faster-whisper` 1.2.1이 이미 설치돼 있음을 `pip list`로 실측 확인해
  엔진 선택 근거로 채택. `backend/domain/chunking/chunk.py`에 `timestamp_start_ms`/
  `timestamp_end_ms` 필드 추가(02_PHASE2 §1-2에서 3차 이후로 미뤄뒀던 것), `router.py`
  `FORMAT_STRATEGY`에 `.wav`/`.mp3`/`.m4a` → `speech_to_text` 매핑 추가, 신규
  `backend/adapters/parsers/speech_to_text_adapter.py`(`SpeechToTextAdapter` —
  `stt_engine` 콜백 미주입 시 `NotImplementedError`, 실제 STT 호출 코드는 작성하지
  않음) 구현. `codes.py`의 `REC` 설명을 "스캐폴딩 완료, 실제 엔진 연결 미구현"으로
  갱신. 상세 설계·MPCR 7관점 검토는 `plans/_plan/08_RECORDING_STT_STRATEGY.md` 참조.
  신규 테스트 9건 포함 전체 110개 pytest 전부 pass(회귀 0).

- ✅ **requirements.html/preview.html — 백엔드 API 실연결 완료(2026-07-20)**: 두 화면이
  지금까지 정적 `frontend/data/requirements.json`/`documents/*.md`만 fetch하고 이미
  구현된 `backend/adapters/api/requirements_api.py`(`POST /requirements/{req_id}/status`,
  `GET /requirements/{req_id}/preview`)를 전혀 호출하지 않던 실측 갭을 메웠다.
  `requirements.html`에 REQ ID 클릭→`preview.html?req_id=...` 이동 + 액션 열(수용/반려/
  철회, 반려·철회는 사유 프롬프트 필수) 추가. `preview.html`에 §2-4 PII 클릭스루 게이트
  (`contains_pii`/`requires_pii_confirmation` 확인 후 열람, 확인 시 `confirm_pii=true`로
  재요청해 `preview_access_log.jsonl` 접근기록 남김) + 동일한 상태변경 액션 버튼 추가.
  API 경로는 절대호스트(`http://127.0.0.1:8000` 등) 대신 root-absolute 상대경로
  (`/requirements/...`)를 채택 — `backend/server.py`가 `StaticFiles(frontend, html=True)`를
  `"/"`에 마운트해 화면과 API가 같은 오리진에서 서빙됨을 curl 스모크로 실측 확인했다(신규
  API·백엔드 코드 변경 없음, CRZ). 4xx/5xx는 envelope의 `error.message`를 alert/콘솔로
  표시(방치 없음). 백엔드 코드 변경이 없어 신규 회귀 테스트는 추가하지 않았다(과잉 테스트
  방지) — 전체 113개 pytest(+1 skipped) 그대로 pass. 정직한 한계: 이 세션은 브라우저
  렌더링 자체를 확인할 수 없다 — curl로 API 응답 계약만 실측했고, HTML/JS 로직의 실제
  브라우저 동작은 미검증으로 남긴다.

- ✅ **faster-whisper 실제 오디오 e2e 검증 완료(2026-07-20)**: `tests/test_faster_whisper_
  engine.py`의 `@pytest.mark.skip` 실제 오디오 테스트를 해제하고 실행 — Windows SAPI로
  합성한 실제 음성 오디오(`tests/fixtures/sample_speech_ko.wav`)에 `tiny` 모델
  (`Systran/faster-whisper-tiny`, HuggingFace 캐시 자동 다운로드·재사용 확인)로
  `transcribe()`를 실호출해 `SpeechSegment(text='Hello, this is a short test recording
  for the speech to text pipeline verification.', start_ms=0, end_ms=5000)`를 실제로
  반환받았다(합성 원문과 텍스트 일치). 상세는 `plans/_plan/08_RECORDING_STT_STRATEGY.md`
  §7-5 참조. 전체 114개 pytest 전부 pass, **0 skipped**(기존 113 + skip 해제 1건, 회귀 0).

- ✅ **§2 ProjectDomainSnapshot 이력(diff) 관리 구현 완료(2026-07-20)**: §2-2 docstring이
  언급해온 "이전 스냅샷과 diff"를 구현 — `project_domain_snapshot_store.py`에
  `load_previous()`(스토어가 프로젝트당 파일 1개만 다루는 스코프라 `load()`의 의도 명확화
  별칭, 신규 저장 로직 없음) + `project_domain_snapshot_service.py`에 `diff_snapshots
  (old, new)`(청크별 ADDED/REMOVED/UNCHANGED/CHANGED 얕은 키 비교, 정교한 구조적 diff
  아님) 신규 추가. `build_project_domain_snapshot()` 자체는 변경하지 않음(하위호환 유지).
  `plans/_plan/` 8개 설계문서를 `plans/_done/`의 2개 완료 트랙(agent-dispatch-impl·
  refactor-hexagonal)과 대조 확인 — 05번·06번 설계서는 이미 그 두 트랙의 `design_ref`로
  연결돼 있어 중복 없음. 이번 세션 나머지 완료 항목(API서버·배차확장·PII게이트·
  ProjectDomainSnapshot 5/5+이력관리·STT·design_draft_gate)은 이 §6 로그의 반복된 전례
  (직전 사이클들이 일관되게 "작고 자기완결적 추가는 새 트랙 불필요, §6 로그로 충분"으로
  판단해온 패턴 — 위 getattr 전수감사·오케스트레이션 그룹핑·프롬프트 조립 보강 등)를
  그대로 적용해 신규 `plans/_open/` 트랙을 만들지 않기로 판단함(T45 TLM 라이프사이클
  불필요 판정). `tests/test_project_domain_snapshot_service.py`에 5건 추가, 전체 119개
  pytest 전부 pass(회귀 0).

- ✅ **프론트엔드 화면 흐름 연결 완료(2026-07-20)**: 근본원인 — 지금까지의 개발 사이클이
  `index.html`·`project-setup.html`·`requirements.html`·`preview.html` 각 화면을 매번
  좁게 스코프 지정해 개별 제작했고, "전체 사용자 여정을 잇는 작업" 자체가 어느 사이클
  지시에도 포함된 적이 없어 화면 간 이동 링크가 통째로 누락돼 있었다(단순 기능 추가
  누락이 아니라 스코프 설계 관행의 반복된 결과 — 재발 방지 가치가 있는 기록). 조치:
  `index.html`을 Phase 1.4 죽은 placeholder(`core_was_block` 언급, 링크 0개)에서 실제
  시스템 진입점으로 전면 재작성, `frontend/styles/nav.css` + 정적 HTML 네비게이션 바를
  `project-setup.html`/`requirements.html`/`preview.html` 상단에 삽입(현재 단계 하이라이트
  + "처음으로" 링크), `project-setup.html` STEP 6(완료 확인)에 "요구사항 목록으로 이동"
  버튼 추가. workbase `wizard.html`의 단계 인디케이터 UX 패턴만 벤치마킹(SPA 통합 아님).
  curl+grep으로 4페이지 200 응답 + 실제 href 존재 확인, `pytest tests/` 119개 전부
  pass(회귀 0). 한계: 페이지 단위 이동이라 상태 공유는 `localStorage`/URL 쿼리 수준에
  그치고 진짜 SPA는 아니다.

- 🔶 **청킹/배차 설계 심층 보강 — 설계만(2026-07-20)**: 사용자가 "청크→분류→채번" 요약이
  얕다고 구체적으로 지적한 3가지를 반영해 설계를 보강했다(코드 미변경, `frontend/`·
  `backend/` 실측만 하고 수정하지 않음) — ①**청킹 검수 순환 루프 미명시**: 문서등록→
  청킹→결과확인→"맞으면 저장, 틀리면 재청킹"의 순환이 서술돼 있지 않았던 것을
  `02_PHASE2_ORCHESTRATION_PREVIEW.md` §5(재청킹 요청 액션 + `rechunk_queue.jsonl` +
  `supersedes_req_id`)로 보강. ②**청킹 시각화가 REQ 1건 하이라이트에 그침**: "이 구분이
  청킹되었습니다"를 문서 전체 단위로 보여주는 심층 시각화가 없었던 것을 같은 문서 §6
  (문서 전체 청크 경계 뷰 — 청킹 누락·중복 구간까지 색으로 진단)으로 보강. ③**요구사항별
  작업상태·배정agent 비노출**: `agent_dispatch_resolver.py`·`task_dispatch_service.py`
  (배차 로직)는 이미 구현돼 있으나 그 결과가 `RequirementRecord`에 되먹임되지 않아 화면에
  보이지 않던 것(실측 확인 — 필드 자체 부재)을 `06_AGENT_DISPATCH_REPORTING.md` §10
  (`assigned_agent_command`·`work_status` 신규 필드 + API·UI 노출 설계)으로 보강. 3건
  전부 재발 방지 가치 있는 지적(구현 로직과 사람이 보는 화면 사이의 되먹임 경로 누락
  패턴)이라 이 §6 로그에 남긴다 — 구현은 사용자 승인 후 별도 턴.

- ✅ **GNB/LNB 공통 셸 구조 적용(2026-07-20)**: 직전 사이클의 "화면 상단 브레드크럼
  연결"(2026-07-20 앞 항목의 `nav.css`/`jnav-bar`)이 여전히 화면마다 독립된 링크 나열일 뿐
  진짜 시스템 셸이 아니라는 재지적을 반영 — 모든 업무 화면이 공유하는 GNB(상단)+LNB(좌측
  업무영역 메뉴)+컨텐츠 영역 구조로 격상했다. 구현: `frontend/partials/shell-nav.html`
  (공통 마크업 조각) + `frontend/js/shell-loader.js`(fetch+innerHTML 삽입, 실패 시 최소
  텍스트 네비게이션 폴백) + `frontend/styles/shell.css`(그리드 레이아웃) — vanilla JS
  컴포넌트 로드 방식(B안)을 택함, 복잡도가 감당 가능해 정적 반복 삽입(A안)으로 폴백하지
  않음. `project-setup.html`/`requirements.html`/`preview.html` 3개 업무 화면에 적용,
  `index.html`은 진입 전 랜딩 화면 특성상 셸 미적용(파일 내 주석으로 근거 명시). LNB 메뉴는
  `plans/_plan/00_INDEX.md` 기준 3개 구현 화면(프로젝트 설정·요구사항 관리·청크 미리보기)
  + 2개 준비중 항목(문서/청킹 관리, 배차 현황 — §10 설계만 존재)으로 구성, 준비중 항목은
  비활성 `<span>`으로 처리(클릭 시 동작하는 것처럼 보이지 않게, T98 AIP 과장 금지). 옛
  `frontend/styles/nav.css`(대체된 브레드크럼 스타일)는 더 이상 어떤 HTML도 참조하지 않아
  삭제(단, 위 2026-07-20 앞 항목의 이력 서술 자체는 CRZ 감사 이력이므로 수정하지 않음).
  curl로 4페이지 200 + 서빙된 HTML에 `ai-gnb-slot`/`ai-lnb-slot`/`shell-loader.js`/
  `shell.css` 존재 확인, `partials/shell-nav.html` 응답에 3개 활성 메뉴 + 2개 "준비중"
  배지 확인. `pytest tests/` 119개 전부 pass(회귀 0). 한계: 여전히 페이지 단위 이동(진짜
  SPA 아님), "준비중" LNB 항목은 자리만 있고 실제 화면·API는 없음, GNB 사용자 표시는
  `localStorage`의 `aegis_actor` 문자열을 그대로 보여주는 수준(실제 인증 없음).

- ✅ **§6 문서 전체 청크 경계 시각화 뷰 구현 완료(2026-07-20)**: `02_PHASE2_ORCHESTRATION_
  PREVIEW.md` §6 설계대로 `backend/adapters/api/documents_api.py`(`GET /documents/{doc_id}/
  chunk-map` 신규, `requirements_api`의 envelope·에러코드·PII 게이트 로그 재사용, 신규 로직
  최소화) + `frontend/views/documents.html`(신규 — 문서 전체 원문 + 그 문서에서 나온 모든
  REQ의 청크 경계를 동시에 표시, 경계점 스윕 알고리즘으로 gap(미청킹)·overlap(겹침, 2건
  이상 어떤 개수든 일반해) 계산, 블록 클릭 시 읽기전용 팝오버 + preview.html 이동 링크 —
  §2 preview.html의 상태변경 액션과 중복시키지 않음, GNB/LNB 셸 적용). §6-3 진입점은 (B)
  신규 화면으로 확정 — `frontend/partials/shell-nav.html`의 "문서/청킹 관리" 준비중 항목을
  이 화면으로 활성화하는 변경은 그 파일 소유 병렬 에이전트에게 위임(직접 수정 안 함, 필요
  변경사항만 명시 전달). `tests/test_documents_api.py` 4건 신규, `pytest tests/` 123개
  전부 pass(회귀 0), uvicorn 실기동 curl 스모크로 `/documents/{doc_id}/chunk-map`
  404/200·`documents.html` 200 확인 후 서버 종료·포트 회수.

- ✅ **§5 청킹 검수 루프 + §10 작업상태·배정agent 노출 구현 완료(2026-07-20)**:
  `02_PHASE2_ORCHESTRATION_PREVIEW.md` §5·`06_AGENT_DISPATCH_REPORTING.md` §10 설계대로
  `RequirementRecord`에 `supersedes_req_id`/`assigned_agent_command`/`work_status`/
  `work_status_updated_at` 필드 추가 + `RequirementStore.request_rechunk()`(REJECTED 재사용
  + `rechunk_queue.jsonl` append)·`set_work_status()` 신설 + `task_dispatch_service.
  sync_requirement_work_status()`(§10-2 집계 우선순위 BLOCKED>IN_PROGRESS>DISPATCHED>
  DONE>NOT_DISPATCHED 구현) + `POST /requirements/{req_id}/rechunk`·`GET /requirements`·
  `GET /requirements/{req_id}` API 신설(뒤 두 API는 설계 시점 존재를 전제했으나 실측 결과
  없어 이번에 신설, 하위호환 유지) + `requirements.html`에 "배정 agent"·"작업상태" 컬럼과
  "재청킹 요청" 버튼 추가(GNB/LNB 셸 구조 무변경, 컨텐츠 영역 안에서만 수정). 테스트 20건
  신규(`test_requirement_store.py` 5·`test_requirements_api.py` 6·`test_task_dispatch_
  service.py` 4 + 기존 파일 보강), `pytest tests/` 138개 전부 pass(회귀 0), uvicorn 실기동
  curl 스모크로 목록/단건/rechunk 성공·사유누락 422·큐 append 확인 후 서버 종료·포트 회수.

- ✅ **Phase 4.2 Task 상태 머신 + 통신 API 구현 완료(2026-07-21)**: `00_DESIGN_TOC.md` Phase
  4.2가 "미구현"으로 남아 있던 것을 검토하다 실측으로 확인한 갭 — `Task.status` 필드는
  `backend/domain/entities/task.py` docstring 주석으로만 전이 규칙(DRAFT→READY→
  IN_PROGRESS→DONE/BLOCKED)을 표현했을 뿐, 실제로 그 규칙을 강제하는 코드가 전혀 없었다
  (`TaskStore`에 상태 변경 메서드 자체가 없어 DRAFT에서 DONE으로 바로 덮어써도 막을 방법이
  없었음). `backend/domain/requirements/task_state_machine.py`(전이 그래프 검증 + BLOCKED
  reason 필수, `RequirementRecord.set_status()` 패턴 CRZ 재사용) + `TaskStore.set_status()`
  (검증 통과분만 `status_history` 감사로그 append) + `POST /tasks/{task_id}/status` API
  신설(`GET /tasks`·`GET /tasks/{task_id}` 포함, `requirements_api.py`의 envelope·락·
  에러코드 패턴 그대로 재사용) — 이 API가 배차된 agent가 진행상황을 보고하는 실제 통신
  경로다("MCP 프로토콜"이라는 별도 프로토콜을 새로 구현한 것은 아님, 과장 금지 T98 AIP).
  신규 pytest 18건(`test_task_state_machine.py` 7·`test_task_store_set_status.py` 5·
  `test_tasks_api.py` 6), `pytest tests/` 156개 전부 pass(회귀 0), uvicorn 실기동 curl
  스모크로 DRAFT→DONE 직행 거부·사유없는 BLOCKED 거부·정상 전이(DRAFT→READY) 반영을 각각
  확인 후 서버 종료·포트 회수. 부수 작업(사용자 지시): `restart.sh`에서 `stop.sh`(종료
  전용)를 분리해 재사용하도록 리팩토링, 3회 반복 실행(기동→단독종료→재기동)으로 정상 동작
  확인. 남은 것: Phase 4.3(병렬 작업 통제 + Distributed Lock)은 여전히 미구현.

- ✅ **Task 생성 API + Phase 4.3 Distributed Lock 구현 완료(2026-07-21)**: 이전 항목이 남긴
  두 가지를 이어서 처리(사용자 지시, §PCM CLEAR 병행) — ①`POST /tasks` 신설(`TaskStore.
  generate_task_id()`가 `REQ-{코드}-{번호}`와 동일 원칙으로 `TASK-{domain_code}-{일련번호}`
  서버 채번, 지금까지 Task 생성이 코드 레벨에서만 가능했던 갭을 메움) ②`backend/adapters/
  persistence/task_lock_store.py`(파일 기반 배타 락 — `detect_area_conflicts()`가 계획
  단계 감지만 할 뿐 실행을 막지 않던 갭을 메움, AEGIS `claim_llm_task.py`와 동일 원칙을
  프로젝트 로컬로 재구현) + `TaskStore.set_status()`에 배선(IN_PROGRESS 진입=점유 시도,
  이탈=자동 해제). 신규 pytest 11건(`test_task_lock_store.py` 4·상태전이 락 배선 3·API
  생성 4), `pytest tests/` 167개 전부 pass(회귀 0). uvicorn 실기동으로 겹치는 impact_scope
  두 Task 생성 → T1 IN_PROGRESS 성공 → T2 IN_PROGRESS 시도 422 거부(메시지에 점유 Task ID
  명시) → T1 DONE 처리로 락 해제 → T2 IN_PROGRESS 재시도 성공까지 전 과정을 curl로 실측
  확인. Phase 4(자율 오케스트레이션 및 멀티 에이전트 협업) 4.1~4.3 전부 구현·검증 완료.

- ✅ **Phase 5 증거 기반 검증 루프 1차 구현 완료(2026-07-21)**: 사용자 지시(다음작업 순서대로
  진행) — 5.1 E2E: `tests/test_e2e_task_lifecycle.py`(생성→READY→IN_PROGRESS 락획득→완료
  보고서 조립→DONE 락해제 전 생애주기 + 병렬 락 통제 시나리오, TestClient로 HTTP API 관통).
  5.2 정적 완전성 검증: `tests/test_task_state_machine_exhaustive.py`(5x5=25개 전이 조합 전수
  대조 + 자기전이 불가·DONE terminal·전상태 커버리지 불변식). 5.3 HITL+서킷 브레이커:
  `task_state_machine.py`(`BLOCKED_CIRCUIT_BREAKER_THRESHOLD=3`, `check_circuit_breaker()`) +
  `TaskStore.set_status()`에 배선(BLOCKED 3회 도달→`needs_escalation=True` 트립→
  `override_escalation=True`(사람 검토 확인) 없이는 전이 거부) + `POST /tasks/{id}/status`에
  `override_escalation` 파라미터 노출. **정직 기록(과장 금지 T98 AIP)**: "Verifier 에이전트"는
  자율 에이전트가 아니라 pytest E2E 스위트, "Red Teaming"은 공격 시뮬레이션이 아니라 전이
  그래프 정적 완전성 검증, "서킷 브레이커"는 간단한 임계값 카운터(정교한 CB 라이브러리 아님).
  신규 pytest 38건, `pytest tests/` 205개 전부 pass(회귀 0). uvicorn 실기동으로 3회 BLOCKED→
  트립→override 없는 전이 422→override 승인→해제 전 과정 실측 확인. Phase 5(5.1~5.3) 1차
  구현 완료 — Phase 6(자가 진화 및 지식 자산화)이 남은 마지막 Phase.

- ✅ **DONE 오검증 방지(HITL 게이트 확장) 구현 완료(2026-07-21, /autobuild)**: 직전 항목이 남긴
  "다음 작업" 2개 후보 중 **Phase 6(자가 진화 및 지식 자산화)은 착수 전 reconcile-first
  게이트로 재검토한 결과 §1·§4 드리프트 체크리스트에 명시적으로 위배**(§1이 "자가진화 Growth
  DNA"를 반예시로 직접 거명, §4 Q1·Q4 NO) — 2026-07-17 Phase 3 "10ms 신경망 소환" 배제
  판정과 동일 패턴이라 **사용자 명시 확인 전까지 착수 보류**(정직 중단, 임의 진행 금지).
  대신 2번(HITL 게이트를 DONE까지 확장)을 진행: `task_state_machine.REASON_REQUIRED_STATUSES`에
  `"DONE"` 추가(`{"BLOCKED", "DONE"}`) — 근거(reason) 없는 "완료됐다"는 침묵 선언을 막는다
  (T98 AIP §W-5 물증 원칙과 동일 정신, 기존 BLOCKED reason-required 패턴 그대로 재사용라
  신규 로직 아님). **정직 기록**: 이 reason이 실제 완료 여부를 자동 검증하지는 않는다(무엇을
  했는지 말해야 한다는 최소 장치일 뿐, 완전한 증거 검증 시스템은 미구현). 기존 DONE 전이
  호출부 6곳(pure 함수 테스트 2·store 테스트 2·API 테스트 1·E2E 테스트 2)에 reason 추가 +
  신규 API 테스트 1건(`test_status_change_done_without_reason_returns_422`), `pytest tests/`
  207개 전부 pass(회귀 0). uvicorn 실기동으로 reason 없는 DONE 422 거부·reason 있으면 정상
  반영을 curl로 실측 확인.

- ✅ **Phase 6.1 실패 패턴 분석(좁은 재해석) 구현 완료(2026-07-21, /autobuild — 사용자 "평식
  승인 계속 진행")**: 사용자가 Phase 6 착수를 승인했으나, §1이 "자가진화 Growth DNA"를 반예시로
  직접 거명하는 드리프트는 승인 한 줄로 사라지지 않는다고 판단해(T100 AACG "승인의 본질=목표·
  의도 명확성, 기술 실현방법은 자율") **6.1을 자율 코드 자기수정이 아닌 읽기전용 집계 리포트로
  좁게 재스코프**했다(00_DESIGN_TOC.md Phase 6 절 상단 드리프트 경고 참조). `failure_pattern_
  analysis_service.py` + `GET /analytics/failure-patterns` — UNDER_REVIEW 요구사항·
  needs_escalation Task를 집계해 표면화만 하고, 분류 규칙 자체는 사람이 개선. 신규 pytest 8건,
  `pytest tests/` 214개 전부 pass(회귀 0). 개발 중 실측 버그 2건 발견·즉시 수정(§W-5): analytics_api
  가 `from X import get_xxx_store`로 함수를 직접 가져와 테스트 monkeypatch가 무효화되던 문제(모듈
  참조로 전환), 테스트 헬퍼의 `reasons or [기본값]`이 빈 리스트를 falsy로 오판하던 문제. uvicorn
  실기동으로 불충분 Task 생성→5가지 부족사유 정확 집계 확인. **6.2·6.3은 여전히 미착수** —
  원안 그대로면 §1 위배가 명백해(자율 코드/스킬 자기수정, "정본" 개념 자체 부재) 사용자가 구체적
  범위를 좁혀 재지시하기 전까지 보류.

- ✅ **실패 패턴 리포트 화면 시각화 구현 완료(2026-07-21, /autobuild — 반복된 "다음 작업 진행,
  평식 승인 계속 진행")**: 직전 메뉴 1번(6.2/6.3)은 사용자가 반복 지시에도 구체적 범위를 새로
  좁히지 않아 여전히 진행 불가 — 0-G 기본동작으로 드리프트 없는 2번(리포트 화면 연동)을 진행.
  `frontend/views/requirements.html`에 `GET /analytics/failure-patterns`를 fetch해 요약카드
  아래 패널로 렌더링(패턴 0건이거나 API 없이 정적서버로 열렸을 때는 패널을 조용히 숨김 — 메인
  화면 동작을 방해하지 않음). 기존 배지·신뢰도바 스타일(badge-doc/badge-area/conf-bar) 그대로
  재사용(CRZ, 신규 시각 언어 없음). `node --check`로 인라인 스크립트 구문 확인 + uvicorn
  실기동으로 200 응답·패널 마크업 존재·API 실데이터 확인. **한계(정직 기록)**: 실제 브라우저
  DOM 렌더링(픽셀 단위)은 이 세션 도구로 확인 불가 — 로컬에서 직접 열어 확인 필요(기존 화면들과
  동일한 한계). `pytest tests/` 214개 전부 pass(회귀 0, 백엔드 변경 없음 — 프론트 전용 작업).

- ✅ **plans/_plan stale 상태표기 정정 + PPTX/PDF 파서 구현 완료(2026-07-22, /ao — 사용자 지시
  "비기술 제외 나머지 충돌나지않는 영역 확인해서 병렬 진행")**: 재검토 결과 `00_INDEX.md`
  ("구현 미착수(승인 대기)")·`05_REFACTOR`("L4 DONE 승인 대기")·`06_AGENT_DISPATCH`("구현은
  별도 턴")가 전부 stale이었음을 `plans/_done/` status.json·실제 코드 대조로 확인, 3개 문서
  상태표기 정정. 이어서 실제 갭 목록(HWP/PDF/PPTX 파서·SemanticBoundarySplitter·search_all
  실시간연동·STT 실오디오 검증·Phase 6.2/6.3) 중 비기술(§5 코드 범위) 항목 제외 + §PCM
  검토 후 병렬 진행 가능한 것만 착수: `backend/adapters/parsers/pptx_adapter.py`(python-pptx,
  기설치 라이브러리)·`pdf_adapter.py`(`pdfplumber` 신규 설치)를 실제 구현, `document_upload_
  service.py` `_ADAPTERS`에 등록. STT는 재확인 결과 `test_faster_whisper_engine.py`가 이미
  2026-07-20 실오디오 e2e 검증 완료했음을 발견(codes.py의 stale 주석도 함께 정정) — 별도
  구현 불요. HWP(OLE 바이너리, 적절한 순수 라이브러리 부재)·SemanticBoundarySplitter(LLM
  콜백 주입 설계 필요)·search_all 실시간연동(AEGIS측 graphify-hub 인덱싱 별도 작업, 이
  프로젝트 범위 밖)은 근거와 함께 명시적으로 보류. 합성 pptx(python-pptx)·pdf(reportlab)로
  실제 parse_to_markdown() smoke test 통과 확인 후 신규 pytest 13건 추가, `pytest tests/`
  227개 전부 pass(회귀 0). **부수 관측(정직 기록)**: `pip install pdfplumber`가 전역 Python
  3.12 환경의 Pillow를 11.3.0→12.3.0으로 올려 `streamlit`(별도 도구, pip 의존성 경고 발생)과
  버전 충돌 경고가 떴으나 실측(`import streamlit`) 결과 정상 동작 확인(현재는 문제 없음,
  향후 streamlit 쪽 이슈 발생 시 원인 후보로 참고). `document_upload_service.process_
  uploaded_file`이 아직 실제 HTTP 업로드 엔드포인트에 배선되지 않은 것도 함께 발견(테스트에서만
  직접 호출됨, `documents_api.py`가 import만 하고 라우트 미사용) — 이번 스코프 밖이라 별도
  갭으로만 기록, 수정하지 않음.

- ✅ **UI 밝은 테마 전환 + CSS 공통화 + 콤보(select) 반전 버그 근본수정 완료(2026-07-22,
  사용자 지적)**: ①**근본원인 실측**: 전 6개 view HTML(`index`·`project-setup`·`requirements`·
  `preview`·`documents`·`dispatch-dashboard`)이 `<html data-theme="dark">`를 하드코딩해
  `tokens.css`가 이미 갖고 있던 라이트 기본값(`:root`)을 무시하고 있었다(실측: grep 전수
  확인) — 하드코딩 제거만으로 밝은 톤 전환. ②**콤보 반전 버그 근본원인**: `color-scheme`
  CSS 프로퍼티 선언 누락 — 브라우저 네이티브 `<select>` 드롭다운 팝업은 페이지 CSS 변수가
  아니라 `color-scheme`을 보고 자기 배경/글자색을 정하는데, 이게 없어 팝업이 OS 기본으로
  뜨면서 페이지가 지정한 다크텍스트 색과 충돌해 흰바탕 흰글씨(또는 그 반대)로 안 보였다 —
  `tokens.css`의 `:root`/`[data-theme='dark']`에 `color-scheme: light`/`dark`를 각각
  선언해 해결(전문가 CSS 표준 기법, 신규 JS 불필요). 부가로 `select`/`input`/`textarea`
  배경을 기존 `transparent`에서 `var(--bg-primary)`로 명시(투명 배경이 팝업 겹침의 2차
  원인이었음). ③**CSS 공통화**: 6개 view에 복사돼 있던 배지(`.badge*`)·요약카드(`.summary-*`)
  ·테이블·`.actor-bar`·`.action-btn`·`.pii-gate-*`·`.topbar`·reset 등을 `frontend/styles/
  components.css`(신규)로 통합, 각 view는 이 파일을 link하고 자기 화면 전용 레이아웃만
  유지(픽셀 결과는 최대한 보존, 시각 언어 신규 발명 없음). 토큰에 `--text-muted`·
  `--border-color`·`--hover-tint`·`--bg-secondary`를 추가해 공통 CSS와 `shell.css`(GNB/LNB)
  전반의 리터럴 회색값(`#888`·`rgba(128,128,128,.X)`)을 테마 인식 변수로 치환. 신규 pytest
  없음(프론트 전용, 백엔드 무변경) — `pytest tests/` 227개 전부 pass(회귀 0). uvicorn
  실기동으로 `components.css` 200·`tokens.css`에 `color-scheme: light` 포함·전 6화면 200·
  `data-theme="dark"` 서빙 잔존 0·`select` 규칙 실제 서빙 확인. **한계(정직 기록)**: 실제
  브라우저에서 콤보를 열어 픽셀 단위로 반전 해소를 확인하는 것은 이 세션 도구로 불가 —
  `color-scheme`은 W3C 표준이 보장하는 동작이라 근거는 명확하나, 로컬에서 직접 열어
  최종 확인 권장.

- ✅ **문서 업로드 HTTP 엔드포인트 배선 완료(2026-07-22, /autobuild — 사용자 "다음작업 순차적으로
  병렬 계속 진행, 승인")**: 직전 세션이 발견한 갭("`document_upload_service.process_uploaded_file`이
  테스트에서만 호출되고 실제 라우트에 배선 안 됨")을 이어서 처리 — `documents_api.py`에
  `POST /documents/upload`(multipart file+actor) 신설, 기존 서비스 함수를 그대로 호출만
  함(CRZ, 신규 비즈니스 로직 없음). 신규 pytest 4건(txt 정상 업로드·빈 파일 422·미지원
  확장자 422·미구현 포맷(.hwp) 422), `pytest tests/` 231개 전부 pass(회귀 0). **uvicorn
  실기동 curl 스모크 3종 확인**(§W-5 물증) — txt/pptx/pdf 각각 실제 파일을 multipart로
  전송해 `{"ok":true,"chunk_count":1,...}` 정상 응답 확인 후 서버 정상 종료(포트 8899
  TIME_WAIT만 남고 LISTENING 없음, 잔존 프로세스 0 확인). **의도적 보류(RCA)**: HWP 파서는
  이번 라운드에서 착수하지 않음 — `olefile`로 PrvText(미리보기 텍스트) 스트림만 뽑는
  방법은 가능하나 그 경우 "실제 본문 파싱"이 아니라 "수백자 미리보기"에 불과해 docx/pptx/pdf
  어댑터와 같은 급의 "실제 동작 파서"라고 부르면 과장(T98 AIP)이 된다 — 전체 본문을 다루려면
  HWP v5 바이너리 레코드 포맷(zlib 압축 BodyText 섹션)을 직접 구현하거나 미유지보수
  라이브러리(pyhwp 등)에 의존해야 해 품질/유지보수 트레이드오프가 있음 — 사용자가 "미리보기만
  이라도 좋다" vs "전체 본문 파서까지 필요"를 확정해주면 그에 따라 후속 진행.

- ✅ **업로드 UI-백엔드 연결 확인 + 지원포맷 힌트 갱신(2026-07-22, /autobuild — 사용자 "다음작업
  순차적으로 병렬 계속 진행, 승인")**: `frontend/views/documents.html`을 확인한 결과 업로드
  UI(`uploadDocument()`)가 **이미 이전 세션에서 `POST /documents/upload`(file+actor
  FormData) 계약에 맞춰 구현돼 있었음**을 발견 — 직전 사이클에서 만든 백엔드 엔드포인트와
  정확히 같은 응답 필드(`doc_filename`/`chunk_count`/`requirements_created`/
  `unclassified_chunk_count`/`doc_id`)를 이미 소비하도록 짜여 있어 별도 UI 신규 개발이
  필요 없었다(즉 "프론트 업로드 UI" 후보는 이미 완료 상태였음, 중복 개발 회피). 유일한
  실제 갭은 안내 문구 stale이었음: "지원 포맷: .txt·.md·.docx"가 pptx/pdf 추가를 반영하지
  않고 있어 한 줄 갱신. `node --check`로 인라인 스크립트 구문 확인(회귀 0) + uvicorn 실기동
  으로 `documents.html` 200·갱신된 힌트 텍스트 실제 서빙 확인 + **실제 README.md 파일을
  진짜 업로드**해 청크 13개·요구사항 3건 자동채번(REQ-TECH-LLM-001 등) 확인 후 서버 정상
  종료. `pytest tests/` 231개 전부 pass(회귀 0, 프론트 텍스트 1줄 변경뿐 — 백엔드 무변경).

- ✅ **청킹 방법론 재검토(2026-07-22, 사용자 지시 — hwp/docx/pptx/txt/excel/기타 형식별 재검토)**:
  WebSearch로 2026년 RAG 청킹 모범사례를 실제 조사(출처: firecrawl.dev·futureagi.com·
  digitalapplied.com 등) — 핵심 발견 "표(table)는 산문과 섞인 채로 두지 않고 반드시 별도
  청크로 분리해야 한다"와 "구조인식(헤딩 기반) 분할이 2026 기준 여전히 권장 기본 전략"을
  확인. **현재 구현 재확인 결과**: 모든 포맷(docx/pptx/pdf/txt)이 마크다운으로 정규화된 뒤
  `HeadingBoundarySplitter`(`#` 경계 결정론적 분할)로 동일하게 청킹되는 구조는 2026 권장
  기본 전략과 **이미 일치**(슬라이드=`## Slide N`, 페이지=`## Page N`이 자연스러운 헤딩
  경계) — 근본 알고리즘 교체는 불필요. **실제 발견된 갭**: `pptx_adapter.py`·`pdf_adapter.py`
  가 표를 슬라이드/페이지 본문과 **같은 헤딩 블록에 인라인으로 삽입**하고 있어 표-산문 혼합
  청크가 만들어지던 문제(외부 모범사례 위반) — 표마다 `### Table N (Slide/Page M)` 서브헤딩을
  추가해 `HeadingBoundarySplitter`가 자연히 별도 청크로 분리하도록 수정(heading_path에
  부모 경로 보존, 문맥 손실 없음). 신규 pytest 2건(`test_chunking.py`의 표-산문 분리 검증 +
  `test_pptx_adapter.py` 서브헤딩 존재 확인), `pytest tests/` 232개 전부 pass(회귀 0).
  실제 합성 pptx(프로즈 슬라이드 1장 + 표 슬라이드 1장) 업로드 E2E로 표가 독립 청크로
  분리됨을 청크맵 API 응답에서 직접 확인. **정직하게 남는 갭(이번 범위 밖)**: Excel(.xlsx)은
  `FORMAT_STRATEGY`에 항목 자체가 없어 완전 미지원(신규 파서 어댑터 필요 — 청킹 알고리즘
  문제가 아니라 파싱 자체가 없음), HWP는 `FORMAT_STRATEGY`에 등록만 돼 있고 실제 파서가
  없어 여전히 422(적절한 순수 라이브러리 부재, 이전 세션부터 이어진 기존 한계). "기타
  형식 추가 시 청킹개발" 요청은 기존 `_ADAPTERS` 리스트 확장 패턴(ParserPort 구현체 추가
  + 필요 시 `### 서브헤딩`으로 구조 요소 분리)이 이미 그 확장 지점을 제공함을 확인.

- ✅ **SemanticBoundarySplitter 실제 LLM 연동 구현 완료(2026-07-22, /ao — 사용자 지시:
  "LLM 연동해서 청킹 퀄리티를 끌어올려야 한다 / 문서 안 관계 판단도 해야 한다 / 출처가
  확실해야 한다")**: 지금까지 `NotImplementedError` 스텁이던 `SemanticBoundarySplitter`
  (`backend/domain/chunking/heading_splitter.py`)를 Port/Adapter 패턴으로 실제 구현.
  `backend/application/ports/semantic_judge_port.py`(신규 Port, `ChunkRelationship`/
  `SemanticJudgment`) + `backend/adapters/llm/ollama_semantic_judge.py`(신규 실구현체) —
  로컬 Ollama(127.0.0.1:11434, 실측 확인 후 채택, API 키 불요·인증 없음이라 SAFETY 비밀키
  게이트 대상 아님)의 `qwen2.5:1.5b`를 호출해 헤딩 기준 후보 섹션 간 관계(continues/
  references/elaborates/contradicts/summarizes)를 판단한다. **출처 확실성 강제**(사용자
  지시 핵심): LLM이 응답한 `evidence`(원문 인용)가 실제로 원문에 문자 그대로 존재하는지
  검증 후 없으면 반려 — 실측(2026-07-22)으로 qwen2.5:1.5b가 from/to 섹션을 혼동하는 오류를
  직접 관찰해 to 섹션도 함께 확인하는 자기교정 로직 추가(그래도 어디에도 없으면 할루시네이션
  판정 반려). `RequirementRecord`에 `related_chunks` 필드 신설(§계열 기존 필드 추가 패턴
  그대로, CRZ) + `requirement_extraction_service.py`가 section index → 실제 chunk_id로
  안전 변환해 연결. **우아한 성능저하**: `document_upload_service.py`가 업로드마다 짧은
  타임아웃(1.5s)으로 Ollama 헬스체크 후 가용하면 LLM 연동 분할기, 불가하면 기존
  HeadingBoundarySplitter로 조용히 폴백(Ollama 다운되어도 업로드 자체는 절대 안 막힘,
  T99 AIOS) — `SemanticBoundarySplitter.split_with_spans()`도 judge 호출 자체가 실패하면
  동일하게 관계정보 없이 정직 반환. 신규 pytest 15건(`test_semantic_boundary_splitter.py`
  4·`test_ollama_semantic_judge.py` 7건, 실제 Ollama 연동 e2e 1건 포함), `pytest tests/`
  243개 전부 pass(회귀 0). **uvicorn 실기동 + 실제 문서 업로드 5회 반복 검증**(§W-5 물증):
  `data/requirements_store.json` 직접 열람으로 2/5 업로드에서 실제 검증된 관계(evidence
  span·to_chunk_id 포함)가 저장됨을 확인 — 소형 로컬 모델(1.5B) 특성상 관계 발견 여부는
  비결정적이나(실측 0~2/3 hit rate observed), 발견될 때는 항상 출처 검증을 통과한 것만
  채택됨을 확인. **정직 기록(한계)**: `type` 필드가 소형모델의 포맷 미준수로 자주
  "unclassified"로 정규화됨(5개 유효 타입 중 하나를 못 고르고 설명 문자열을 그대로
  복사하는 오류 관찰) — 더 큰 모델로 교체하면 개선 가능하나 이번 범위 밖(사용자가 특정
  모델을 지시하지 않아 이미 로컬에 떠 있는 것 재사용, CRZ).

- ✅ **Excel(.xlsx) 파서 어댑터 구현 완료(2026-07-22, /autobuild — "문서 청킹 작업 이어서
  진행")**: 직전 청킹 방법론 재검토(위 항목)에서 "정직하게 남는 갭"으로 명시했던 두
  포맷(Excel/HWP) 중, 완전 미지원(`FORMAT_STRATEGY`에 항목 자체가 없음)이던 Excel을
  닫았다. `backend/adapters/parsers/xlsx_adapter.py`(신규, `openpyxl` 기설치 재사용,
  CRZ) — pptx/pdf 어댑터와 동일한 `ParserPort` 패턴이며, 시트마다 `## Sheet: {이름}`
  헤딩으로 구분해 시트=청크 경계가 자연 성립한다(엑셀은 시트 자체가 표이므로 pptx/pdf처럼
  "표를 별도 서브헤딩으로 분리"할 필요가 애초에 없음 — 프로즈와 섞이는 문제가 구조적으로
  발생하지 않는 포맷). `router.py`(FORMAT_STRATEGY에 `.xlsx: spreadsheet_parse` 추가)·
  `document_upload_service.py`(`_ADAPTERS` 리스트 추가, 확장 지점 그대로 사용)·
  `documents.html`(업로드 accept·안내문구 갱신, 기존 pptx/pdf 누락돼 있던 것도 함께
  교정) 갱신. 신규 pytest 3건, `pytest tests/` 246개 전부 pass(회귀 0). uvicorn 실기동 +
  실제 xlsx(요구사항 2행) 업로드 E2E로 `REQ-ENV-SEC-006` 자동 채번 확인(§W-5 물증).
  **정직하게 남는 갭**: HWP는 여전히 미구현 — 순수 Python 라이브러리 부재가 근본원인이며
  (`olefile`+커스텀 파싱 또는 외부 CLI 의존 필요), 신규 외부 의존성 도입 여부는 사용자
  결정이 필요해 이번 작업 범위에서 임의로 진행하지 않았다. 대용량 시트(행 수 과다) 시
  청크 하나에 표 전체가 들어가 컨텍스트 윈도우를 넘길 가능성은 실측 근거(실사용 문서의
  전형적 행 수) 없이 선제 대응하지 않음(과설계 방지) — 필요성이 실측되면 후속 작업.

- ✅ **HWP(.hwp) 파서 어댑터 구현 완료(2026-07-22, AskUserQuestion 사용자 결정: "olefile +
  커스텀 파싱")**: 사용자가 선택한 방향을 그대로 따르되, 실제 구현 단계에서 계획을
  변경했다 — 자체 HWP5 이진 레코드 파서(HWPTAG_PARA_TEXT 등)를 처음부터 새로 짜지 않고,
  `olefile`을 내부적으로 그대로 사용하는 기존 오픈소스 구현 `pyhwp`(`pip install pyhwp`,
  이 환경 실측 설치·동작 확인)를 재사용했다. **변경 사유(정직 고지)**: 자체 이진 파서는
  이 환경에 실제 `.hwp` 샘플이 전무하고 이를 합성 생성할 라이브러리도 없어(pptx/pdf/xlsx
  어댑터와 달리) 정확성을 전혀 검증할 방법이 없었다 — 미검증 자체 구현이 "그럴듯하지만
  틀린" 텍스트를 낼 위험이 이미 검증된 오픈소스 구현 재사용보다 훨씬 크다고 판단(T98 AIP
  정직성 원칙, CRZ 재발명 회피). `backend/adapters/parsers/hwp_adapter.py`(신규) —
  `hwp5.xmlmodel.Hwp5File` + `hwp5.hwp5txt.TextTransform`(pyhwp의 `hwp5txt` CLI가 실제
  릴리스에서 쓰는 것과 동일한 코드 경로, 소스 직접 확인) 재사용. `router.py`(`.hwp` strategy
  주석 갱신)·`document_upload_service.py`(`_ADAPTERS` 등록)·`documents.html`(accept·안내문구
  갱신) 반영. **검증 범위(정직 고지, 중요)**: 부정 경로(무작위 바이트 → `InvalidHwp5FileError`
  → `HwpParsingError` → API 422)는 신규 pytest 2건 + uvicorn 실기동 curl로 실측 확인
  완료(§W-5 물증). **긍정 경로(실제 유효한 .hwp → 올바른 텍스트 추출)는 이 세션에서
  검증하지 못했다** — 실제 `.hwp` 샘플 파일이 이 환경에 없기 때문이다. 실사용 전 실제
  `.hwp` 파일로 1회 이상 확인을 권장하며, 이 한계는 어댑터 docstring에도 동일하게 명시했다.
  `pytest tests/` 250개 전부 pass(회귀 0). 이로써 사용자가 원래 요청한 6개 포맷
  (hwp/docx/pptx/txt/excel/기타) 중 hwp·docx·pptx·txt·excel(xlsx) 5개가 실제 동작하는
  파서를 갖췄다(이미지 포맷은 `FORMAT_STRATEGY`에 vision_describe 전략만 등록, LLM Vision
  어댑터는 이번 범위 밖).

- ✅ **다중 프로젝트 관리 고도화 + UI/UX 개선(2026-07-22, /autobuild — "여러 프로젝트 안에서
  애자일 요구사항을 관리하는 구조로 고도화" + "버튼·아이콘·설명문구 디자인 성의없어 보임")**:
  **① 다중 프로젝트**: 기존 `ProjectConfigStore` 자체 docstring에 "여러 프로젝트를 한
  인스턴스에서 관리하지 않는다"고 명시돼 있던 제약(헌법상 강제가 아니라 과거 구현 단계의
  임시 가정이었음, 실측 확인)을 실제로 해소했다. `backend/adapters/persistence/
  project_registry.py`(신규, 기존 미사용 `Project` 엔티티 재사용, CRZ) + `project_scope.py`
  (`resolve_project_data_dir()` — 유일한 경로결정 SSOT, `DEFAULT_PROJECT_ID="default"`는
  기존 평면 `data/` 경로 그대로라 **무마이그레이션**) + `projects_api.py`(`GET/POST /projects`).
  `requirements_api.get_requirement_store()`/`get_document_store()`·`tasks_api.
  get_task_store()`(이미 "이 함수만 바꾸면 됨"이라고 예견해 둔 seam, 실측 확인) 3곳에
  `project_id` 파라미터를 추가하고 모든 관련 라우트(요구사항 8개·태스크 4개·문서 2개·
  analytics 1개)에 스레딩. 프론트는 GNB에 프로젝트 선택기(`+ 새 프로젝트`) 신설
  (`frontend/js/project-scope.js` 신규 — localStorage 공유 헬퍼, `shell-loader.js`가 `/projects`
  채워넣고 전환 시 새로고침) + `requirements.html`/`preview.html`/`documents.html`이 그동안
  프로젝트 구분이 없던 정적 스냅샷(`../data/requirements.json`)을 fetch하던 것을 이미
  project_id를 지원하는 실시간 `GET /requirements`로 전환(부수 발견: `preview.html`의
  `fetchDoc()`도 실제로는 절대 갱신되지 않는 `frontend/data/documents/{id}.md` 정적 사본을
  읽는 잠재 버그였음 — chunk-map API의 `content` 필드로 대체해 함께 해결). `project-setup.html`
  마법사 완료 단계에 실제 `POST /projects` 호출(프로젝트 생성) 버튼 추가(기존 JSON 다운로드는
  유지). **실측 검증**: 신규 pytest 11건(`test_project_registry.py`·`test_projects_api.py`·
  `test_project_scoped_isolation.py` — 실제 HTTP 업로드로 프로젝트 A에서 만든 REQ/Task가
  프로젝트 B·default에 보이지 않음을 확인) + uvicorn 실기동으로 프로젝트 생성→문서 업로드→
  격리된 `data/projects/{id}/` 디렉터리 생성 확인(테스트 산출물은 확인 후 정리). `pytest
  tests/` 261개 전부 pass(회귀 0). **② UI/UX**: `tokens.css`의 `--border-radius-base`·브랜드
  컬러는 그대로 두고(색상 팔레트 재설계는 범위 밖 — 벤치마킹 사이트를 실제로 열람하지
  못했으므로 "네이버와 동일한 디자인"이라 과장하지 않음, T98 AIP), 표준 플랫 디자인 관용구
  (둥근 pill 버튼·hover lift·box-shadow·좌측 강조선 카드)로 `components.css`의 `.action-btn`/
  `.btn`/`.summary-card`를 갱신하고, LNB 아이콘을 원형 숫자에서 이모지 글리프(📁📋🔎📄📊)로
  교체, 배차 대시보드(`dispatch-dashboard.html`)의 한 줄짜리 기술 용어 설명문을 아이콘+핵심
  문장+상세설명 2단 구조로 재작성하고 요약카드에 상태별 아이콘(⏳📨⚙️✅🚫)을 추가했다.
  **정직한 한계**: 실제 브라우저 렌더링(색상 대비·클릭 인터랙션 체감)은 이번 세션 도구로
  검증하지 못함(기존 UI 변경들과 동일한 한계, 사용자 육안 확인 권장) — HTTP 200 서빙 확인과
  CSS/HTML 문법 정합만 실측했다.

- ✅ **색상 조화 검증 + 다크모드 실사용화(2026-07-23, /autolp — "디자인 반전 색감은
  이질감이 없어야, 다양한 시각에서 검증되어야")**: `/autolp`가 요청한 "디자인 agent 신설"은
  이 프로젝트 헌법(§4 — 범용 AEGIS류 인프라 비대화 금지)에 비춰 별도 agent 정의 파일 대신
  **본 항목의 재사용 가능한 검증 절차**로 대체했다(과잉 인프라화 회피, CRZ) — 무한
  autoloop(ScheduleWakeup)도 이 세션에서는 사람 감독하의 유한 UI 작업에 맞지 않아 사용하지
  않았다(1회 철저한 검증 패스로 대체, 정직 고지).
  **실제 문제 발견(WCAG 2.1 상대휘도 공식 직접 계산, 추정 아님)**: 기존 상태색(`--ok`/
  `--warn`/`--danger`)을 배지·요약숫자·에러문구 등 **작은 텍스트 색으로 직접 사용**하던
  곳이 라이트 배경 기준 대비비 2.15~3.76:1로 WCAG AA(4.5:1) 기준에 크게 미달했다(초록
  2.28:1·주황 2.15:1·빨강 3.76:1·브랜드블루 5.02:1만 통과). 다크모드 또한 순수 검정(#121212)
  +순수 흰 글자(#ffffff) 조합(대비 18.7:1)이 과도해 "다크가 이질적으로 번쩍인다"는 흔한
  원인이었다. **조치**: `tokens.css`에 라이트/다크 테마별 `--*-text`(ok/warn/danger/brand/
  accent2) 텍스트 전용 변형을 신설 — 같은 색상군을 라이트에서 진하게, 다크에서 밝게 낮춰
  양쪽 모두 5.0~15.8:1 확보(계산값 그대로: green 5.02/10.37·amber 5.02/12.53·red 6.47/6.53·
  brand 5.02/6.43·accent2 5.70/7.38, 라이트/다크 순). 다크 배경·글자도 순흑/순백 대신 완화된
  남색조(#15161b)/오프화이트(#eef0f3)로 조정해 라이트와 "같은 질감"을 유지(색상환은
  그대로, 명도만 테마별 재조정 — 이질감 없는 반전의 핵심 원칙). `components.css`·5개
  view의 배지·버튼·에러문구 전수(정밀 검색 `[{;] color: var\(--(ok|warn|danger|
  color-brand-primary|accent2)\);` 로 잔여 0건 확인, border-color/배경 스와치는 원색 그대로
  유지 구분) 교체. **다크모드 실사용 진입점 신설**: 지금까지 다크 팔레트가 있어도 켤 UI가
  없어 검증 자체가 불가능했다 — GNB에 🌙/☀️ 토글 버튼 추가(`localStorage.aegis_theme`,
  FOUC 방지를 위해 셸 로드 전에 즉시 적용). **다관점 검증 체크리스트(이번 세션 실측
  기준)**: ①WCAG AA 대비비 계산(색상 쌍마다) ②라이트/다크 명도 반전 시 색상환 동일성
  유지 ③상태 구분에 색만 의존하지 않고 아이콘 병기(색맹 고려 — 배차대시보드 상태 아이콘
  ⏳📨⚙️✅🚫는 이전 작업에서 이미 반영) ④border-color(스와치)와 text-color(가독성)의
  용도 분리. `pytest tests/` 회귀 0(프론트 전용 변경, 백엔드 무영향) + uvicorn 실기동으로
  신규 토큰·토글 버튼 실제 서빙 확인. **정직한 한계**: 여전히 실제 브라우저 렌더링(색
  체감·다크모드 전환 애니메이션)은 도구로 검증 못 함 — 계산된 대비비와 코드 서빙만 실측.

- ✅ **문서유형 동적 확장 + 단건 요구사항 등록 + 워크플로 순서 개편(2026-07-23, /ao —
  "프로젝트 배경... 문서유형은 동적으로 추가 가능... 중간 애자일 요구사항... 단건 등록
  프롬프트... 작업순서를 개편")**: 실측 확인 결과 `backend/domain/requirements/codes.py`의
  `DOC_TYPE_CODES`(BIZ/ITV/ENV/QA/TECH/OUT/MEMO/REC 8종)는 코드 파일을 고쳐야만 확장
  가능한 고정 dict였다(파일 자체에 "코드 추가 시 이 파일을 갱신"이라 명시돼 있었음).
  **① 동적 문서유형**: `DocTypeRegistry`(신규, `project_registry.py`와 동일한 append-only
  JSON 패턴, CRZ)를 프로젝트별로 신설 — 내장 8종(SSOT 그대로 불변)에 커스텀 유형을
  추가만 한다. `POST /doc-types`(등록)·`GET /doc-types`(목록, custom 플래그 포함) API +
  `documents.html`에 "+ 새 문서유형" 버튼(칩 UI로 등록된 유형 표시) + `project-setup.html`
  STEP3 그리드에도 커스텀 유형 자동 병합. **실측 버그 발견·수정**: 충돌 회피에 숫자
  접미사("CUSTOM2")를 쓰면 REQ ID 형식(`id_format.REQ_ID_PATTERN`이 문서유형 세그먼트를
  `[A-Z]+`로 제한, 숫자 불가)과 충돌해 `POST /requirements` 실제 호출이 500 에러로
  즉시 실패함을 uvicorn 실기동 E2E로 발견 — 접미사를 알파벳(X,Y,Z...)으로 교체해 수정,
  회귀 테스트 추가. `id_format.build_req_id()`/`parse_req_id()`에 `extra_doc_types`
  선택 인자를 추가해(도메인 계층이 영속 레지스트리를 직접 import하지 않는 헥사고날 경계
  유지 — API 레이어가 병합된 코드 집합을 주입) 커스텀 코드도 REQ 채번을 통과하게 했다
  (미지정 시 기존과 100% 동일 동작, 회귀 0). **② 단건 요구사항 등록**: `POST /requirements`
  신설 — 문서 업로드·청킹 없이 사람이 doc_type_code·area_code·description을 직접 입력해
  즉시 REQ를 채번한다(`ClassificationResult`를 사람이 만들어 기존 `add_from_classification()`
  을 그대로 재사용, 신규 스토어 메서드 없음, CRZ). `requirements.html`에 "+ 단건 요구사항
  등록" 인라인 폼(설명 textarea + 문서유형/영역 드롭다운) 추가. **③ 워크플로 순서 개편**:
  LNB 메뉴를 실제 의존관계(문서를 올려야 요구사항이 나온다) 순서로 재배열 — 이전에는
  "요구사항 관리"가 "문서/청킹 관리"보다 앞에 있어 화면 순서와 실제 흐름이 어긋나 있었다.
  ①프로젝트 설정 → ②프로젝트 배경(문서 등록, "문서/청킹 관리"에서 개명) → ③요구사항 관리 →
  ④청크 미리보기 → ⑤배차 현황 대시보드로 재배열하고 각 화면 제목·부제에 번호와 다음 단계를
  명시(화면 코드 자체 로직은 변경 없음, 메뉴 순서·표현만 조정). **실측 검증**: 신규 pytest
  18건(`test_doc_type_registry.py`·`test_doc_types_api.py`·`test_manual_requirement_
  creation.py`) + uvicorn 실기동으로 "커스텀 문서유형 등록 → 그 코드로 단건 요구사항 등록 →
  REQ-CUSTOM-WEB-001 실제 채번" 전 과정 실측 확인(§W-5 물증, 최초 시도는 위 버그로 500
  실패 → 수정 후 재시도로 성공까지 정직 기록). `pytest tests/` 279개 전부 pass(회귀 0).
