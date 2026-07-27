"""POST /documents/upload -- job polling conversion test file (2026-07-27)."""

import io

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import documents_api, requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.server import app
from tests._job_polling import poll_job_until_done


@pytest.fixture
def client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    graph_path = tmp_path / ".graphify-out" / "graph.json"
    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(requirements_api, "get_document_store", lambda *a, **k: doc_store)
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)
    monkeypatch.setattr(documents_api.project_scope, "resolve_project_data_dir", lambda *a, **k: tmp_path)
    return TestClient(app), req_store, doc_store


def _upload_and_wait(test_client, filename, content, content_type, actor="tester"):
    resp = test_client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), content_type)},
        data={"actor": actor},
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["data"]["job_id"]
    return poll_job_until_done(test_client, job_id)


def test_upload_txt_document_creates_chunks(client):
    test_client, req_store, doc_store = client
    content = b"# Security Requirements\nEncryption and SSL certificates must be applied."

    body = _upload_and_wait(test_client, "sample.txt", content, "text/plain")

    assert body["data"]["status"] == "done"
    result = body["data"]["result"]
    assert body["ok"] is True
    assert result["doc_filename"] == "sample.txt"
    assert result["chunk_count"] >= 1
    assert doc_store.load(result["doc_id"]) is not None


def test_upload_wav_audio_transcribes_via_faster_whisper(client):
    import os

    test_client, req_store, doc_store = client
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_speech_ko.wav")
    with open(fixture_path, "rb") as f:
        audio_bytes = f.read()

    body = _upload_and_wait(test_client, "sample_speech_ko.wav", audio_bytes, "audio/wav")

    assert body["data"]["status"] == "done"
    result = body["data"]["result"]
    assert body["ok"] is True
    assert result["doc_filename"] == "sample_speech_ko.wav"
    assert result["chunk_count"] >= 1
    markdown = doc_store.load(result["doc_id"])
    assert markdown is not None
    assert markdown.strip()


def test_upload_pdf_persists_original_bytes(client, tmp_path):
    from reportlab.pdfgen import canvas
    import io as _io

    buf = _io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Security requirement: encryption must be applied.")
    c.save()
    pdf_bytes = buf.getvalue()

    test_client, _req_store, _doc_store = client
    body = _upload_and_wait(test_client, "sample.pdf", pdf_bytes, "application/pdf")

    assert body["data"]["status"] == "done"
    doc_id = body["data"]["result"]["doc_id"]
    raw_path = tmp_path / "documents_raw" / f"{doc_id}.pdf"
    assert raw_path.exists()
    assert raw_path.read_bytes() == pdf_bytes


def test_upload_txt_does_not_create_raw_pdf_dir(client, tmp_path):
    test_client, _req_store, _doc_store = client
    body = _upload_and_wait(test_client, "sample.txt", b"plain text content here", "text/plain")
    assert body["data"]["status"] == "done"
    assert not (tmp_path / "documents_raw").exists()


def test_upload_docx_converts_via_libreoffice_and_persists_pdf(client, tmp_path):
    from backend.adapters.office_convert.libreoffice_bridge import (
        LibreOfficeNotFoundError,
        _soffice_path,
    )
    try:
        _soffice_path()
    except LibreOfficeNotFoundError:
        pytest.skip("LibreOffice not installed -- skip real integration test")

    from docx import Document

    docx_buf = io.BytesIO()
    doc = Document()
    doc.add_heading("Security Requirements", level=1)
    doc.add_paragraph("Encryption and SSL certificates must be applied.")
    doc.save(docx_buf)
    docx_buf.seek(0)

    test_client, req_store, _doc_store = client
    body = _upload_and_wait(
        test_client, "sample.docx", docx_buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert body["data"]["status"] == "done"
    doc_id = body["data"]["result"]["doc_id"]

    raw_path = tmp_path / "documents_raw" / f"{doc_id}.pdf"
    assert raw_path.exists()

    created = [r for r in req_store.list_all() if r.doc_id == doc_id]
    assert created, "no requirements created from docx upload"
    assert any(r.page_number is not None and r.bbox is not None for r in created)


def test_upload_empty_file_returns_422(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_upload_unsupported_extension_returns_422(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("file.xyz", io.BytesIO(b"content"), "application/octet-stream")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]
    body = poll_job_until_done(test_client, job_id)
    assert body["data"]["status"] == "failed"
    assert body["data"]["error"]["code"] == "AEGIS-VALIDATION"


def test_upload_not_yet_implemented_format_returns_422(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("doc.hwp", io.BytesIO(b"fake hwp content"), "application/octet-stream")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["job_id"]
    body = poll_job_until_done(test_client, job_id)
    assert body["data"]["status"] == "failed"
    assert body["data"]["error"]["code"] == "AEGIS-VALIDATION"
