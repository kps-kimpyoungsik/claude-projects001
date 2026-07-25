"""faster-whisper 실제 엔진 연결(faster_whisper_engine.py) 테스트.

plans/_plan/08_RECORDING_STT_STRATEGY.md §6-2 후속 작업. 아래 4가지를 확인한다:

1. 모듈이 정상 import되는지 (WhisperModel 인스턴스화 없이 — 지연 로딩 확인)
2. build_faster_whisper_stt_engine의 함수 시그니처가 올바른지
3. faster-whisper 패키지가 실제 설치돼 있는지
4. 실제 오디오(tests/fixtures/sample_speech_ko.wav) + tiny 모델로 end-to-end
   transcribe() 호출 — 2026-07-20 실제 실행·검증 완료(README 하단 결과 참고).
   `tiny` 모델은 최초 실행 시 HuggingFace 캐시(`~/.cache/huggingface`)에
   자동 다운로드되며, 이후 실행은 캐시를 재사용한다(별도 캐시 로직 없음 —
   faster-whisper/huggingface_hub 기본 동작 그대로).
"""

import inspect
import os


def test_module_imports_without_loading_model():
    """모듈 import 시점에 WhisperModel을 로드하지 않는다(지연 로딩) — import만으로
    무거운 모델 다운로드가 트리거되면 안 된다."""
    from backend.adapters.parsers import faster_whisper_engine

    assert hasattr(faster_whisper_engine, "build_faster_whisper_stt_engine")
    assert faster_whisper_engine.DEFAULT_MODEL_SIZE == "tiny"


def test_build_faster_whisper_stt_engine_signature():
    from backend.adapters.parsers.faster_whisper_engine import (
        build_faster_whisper_stt_engine,
    )

    sig = inspect.signature(build_faster_whisper_stt_engine)
    params = sig.parameters
    assert "model_size" in params
    assert params["model_size"].default == "tiny"
    assert "device" in params
    assert "compute_type" in params
    assert "language" in params


def test_faster_whisper_package_is_installed():
    """faster-whisper가 실제 설치돼 있는지만 확인 — WhisperModel 인스턴스화는 하지 않는다."""
    import faster_whisper
    from faster_whisper import WhisperModel

    assert WhisperModel is not None
    assert faster_whisper is not None


def test_build_faster_whisper_stt_engine_transcribes_real_audio():
    """실제 엔진 호출 end-to-end 테스트 — tiny 모델(최초 실행 시 자동 다운로드,
    ~75MB, HuggingFace 캐시 재사용) + 실제 음성 오디오(Windows SAPI로 합성한
    영어 문장, tests/fixtures/sample_speech_ko.wav)로 transcribe()를 실제 호출한다.

    시간이 걸릴 수 있다(최초 실행 시 모델 다운로드 포함 수십 초~수 분) — 정상이다.
    """
    from backend.adapters.parsers.faster_whisper_engine import (
        build_faster_whisper_stt_engine,
    )

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "sample_speech_ko.wav"
    )
    assert os.path.isfile(fixture_path), f"fixture 오디오 없음: {fixture_path}"

    engine = build_faster_whisper_stt_engine(language="en")
    segments = engine(fixture_path)

    assert segments, "실제 음성 오디오인데 세그먼트가 하나도 없음 — VAD/모델 문제 의심"
    for seg in segments:
        assert isinstance(seg.text, str) and seg.text.strip()
        assert isinstance(seg.start_ms, int)
        assert isinstance(seg.end_ms, int)
        assert seg.end_ms > seg.start_ms >= 0
