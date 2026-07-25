---
role: DESIGN_INDEX
scope: plans/_plan — 요구사항 관리 시스템 재설계 0~3차 로드맵
status: |
  [2026-07-22 재검토 갱신 — 이 줄 아래 "구현 미착수(승인 대기)"는 stale이었음, 실측으로 정정]
  0~9번 문서 전부 뼈대~핵심 구현 완료 상태(각 문서 status 참조, 세부 구현 이력은
  00_PROJECT_CONSTITUTION.md §6 로그 참조 — Phase 1~6.1까지 구현·pytest 214개 pass 실측
  2026-07-22). 같은 턴 후속으로 PPTX/PDF 파서 신규 구현 + 문서업로드 HTTP 엔드포인트
  배선 완료(pytest 231개 pass, uvicorn 실기동 curl 스모크 3종 확인) — "08 실제오디오
  미검증"도 재확인 결과 2026-07-20 이미 검증 완료(stale 주석이었음, 정정 완료).
  남은 진짜 갭: 02 §5 청킹검수 순환루프·03 §2-2 이력diff·§3-5 실시간알림·HWP 파서(전체
  본문 vs 미리보기만 범위 확정 필요 — 사용자 확인 대기)·SemanticBoundarySplitter(LLM
  콜백 설계 필요)·search_all 실시간연동(AEGIS측 인덱싱 별도 작업). "구현 미착수"가
  아니라 "핵심 구현 완료 + 소수 후속 갭 존재"로 정정.
updated: 2026-07-22
---

# 요구사항 관리 시스템 재설계 — 1~3차 설계 로드맵

> 최우선 참조: [`../../00_PROJECT_CONSTITUTION.md`](../../00_PROJECT_CONSTITUTION.md) — 이 설계는
> 그 헌법의 §1 핵심 목표("요구사항 문서 → 청킹·구조화 → 영역별 태스크화 → AI 수행관리")를
> 벗어나지 않는 범위에서, §5 데이터 모델을 확장하는 재설계다. §5(영역코드)·§5-A(문서유형코드)는
> 이미 사용자 확정 사항이며 이번 재설계에서 **변경하지 않는다** — 그 위에 새 축을 추가한다.

## 이번 재설계의 출발점 (사용자 원 요청 요약)

1. `D:\projects\products\workbase` 벤치마킹 — 프로젝트 관리 영역(분야) 선택부터 시작하는 흐름
2. 다양한 문서 유형(제안서/사업계획서/수행계획서/인터뷰/녹음/메모) 첨부 + 요구사항 라이프사이클
   (접수→수용) + 요구사항 유형(기능/비기능)
3. 청크가 원본 문서의 **어느 위치**에서 나왔는지 추적 → REQ 번호 클릭 시 그 위치로 바로 이동하는
   **미리보기**로 신뢰도를 사람이 직접 확인 가능하게
4. 기존 §5 영역코드와 별개로 **아키텍처 계층**(시스템/보안/사용자환경/서드파티인터페이스/연계)
   축 추가
5. 요구사항마다 **솔루션·라이브러리·프레임워크**(전자정부표준프레임워크/마이플랫폼/JEX
   Framework/JEX Operia AI/자체 프레임워크 등) 태그를 **필수**로 수집
6. 최종 개발 환경·언어·방법·테스트 분류까지 뼈대→단계별로 나눠 **영역별 병렬 진행** 가능하게
7. 기존 구현(classifier/requirement_store/requirements.html)도 이 확장 모델에 맞게 재설계
8. 최종 목표: 설계서 기반으로 AI agent가 작업수행 프롬프트를 만들어 프로젝트를 수행 — 요구사항은
   프로젝트 진행 중 **상시 추가·변경·삭제** 가능
9. **가장 중요**: 실측된 현재 프로젝트 구조·기능·환경·프로세스·공통화·기술을 **graphify에 저장**
   해서 프로젝트별 도메인 정보를 최신 상태로 관리

## Stage 0 명확화 결과 (AskUserQuestion, 2026-07-18 — 확정 사항)

| 갈림길 | 확정 |
|---|---|
| 계층코드(시스템/보안/사용자환경/서드파티/연계)와 기존 §5 영역코드의 관계 | **별도 새 축(계층코드, §5-B)으로 추가** — §5 그대로 유지, REQ 번호 형식에는 포함하지 않고 메타데이터 필드로만 존재 |
| 프레임워크/솔루션 카탈로그 관리 방식 | **자유 태그 + 추천목록(오토컴플리트)** — 고정 enum 아님, 조직 표준이 바뀌어도 코드 수정 불필요 |
| 이번 턴 산출물 범위 | **plans/_plan에 1~3차 설계서(문서)만** — 코드 구현은 각 차수 승인 후 별도 진행 |

## 로드맵 개요 (0~3차, 품질검토 게이트로 구분) — 2026-07-18 보강 라운드로 0차 추가

