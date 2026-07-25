# ai-project-system — 요구사항 기반 AI 개발 태스크 관리 시스템

> 이 프로젝트에 진입하는 모든 LLM 세션은 [`CLAUDE.md`](./CLAUDE.md)가 진입점이며,
> 그 파일이 아래 헌법을 최초 목표로 자동 앵커링한다.

> **⚠️ 먼저 읽을 문서**: [`00_PROJECT_CONSTITUTION.md`](./00_PROJECT_CONSTITUTION.md) —
> 이 프로젝트의 진짜 목표(사업 요구사항 문서 → 구조화 → 영역별 태스크화 → AI 수행관리)와
> 방향 이탈 방지 체크리스트. 아래 Phase 설계보다 이 문서가 우선한다.

- 프로젝트 헌법(최우선): [`00_PROJECT_CONSTITUTION.md`](./00_PROJECT_CONSTITUTION.md)
- 설계 목차(헌법 기준으로 재해석됨): [`00_DESIGN_TOC.md`](./00_DESIGN_TOC.md)
- `/recall` 통합 지침: [`governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md`](./governance/workflows/RECALL_UNIVERSAL_SEARCH_GUIDE.md)
- 현재 단계: **헥사고날 백엔드 통합 리팩토링 완료(2026-07-19)** —
  `plans/_plan/05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md` 설계대로 기존
  `graphify_engine/`·`ingestion/`·`orchestrator/`·`core_was_block/`(플랫하게 흩어져 있던
  4개 최상위 패키지)를 단일 `backend/domain·application·adapters` 3계층으로 통합하고,
  `agent-view/`+`frontend/styles/`를 `frontend/{views,styles,data}`로 병합했다. `tests/`에
  23개 pytest로 리팩토링 전후 회귀 0 확인(**2026-07-25 갱신: 현재 345개** — STEP2/3 인프라존·
  ProjectConfig API·auth 게이트 등 후속 작업 누적). Phase 0~2(등록 마법사·데이터 모델·위치추적
  미리보기)는 구현 완료, Phase 3(agent 프롬프트·graphify 최신화)은 설계만 — 상세 이력은
  `00_DESIGN_TOC.md`(과거 경로 그대로 보존, T39 CRZ) 참조.

## 요구사항 관리 화면 로컬 확인

`backend/server.py`(FastAPI)가 API와 정적 프론트를 한 프로세스로 서빙한다(과거 `python -m
http.server`는 폐기 — API 라우트가 없어 requirements/documents 화면이 정상 동작하지 않는다).

```bash
python -m uvicorn backend.server:app --port 8899
# 주의(§DRL-1): --workers 지정 금지(단일 프로세스 전제, requirements_api._write_lock 참조)
# [2026-07-25] API 인증(선택): AIPS_API_KEY 환경변수를 설정하면 모든 API 요청(정적 프론트·
# /health 제외)에 일치하는 X-API-Key 헤더가 필요해진다. 미설정(기본값) = 인증 비활성,
# 기존 로컬 개발 워크플로우 그대로 동작(회귀 0). 설정 시 프론트 JS의 fetch 호출도 헤더를
# 함께 보내야 하므로, 실제 배포 시에는 프론트 fetch 래퍼 보강이 별도 필요(현재는 opt-in
# 서버측 게이트만 구현 — backend/adapters/api/auth.py).
# 브라우저에서 아래 화면들을 확인
#   http://127.0.0.1:8899/                            (root -> /views/index.html 리다이렉트)
#   http://127.0.0.1:8899/views/project-setup.html    (0차 — 프로젝트 등록 마법사)
#   http://127.0.0.1:8899/views/requirements.html      (1차 — 요구사항 관리)
#   http://127.0.0.1:8899/views/preview.html           (2차 — 청크 위치 미리보기)
#   http://127.0.0.1:8899/views/documents.html         (§6 — 문서 전체 청크 경계 시각화)
#   http://127.0.0.1:8899/health                       (헬스체크)
```

`file://`로 직접 열면 브라우저가 로컬 JSON fetch를 차단하므로 반드시 위 서버를 거쳐야 한다.

## 회귀 테스트

```bash
python -m pytest tests/ -v
```

## 디렉터리 구조 (2026-07-19 헥사고날 리팩토링 결과)

```
ai-project-system/
├── .graphify-out/              ← 지식 그래프 산출물 (Phase 3)
├── backend/                    ← 헥사고날 아키텍처 단일 루트
│   ├── domain/                 ← 순수 로직(I/O 없음): codes·graph_entities·classifier·
│   │                              id_format·chunk·project·task
│   ├── application/
│   │   ├── ports/              ← 추상 인터페이스(DatabasePort·ParserPort)
│   │   └── services/           ← 유스케이스(requirement_extraction·graph_pipeline·context)
│   └── adapters/                ← 구체 기술
│       ├── db/ · api/           ← SQLite·HTTP health
│       ├── persistence/         ← JSON 스토어(requirement·document·project_config·task)
│       ├── parsers/             ← router·docx_adapter
│       └── extractors/          ← ast·semantic
├── frontend/
│   ├── styles/tokens.css       ← 전역 디자인 시스템 토큰 (workbase 계승)
│   ├── views/                  ← 화면 4개(index·requirements·preview·project-setup)
│   └── data/                   ← 화면용 JSON·원본문서 export
├── tests/                      ← pytest 회귀 스위트(23건)
├── infrastructure/              ← 배포·이중화 설정 + config_loader.py(단일↔HA 전환)
├── governance/
│   ├── constitution/           ← 시스템 헌법
│   ├── agents/                  ← 에이전트별 정책
│   ├── workflows/               ← 실행 정책 (SERVER-EXECUTION_POLICY.md 등)
│   └── reports/                 ← 검증·감사 리포트
├── plans/_plan/                 ← 설계서(0~5차) · plans/_open/ ← 진행 중 작업(T45 TLM)
└── workbase/                     ← 개발 샌드박스 (Phase 0.3, workbase 패턴)
```

## 설계 원칙

- **Port/Adapter 분리**: 모든 기술 구현(DB, HTTP)은 `application/ports`의 추상 계약을 구현하며,
  구체 기술 교체 시 어댑터만 교체한다 (예: SQLite → PostgreSQL).
- **재사용 우선(CRZ)**: workbase에서 검증된 CSS 토큰·서버 실행 안전정책(SEP)·CORS/health 패턴을
  재발명 없이 계승했다. 상세는 `00_DESIGN_TOC.md`의 "workbase 검토 요약" 참조.
- **비가역 작업 게이트**: Phase 1.1 실제 이중화 배포·방화벽 설정 등 서비스 배포(C등급)는 본
  스캐폴딩 범위 밖이며, 실행 전 평식 승인이 필요하다.
