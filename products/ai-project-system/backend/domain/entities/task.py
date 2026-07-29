"""[Phase 4] AI 개발 태스크 엔티티 — 순수 도메인 로직 (00_PROJECT_CONSTITUTION.md §3).

헥사고날 리팩토링(2026-07-19, plans/_plan/05_REFACTOR_BACKEND_FRONTEND_STRUCTURE.md)으로
`orchestrator/task_manager.py`에서 분리한 뒤, 다시 이번 세분화(§2-2)에서 Task 데이터클래스만
남기고 충분성 체크·충돌탐지(check_sufficiency/detect_area_conflicts)는
`backend/domain/requirements/conflict_detection.py`로 옮겼다 — Task 엔티티 자체와
그 위에서 동작하는 검증 로직을 분리해 각 파일의 책임을 하나로 좁힌다(CRZ, 재복제 없음).
"""

from dataclasses import dataclass, field

from backend.domain.graph.entities import Node, NodeKind
from backend.domain.requirements.codes import DOMAIN_CODES


class InvalidDomainCodeError(ValueError):
    pass


@dataclass
class Task:
    task_id: str
    domain_code: str
    title: str
    description: str
    source_req_ids: list[str] = field(default_factory=list)  # 요구사항 추적성 (REQ-{코드}-{번호})
    acceptance_criteria: list[str] = field(default_factory=list)
    impact_scope: list[str] = field(default_factory=list)  # 이 태스크가 건드릴 파일/폴더
    solution_stack: list[str] = field(default_factory=list)  # 필수(plans/_plan/01_PHASE1_DATA_MODEL.md §2-4) — 어느 프레임워크 기반인지
    status: str = "DRAFT"  # DRAFT -> READY -> IN_PROGRESS -> DONE / BLOCKED
    revision: int = 1
    needs_escalation: bool = False
    escalation_reasons: list[str] = field(default_factory=list)
    updated_at: str = ""
    # [Phase 4.2] status 전이 감사로그 — backend.domain.requirements.task_state_machine이
    # 검증하고 TaskStore.set_status()가 이 리스트에 append한다(RequirementRecord.status_history와
    # 동일 패턴, CRZ).
    status_history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.domain_code not in DOMAIN_CODES:
            raise InvalidDomainCodeError(
                f"미등록 도메인 코드: {self.domain_code} (허용: {sorted(DOMAIN_CODES)})"
            )


def make_task_node(task: Task) -> Node:
    """[2026-07-29 배선, directive D-eebcef47] Task를 그래프의 Task 노드로 만든다.

    `backend.domain.entities.requirement.make_requirement_node()`와 대칭되는 패턴(도메인
    계층, I/O 없는 순수 변환) — Task는 문서 청킹 산출물이 아니라 API 호출로 사람/시스템이
    직접 생성하는 레코드라 source_ref는 문서 출처가 아니라 task_id 자체를 쓴다(스스로가
    근거 — task_id는 TaskStore.generate_task_id()가 채번해 이미 실재가 보장된 값이다).

    `requirement.make_implements_edge(task_id, req_id)`가 가리키는 task_id 쪽 노드가
    그래프에 실재하려면, 이 함수로 만든 노드를 그 엣지와 **같은 merge_into_graph() 호출**에
    함께 넘겨야 한다(고아 엣지 방지, T92 GDI) — `tasks_api.create_task()` 참조.
    """
    return Node(node_id=task.task_id, kind=NodeKind.TASK, label=task.title, source_ref=task.task_id)