```
0차: 프로젝트 등록·분야 선택 마법사 설계 (workbase wizard.html 9단계 벤치마킹)
        ↓ [품질검토 게이트 0 — MPCR 7관점]
1차: 데이터 모델 확장 + 문서유형·계층·유형·라이프사이클·프레임워크 축 설계
        ↓ [품질검토 게이트 1 — MPCR 7관점] — PASS(2026-07-18 보강 라운드로 전 미결 해소)
2차: 청크 위치추적 + 미리보기 UI + 영역×계층 기반 병렬 오케스트레이션 설계
        ↓ [품질검토 게이트 2 — MPCR 7관점 + §PCM 시뮬레이션] — PASS(전 미결 해소)
3차: AI agent 작업 프롬프트 생성 파이프라인 + graphify 프로젝트 도메인 최신화 설계
        ↓ [품질검토 게이트 3 — 최종 비판적 다관점 검토(E2E 워크스루)] — PASS(Critical 포함 전 미결 해소)
승인 후 구현 착수 (차수별로 별도 세션/턴에서 진행)
```

> **[2026-07-22 재검토 갱신]** 위 "승인 후 구현 착수 (이 4개 문서 전부 아직 설계만, 실행 코드 0)"는
> stale — 실측 결과 0~9번 전 문서가 이미 뼈대~핵심 구현 완료 상태다(각 문서 status 필드 +
> `00_PROJECT_CONSTITUTION.md §6` 진행 로그 참조). 남은 것은 각 문서에 이미 정직 기록된
> 소수 후속 갭뿐(HWP/PDF/PPTX 파서, 03 §2-2 이력diff, 02 §5 청킹검수 순환루프, 08 실오디오
> 미검증, search_all 실시간 연동 등) — 전면 재구현이 아니라 이 갭들 중 우선순위 선택이 다음 단계.

각 차수 설계서: [`04_PHASE0_PROJECT_REGISTRATION.md`](./04_PHASE0_PROJECT_REGISTRATION.md) ·
[`01_PHASE1_DATA_MODEL.md`](./01_PHASE1_DATA_MODEL.md) ·
[`02_PHASE2_ORCHESTRATION_PREVIEW.md`](./02_PHASE2_ORCHESTRATION_PREVIEW.md) ·
[`03_PHASE3_AGENT_GRAPHIFY.md`](./03_PHASE3_AGENT_GRAPHIFY.md)

> **별도 트랙(2026-07-19 추가)**: [`05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md`](./05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md)
> — 위 0~3차와 별개로, 지금까지 쌓인 코드를 헥사고날 단일 구조로 재정리하는 설계(사용자
> 지적: "그냥 한파일에 만들고 있는거 같다"). 기능 차수가 아니라 구조 리팩토링 트랙이라
> 번호 순서(0~3차)와 무관하게 언제든 먼저 실행 가능.

> **별도 트랙(2026-07-19 추가)**: [`06_AGENT_DISPATCH_REPORTING.md`](./06_AGENT_DISPATCH_REPORTING.md)
> — 3차 설계(agent 프롬프트 생성)의 구체화. 요구사항→AEGIS 전문가 agent 매핑·우선순위
> 오케스트레이션·완료보고서 설계. 설계만, 구현은 사용자 승인 대기.
> **2026-07-20 추가**: 같은 문서 §10에 "요구사항별 작업상태+배정agent 노출" 설계 보강
> (배차 로직은 있으나 그 결과가 요구사항 화면에 보이지 않는다는 지적 반영) — 상세는
> 아래 "설계 심화(2026-07-20)" 항목 참조.

> **설계 심화(2026-07-20 추가, 사용자 심층 지적 반영)**: "청크→분류→채번" 한 줄 요약은
> 실제 순환 검수 흐름(문서 등록→청킹→결과확인→저장 또는 재청킹)과 심층 시각화(문서 전체
> 청크 경계 뷰)까지는 담지 못한다는 지적이 있었다 — 상세 설계는 이 요약이 아니라 아래 두
> 문서를 참조할 것:
> - 청킹 검수 순환 루프("맞으면 저장, 틀리면 재청킹") + 문서 전체 청크 경계 시각화 →
>   [`02_PHASE2_ORCHESTRATION_PREVIEW.md`](./02_PHASE2_ORCHESTRATION_PREVIEW.md) §5·§6
> - 요구사항별 작업상태·배정 agent 노출(API·UI) →
>   [`06_AGENT_DISPATCH_REPORTING.md`](./06_AGENT_DISPATCH_REPORTING.md) §10

> **셸 구조 반영(2026-07-20)**: 위 3개 구현 화면(프로젝트 설정·요구사항 관리·청크 미리보기)
> + 2개 준비중 영역(문서/청킹 관리, 배차 현황)이 이제 `frontend/partials/shell-nav.html`
> 기반 공통 GNB/LNB 셸의 LNB 메뉴 구조 그대로다 — 이 인덱스가 시스템 전체 IA(정보구조)의
> 뼈대이자 LNB 메뉴 구성의 근거임을 명시(00_PROJECT_CONSTITUTION.md §6 로그 참조).

