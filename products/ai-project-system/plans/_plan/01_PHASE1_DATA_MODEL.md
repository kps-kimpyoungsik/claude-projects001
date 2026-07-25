---
role: DESIGN_PHASE1
scope: 요구사항 데이터 모델 확장 (2축 → 6축 → 7축)
status: 게이트 1 PASS(6축, 뼈대 구현 완료 2026-07-18) — **게이트 1-B(7번째 축, 디자인 시안
  선행 게이트) 설계 추가(2026-07-19), design_draft_gate 코드 구현 완료(2026-07-19)**. §5는
  2026-07-19 사용자 지적("매번 게이트가 걸리는 것처럼 읽힌다") 반영해 §5-1(프로젝트 레벨
  확정 플래그)·§5-2(재정의 게이트 로직)로 보강, 이 게이트 판정 로직도 함께 구현 완료
  (`backend/domain/requirements/design_gate.py`).
updated: 2026-07-19
---

# 1차 설계 — 요구사항 데이터 모델 확장

> 상위: [`00_INDEX.md`](./00_INDEX.md) | 다음: [`02_PHASE2_ORCHESTRATION_PREVIEW.md`](./02_PHASE2_ORCHESTRATION_PREVIEW.md)

## §1. 목표

지금까지(2026-07-18 이전 세션)는 요구사항 1건이 **문서유형코드(doc_type_code)·영역코드
(area_code)** 2축으로만 분류됐다(`REQ-{문서유형}-{영역}-{번호}`). 이번 요청은 여기에 4개
축을 더해 **6축 데이터 모델**로 확장한다. REQ 번호 형식(`REQ-{문서유형}-{영역}-{번호}`)
자체는 **바꾸지 않는다** — 나머지 4축은 메타데이터 필드로 얹는다(불필요한 재발명·기존 자산
파괴 방지, T57 PVS over-engineering 회피).

## §2. 6축 데이터 모델 (+ 2026-07-19: 7번째 축 추가 — §2-5 이하)

| # | 축 | 필드명 | 상태 | 정의 위치 |
|---|---|---|---|---|
| 1 | 문서유형 | `doc_type_code` | 기존(§5-A) | `graphify_engine/codes.py` |
| 2 | 기술영역 | `area_code` | 기존(§5, 확정) | `graphify_engine/codes.py` |
| 3 | **아키텍처 계층** | `layer_code` | **신규** | `graphify_engine/codes.py` (§5-B) |
| 4 | **요구사항 유형** | `requirement_type` | **신규** | `graphify_engine/codes.py` (§5-C) |
| 5 | **라이프사이클 상태** | `lifecycle_status` | **신규**(기존 status 대체) | `graphify_engine/requirement_store.py` |
| 6 | **솔루션·프레임워크** | `solution_stack[]` | **신규**(자유태그+추천목록) | `graphify_engine/framework_catalog.py`(신규 파일 예정) |
| 7 | **디자인 시안 선행 게이트** | `design_draft_gate` | **신규(2026-07-19, 설계만)** | `backend/domain/requirements/codes.py`(§5-D 예정) |

### §2-1. 축 3 — 아키텍처 계층코드 (§5-B, 신규, 확정)

**최초 초안에서는 `SECL`이었으나, area_code의 `SEC`와 문자열 수준에서도 겹치지 않도록
`SECU`로 확정했다**(개념 축이 달라도 로그·grep·디버깅 시 사람이 두 축을 혼동해 잘못
비교하는 사고를 원천 차단하기 위함 — 낮은 리스크의 되돌리기 쉬운 네이밍 결정이라 별도
재질의 없이 이 설계 라운드에서 확정):

| 코드(확정) | 계층 |
|---|---|
| `SYS` | 시스템영역 (인프라·서버·OS·배치) |
| `SECU` | 보안영역(아키텍처 계층 관점 — area_code의 `SEC`와는 다른 축. `SEC`=요구사항이 다루는 기술영역, `SECU`=그 요구사항이 시스템 아키텍처의 어느 계층에 위치하는지) |
| `UXENV` | 사용자환경영역 (클라이언트 UX·접근성·디바이스 환경) |
| `TPI` | 서드파티 인터페이스 영역 (외부 API·PG·인증 연동) |
| `INTG` | 연계영역 (내부 시스템 간 연계·배치 연동·ESB) |

**§PCM-정합 검토(품질검토 게이트 1 반영)**: `layer_code`와 `area_code`는 독립 축이라 하나의
요구사항이 `area_code=SEC`(암호화 기술영역) + `layer_code=SYS`(시스템 계층에 적용)처럼
동시에 성립할 수 있다 — 이것이 "왜 계층코드를 REQ 번호에 넣지 않고 메타데이터로만 두었는가"의
근거다(번호에 넣으면 6축 전부가 번호 폭발을 일으킴).

