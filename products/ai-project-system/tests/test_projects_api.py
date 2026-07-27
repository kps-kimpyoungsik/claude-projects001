"""프로젝트 목록·생성 API(projects_api.py) — 기존 test_tasks_api.py와 동일한 monkeypatch
격리 패턴(TestClient + get_project_registry 교체, CRZ)."""

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import projects_api
from backend.adapters.persistence import project_scope
from backend.adapters.persistence.project_registry import DEFAULT_PROJECT_ID, ProjectRegistry
from backend.adapters.persistence.task_store import TaskStore
from backend.domain.entities.task import Task
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    registry = ProjectRegistry(tmp_path / "projects_registry.json")
    monkeypatch.setattr(projects_api, "get_project_registry", lambda: registry)
    # [2026-07-26 고도화] GET /projects/{id}(progress·config 병합)·
    # GET /projects/{id}/progress 테스트가 tasks_api.get_task_store()/
    # project_config_api.get_project_config_store()도 프로젝트별로 호출하므로,
    # 실제 data/ 오염 없이 tmp_path 아래로 격리(test_tasks_api.py와 동일 패턴, CRZ).
    monkeypatch.setattr(project_scope, "resolve_project_data_dir", lambda project_id: tmp_path / project_id)
    return TestClient(app), registry


def test_list_projects_includes_default_when_empty(client):
    test_client, _ = client
    res = test_client.get("/projects")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    ids = [p["id"] for p in body["data"]["projects"]]
    assert DEFAULT_PROJECT_ID in ids


def test_create_project_success(client):
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "새 프로젝트"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["name"] == "새 프로젝트"
    assert body["data"]["id"] != DEFAULT_PROJECT_ID

    listed = test_client.get("/projects").json()
    ids = [p["id"] for p in listed["data"]["projects"]]
    assert body["data"]["id"] in ids


def test_create_project_empty_name_returns_422(client):
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "   "})
    assert res.status_code == 422
    body = res.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-VALIDATION"


def test_create_project_missing_name_field_returns_422(client):
    test_client, _ = client
    res = test_client.post("/projects", json={})
    assert res.status_code == 422


# [2026-07-26 고도화] status 확장(ON_HOLD/ARCHIVED) — PATCH /projects/{id}/status는 이미
# 존재하는 엔드포인트라 "이미 동작할 것"을 실측 확인만 한다(과제 지시 1번의 검증 요구).


def test_update_project_status_to_on_hold_and_archived(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "보류 대상"}).json()["data"]

    res = test_client.patch(f"/projects/{created['id']}/status", json={"status": "ON_HOLD"})
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "ON_HOLD"

    res2 = test_client.patch(f"/projects/{created['id']}/status", json={"status": "ARCHIVED"})
    assert res2.status_code == 200
    assert res2.json()["data"]["status"] == "ARCHIVED"

    # 삭제(ARCHIVED)여도 물리 삭제가 아니라 목록에 그대로 남는다.
    listed = test_client.get("/projects").json()["data"]["projects"]
    ids = [p["id"] for p in listed]
    assert created["id"] in ids


def test_update_project_status_invalid_value_returns_422(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "x"}).json()["data"]
    res = test_client.patch(f"/projects/{created['id']}/status", json={"status": "NOPE"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


# [2026-07-26 고도화] start_date/end_date.


def test_create_project_with_dates(client):
    test_client, _ = client
    res = test_client.post(
        "/projects", json={"name": "일정있는 프로젝트", "start_date": "2026-08-01", "end_date": "2026-12-31"}
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["start_date"] == "2026-08-01"
    assert body["end_date"] == "2026-12-31"


def test_create_project_without_dates_defaults_null(client):
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "날짜없는 프로젝트"})
    body = res.json()["data"]
    assert body["start_date"] is None
    assert body["end_date"] is None


def test_create_project_invalid_date_format_returns_422(client):
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "x", "start_date": "not-a-date"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


# [2026-07-26 신설] GET /projects/{project_id} — 레지스트리 + config + progress 병합.


def test_get_project_detail_not_found_returns_404(client):
    test_client, _ = client
    res = test_client.get("/projects/proj-999")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "AEGIS-NOTFOUND"


def test_get_project_detail_without_config_returns_null_config_and_zero_progress(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "설정 없는 프로젝트"}).json()["data"]

    res = test_client.get(f"/projects/{created['id']}")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["id"] == created["id"]
    assert body["config"] is None
    assert body["progress"] == {"done_tasks": 0, "total_tasks": 0, "progress_pct": 0.0}


