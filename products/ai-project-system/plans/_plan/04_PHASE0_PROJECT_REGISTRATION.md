---
role: DESIGN_PHASE0
scope: 프로젝트 등록·분야 선택 마법사 (workbase wizard.html 9단계 벤치마킹)
status: 게이트 0 PASS — **뼈대 구현 완료(2026-07-18)**: `graphify_engine/project_config.py` + `agent-view/project-setup.html`(6단계 전부), smoke test로 위저드→python 스토어 스키마 호환 확인. §7-A — 프로젝트 레벨 시안 확정 플래그(`project_design_draft_confirmed`) STEP 6 반영. **design_draft_gate 코드 구현 완료(2026-07-19)**: `project_config_store.py`의 `ProjectConfig`에 `project_design_draft_confirmed`/`_by`/`_at` 필드 추가.
**§8 신규 설계 추가(2026-07-25, 구현 미착수)**: STEP 2(분야 선택) 대폭 보완 — 용어
설명 배선 누락 근본원인 규명 + HA(이중화) 조건부 아키텍처 옵션 + 그리드/LLM/리포트
정적 큐레이션 추천(WebSearch 조사) + 아키텍처/보안 지식페이지 신설 + 보안레벨 선택 +
Mermaid 다이어그램 시각화 + UI/UX 개선(설명박스·타이틀) + MD 파일 정리 후보 식별. Stage5
작업분해(W1~W8) 포함, 구현은 다음 턴부터 단계별(사용자 확정).
**§8-7-A 참고이미지 반영 디자인 검토 완료(2026-07-25, aegis-design000)**: Mermaid 폐기
→ 커스텀 SVG/CSS 격상 확정, 기존 토큰 재사용 CSS 스펙 확정.
**W1~W7 구현 완료(2026-07-25, /autobuild)**: `codes.py` DOMAIN_CODES/LAYER_CODES를
label+desc dict로 승격(W1, 회귀 없음 실측 확인) + `project-setup.html` 설명박스·타이틀
CSS(W2) + HA 토글·조건부 필드(W3, `ProjectConfig` 신규 필드 다수) + 그리드/LLM/리포트
추천 태그(W4) + 보안레벨 선택기(W5, SHA-256 비권장 경고 배지 포함) + 원형게이지+SVG
토폴로지 아키텍처 요약 시각화(W7, §8-7-A 스펙 그대로) + `architecture-glossary.html`
지식페이지 신설(W6, 병렬 에이전트) — 전체 회귀 325 passed(변화 없음, 프론트만 변경).
**W8(MD 파일 삭제)은 SAFETY 큐 유지** — 사용자 승인 대기.
updated: 2026-07-25
---

# 0차 설계 — 프로젝트 등록·분야 선택 마법사

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 이후 단계: [`01_PHASE1_DATA_MODEL.md`](./01_PHASE1_DATA_MODEL.md)

> **왜 0차인가**: 사용자 원 요청 1번 — "프로젝트 관리 영역부터 먼저 어느 분야부터 선택하고"가
> 1~3차 설계 어디에도 없었다(1차는 이미 청크가 들어온 이후를 다룸). 이 공백을 메우는 **입구
> 단계**라 0차로 앞에 둔다. 1~3차 번호·내용은 그대로 유지(CRZ — 재작성 없이 앞에 삽입).

## §1. workbase `wizard.html` 실측 — 무엇을 그대로 가져오는가

`D:\projects\products\workbase\frontend\project-setup\wizard.html`(3064줄)을 직접 열어
9단계 구조와 상호작용 패턴을 확인했다:

```js
const STEPS = [
  {num:1, title:'기본 정보',       sub:'프로젝트명, 설명'},
  {num:2, title:'시스템 환경',     sub:'배포환경, 컴포넌트'},
  {num:3, title:'데이터베이스',    sub:'DB 종류 및 연결'},
  {num:4, title:'서비스 업무영역', sub:'도메인 태그'},
  {num:5, title:'사용자 유형',     sub:'역할 선택'},
  {num:6, title:'정보 접근 범위',  sub:'데이터 공개 정책'},
  {num:7, title:'저장 데이터',     sub:'데이터 유형'},
  {num:8, title:'UI/UX 설계',      sub:'레이아웃·디자인 방향'},
  {num:9, title:'완료 확인',       sub:'최종 검토 및 저장'},
];
```

| workbase 패턴(실측 위치) | 그대로 가져오는 이유 |
|---|---|
| 사이드바 단계 도트(`step-dot done/active`) + 진행률 | 마법사 진행 상태를 한눈에(시각화 인지 포인트, 이미 이 프로젝트가 채택한 원칙과 동일) |
| `check-cards`(단일/다중 선택 카드) | 본 문서(0차) §2 "분야 선택"에 그대로 사용 — 새 위젯 발명 없음 |
| `DOMAIN_CATEGORIES`(카테고리별 태그 그룹 + 자유 입력) | Stage 0에서 확정한 "자유 태그 + 추천목록"을 **이미 검증된 실제 UI 패턴**으로 구현 — `tag-wrap`/`tag-sug`/`tag-del` 그대로 재사용 |
| `DATA_TYPES_DEF`의 `pii` 항목(⚠ 아이콘 경고) | 2차 설계의 "문서 접근제어" 미결 항목을 해소하는 **직접적 근거**(§3 참조) |
| `buildProjectContextBlock(cfg)`(project-context.js:591) | 3차 설계의 "AI agent 프롬프트 생성"이 그대로 벤치마킹할 **검증된 함수 패턴**(§4 참조) |
| SQLite `projects`/`history`/`step_logs` 3테이블 + REST API + localStorage 폴백 | 마법사 응답 영속화 방식의 근거(§2-3) — 단, 이 프로젝트는 SQLite 대신 기존 JSON 스토어 패턴(TaskStore와 동일)을 유지해 기술스택 일관성 확보(CRZ, 새 DB 의존성 추가 안 함) |

## §2. 이 프로젝트용 마법사 단계 재설계 (workbase 9단계 → ai-project-system 6단계)

workbase는 "새 웹앱 만들기" 맥락이라 시스템환경·DB·UI/UX 단계가 있지만, 이 프로젝트는 "요구사항
문서를 받아 태스크화"가 목적(00_PROJECT_CONSTITUTION.md §1)이라 **불필요한 단계는 가져오지
않는다**(과잉설계와 무관한 목적 불일치 — 그대로 베끼면 헌법 §4 드리프트 위반). 시스템환경·DB는
완전 제외하되, UI/UX는 "프로젝트마다 매번 재선택하는 단계"로는 제외하고 대신 **전체 화면에
적용할 공통 결정**으로 §6-A에서 별도 확정한다(2026-07-18 추가 라운드 — 완전 배제가 아님).

| # | 단계 | workbase 대응 단계 | 이 프로젝트 내용 |
|---|---|---|---|
| 1 | 기본 정보 | STEP 1 그대로 | 프로젝트명, 목표 한 문장(§1 헌법의 "산출물·완료조건 한 문장" 원칙과 정합) |
| 2 | **분야 선택** (사용자 원 요청 1번) | STEP 4 "서비스 업무영역" 패턴 재사용 | §5(기술영역)+§5-B(계층코드, 아래 §5 참조) 카테고리를 `DOMAIN_CATEGORIES`와 동일한 카드+태그 UI로 다중 선택. 이 선택이 이후 청크 분류기(1차 설계)의 **1차 필터**가 됨 — 예: "이 프로젝트는 WEB/SEC/LLM 영역만 다룬다"고 미리 선언하면 분류기가 그 범위 안에서만 판정(오탐 감소) |
| 3 | 첨부 문서 유형 | STEP 7 "저장 데이터 유형" 패턴 재사용(카드 선택 + PII 경고 아이콘) + STEP 8 "파일업로드(DnD)" 패턴(§6-A) | §5-A 문서유형(BIZ/ITV/ENV/QA/TECH/OUT) + 신규 `MEMO`(메모)·`REC`(녹음) 추가(사용자 원 요청 "제안서·사업계획서·수행계획서·인터뷰·녹음·메모") — 각 카드에 "PII 가능성" 경고 배지(§3), 실제 업로드는 드래그&드롭(§6-A 폼&입력) |
| 4 | 프레임워크·솔루션 사전 등록 | STEP 4 `tag-wrap`+`tag-sug` 그대로 | 1차 설계 §2-4 `solution_stack` 초기값 — `RECOMMENDED_SOLUTION_TAGS`(전자정부표준프레임워크/마이플랫폼/JEX Framework/JEX Operia AI/자체 프레임워크)를 추천 태그로 노출, 자유 추가 가능 |
| 5 | 정보 접근 정책 | STEP 6 "정보 접근 범위" 그대로 | PII 포함 문서의 기본 열람 정책(개인별/역할별/전체공유) — 2차 설계 미결 #4 해소(§3) |
| 6 | 완료 확인 | STEP 9 그대로 | 저장 시 `ProjectDomainSnapshot` 최초 스냅샷 생성 트리거(3차 설계 §2와 연결, §5 참조) |

