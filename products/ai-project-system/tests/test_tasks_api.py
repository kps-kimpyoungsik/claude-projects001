"""Task 상태 조회·전이 API — FastAPI TestClient로 인메모리 검증 (test_requirements_api.py와
동일 monkeypatch 격리 패턴, CRZ)."""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import tasks_api
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import Task
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "tasks.json")
    monkeypatch.setattr(tasks_api, "get_task_store", lambda *a, **k: store)
    # [2026-07-25 회귀수정] tasks_api._load_graph()가 project_scope.resolve_project_data_dir()로
    # 그래프 경로를 얻는다(test_e2e_task_lifecycle.py와 동일 격리 패턴, CRZ) — 격리 없으면 실제
    # data/.graphify-out/graph.json을 오염시킨다.
    monkeypatch.setattr(project_scope, "resolve_project_data_dir", lambda project_id: tmp_path / project_id)
    return TestClient(app), store


def _seed(store) -> Task:
    task = Task(
        task_id="T-1",
        domain_code="WEB",
        title="테스트 태스크",
        description="충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
        source_req_ids=["REQ-TECH-WEB-001"],
        acceptance_criteria=["동작 확인"],
        impact_scope=["frontend/views/x.html"],
        solution_stack=["FastAPI"],
    )
    return store.create_or_update(task)


def test_create_task_success(client):
    http, store = client
    res = http.post(
        "/tasks",
        json={
            "domain_code": "WEB",
            "title": "새 태스크",
            "description": "충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
            "source_req_ids": ["REQ-TECH-WEB-001"],
            "acceptance_criteria": ["동작 확인"],
            "impact_scope": ["frontend/views/x.html"],
            "solution_stack": ["FastAPI"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["task_id"] == "TASK-WEB-001"
    assert body["data"]["status"] == "DRAFT"

    # 두 번째 생성은 동일 domain_code에서 채번이 증가한다
    res2 = http.post("/tasks", json={"domain_code": "WEB", "title": "t2", "description": "x" * 25})
    assert res2.json()["data"]["task_id"] == "TASK-WEB-002"


def test_create_task_invalid_domain_code_returns_422(client):
    http, _store = client
    res = http.post("/tasks", json={"domain_code": "NOPE", "title": "t", "description": "x" * 25})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_create_task_missing_required_field_returns_422(client):
    http, _store = client
    res = http.post("/tasks", json={"domain_code": "WEB", "title": "t"})  # description 누락
    assert res.status_code == 422


def test_create_task_insufficient_content_stays_draft_with_escalation(client):
    """설명만 있고 acceptance_criteria/impact_scope/solution_stack/source_req_ids가 없으면
    check_sufficiency()가 부족하다고 판단해 DRAFT + needs_escalation=True로 남아야 한다."""
    http, _store = client
    res = http.post("/tasks", json={"domain_code": "WEB", "title": "t", "description": "x" * 25})
    body = res.json()
    assert body["data"]["status"] == "DRAFT"
    assert body["data"]["needs_escalation"] is True


def test_list_tasks(client):
    http, store = client
    _seed(store)
    res = http.get("/tasks")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert len(body["data"]["tasks"]) == 1


def test_get_task_not_found(client):
    http, _store = client
    res = http.get("/tasks/NOPE")
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-NOTFOUND"


def test_status_change_success(client):
    http, store = client
    _seed(store)
    res = http.post("/tasks/T-1/status", json={"status": "READY", "actor": "hong.gildong"})
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["status"] == "READY"
    assert len(body["data"]["status_history"]) == 1


def test_status_change_invalid_transition_returns_422(client):
    http, store = client
    _seed(store)
    res = http.post("/tasks/T-1/status", json={"status": "DONE", "actor": "hong.gildong"})
    assert res.status_code == 422
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-VALIDATION"


def test_status_change_done_without_reason_returns_422(client):
    """[Phase 5.3 보완] DONE도 reason 없이는 거부 — 침묵 완료 오검증 방지."""
    http, store = client
    _seed(store)
    http.post("/tasks/T-1/status", json={"status": "READY", "actor": "hong.gildong"})
    http.post("/tasks/T-1/status", json={"status": "IN_PROGRESS", "actor": "hong.gildong"})
    res = http.post("/tasks/T-1/status", json={"status": "DONE", "actor": "hong.gildong"})
    assert res.status_code == 422

    ok = http.post("/tasks/T-1/status", json={"status": "DONE", "actor": "hong.gildong", "reason": "테스트 3건 통과"})
    assert ok.status_code == 200


def test_status_change_blocked_without_reason_returns_422(client):
    http, store = client
    _seed(store)
    http.post("/tasks/T-1/status", json={"status": "READY", "actor": "hong.gildong"})
    res = http.post("/tasks/T-1/status", json={"status": "BLOCKED", "actor": "hong.gildong"})
    assert res.status_code == 422


def test_status_change_malformed_body_returns_422(client):
    """T99 AIOS 경계검증 — actor 누락(malformed)은 Pydantic이 422로 fail-fast 처리한다."""
    http, store = client
    _seed(store)
    res = http.post("/tasks/T-1/status", json={"status": "READY"})
    assert res.status_code == 422
