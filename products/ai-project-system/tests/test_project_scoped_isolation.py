"""[2026-07-22 고도화] 여러 프로젝트가 실제로 격리되는지 검증하는 통합 테스트.

`project_scope.resolve_project_data_dir()`를 tmp_path 기반으로 바꿔치기해(CRZ — 실제
운영 경로 규칙과 동일한 함수를 그대로 사용, 별도 테스트 전용 로직 없음), project_id를
다르게 준 두 번의 업로드가 서로의 요구사항 목록에 나타나지 않음을 실제 HTTP 요청으로
확인한다(§W-5 — API 레벨 ground-truth, 스토어 객체 직접 조작 아님)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.adapters.persistence import project_scope
from backend.server import app
from tests._job_polling import poll_job_until_done

DOC_TEXT = "# 보안 요건\n암호화 솔루션과 SSL 인증서를 적용하고 소스코드 취약성 점검을 수행한다.\n"


@pytest.fixture
def client(tmp_path, monkeypatch):
    def _scoped_dir(project_id: str) -> Path:
        return tmp_path / project_id

    monkeypatch.setattr(project_scope, "resolve_project_data_dir", _scoped_dir)
    # requirements_api/tasks_api/documents_api 전부 이 모듈 함수를 import해서 쓰므로
    # 한 곳만 패치하면 전 라우터에 반영된다(모듈 속성 참조, CRZ 재사용).
    return TestClient(app)


def test_requirements_created_in_one_project_are_invisible_in_another(client):
    # [2026-07-28 회귀수정] `POST /documents/upload`는 2026-07-27 근본전환으로 동기 200이
    # 아니라 202+job_id를 반환하고 실제 파이프라인은 백그라운드에서 처리된다(documents_api.py
    # upload_document() docstring 참조) — 이 테스트는 그 전환 이전에 작성돼 갱신되지 않은
    # 채 남아 있었다(실측 발견, 신규 계약 변경 아님 — 기존 API 계약을 뒤늦게 반영).
    upload_a = client.post(
        "/documents/upload",
        files={"file": ("a.txt", DOC_TEXT.encode("utf-8"), "text/plain")},
        data={"actor": "tester", "project_id": "proj-a"},
    )
    assert upload_a.status_code == 202
    job_id = upload_a.json()["data"]["job_id"]
    job_body = poll_job_until_done(client, job_id)
    assert job_body["ok"] is True
    assert job_body["data"]["status"] == "done"
    created_req_ids = job_body["data"]["result"]["requirements_created"]
    assert created_req_ids  # 최소 1건은 채번되어야 이 테스트가 의미 있음

    list_a = client.get("/requirements", params={"project_id": "proj-a"}).json()
    list_b = client.get("/requirements", params={"project_id": "proj-b"}).json()
    list_default = client.get("/requirements").json()

    ids_a = [r["req_id"] for r in list_a["data"]["requirements"]]
    ids_b = [r["req_id"] for r in list_b["data"]["requirements"]]
    ids_default = [r["req_id"] for r in list_default["data"]["requirements"]]

    assert set(created_req_ids).issubset(set(ids_a))
    assert not set(created_req_ids) & set(ids_b)
    assert not set(created_req_ids) & set(ids_default)


def test_tasks_are_isolated_per_project(client):
    task_body = {
        "domain_code": "WEB",
        "title": "테스트 태스크",
        "description": "격리 검증용",
    }
    created = client.post("/tasks", params={"project_id": "proj-a"}, json=task_body)
    assert created.status_code == 200
    task_id = created.json()["data"]["task_id"]

    list_a = client.get("/tasks", params={"project_id": "proj-a"}).json()
    list_b = client.get("/tasks", params={"project_id": "proj-b"}).json()

    assert task_id in [t["task_id"] for t in list_a["data"]["tasks"]]
    assert task_id not in [t["task_id"] for t in list_b["data"]["tasks"]]