> **별도 트랙(2026-07-19 추가)**: [`07_API_SERVER_ARCHITECTURE.md`](./07_API_SERVER_ARCHITECTURE.md)
> — 프론트엔드(`frontend/views/*.html`)와 백엔드(`backend/`)를 실제 실행 서버로 연결하는
> API 아키텍처 결정(FastAPI 채택, §2-3 상태변경·§2-4 PII 게이트 엔드포인트 설계). 설계만,
> 구현은 사용자 승인 대기.

> **별도 트랙(2026-07-19 추가, 설계+스캐폴딩 구현 완료)**:
> [`08_RECORDING_STT_STRATEGY.md`](./08_RECORDING_STT_STRATEGY.md) — REC(녹음) 문서유형
> STT ingestion 전략. sibling 프로젝트 chatAW/chatAWV2 조사(참고할 서버측 구현 없음을
> 확인) + 이 프로젝트에 이미 설치된 `faster-whisper` 실측 근거로 `speech_to_text_adapter.py`
> 콜백 주입 스캐폴딩 구현(실제 엔진 연결은 후속). 02_PHASE2 §1-3에서 미뤄뒀던
> `timestamp_start_ms`/`timestamp_end_ms` 필드를 이번에 채움.

> 파일명은 발견 순서(0차를 나중에 추가)를 그대로 보존해 `04_`로 남겨둔다(내용상 0차,
> 번호상 4번째 생성 파일 — 이력 보존 원칙, 소급 파일명 변경 안 함).

> **별도 트랙(2026-07-19 추가)**: 1차 설계에 7번째 축(`design_draft_gate` — 디자인 시안
> 선행 게이트, MANDATORY/NOT_MANDATORY/STRATEGIC_MANDATORY)을 추가 — 새 파일이 아니라
> `01_PHASE1_DATA_MODEL.md` §2-5~§2-7·§5·§6 + `04_PHASE0_PROJECT_REGISTRATION.md` §7로
> 기존 문서를 확장(게이트 1-B). 설계만, 구현은 사용자 승인 대기.

## workbase 벤치마킹 근거 (CRZ — 재발명 금지, 2026-07-18 보강 라운드에 실제 파일 열람으로 확인)

| workbase 자산 | 위치(실측) | 이번 설계 반영 지점 |
|---|---|---|
| 9단계 프로젝트 설정 마법사(사이드바 단계도트·체크카드·태그입력) | `frontend/project-setup/wizard.html`(3064줄, `STEPS` 배열 실측) | `04_PHASE0_PROJECT_REGISTRATION.md` 전체 — 9단계 중 목적에 맞는 6단계만 선별 이식 |
| 카테고리별 태그 선택(`DOMAIN_CATEGORIES`) | `wizard.html` 내 `DOMAIN_CATEGORIES` 객체 | Stage 0 확정 "자유태그+추천목록"의 실제 구현 패턴 — 04_PHASE0 §2 |
| PII 데이터유형 경고(`DATA_TYPES_DEF`) | `wizard.html` 내 `DATA_TYPES_DEF` 객체 | 문서 접근제어(PII 게이트) 설계의 직접 근거 — 04_PHASE0 §3, 02_PHASE2 §2-4 |
| UI/UX 설계 카탈로그(레이아웃·스타일·GNB·콘텐츠·폼·알림·모바일·인터랙션 8분류) | `wizard.html` STEP 8 패널(줄 828~984) | 04_PHASE0 §6-A — 화면별(테이블·모달·마법사) 공통 UI/UX 결정 확정(2026-07-18 추가 라운드) |
| 프롬프트 자동 컨텍스트 주입(`buildProjectContextBlock`) | `frontend/common/js/project-context.js:591` | 3차 설계 §3-3 — 태스크 프롬프트 생성기가 벤치마킹하는 핵심 함수 |
| API 우선+localStorage 폴백 이중 경로 | `_design/DB_SCHEMA.md` "localStorage 폴백" 절 | 3차 설계 §2-2 그래프 최신화 "자동+수동 이중 경로" 설계 근거 |
| 단계별 항목 동적 추가/soft-delete 설계 | `_design/DYNAMIC-STEP-ITEMS.md` | 1차 설계 §2-3 "요구사항 CRUD" — 삭제를 물리삭제가 아니라 WITHDRAWN 상태로 이력 보존 |
| CSS 토큰·서버 실행 정책 | 기존 `00_DESIGN_TOC.md`에 이미 계승 완료 | 변경 없음 (이미 반영됨) |

## 확정/미확정 총괄 (재설계 전반 — 2026-07-18 보강 라운드로 전면 갱신)

- ✅ 확정: Stage 0 표 3건(위) + **1~3차 이월 미결 6건 전부**(`03_PHASE3_AGENT_GRAPHIFY.md`
  §5 인덱스 표 참조 — layer_code 코드값·철회사유·행위자기록·PII접근제어·그래프최신화트리거·
  진행중agent통지 경로)
- 🔶 신규 후속 확인 사항(Critical 아님, 구현 단계에서 실측으로 자연 해소 예정): 프롬프트
  컨텍스트 블록의 PII 재확인, JSON 스토어의 동시편집 내성 — `03_PHASE3_AGENT_GRAPHIFY.md`
  §5의 #7·#8
