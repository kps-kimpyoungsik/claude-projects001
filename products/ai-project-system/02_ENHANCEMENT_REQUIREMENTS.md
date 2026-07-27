---
role: ANALYSIS
scope: ai-project-system 고도화(enhancement) 요구사항 리스트 — 신규 착수가 아닌 기존 가동 시스템 재분석
status: 산출 완료 — S4 열린 질문은 사용자 확인 후 반영
updated: 2026-07-27
source_skill: D:\aegis\base\02_skills\general\D_architecture\98_project_kickoff_requirement_orchestrator_skill\SKILL.md (S0-S7, L0/L1/L2 3단 축소)
cross_ref:
  - plans/_plan/UPGRADE_PLAN_2026-07-23.md
  - plans/_plan/UPGRADE_PLAN_2026-07-24_5agent.md (동일 SSOT, 아래 표는 그 결과를 흡수·갱신하며 중복 재작성하지 않음 — T39 CRZ)
  - 00_PROJECT_CONSTITUTION.md §1·§4·§5·§5-A·§6
non_goal: 이 문서는 요구사항 도출·갭 발굴만 수행한다. 코드 구현·설계 상세화는 하지 않는다(스킬 Non-Goal 원칙).
---

# ai-project-system — 고도화 요구사항 리스트 (S0~S7)

> **읽는 법**: L0(시스템 전체 그림, 1개) → L1(실제 업무 영역, 이 시스템 화면·모듈 경계 그대로) →
> L2(CRUD 리프, 요구사항 리스트 실 항목). 이후 **S3 갭 발굴**(문서에 없어도 확인) ·
> **S4 열린 질문**(사용자 확인 필요) 섹션이 이어진다.

---

## S0 — 선행 인지 (요약, 재도출 없음)

이 세션 착수 전 컨텍스트로 이미 확보된 ground-truth(화면 ①-⑦ 존재·청킹 파이프라인 동기화
구조·재청킹 실행기·Project 모델 확장·postgres 어댑터 미배선·async 큐 부재·`api.js`/
`constants.js`/`ui-dialogs.js` 공통화)를 그대로 전제로 사용했고, 이번 세션에서
`backend/adapters/api/auth.py`(2026-07-25 §D-b83768b2, X-API-Key opt-in 게이트, 8개
라우터 전체 적용 확인)·`plans/_plan/UPGRADE_PLAN_2026-07-24_5agent.md`(5-agent 진단 —
경로순회(CWE-22) 2건은 이미 수정 완료, graph.json dead-wiring·postgres 이중구조·API 인증
스코프 산정은 이미 문서화돼 있음)를 추가로 실측했다. **본 문서는 그 UPGRADE_PLAN을 대체하지
않고, 그 이후(2026-07-24 이후) 신규로 늘어난 화면(`tasks.html`·`project-dashboard.html`·
`architecture-glossary.html`)·기능(Task 상태머신 확장·doc-type 동적등록·다중 프로젝트·Project
상태/진행률)까지 포함해 L0/L1/L2 요구사항 트리 형식으로 재구성하고, UPGRADE_PLAN이 다루지 않은
축(④비기능-동기처리 구조·⑦연계맵·⑨인프라토폴로지·⑪솔루션도입)을 보완한 것**이다(T39 CRZ —
기존 정본 보강·인용, 재작성 아님).

---

## L0 — 시스템 큰그림

