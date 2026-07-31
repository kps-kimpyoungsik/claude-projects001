"""[D-011db847 후속] 실제 vision 엔진 연결 — Ollama `moondream`.

`vision_describe_adapter.py`가 비워둔 `vision_engine: Callable[[str], str]` 콜백 하나를
여기서 구현한다. `ollama_semantic_judge.py`(같은 로컬 Ollama 127.0.0.1:11434, API 키
불요·인증 없음 로컬호스트라 SAFETY 비밀키 게이트 대상 아님)와 동일한 `urllib` HTTP 호출
패턴을 재사용한다(CRZ — 새 HTTP 클라이언트 방식 발명 없음).

## 모델 선택 근거 (사용자 결정 2026-07-30, AskUserQuestion)

D-011db847이 미결로 남겨둔 "어떤 vision 모델을 쓸지" 결정 — 로컬 Ollama에 vision 모델이
전혀 설치돼 있지 않음을 `curl /api/tags` 실측으로 확인(텍스트전용 qwen2.5:1.5b뿐)한 뒤,
아래 트레이드오프를 사용자에게 제시해 **moondream**(~1.7GB, CPU에서도 빠름)을 선택받았다
— 이 프로젝트가 로컬 세션 실행 전제(faster_whisper_engine.py의 "tiny" 선택과 동일한 이유,
T38 PAP)이고, 이 개발 환경 자체가 이미 CPU 100% 고부하(KH-2026-0783, 30+ pm2 데몬 상시
가동)라 무거운 llava:7b(~4.7GB)보다 경량 모델이 더 안전한 선택이다.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Callable

OLLAMA_GENERATE_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "moondream"
# [2026-07-30 실측] 첫 호출(모델 최초 메모리 로드 포함)이 이 개발 환경의 상시 CPU 100%
# 부하(KH-2026-0783, 30+ pm2 데몬)에서 60초를 넘기는 것을 실제로 관측했다(60s 타임아웃으로
# 재현 실패 확인 후 상향) — `ollama_semantic_judge.py`의 60s(텍스트전용 소형모델, 훨씬
# 가벼움)와 달리 vision 모델은 이미지 인코딩 오버헤드가 더 크다. `libreoffice_bridge.
# DEFAULT_TIMEOUT_SECONDS`(120s)와 동일한 값을 채택 — 이 프로젝트가 이미 "무거운 로컬 변환
# 작업은 120s"로 합의한 기준선이 있어 새 임계값을 만들지 않는다(CRZ).
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_PROMPT = (
    "이 이미지에 무엇이 보이는지 한국어로 상세히 설명하라 — 텍스트가 보이면 그 텍스트도 "
    "그대로 옮겨 적어라. 설명문만 출력하고 다른 부연은 하지 마라."
)


class OllamaVisionUnavailableError(RuntimeError):
    """Ollama 서버 미기동/타임아웃/모델 미설치 — 호출자가 구분해서 처리하도록 별도 예외로 던진다."""


def build_ollama_vision_engine(
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    url: str = OLLAMA_GENERATE_URL,
    prompt: str = DEFAULT_PROMPT,
) -> Callable[[str], str]:
    """`VisionDescribeAdapter(vision_engine=...)`에 그대로 주입 가능한 콜백을 만든다.

    `faster_whisper_engine.build_faster_whisper_stt_engine()`과 동일하게, 이 함수는
    "설정을 캡처한 콜백"만 만든다 — 실제 HTTP 요청은 콜백이 호출되는 시점(이미지 업로드
    시점)에만 발생한다(지연 실행, 모듈 import 시점 네트워크 호출 없음).
    """

    def _vision_engine(source_path: str) -> str:
        with open(source_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("ascii")

        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise OllamaVisionUnavailableError(f"Ollama vision 호출 실패({url}, model={model}): {exc}") from exc

        # Ollama가 모델 미설치 시에도 HTTP 200 + error 필드로 응답하는 경우가 있어(실측
        # ollama_semantic_judge.py의 관례와 달리 vision은 이 실패 모드가 흔함) 명시적으로
        # 확인한다 — 조용히 빈 설명문을 반환하지 않는다(T98 AIP).
        if "error" in body:
            raise OllamaVisionUnavailableError(f"Ollama vision 모델 오류(model={model}): {body['error']}")

        return body.get("response", "")

    return _vision_engine
