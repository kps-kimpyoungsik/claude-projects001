"""[2026-07-30 신규] `backend/adapters/error_log.py` 재배선 통합 테스트.

`error_log.py`(log_parse_failure/has_known_failure)는 그 자체로는 이미 검증된 순수 유틸이지만
(CRZ — 이 파일에서 내부 로직을 다시 수정하지 않는다), 지금까지 어디서도 호출되지 않는 미배선
코드였다(directive D-664470cc). 이 테스트는 `document_upload_service.process_uploaded_file()`이
①실패 시 실제로 로그를 남기고 ②동일 (확장자, 파서전략) 조합의 과거 실패 이력이 있으면
`UploadResult.known_failure_warning`을 채우는지(업로드 자체는 막지 않음, T99 AIOS)를 검증한다.
"""

import io

import pytest

from backend.adapters.api import documents_api, requirements_api
from backend.adapters.parsers.text_passthrough_adapter import TextPassthroughAdapter
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.application.services import document_upload_service as svc
from backend.server import app
from fastapi.testclient import TestClient
from tests._job_polling import poll_job_until_done


def _make_flaky_parse(fail_on_calls: set[int], original_parse):
    """`TextPassthroughAdapter.parse_to_markdown`을 몇 번째 호출까지만 실패시키는 래퍼.

    `calls` 카운터를 클로저로 공유해, 같은 몽키패치를 여러 업로드에 걸쳐 재사용할 수 있게
    한다(테스트별로 독립된 카운터 dict를 새로 만들어 격리)."""
    calls = {"n": 0}

    def flaky_parse(self, file_stream, metadata):
        calls["n"] += 1
        if calls["n"] in fail_on_calls:
            raise ValueError(f"forced parse failure #{calls['n']}")
        return original_parse(self, file_stream, metadata)

    return flaky_parse


@pytest.fixture
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(svc.project_scope, "resolve_project_data_dir", lambda *a, **k: tmp_path)
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    return req_store, doc_store, tmp_path


def test_second_upload_after_failure_carries_known_failure_warning(stores, monkeypatch):
    """동일 (.txt, text_passthrough) 조합이 1번째 실패 후, 2번째(파싱 자체는 성공)
    호출 결과에 known_failure_warning이 채워지는지 확인한다."""
    req_store, doc_store, tmp_path = stores

    original_parse = TextPassthroughAdapter.parse_to_markdown
    flaky_parse = _make_flaky_parse({1}, original_parse)
    monkeypatch.setattr(TextPassthroughAdapter, "parse_to_markdown", flaky_parse)

    # 1번째 업로드: 아직 실패 이력이 없으므로 파싱 자체가 실패해도 known_failure_warning을
    # 채울 로그가 사전에 없다 — 예외가 그대로 전파되고(기존 422 흐름 유지), 실패가 새로
    # 기록된다.
    with pytest.raises(ValueError):
        svc.process_uploaded_file(
            filename="sample.txt",
            content=b"first content",
            actor="tester",
            req_store=req_store,
            doc_store=doc_store,
        )

    log_path = tmp_path / "parse_failures.jsonl"
    assert log_path.exists()
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 1

    # 2번째 업로드: 이번엔 파싱 자체는 성공하지만, 직전 실패 이력이 있으므로 경고가 채워져야
    # 한다(업로드는 막히지 않는다 — result가 정상 반환됨).
    result = svc.process_uploaded_file(
        filename="sample.txt",
        content=b"second content",
        actor="tester",
        req_store=req_store,
        doc_store=doc_store,
    )
    assert result.known_failure_warning is not None
    assert ".txt" in result.known_failure_warning
    assert "text_passthrough" in result.known_failure_warning

    # 로그는 실패 1건만 남아있어야 한다(2번째는 성공했으므로 추가 기록 없음).
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_successful_upload_without_prior_failure_has_no_warning(stores):
    """회귀 확인: 과거 실패 이력이 전혀 없는 정상 업로드는 known_failure_warning이 항상
    None이어야 한다."""
    req_store, doc_store, tmp_path = stores

    result = svc.process_uploaded_file(
        filename="sample.txt",
        content=b"# Security Requirements\nEncryption must be applied.",
        actor="tester",
        req_store=req_store,
        doc_store=doc_store,
    )

    assert result.known_failure_warning is None
    assert not (tmp_path / "parse_failures.jsonl").exists()


def test_parse_failure_is_appended_to_local_log(stores, monkeypatch):
    """파싱 실패 시 `parse_failures.jsonl`에 실제로 실패 레코드가 append되는지 확인한다."""
    req_store, doc_store, tmp_path = stores

    original_parse = TextPassthroughAdapter.parse_to_markdown
    flaky_parse = _make_flaky_parse({1}, original_parse)
    monkeypatch.setattr(TextPassthroughAdapter, "parse_to_markdown", flaky_parse)

    with pytest.raises(ValueError):
        svc.process_uploaded_file(
            filename="broken.txt",
            content=b"content that will fail to parse",
            actor="tester",
            req_store=req_store,
            doc_store=doc_store,
        )

    log_path = tmp_path / "parse_failures.jsonl"
    assert log_path.exists()

    import json

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["file_ext"] == ".txt"
    assert record["filename"] == "broken.txt"
    assert record["parser_strategy"] == "text_passthrough"
    assert "forced parse failure" in record["error_message"]


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    graph_path = tmp_path / ".graphify-out" / "graph.json"
    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(requirements_api, "get_document_store", lambda *a, **k: doc_store)
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)
    monkeypatch.setattr(documents_api.project_scope, "resolve_project_data_dir", lambda *a, **k: tmp_path)
    return TestClient(app), req_store, doc_store, tmp_path


def test_upload_api_exposes_known_failure_warning_field(api_client, monkeypatch):
    """HTTP 배선 확인: `POST /documents/upload` 폴링 결과 dict에 known_failure_warning
    필드가 노출되는지(있으면 문자열, 없으면 None) 확인한다 — 프론트 UI 변경은 스코프 밖."""
    test_client, req_store, doc_store, tmp_path = api_client

    original_parse = TextPassthroughAdapter.parse_to_markdown
    flaky_parse = _make_flaky_parse({1}, original_parse)
    monkeypatch.setattr(TextPassthroughAdapter, "parse_to_markdown", flaky_parse)

    # 1번째 업로드는 파싱 실패로 job이 failed 처리된다(known_failure_warning 필드는 이
    # 실패 응답에는 존재하지 않는다 — result 자체가 없으므로).
    resp1 = test_client.post(
        "/documents/upload",
        files={"file": ("sample.txt", io.BytesIO(b"first"), "text/plain")},
        data={"actor": "tester"},
    )
    assert resp1.status_code == 202
    body1 = poll_job_until_done(test_client, resp1.json()["data"]["job_id"])
    assert body1["data"]["status"] == "failed"

    # 2번째 업로드는 파싱이 성공하고, 과거 실패 이력 때문에 known_failure_warning이 채워져야
    # 한다.
    resp2 = test_client.post(
        "/documents/upload",
        files={"file": ("sample.txt", io.BytesIO(b"second"), "text/plain")},
        data={"actor": "tester"},
    )
    assert resp2.status_code == 202
    body2 = poll_job_until_done(test_client, resp2.json()["data"]["job_id"])
    assert body2["data"]["status"] == "done"
    result = body2["data"]["result"]
    assert result["known_failure_warning"] is not None
    assert ".txt" in result["known_failure_warning"]
