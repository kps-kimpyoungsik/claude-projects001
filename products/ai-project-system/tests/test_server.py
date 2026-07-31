"""backend/server.py 단위 테스트 — 지금까지 전용 테스트 파일이 없었다. 전역 예외
핸들러(스택트레이스 비노출, T99 AIOS)와 루트 리다이렉트를 직접 검증한다."""

import asyncio
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.server import app, unhandled_exception_handler


def test_root_redirects_to_index_html():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/views/index.html"


def test_unhandled_exception_handler_returns_generic_envelope_without_stack_trace():
    """[커버리지 보완, T99 AIOS] 처리되지 않은 예외는 500 + 공통 envelope로 변환되고,
    원본 예외 메시지(내부 정보 노출 가능성)는 응답 바디에 그대로 노출되지 않는다 —
    서버 로그에만 남는다."""
    fake_request = MagicMock()
    fake_request.method = "GET"
    fake_request.url.path = "/some/path"

    response = asyncio.run(
        unhandled_exception_handler(fake_request, RuntimeError("내부 DB 커넥션 문자열 유출 위험"))
    )

    assert response.status_code == 500
    import json

    body = json.loads(response.body)
    assert body["ok"] is False
    assert body["error"]["code"] == "AEGIS-INTERNAL"
    assert "내부 DB 커넥션 문자열" not in body["error"]["message"]  # 원본 예외 메시지 비노출
    assert body["meta"]["degraded"] is True
