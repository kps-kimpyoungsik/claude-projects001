"""[Phase 3 §2-1 "공통화"] solution_stack 재사용 빈도 집계.

설계 근거: `plans/_plan/03_PHASE3_AGENT_GRAPHIFY.md` §2-1 "공통화" 행 — "1차 설계의
`solution_stack` 태그(프레임워크 사용 현황) — 어떤 프레임워크가 몇 개 요구사항/태스크에
걸쳐 재사용되는지 그래프로 집계".

**순수 집계 함수 — 파일 스캔이 아니다.** `structure`/`environment`/`process` 청크와 달리
이 청크는 디스크를 읽지 않는다. `RequirementRecord.solution_stack`(backend/adapters/
persistence/requirement_store.py)과 `Task.solution_stack`(backend/domain/entities/task.py)은
이미 메모리에 로드된 데이터이므로, 그 값을 호출자가 그대로 주입한다 — 직전 청크들의
"DB/스토어 접근은 호출자가 주입" 패턴(예: `agent_dispatch_resolver.py`의 `search_fn` 방식)과
동일하게 이 함수도 `requirements`/`tasks` 리스트를 파라미터로 받는다(신규 스토어 접근
로직 발명 없음, CRZ).

`requirements`/`tasks`는 `RequirementRecord`/`Task` 데이터클래스 인스턴스를 우선 기대하지만,
호출자가 plain dict(예: JSON에서 막 로드한 레코드)를 넘겨도 죽지 않도록 duck-typing으로
`solution_stack`/`req_id`/`task_id`를 both attribute와 dict key 양쪽에서 조회한다(방어적
읽기 — 이 함수가 두 스토어의 내부 구현에 강하게 결합되지 않도록).
"""

from typing import Any


def _get_field(item: Any, name: str, default=None):
    """dataclass 인스턴스든 dict든 동일하게 필드를 읽는다."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def extract_solution_stack_usage(
    requirements: list | None,
    tasks: list | None,
) -> dict:
    """`RequirementRecord.solution_stack` + `Task.solution_stack`을 합쳐 재사용 빈도를 집계한다.

    반환 예시:
        {
            "status": "OK",
            "stack_usage": {
                "전자정부표준프레임워크": {
                    "count": 5,
                    "used_by": ["REQ-BIZ-SEC-002", "TASK-SEC-001", ...],
                },
                ...
            },
            "requirement_count": 3,
            "task_count": 2,
        }

    `requirements`/`tasks`가 둘 다 None(또는 빈 리스트)이면 크래시하지 않고 빈 집계를
    "데이터 미제공"으로 정직하게 반환한다(T98 AIP — 과장 금지, `NOT_IMPLEMENTED`가 아니라
    함수 자체는 구현됐으므로 별도 상태값 `NO_DATA`로 구분).
    """
    requirements = requirements or []
    tasks = tasks or []

    if not requirements and not tasks:
        return {
            "status": "NO_DATA",
            "note": "requirements/tasks 미제공 — 호출자가 주입해야 집계 가능",
            "stack_usage": {},
            "requirement_count": 0,
            "task_count": 0,
        }

    usage: dict[str, dict] = {}

    for req in requirements:
        req_id = _get_field(req, "req_id", "UNKNOWN_REQ")
        for stack_name in _get_field(req, "solution_stack", []) or []:
            entry = usage.setdefault(stack_name, {"count": 0, "used_by": []})
            entry["count"] += 1
            entry["used_by"].append(req_id)

    for task in tasks:
        task_id = _get_field(task, "task_id", "UNKNOWN_TASK")
        for stack_name in _get_field(task, "solution_stack", []) or []:
            entry = usage.setdefault(stack_name, {"count": 0, "used_by": []})
            entry["count"] += 1
            entry["used_by"].append(task_id)

    return {
        "status": "OK",
        "stack_usage": usage,
        "requirement_count": len(requirements),
        "task_count": len(tasks),
    }
