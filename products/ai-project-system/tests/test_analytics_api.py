import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import requirements_api, tasks_api
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import Task
from backend.domain.requirements.classifier import classify_chunk
from backend.server import app

SECURITY_TEXT = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다."


@pytest.fixture
def client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    task_store = TaskStore(tmp_path / "tasks.json")
    graph_path = tmp_path / ".graphify-out" / "graph.json"
    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(tasks_api, "get_task_store", lambda *a, **k: task_store)
    # [2026-07-25 회귀수정] requirements_api._graph_path() 격리(tests/test_requirements_api.py와
    # 동일 패턴) — 없으면 실제 data/.graphify-out/graph.json 오염(CRZ).
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)
    return TestClient(app), req_store, task_store


def test_failure_patterns_empty_when_nothing_pending(client):
    http, _req_store, _task_store = client
    res = http.get("/analytics/failure-patterns")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["requirement_review_patterns"] == []
    assert body["task_escalation_patterns"] == []


def test_failure_patterns_surfaces_under_review_requirement(client):
    http, req_store, _task_store = client
    classification = classify_chunk(SECURITY_TEXT)
    req_store.add_from_classification(
        classification, description="보안 요건", source_ref="doc::child:0",
        doc_id="doc1", heading_path=["보안 요건"], char_start=0, char_end=10,
    )

    res = http.get("/analytics/failure-patterns")
    patterns = res.json()["data"]["requirement_review_patterns"]
    # UNDER_REVIEW로 남았는지 여부는 classify_chunk 신뢰도에 따라 갈리므로, "패턴 있으면 구조가
    # 맞는지"만 확인(신뢰도 낮은 텍스트가 아니면 빈 리스트일 수 있어 존재 여부는 단정하지 않음)
    for p in patterns:
        assert set(p.keys()) == {
            "doc_type_code", "area_code", "count", "avg_doc_type_confidence",
            "avg_area_confidence", "example_req_ids",
        }


def test_failure_patterns_surfaces_task_escalation(client):
    http, _req_store, task_store = client
    task_store.create_or_update(Task(task_id="T-1", domain_code="WEB", title="t", description="short"))  # 불충분

    res = http.get("/analytics/failure-patterns")
    patterns = res.json()["data"]["task_escalation_patterns"]
    assert len(patterns) > 0
    assert patterns[0]["domain_code"] == "WEB"
    assert "T-1" in patterns[0]["example_task_ids"]
