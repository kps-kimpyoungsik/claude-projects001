"""Task 상태 조회·전이 API — FastAPI TestClient로 인메모리 검증 (test_requirements_api.py와
동일 monkeypatch 격리 패턴, CRZ)."""

import json

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import tasks_api
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.file_lock import graph_path
from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import Task
from backend.domain.graph.entities import NodeKind
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


def _read_graph(project_id: str = "default") -> dict:
    return json.loads(graph_path(project_id).read_text(encoding="utf-8"))


def test_create_task_merges_task_node_and_implements_edge_into_graph(client):
    """[2026-07-29 배선, directive D-eebcef47] Task 생성 시 그래프에 TASK 노드 +
    IMPLEMENTS 엣지가 함께 merge되어야 한다 — 엣지만 생기고 노드가 없는 고아 엣지
    (T92 GDI 위반)가 생기지 않음을 실제 graph.json 내용으로 확인한다."""
    http, _store = client
    res = http.post(
        "/tasks",
        json={
            "domain_code": "WEB",
            "title": "그래프 연결 태스크",
            "description": "충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
            "source_req_ids": ["REQ-TECH-WEB-001"],
            "acceptance_criteria": ["동작 확인"],
            "impact_scope": ["frontend/views/x.html"],
            "solution_stack": ["FastAPI"],
        },
    )
    assert res.status_code == 200
    task_id = res.json()["data"]["task_id"]

    graph = _read_graph()
    task_nodes = [n for n in graph["nodes"] if n["kind"] == NodeKind.TASK.value]
    assert len(task_nodes) == 1
    assert task_nodes[0]["node_id"] == task_id
    assert task_nodes[0]["label"] == "그래프 연결 태스크"

    implements_edges = [e for e in graph["edges"] if e["kind"] == "IMPLEMENTS"]
    assert len(implements_edges) == 1
    assert implements_edges[0]["source_id"] == task_id
    assert implements_edges[0]["target_id"] == "REQ-TECH-WEB-001"

    # 고아 엣지 방지 확인: 엣지의 source_id(task_id)를 가리키는 노드가 실제로 그래프에 있다.
    node_ids = {n["node_id"] for n in graph["nodes"]}
    assert implements_edges[0]["source_id"] in node_ids
    assert graph.get("rejected_edges", []) == []


def test_create_task_without_source_req_ids_merges_node_but_no_edge(client):
    """source_req_ids가 비어 있으면 IMPLEMENTS 엣지는 생기지 않지만 Task 노드는 여전히
    merge되어야 한다(추후 요구사항이 연결될 때를 대비한 완전한 그래프 표현)."""
    http, _store = client
    res = http.post("/tasks", json={"domain_code": "WEB", "title": "단독 태스크", "description": "x" * 25})
    assert res.status_code == 200
    task_id = res.json()["data"]["task_id"]

    graph = _read_graph()
    task_nodes = [n for n in graph["nodes"] if n["kind"] == NodeKind.TASK.value]
    assert len(task_nodes) == 1
    assert task_nodes[0]["node_id"] == task_id
    assert [e for e in graph["edges"] if e["source_id"] == task_id] == []
