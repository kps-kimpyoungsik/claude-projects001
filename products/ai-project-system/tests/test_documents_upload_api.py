"""POST /documents/upload — 실제 HTTP 업로드 엔드포인트 테스트(2026-07-22 신규).

`document_upload_service.process_uploaded_file`이 테스트에서만 직접 호출되고 실제
라우트가 없었던 갭을 메운 배선을 검증한다. fixture는 test_documents_api.py와 동일한
monkeypatch 격리 패턴을 재사용한다(신규 로직 없음, CRZ).
"""

import io

import pytest
from fastapi.testclient import TestClient

from backend.adapters.api import documents_api, requirements_api
from backend.adapters.persistence.document_store import DocumentStore
from backend.adapters.persistence.requirement_store import RequirementStore
from backend.server import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    req_store = RequirementStore(tmp_path / "requirements_store.json")
    doc_store = DocumentStore(tmp_path / "documents")
    graph_path = tmp_path / ".graphify-out" / "graph.json"
    monkeypatch.setattr(requirements_api, "get_requirement_store", lambda *a, **k: req_store)
    monkeypatch.setattr(requirements_api, "get_document_store", lambda *a, **k: doc_store)
    # [2026-07-25 회귀수정] 문서업로드→요구사항 채번 경로가 sync_requirement_to_graph()를
    # 거쳐 _graph_path()에 쓴다 — 격리 없으면 실제 data/.graphify-out/graph.json 오염(CRZ,
    # tests/test_requirements_api.py와 동일 패턴).
    monkeypatch.setattr(requirements_api, "_graph_path", lambda *a, **k: graph_path)
    # [2026-07-25 §8 원본PDF저장 테스트 격리] documents_api._original_pdf_path()가
    # project_scope.resolve_project_data_dir()를 직접 호출한다 — 격리 없으면 PDF 업로드
    # 테스트가 실제 data/documents_raw/에 파일을 쓴다(tests/test_documents_api.py와 동일
    # 패턴 재사용, CRZ — tasks_api 회귀수정 사례와 동일 계열 함정 사전 차단).
    monkeypatch.setattr(documents_api.project_scope, "resolve_project_data_dir", lambda *a, **k: tmp_path)
    return TestClient(app), req_store, doc_store


def test_upload_txt_document_creates_chunks(client):
    test_client, req_store, doc_store = client
    content = b"# Security Requirements\nEncryption and SSL certificates must be applied."

    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample.txt", io.BytesIO(content), "text/plain")},
        data={"actor": "tester"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["doc_filename"] == "sample.txt"
    assert body["data"]["chunk_count"] >= 1
    assert doc_store.load(body["data"]["doc_id"]) is not None


def test_upload_wav_audio_transcribes_via_faster_whisper(client):
    """[2026-07-25 §D-777d8fd9] 음성(.wav) 업로드가 더 이상 422가 아니라 실제
    faster-whisper(tiny 모델, 실오디오)로 전사되어 청크가 생성되는지 검증한다 —
    SpeechToTextAdapter가 document_upload_service._ADAPTERS에 배선됐는지의 end-to-end
    확인(단위 테스트인 tests/test_faster_whisper_engine.py와 별개로, 실제 업로드
    경로 전체가 연결됐는지가 이 테스트의 목적)."""
    import os

    test_client, req_store, doc_store = client
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_speech_ko.wav")
    with open(fixture_path, "rb") as f:
        audio_bytes = f.read()

    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample_speech_ko.wav", io.BytesIO(audio_bytes), "audio/wav")},
        data={"actor": "tester"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["doc_filename"] == "sample_speech_ko.wav"
    assert body["data"]["chunk_count"] >= 1
    markdown = doc_store.load(body["data"]["doc_id"])
    assert markdown is not None
    assert markdown.strip()  # 실제 전사 텍스트가 비어있지 않음


def test_upload_pdf_persists_original_bytes(client, tmp_path):
    """[2026-07-25 §8 갭 해소, directive D-d65a28f2] PDF 업로드 시 원본 바이트가
    documents_api._original_pdf_path()가 가리키는 위치에 그대로 저장되는지 검증한다 —
    이게 없으면 GET /documents/{doc_id}/page/{page_number}가 실제 업로드 문서에서
    항상 404를 반환한다(§8-4 페이지 이미지 렌더링의 전제조건)."""
    from reportlab.pdfgen import canvas
    import io as _io

    buf = _io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Security requirement: encryption must be applied.")
    c.save()
    pdf_bytes = buf.getvalue()

    test_client, _req_store, _doc_store = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"actor": "tester"},
    )

    assert resp.status_code == 200
    doc_id = resp.json()["data"]["doc_id"]
    raw_path = tmp_path / "documents_raw" / f"{doc_id}.pdf"
    assert raw_path.exists()
    assert raw_path.read_bytes() == pdf_bytes