## §3. 2차 설계 미결 #4 해소 — 문서 접근제어(PII) 설계 확정

workbase의 `DATA_TYPES_DEF`에서 `pii` 항목이 이미 "이름/연락처/주소/식별자 ⚠"로 정의돼 있고
UI에 경고 아이콘까지 있다 — **이 프로젝트도 같은 개념을 청크 단위로 내린다**:

```python
# 1차 Chunk/2차 SourceLocation에 추가할 필드 (설계 확정)
contains_pii: bool = False          # 정규식 기반 결정론적 스캔 결과(주민번호/전화번호/이메일 패턴)
pii_scan_matched: list[str] = []    # 어떤 패턴이 매치됐는지(투명성 — classifier.py와 동일 원칙)
```

미리보기 모달(2차 설계 §2) 동작 확정:
- `contains_pii=True`인 청크는 미리보기 오픈 시 **"민감정보 열람 확인" 클릭스루 게이트**를
  한 번 거친 뒤에만 원문 표시(workbase pii 경고 아이콘의 인터랙션 버전)
- 열람 시도는 `preview_access_log.jsonl`에 `{req_id, actor, ts, granted}` 형태로 기록(2차
  설계에서 신설한 `status_history`와 동일한 append-only 감사로그 패턴 — 신규 로깅 방식 발명
  없음, CRZ)
- 0차 §2 STEP 5(정보 접근 정책)에서 선택한 기본 정책(개인별/역할별/전체공유)이 이 게이트의
  기본값을 결정 — "역할별"이면 열람 전 역할 확인까지 요구(구현은 3차 이후, 이번엔 정책 설계만)

**미결 #4 — 해소 완료**(더 이상 이월 없음).

## §4. 3차 설계 미결 #6(Critical) 해소 근거 — `buildProjectContextBlock` 벤치마킹

workbase의 `project-context.js:591 buildProjectContextBlock(cfg)`가 이미 실전에서 검증한 패턴:
마법사에서 모은 설정을 **모든 프롬프트에 자동 주입**하고, 기존 시스템 컨텍스트가 있으면
"작업 사전 분석 지시" 블록까지 프롬프트에 강제 삽입한다. 이 구조를 3차 설계의 프롬프트
생성기가 그대로 계승한다 — 상세 설계는 [`03_PHASE3_AGENT_GRAPHIFY.md`](./03_PHASE3_AGENT_GRAPHIFY.md)
§3-3(보강판)에 반영했다.

## §5. 완료 시점 트리거

0차 마법사의 "완료 확인"(STEP 6) 저장 액션이 3차 설계 §2-2 `ProjectDomainSnapshot`의 **최초
생성 시점**이다 — 이후 최신화는 3차 §2-2(보강판)의 이벤트 기반 트리거가 이어받는다.

## §6-A. UI/UX 설계 벤치마킹 (2026-07-18 추가 라운드 — workbase STEP 8 실측)

이전 라운드에서 "9단계 중 시스템환경·DB·UI/UX 3단계를 목적 불일치로 제외"라 판정했으나,
UI/UX는 재검토 결과 **완전 제외가 아니라 적용 방식이 다르다**로 정정한다: workbase는
"매번 다른 웹앱을 생성"하는 도구라 프로젝트마다 레이아웃·스타일을 물어야 하지만, 이
프로젝트는 화면이 정해진 내부 관리도구(요구사항 테이블·미리보기 모달·등록 마법사)라
**프로젝트마다 다시 묻는 대신, 전체 화면에 일관 적용할 한 벌의 결정을 지금 확정**하는
것이 맞다. `wizard.html` STEP 8(줄 828~984)을 실제로 열어 카탈로그 전체를 확인했다.

### 카탈로그 실측 (workbase STEP 8 그대로)

| 분류 | workbase 선택지 |
|---|---|
| 화면 레이아웃(단일) | 탑다운·사이드바·대시보드·SPA단일화면·스플릿뷰·풀스크린·벤토그리드 |
| 디자인 스타일(단일) | 플랫미니멀·Material·뉴모피즘·글래스모피즘·다크퍼스트·브루탈리즘·벤토스타일 |
| GNB 내비게이션(단일) | 고정상단바·좌측사이드바·아이콘레일·플로팅내비·하단탭바 |
| 콘텐츠 표현(복수) | 카드그리드·매이슨리·목록/카드토글·가상스크롤·데이터테이블·KPI카드·차트·히트맵·게이지·타임라인·칸반보드 |
| 폼&입력(복수) | 단계별마법사·인라인편집·자동완성·파일업로드(DnD)·날짜선택기·태그입력·리치텍스트 |
| 알림&피드백(복수) | 토스트·배너·모달다이얼로그·인라인오류·뱃지·진행표시줄·스켈레톤로딩 |
| 모바일&반응형(복수) | 햄버거메뉴·바텀시트·당겨서새로고침·반응형레이아웃·PWA |
| 인터랙션(복수) | 낙관적UI·스크롤애니메이션·드래그&드롭정렬·마이크로애니메이션·컨텍스트메뉴 |

### 이 프로젝트 화면별 확정 매핑 (기존 구현·설계와 대조)

| 분류 | 확정 선택 | 근거(이미 한 것 vs 새로 정하는 것) |
|---|---|---|
| 레이아웃 | **탑다운**(agent-view/requirements.html이 이미 이 패턴 — 헤더→요약카드→필터→테이블 수직 흐름) | 기존 구현과 일치 확인, 변경 없음 |
| 디자인 스타일 | **플랫 미니멀 + 다크퍼스트**(`tokens.css`의 `[data-theme='dark']` 기본값과 배지·막대바 방식이 이미 이 조합) | 기존 구현과 일치 확인, 변경 없음 |
| GNB | **좌측 사이드바**(workbase wizard 자체의 `wiz-sidebar` 패턴을 0차 마법사가 그대로 이식하기로 이미 §1에서 확정) | 기존 설계(§1)와 일치, 신규 결정 아님 |
| 콘텐츠 표현 | **데이터 테이블**(이미 구현) + **KPI 카드**(이미 구현, 요약카드) — 신규로 **뱃지**(상태·문서유형·영역·계층 배지, 1차 설계 §3 매핑표에서 4종으로 확장 예정) 채택 | 기존 2종 확인 + 뱃지 조합 명시적으로 이 카탈로그 용어로 재정리 |
| 폼&입력 | **단계별 마법사**(0차 전체) + **태그입력**(솔루션스택, 1차 §2-4) + 신규 **파일업로드(DnD)** 채택 — 0차 §2 STEP 3(첨부 문서 유형)의 실제 업로드 인터랙션으로 이 패턴을 명시(이전 라운드엔 "카드 선택"까지만 설계, 실제 파일을 드래그해 올리는 방식은 미정의였음 — 이번에 메움) | **신규 확정**(이전 미결이었던 부분) |
| 알림&피드백 | **모달 다이얼로그**(2차 설계의 미리보기 모달이 이미 이 패턴) + 신규 **토스트**(상태변경 성공/실패 즉시 피드백) + **인라인 오류**(사유 필수입력 미기재 시 폼 필드 옆 오류 표시) 채택 | 모달은 기존 확인, 토스트·인라인오류는 **신규 확정** |
| 모바일&반응형 | **미채택** — 내부 관리도구는 데스크톱 사용을 전제(헌법 §4 "목적 불일치" 판정 유지, 과잉설계 회피) | 명시적 제외 유지 |
| 인터랙션 | 신규 **컨텍스트 메뉴**(요구사항 행 우클릭 → 빠른 상태변경, 관리 포인트 강화) 채택. 낙관적UI·드래그정렬·마이크로애니메이션은 **미채택**(내부도구 규모에 과함) | **신규 확정** 1건 + 명시적 제외 다수 |

