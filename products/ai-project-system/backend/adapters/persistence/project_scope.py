"""[2026-07-22 고도화] 프로젝트별 데이터 디렉터리 경로 결정 — 유일한 SSOT.

`requirements_api.get_requirement_store()`/`get_document_store()`·`tasks_api.
get_task_store()`가 전부 이 함수 하나로 경로를 결정한다(CRZ — 경로 규칙을 여러 곳에
중복 구현하지 않음). `project_registry.py`의 "무마이그레이션" 원칙과 정확히 대응한다:
`DEFAULT_PROJECT_ID`("default")는 기존 평면 경로(`data/`) 그대로 쓰고, 그 외 프로젝트만
`data/projects/{project_id}/` 아래로 격리한다.
"""

import re
from pathlib import Path

from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID

DATA_ROOT = Path("data")

# [2026-07-24 보안수정] project_id가 API Query 파라미터로 그대로 유입되어 검증 없이
# 경로 조합에 쓰이면 `../../etc/passwd` 등 경로 순회(CWE-22)로 data/ 밖 임의 경로에
# read/write가 가능해진다(5-agent 진단 실측 확인). 이 함수가 유일한 SSOT이므로
# 여기 한 곳만 검증하면 모든 호출부(requirements/tasks/documents/doc_types API)가 방어된다.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class InvalidProjectIdError(ValueError):
    """project_id가 안전 문자셋(영숫자·-·_)을 벗어남 — 경로 순회 방지."""


def resolve_project_data_dir(project_id: str) -> Path:
    if not _SAFE_ID.fullmatch(project_id):
        raise InvalidProjectIdError(f"허용되지 않는 project_id 형식: {project_id!r}")
    if project_id == DEFAULT_PROJECT_ID:
        return DATA_ROOT
    return DATA_ROOT / "projects" / project_id
