"""녹음(REC) STT 어댑터 스캐폴딩 테스트 — plans/_plan/08_RECORDING_STT_STRATEGY.md.

실제 STT 엔진(faster-whisper)은 호출하지 않는다 — stt_engine 콜백을 mock으로 주입해
"청크 분할 + timestamp_start_ms/end_ms 채우기 + 콜백 주입 구조"만 검증한다.
"""

import pytest

from backend.adapters.parsers.format_dispatch import FORMAT_STRATEGY
from backend.adapters.parsers.speech_to_text_adapter import (
    SUPPORTED_AUDIO_EXTENSIONS,
    SpeechSegment,
    SpeechToTextAdapter,
)


def test_router_maps_audio_extensions_to_speech_to_text_strategy():
    for ext in SUPPORTED_AUDIO_EXTENSIONS:
        assert FORMAT_STRATEGY[ext] == "speech_to_text"


def _fake_stt_engine(source_path: str) -> list[SpeechSegment]:
    """faster-whisper 등 실제 엔진을 흉내내는 mock — 초 단위가 아니라 이미 ms로 반환한다
    (단위 변환은 실제 엔진 어댑터 내부에서 처리될 부분이라 mock에서는 결과만 고정)."""
    assert source_path == "uploads/interview.wav"
    return [
        SpeechSegment(text="안녕하세요 회의를 시작하겠습니다.", start_ms=0, end_ms=2500),
        SpeechSegment(text="오늘 안건은 보안 요건입니다.", start_ms=2500, end_ms=5200),
    ]


def test_can_handle_audio_extensions():
    adapter = SpeechToTextAdapter()
    for ext in SUPPORTED_AUDIO_EXTENSIONS:
        assert adapter.can_handle(ext)
        assert adapter.can_handle(ext.upper())  # 대소문자 무관
    assert not adapter.can_handle(".docx")


def test_no_engine_injected_raises_not_implemented():
    adapter = SpeechToTextAdapter()  # stt_engine 미주입
    with pytest.raises(NotImplementedError):
        adapter.transcribe_to_chunks({"source_path": "uploads/interview.wav"}, doc_id="doc1")


def test_missing_source_path_raises_value_error():
    adapter = SpeechToTextAdapter(stt_engine=_fake_stt_engine)
    with pytest.raises(ValueError):
        adapter.transcribe_to_chunks({}, doc_id="doc1")


def test_transcribe_to_chunks_fills_timestamp_fields():
    adapter = SpeechToTextAdapter(stt_engine=_fake_stt_engine)
    chunks = adapter.transcribe_to_chunks(
        {"source_path": "uploads/interview.wav"}, doc_id="doc1"
    )
    assert len(chunks) == 2

    first, second = chunks
    assert first.chunk_id == "doc1::segment:0"
    assert first.doc_id == "doc1"
    assert first.timestamp_start_ms == 0
    assert first.timestamp_end_ms == 2500
    assert first.content == "안녕하세요 회의를 시작하겠습니다."
    # 오디오는 heading_path/char_start/char_end가 의미 없음 (§1-2 포맷별 선택적 좌표)
    assert first.heading_path == []
    assert first.char_start is None
    assert first.char_end is None

    assert second.chunk_id == "doc1::segment:1"
    assert second.timestamp_start_ms == 2500
    assert second.timestamp_end_ms == 5200


def test_parse_to_markdown_renders_timestamped_lines():
    adapter = SpeechToTextAdapter(stt_engine=_fake_stt_engine)
    markdown = adapter.parse_to_markdown(
        file_stream=None, metadata={"source_path": "uploads/interview.wav"}
    )
    assert "[00:00 → 00:02] 안녕하세요 회의를 시작하겠습니다." in markdown
    assert "[00:02 → 00:05] 오늘 안건은 보안 요건입니다." in markdown


def test_parse_to_markdown_empty_segments_returns_empty_string():
    adapter = SpeechToTextAdapter(stt_engine=lambda path: [])
    markdown = adapter.parse_to_markdown(
        file_stream=None, metadata={"source_path": "uploads/interview.wav"}
    )
    assert markdown == ""
