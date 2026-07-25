"""[Phase 6.1] 실패 패턴 분석 리포트 HTTP 어댑터 — 읽기전용.

`requirements_api.get_requirement_store()`/`tasks_api.get_task_store()`를 그대로 재사용한다
(CRZ — 스토어 경로 결정 로직 중복 없음). 쓰기 없는 순수 조회이므로 `_write_lock` 불필요.
"""

from fastapi import APIRouter, Query

from backend.adapters.api import requirements_api, tasks_api
from backend.adapters.api.requirements_api import envelope
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID
from backend.application.services.failure_pattern_analysis_service import (
    analyze_requirement_review_patterns,
    analyze_task_escalation_patterns,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/failure-patterns")
def failure_patterns(project_id: str = Query(DEFAULT_PROJECT_ID)):
    """[Phase 6.1] UNDER_REVIEW 요구사항 + needs_escalation Task를 집계해 반복되는 실패
    패턴을 표면화한다 — 자동 수정 없음, 사람이 보고 분류규칙/태스크 완성도를 개선하는 용도.

    `requirements_api`/`tasks_api` 모듈을 통째로 import해 `.get_requirement_store()`/
    `.get_task_store()`를 호출한다(모듈 속성 참조 유지) — `from X import get_xxx_store`로
    함수 객체만 가져오면 테스트가 `monkeypatch.setattr(tasks_api, "get_task_store", ...)`로
    원본 모듈을 패치해도 이 파일이 이미 캡처한 참조는 바뀌지 않는 흔한 함정을 피한다."""
    requirement_store = requirements_api.get_requirement_store(project_id)
    task_store = tasks_api.get_task_store(project_id)

    return envelope(
        ok=True,
        data={
            "requirement_review_patterns": analyze_requirement_review_patterns(requirement_store.list_all()),
            "task_escalation_patterns": analyze_task_escalation_patterns(task_store.list_all()),
        },
    )
