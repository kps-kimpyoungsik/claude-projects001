"""[Phase 5.1] E2E — Task 생성부터 완료까지 전체 생애주기를 실제 HTTP API로 관통 검증한다.

개별 유닛 테스트(state machine·lock store·API 각각)는 이미 있다 — 이 파일의 목적은 그
조각들이 실제로 "조합됐을 때" 끊김 없이 동작하는지(생성 → 배차 준비 → 병렬 락 통제 →
완료보고서 → 서킷 브레이커까지) 하나의 시나리오로 확인하는 것이다."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import tasks_api
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.file_lock import graph_path
from backend.adapters.persistence.task_store import TaskStore
from backend.application.services.completion_report_service import build_completion_report
from backend.application.services.graph_pipeline_service import merge_into_graph
from backend.domain.entities.requirement import make_requirement_node
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / "tasks.json")
    monkeypatch.setattr(tasks_api, "get_task_store", lambda *a, **k: store)
    # [2026-07-25 회귀수정] tasks_api._load_graph()가 project_scope.resolve_project_data_dir()로
    # 그래프 경로를 얻는다(test_manual_requirement_creation.py와 동일 격리 패턴, CRZ) — 이 격리가
    # 없으면 실제 data/.graphify-out/graph.json(다른 테스트·실사용이 채운 그래프)을 읽어 이
    # 테스트의 source_req_ids가 "그래프에 없음"으로 오판정되어 태스크가 DRAFT에 강제 고정된다.
    monkeypatch.setattr(project_scope, "resolve_project_data_dir", lambda project_id: tmp_path / project_id)

    # [2026-07-29 회귀수정, directive D-eebcef47] `POST /tasks`가 이제 Task 생성 시점에
    # Task 노드를 그래프에 merge한다(고아 엣지 방지, T92 GDI) — 그 결과 이 파일의 첫 번째
    # Task 생성부터 graph.json이 실재하게 되어, 이후 생성되는 Task의 `_load_graph()`가 더
    # 이상 `None`이 아니게 된다. `check_sufficiency()`는 graph가 주어지면
    # `verify_task_requirement_links()`로 source_req_ids가 그래프상 실제 Requirement
    # 노드인지까지 검증하므로, 이 파일이 쓰는 "REQ-TECH-WEB-001"이 그래프에 실재하지
    # 않으면 두 번째 이후 Task부터 "그래프에 없는 요구사항 참조"로 needs_escalation=True가
    # 되어 상태 전이가 서킷 브레이커에 막힌다(회귀). 실제 운영에서는 문서 업로드/수동 등록 시
    # `requirements_api.sync_requirement_to_graph()`가 이 노드를 먼저 채워두므로, 테스트도
    # 그 전제(요구사항이 먼저 그래프에 실재)를 동일하게 맞춘다(CRZ — 신규 헬퍼 로직 없음,
    # 기존 `make_requirement_node`/`merge_into_graph`만 재사용).
    merge_into_graph(
        graph_path("default"),
        nodes=[make_requirement_node("REQ-TECH-WEB-001", description="테스트용 요구사항", source_ref="test fixture")],
        edges=[],
    )
    return TestClient(app), store


def _create(http, title="E2E 태스크", impact_scope=None):
    res = http.post(
        "/tasks",
        json={
            "domain_code": "WEB",
            "title": title,
            "description": "충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
            "source_req_ids": ["REQ-TECH-WEB-001"],
            "acceptance_criteria": ["동작 확인"],
            "impact_scope": impact_scope or ["frontend/views/x.html"],
            "solution_stack": ["FastAPI"],
        },
    )
    assert res.status_code == 200
    return res.json()["data"]["task_id"]


def test_full_lifecycle_create_to_done_with_completion_report(client):
    http, store = client
    task_id = _create(http)

    # 생성 직후 DRAFT
    assert http.get(f"/tasks/{task_id}").json()["data"]["status"] == "DRAFT"

    # 배차 준비: READY -> IN_PROGRESS(락 획득)
    http.post(f"/tasks/{task_id}/status", json={"status": "READY", "actor": "dispatcher"})
    res = http.post(f"/tasks/{task_id}/status", json={"status": "IN_PROGRESS", "actor": "worker-agent"})
    assert res.status_code == 200
    assert store._lock_store.held_by(task_id) == ["frontend/views/x.html"]

    # 배차된 agent가 작업 결과를 완료 보고서로 조립(실제 git 호출은 이 테스트에서 흉내만 낸다)
    diff_stat = " frontend/views/x.html | 12 +++++--\n 1 file changed, 8 insertions(+), 4 deletions(-)"
    report = build_completion_report(
        task_id=task_id,
        source_req_ids=["REQ-TECH-WEB-001"],
        git_diff_stat_output=diff_stat,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    assert report.files_changed == [{"path": "frontend/views/x.html", "change_type": "modified", "summary": "12 line(s) changed"}]

    # 완료 보고 후 DONE 전이(근거=완료 보고서 파일 목록) -> 락 해제
    res = http.post(
        f"/tasks/{task_id}/status",
        json={"status": "DONE", "actor": "worker-agent", "reason": f"완료 보고서: {report.files_changed}"},
    )
    assert res.status_code == 200
    assert store._lock_store.held_by(task_id) == []

    final = http.get(f"/tasks/{task_id}").json()["data"]
    assert final["status"] == "DONE"
    assert [e["to_status"] for e in final["status_history"]] == ["READY", "IN_PROGRESS", "DONE"]


def test_two_parallel_tasks_second_waits_for_first_lock_release(client):
    """§PCM 원칙의 런타임판 — 겹치는 impact_scope를 가진 두 Task는 동시에 IN_PROGRESS일 수
    없고, 하나가 끝나야(DONE) 다른 하나가 진행 가능하다."""
    http, _store = client
    t1 = _create(http, title="T1", impact_scope=["shared.py"])
    t2 = _create(http, title="T2", impact_scope=["shared.py"])

    http.post(f"/tasks/{t1}/status", json={"status": "READY", "actor": "x"})
    http.post(f"/tasks/{t1}/status", json={"status": "IN_PROGRESS", "actor": "x"})

    http.post(f"/tasks/{t2}/status", json={"status": "READY", "actor": "x"})
    blocked = http.post(f"/tasks/{t2}/status", json={"status": "IN_PROGRESS", "actor": "x"})
    assert blocked.status_code == 422

    http.post(f"/tasks/{t1}/status", json={"status": "DONE", "actor": "x", "reason": "완료"})
    now_ok = http.post(f"/tasks/{t2}/status", json={"status": "IN_PROGRESS", "actor": "x"})
    assert now_ok.status_code == 200


def test_circuit_breaker_trips_after_repeated_blocked_and_requires_override(client):
    """[Phase 5.3] 같은 Task가 BLOCKED에 3회 도달하면 서킷 브레이커가 트립되어 사람 검토
    없이는(override_escalation) 더 이상 전이할 수 없어야 한다."""
    http, _store = client
    task_id = _create(http)
    http.post(f"/tasks/{task_id}/status", json={"status": "READY", "actor": "x"})

    # 1~2번째 BLOCKED: 아직 임계(3) 미달 — override 없이도 정상 왕복 가능
    for _ in range(2):
        http.post(f"/tasks/{task_id}/status", json={"status": "BLOCKED", "actor": "x", "reason": "의존성 미해결"})
        res = http.post(f"/tasks/{task_id}/status", json={"status": "READY", "actor": "x"})
        assert res.status_code == 200
        assert res.json()["data"]["needs_escalation"] is False

    # 3번째 BLOCKED: 임계 도달 -> 서킷 브레이커 트립(needs_escalation=True)
    tripped = http.post(f"/tasks/{task_id}/status", json={"status": "BLOCKED", "actor": "x", "reason": "의존성 미해결"})
    assert tripped.json()["data"]["needs_escalation"] is True

    # 트립 상태에서 override 없는 READY 전이는 거부되어야 함
    denied = http.post(f"/tasks/{task_id}/status", json={"status": "READY", "actor": "x"})
    assert denied.status_code == 422

    # 사람 검토 확인(override_escalation=True) 후에만 전이 허용 + 브레이커 리셋
    approved = http.post(
        f"/tasks/{task_id}/status",
        json={"status": "READY", "actor": "human-reviewer", "override_escalation": True},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["needs_escalation"] is False
