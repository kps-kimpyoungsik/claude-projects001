"""[2026-07-25 §D-b83768b2] 최소 API 인증 게이트(auth.py) 회귀 테스트.

기본값(AIPS_API_KEY 미설정)은 인증 비활성 — 기존 테스트 전부가 이 상태로 통과해야
한다(회귀 0). AIPS_API_KEY 설정 시에만 X-API-Key 헤더 검증이 활성화됨을 별도 확인.
"""

import pytest
from fastapi.testclient import TestClient

from backend.server import app


def test_api_open_by_default_when_no_key_configured(monkeypatch):
    monkeypatch.delenv("AIPS_API_KEY", raising=False)
    client = TestClient(app)
    res = client.get("/projects")
    assert res.status_code == 200


def test_api_requires_matching_key_when_configured(monkeypatch):
    monkeypatch.setenv("AIPS_API_KEY", "secret-test-key")
    client = TestClient(app)

    res_no_key = client.get("/projects")
    assert res_no_key.status_code == 401

    res_wrong_key = client.get("/projects", headers={"X-API-Key": "wrong"})
    assert res_wrong_key.status_code == 401

    res_correct_key = client.get("/projects", headers={"X-API-Key": "secret-test-key"})
    assert res_correct_key.status_code == 200


def test_health_endpoint_not_gated_by_api_key(monkeypatch):
    monkeypatch.setenv("AIPS_API_KEY", "secret-test-key")
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200


def test_static_frontend_not_gated_by_api_key(monkeypatch):
    monkeypatch.setenv("AIPS_API_KEY", "secret-test-key")
    client = TestClient(app)
    res = client.get("/views/project-setup.html")
    assert res.status_code == 200