### §6-A 정정 — 이전 라운드 문구 교정

`§2`의 "9단계 중 3단계(시스템환경·DB·UI/UX)를 의도적으로 제외"는 부정확했다. 정확히는:
**시스템환경·DB는 완전 제외(목적 불일치 유지)**, **UI/UX는 "프로젝트별 재선택 단계"로는
제외하되 "전체 화면 공통 결정"으로 본 §6-A에서 확정**했다 — 제외와 반영을 혼동하지 않도록
§2 표 자체도 함께 정정한다(아래).

## §6. 품질검토 — MPCR 7관점 (신설 0차 자체 검토)

| 관점 | 검토 결과 |
|---|---|
| 개발 | workbase UI 컴포넌트(체크카드·태그입력)는 코드가 아니라 **패턴**만 가져옴 — 기술스택이 달라도(이 프로젝트는 Python 백엔드, workbase는 Go) 프론트 HTML/CSS/JS는 그대로 이식 가능(둘 다 정적 파일 서빙, `frontend/styles/tokens.css` 계승 이미 완료) |
| 설계 | 9단계 중 시스템환경·DB 2단계는 완전 제외(목적 불일치), UI/UX 1단계는 §6-A에서 "프로젝트별 재선택"이 아닌 "전체 화면 공통 결정"으로 반영 — 제외와 반영을 구분해 "벤치마킹=전체 복사"가 아님을 분명히 함 |
| 운영 | 마법사 완료 전엔 청크 분류(1차)가 동작하지 않도록 설계(분야 미선택 상태에서 분류기를 돌리면 §2의 "1차 필터" 근거가 없어짐) — 순서 의존성 명시 |
| 정보안정성 | PII 게이트(§3)가 미리보기 화면의 유일한 보호 장치 — 3차 이후 실제 접근제어(역할 인증)까지 이어지지 않으면 "클릭스루 확인"은 형식적 보호에 그침(한계 정직 기록) |
| 헌법정합 | 00_PROJECT_CONSTITUTION.md §3 "Phase 0 환경설정"이 이미 "임의 가정 금지, 요구사항 문서에서 추출한 값으로 확정"이라 명시 — 이 마법사가 그 Phase 0을 구체화하는 것이라 헌법과 정합 |
| 검증 | 마법사 응답 저장소를 SQLite 대신 JSON(TaskStore 패턴)으로 결정 — 이유: 이미 이 프로젝트가 SQLite/pgvector를 "의존성 미설치 상태로 보류"해뒀기 때문에(00_DESIGN_TOC.md Phase 2.3) 새 DB를 여기서 끌어들이면 불일치. **기술스택 일관성 위해 JSON 유지가 맞다** |
| 책임 | 마법사 완료자(누가 이 프로젝트의 분야를 확정했는지)를 `created_by` 필드로 기록 — 2차 설계 `status_history`의 actor 개념과 동일 패턴 재사용 |

**게이트 0 결론**: **PASS** — "정보안정성" 행의 한계(클릭스루 확인이 역할인증 없이는
형식적 보호에 그침)는 의도적 범위 제외(헌법 §4 판정)로 이미 정직하게 기록돼 있어 추가
해소 대상이 아니다. 나머지 6관점 모두 리스크 없이 통과.

## §7. 디자인 시안 선행 게이트 체크포인트 (신규, 2026-07-19 — `01_PHASE1_DATA_MODEL.md`
§5·§2-5~§2-7과 연결)

**§6-A와의 구분(혼동 방지)**: §6-A는 "이 관리 시스템 화면 전체에 적용할 한 벌의 UI/UX
결정"(일회성, 프로젝트 착수 시 한 번 확정)이고, 본 §7은 "이번에 등록되는 프로젝트의
개별 요구사항들이 (관리 대상 시스템의) 디자인 시안 확정을 선행 조건으로 요구하는가"
(요구사항 단위, 신규 요구사항이 들어올 때마다 갱신)다 — 서로 다른 레벨의 결정이라
§6-A를 고치지 않고 새 절로 추가한다.

**STEP 6(완료 확인) 화면 보강 설계**: 기존 §2 표의 STEP 6("완료 확인")이 `Project
DomainSnapshot` 최초 생성을 트리거하는 지점이다(§5). 여기에 `01_PHASE1_DATA_MODEL.md`
§5의 스캔 규칙을 적용한 배너를 추가한다:

| 스캔 결과 | STEP 6 화면 표시 |
|---|---|
| `design_draft_gate=MANDATORY` 요구사항 1건 이상 | 빨간 배너: "N건의 요구사항이 디자인 시안 확정을 선행 조건으로 요구합니다 — Phase 1 스캐폴딩 착수 전 디자인 시안을 먼저 확정하세요" (차단은 아님 — 경고 후 진행 여부는 사람이 결정, 04_PHASE0 §6 "책임" 행의 `created_by` 기록 원칙과 일관되게 무시하고 진행해도 그 결정이 `design_draft_gate_history`에 남는 자동판정 그대로 보존됨) |
| `design_draft_gate=STRATEGIC_MANDATORY`만 있음(MANDATORY 없음) | 노란 배너(권장): "M건의 요구사항이 디자인 시안을 먼저 진행하면 유리할 수 있습니다(전략적 판단)" |
| 전부 `NOT_MANDATORY` | 배너 없음, 기존 흐름 그대로 |

이 배너는 0차 마법사(최초 등록)와 이후 요구사항이 중간에 추가돼 재스캔될 때 모두 같은
규칙으로 갱신된다(`01_PHASE1_DATA_MODEL.md` §5 "최초/중간 신규 요구사항 모두 적용"
그대로 상속 — 이 문서에서 별도 판정 로직을 만들지 않음, CRZ).

**최초 버전이 놓친 것(사용자 지적, 2026-07-19 반영 — §7-A로 보강)**: 위 배너 표는 project
전체가 이미 시안을 확정해뒀는지를 반영하지 않아, MANDATORY 요구사항이 나올 때마다 매번
배너가 뜨는 것으로 오독될 수 있었다. `01_PHASE1_DATA_MODEL.md` §5-1·§5-2에서 이를
`project_design_draft_confirmed` 플래그로 해소했고, 그 플래그를 세우는 단계를 아래
§7-A에서 이 마법사 흐름에 실제로 연결한다.

### §7-A. 프로젝트 레벨 시안 확정 플래그를 세우는 단계 (신규, 2026-07-19)

**세우는 지점**: STEP 6("완료 확인") 화면에 §6-A(전체 화면 공통 UI/UX 결정)가 이미
확정돼 있다는 사실과 별개로, "이 프로젝트가 다루는 요구사항들의 UI/UX 디자인 시안 자체
(관리 대상 시스템의 화면 시안)가 이미 확정됐습니까?"를 묻는 체크박스 1개를 추가한다.
사람이 체크하고 STEP 6을 저장하면 `ProjectConfig.project_design_draft_confirmed = True`
+ `project_design_draft_confirmed_by`/`_at`이 함께 기록된다(§5-1, `created_by`/
`created_at`과 동일 저장 시점·동일 패턴 — 별도 API 호출 추가 없이 기존 STEP 6 저장
액션에 필드만 얹는다).

**세운 이후 동작(사용자 지적의 핵심)**: 이 플래그가 `True`인 프로젝트는, 그 뒤에 새로
추가되는 요구사항이 `design_draft_gate=MANDATORY`로 분류되더라도 **개별 요구사항 단위
게이트가 기본적으로 스킵**된다(`01_PHASE1_DATA_MODEL.md` §5-2 자동 통과 경로) — 위
§7 배너 표는 `project_design_draft_confirmed == False`인 프로젝트에만 적용되는 것으로
범위를 좁힌다. 즉:

| `project_design_draft_confirmed` | 개별 요구사항 게이트 동작 |
|---|---|
| `False`(기본값, 아직 미확정) | §7 배너 표 그대로 — MANDATORY=빨간 배너, STRATEGIC_MANDATORY=노란 배너 |
| `True`(사람이 STEP 6에서 확정) | 배너 없음, 게이트 자동 통과 — 단, 개별 요구사항에 `design_draft_gate_override=True`가 수기 지정된 경우는 예외적으로 §7 배너 표가 그 요구사항 1건에 한해 그대로 적용된다 |