**UI 표시 규칙(확정)**: `agent-view/requirements.html`(2차 설계 §2)의 배지는 반드시 축
이름을 라벨로 병기한다 — 예: `영역: SEC` / `계층: SECU`처럼 코드값 앞에 축 이름을 붙여
렌더링(색상도 `badge-area`와 `badge-layer`로 서로 다르게, 2차 설계 §2-2에 반영). 코드
문자열 분리 + UI 라벨 분리, 이중 안전장치.

### §2-2. 축 4 — 요구사항 유형 (§5-C, 신규)

| 코드 | 유형 |
|---|---|
| `FUNC` | 기능 요구사항 (기능적으로 무엇을 해야 하는가) |
| `NFUNC` | 비기능 요구사항 (성능·보안·가용성 등 품질 속성) |

가장 표준적인 소프트웨어 요구공학 분류(IEEE 830 계열)를 그대로 채용 — 신규 발명 없음.

### §2-3. 축 5 — 라이프사이클 상태 (기존 `status` 필드 확장·재정의)

사용자 요청의 "요구사항접수, 수용"을 상태 전이로 모델링한다. 기존
`RequirementStore`(2026-07-18 이전 구현)의 `status`(PENDING_REVIEW/CLASSIFIED/CONFIRMED/
REJECTED)를 **폐기하지 않고 아래로 매핑**한다(하위호환, CRZ):

```
RECEIVED(접수)          ← 청크가 처음 분류기를 통과한 직후, 사람 확인 전
  → CLASSIFIED(자동분류) ← 기존 status="CLASSIFIED"와 동일(분류기 확신 높음)
  → UNDER_REVIEW(검토중) ← 기존 status="PENDING_REVIEW"와 동일(분류기 확신 낮음, 사람 확인 대기)
  → ACCEPTED(수용)       ← 기존 status="CONFIRMED"와 동일(사람이 확정)
  → IN_PROGRESS(구현중)  ← Phase 4 태스크가 이 REQ를 source_req_ids로 물고 IN_PROGRESS일 때
  → IMPLEMENTED(구현완료)
  → VERIFIED(검증완료)
  (또는 어느 단계에서든) → REJECTED(반려) ← 기존 status="REJECTED"와 동일
  (또는 어느 단계에서든) → WITHDRAWN(철회) ← 신규(§3-A)
```

### §2-3-A. 상태변경 이력 + 철회 사유 (미결 #2·#3 해소 — 통합 감사로그 설계 확정)

이전 라운드에서 "철회 사유 필드"(1차 미결)와 "상태변경 행위자 기록"(2차 미결)을 **별개
필드로 각각 추가**하려 했으나, 재검토 결과 둘 다 "상태가 바뀔 때마다 누가·언제·왜"라는
동일한 질문이라 **하나의 이력 배열로 통합**하는 것이 CRZ(중복 설계 회피)에 부합한다:

```python
@dataclass
class StatusChangeEvent:
    from_status: str
    to_status: str
    actor: str            # 사람 식별자(이메일/사번 등) 또는 "system"(자동분류기)
    reason: str | None = None   # WITHDRAWN/REJECTED 전이 시 필수(아래 검증 규칙)
    ts: str = ""

# RequirementRecord(requirement_store.py)에 추가할 필드
status_history: list[StatusChangeEvent] = field(default_factory=list)
```

`RequirementStore.set_status()`(이미 구현된 함수)의 시그니처를 확장한다 —
`set_status(req_id, status, actor, reason=None)`. **검증 규칙**: `status in
{WITHDRAWN, REJECTED}`인데 `reason`이 없으면 `ValueError`(추정 사유로 채우지 않음 — 왜
철회/반려했는지 기록 없는 전이는 거부). 이 배열이 "누가 철회했는지"(1차 미결)와 "누가
수용/반려했는지"(2차 미결)를 **동시에** 해소한다.

**미결 #1·#2·#3 — 전부 해소 완료**(더 이상 이월 없음, 2차 설계의 상태변경 액션 UI는
이 확정된 `set_status(actor=, reason=)` 시그니처를 그대로 호출).

**요구사항 CRUD(상시 추가·변경·삭제) 설계 — workbase 패턴 재사용**:
`_design/DYNAMIC-STEP-ITEMS.md`의 "물리 삭제 대신 hidden 처리로 이력 보존" 원칙을 그대로
가져온다. 즉:
- **추가**: 언제든 신규 REQ 채번 가능(기존과 동일)
- **변경**: `revision` 증가 + 변경 이력(diff) 별도 로그 — `task_manager.py`의 `revision` 패턴
  재사용(CRZ)
