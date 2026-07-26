"""공유 JSON 파일 스토어 동시성 원시값 (§DRL-1).

[2026-07-26 순수 이동] `backend/adapters/api/requirements_api.py`에 있던 `_write_lock`/
`_graph_path`를 이 모듈로 재배치한다 — 동작 변경 없음(CRZ). 이 두 값은 "요구사항" 도메인
전용이 아니라 여러 API 어댑터(`requirements_api`·`doc_types_api`·`project_config_api`·
`projects_api`·`documents_api`·`tasks_api`)가 공유하는 범용 JSON 파일 스토어 동시성 관심사라,
소유권이 `requirements_api.py`라는 특정 도메인 파일에 있는 것이 부적절했다(실측 감사에서
확인된 구조 문제) — 그래서 `backend/adapters/persistence/`(공유 저장소 어댑터 계층)로
옮긴다.

동시성(§DRL-1): 이 프로세스 안에서 여러 요청이 동시에 들어와도 각 JSON 스토어의
read-modify-write(전체 로드 → 수정 → 전체 저장)가 서로 겹치지 않도록 쓰기 경로(상태
변경·PII 열람 로그 append 등)를 모듈 레벨 `threading.Lock()` 하나로 직렬화한다. 이 락은
"같은 프로세스 안의 스레드 경합"만 막는다 — 여러 프로세스(uvicorn --workers > 1)로 띄우면
이 락으로 막을 수 없으므로, 반드시 단일 프로세스(--workers 지정 없이 기본값)로만 기동한다.

**이 파일이 정본**: 아래 `write_lock`은 모든 API 어댑터가 import해 재사용하는 단 하나의
공유 `threading.Lock()` 인스턴스다 — 각 모듈이 별도로 `threading.Lock()`을 새로 만들면
같은 파일에 대한 쓰기 경합을 막지 못하는 회귀 버그가 재발한다(과거 `tasks_api.py`와
`requirements_api.py`가 각자 별도 락으로 같은 `tasks_store.json`을 썼던 실측 버그가 그
사례 — 이미 수정 완료, 이 재배치는 그 수정을 유지한 채 소유 위치만 옮기는 것).
"""

import threading

from backend.adapters.persistence import project_scope
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID

# §DRL-1 — 상태변경·PII 열람 로그 append 등 JSON 파일 스토어 쓰기 경로를 직렬화하는
# 프로세스 내 단일 락. 모든 API 어댑터가 이 객체 하나를 공유해야 한다(신규 Lock() 금지).
write_lock = threading.Lock()


def graph_path(project_id: str = DEFAULT_PROJECT_ID):
    """요구사항→그래프 동기화 대상 경로. `requirements_api.py`(REQ 동기화)와
    `tasks_api.py`(Task-Requirement 그래프 링크 검증) 양쪽이 동일 project_id의
    `graph.json`을 참조하기 위해 공유한다(CRZ, 신규 경로규칙 없음 — 기존
    `project_scope.resolve_project_data_dir()`를 그대로 재사용)."""
    return project_scope.resolve_project_data_dir(project_id) / ".graphify-out" / "graph.json"