**수기 오버라이드 입력 경로**: `design_draft_gate_override`(§5-2)는 이 0차 마법사가
아니라 요구사항 상세 화면(`agent-view/requirements.html`, 1차 설계 §3 매핑표)에서
요구사항 단위로 사람이 켜는 값이다 — 0차는 프로젝트 전역 플래그만 다루고, 요구사항별
예외는 요구사항 화면이 다룬다(레벨 분리, §7 서두의 §6-A 구분 원칙과 동일하게 유지).

**design_draft_gate 코드 구현 완료(2026-07-19)**: `backend/adapters/persistence/
project_config_store.py`의 `ProjectConfig`에 `project_design_draft_confirmed`/`_by`/`_at`
필드 추가(§7-A), `ProjectConfigStore.save()`가 `created_by`/`created_at`과 동일 저장
시점에 확정자·확정시각을 함께 기록. 요구사항 단위 게이트 판정 순수함수는
`backend/domain/requirements/design_gate.py`(1차 설계 문서에 상세 기록)로 구현. 이
0차 문서가 다루는 STEP 6 배너 UI 자체(실제 화면 렌더링)는 아직 미구현 — 이번 사이클은
데이터 모델·판정 로직까지만(과장 금지, T98 AIP).

## §8. STEP 2(분야 선택) 대폭 보완 — 용어 설명·HA 조건부 아키텍처·지식페이지·보안레벨·다이어그램 (2026-07-25 신규, 설계만·구현 미착수)

> **AskUserQuestion 확정 사항(2026-07-25, `/aegis-oneshot-plan`)**: ①그리드/LLM/리포트
> 솔루션 추천정보 및 보안 지식페이지는 **실시간 외부 검색 API 연동이 아니라, 이 세션에서
> WebSearch로 조사한 정적 큐레이션 콘텐츠**로 구현 ②아키텍처 다이어그램도 정적 방식으로
> 즉시 구현 ③**이번 턴은 설계문서까지만** — 코드 구현은 다음 턴부터 항목별 단계 진행.

### §8-1. 실측 근본원인 — 용어 설명이 "존재하는데 안 쓰이고 있었다"

`backend/domain/requirements/codes.py`에 `DOC_TYPE_CODES`·`LAYER_CODES`는 이미
`{코드: 한국어설명}` 딕셔너리 형태로 설명을 갖고 있다(예: `"SECU": "보안영역 (아키텍처
계층 관점 — area_code=SEC와는 다른 축)"`) — **그러나 `DOMAIN_CODES`(§5 기술영역)만
유일하게 설명 없는 순수 `set`**(`{"WEB", "WAS", "DB", ...}`)이고, 프론트엔드
`project-setup.html:186-189`의 `renderCardGrid()`는 애초에 어떤 코드든 **원시 코드
문자열만 렌더링**(`${c}`)해 이미 존재하는 `DOC_TYPE_CODES`/`LAYER_CODES`의 설명조차
화면에 안 쓰고 있었다 — 사용자가 "용어만 있고 설명이 없다"고 느낀 것은 **콘텐츠 부재가
아니라 배선 부재**(두 곳 다 고쳐야 함: ①`DOMAIN_CODES`에 설명 추가 ②프론트가 설명을
실제로 렌더링하도록 수정).

### §8-2. §5 기술영역(DOMAIN_CODES) 라벨·설명 확정 (codes.py 보강안)

| 코드 | 쉬운 라벨(신규) | 설명(신규) |
|---|---|---|
| WEB | 웹 프론트엔드 | 사용자가 브라우저로 직접 보는 화면(웹사이트·웹앱) 관련 요구사항 |
| WAS | 애플리케이션 서버(WAS) | 화면 뒤에서 실제 로직을 처리하는 서버(백엔드) 관련 요구사항 |
| DB | 데이터베이스 | 데이터를 저장·조회하는 저장소(DB) 구성·성능 관련 요구사항 |
| SEC | 보안 | 암호화·인증·접근제어 등 보안 관련 요구사항 |
| GRID | 데이터 그리드(표 화면) | 대량 데이터를 표(그리드) 형태로 보여주고 편집하는 화면 컴포넌트 |
| A11Y | 웹 접근성 | 장애인·고령자 등 누구나 이용 가능하게 하는 웹 표준 준수 요구사항 |
| VULN | 취약점 점검 | 보안 취약점 진단·모의해킹·코드 점검 관련 요구사항 |
| GW | 게이트웨이/연계 | 외부 시스템과 데이터를 주고받는 연계·중계 서버 관련 요구사항 |
| LLM | AI(생성형 AI/LLM) | ChatGPT류 AI 모델을 활용하는 기능(요약·분류·챗봇 등) 관련 요구사항 |
| RPT | 보고서/리포트 | 데이터를 문서·PDF·엑셀 등으로 출력하는 보고서 기능 관련 요구사항 |

`LAYER_CODES`(§5-B 아키텍처 계층)도 카드 위에 짧은 라벨을 추가한다(설명 문자열은 이미
있음, 라벨만 신설):

| 코드 | 쉬운 라벨(신규) |
|---|---|
| SYS | 시스템/인프라 계층 |
| SECU | 보안 계층 |
| UXENV | 사용자 환경 계층 |
| TPI | 외부 연동(서드파티) 계층 |
| INTG | 내부 연계 계층 |

**구현 방식(다음 턴)**: `codes.py`의 `DOMAIN_CODES`를 `set` → `{코드: {"label":..,
"desc":..}}` 딕셔너리로 승격(하위호환: `DOMAIN_CODES.keys()`로 기존 `in DOMAIN_CODES`
검증 코드는 그대로 동작 — dict의 `in`은 키 검사이므로 회귀 없음, CRZ). 프론트
`renderCardGrid()`를 라벨(굵게)+설명(작은 글씨, 툴팁 또는 카드 하단)을 함께 그리도록
확장.

### §8-3. HA(이중화) 토글 + 조건부 아키텍처 구성 옵션 (STEP 2 신규 하위 섹션)

STEP 2에 "배포 구성" 하위 섹션을 신설한다 — WEB/WAS/DB는 §8-2 카드 그대로 항상 표시하고,
그 아래 **"이중화(HA) 구성입니까?"** 토글(단일/이중화 2택)을 추가한다. **토글 상태에
따라 아래 필드가 동적으로 나타난다**(단일이면 아래 필드 전부 숨김 — 불필요한 복잡도 노출
방지, T57 PVS):

```
[ ] 단일 구성        [●] 이중화(HA) 구성   ← 라디오 토글

  ↓ "이중화" 선택 시에만 아래 필드 펼쳐짐 ↓

  HA 관리 방식        [드롭다운] Keepalived+VIP / Pacemaker+Corosync / 클라우드 LB(ALB/NLB) / 기타(직접입력)
  WebSocket 사용 여부  [토글] 사용 안 함 / 사용함
    ↳ "사용함"이면 →  실시간 백플레인 [드롭다운] Redis Pub/Sub / NATS / 없음(단일노드로 충분)
  데이터 그리드 사용   [토글] 사용 안 함 / 사용함
    ↳ "사용함"이면 →  그리드 솔루션 [자유입력+추천목록, §8-6 참조] + 오픈소스 여부 [Y/N] + 가이드 URL [입력]
  AI(LLM) 업무 여부    [토글] 없음 / 있음
    ↳ "있음"이면   →  LLM 서버 방식 [자유입력+추천목록, §8-6] + 서버 정보(호스트/포트/모델명) [입력]
  리포트 기능 여부     [토글] 없음 / 있음
    ↳ "있음"이면   →  리포트 솔루션 [자유입력+추천목록, §8-6] + 무료/상용 [Y/N] + 가이드 URL [입력]
```

이 구조는 §5의 "카드=고정 선택"과 다른 **"조건부 상세 폼"** 패턴이라 workbase에 선례가
없다 — 그러나 신규 위젯을 발명하지 않고 기존 `radio-cards`(ACCESS_POLICIES가 이미 쓰는
패턴)+`tag-wrap`(솔루션스택이 이미 쓰는 패턴)+단순 `<select>`만 조합해 구현한다(CRZ,
STEP 4의 태그입력을 그리드/LLM/리포트 3곳에서 재사용).