**ai-project-system은 "사업 착수 전 요구사항 문서 → 구조화된 요구사항 항목 → AI 개발 태스크
→ 배차·진행 추적"이라는 단일 파이프라인을 실제로 가동 중인 FastAPI(백엔드 단일 프로세스) +
vanilla HTML/CSS/JS(프론트) 시스템이다.** 사용자는 프로젝트를 등록(마법사)하고, 원본 문서
(txt/docx/pptx/pdf/xlsx/hwp)를 업로드하면 시스템이 헤딩 기반(+선택적 로컬 LLM 의미판단) 청킹
으로 이를 분해해 `REQ-{문서유형}-{영역}-{번호}` 요구사항 항목을 자동 채번하고, 사람이 그
요구사항을 수용/반려/재청킹하며, 배차 로직이 요구사항을 Task로 묶어 영역×계층 충돌 없이 실행
계획을 세우고, Task는 DRAFT→READY→IN_PROGRESS→DONE/BLOCKED 상태머신(파일 락·서킷브레이커
포함)으로 진행되며, 프로젝트/요구사항/Task 현황이 대시보드로 집계된다. **현재 다중 프로젝트를
지원하지만 실사용 데이터는 여전히 얕고(§5 영역코드 10종 중 대부분 미사용, postgres 어댑터
미배선), 전체가 단일 uvicorn 프로세스의 동기 요청-응답으로 동작해 무거운 청킹(LLM 판단·오피스
변환)이 HTTP 요청을 그대로 블로킹**한다 — 이것이 이 시스템의 가장 뚜렷한 구조적 특성이다.

---

## L1 — 영역·업무 단위 (7개)

```
[L0] 요구사항 기반 AI 개발 태스크 관리 시스템
 ├─[L1-A] 프로젝트 설정·등록·다중 프로젝트 관리
 ├─[L1-B] 문서 등록·청킹(프로젝트 배경)
 ├─[L1-C] 요구사항 관리(수용/반려/재청킹/단건등록)
 ├─[L1-D] 청크 위치추적·미리보기(PII 게이트)
 ├─[L1-E] Task 배차·상태관리·오케스트레이션
 ├─[L1-F] 프로젝트 현황·분석 대시보드
 └─[L1-G] 플랫폼 공통(횡단) — 인증·GNB/LNB 셸·테마·문서유형 레지스트리
```

---

## L2 — CRUD 리프 요구사항 리스트

각 항목: `REQ 라인 | 공통/개별 | 담당 agent 매핑축`

### [L1-A] 프로젝트 설정·등록·다중 프로젝트 관리

- 프로젝트 등록(마법사 6단계 입력→`POST /projects`) — 개별 | ⑥개발영역도(`aegis-dev000`)
- 프로젝트 조회(목록/단건, `GET /projects`) — 공통 | ⑥
- 프로젝트 수정(설정 재편집, `?project_id=` edit 모드) — 개별 | ⑥
- 프로젝트 삭제/보관(ARCHIVED 상태 전이) — 개별 | ⑥ · ⑬(`aegis-architect000`, 상태값 경계)
- ProjectConfig 등록·조회(goal/영역/문서유형/솔루션스택/접근정책/HA·보안·인프라) — 개별 | ⑨⑩⑪
- Project ↔ ProjectConfig 연결 정합성 관리(2-store join, 현재 느슨) — 공통 | ⑬(§S4 참조)
- 프로젝트별 데이터 격리 조회(`project_scope.resolve_project_data_dir` 경로 검증) — 공통 | ⑩(`aegis-security000`)

### [L1-B] 문서 등록·청킹(프로젝트 배경)

- 문서 업로드(`POST /documents/upload`, txt/docx/pptx/pdf/xlsx/hwp) — 공통 | ⑥
- 문서유형 동적 등록·조회(`POST/GET /doc-types`) — 개별 | ①분야(`aegis-architect000`)
- 청킹 결과 조회(청크맵, gap/overlap 시각화) — 공통 | ③기능
- 재청킹 요청(`POST /documents/{doc_id}/rechunk`, 실제 실행기) — 개별 | ③
- 청크-요구사항 원문 위치 조회(char_start/end·heading_path) — 공통 | ③
- 이미지 포맷 업로드(vision_describe 전략, 어댑터 미구현) — 개별 | ⑪솔루션도입(`aegis-secretary000`)
- Excel 대용량 시트 분할 정책(현재 시트=청크 1개 고정) — 개별 | ④비기능