def test_get_project_detail_merges_config(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "설정 있는 프로젝트"}).json()["data"]

    put_res = test_client.put(
        "/project-config",
        params={"project_id": created["id"]},
        json={
            "project_name": created["name"],
            "goal": "목표 문장",
            "selected_areas": ["WEB"],
            "actor": "tester",
        },
    )
    assert put_res.status_code == 200

    res = test_client.get(f"/projects/{created['id']}")
    body = res.json()["data"]
    assert body["config"]["goal"] == "목표 문장"
    assert body["config"]["selected_areas"] == ["WEB"]


# [2026-07-26 신설] PATCH /projects/{project_id} — name/start_date/end_date 부분 업데이트.


def test_patch_project_updates_name_and_dates(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "원래 이름"}).json()["data"]

    res = test_client.patch(
        f"/projects/{created['id']}",
        json={"name": "바뀐 이름", "start_date": "2026-09-01", "end_date": "2026-10-01"},
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["name"] == "바뀐 이름"
    assert body["start_date"] == "2026-09-01"
    assert body["end_date"] == "2026-10-01"

    listed = test_client.get("/projects").json()["data"]["projects"]
    match = next(p for p in listed if p["id"] == created["id"])
    assert match["name"] == "바뀐 이름"


def test_patch_project_partial_update_keeps_other_fields(client):
    test_client, _ = client
    created = test_client.post(
        "/projects", json={"name": "원래 이름", "start_date": "2026-01-01", "end_date": "2026-02-01"}
    ).json()["data"]

    res = test_client.patch(f"/projects/{created['id']}", json={"name": "새 이름만 변경"})
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["name"] == "새 이름만 변경"
    assert body["start_date"] == "2026-01-01"
    assert body["end_date"] == "2026-02-01"


def test_patch_project_not_found_returns_422(client):
    test_client, _ = client
    res = test_client.patch("/projects/proj-999", json={"name": "x"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


# [2026-07-26 신설] GET /projects/{project_id}/progress.


def test_get_project_progress_not_found_returns_404(client):
    test_client, _ = client
    res = test_client.get("/projects/proj-999/progress")
    assert res.status_code == 404


# [2026-07-27 신설] 원자적 생성(`POST /projects` + `config` 필드) — 사용자 지시로 확정된
# 방향: registry.create() + ProjectConfigStore.save()를 한 요청 안에서 원자적으로 묶는다.


def test_create_project_atomic_persists_registry_and_config(client):
    test_client, _ = client
    res = test_client.post(
        "/projects",
        json={
            "name": "원자적 생성 프로젝트",
            "config": {"goal": "목표 문장", "selected_areas": ["WEB"]},
            "actor": "tester",
        },
    )
    assert res.status_code == 200
    project_id = res.json()["data"]["id"]

    detail = test_client.get(f"/projects/{project_id}").json()["data"]
    assert detail["config"]["goal"] == "목표 문장"
    assert detail["config"]["selected_areas"] == ["WEB"]


def test_create_project_atomic_rolls_back_registry_on_config_failure(client, monkeypatch):
    test_client, registry = client

    from backend.adapters.persistence.project_config_store import ProjectConfigStore

    def _boom(self, config, created_by):
        raise RuntimeError("simulated config save failure")

    monkeypatch.setattr(ProjectConfigStore, "save", _boom)

    res = test_client.post(
        "/projects",
        json={
            "name": "롤백되어야 할 프로젝트",
            "config": {"goal": "목표", "selected_areas": ["WEB"]},
            "actor": "tester",
        },
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"

    # 실패한 요청이 만든 이름의 registry 레코드가 남아있으면 안 된다(고아 방지).
    listed = test_client.get("/projects").json()["data"]["projects"]
    assert all(p["name"] != "롤백되어야 할 프로젝트" for p in listed)


def test_create_project_atomic_registry_failure_leaves_no_orphan_config(client):
    test_client, _ = client
    # 빈 이름은 registry.create()가 즉시 거부 — config_store.save()는 호출조차 되지 않아야
    # 하므로, 이 project_id 자체가 만들어지지 않는다(비교 대상 config 파일도 생기지 않음).
    res = test_client.post(
        "/projects",
        json={"name": "   ", "config": {"goal": "목표", "selected_areas": ["WEB"]}, "actor": "tester"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_create_project_without_config_keeps_backward_compatible_contract(client):
    """`config`를 생략하면 기존 계약(레지스트리 엔트리만 생성) 그대로 — 회귀 없음."""
    test_client, _ = client
    res = test_client.post("/projects", json={"name": "설정 없이 생성"})
    assert res.status_code == 200
    project_id = res.json()["data"]["id"]

    detail = test_client.get(f"/projects/{project_id}").json()["data"]
    assert detail["config"] is None


# [2026-07-27 신설] GET /projects/_consistency-check — 고아 실측 탐지(자동수정 없음).


def test_consistency_check_reports_project_without_config(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "설정 없는 프로젝트"}).json()["data"]

    res = test_client.get("/projects/_consistency-check")
    assert res.status_code == 200
    data = res.json()["data"]
    # DEFAULT_PROJECT_ID도 config가 없으면 함께 잡힐 수 있으므로(list_all()의 가상
    # 포함, 이 fixture의 tmp_path엔 default config가 없음) 개수가 아니라 방금 만든
    # project_id가 포함되는지로 확인한다.
    assert created["id"] in data["projects_without_config"]


def test_consistency_check_clean_when_config_saved(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "설정 있는 프로젝트"}).json()["data"]
    test_client.put(
        "/project-config",
        params={"project_id": created["id"]},
        json={"project_name": created["name"], "goal": "목표", "selected_areas": ["WEB"], "actor": "tester"},
    )

    res = test_client.get("/projects/_consistency-check")
    data = res.json()["data"]
    assert created["id"] not in data["projects_without_config"]


def test_get_project_progress_counts_done_tasks(client):
    test_client, _ = client
    created = test_client.post("/projects", json={"name": "태스크 있는 프로젝트"}).json()["data"]

    task_store = TaskStore(project_scope.resolve_project_data_dir(created["id"]) / "tasks_store.json")
    seeded = []
    for i in range(3):
        task = Task(
            task_id=f"T-{i}",
            domain_code="WEB",
            title=f"태스크{i}",
            description="충분히 긴 설명 텍스트로 최소 길이 요건을 충족시킨다",
            source_req_ids=["REQ-TECH-WEB-001"],
            acceptance_criteria=["동작 확인"],
            impact_scope=["frontend/views/x.html"],
            solution_stack=["FastAPI"],
        )
        task_store.create_or_update(task)
        seeded.append(task)

    # 2건만 READY -> IN_PROGRESS -> DONE까지 전이, 1건은 DRAFT로 남긴다.
    for i in range(2):
        task_store.set_status(f"T-{i}", "READY", actor="tester")
        task_store.set_status(f"T-{i}", "IN_PROGRESS", actor="tester")
        task_store.set_status(f"T-{i}", "DONE", actor="tester", reason="검증 완료")

    res = test_client.get(f"/projects/{created['id']}/progress")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body == {"done_tasks": 2, "total_tasks": 3, "progress_pct": pytest.approx(66.7)}

    # GET /projects/{id}가 동일한 progress를 함께 반환하는지도 확인.
    detail = test_client.get(f"/projects/{created['id']}").json()["data"]
    assert detail["progress"] == body