**데이터 모델 확장안**(`ProjectConfig`에 추가, 전부 옵셔널 — 기존 프로젝트 하위호환):

```python
is_ha: bool = False
ha_management: str | None = None       # "keepalived_vip" | "pacemaker_corosync" | "cloud_lb" | 자유입력
uses_websocket: bool = False
realtime_backplane: str | None = None  # "redis" | "nats" | None
uses_grid: bool = False
grid_solution: str | None = None
grid_is_opensource: bool | None = None
grid_guide_url: str | None = None
has_ai_workload: bool = False
llm_solution: str | None = None
llm_server_info: str | None = None
has_report: bool = False
report_solution: str | None = None
report_is_free: bool | None = None
report_guide_url: str | None = None
```

### §8-4. 정적 큐레이션 추천정보 (WebSearch 조사 결과, 2026-07-25 — AskUserQuestion 확정 방식)

프론트 `tag-suggestions` 영역에 아래 추천 태그+가이드 링크를 하드코딩한다(사용자가
클릭하면 태그+가이드URL 필드에 자동 채워짐, 자유 수정 가능 — 강제 아님):

**데이터 그리드(오픈소스)**
| 솔루션 | 오픈소스 | 특징 | 가이드 |
|---|---|---|---|
| Tabulator | Y | AG Grid의 대부분 기능(그룹핑·트리데이터·인라인편집·다중 export)을 엔터프라이즈 라이선스 비용 없이 제공 | [tabulator.info/docs](http://tabulator.info/docs) |
| Toast UI Grid | Y(NHN, MIT) | 국내(NHN) 개발, 한국어 문서·커뮤니티 접근성 좋음 | [ui.toast.com/tui-grid](https://ui.toast.com/tui-grid) |
| AG Grid Community | Y(무료 티어) | 초대용량 가상 스크롤 렌더링 성능 최상 — 그룹핑/피벗 등 고급기능은 Enterprise 유료 | [ag-grid.com/documentation](https://www.ag-grid.com/documentation) |
| Handsontable | N(무료 커뮤니티 버전 없음) | 엑셀과 동일한 수식·서식 UX가 필요할 때만 고려(유료) | — |

**AI/LLM 서버(온프레미스)**
| 솔루션 | 특징 | 적합한 경우 |
|---|---|---|
| Ollama | 가장 쉬운 설치(OpenAI 호환 API), GitHub 16만+ star | 소규모·PoC, 빠른 실험 |
| vLLM | PagedAttention·연속배칭으로 동시사용자 100+ 규모에서 지연시간 최저 | 운영 환경, 다수 동시 사용자 |
| LocalAI | OpenAI API 완전 호환 드롭인, LLM 외 STT/TTS/이미지생성까지 지원 | 멀티모달(음성·이미지)까지 필요할 때 |

**리포트 솔루션**
| 솔루션 | 라이선스 | 특징 |
|---|---|---|
| JasperReports Community | LGPL v2.1(무료) | Crystal Reports와 가장 유사한 픽셀 단위 정밀 출력, Java 진영 |
| Metabase(Open Source) | AGPL v3(무료) | 비개발자도 SQL 없이 대시보드 구성 가능, 스타트업/SMB에 인기 |
| ReportBro | 오픈소스 | 브라우저 기반 WYSIWYG 리포트 디자이너, Python 연동 용이 |

> **출처**: [Bryntum — Best JS Data Grids 2026](https://bryntum.com/blog/the-best-javascript-data-grids-in-2026/) · [rv-grid.com 2026 비교](https://rv-grid.com/blog/best-js-datagrid-in-2026) · [Contabo — Ollama vs LocalAI 2026](https://contabo.com/blog/ollama-vs-localai-best-self-hosted-openai-compatible-llm-server/) · [glukhov.org — Ollama vs vLLM 2026](https://www.glukhov.org/llm-hosting/comparisons/hosting-llms-ollama-localai-jan-lmstudio-vllm-comparison/) · [Helical Insight — Jaspersoft 대안 2026](https://www.helicalinsight.com/10-best-open-source-jaspersoft-alternatives-in-2026/) · [Wikipedia — JasperReports](https://en.wikipedia.org/wiki/JasperReports)

### §8-5. 보안 레벨 선택 (STEP 2 또는 신규 STEP 2.5 — Stage5에서 배치 확정)

"그냥 선택만" 요청에 맞춰 **체크박스 나열이 아니라 3단계 프리셋 + 개별 토글** 혼합으로
설계한다(과도한 선택지 피로 방지, workbase STEP 알림&피드백 카탈로그의 "인라인오류"
패턴과 함께):

```
보안 수준   [◉ 표준(HTTP)]  [○ 강화(HTTPS)]  [○ 커스텀]
              ↓ "강화"/"커스텀" 선택 시 펼쳐짐
  전송 암호화     HTTP(기본) → HTTPS/SSL [토글] → "사설 인증서(자체서명 openssl)" | "공인 인증서(Let's Encrypt 등)" [택1]
  비밀번호 저장   SHA-256(기본, 사용자 요청) → ⚠ 경고 배지 + "권장: Argon2id" 대안 제시 [토글로 전환 가능]
  로그인 세션     세션 기반(기본, 항상 켜짐 — 끌 수 없음)
```

**보안 전문가 지식페이지 연결(§8-6)에서 근거 제시**: SHA-256을 "기본"으로 두되 사용자가
그 선택의 실제 위험을 알고 결정하도록 **경고 배지 + 지식페이지 링크**를 붙인다(과장도
은폐도 아닌 정직한 정보 제공, T98 AIP) — WebSearch 조사 결과 **OWASP 2026 기준 SHA-256
단독 해시는 취약**(GPU로 초당 수천억 회 대입 가능, 메모리 하드니스 없음)하고 **Argon2id
(OWASP 권장, RFC 9106)** 또는 최소 **bcrypt(cost≥10, 레거시 허용)**가 권장된다 — 이
사실을 지식페이지에 명시하고, 선택 화면에도 "SHA-256(비권장 — 이유 보기)" 배지를
붙인다.

**데이터 모델 확장안**:
```python
security_level: str = "standard"        # "standard" | "enhanced" | "custom"
use_https: bool = False
tls_cert_type: str | None = None        # "self_signed" | "public_ca"
password_hash_algo: str = "sha256"      # "sha256" | "bcrypt" | "argon2id"
session_based_login: bool = True        # 항상 True(끌 수 없음 — UI에도 비활성 표시)
```

### §8-6. 아키텍처/보안 지식페이지 신설 (`frontend/views/architecture-glossary.html`, 신규 파일)

STEP 2·보안선택 화면 각 카드/토글 옆에 **"❓ 알아보기"** 링크를 붙여 이 신규 페이지의
해당 앵커(`#WEB`, `#SECU`, `#security-hash` 등)로 이동시킨다(새 창이 아니라 같은 GNB/LNB
셸 안의 새 화면 — 기존 셸 구조 재사용, CRZ). 페이지 구성:

1. **§5 기술영역 10종 + §5-B 계층 5종**: §8-2 표 그대로, "왜 필요한가"·"실무 예시" 1~2문장씩
2. **HA/이중화 개념**: HA가 왜 필요한지(단일 서버 장애 시 서비스 중단 방지), Keepalived+VIP
   vs Pacemaker+Corosync vs 클라우드 LB의 차이(관리 난이도·비용 순으로 비교표)
3. **WebSocket+Redis**: 왜 이중화 환경에서 WebSocket에 Redis/NATS 같은 백플레인이 필요한지
   (여러 WAS 인스턴스 간 실시간 메시지 동기화 문제) — 그림으로 설명(§8-7 다이어그램 연동)
4. **그리드/LLM/리포트 솔루션 비교**: §8-4 표 그대로 + 출처 링크
5. **보안 기술**: HTTP vs HTTPS(SSL/TLS) 차이, 자체서명 vs 공인인증서 차이, 비밀번호
   해시 알고리즘 비교표(SHA-256 vs bcrypt vs Argon2id — §8-5 경고 근거)

이 페이지에서 사용자가 실제로 "이번 프로젝트가 선택한 기술"을 클릭하면(§8-5/§8-3에서
이미 선택한 값과 연동) §8-7 다이어그램이 그 선택을 반영해 하이라이트된다.

### §8-7. 아키텍처 다이어그램 시각화 (Mermaid.js, 정적 클라이언트 렌더링)

**기술 선택 근거**: 신규 외부 라이브러리 설치 없이(CDN 1줄) 텍스트 기반 다이어그램을
그릴 수 있는 Mermaid.js를 채택한다(CRZ — 이 세션의 Artifact 산출물에서도 이미 표준
지원되는 방식과 동일 계열 기술, 이 프로젝트 프론트가 정적 HTML+JS 구조라 별도 빌드
파이프라인 없이 `<script src="mermaid.min.js">` 한 줄로 통합 가능).

**다이어그램 자동 생성 로직**: STEP 2/보안선택에서 모은 `ProjectConfig` 값을 읽어
Mermaid `flowchart` 문법 문자열을 JS로 조립(신규 서버 로직 없음 — 순수 클라이언트
렌더링, `buildProjectContextBlock` 패턴처럼 "이미 모은 설정을 다른 형태로 조립"하는
동일 원칙 재사용):

```
단일 구성 예시:                          이중화 구성 예시(WebSocket+Redis 사용 시):
[사용자] → [WEB] → [WAS] → [DB]         [사용자] → [로드밸런서/HA관리]
                                                        ↓         ↓
                                                    [WEB-1]    [WEB-2]
                                                        ↓         ↓
                                                    [WAS-1]    [WAS-2]
                                                        ↓         ↓
                                                       [Redis Pub/Sub]
                                                        ↓         ↓
                                                       [DB(공유)]
```
+ HTTPS 선택 시 사용자↔WEB 화살표에 자물쇠 아이콘 라벨, LLM 있음 선택 시 WAS 옆에
[LLM 서버] 박스 추가, 그리드/리포트도 각각 사용 여부에 따라 부가 박스로 표시 — **선택한
것만 그려지고, 선택 안 한 것은 다이어그램에 나타나지 않는다**(정보 과잉 방지).

### §8-7-A. 참고 이미지 반영 디자인 스펙 보강 (2026-07-25, aegis-design000)

사용자가 제시한 참고 이미지(`ref_dashboard.jpg` — 보안 모니터링 대시보드 "KOMINFO SER
Monitoring System")를 Read 도구로 직접 열어 실측했다. §8-7의 Mermaid 정적 flowchart 안을
그대로 유지할지, 이 참고 이미지 스타일로 격상할지 검토한 결과다.

**1) 실측 관찰 — 참고 이미지에 실제로 있던 것 (추정 아님, 직접 확인)**

| 구역 | 관찰 내용 |
|---|---|
| 전체 배경 | 거의 순검정에 가까운 네이비(약 `#0a0e17`~`#0d1420`), 배경에 흐릿한 블루 광원 블롭 장식 |
| 좌측 패널 | 로고+타이틀, 얇은 pill형 상태바 4줄(알림 로그), 도넛차트(SIEM TOP10 이벤트, 마젠타 55%·시안 21%·퍼플 16% 구간), 꺾은선/영역 차트("SECURITY EVENTS TREND — LAST DAY", 시안·퍼플·주황 3색 라인, x축 15h~0h) |
| 중앙 패널 | `› Network Visibility` / `› Assets Visibility` / `› Global Visibility` 3개 그룹 패널(상단 얇은 시안 보더+대문자 라벨). 각 그룹 안에 **원형 게이지(도넛형 링) 위젯**이 2~5개씩 — 큰 퍼센트 숫자(예: 55%·60.1%·20.1%·100%·100%) + 하단 라벨(예: "IDS Enabled — 1/1 Networks") + 게이지 링 색(시안/그린/오렌지, 값에 따라 다름) |
| 우측 패널 | 상단 "기본뷰/자산뷰" pill 토글, 하단 네트워크 토폴로지 노드-링크 다이어그램 — Internet(구름 아이콘) → Router 1/2 → Firewall 1/2(불꽃 아이콘) → Web Firewall 1/2(지구본 아이콘) → Switch 1/2 → Server 1~4(랙 아이콘), 점선 연결선, 스위치↔서버 구간은 X자 교차 배선 |
| 공통 톤 | 카드마다 1px 시안 보더 + 은은한 글로우(box-shadow), 모서리 반경 8~10px, 헤더는 대문자+자간 넓힘 |

**2) 판단 — 가져올 것 vs 버릴 것 (이 프로젝트는 "실시간 보안 모니터링"이 아니라
"설정값 기반 정적 요약"이므로 실시간성이 전제된 요소는 전부 버린다)**

| 요소 | 판정 | 근거 |
|---|---|---|
| 원형 게이지 위젯(도넛 링+퍼센트) | **채택** | 값만 바뀌면 "설정 완성도/보안 충족도" 같은 정적 지표에도 그대로 의미 있음(§3 참조) |
| 그룹 패널(`› 라벨` 헤더 + 얇은 보더) | **채택** | STEP2 정보를 3그룹(구성 완성도/보안 충족도/이중화 커버리지)으로 나누는 §8-7 목적과 구조가 일치 |
| 네트워크 토폴로지 노드-링크 다이어그램의 "느낌"(아이콘 노드+글로우+연결선) | **채택** | §8-7이 이미 그리려는 WEB→WAS→DB 다이어그램의 렌더링 방식만 업그레이드하는 것 — 신규 콘텐츠 아님 |
| SIEM 도넛차트(이벤트 카테고리 비율) | **버림** | 실시간 이벤트 로그 데이터가 이 프로젝트에 존재하지 않음 — 억지로 채우면 가짜 데이터(S1 위반) |
| 이벤트 트렌드 라인차트(시계열) | **버림** | 동일 이유 — 시계열 데이터 자체가 없음 |
| 좌측 pill형 알림 로그 스트립 | **버림** | 실시간 알림 개념이 이 화면에 없음 |
| 전체를 다크네온(순검정+시안글로우)으로 하드코딩 | **버림(부분 채택으로 완화)** | `tokens.css`가 라이트를 기본 테마로 명시적으로 되돌린 상태(2026-07-22 커밋 사유 참조) — 이 화면만 강제로 다크로 고정하면 나머지 STEP1~3과 테마 불일치가 생긴다. **색상 언어(시안/그린/앰버 게이지, 얇은 보더+은은한 글로우)만 라이트/다크 양쪽에서 성립하도록 토큰화**해서 가져온다 |
| 우측 상단 "기본뷰/자산뷰" 토글 | **보류(이번 스코프 아님)** | 유용할 수 있으나 이번 요청 범위(정적 요약 1개 뷰) 밖 — 과잉설계 방지, 후속 개선 후보로만 기록 |

**3) 원형 게이지 — 이 프로젝트 맥락 재정의 (실시간 데이터 아님)**

참고 이미지의 게이지는 "실시간 스캔 진행률"이었지만, 이 프로젝트에서는 **STEP2에서 사용자가
이미 선택 완료한 설정값의 요약 지표**로 재정의한다 — 3그룹 대응:

| 그룹(§8-7 3영역과 대응) | 게이지 의미 | 값 산식(신규 계산 로직 없음 — 이미 모은 `ProjectConfig` 필드 카운트) | 색상 규칙 |
|---|---|---|---|
| 구성 완성도 | STEP2 필수 선택 항목 중 완료된 비율 | `선택완료 필드 수 / 필수 필드 수 × 100` | 100% 미만=`--color-brand-primary`(진행중, 상태 아님) / 100%=`--ok`(완료) |
| 보안 충족도 | §8-5 보안 레벨 선택값(최소/권장/강함)의 충족 단계 | 최소=33%, 권장=66%, 강함=100% (레벨 열거값 매핑, 계산 아님) | 최소=`--warn`(취약 경고 성격 유지) / 권장=`--color-brand-primary` / 강함=`--ok` — **명시적 상태색이므로 §8-5 경고 취지와 일관** |
| 이중화 커버리지 | HA 적용된 계층 수(WEB/WAS/DB 중) | `이중화 계층 수 / 전체 계층 수(3) × 100` | 값과 무관하게 항상 `--accent2`(퍼플, 중립색) — **단일 구성도 유효한 선택**이므로 0%를 "나쁨"으로 색칠하지 않는다(의미색 분리 원칙, SPECIALIST §3 "상태(good/warn/critical)는 accent와 별개") |

**4) Mermaid 유지 vs 커스텀 SVG/CSS 격상 — 트레이드오프 판단**

| 기준 | Mermaid.js(§8-7 원안) | 커스텀 SVG/CSS(격상안) |
|---|---|---|
| 구현 난이도 | 낮음 — 문자열 조립만(D3) | 중간 — 노드 좌표 배치+SVG 생성 함수(D3~D4, 여전히 클라이언트 전용) |
| 참고 이미지 느낌(아이콘 노드+글로우+상태색) 재현 | **낮음** — Mermaid 테마 변수로는 노드에 아이콘·글로우·색상별 상태를 세밀 제어하기 어려움(기본 사각박스+화살표 톤에 머무름) | **높음** — 노드 스타일 완전 제어 가능 |
| 자기완결성(S2, 외부 CDN 금지) | **위반 소지** — `<script src="mermaid.min.js">` CDN 의존(오프라인/사내망 방화벽 환경에서 깨질 수 있음, W7 의존성 리스크로 이미 §8-10에 내재) | **충족** — 순수 SVG+CSS, 외부 자산 0 |
| 토폴로지 복잡도 | 노드 종류 최대 6~7개(사용자/WEB/WAS/Redis/DB/LLM/그리드/리포트), 분기 최대 2단(이중화 시) — **고정되고 작음** | 위와 동일 — 고정 소규모라 손코딩 SVG path 없이 "생성 함수 1개"로 충분(SPECIALIST 안티패턴 "손으로 긴 SVG path" 아님, 좌표는 그리드 배치 규칙으로 계산) |
| 유지보수 | 문법 변경 시 Mermaid 버전 종속 | 이 프로젝트 CSS 변수 체계에 완전히 종속(장점: 테마 스위치 자동 대응) |

**권고: 커스텀 SVG/CSS로 격상한다 (Mermaid 폐기).** 이유는 난이도보다 두 가지가 결정적이다 —
① 토폴로지가 작고 고정적이라 "생성 함수 1개"로 손코딩 없이 구현 가능해 격상 비용이
낮고, ② CDN 의존 제거가 사내 프로젝트관리 도구라는 배포 맥락(방화벽/오프라인 가능성)에서
실질적 리스크 감소다. 참고 이미지의 핵심 시각 언어(아이콘 노드·글로우·상태색)는 Mermaid로는
재현 한계가 뚜렷해 "격상하지 않으면 참고 이미지를 반영한 게 아니라 흉내만 낸 것"이 된다.
**§8-10 W7의 작업 내용은 이 절로 대체된다** (표 자체는 CRZ상 삭제하지 않고 그대로 두되,
다음 턴 구현 시 "Mermaid 자동생성"이 아니라 아래 §5·§6 스펙을 따른다).

**5) CSS 방향 — `tokens.css`/`components.css` 기존 변수 재사용(신규 토큰 발명 최소화)**