- **삭제**: 물리 삭제 금지, `lifecycle_status`에 `WITHDRAWN`(철회) 상태 추가 — soft-delete.
  이미 이 REQ를 `source_req_ids`로 참조하는 Task가 있으면 삭제(철회) 시 그 Task들이
  `needs_escalation=True`로 자동 전환되어야 함(`task_manager.check_sufficiency`가 이미
  가진 그래프 실재 검증 로직을 재사용 — REQ가 WITHDRAWN이면 "그래프에 없는 요구사항 참조"와
  동일하게 취급하도록 확장)

### §2-4. 축 6 — 솔루션·프레임워크 태그 (신규, 자유태그+추천목록)

Stage 0에서 확정된 대로 **고정 enum이 아니라 자유 태그 + 추천목록(오토컴플리트)** 구조.

```python
# graphify_engine/framework_catalog.py (2차 이후 구현 예정 스텁 설계)
RECOMMENDED_SOLUTION_TAGS = [
    "전자정부표준프레임워크", "마이플랫폼", "JEX Framework", "JEX Operia AI Framework",
    "자체 프레임워크",
]  # 추천 초기값 — 조직에서 실제 쓰는 것이 확인되는 대로 계속 추가(고정 아님)
```

`solution_stack: list[str]`을 요구사항 필수 필드로 두되(사용자 지시 — "필수 사항으로"),
**값 자체는 자유 문자열**이라 새 프레임워크가 나와도 코드 수정 없이 태그만 추가하면 된다.
"필수"의 의미: `task_manager.check_sufficiency()`에 5번째 조건으로
`solution_stack이 최소 1개 이상`을 추가 — 없으면 `needs_escalation=True`(기존 4조건에 이어
확장, 함수 시그니처 변경 없이 Task 데이터클래스에 필드만 추가하면 됨).

### §2-5. 축 7 — 디자인 시안 선행 게이트 (신규, 2026-07-19, 설계만 — §5-D 예정)

**배경(사용자 원 요청 요약)**: 뼈대(스캐폴딩)를 만들더라도 UI/UX 디자인 시안이 먼저
확정돼 있으면 그 스타일·테마까지 뼈대 영역으로 함께 잡을 수 있다. 백엔드 인터페이스
(API 요청/응답 스키마)는 UI/UX 패턴에 따라 달라질 수 있으므로, "이 요구사항은 디자인
시안 확정이 먼저여야 하는가"를 요구사항 축에서 판정해 **개발 순서(뼈대→점진 확장)에
영향을 주는 게이트**로 삼는다 — 단순 참고용 메타데이터가 아니다.

**필드명**: `design_draft_gate` (기존 필드명 컨벤션 확인 결과 — `lifecycle_status`·
`requirement_type`처럼 축 이름 그대로 snake_case, "게이트" 성격을 이름에 명시해 단순
분류축이 아니라 순서를 강제하는 게이트임을 코드 레벨에서도 드러낸다).

**값 3종** (대문자 스네이크케이스 — `LIFECYCLE_STATUSES`/`REQUIREMENT_TYPES`와 동일
컨벤션, `layer_code`처럼 짧은 약어로 축약하지 않는다 — 3값뿐이라 축약 이득이 없고,
게이트 판정문이라 풀어 쓰는 편이 사람이 읽고 override할 때 오독을 줄인다):

| 값 | 의미 | 판정 기준 |
|---|---|---|
| `MANDATORY` | 이 요구사항은 **UI/UX 디자인 시안 확정 없이는 개발 착수 자체가 불가**하다 | 요구사항 본문이 화면·레이아웃·사용자 상호작용을 직접 다루고(예: "이 화면은 ~하게 보여야 한다"), 그 결과가 API 응답 구조·필드 형태를 직접 좌우하는 경우(§2-6 자동판정 근거) |
| `NOT_MANDATORY` | 이 요구사항은 **UI/UX와 무관하게 디자인 시안 확정 전에도 독립적으로 진행 가능**하다 | 배치·스케줄러·내부 로직·데이터 처리·인프라 설정 등 화면 자체가 없거나, 있어도 이미 확정된 공통 UI 패턴(04_PHASE0 §6-A)만 그대로 쓰면 되는 경우 |
| `STRATEGIC_MANDATORY` | 이 **요구사항 자체는 디자인 시안 없이도 개발을 시작할 수 있지만**, 프로젝트 전체 뼈대 단계 관점에서는 디자인 시안이 먼저 확정되는 편이 유리한 **전략적 판단 대상**이다 | 백엔드 로직 위주이나 응답 스키마가 나중에 화면 요구사항과 맞물릴 가능성이 있는 경우(예: 목록 API인데 아직 그 목록을 보여줄 화면의 정렬·페이지네이션·카드/테이블 여부가 확정 안 됨) — MANDATORY만큼 확실하지 않지만 NOT_MANDATORY로 방치하면 나중에 API 재설계 리스크가 있는 "중간 판정" |

