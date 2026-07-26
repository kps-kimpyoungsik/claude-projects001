---
role: DESIGN
scope: backend/adapters·domain·application 내부 정리 + frontend/data 잡음 정리 (헥사고날 최상위 3분할 자체는 대상 아님)
status: 설계만 — 코드 변경 없음. 실행은 별도 승인 턴에서.
updated: 2026-07-26
---

# 01_ARCHITECTURE_REFACTOR_PLAN — 아키텍처 내부 정리 리팩토링 계획

> 이 문서는 `00_PROJECT_CONSTITUTION.md` §4 드리프트 체크리스트 기준으로 판정한다: 아래 각
> Phase는 "요구사항 관리 시스템 자체의 코드 품질·유지보수성"에 기여하는 인프라 정리이며,
> §1의 핵심 목표(요구사항 문서→구조화→태스크 관리) 자체를 확장하지 않는다 — 순수
> 하우스키핑이다. 실행하지 않아도 §1 목표 달성에 지장이 없다는 것이 이 문서의 솔직한
> 전제다. **본 문서는 실측 검증(SCAN)만 수행했으며 어떤 파일도 이동·수정하지 않았다.**

## §0. 실측 검증 로그 (T59 CFD S1 SCAN — 감사 요약을 그대로 믿지 않고 재확인)

작업 지시가 요구한 "감사의 수치 주장 최소 3건 spot-check"를 아래처럼 수행했다. 감사 시점과
이 문서 작성 시점 사이(2026-07-24~26) 프로젝트가 계속 개발되고 있어(00_PROJECT_CONSTITUTION.md
§6 로그 참조 — pytest 279개까지 증가) 완전히 동일한 숫자가 나오지는 않았지만, **감사가 말한
질적 판정(범위·구조)은 전부 실측으로 재확인됐다.**

| 감사 주장 | 검증 명령 | 실측 결과 | 판정 |
|---|---|---|---|
| `postgres/` 5 .py + README + schema.sql, 미배선 | `ls backend/adapters/db/postgres/` | `connection.py`·`postgres_project_store.py`·`postgres_requirement_store.py`·`postgres_task_lock_store.py`·`postgres_task_store.py` (5개) + `README.md` + `schema.sql` | ✅ 정확 일치 |
| README가 "unverified" 명시 | `Read README.md` | "⚠ 검증 미확정(unverified)... 평식 지시 2026-07-24" 1행 명시, 파일 상단 경고 반복 언급 | ✅ 정확 일치 |
| `router.py`→`format_dispatch.py` 완료 | `test -f backend/adapters/parsers/router.py` + `ls` | `router.py` 없음, `format_dispatch.py` 존재. git log에 `2c271b4 refactor: ... rename router.py` 커밋 확인 | ✅ 완료 확인 |
| `backend.` import 46파일/148건, domain 28/application 20/adapters 21 | `grep -rl "from backend\." backend/` (tests/ 제외) | **47파일/159건**, domain **28**(정확 일치)·application **20**(정확 일치)·adapters **22**(1 차이) | 🟡 근사 일치 — 감사 이후 신규 파일 1개 추가된 것으로 보이며 domain/application은 정확히 일치. 방법론(backend/ 한정, tests/ 제외) 확인됨 |
| frontend 8개 view, 48 tag 참조 | `grep -o '<script...src=\|<link...href='` | view 파일 **8개**(정확), 태그 참조 **53건**(5건 차이, `dispatch-dashboard.html`/`tasks.html`/`architecture-glossary.html` 신설로 추정) | 🟡 근사 일치 — 파일 수 정확, 참조 수는 계속된 개발로 소폭 증가 |
| Stage 1 완료(`file_lock.py` 이관, `api.js`/`constants.js` 추출) | `ls backend/adapters/persistence/file_lock.py` + git log | 파일 존재, git log에 `2c271b4`(lock 이관+router rename)·`c9f5a21`(frontend api.js/constants.js 추출) 커밋 확인 | ✅ 완료 확인 — 재계획 대상 아님 |

