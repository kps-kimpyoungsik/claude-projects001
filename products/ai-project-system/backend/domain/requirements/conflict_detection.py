"""[Phase 4] 태스크 충분성 체크 + impact_scope 충돌탐지 — 순수 로직(I/O 없음).

헥사고날 리팩토링(2026-07-19)으로 `backend/domain/entities/task.py`에서 분리했다 — Task
엔티티 자체는 그대로 두고, "이 태스크 내용이 충분한가"·"태스크끼리 충돌하는가"라는
검증 로직만 이 파일로 좁혔다(§PCM 원칙의 프로젝트 로컬 적용).

목표: 태스크가 만들어지는 시점에 ①내용을 확인할 수 있고(조회) ②내용이 부족하면
`aegis-oneshot-plan`으로 설계를 구체화해야 함을 스스로 표시하고(충분성 체크 →
escalation 플래그) ③영역(도메인 코드)별 impact_scope 충돌을 명확히 판단해서
④태스크 내용을 갱신할 수 있어야 한다.

이 모듈은 "aegis-oneshot-plan을 자동 호출"하지 않는다 — 그것은 세션 레벨 Skill 호출이라
Python 모듈 내부에서 실행할 수 없다. 대신 `needs_escalation=True` + `escalation_hint`를
반환해, 호출한 에이전트/세션이 실제로 `/aegis-oneshot-plan`을 실행하도록 한다
(과장 금지 — "자동 호출한 것처럼" 구현하지 않음, T98 AIP).
"""

from backend.domain.entities.task import Task
from backend.domain.requirements.id_format import verify_task_requirement_links

MIN_DESCRIPTION_LEN = 20  # 이보다 짧으면 "내용 부족" 후보로 간주(임계값 — §6 미확정시 조정 여지)


def check_sufficiency(task: Task, graph: dict | None = None) -> tuple[bool, list[str]]:
    """태스크 내용이 충분한지 확인. 부족하면 (False, 부족사유 목록)을 반환한다.

    "충분"의 기준(최소 실행 가능 명세):
    - 설명이 최소 길이 이상(모호한 1줄 제목만으로는 실행 불가)
    - acceptance_criteria가 최소 1개 이상(무엇을 완료로 볼지 명확)
    - impact_scope가 최소 1개 이상(어디를 건드릴지 명확 — §PCM 충돌판단의 전제)
    - source_req_ids가 최소 1개 이상(요구사항 추적 없는 태스크는 근거 불명)
    - solution_stack이 최소 1개 이상(어느 프레임워크·솔루션 기반인지 필수 — 사용자 지시,
      plans/_plan/01_PHASE1_DATA_MODEL.md §2-4)

    graph가 주어지면 추가로 backend.domain.requirements.id_format.verify_task_requirement_links로
    source_req_ids가 실제 그래프상 Requirement 노드로 존재하는지까지 검증한다(더 강한 검증 —
    "요구사항 ID를 적었다"와 "그 요구사항이 그래프에 실재한다"는 다른 문제).
    """
    reasons = []
    if len(task.description.strip()) < MIN_DESCRIPTION_LEN:
        reasons.append(f"설명이 너무 짧음(<{MIN_DESCRIPTION_LEN}자) — 구체화 필요")
    if not task.acceptance_criteria:
        reasons.append("완료 기준(acceptance_criteria) 없음")
    if not task.impact_scope:
        reasons.append("impact_scope(건드릴 파일/영역) 미지정 — 충돌판단 불가")
    if not task.solution_stack:
        reasons.append("solution_stack(기반 프레임워크·솔루션) 미지정 — 필수 사항")
    if not task.source_req_ids:
        reasons.append("요구사항 추적 근거(source_req_ids) 없음")
    elif graph is not None:
        grounded, missing = verify_task_requirement_links(task.source_req_ids, graph)
        if not grounded:
            reasons.append(f"그래프에 없는 요구사항 참조: {missing}")
    return (len(reasons) == 0, reasons)