**REQ ID 형식에는 포함하지 않는다** — `layer_code`(§2-1)와 동일한 선례. `area_code`·
`doc_type_code` 2축만 채번에 쓰고, 나머지는 메타데이터 필드로 얹는 기존 원칙(§2-1 참조)을
그대로 따른다. 이 필드도 번호에 넣으면 축이 7개로 늘어난 지금 번호 폭발 문제가 §2-1이
경고한 그대로 재현된다 — 재발명 없이 기존 판단을 상속.

### §2-6. 축 7 자동 판정 전략 (classifier.py 기존 패턴 재사용 — 새 판정 엔진 발명 금지)

`classifier.py`는 이미 `DOC_TYPE_KEYWORDS`/`AREA_KEYWORDS`/`LAYER_KEYWORDS`/
`REQUIREMENT_TYPE_KEYWORDS` 4개 사전을 같은 `_score_keywords()`/`_pick_best()` 함수로
채점한다(결정론적 키워드 매칭, LLM 의미판단 아님 — 파일 상단 주석 그대로). 축 7도 **같은
패턴**으로 5번째 키워드 사전을 추가하는 설계다(의사코드 — 실제 파일 수정은 이번 사이클
범위 밖):

```python
# backend/domain/requirements/classifier.py 에 추가할 설계(의사코드, 미구현)
# §5-D 디자인 시안 선행 게이트 키워드 — plans/_plan/01_PHASE1_DATA_MODEL.md §2-6 정의 그대로.
DESIGN_GATE_KEYWORDS: dict[str, list[str]] = {
    "MANDATORY": [
        "화면", "UI", "UX", "레이아웃", "디자인", "테마", "사용자 인터페이스",
        "화면 구성", "와이어프레임", "시안", "배치(화면)", "색상", "폰트", "반응형 화면",
    ],
    "NOT_MANDATORY": [
        "배치 작업", "스케줄러", "내부 로직", "데이터 처리", "API 전용", "백그라운드",
        "연산 처리", "동기화 작업", "무중단 배포", "인프라 설정", "화면 없음",
    ],
    # STRATEGIC_MANDATORY는 위 두 사전 모두에서 애매하게 걸리는 경우(혼재) 또는
    # 아래 "혼재 신호" 키워드가 함께 나타날 때 별도로 채점한다(3지선다라 이진 대립이
    # 아니라 "혼재 신호"를 명시 사전으로 따로 둔다 — LAYER_KEYWORDS류의 확장판).
    "STRATEGIC_MANDATORY": [
        "API 응답", "응답 구조", "데이터 스키마", "목록 조회", "화면에 표시할",
        "추후 화면", "프론트 연동 예정", "인터페이스 정의",
    ],
}

def classify_design_gate(text: str) -> tuple[str | None, float, bool]:
    """§2-6 판정 규칙:
    1) MANDATORY 키워드만 매칭 + NOT_MANDATORY 매칭 없음 → MANDATORY 후보
    2) NOT_MANDATORY 키워드만 매칭 + MANDATORY 매칭 없음 → NOT_MANDATORY 후보
    3) MANDATORY와 NOT_MANDATORY가 동시에 매칭(백엔드+프론트 혼재) → STRATEGIC_MANDATORY
    4) STRATEGIC_MANDATORY 전용 키워드가 매칭 → STRATEGIC_MANDATORY (설령 1)·2) 조건을
       만족해도 이 신호가 있으면 전략적 판정으로 상향 — "화면 없어 보이지만 나중에
       화면과 맞물릴 신호"를 놓치지 않기 위함(사용자 원 요청의 핵심 동기)
    5) 아무 것도 안 걸리면 None + needs_review=True (기존 4축과 동일한 안전 원칙 —
       "찍었다고 자신하지 않는다", classifier.py 파일 상단 주석 그대로 계승)
    """
    ...  # 실제 구현은 _score_keywords()/_pick_best() 재사용, 이번 사이클 범위 밖
```

`ClassificationResult`(기존 dataclass)에도 `design_draft_gate: str | None = None` +
`design_draft_gate_confidence: float = 0.0` 필드를 추가하는 설계다(§2-1 계층코드가 이미
같은 방식으로 기존 dataclass에 필드만 늘려 확장한 선례 그대로 — 새 dataclass 발명 없음).

### §2-7. 수동 재정의 경로 (기존 `status_history` 패턴 재사용 — 신규 이력관리 발명 금지)

사용자가 자동판정을 언제든 override할 수 있어야 한다는 요구는, 이미 §2-3-A에서 확정한
`StatusChangeEvent`(actor+reason+ts append-only 이력) 패턴과 **개념적으로 동일**하다 —
"필드가 바뀔 때 누가·언제·왜 바꿨는지 남긴다"는 질문이 `lifecycle_status`든
`design_draft_gate`든 같기 때문에, 새 이력 클래스를 또 만들지 않고 **같은 이벤트 구조를
재사용**하는 설계로 확정한다(CRZ):