**결론**: 감사 수치는 스냅샷 시점 기준 정확했고, 지금은 프로젝트가 활발히 개발 중이라 자연
드리프트가 있을 뿐 구조적 결론(무엇이 죽은 코드인지, 무엇이 이미 끝났는지)은 전부 유효하다.
git 작업 트리는 clean(커밋 대기 변경 없음), 현재 브랜치 `main`.

## §1. 대상 파일·폴더 현황 (실측)

```
backend/adapters/db/postgres/          ← 미배선 죽은 코드 (5 .py + README + schema.sql)
backend/adapters/parsers/              ← format_dispatch.py(구 router.py) + 9개 어댑터
backend/adapters/extractors/           ← ast/commonization/environment/process/semantic/technology (6개, 평면 나열)
backend/adapters/persistence/          ← file_lock.py 등 12개 (이미 Stage 1에서 정리됨)
backend/adapters/api/                  ← 10개 FastAPI 라우터
backend/adapters/llm/                  ← (Ollama 어댑터 등)
backend/adapters/aegis_bridge/         ← (미확인 범위 — 이 계획 밖)
backend/adapters/office_convert/       ← (미확인 범위 — 이 계획 밖)
frontend/data/documents/payment-req-doc.md   ← 샘플/시드 데이터 1개 파일, 서빙 대상 아님
frontend/views/*.html (8개)            ← script/link 태그 53건
```

## §2. 결정 + 근거 — postgres 죽은 코드 처리

**결정: OPTION B — 그대로 둔다(No-op). 이동·격리·삭제 어느 것도 하지 않는다.**

### 검토한 대안 (S3 — 대안 ≥3 비교)

| 대안 | 내용 | 확장성 | 안정성 | 유지보수 | 비용(작업량) | 판정 |
|---|---|---|---|---|---|---|
| A. `_unwired/`·`experimental/` 하위로 물리 이동 | `backend/adapters/db/postgres/` → `backend/adapters/db/_unwired/postgres/` | 무영향(어차피 미배선) | **위험 — import 경로가 실제로 존재하면 깨짐(아래 참조)**, README 상대경로 자기참조도 갱신 필요 | 이름이 "죽은 코드"임을 더 명시적으로 드러냄 | 낮음(5파일+2문서 이동, grep 1회) | 비추천 — 이득 대비 이름 하나 바꾸는 것 이상의 실질 효과 없음 |
| B. **그대로 둔다** — README 경고만 유지 | 변경 없음 | 무관 | **위험 0** | README가 이미 "검증 미확정"·"드롭인 교체 목적"·"JSON/Postgres drift 관리 체크리스트"까지 상세히 갖추고 있어 추가 정리 불필요 | **0** | ✅ **채택** |
| C. 삭제(향후 별도 승인) 플래그만 남김 | 코드는 두되 "N일 내 미사용 시 삭제 검토" 마커 추가 | 무관 | 무관 | 향후 재검토 트리거는 있으나 지금 가치 없음(사용 계획이 실제로 있음 — 아래 근거) | 낮음 | 비추천 — 아래 근거로 삭제 후보가 아님 |

### 근거 — 왜 B(그대로 둠)인가

1. **README가 이미 "왜 존재하는가"를 정확히 설명한다**: `UPGRADE_PLAN_2026-07-23.md` 고도화
   과정에서 나온, `RequirementStorePort`/`TaskStorePort`/`ProjectStorePort`의 **두 번째
   드롭인 어댑터**(JSON 대체용)이지 우발적 잔재가 아니다. `infrastructure/requirements.txt`에
   `psycopg2-binary`/`sqlalchemy`/`pgvector`가 "공식 선언"돼 있었다는 배경도 있다.
2. **평식이 이미 "코드만 작성, 검증은 미확정으로 명시"라고 지시한 이력이 있다**
   (README 1행, 2026-07-24) — 이는 "당장 쓰지 않지만 남겨두라"는 명시적 결정이지, 정리
   대상으로 재분류할 근거가 아니다. 이 계획이 임의로 그 결정을 뒤집는 것은 범위 밖이다.
