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
변경·PII 열람 로그 append 등)를 모듈 레벨 락 하나로 직렬화한다. 이 락은
"같은 프로세스 안의 스레드 경합"만 막는다 — 여러 프로세스(uvicorn --workers > 1)로 띄우면
이 락으로 막을 수 없으므로, 반드시 단일 프로세스(--workers 지정 없이 기본값)로만 기동한다.

**이 파일이 정본**: 아래 `write_lock`은 모든 API 어댑터가 import해 재사용하는 단 하나의
공유 락 인스턴스다 — 각 모듈이 별도로 `threading.Lock()`을 새로 만들면 같은 파일에 대한
쓰기 경합을 막지 못하는 회귀 버그가 재발한다(과거 `tasks_api.py`와 `requirements_api.py`가
각자 별도 락으로 같은 `tasks_store.json`을 썼던 실측 버그가 그 사례 — 이미 수정 완료, 이
재배치는 그 수정을 유지한 채 소유 위치만 옮기는 것).

[2026-07-28 `Lock()` → `RLock()` 전환, ai-project-system 2번 작업] 실측 확인: 이 시점까지
API 레이어(`requirements_api.py`·`documents_api.py`)의 호출부는 전부 `with write_lock:`으로
스토어 메서드 호출을 감싸고 있었지만, `RequirementStore`/`DocumentStore` 자체(스토어
내부)에는 락이 전혀 없었다(모듈 docstring·`job_registry.py` docstring에 이미 명시된 기존
갭). 그 결과 API 레이어가 이 락으로 직접 감싸지 않은 새 호출 경로(예:
`document_upload_service.process_uploaded_file()` → `extract_requirements_from_chunks()` →
`RequirementStore.add_from_classification()`, 백그라운드 잡 워커 스레드에서 실행)는 무방비
상태였다 — 워커 수를 1보다 늘리면 두 문서가 동시에 같은 `requirements_store.json`을
read-modify-write해 서로 덮어쓸 수 있었다.

근본 수정은 락을 "매 호출부가 기억해서 감싸야 하는 관례"가 아니라 스토어 메서드 자체에
내장하는 것이다(모든 현재·미래 호출부를 자동으로 보호). 하지만 기존 API 레이어 호출부는
이미 `with write_lock:` 블록 **안에서** 스토어 메서드를 호출한다(예: `requirements_api.py`
`change_status()`가 `with _write_lock: store.set_status(...)`) — 스토어 메서드 내부에도
동일 락을 걸면 같은 스레드가 이미 보유한 락을 다시 획득하려는 **중첩 획득**이 된다.
`threading.Lock()`은 재진입 불가라 이 경우 그 자리에서 영구 교착(deadlock)된다. 그래서
`threading.RLock()`(재진입 가능 락, 같은 스레드의 중첩 획득을 카운트로 허용)으로 바꾼다 —
API 레이어의 기존 `with write_lock:` 감싸기는 그대로 안전하게 유지되면서(외부에서 한 번,
내부 스토어 메서드에서 한 번 더 획득 — 카운트만 증가), 스토어 메서드 자체가 이제 그 안전을
직접 보장한다(신규 락 프리미티브 발명 없음 — 같은 객체를 RLock으로 바꿨을 뿐, CRZ).
"""

import threading

from backend.adapters.persistence import project_scope
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID

# §DRL-1 — 상태변경·PII 열람 로그 append 등 JSON 파일 스토어 쓰기 경로를 직렬화하는
# 프로세스 내 단일 락. 모든 API 어댑터 + 스토어 자체가 이 객체 하나를 공유해야 한다(신규
# Lock()/RLock() 새로 만들기 금지). RLock인 이유: 위 모듈 docstring 2026-07-28 항목 참고
# (API 레이어의 기존 `with write_lock:` 안에서 스토어 메서드가 다시 이 락을 거는 중첩 획득을
# 허용해야 하므로 재진입 가능 락이 필수).
write_lock = threading.RLock()


def graph_path(project_id: str = DEFAULT_PROJECT_ID):
    """요구사항→그래프 동기화 대상 경로. `requirements_api.py`(REQ 동기화)와
    `tasks_api.py`(Task-Requirement 그래프 링크 검증) 양쪽이 동일 project_id의
    `graph.json`을 참조하기 위해 공유한다(CRZ, 신규 경로규칙 없음 — 기존
    `project_scope.resolve_project_data_dir()`를 그대로 재사용)."""
    return project_scope.resolve_project_data_dir(project_id) / ".graphify-out" / "graph.json"