```python
# RequirementRecord(requirement_store.py)에 추가할 설계(의사코드, 미구현)
design_draft_gate: str | None = None            # MANDATORY / NOT_MANDATORY / STRATEGIC_MANDATORY
design_draft_gate_confidence: float = 0.0        # 자동판정 신뢰도(§2-6), 수동 override 시 1.0 고정
design_draft_gate_history: list[dict] = field(default_factory=list)  # StatusChangeEvent 재사용

# RequirementStore에 추가할 설계 — set_status()와 동일 시그니처 패턴
def set_design_draft_gate(self, req_id: str, value: str, actor: str, reason: str | None = None) -> RequirementRecord:
    """actor="system"(자동 classifier) 또는 사람 식별자. 자동 판정 결과를 사람이 override
    하면 reason 기록을 권장(단, §2-3-A의 WITHDRAWN/REJECTED처럼 강제(ValueError)까지는
    하지 않는다 — 이 필드는 라이프사이클 전이만큼 비가역적이지 않아 강제 수준을 다르게
    설계, 과잉규제 회피). `design_draft_gate_history`에 `StatusChangeEvent`(from_status→
    to_status 자리에 이전값→신규값)를 append."""
```

**(2026-07-19 추가)** 프로젝트 레벨 확정 플래그(`project_design_draft_confirmed`, §5-1)가
도입되면서, 이 필드와는 별개로 "이 요구사항만은 project 확정 여부와 무관하게 게이트를
작동시키고 싶다"는 요구사항 단위 수기 오버라이드가 필요해졌다 — `design_draft_gate_
override: bool`(§5-2)로 설계했고, 변경 이력은 이 `design_draft_gate_history` 배열을
그대로 공유한다(신규 이력 클래스 추가 없음).

**최초/중간 추가 요구사항 모두 동일 적용**: 이 판정 로직은 04_PHASE0(프로젝트 등록
마법사, Phase 0 최초 일괄classify)과 1차 설계 자체가 다루는 "청크→classifier 실시간
분류 파이프라인"(00_PROJECT_CONSTITUTION.md §3 Phase 2 대응) **양쪽 경로 모두**에서
`classify_chunk()`가 호출되는 지점에 동일하게 걸린다 — 최초 등록 시점과 이후 개별
요구사항이 신규 채번될 때를 분기 처리하지 않는다(단일 진입점, 새 파이프라인 발명 금지).

## §3. 기존 구현 재설계 매핑표 (CRZ — 무엇을 버리고 무엇을 남기는가)

| 기존(2026-07-18 이전) | 재설계 후 |
|---|---|
| `graphify_engine/codes.py` — `DOMAIN_CODES`, `DOC_TYPE_CODES` | 그대로 유지 + `LAYER_CODES`(§5-B), `REQUIREMENT_TYPES`(§5-C) 추가 |
| `graphify_engine/classifier.py` — doc_type/area 2축 키워드 분류 | 그대로 유지 + `layer_code`·`requirement_type` 키워드 분류 함수 추가(같은 패턴 확장, 새 분류엔진 아님) |
| `graphify_engine/requirement_store.py` — `status`(4값) | `lifecycle_status`(9값 — §2-3 8개 + `WITHDRAWN`) + `status_history`(§2-3-A) 로 확장. 마이그레이션 함수: 기존 4값 → 신규 값 매핑(PENDING_REVIEW→UNDER_REVIEW, CLASSIFIED→CLASSIFIED, CONFIRMED→ACCEPTED, REJECTED→REJECTED), 데이터 손실 0 |
| `agent-view/requirements.html` — 배지 2종(문서유형/영역) | 배지 4종(문서유형/영역/**계층**/**유형**, §2-1 UI 표시 규칙대로 축 이름 라벨 병기) + 라이프사이클 상태 파이프라인 시각화 + PII 경고 배지(2차 설계 §2·04_PHASE0 §3) |
| `orchestrator/task_manager.py` — `check_sufficiency` 4조건 | 5조건(solution_stack 추가) |
| **(신규, 2026-07-19 설계)** `backend/domain/requirements/classifier.py` — 4개 키워드 사전 | `DESIGN_GATE_KEYWORDS` 사전 + `classify_design_gate()` 추가(§2-6, 같은 `_score_keywords`/`_pick_best` 재사용) |
| **(신규, 2026-07-19 설계)** `RequirementRecord`(requirement_store.py) | `design_draft_gate`·`design_draft_gate_confidence`·`design_draft_gate_history` 필드 추가(§2-7) |

## §4. 품질검토 게이트 1 — MPCR 7관점 비판검토

| 관점 | 검토 결과 |
|---|---|
| 개발 | 6축 모두 독립 필드로 추가 가능 — 기존 dataclass에 필드 추가만 하면 되므로 구현 난이도 낮음(D2 수준) |
| 설계 | 최초 지적됐던 `layer_code`/`area_code` 코드값 혼동 리스크는 §2-1에서 `SECU`로 확정해 해소(2026-07-18 보강) |
| 운영 | soft-delete(WITHDRAWN) 덕분에 요구사항 삭제가 하위 Task 무결성을 깨지 않고 안전하게 처리됨 |
| 정보안정성 | **해소(2026-07-18 보강)**: `solution_stack` 자유태그는 `agent-view/requirements.html`이 이미 채택한 렌더링 규칙(`description.replace(/</g, "&lt;")`, 이전 세션에서 실제로 구현된 이스케이프 패턴)을 태그 렌더링에도 동일 적용 — 별도 sanitize 로직 발명 없이 기존 패턴 재사용(CRZ). 입력 단계(0차 마법사 §2 STEP4 태그입력)에서는 제어문자·개행을 거부해 저장 단계로 악성 문자열이 넘어가지 않게 한다 |
| 헌법정합 | §5(영역코드)를 변경하지 않고 순수 확장만 했으므로 00_PROJECT_CONSTITUTION.md §6 확정사항과 충돌 없음 |
| 검증 | 라이프사이클 상태 전이가 9개로 늘어 상태머신 테스트 케이스가 늘어남 — 구현 단계에서 상태전이표 기반 테스트 설계 필요(설계 단계에서 미리 다 채울 수 없는 성격이라 정직하게 구현 단계 과제로 남김) |
| 책임 | **해소(2026-07-18 보강)**: §2-3-A `status_history`가 "누가·언제·왜"를 함께 남겨 REQ가 WITHDRAWN 되어도 추적 가능 |

**게이트 1 결론(2026-07-18 보강 라운드 갱신)**: **PASS** — 최초 지적된 `layer_code` 코드값
혼동 리스크·철회사유 미비·솔루션태그 sanitize 미비 전부 §2-1·§2-3-A·본 §4 "정보안정성"
행에서 해소됨. 문서 접근제어(PII)는 2차 설계로 이월했고 그것도 `plans/_plan/04_PHASE0_
PROJECT_REGISTRATION.md` §3에서 이번 라운드에 함께 해소됨. 유일하게 설계 단계에서 채울 수
없는 "검증" 행(상태전이 테스트 설계)만 구현 단계 과제로 정직하게 남긴다.

## §5. 뼈대 단계 게이트 전략 (2026-07-19 최초 설계 → 2026-07-19 사용자 지적 반영 보강)

00_PROJECT_CONSTITUTION.md §3(Phase 0 환경설정 = "임의 가정 금지, 뼈대→점진 확장")과
04_PHASE0_PROJECT_REGISTRATION.md §6-A(전체 화면 공통 UI/UX 결정)가 이미 다루는 것은
**"이 관리 시스템 자체의 화면들이 어떤 스타일인가"**(일회성·프로젝트 전체에 한 벌)이지,
**"관리 대상 프로젝트의 개별 요구사항이 디자인 시안을 먼저 요구하는가"**(요구사항 단위·
매번 다름)가 아니다 — 두 개념은 서로 다른 레벨이라 §6-A를 대체하지 않고 **보강**한다
(CRZ, 중복 아님을 확인).

**최초 버전이 놓친 것(사용자 지적, 2026-07-19)**: 아래 최초 규칙은 "MANDATORY 요구사항이
하나라도 있으면 매번 게이트가 걸린다"로 읽혀, **프로젝트가 이미 전체 UI/UX 시안을
사전 확정해둔 경우에도 신규 MANDATORY 요구사항마다 다시 게이트를 거는 것처럼** 보이는
결함이 있었다. 실제 의도는 "시안이 아직 확정 안 됐을 때만 선행을 강제하고, 이미
확정됐으면 그 시안을 재사용하면 되므로 게이트를 스킵한다"였다 — 이를 아래 §5-1(프로젝트
레벨 확정 플래그)·§5-2(재정의 게이트 로직)로 명시한다.

### §5-1. 프로젝트 레벨 확정 플래그 (신규 필드 — 04_PHASE0_PROJECT_REGISTRATION.md §7 연결)

`ProjectConfig`(`backend/adapters/persistence/project_config_store.py`)에 아래 필드를
추가하는 설계다(기존 `created_by`/`created_at` 컨벤션과 동일하게 "누가·언제 확정했는지"를
같이 남긴다 — §2-3-A `StatusChangeEvent`처럼 별도 이력 배열을 새로 만들지 않고, 이 필드는
1회성 전역 플래그라 `created_by`/`created_at` 패턴을 그대로 재사용하는 것으로 충분하다고
판단, CRZ):

```python
# ProjectConfig(project_config_store.py)에 추가할 설계(의사코드, 미구현)
project_design_draft_confirmed: bool = False        # "프로젝트 전체 UI/UX 시안이 이미 확정됨"
project_design_draft_confirmed_by: str = ""         # 확정한 사람 식별자(created_by와 동일 패턴)
project_design_draft_confirmed_at: str = ""         # 확정 시각(created_at과 동일 패턴)
```

이 플래그가 세워지는 단계는 04_PHASE0_PROJECT_REGISTRATION.md §7(보강)에서 정의한다 —
0차 마법사 STEP 6("완료 확인") 또는 §6-A(전체 UI/UX 공통 결정) 확정 시점에 사람이 명시
체크하는 액션으로, **자동 추정으로 세워지지 않는다**(0-N No-Skip 원칙 — 시안이 실제로
확정됐는지는 사람만 안다).

### §5-2. 게이트 판정 규칙 (재정의 — 프로젝트 확정 플래그 반영)

```
요구사항 하나마다:
  IF design_draft_gate in {MANDATORY, STRATEGIC_MANDATORY}:
      # 이 요구사항의 design_draft_gate 값 자체는 그대로 기록(감사 목적 — "원래 시안이
      # 필요한 성격이었다"는 판정 사실은 project 확정 여부와 무관하게 지워지지 않는다)

      IF requirement.design_draft_gate_override == True:
          → project_design_draft_confirmed 값과 무관하게 게이트 작동(§5-2-A 원래 규칙
            그대로 MANDATORY=선행 강제 / STRATEGIC_MANDATORY=경고 배너) — 사용자가 이
            요구사항만은 기존 확정 시안과 다른 별도 화면/패턴이 필요하다고 수기 지정한 경우
      ELIF project_config.project_design_draft_confirmed == True:
          → 게이트 자동 통과(이미 확정된 프로젝트 공통 시안을 재사용) — 선행 단계 없이
            바로 Phase 1 스캐폴딩 착수 가능, 배너 없음
      ELSE:
          → §5-2-A 원래 규칙 그대로 작동(선행 강제 또는 경고 배너)
  ELSE (NOT_MANDATORY):
      → 게이트 없음, 기존 뼈대→점진 확장 순서 그대로 진행.