3. **물리 이동은 실이득이 거의 없고 위험만 소폭 추가한다**: `_unwired/`로 옮겨도 "죽은
   코드"라는 사실 자체는 바뀌지 않고, README가 이미 그 사실을 1번째 줄에서 경고한다.
   반면 이동하면 (a) 상대 경로 문서 갱신, (b) 만에 하나 미래에 어떤 파일이 이 경로를 참조하게
   될 경우의 회귀 위험을 새로 만든다 — 이득 없는 처칠(잔재 제로 원칙의 반대 방향: "정리를
   위한 정리"는 S6 CRZ가 요구하는 가치가 아니다).
4. **T39 CRZ 원칙**: 잔재는 "깨진 참조·오래된 경로·중복 정본"을 뜻하지, "현재 미사용이지만
   설계 의도가 문서화된 대기 코드"를 뜻하지 않는다. postgres 어댑터는 후자다.

**명시적으로 하지 않는 것**: 삭제는 검토조차 이 문서 범위에서 제안하지 않는다 — 실제
PostgreSQL 배선 여부는 순수하게 향후 인프라 결정(§5 GRID/DB 요구사항이 실제로 그런 배선을
요구하게 될 때)의 문제이고, 지금 유일하게 필요한 조치는 **"이대로 둔다"는 이번 결정을
README에 한 줄 추가하는 것뿐**이며 그것조차 이 계획서 자체가 그 기록 역할을 한다(README를
추가로 건드릴 필요도 없음 — 이미 충분히 명시적).

## §3. Phase별 계획 (위험도 오름차순 — 안전한 것부터)

### Phase A (LOW risk) — `frontend/data/documents/payment-req-doc.md` 재배치

**현황**: 이 파일은 `frontend/{views,styles,data}` 3분류 중 `data/`에 있지만, 실제로 정적
서빙되는 `frontend/data/*.json`(예: 과거 `requirements.json` 스냅샷) 부류가 아니라 **샘플
요구사항 원본 문서**(사업계획서류 시드 데이터)로 보인다 — README/구조상 `documents/` 하위에
JSON 스토어가 실제로 관리하는 업로드 문서(`DocumentStore`가 `{doc_id}.md`로 저장하는 것)와
혼동될 위험이 있다.

- **결정**: 이동 **보류(하지 않음)** — 아래 이유로 이번 계획 범위에서는 Phase 자체를
  "검토했으나 미실행"으로 명시한다.
- **이유**: 이 파일이 (a) 테스트 픽스처로 참조되는지, (b) 데모/온보딩 자료로 문서에서
  링크되는지, (c) 완전한 고아 파일인지를 **현재 grep 1회로 확실히 답할 수 없다** —
  `payment-req-doc`이라는 이름 자체가 임의 문자열이라 참조 검색의 신뢰도가 낮다. 이동을
  제안하려면 먼저 실제 참조 여부를 대조해야 하고, 그 대조 자체가 이 계획 문서(설계만) 범위를
  넘어 코드/테스트 스캔 실행에 해당한다.
- **다음 조치(이 계획이 하는 일)**: 실행 승인 시 최초 스텝으로 아래 검증 커맨드를 먼저
  돌리고, 결과가 "참조 없음"이면 `frontend/data/samples/payment-req-doc.md`(제안 경로)로
  이동한다.

| 항목 | 값 |
|---|---|
| 源경로 | `frontend/data/documents/payment-req-doc.md` |
| 대상경로(제안) | `frontend/data/samples/payment-req-doc.md` |
| 영향 파일 수 | **사전 검증 필요** — 아래 grep으로 0건 확인 후에만 진행 |
| 사전검증 grep | `grep -rn "payment-req-doc" --include="*.py" --include="*.html" --include="*.js" .` |
| 잔재 확인 grep(이동 후) | 동일 grep — 0건이어야 함 |
| 롤백 | `git mv` 사용 시 `git revert <commit>` 1회로 완전 복구(단일 파일, 비가역 요소 없음) |

### Phase B (LOW risk) — postgres README에 "이번 계획의 결정" 각주 1줄 추가 (선택)

- **내용**: §2 결정(B: 그대로 둠)을 README에 명시적으로 남겨 다음 세션이 같은 질문을
  반복하지 않도록 한다 — `## 사용 전 필요한 것` 섹션 아래 "2026-07-26 아키텍처 정리
  검토 — 그대로 유지 결정, 근거: 01_ARCHITECTURE_REFACTOR_PLAN.md §2" 1줄.
- **영향 파일 수**: 1 (README.md만, import 없음 — 문서 수정에는 그 어떤 grep 검증도 불필요).
- **롤백**: `git revert` 1회.
- **위험도**: 사실상 0 — 코드 미변경, 문서 각주 추가뿐.

### Phase C (MEDIUM risk) — `backend/adapters/extractors/` 재분류 (권고 — 낮은 우선순위로 보류)

**현황 재확인**: `ast_extractor.py`·`commonization_extractor.py`·`environment_extractor.py`·
`process_extractor.py`·`semantic_extractor.py`·`technology_extractor.py` 6개 파일이 평면
나열돼 있다. 감사가 "혼재하지만 낮은 우선순위"라 판단한 것에 동의한다.

- **결정: 이번 계획에서는 실행하지 않는다 — §4에 "하지 말아야 할 것"으로 명시.**
- **이유**: 6개 파일 모두 `ProjectDomainSnapshot`이라는 **단일 소비자**
  (`backend/application/services/project_domain_snapshot_service.py`)를 위한 "5/5 청크"
  구현물이며(00_PROJECT_CONSTITUTION.md §6 2026-07-19 로그), 이름 자체가 이미 각 청크의
  역할을 명확히 표현한다(`environment_extractor` = 환경 청크). 하위 폴더로
  나누려면(`extractors/snapshot/{ast,commonization,environment,process,semantic,
  technology}.py` 등) 6개 파일의 import 경로 6곳 + 그 파일들을 import하는
  `project_domain_snapshot_service.py` 1곳 = 최소 7곳을 고쳐야 하는데, **평면 6개 파일은
  아직 탐색성 문제를 실제로 일으키고 있지 않다**(파일 수가 적고 이름이 자기설명적) — 이는
  "재발명 방지"가 아니라 "정리를 위한 정리"에 가깝다.

| 항목 | 값(참고용 — 미실행) |
|---|---|
| 源경로 | `backend/adapters/extractors/{ast,commonization,environment,process,semantic,technology}_extractor.py` |
| 대상경로(가정) | `backend/adapters/extractors/snapshot/{ast,commonization,environment,process,semantic,technology}.py` |
| 영향 파일 수(가정) | 6개 파일 자체 + import하는 소비자 1개(`project_domain_snapshot_service.py`) = 7 |
| 검증 grep(실행 시) | `grep -rn "adapters.extractors.\(ast\|commonization\|environment\|process\|semantic\|technology\)_extractor" --include="*.py" backend/ tests/` |
| 롤백 | `git mv` + import 경로 sed 치환은 단일 커밋으로 묶어 `git revert` 1회 복구 가능 |

### Phase D (HIGH risk, 권고: 하지 않음) — `backend/domain`/`application`/`adapters` 자체 rename/재구조화

**결정: 하지 않는다. 이 Phase는 "실행 계획"이 아니라 "왜 안 하는지"를 기록하기 위한
Phase다.**

- **이유 1 — 감사 판정 그대로 유지**: 이전 감사가 이미 이 헥사고날 최상위 3분할을
  "coherent, no major disorder"로 판정했고, 이 계획 작성 중 재확인한 실측(§0)에서도
  구조 자체에 이상 징후를 발견하지 못했다. 바꿀 결함이 없다.
- **이유 2 — 블라스트 반경 대비 무가치**: `from backend.` import가 **47개 파일·159건**
  (domain 28, application 20, adapters 22)에 걸쳐 있다. `domain`/`application`/`adapters`
  이름 자체를 바꾸면(예: `domain`→`core`, `adapters`→`infra`) 이 159건 전부가 잠재적
  충돌 대상이 되고, 문자열 치환 방식(`sed`)은 부분 일치(`adapters`가 변수명·주석에도
  등장할 가능성)로 인한 오치환 위험이 있어 실제로는 각 129건(도메인 20/애플리케이션 22
  제외한 adapters 관련만 따져도) 이상을 사람이 검수해야 하는 규모가 된다.
- **이유 3 — 아무 실질적 이득이 없다**: `domain`/`application`/`adapters`는 헥사고날
  아키텍처의 **표준 용어**이며, 이 이름을 바꿔서 얻는 "더 도메인에 맞는 이름"이 실재하지
  않는다(예: `requirements`/`tasks`처럼 이 프로젝트 고유 개념이 있는 것도 아니다 — 이건
  범용 계층 이름이다). 바꾼다면 팀 신규 합류자의 학습 비용만 늘어난다(헥사고날 패턴을 아는
  사람이 낯선 이름과 재매핑해야 함).
- **이 판단 자체가 §4 드리프트 체크리스트 확인이다**: "범용 AEGIS류 인프라를 위한 리네이밍"은
  §1 목표(요구사항→구조화→태스크 관리)에 전혀 기여하지 않는다 — 순수 스타일 선호 변경이며
  148~159건급 blast radius를 정당화하지 못한다.

**만약 향후 이 rename이 다시 제안된다면 다음 조건을 모두 만족해야 진행 가치가 있다**
(참고용 임계값 — 지금은 미충족):
1. 실제 이름 혼동으로 인한 버그·오배치가 최소 2회 이상 발생한 실측 기록이 있을 것
2. 대체 이름이 이 프로젝트 고유 도메인 개념을 명확히 반영할 것(범용 헥사고날 용어의
   동의어 교체가 아닐 것)
3. 자동화된 AST 기반 리네이밍 도구(`sed` 문자열 치환이 아닌)를 사용할 수 있을 것

## §4. 명시적으로 하지 말아야 할 것 (요약)

| 항목 | 판정 | 근거 |
|---|---|---|
| `backend/domain`/`application`/`adapters` 최상위 rename | ❌ 하지 않음 | §3 Phase D — 159건 blast radius 대비 무가치, 감사 "coherent" 판정 유지 |
| `backend/adapters/extractors/` 하위 폴더 재분류 | ❌ 이번 계획에서 하지 않음(낮은 가치) | §3 Phase C — 6개 파일 자기설명적, 실제 탐색성 문제 미확인 |
| postgres 죽은 코드 삭제 | ❌ 삭제 검토 자체를 하지 않음 | §2 — README가 명시한 "드롭인 교체용 대기 코드"이지 삭제 후보 아님 |
| postgres 죽은 코드 물리 이동(`_unwired/` 등) | ❌ 하지 않음 | §2 대안 A 기각 — 이름표만 바뀔 뿐 실질 위험 감소 없음 |

## §5. 실행 순서 요약 (승인 시)

```
1. Phase A 사전검증 grep 실행 → 0건이면 payment-req-doc.md 이동, 아니면 보류 유지
2. Phase B — README 각주 1줄 추가 (선택, 사용자 원하면)
3. Phase C, D — 실행하지 않음(이 문서가 최종 기록)
```

각 Phase는 독립적이며 순서를 바꿔도 서로 영향 없음(파일 스코프가 겹치지 않음 — §PCM 매트릭스:
Phase A(frontend/data) × Phase B(backend/adapters/db/postgres/README.md) = CLEAR).

## §6. 열린 질문 (사용자 확인 필요 시)

- Phase A의 `payment-req-doc.md` 실제 참조 여부는 이 문서 작성 중 실행하지 않았다(계획
  문서만 쓰라는 지시 범위 준수) — 승인 시 첫 실행 스텝에서 검증한다.
- Phase C(extractors 재분류)를 "낮은 우선순위로 언젠가"라고 남겨둘지, 아예 backlog에서
  제외할지는 사용자 판단이 필요하다 — 이 문서는 "지금은 안 한다"까지만 결정했다.