### [L1-C] 요구사항 관리

- 요구사항 목록 조회(`GET /requirements`, 프로젝트 스코프) — 공통 | ③
- 요구사항 단건 조회(`GET /requirements/{req_id}`) — 공통 | ③
- 요구사항 단건 등록(문서 없이 직접 입력, `POST /requirements`) — 개별 | ③
- 요구사항 상태 변경(수용/반려/철회, 사유 필수) — 공통 | ⑤업무도
- 요구사항 lifecycle_status 9값 전이·감사이력(`status_history`) — 공통 | ⑤
- 요구사항 계층·유형 분류(LAYER_CODES·REQUIREMENT_TYPES) — 공통 | ①
- PII 스캔 게이트(`contains_pii`/`pii_scan_matched`) — 공통 | ⑩
- design_draft_gate 판정·수동 override — 개별 | ⑤
- 요구사항↔Task 연계 상태 노출(`assigned_agent_command`/`work_status`) — 공통 | ⑤·⑥
- 관계 요구사항(`related_chunks`, continues/references/elaborates/contradicts/summarizes) 조회 — 개별 | ③

### [L1-D] 청크 위치추적·미리보기

- 원문 하이라이트 미리보기(`GET /requirements/{req_id}/preview`) — 공통 | ③
- PII 클릭스루 확인·접근 로그(`preview_access_log.jsonl`) — 공통 | ⑩
- 문서 전체 청크 경계 뷰(gap/overlap 스윕) — 개별 | ③

### [L1-E] Task 배차·상태관리·오케스트레이션

- Task 생성(`POST /tasks`, `TASK-{domain_code}-{일련번호}` 채번) — 공통 | ⑥
- Task 목록/단건 조회(`GET /tasks`, `GET /tasks/{task_id}`) — 공통 | ⑥
- Task 상태 변경(`POST /tasks/{task_id}/status`, 상태머신 검증) — 공통 | ⑥
- Task 실행 락 획득/해제(파일 기반 배타 락, 영역×계층 충돌 방지) — 공통 | ⑦연계영역도(`aegis-infra000`)
- BLOCKED 서킷브레이커(3회 → `needs_escalation` → override 필요) — 개별 | ⑤
- DONE 전이 사유 필수(HITL 게이트) — 공통 | ⑤
- 배차 계획 산출(우선순위+CLEAR/OVERLAP, `task_dispatch_service`) — 개별 | ⑥
- 프롬프트 조립(요구사항 원문+solution_stack 병합) — 개별 | ⑥
- 완료 보고서 조립(`completion_report_service`, git diff --stat 파싱) — 개별 | ⑤
- 요구사항↔코드 IMPLEMENTS 추적 검증(graph 인자 배선) — 개별 | ⑬(§S3 참조, 현재 dead-wiring)

### [L1-F] 프로젝트 현황·분석 대시보드

- 프로젝트 대시보드(상태 요약카드+프로젝트카드+진행률) — 공통 | ⑤
- 진행률 계산(Task DONE-비율) — 공통 | ③
- 배차 현황 대시보드(dispatch-dashboard) — 공통 | ⑤
- 실패 패턴 분석 조회(`GET /analytics/failure-patterns`, 읽기전용 집계) — 개별 | ⑤

### [L1-G] 플랫폼 공통(횡단)

- API 인증 게이트(X-API-Key opt-in) — 공통 | ⑩
- 프론트 fetch 인증 헤더 배선(현재 미배선, §S3 참조) — 공통 | ⑩
- GNB/LNB 공통 셸 네비게이션 — 공통 | ②영역별
- 라이트/다크 테마 토글(WCAG AA 대비 확보) — 공통 | ④비기능(접근성)
- 아키텍처/보안 용어 글로서리 화면(`architecture-glossary.html`) — 공통 | ①(§S4 — 목적 미확인)
- 공통 fetch/상태상수 모듈(`api.js`/`constants.js`) — 공통 | ⑥