```

**§5-2-A 원래 규칙(변경 없음 — project 미확정 또는 override 시 그대로 적용)**:

```
프로젝트 내 요구사항 전체를 스캔:
  IF 하나 이상의 요구사항이 design_draft_gate == MANDATORY (그리고 위 §5-2 조건에 따라
     게이트가 실제로 작동해야 하는 경우):
      → 그 요구사항이 속한 영역(area_code)의 백엔드 스캐폴딩(Phase 1 인프라 뼈대 중
        해당 영역 API 설계)보다 "UI/UX 디자인 시안 확정"을 선행 단계로 강제한다.
        (04_PHASE0 §2 STEP 6 "완료 확인" 이후, Phase 1 착수 전 체크포인트)
  ELIF 하나 이상의 요구사항이 design_draft_gate == STRATEGIC_MANDATORY (동일 조건):
      → 즉시 강제하지는 않되, 04_PHASE0 §6 완료 확인 화면에 "전략적으로 디자인 시안을
        먼저 진행하는 것을 권장합니다"라는 경고 배지를 노출한다(강제 아님 — 사람이
        판단할 여지를 남긴다, MANDATORY와 차등 처리).
  ELSE (전부 NOT_MANDATORY, 또는 위 조건에 따라 전부 자동 통과):
      → 순서 강제 없음, 기존 뼈대→점진 확장 순서 그대로 진행.