```css
/* frontend/styles/components.css 에 추가할 블록 (신규 파일 아님, 기존 파일 확장) */

/* ── 아키텍처 요약 그룹 패널 ── */
.arch-summary { display: flex; gap: 14px; flex-wrap: wrap; margin: 16px 0 20px; }
.arch-group {
  flex: 1 1 220px; min-width: 220px;
  border: 1px solid var(--border-color); border-top: 2px solid var(--color-brand-primary);
  border-radius: 10px; padding: 14px 16px; background: var(--bg-secondary);
}
.arch-group h3 {
  font-size: 12px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--brand-text); margin: 0 0 12px;
}
.arch-group h3::before { content: "\203A\A0"; }  /* › + nbsp, 참고 이미지의 셰브런 라벨 재현 */
.arch-gauge-row { display: flex; gap: 14px; flex-wrap: wrap; }

/* ── 원형 게이지 (conic-gradient, 신규 라이브러리/캔버스 없음) ── */
.arch-gauge {
  --pct: 0; --ring: var(--color-brand-primary);
  width: 76px; height: 76px; border-radius: 50%; position: relative; flex-shrink: 0;
  background: conic-gradient(var(--ring) calc(var(--pct) * 1%), var(--hover-tint) 0);
  box-shadow: 0 0 0 1px var(--border-color),
              0 0 14px color-mix(in srgb, var(--ring) 35%, transparent);
  display: flex; align-items: center; justify-content: center;
}
.arch-gauge::before {
  content: ""; position: absolute; inset: 7px; border-radius: 50%; background: var(--bg-secondary);
}
.arch-gauge .pct { position: relative; z-index: 1; font-size: 16px; font-weight: 800; color: var(--text-primary); }
.arch-gauge-wrap { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 92px; }
.arch-gauge-label { font-size: 11px; color: var(--text-muted); text-align: center; line-height: 1.4; }

/* 그룹별 색상 롤 — inline style로 --ring 지정(JS에서 세팅), 정적 클래스도 폴백 제공 */
.arch-gauge.ring-ok { --ring: var(--ok); }
.arch-gauge.ring-warn { --ring: var(--warn); }
.arch-gauge.ring-brand { --ring: var(--color-brand-primary); }
.arch-gauge.ring-accent2 { --ring: var(--accent2); }

/* ── 토폴로지 SVG 컨테이너 ── */
.arch-topology { width: 100%; overflow-x: auto; border: 1px solid var(--border-color);
  border-radius: 10px; background: var(--bg-secondary); padding: 16px; }
.arch-topology svg { display: block; min-width: 480px; }
.arch-node rect, .arch-node circle {
  fill: var(--bg-primary); stroke: var(--border-color); stroke-width: 1.5;
}
.arch-node.node-active rect, .arch-node.node-active circle {
  stroke: var(--color-brand-primary);
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--color-brand-primary) 55%, transparent));
}
.arch-node text { fill: var(--text-primary); font-size: 11px; font-family: system-ui, sans-serif; }
.arch-link { stroke: var(--text-muted); stroke-width: 1.5; fill: none; }
.arch-link.link-logical { stroke-dasharray: 4 3; }  /* Redis Pub/Sub 등 논리적 연결 표시 */
```