**L2 총 항목 수: 40건** (공통 25 / 개별 15)

---

## 13축 분류표 (MECE 확인 — 전 항목 확인됨/N/A)

| 축 | 상태 | 근거 |
|---|---|---|
| ① 분야별 | 확인됨 | 요구사항관리·문서관리·태스크오케스트레이션·대시보드 4대 하위 도메인 |
| ② 영역별 | 확인됨 | L1-A~G 7개 화면/모듈 경계가 곧 조직 경계(1인 다역 프로젝트라 부서 분리 없음) |
| ③ 기능 | 확인됨 | 위 L2 40건 |
| ④ 비기능 | 확인됨(갭 있음) | 동기 블로킹 구조·WCAG AA(2026-07-23 조치완료)·대용량 시트 미대응 — 아래 S3 참조 |
| ⑤ 업무도 | 확인됨 | 문서등록→청킹→요구사항확정→배차→진행→완료보고 흐름이 LNB 순서와 일치(2026-07-23 개편) |
| ⑥ 개발영역도 | 확인됨 | domain/application/adapters 3계층, 159-import 리네임 비권고 확정(01번 설계서) |
| ⑦ 연계영역도 | 확인됨(갭 있음) | 내부 연계는 Task 락+배차뿐, graphify-hub 등 AEGIS 외부 검색 연동은 "이 프로젝트 범위 밖" 명시 — 아래 S3 |
| ⑧ 대외 연계 | N/A(사유: 이 시스템은 외부기관·타사 연동이 설계상 없음 — LLM 연계(로컬 Ollama)만 존재하며 이는 ⑪로 분류) | — |
| ⑨ 인프라 토폴로지 | 확인됨(갭 있음) | 단일 uvicorn 프로세스, DMZ/전용선망 개념 자체가 로컬 개발 전제라 미적용 — `infrastructure/config_loader.py`(단일↔HA)만 존재, 실배포 미검증 |
| ⑩ 보안·컴플라이언스 | 확인됨(부분 조치) | 인증(2026-07-25 조치)·경로순회(2026-07-24 조치) 완료, 프론트 헤더 미배선·PII 게이트 일관성 재검토는 미해결 |
| ⑪ 솔루션 도입 | 확인됨 | 로컬 Ollama(qwen2.5:1.5b, 라이선스 불요·API키 불요), faster-whisper(tiny), pyhwp/openpyxl/pdfplumber/python-pptx(전부 오픈소스, 라이선스 관리 필요성 낮음) |
| ⑫ 프로젝트 유형 | 확인됨 | **고도화(기존 가동 시스템 enhancement)** — 이번 세션 스코프 정의 그대로 |
| ⑬ 기초 뼈대 | 확인됨 | 헥사고날 domain/application/adapters, Port/Adapter(4개 Port), postgres는 미배선 대안 어댑터로 존재 |

---

## S3 — 갭 발굴 (문서에 없어도 확인, "없다"≠"불필요")

> UPGRADE_PLAN_2026-07-24(5-agent)가 이미 다룬 항목은 **[기존]** 표기로 인용만 하고 재분석하지
> 않는다(T39 CRZ). 그 이후 신규 실측·미다룬 축만 상세 서술한다.