def detect_area_conflicts(tasks: list[Task]) -> dict:
    """태스크 간 impact_scope 교집합을 N x N으로 확인한다 (§PCM 원칙의 프로젝트 로컬 적용).

    반환: {"pairs": [{"a": id, "b": id, "overlap": [...]}], "clear_pairs": N, "overlap_pairs": M}
    같은 도메인이든 다른 도메인이든, 파일 경로가 겹치면 충돌로 본다(파일은 도메인을 모른다).
    """
    pairs = []
    clear = 0
    for i in range(len(tasks)):
        for j in range(i + 1, len(tasks)):
            a, b = tasks[i], tasks[j]
            overlap = sorted(set(a.impact_scope) & set(b.impact_scope))
            if overlap:
                pairs.append({"a": a.task_id, "b": b.task_id, "overlap": overlap})
            else:
                clear += 1
    return {"pairs": pairs, "clear_pairs": clear, "overlap_pairs": len(pairs)}


UNSPECIFIED_LAYER = "UNSPECIFIED"  # source_req_ids가 없거나 연결된 요구사항에 layer_code가 없을 때


def _resolve_layer_code(task: Task, layer_by_req_id: dict[str, str]) -> str:
    """task.source_req_ids가 가리키는 요구사항들 중 layer_code가 있는 첫 값을 채택한다.

    layer_code는 Requirement(RequirementRecord.layer_code, plans/_plan/01_PHASE1_DATA_MODEL.md
    §2-1)의 필드이지 Task 자체의 필드가 아니다(실측: backend/domain/entities/task.py에
    layer_code 없음, backend/adapters/persistence/requirement_store.py의 RequirementRecord에
    있음) — Task에 중복 저장하지 않고 source_req_ids로 연결된 요구사항에서 조회한다(CRZ).
    """
    for req_id in task.source_req_ids:
        layer_code = layer_by_req_id.get(req_id)
        if layer_code:
            return layer_code
    return UNSPECIFIED_LAYER


def group_tasks_by_area_layer(
    tasks: list[Task],
    layer_by_req_id: dict[str, str] | None = None,
) -> dict[tuple[str, str], list[Task]]:
    """(domain_code, layer_code) 조합별로 태스크를 묶는다.

    plans/_plan/02_PHASE2_ORCHESTRATION_PREVIEW.md §3-1 "영역×계층 기반 병렬 오케스트레이션"
    구현 — §PCM-6 DAA(난이도 기반 agent 배정)의 "분야별 agent 배정" 근거표를 만든다.

    설계서 원문은 `area_code`라 부르지만 이 코드베이스의 Task 필드명은 `domain_code`다
    (codes.py DOMAIN_CODES를 Task.domain_code와 RequirementRecord.area_code가 같이 쓴다 —
    같은 코드 공간의 다른 이름일 뿐, 별도 개념 아님).

    layer_code는 Task가 아니라 Requirement 쪽 필드라서(위 _resolve_layer_code 참고),
    이 함수는 순수 domain 로직을 유지하기 위해 `layer_by_req_id`(req_id -> layer_code
    딕셔너리)를 호출자가 넘겨받아 전달하는 방식을 쓴다 — RequirementStore(어댑터/영속성
    계층)를 이 domain 모듈이 직접 import하면 헥사고날 경계(domain -> adapters 역방향 의존)를
    깨기 때문이다(2026-07-19 리팩토링 원칙 위반 회피). 미전달 시(None) 또는 조회 실패 시
    모든 태스크가 layer_code="UNSPECIFIED" 그룹으로 묶인다 — 조용히 잘못된 값으로 채우지 않음.

    같은 조합 안에서도 impact_scope 교집합이 있으면 여전히 detect_area_conflicts()로
    순차화 대상 판단이 필요하다(이중 안전망) — 이 함수는 그룹핑만 하고, 그룹별 충돌
    재확인은 detect_conflicts_within_groups()가 detect_area_conflicts()를 그대로 재사용한다.
    """
    layer_by_req_id = layer_by_req_id or {}
    groups: dict[tuple[str, str], list[Task]] = {}
    for task in tasks:
        key = (task.domain_code, _resolve_layer_code(task, layer_by_req_id))
        groups.setdefault(key, []).append(task)
    return groups


def detect_conflicts_within_groups(
    groups: dict[tuple[str, str], list[Task]],
) -> dict[tuple[str, str], dict]:
    """group_tasks_by_area_layer()의 각 그룹에 detect_area_conflicts()를 재적용한다.

    §3-1 "이중 안전망"(그룹 분리 + 파일단위 충돌탐지) 그대로 — detect_area_conflicts() 자체의
    로직(impact_scope 교집합 판단)은 바꾸지 않고, 그룹별로 반복 호출만 한다.
    """
    return {key: detect_area_conflicts(group_tasks) for key, group_tasks in groups.items()}
