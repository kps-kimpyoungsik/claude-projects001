"""POST /documents/upload -- job polling conversion test file (2026-07-27)."""

import io

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import documents_api, requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.server import app
from tests._job_polling import poll_job_until_done
from tests.conftest import ollama_is_reachable


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


def test_upload_wav_audio_transcribes_via_faster_whisper(client, monkeypatch):
    import os

    from backend.application.services import job_registry

    # [2026-07-30 근본원인 확정, KH-2026-0783 패턴] 이 AEGIS 개발 환경은 30개 이상의 pm2
    # 백그라운드 데몬이 상시 CPU를 점유해(실측 loadpercentage=100) faster-whisper 전사가
    # `JOB_TIMEOUT_SECONDS`(기본 140s) 안에 못 끝나고 job_registry가 poison-pill 타임아웃으로
    # 잡을 failed 처리하는 flake가 반복 관측됐다 — 로그로 "job finished successfully after it
    # was already marked as timed out"가 확인돼(실제 전사 자체는 완료) 코드 결함이 아니라 순수
    # 시간 여유 부족임을 확정. 프로덕션 기본값(140s)은 그대로 두고, 이 테스트에서만
    # `job_registry.submit_job` 호출에 더 넉넉한 timeout_seconds를 주입한다(CRZ — 신규 override
    # 메커니즘 없음, submit_job이 이미 노출한 파라미터를 그대로 사용).
    _real_submit_job = job_registry.submit_job

    def _submit_job_with_generous_timeout(kind, fn, timeout_seconds=None):
        return _real_submit_job(kind, fn, timeout_seconds=300.0)

    monkeypatch.setattr(documents_api.job_registry, "submit_job", _submit_job_with_generous_timeout)

    test_client, req_store, doc_store = client
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_speech_ko.wav")
    with open(fixture_path, "rb") as f:
        audio_bytes = f.read()

    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample_speech_ko.wav", io.BytesIO(audio_bytes), "audio/wav")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 202, resp.text
    body = poll_job_until_done(test_client, resp.json()["data"]["job_id"], timeout=320.0)

    assert body["data"]["status"] == "done"
    result = body["data"]["result"]
    assert body["ok"] is True
    assert result["doc_filename"] == "sample_speech_ko.wav"
    assert result["chunk_count"] >= 1
    markdown = doc_store.load(result["doc_id"])
    assert markdown is not None
    assert markdown.strip()


@pytest.mark.skipif(
    not ollama_is_reachable(),
    reason="Ollama(127.0.0.1:11434) 미기동 — CI 등 vision 모델이 없는 환경에서는 스킵(CRZ, "
    "document_upload_service._build_chunking_splitter()와 동일한 헬스체크 폴백 패턴)",
)
def test_upload_png_image_describes_via_ollama_vision(client, monkeypatch):
    """[D-011db847 후속] png 업로드 → VisionDescribeAdapter → Ollama moondream 설명문.

    이 환경의 CPU 100% 상시 부하(KH-2026-0783) 패턴을 whisper 테스트에서 이미 확인했으므로
    처음부터 넉넉한 timeout_seconds를 준다(같은 근본원인에 대한 재발방지, 재차 flake→수정
    사이클을 반복하지 않기 위한 선제 조치)."""
    from backend.application.services import job_registry

    _real_submit_job = job_registry.submit_job

    def _submit_job_with_generous_timeout(kind, fn, timeout_seconds=None):
        return _real_submit_job(kind, fn, timeout_seconds=300.0)

    monkeypatch.setattr(documents_api.job_registry, "submit_job", _submit_job_with_generous_timeout)

    from PIL import Image
    import io as _io

    buf = _io.BytesIO()
    img = Image.new("RGB", (64, 64), color=(255, 0, 0))
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    test_client, req_store, doc_store = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample.png", io.BytesIO(png_bytes), "image/png")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 202, resp.text
    body = poll_job_until_done(test_client, resp.json()["data"]["job_id"], timeout=320.0)

    assert body["data"]["status"] == "done", body["data"].get("error")
    result = body["data"]["result"]
    assert body["ok"] is True
    assert result["doc_filename"] == "sample.png"
    assert result["chunk_count"] >= 1
    markdown = doc_store.load(result["doc_id"])
    assert markdown is not None
    assert markdown.strip()
    assert "이미지 설명" in markdown


def test_upload_whitespace_only_txt_fails_with_empty_parse_result(client):
    """[커버리지 보완] markdown.strip()이 빈 문자열이면(파일 자체는 비어있지 않지만 공백뿐)
    '파싱 결과가 비어 있습니다' ValueError로 실패해야 한다 — content 자체가 완전히 빈
    경우(422)와는 다른 경로."""
    test_client, _req_store, _doc_store = client
    body = _upload_and_wait(test_client, "whitespace.txt", b"   \n\t  \n  ", "text/plain")
    assert body["data"]["status"] == "failed"
    assert "비어 있습니다" in body["data"]["error"]["message"]


def test_upload_docx_falls_back_to_native_adapter_when_libreoffice_unavailable(client, monkeypatch):
    """[커버리지 보완] LibreOffice 변환이 실패(LibreOfficeNotFoundError 등)해도 업로드
    자체는 막지 않고 기존 네이티브 docx 어댑터로 조용히 폴백해야 한다(T99 AIOS) — 실제
    LibreOffice 설치 여부와 무관하게 이 폴백 분기를 직접 검증한다."""
    from backend.adapters.office_convert.libreoffice_bridge import LibreOfficeNotFoundError
    from backend.application.services import document_upload_service

    def _raise_not_found(*args, **kwargs):
        raise LibreOfficeNotFoundError("테스트: LibreOffice 미설치 시뮬레이션")

    monkeypatch.setattr(document_upload_service, "convert_to_pdf", _raise_not_found)

    from docx import Document

    docx_buf = io.BytesIO()
    doc = Document()
    doc.add_heading("Security Requirements", level=1)
    doc.add_paragraph("Encryption and SSL certificates must be applied.")
    doc.save(docx_buf)
    docx_buf.seek(0)

    test_client, _req_store, _doc_store = client
    body = _upload_and_wait(
        test_client, "sample.docx", docx_buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert body["data"]["status"] == "done", body["data"].get("error")
    assert body["data"]["result"]["chunk_count"] >= 1


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