1. **[신규] ④비기능 — 동기 블로킹 아키텍처가 청킹에 국한되지 않음**: 재확인 결과 async job
   queue·`BackgroundTasks`·`celery`/`arq`/`rq` 어떤 패턴도 `backend/` 전체에 0건(grep 실측,
   `rechunk_queue`는 이름과 달리 append-only 로그일 뿐 실제 워커 큐가 아님). 이는 청킹만의
   문제가 아니라 **시스템 전체의 구조적 특성**(Ollama 의미판단 최대 60s·LibreOffice 변환
   최대 120s가 그대로 HTTP 응답을 막음, `threading.Lock`이 `--workers` 자체를 금지). 2026년
   FastAPI 모범사례 기준(WebSearch 확인, 아래 출처): 가벼운 후처리는 `BackgroundTasks`,
   진짜 장시간 I/O 작업은 Redis 기반 `arq`(완전 비동기, 단일 워커에서도 다수 job 동시처리
   가능)나 `RQ`(설정 단순)가 표준 대안이며, CPU 바운드 작업은 `asyncio.to_thread()`가
   최소 개선책이다. **권고 우선순위**: 청킹 API를 `202 Accepted`+job-id 폴링 패턴으로 먼저
   전환(가장 사용자 체감 크고 리스크 낮음), Redis 도입은 다음 단계로 분리.
   [출처: leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi,
   davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in]

2. **[신규] ⑩보안 — 프론트엔드가 인증 게이트를 실제로 사용하지 않음**: `auth.py`가
   2026-07-25에 구현·8개 라우터에 적용됐음을 확인했으나, `frontend/js/api.js` 및 각 view의
   `fetch()` 호출부에 `X-API-Key` 헤더를 붙이는 코드가 없다(README §요구사항 관리 화면 섹션도
   "실제 배포 시에는 프론트 fetch 래퍼 보강이 별도 필요"라고 스스로 명시). **현재 상태 = 백엔드
   게이트는 켤 수 있지만 켜는 순간 모든 화면이 401로 깨진다** — "인증 도입 완료"로 오인하면
   위험한 반쪽 구현. UPGRADE_PLAN이 스코프만 산정하고 미구현으로 남긴 항목([기존])의 후속.

3. **[신규] ⑦연계영역도 — graphify-hub 등 AEGIS 외부 검색 연동이 설계 문서에서만 언급되고
   실제 연동 지점이 없음**: `backend/adapters/aegis_bridge/search_all_adapter.py`가 존재하나
   UPGRADE_PLAN이 이미 "미문서화 죽은 코드(참조 0건)"로 확인함([기존]). 추가 확인: 이
   어댑터가 무엇과 연결될 예정이었는지 코드/설계서 어디에도 계약(Port)이 없어, 향후 되살릴 때
   그대로 재사용 가능한지조차 판단 불가 — 삭제도 보강도 아닌 **미확정 상태로 방치** 중.

4. **[신규] ⑬기초뼈대 — Project 레지스트리와 ProjectConfig가 여전히 느슨한 2-store 결합**:
   ground-truth로 이미 알려진 "플래그된 아키텍처 질문"을 코드 레벨로 재확인 —
   `project_registry.py`(Project 엔티티: id/name/status/날짜/progress)와
   `project_config_store.py`(goal/영역/솔루션스택/보안 등)가 같은 `project_id`로만 느슨하게
   연결되고 서로의 스키마를 참조하는 FK성 검증이 없다. 한쪽만 생성되고 다른 쪽이 없는 상태
   (orphan) 방지 로직 부재 — 실제로 `POST /projects`와 `ProjectConfig` 저장 API가 별도
   호출이라 트랜잭션 경계가 없다.

5. **[신규] ④비기능/⑤업무도 — Task 완료(DONE) reason이 자유텍스트라 실제 완료 증거를
   검증하지 않음**: 00_PROJECT_CONSTITUTION §6 자체가 "이 reason이 실제 완료 여부를 자동
   검증하지는 않는다"고 정직하게 기록해둔 기존 한계다([기존], 재확인만). 고도화 관점에서
   보면 이는 Phase 5(증거 기반 검증 루프)의 다음 단계 후보로 남아있다 — 완료 보고서
   (`completion_report_service`, git diff --stat)와 reason 텍스트를 교차 검증하는 로직은
   아직 없음.

