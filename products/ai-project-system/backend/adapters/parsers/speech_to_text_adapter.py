"""[Phase 2 후속] 녹음(REC) 문서유형 STT 어댑터 — 스캐폴딩.

plans/_plan/08_RECORDING_STT_STRATEGY.md 참조. 실제 STT 엔진(faster-whisper) 호출은
이 스캐폴딩에 포함하지 않는다 — `heading_splitter.py`의 `SemanticBoundarySplitter`,
`docx_adapter.py`의 "실제 파싱만 구현" 원칙과 동일하게, 여기서는

    오디오 파일 경로 → (STT 엔진 콜백 호출) → 세그먼트 리스트 → Chunk 리스트
    (timestamp_start_ms/timestamp_end_ms 채움)

라는 **데이터 흐름과 인터페이스**만 구현한다. 실제 엔진은 `stt_engine` 콜백으로 주입한다
(`SPCEngine.recall_hook`과 동일한 주입 패턴 — 미주입 시 조용히 가짜 결과를 만들지 않고
`NotImplementedError`로 명시한다, T98 AIP 정직성 원칙).

엔진 선택 근거(08번 설계서 §1 참조 — 실측 상세는 그 문서 참고): 이 프로젝트 Python
환경에 `faster-whisper` 1.2.1이 이미 설치돼 있음을 `pip list`로 직접 확인했다 — 신규
유료 API 의존성 없이 기존 로컬 자산을 재사용하는 것이 이 프로젝트의 철학
(00_PROJECT_CONSTITUTION.md §1·§4)과 일치한다. 실제 `WhisperModel` 인스턴스 생성·호출은
이번 착수 범위 밖(후속)이다.
"""

from dataclasses import dataclass
from typing import Any, BinaryIO, Callable

from backend.application.ports.parser_port import ParserPort
from backend.domain.chunking.chunk import Chunk

# 녹음(REC) 문서유형이 다루는 오디오 확장자 — router.py의 FORMAT_STRATEGY와 동기화 유지(CRZ).
SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a")


@dataclass
class SpeechSegment:
    """STT 엔진 1회 인식 결과 단위 — voiceAW의 `segments:[{start,end,text}]` 관례를
    이 프로젝트의 ms 단위 필드명(timestamp_start_ms/timestamp_end_ms)에 맞춰 표현한다.

    voiceAW는 초(float) 단위를 쓰지만 이 프로젝트의 Chunk.timestamp_*_ms는 ms(int)
    이므로, 초→ms 변환은 이 어댑터 경계에서 한 번만 수행하고 그 이후 계층(Chunk,
    미리보기 UI)은 항상 ms만 다룬다(단위 혼재 방지).
    """

    text: str
    start_ms: int
    end_ms: int


# 실제 엔진 호출부(faster-whisper WhisperModel.transcribe 등)를 주입하는 콜백 시그니처.
# 인자는 오디오 파일 경로(문자열) — 스트림이 아니라 경로를 받는 이유: faster-whisper를
# 포함한 대부분의 STT 엔진이 내부적으로 ffmpeg 디코딩을 위해 파일 경로(또는 seekable
# 파일 객체)를 요구하며, 이 프로젝트에서는 호출자가 이미 디스크에 저장된 업로드 파일의
# 경로를 metadata["source_path"]로 넘겨주는 것을 전제로 한다(§2 참고).
SttEngineCallback = Callable[[str], list[SpeechSegment]]


class SpeechToTextAdapter(ParserPort):
    """녹음 파일 → 정규화 마크다운 변환 어댑터 (ParserPort 표준 구현).

    `docx_adapter.DocxParserAdapter`와 동일한 포트를 구현하지만, 실제 음성인식 로직은
    갖고 있지 않다 — `stt_engine` 콜백이 없으면 "동작하는 척" 하지 않고 즉시
    NotImplementedError를 낸다(과장 금지, T98 AIP).
    """

    def __init__(self, stt_engine: SttEngineCallback | None = None):
        self._stt_engine = stt_engine

    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in SUPPORTED_AUDIO_EXTENSIONS

    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        segments = self._transcribe(metadata)
        if not segments:
            return ""
        lines = [
            f"- [{_ms_to_timestamp(s.start_ms)} → {_ms_to_timestamp(s.end_ms)}] {s.text}"
            for s in segments
        ]
        return "\n".join(lines)

    def transcribe_to_chunks(self, metadata: dict[str, Any], doc_id: str) -> list[Chunk]:
        """§2 데이터 흐름의 핵심 산출물 — timestamp_start_ms/end_ms가 채워진 Chunk 리스트.

        `heading_splitter.SPCEngine.process_document`가 텍스트 문서에서 하는 일(마크다운
        → Chunk 리스트)과 대응되는, 오디오 전용 경로다. `heading_path`는 오디오에는
        의미가 없으므로 비워두고(§1-2 설계 그대로 — 포맷별 선택적 좌표), char_start/
        char_end 대신 timestamp_start_ms/timestamp_end_ms를 채운다.
        """
        segments = self._transcribe(metadata)
        return [
            Chunk(
                chunk_id=f"{doc_id}::segment:{i}",
                content=segment.text,
                doc_id=doc_id,
                timestamp_start_ms=segment.start_ms,
                timestamp_end_ms=segment.end_ms,
            )
            for i, segment in enumerate(segments)
        ]

    def _transcribe(self, metadata: dict[str, Any]) -> list[SpeechSegment]:
        if self._stt_engine is None:
            raise NotImplementedError(
                "STT 엔진 미주입 — 실제 음성인식(faster-whisper 등)은 후속 작업. "
                "stt_engine 콜백을 주입해야 transcribe_to_chunks/parse_to_markdown이 동작한다 "
                "(plans/_plan/08_RECORDING_STT_STRATEGY.md 참조)."
            )
        source_path = metadata.get("source_path")
        if not source_path:
            raise ValueError(
                "metadata['source_path']가 필요하다 — STT 엔진은 디스크 파일 경로로 호출한다."
            )
        return self._stt_engine(source_path)


def _ms_to_timestamp(ms: int) -> str:
    """ms → "MM:SS" 표시용 변환 (마크다운 가독성 목적, 정밀 좌표는 Chunk 필드가 담당)."""
    total_seconds = max(ms, 0) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"