색상은 전부 `--ok`/`--warn`/`--color-brand-primary`/`--accent2`/`--border-color`/
`--hover-tint`(모두 기존 `tokens.css` 토큰)만 참조 — 참고 이미지 관찰색(시안≈brand,
그린≈ok, 앰버≈warn, 퍼플≈accent2)이 이미 이 프로젝트 토큰과 거의 1:1로 대응해 **신규
색상 hex를 새로 정의할 필요가 없었다**(실측 대조 결과). `conic-gradient`+`color-mix`+
`filter: drop-shadow`는 모두 표준 CSS이며 다크/라이트 양쪽에서 `var()` 참조로 자동 대응
— 참고 이미지처럼 다크를 강제하지 않는다(§2 판정 근거).

**6) 구현 스펙 — 레이아웃 구조 + 컴포넌트 목록 (다음 턴 구현자용)**

```
project-setup.html — STEP2 하단, 기존 radio-cards/HA토글 영역 다음
┌─ .arch-summary (flex row, 3열) ──────────────────────────────────────────┐
│ ┌─ .arch-group "구성 완성도" ─┐ ┌─ "보안 충족도" ─┐ ┌─ "이중화 커버리지" ─┐│
│ │  ◉76px  4/5 항목            │ │  ◉76px 권장     │ │  ◉76px 계층 2/3   ││
│ │  (ring-brand or ring-ok)     │ │  (ring-warn/     │ │  (ring-accent2,   ││
│ │                              │ │   brand/ok)      │ │   항상 고정색)    ││
│ └──────────────────────────────┘ └──────────────────┘ └───────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
┌─ .arch-topology (SVG, overflow-x:auto) ────────────────────────────────────┐
│   [사용자] ──▶ [WEB-1] [WEB-2]        (이중화 미선택 시 WEB 1개만 렌더)    │
│                   │        │                                               │
│                [WAS-1]  [WAS-2] ── (LLM 있음 선택 시 옆에 [LLM] 박스)      │
│                   ╲        ╱                                               │
│               [Redis Pub/Sub] (link-logical 점선, WebSocket+Redis 선택 시만)│
│                       │                                                    │
│                   [DB(공유)]                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트 목록**: `.arch-summary`(래퍼) · `.arch-group`(그룹 패널 ×3) · `.arch-gauge-row`
· `.arch-gauge`+`.arch-gauge-wrap`+`.arch-gauge-label`(게이지, 그룹당 1~2개) ·
`.arch-topology`(SVG 컨테이너) · `.arch-node`(SVG `<g>`, variant: `node-user`/`node-web`/
`node-was`/`node-cache`/`node-db`/`node-llm`/`node-grid`/`node-report`) · `.arch-link`
(SVG `<path>`, `.link-logical` modifier). 노드 좌표는 §8-7의 "선택한 것만 그려진다" 로직을
그대로 유지 — `ProjectConfig` 필드를 읽어 노드 배열을 만들고, 배열 길이만큼 x좌표를
균등분할하는 단순 그리드 배치 함수 하나로 계산(신규 레이아웃 엔진 불필요).

### §8-8. UI/UX 개선 — 설명박스·타이틀 가시성 (STEP 전체 공통 적용)

기존 `.panel p.desc`(작은 회색 텍스트)를 **컬러 배경 설명박스**로 교체(CSS만 추가, 로직
변경 없음):

```css
.info-box { background: color-mix(in srgb, var(--color-brand-primary) 8%, transparent);
  border-left: 3px solid var(--color-brand-primary); border-radius: var(--border-radius-base);
  padding: 12px 14px; font-size: 13px; margin-bottom: 20px; line-height: 1.6; }