6. **[신규] ②영역별/⑤업무도 — `architecture-glossary.html`의 시스템 내 위치가 불분명**: LNB
   메뉴·L1 업무 흐름 어디에도 이 화면으로의 진입 경로가 문서화돼 있지 않다(독립 화면으로만
   존재). 참고자료 화면인지, 특정 사용자 역할(개발자/보안 담당) 전용 문서 뷰인지 목적이
   불명확 — S4로 이월.

7. **[기존, 인용만] Phase 3 IMPLEMENTS 추적 dead-wiring·`.graphify-out/` 빈 디렉터리·postgres
   어댑터 미배선·§5 영역코드 9/10종 미사용·SPOF(백업/CI/CD/프로세스매니저 0건)·PII 게이트
   일관성**: `UPGRADE_PLAN_2026-07-24_5agent.md` §전체 참조, 그 문서의 우선순위(P0~P3)를
   그대로 유효한 것으로 채택한다(재작성 없음).

---

## S4 — 열린 질문 (사용자 확인 필요, 추정 진행 금지)

1. **Project ↔ ProjectConfig 결합 강화 여부**: 지금처럼 느슨한 결합(각자 CRUD, 조인은
   `project_id` 문자열 일치뿐)을 유지할지, 아니면 생성 시 원자적 트랜잭션(둘 다 성공해야
   커밋)으로 강화할지 — 고도화 우선순위에 영향을 주는 아키텍처 결정이라 사용자 확인 필요.
2. **API 인증 완성 시점**: 프론트 fetch 헤더 배선을 이번 고도화 사이클에 포함할지, 아니면
   "로컬 전용 배포가 계속되는 한 우선순위 낮음"이라는 UPGRADE_PLAN의 기존 판단을 그대로
   유지할지 — 이 시스템이 로컬 밖으로 노출될 계획이 있는지가 결정 변수(UPGRADE_PLAN도 동일
   질문을 이미 열어둠, 재확인).
3. **`architecture-glossary.html`의 용도·소속 L1 영역**: 참고문서 화면으로 유지(LNB에 항목
   추가 필요 여부)인지, 특정 역할 전용 온보딩 자료인지 확인 필요 — 확인 전에는 L1-G(플랫폼
   공통)로 잠정 배치.
4. **청킹 비동기화 착수 여부·범위**: `202 Accepted`+폴링(가벼운 개선) 단계까지만 이번
   사이클에 포함할지, Redis(`arq`) 기반 워커까지 포함할지 — 후자는 신규 인프라 의존성
   (Redis) 도입이라 §4 드리프트 체크리스트 Q4("범용 인프라가 도구로만 쓰이는가")에 비춰
   반드시 사용자 확인이 필요한 결정.

---

## Self-Oracle 체크 (스킬 요구 항목)

- [x] L0→L1→L2 3단계 순서로 축소(직행 없음)
- [x] L2 리프가 CRUD/업무동사 1라인 단위
- [x] L2 항목 공통/개별 태깅 완료
- [x] 13축 분류표 전 항목 확인됨/N/A(사유 명시), 빈 슬롯 없음
- [x] 프로젝트 유형 = 고도화로 명확 판정(사용자 지시 그대로)
- [x] 인프라 토폴로지 "DB 직접접근 금지" 원칙 — 이 시스템은 `Store`/`Port` 계층이 이미 그
      경계 역할(WAS→DB 직접접근 없음, Repository 패턴과 동형) 수행 확인
- [x] AskUserQuestion 필요 항목은 S4로 분리(자유텍스트 재질문 없음, 본 세션은 분석 산출만이라
      실제 AskUserQuestion 호출 없이 질문 목록화로 대체)
- [x] 설계·구현·보안점검 직접 수행 안 함(분석만)
- [ ] 산출물 문서번호 필요성 검토 → `aegis-qa000` 인계 — **이번 세션 범위 밖(사용자 지시로
      미인계), 후속 세션 과제로 명시**
- [x] MECE 완결성 검사 통과
- [x] No fabricated values — 모든 파일 경로·API 경로·상태값은 이 세션 내 Read/Grep/Bash로 실측
