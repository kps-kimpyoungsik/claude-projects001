"""[D-011db847 후속] 이미지(png/jpg/jpeg) 업로드 → LLM Vision 설명문 변환 어댑터.

`speech_to_text_adapter.py`(SpeechToTextAdapter)와 동일한 콜백 주입 패턴을 그대로
재사용한다(CRZ — 새 어댑터 골격 발명 없음): 실제 vision 모델 호출은 이 어댑터가 직접
하지 않고 `vision_engine` 콜백으로 주입받는다. 미주입 시 "동작하는 척" 하지 않고
NotImplementedError를 낸다(T98 AIP 정직성 원칙).

`format_dispatch.FORMAT_STRATEGY`가 이미 `.png`/`.jpg`/`.jpeg` → `"vision_describe"`로
분류해 두었다(§5-A 문서유형 SSOT, 신규 목록 발명 없음) — 이 어댑터는 그 전략명에 대응하는
실제 파서 구현체다.
"""

from dataclasses import dataclass
from typing import Any, BinaryIO, Callable

from backend.application.ports.parser_port import ParserPort

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")

# vision 엔진 콜백 시그니처 — 오디오 어댑터(SttEngineCallback)와 동일하게 "파일 경로"를
# 받는다(스트림이 아니라 경로인 이유: Ollama HTTP 요청이 이미지 바이트를 base64로 실어야
# 하므로, 호출자가 디스크에 저장된 파일 경로를 metadata["source_path"]로 넘겨준다는 전제를
# STT 어댑터와 동일하게 유지한다 — 인터페이스 일관성, CRZ).
VisionEngineCallback = Callable[[str], str]


@dataclass
class VisionDescription:
    """vision 엔진 1회 호출 결과 — 이미지 1건 전체에 대한 설명문 1개.

    오디오처럼 여러 세그먼트로 나뉘지 않는다(이미지 1장 = 설명문 1개, 시간축 개념 없음).
    """

    text: str


class VisionDescribeAdapter(ParserPort):
    """이미지 파일 → 정규화 마크다운(설명문) 변환 어댑터 (ParserPort 표준 구현).

    `SpeechToTextAdapter`와 동일하게 실제 vision 추론 로직은 갖지 않는다 — `vision_engine`
    콜백이 없으면 즉시 NotImplementedError를 낸다.
    """

    def __init__(self, vision_engine: VisionEngineCallback | None = None):
        self._vision_engine = vision_engine

    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in SUPPORTED_IMAGE_EXTENSIONS

    def parse_to_markdown(self, file_stream: BinaryIO, metadata: dict[str, Any]) -> str:
        description = self._describe(metadata)
        if not description.text:
            return ""
        return f"## 이미지 설명 (자동 생성)\n\n{description.text}"

    def _describe(self, metadata: dict[str, Any]) -> VisionDescription:
        if self._vision_engine is None:
            raise NotImplementedError(
                "vision 엔진 미주입 — 실제 이미지 설명 생성(Ollama vision 모델 등)은 후속 작업. "
                "vision_engine 콜백을 주입해야 parse_to_markdown이 동작한다."
            )
        source_path = metadata.get("source_path")
        if not source_path:
            raise ValueError(
                "metadata['source_path']가 필요하다 — vision 엔진은 디스크 파일 경로로 호출한다."
            )
        text = self._vision_engine(source_path).strip()
        return VisionDescription(text=text)
