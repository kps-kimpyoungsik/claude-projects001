"""[REC 후속] 실제 STT 엔진 연결 — faster-whisper.

plans/_plan/08_RECORDING_STT_STRATEGY.md §2-1·§6-2 참조. `speech_to_text_adapter.py`가
비워둔 `stt_engine: Callable[[str], list[SpeechSegment]]` 콜백 하나를 여기서 구현한다.
어댑터 본체(`SpeechToTextAdapter`)는 수정하지 않는다 — 08번 설계서가 의도한 대로
"실제 엔진 연결은 콜백 구현 하나로 한정"된다(CRZ, §2-2 콜백 주입 관례 재사용).

## 참고한 패턴의 출처 (코드 복사 아님 — 파라미터·구조만 참고, 이 파일은 새로 작성)

`D:\\projects\\products\\voiceAW\\02_backend\\python\\pipeline\\batch_stt.py`
(읽기 전용 조사, 그 프로젝트 파일은 수정하지 않았다)에서 아래 사실만 확인했다:

- `WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)`로 인스턴스화하고
  `model.transcribe(path, **params)`가 `(segments_generator, info)` 튜플을 반환한다.
- VAD 파라미터: `vad_filter=True`, `vad_parameters={"min_silence_duration_ms": 300,
  "speech_pad_ms": 200}` — 무음구간 기준 세그먼트 분할(고정 길이 분할이 아님).
- 세그먼트 객체는 `seg.start`/`seg.end`(초 단위 float)/`seg.text` 속성을 가진다 —
  이 프로젝트는 ms(int) 단위로 통일하므로(08번 설계서 §2-4), 초→ms 변환은 이 어댑터
  경계에서 한 번만 수행한다(`round(seg.start * 1000)`).

## 모델 크기 선택 근거 (voiceAW와 다르게 결정 — 과잉설계 회피)

voiceAW는 배치 처리 서버(상시 기동, 정확도 우선)라 `large-v3-turbo` + `beam_size=5`를
쓴다. 이 프로젝트는 **로컬 세션 실행**(사용자 워크스테이션에서 그때그때 문서를
업로드·처리하는 방식)이라 그 전제가 다르다:

- large 계열은 첫 실행 시 ~1.5GB+ 모델 다운로드 + 로딩 시간이 필요해, 이 프로젝트의
  "문서 업로드 즉시 처리" 흐름에 부적절하다(응답 지연, T38 PAP 성능 적응형 판단).
- 기본값을 **"tiny"**로 둔다 — 다운로드 용량이 가장 작고(~75MB) CPU에서도 즉시 응답
  가능한 크기다. 정확도가 부족하면 `model_size` 인자로 호출자가 "base"/"small" 등으로
  올릴 수 있게 열어둔다(하드코딩된 단일 크기에 갇히지 않음).
- `beam_size=1`(voiceAW의 5 대신) — tiny 모델은 beam 크기를 올려도 정확도 개선 폭이
  작고, 로컬 세션에서는 속도가 더 중요하다는 판단(실측 없이 5를 그대로 베끼면 근거
  없는 하드코딩이 된다, T98 AIP).
- `compute_type="int8"`(voiceAW의 "int8_float32" 대신) — CPU 전용 로컬 세션에서 CTranslate2
  공식 권장 경량 양자화 타입이며, 별도 float32 누산이 필요할 정도로 긴 배치 오디오를
  이 프로젝트가 다루지 않는다(voiceAW는 상시 배치 서버라 다른 트레이드오프를 택한 것).

VAD 파라미터(`vad_filter=True`, `min_silence_duration_ms=300`, `speech_pad_ms=200`)는
voiceAW 실측값을 그대로 채택한다 — 이 값은 모델 크기가 아니라 "무음 판정 임계치"라
모델 크기 축소와 독립적이고, 이미 검증된 실전 값이므로 재발명하지 않는다(CRZ).
"""

from __future__ import annotations

from typing import Callable

from backend.adapters.parsers.speech_to_text_adapter import SpeechSegment, SttEngineCallback

# 기본 모델 크기 — 로컬 세션 실행 전제(위 모듈 docstring 근거), 필요 시 호출자가 상향 조정.
DEFAULT_MODEL_SIZE = "tiny"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"

# voiceAW 실측 VAD 파라미터(batch_stt.py TRANSCRIBE_PARAMS) — 모델 크기와 독립적으로 재사용.
VAD_PARAMETERS = {
    "min_silence_duration_ms": 300,
    "speech_pad_ms": 200,
}


def build_faster_whisper_stt_engine(
    model_size: str = DEFAULT_MODEL_SIZE,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
    language: str | None = "ko",
) -> SttEngineCallback:
    """`SpeechToTextAdapter(stt_engine=...)`에 그대로 주입 가능한 콜백을 만든다.

    `WhisperModel` 인스턴스화는 이 함수를 호출하는 시점에 1회만 일어난다(지연 로딩) —
    모듈 import 시점에 모델을 로드하지 않는다. 이렇게 해야 `faster-whisper`가 설치돼
    있다는 사실만 확인하는 가벼운 테스트(실제 모델 다운로드 없음)가 가능하다.
    """
    # 지연 import — 모듈 최상단에서 import하면 faster-whisper 미설치 환경에서
    # speech_to_text_adapter.py 등 이 콜백을 쓰지 않는 코드까지 import 실패한다.
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def _stt_engine(source_path: str) -> list[SpeechSegment]:
        segments_gen, _info = model.transcribe(
            source_path,
            language=language,
            beam_size=1,
            vad_filter=True,
            vad_parameters=VAD_PARAMETERS,
        )
        return [
            SpeechSegment(
                text=seg.text.strip(),
                # 초(float) → ms(int) 변환은 이 어댑터 경계에서 한 번만 수행한다
                # (08번 설계서 §2-4 — 이후 계층은 항상 ms만 다룬다).
                start_ms=round(seg.start * 1000),
                end_ms=round(seg.end * 1000),
            )
            for seg in segments_gen
            if seg.text.strip()
        ]

    return _stt_engine