.panel h2 { font-size: 22px; font-weight: 800; padding-bottom: 8px;
  border-bottom: 2px solid var(--color-brand-primary); margin-bottom: 14px; }
```

이미 `tokens.css`/`components.css`에 정의된 `--color-brand-primary`·`--border-radius-base`
변수만 재사용(CRZ, 신규 디자인 토큰 발명 없음) — 다른 화면들(requirements.html 등)과
색상 일관성 유지.

### §8-9. 불필요 MD 파일 정리 후보 (실측, 2026-07-25)

| 경로 | 판정 | 근거 |
|---|---|---|
| `frontend/data/documents/payment-req-doc.md` | **보존(정정, 2026-07-25 재검토)** | 실행 경로 참조는 0건(2026-07-22 고도화로 `preview.html`의 `fetchDoc()`이 실시간 API로 전환)이나, **내용 실측 결과 §5 영역코드 10종(WEB/WAS/DB/SEC/GRID/A11Y/VULN/GW/LLM/RPT) 전부를 커버하는 의도적으로 잘 만들어진 예시 문서**임을 확인 — "실행 미사용=삭제 대상"이 아니라 온보딩/데모/수동테스트 참고자산으로 가치 있어 사용자 승인으로 삭제하지 않고 보존 확정(0-5 명확성 원칙 — 사용자 재확인 요청으로 최초 판단 정정) |
| `plans/_plan/UPGRADE_PLAN_2026-07-23.md`, `UPGRADE_PLAN_2026-07-24_5agent.md` | **보존(삭제 안 함)** | 진행 이력 감사 기록(T39 CRZ "감사·복원·추적 이력은 보호 대상") — "불필요"가 아니라 이력 |
| `plans/_plan/00_INDEX.md` 외 0~9번 설계서 | **보존** | 전부 능동 참조 중인 설계 SSOT |

**삭제는 이번 설계 문서 범위 밖**(파일 삭제=T90 DELP 보호경로 해당 가능성 검토 필요,
사용자 명시 승인 후 별도 턴에서 실행 — 이번엔 후보 식별까지만).

### §8-10. 작업 단위 전략 분해 (Stage 5 — 다음 턴부터 순서대로 진행 권장)

| WORK | 내용 | 복잡도 | 의존 |
|---|---|---|---|
| **W1** | `codes.py` DOMAIN_CODES를 dict(label+desc)로 승격 + `renderCardGrid()` 라벨/설명 렌더링 | SIMPLE(D1~2) | 없음 — 최우선 착수 권장(가장 즉각적인 사용자 불만 해소) |
| **W2** | STEP 2 설명박스·타이틀 CSS 개선(§8-8) | SIMPLE(D1) | 없음, W1과 병렬 가능 |
| **W3** | HA 토글 + 조건부 필드(§8-3) UI 구현 + `ProjectConfig` 필드 확장(§8-3) | MEDIUM(D3) | W1(카드 UI 패턴 먼저 정리 후) |
| **W4** | 그리드/LLM/리포트 추천 태그+가이드URL 필드(§8-4, §8-6 데이터 재사용) | SIMPLE(D2) | W3(조건부 필드 구조 위에 얹힘) |
| **W5** | 보안 레벨 선택 UI + `ProjectConfig` 보안 필드(§8-5) | MEDIUM(D2~3) | W1(설명박스 패턴 재사용) |
| **W6** | 지식페이지 신설(`architecture-glossary.html`, §8-6) | MEDIUM(D3) | W1~W2 완료 후(설명 콘텐츠가 이미 화면에 있어야 "더 알아보기" 링크가 의미 있음) |
| **W7** | Mermaid 다이어그램 자동생성(§8-7) | MEDIUM(D3) | W3+W5(HA·보안 선택값이 있어야 다이어그램 조립 가능) |
| **W8** | ~~`payment-req-doc.md` 삭제~~ — **보존 확정(2026-07-25)**, 삭제 안 함 | 종료 | 재검토 결과 예시자산 가치 확인, 사용자 승인으로 종결 |

**§PCM**: W1~W2 CLEAR(다른 관심사, 같은 파일이지만 순차 편집이면 충돌 없음) — 이후
W3→W4, W1→W5→W6, W3+W5→W7 순서 의존. **뼈대 우선순위(§3-A)**: W1이 나머지 전부의 시각적
기반(라벨 표시 패턴)이라 최우선.

### §8-11. 품질검토 — MPCR 7관점

| 관점 | 검토 결과 |
|---|---|
| 개발 | 신규 라이브러리는 Mermaid.js(CDN) 1개뿐 — 나머지는 기존 패턴(radio-cards·tag-wrap·check-card) 재조합(CRZ) |
| 설계 | §5(고정 카드)와 §8-3(조건부 상세폼)을 구분해 정보 과잉을 막음 — "이중화 아니면 아예 안 보임" 원칙 |
| 운영 | 정적 큐레이션 콘텐츠(그리드/LLM/리포트)는 시간이 지나면 stale해질 수 있음(2026-07-25 기준 조사) — 갱신 주기는 이번 설계 범위 밖, 후속 갭으로 정직 기록 |
| 정보안정성 | SHA-256을 "기본값 유지"하되 명시적 경고+대안 제시 — 은폐도 강요도 아닌 정보 제공(T98 AIP), 최종 선택은 사용자 |
| 헌법정합 | 00_PROJECT_CONSTITUTION §1 목표(요구사항 기반 태스크 관리)와 직접 연결 — 분야 선택이 정확해야 이후 청크 분류·태스크 배차 정확도가 올라감 |
| 검증 | W1(codes.py dict 승격)은 기존 `if x in DOMAIN_CODES` 전 코드 재확인 필요(회귀 없음을 dict의 key-in 동작으로 보장하되, 실제 pytest로 재확인 예정) |
| 책임 | MD 파일 삭제(W8)는 평식 승인 게이트로 분리 — 이 설계 문서가 삭제를 실행하지 않음 |

**게이트 결론**: **PASS** — 실질 리스크 없음, "정적 콘텐츠 stale화"만 후속 갭으로 기록.

Sources:
- [Bryntum — The best JavaScript data grids in 2026](https://bryntum.com/blog/the-best-javascript-data-grids-in-2026/)
- [rv-grid.com — Best JavaScript Data Grid in 2026](https://rv-grid.com/blog/best-js-datagrid-in-2026)
- [Contabo — Ollama vs LocalAI 2026](https://contabo.com/blog/ollama-vs-localai-best-self-hosted-openai-compatible-llm-server/)
- [glukhov.org — Ollama vs vLLM vs LM Studio 2026](https://www.glukhov.org/llm-hosting/comparisons/hosting-llms-ollama-localai-jan-lmstudio-vllm-comparison/)
- [Helical Insight — 10 Best Open Source Jaspersoft Alternatives 2026](https://www.helicalinsight.com/10-best-open-source-jaspersoft-alternatives-in-2026/)
- [Wikipedia — JasperReports](https://en.wikipedia.org/wiki/JasperReports)
- [guptadeepak.com — Password Hashing Decision Framework 2026](https://guptadeepak.com/bcrypt-vs-argon2-vs-scrypt-vs-pbkdf2-password-hashing-decision-framework-2026/)