def test_upload_txt_does_not_create_raw_pdf_dir(client, tmp_path):
    """비-PDF 업로드는 documents_raw/를 만들지 않는다(§8-6 — bbox/page_number가 None인
    포맷은 원본 저장이 불필요, 불필요한 디스크 쓰기 회피)."""
    test_client, _req_store, _doc_store = client
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("sample.txt", io.BytesIO(b"plain text content here"), "text/plain")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 200
    assert not (tmp_path / "documents_raw").exists()


def test_upload_docx_converts_via_libreoffice_and_persists_pdf(client, tmp_path):
    """[2026-07-25 §8 W4] DOCX 업로드가 LibreOffice로 변환돼 §8-2 PDF 파이프라인에 편입되는지
    실통합 검증(mock 아님, 실제 변환) — 이 개발환경에 LibreOffice가 없으면 스킵한다(§0-5,
    거짓 PASS 금지 — process_uploaded_file()이 변환 실패 시 네이티브 어댑터로 자동
    폴백하므로 LibreOffice 미설치여도 업로드 자체는 200으로 성공하지만, 그 경우 이 테스트가
    검증하려는 '변환 경로'는 실행되지 않았으므로 의미 있는 assertion이 불가능하다)."""
    from backend.adapters.office_convert.libreoffice_bridge import (
        LibreOfficeNotFoundError,
        _soffice_path,
    )
    try:
        _soffice_path()
    except LibreOfficeNotFoundError:
        pytest.skip("LibreOffice 미설치 환경 — 실통합 테스트 스킵(§0-5, 거짓 PASS 금지)")

    from docx import Document

    docx_buf = io.BytesIO()
    doc = Document()
    # [수정 — 근본원인] 분류기(classifier.py)는 결정론적 한국어 키워드 매칭만 쓴다
    # (LLM 의미판단 아님, T98 AIP) — 영어 문장은 doc_type_code/area_code 어느 쪽도 매칭되지
    # 않아 채번 자체가 안 된다(추정 아님, tests/test_requirements_api.py의 실제 통과 픽스처
    # "보안 요건\n암호화 솔루션과 SSL 인증서를 적용한다"와 동일 패턴으로 교체).
    doc.add_heading("보안 요건", level=1)
    doc.add_paragraph("암호화 솔루션과 SSL 인증서를 적용한다.")
    doc.save(docx_buf)
    docx_buf.seek(0)

    test_client, req_store, _doc_store = client
    resp = test_client.post(
        "/documents/upload",
        files={
            "file": (
                "sample.docx", docx_buf,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"actor": "tester"},
    )

    assert resp.status_code == 200
    body = resp.json()
    doc_id = body["data"]["doc_id"]

    # 변환된 PDF가 documents_raw/에 저장됐는지(원본 확장자는 .docx였음에도 불구하고)
    raw_path = tmp_path / "documents_raw" / f"{doc_id}.pdf"
    assert raw_path.exists()

    # 최소 1건은 page_number/bbox가 채워졌는지(§8-2 PDF 파이프라인 편입 확인)
    created = [r for r in req_store.list_all() if r.doc_id == doc_id]
    assert created, "DOCX 업로드에서 요구사항이 생성되지 않음"
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
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AEGIS-VALIDATION"


def test_upload_not_yet_implemented_format_returns_422(client):
    test_client, _, _ = client
    # .hwp는 FORMAT_STRATEGY에는 있으나 실제 어댑터가 아직 없다(HWP 파서 미구현)
    resp = test_client.post(
        "/documents/upload",
        files={"file": ("doc.hwp", io.BytesIO(b"fake hwp content"), "application/octet-stream")},
        data={"actor": "tester"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "AEGIS-VALIDATION"