```

**수기 오버라이드 필드 (§2-7 패턴 재사용 — 신규 이력관리 발명 금지)**: `RequirementRecord`
에 `design_draft_gate_override: bool = False` 필드를 추가하는 설계다. 이 값을 사람이
`True`로 바꾸는 행위는 이미 §2-7에서 확정한 `set_design_draft_gate()`와 동일한 성격의
"필드 변경 시 누가·언제·왜"이므로, 새 함수를 만들지 않고 `design_draft_gate_history`
(§2-7에서 이미 설계된 append-only 배열)에 `{field: "design_draft_gate_override", from,
to, actor, reason, ts}` 형태로 함께 기록한다(CRZ — 필드별로 별도 이력 배열을 만들지 않고
같은 이력 구조를 공유).

**체크포인트 위치**: 04_PHASE0_PROJECT_REGISTRATION.md §2 STEP 6("완료 확인")이 이미
`ProjectDomainSnapshot` 최초 생성을 트리거하는 지점(§5)이므로, 이 게이트 스캔(§5-2)도
**같은 시점**에 끼워 넣는 설계다(새 체크포인트 발명 없음 — 기존 완료 트리거에 조건 분기만
추가). §5-2 판정 결과 게이트가 실제로 작동하는 경우에만 완료 확인 화면에 배너를 노출하고,
그 이후 Phase 1 스캐폴딩 착수 화면에서도 동일 조건을 재확인한다(단발성 경고가 아니라 두
지점에서 반복 확인 — 사람이 배너를 놓쳐도 다음 단계 진입 시 다시 표면화). 단,
`project_design_draft_confirmed == True`이고 개별 오버라이드도 없는 경우에는 애초에
배너 자체가 뜨지 않는다(§5-2 자동 통과 경로).

**최초/중간 신규 요구사항 모두 적용**: §2-7에서 이미 확정한 대로 `classify_design_gate()`가
호출되는 모든 경로(0차 최초 일괄분류 + 1차 실시간 분류 파이프라인)에서 이 스캔 대상
집합(`design_draft_gate`별 요구사항 개수)이 갱신되므로, 프로젝트 중간에 새 MANDATORY
요구사항이 추가되면 그 시점에 §5-2 규칙이 다시 평가된다(정적 1회 판정이 아니라 요구사항
집합 변화에 따라 갱신되는 살아있는 게이트) — **단, `project_design_draft_confirmed ==
True`인 프로젝트에서는 이 재평가 결과가 대부분 "자동 통과"로 귀결되는 것이 정상 동작이다**
(사용자 지적의 핵심 — 매번 다시 게이트가 걸리는 것이 아니라, 확정된 시안이 있으면 그
이후 요구사항들은 재사용이 기본값).

## §6. 품질검토 게이트 1-B — 신규 축(디자인 시안 선행 게이트) MPCR 7관점

| 관점 | 검토 결과 |
|---|---|
| 개발 | 기존 `ClassificationResult`/`RequirementRecord` dataclass에 필드 3~4개만 추가하는 구조라 §2-1(계층코드) 선례와 동일한 난이도(D2) — 신규 판정엔진·신규 이력클래스 없음 |
| 설계 | `design_draft_gate`(요구사항 단위·매번 변할 수 있음)와 04_PHASE0 §6-A(화면 전체 공통 UI/UX 결정·일회성)는 레벨이 다른 개념임을 §5에서 명시 구분 — 두 절이 같은 "디자인" 단어를 쓰지만 서로 대체 관계가 아님을 착오 없이 기록 |
| 운영 | STRATEGIC_MANDATORY는 강제가 아니라 경고 배지로만 노출 — MANDATORY만 순서를 강제해 과잉 차단(모든 애매한 요구사항이 프로젝트를 멈추는 상황)을 방지 |
| 정보안정성 | 이 축은 개인정보·보안과 무관한 순수 프로세스 메타데이터라 §2-4(솔루션태그) 수준의 별도 sanitize 요건 없음 — 다만 자유 텍스트가 아니라 3값 enum이라 애초에 인젝션 표면 자체가 없음(추가 조치 불요, 정직하게 "해당 없음"으로 기록) |
| 헌법정합 | 00_PROJECT_CONSTITUTION.md §4 드리프트 체크리스트 4문항 자가점검 — ①"요구사항→구조화" 경로에 직접 기여(개발 순서를 결정하는 메타데이터 자체가 구조화 산출물) ②REQ 번호 자체에는 넣지 않지만 §2-1과 동일한 "메타데이터 필드" 형태로 추적 가능 ③이 필드가 만드는 것은 "다음에 AI가 수행할 태스크의 순서 조건"이라는 관리정보 ④AEGIS류 범용 인프라를 전혀 가져오지 않음(순수 이 시스템 내부 필드) — 4문항 전부 YES |
| 검증 | 설계 단계에서 채울 수 없는 부분: `classify_design_gate()`의 실제 키워드 사전이 현업 요구사항 문서 표본으로 검증되지 않음(§2-6은 의사코드 수준) — 구현 착수 시 실제 요구사항 샘플로 재조정 필요를 정직하게 남긴다(과장 금지, T98 AIP) |
| 책임 | §2-7의 `set_design_draft_gate(actor=, reason=)`이 자동판정(actor="system")과 수동 override(actor=사람 식별자)를 동일한 이력 배열에 남겨 "누가 이 요구사항의 순서를 바꿨는지" 항상 추적 가능 |

**게이트 1-B 결론**: **PASS(설계 완료, 구현 미착수)** — 7관점 모두 리스크 없이 통과.
유일한 한계(§2-6 키워드 사전의 실사용 미검증)는 설계 단계 특성상 불가피하며, 구현
단계 과제로 정직하게 이월한다(§4 게이트 1의 "검증" 행과 동일한 패턴 — 이번 게이트도
같은 방식으로 정직하게 기록).

**design_draft_gate 코드 구현 완료(2026-07-19)**: `classifier.py`/`requirement_store.py`/
`project_config_store.py`/신규 `design_gate.py`로 §2-6·§2-7·§5-2를 그대로 구현, pytest
신규 14건 포함 전체 101개 전부 pass(회귀 0). §2-6 키워드 사전 실사용 미검증 한계는 여전히
남아있다(구현 완료가 "실사용 검증 완료"를 의미하지 않음, 과장 금지 — T98 AIP).
