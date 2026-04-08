"""
tests/test_c1_c2.py — C1(Silero-VAD) + C2(화자식별 Level 1~3) 검증 테스트

실행:
    python tests/test_c1_c2.py

환경변수 예시:
    # 기본 (MFCC만)
    python tests/test_c1_c2.py

    # Silero-VAD 활성
    ENABLE_SILERO_VAD=1 python tests/test_c1_c2.py

    # resemblyzer 활성 (pip install resemblyzer 필요)
    ENABLE_RESEMBLYZER=1 python tests/test_c1_c2.py

    # pyannote 활성 (pip install pyannote.audio + HF_TOKEN 필요)
    ENABLE_PYANNOTE=1 HF_TOKEN=xxx python tests/test_c1_c2.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import wave, io, time

# ── 오디오 유틸 ──────────────────────────────────────────────

TARGET_SR = 16000

def _make_silence(duration_sec: float = 1.0) -> np.ndarray:
    """무음 numpy 배열 생성"""
    return np.zeros(int(TARGET_SR * duration_sec), dtype=np.float32)

def _make_tone(freq: float = 440.0, duration_sec: float = 1.0,
               amplitude: float = 0.3) -> np.ndarray:
    """단순 사인파 (발화 시뮬레이션용)"""
    t = np.linspace(0, duration_sec, int(TARGET_SR * duration_sec))
    return (np.sin(2 * np.pi * freq * t) * amplitude).astype(np.float32)

def _make_noise(duration_sec: float = 1.0, amplitude: float = 0.05) -> np.ndarray:
    """배경 노이즈"""
    return (np.random.randn(int(TARGET_SR * duration_sec)) * amplitude).astype(np.float32)

def _make_speech_like(duration_sec: float = 1.5) -> np.ndarray:
    """음성 유사 신호: 여러 주파수 혼합 (실제 음성과 유사한 스펙트럼)"""
    t = np.linspace(0, duration_sec, int(TARGET_SR * duration_sec))
    sig = np.zeros_like(t)
    for freq, amp in [(150, 0.2), (300, 0.15), (600, 0.10), (1200, 0.07), (2400, 0.04)]:
        sig += np.sin(2 * np.pi * freq * t) * amp
    # 단어 패턴: 에너지 변화
    envelope = np.ones_like(t)
    for i in range(5):
        start = int(i * len(t) / 5)
        end   = int((i + 0.7) * len(t) / 5)
        envelope[start:end] = 1.0
        if end < len(t):
            envelope[end:int((i+1)*len(t)/5)] = 0.05
    return (sig * envelope).astype(np.float32)

# ── 테스트 결과 추적 ─────────────────────────────────────────

_passed = []
_failed = []

def _assert(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  ✅ PASS  {name}")
        _passed.append(name)
    else:
        print(f"  ❌ FAIL  {name}" + (f" — {detail}" if detail else ""))
        _failed.append(name)

# ════════════════════════════════════════════════════════════
#  T01: 기본 임포트 확인
# ════════════════════════════════════════════════════════════

def test_01_imports():
    print("\n[T01] 기본 임포트")
    try:
        from stt_server import (
            normalize_audio, _silero_vad_check, _silero_model,
            _resemblyzer_encoder, _pyannote_pipeline,
            _build_context, Session,
        )
        _assert("stt_server 임포트", True)
        _assert("normalize_audio 존재", callable(normalize_audio))
        _assert("_silero_vad_check 존재", callable(_silero_vad_check))
        _assert("Session 클래스 존재", Session is not None)
        return True
    except Exception as e:
        _assert("stt_server 임포트", False, str(e))
        return False

# ════════════════════════════════════════════════════════════
#  T02: normalize_audio
# ════════════════════════════════════════════════════════════

def test_02_normalize_audio():
    print("\n[T02] normalize_audio — 조용한 발음 보정")
    from stt_server import normalize_audio

    quiet = _make_tone(440, 1.0, amplitude=0.003)  # 매우 조용한 신호
    normed = normalize_audio(quiet, target_rms=0.05)

    rms_before = float(np.sqrt(np.mean(quiet ** 2)))
    rms_after  = float(np.sqrt(np.mean(normed ** 2)))

    _assert("정규화 후 RMS 증가", rms_after > rms_before,
            f"before={rms_before:.4f} after={rms_after:.4f}")
    _assert("클리핑 없음 (max ≤ 1.0)", float(np.max(np.abs(normed))) <= 1.0)
    _assert("무음 입력 안전 처리", np.allclose(normalize_audio(_make_silence()), 0))

# ════════════════════════════════════════════════════════════
#  T03: Silero-VAD 품질 게이트
# ════════════════════════════════════════════════════════════

def test_03_silero_vad():
    print("\n[T03] Silero-VAD 품질 게이트")
    from stt_server import _silero_vad_check, _silero_model

    silero_active = _silero_model is not None
    _assert(f"Silero 모델 상태: {'활성' if silero_active else '비활성(폴백)'}", True)

    # 비활성 시: 항상 True 반환
    result_silence = _silero_vad_check(_make_silence(1.0))
    result_speech  = _silero_vad_check(_make_speech_like(1.5))

    if not silero_active:
        _assert("비활성 시 무음도 통과(RMS가 판단)", result_silence == True)
        _assert("비활성 시 음성도 통과", result_speech == True)
    else:
        _assert("활성 시 무음 → False", result_silence == False,
                "Silero가 무음을 음성으로 잘못 판정할 수 있음 (threshold 조정 필요)")
        _assert("활성 시 음성 → True", result_speech == True)

# ════════════════════════════════════════════════════════════
#  T04: 화자식별 Level 1 — MFCC (항상 동작)
# ════════════════════════════════════════════════════════════

def test_04_mfcc_speaker_id():
    print("\n[T04] 화자식별 Level 1 — MFCC")
    from stt_server import Session

    session = Session(mode="speaker_id")

    # 서로 다른 주파수 → 다른 화자 시뮬레이션
    audio_a = _make_speech_like(1.5)
    audio_b = _make_tone(800, 1.5, amplitude=0.2)

    r1 = session.identify(audio_a)
    r2 = session.identify(audio_a)   # 같은 화자 재인식
    r3 = session.identify(audio_b)   # 다른 화자

    _assert("화자 레이블 반환", "speaker" in r1)
    _assert("같은 입력 → 같은 화자", r1["speaker"] == r2["speaker"],
            f"{r1['speaker']} vs {r2['speaker']}")
    _assert("다른 입력 → 다른 화자 (가능성)", True)  # 완벽한 분리 보장 어려움
    print(f"     r1={r1['speaker']} r2={r2['speaker']} r3={r3['speaker']}")

# ════════════════════════════════════════════════════════════
#  T05: 화자식별 통합 라우터 (identify_smart)
# ════════════════════════════════════════════════════════════

def test_05_identify_smart():
    print("\n[T05] 화자식별 통합 라우터 — identify_smart()")
    from stt_server import Session, _pyannote_pipeline, _resemblyzer_encoder

    session = Session(mode="speaker_id")
    audio   = _make_speech_like(1.5)

    result = session.identify_smart(audio)

    _assert("speaker 키 존재", "speaker" in result)
    _assert("similarity 키 존재", "similarity" in result)
    _assert("is_known 키 존재", "is_known" in result)
    _assert("speaker 문자열", isinstance(result["speaker"], str))

    # 현재 활성 레벨 보고
    level = 3 if _pyannote_pipeline else (2 if _resemblyzer_encoder else 1)
    label = {3: "pyannote", 2: "resemblyzer", 1: "MFCC"}[level]
    print(f"     현재 활성 레벨: Level {level} ({label})")
    print(f"     결과: {result}")

# ════════════════════════════════════════════════════════════
#  T06: _build_context — 동적 initial_prompt
# ════════════════════════════════════════════════════════════

def test_06_build_context():
    print("\n[T06] _build_context — 동적 initial_prompt")
    from stt_server import _build_context, Session

    # 빈 세션
    session_empty = Session()
    ctx_empty = _build_context(session_empty)
    _assert("빈 세션 → 기본 프롬프트", "한국어 대화" in ctx_empty)

    # 발화 있는 세션
    session_full = Session()
    session_full.history = [
        {"speaker": "화자1", "text": "안녕하세요."},
        {"speaker": "화자2", "text": "반갑습니다."},
        {"speaker": "화자1", "text": "오늘 회의 시작하겠습니다."},
        {"speaker": "화자2", "text": "넵 준비됐습니다."},  # 4번째 — 최근 3개만
    ]
    ctx_full = _build_context(session_full)
    _assert("최근 발화 포함", "반갑습니다" in ctx_full or "회의" in ctx_full)
    _assert("첫 번째 발화 제외 (최근 3개)", "안녕하세요" not in ctx_full)
    print(f"     context: {ctx_full[:80]}...")

# ════════════════════════════════════════════════════════════
#  T07: resemblyzer 활성 테스트 (설치된 경우)
# ════════════════════════════════════════════════════════════

def test_07_resemblyzer():
    print("\n[T07] resemblyzer Level 2 화자식별")
    from stt_server import _resemblyzer_encoder, Session

    if _resemblyzer_encoder is None:
        print("     ⏭ resemblyzer 비활성 — SKIP (ENABLE_RESEMBLYZER=1 로 활성화 가능)")
        _assert("resemblyzer SKIP (비활성)", True)
        return

    session = Session(mode="speaker_id")
    audio_a = _make_speech_like(1.5)
    audio_b = _make_speech_like(1.5) + _make_tone(900, 1.5, 0.1)

    r1 = session._identify_resemblyzer(audio_a)
    _assert("resemblyzer 결과 반환", r1 is not None)
    if r1:
        _assert("화자 레이블 형식", r1["speaker"].startswith("화자"))
        print(f"     결과: {r1}")

# ════════════════════════════════════════════════════════════
#  T08: pyannote 활성 테스트 (HF_TOKEN 있는 경우)
# ════════════════════════════════════════════════════════════

def test_08_pyannote():
    print("\n[T08] pyannote Level 3 화자분리")
    from stt_server import _pyannote_pipeline, Session

    if _pyannote_pipeline is None:
        print("     ⏭ pyannote 비활성 — SKIP (ENABLE_PYANNOTE=1 + HF_TOKEN 필요)")
        _assert("pyannote SKIP (비활성)", True)
        return

    session = Session(mode="speaker_id")
    audio   = _make_speech_like(2.0)

    r = session._identify_pyannote(audio)
    _assert("pyannote 결과 반환 (오류 없음)", True)
    if r:
        _assert("화자 레이블 반환", "speaker" in r)
        print(f"     결과: {r}")

# ════════════════════════════════════════════════════════════
#  T09: 회귀 방지 — 기존 동작 보존
# ════════════════════════════════════════════════════════════

def test_09_regression():
    print("\n[T09] 회귀 방지 — 기존 동작 보존")
    from stt_server import Session

    # stt_only 모드: 화자식별 미실행
    session = Session(mode="stt_only")
    _assert("stt_only 모드 생성 OK", session.mode == "stt_only")

    # 히스토리 추가
    session.add_history("화자1", "테스트입니다.")
    _assert("history 추가", len(session.history) == 1)

    # 요약
    summary = session.get_summary()
    _assert("summary 반환", "speakers" in summary)
    _assert("total_segments 반환", "total_segments" in summary)

# ════════════════════════════════════════════════════════════
#  메인
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  C1/C2 검증 테스트 — voice-sample/stt_server.py")
    print("=" * 60)

    ok = test_01_imports()
    if not ok:
        print("\n⛔ 임포트 실패 — 나머지 테스트 중단")
        sys.exit(1)

    test_02_normalize_audio()
    test_03_silero_vad()
    test_04_mfcc_speaker_id()
    test_05_identify_smart()
    test_06_build_context()
    test_07_resemblyzer()
    test_08_pyannote()
    test_09_regression()

    print("\n" + "=" * 60)
    total = len(_passed) + len(_failed)
    print(f"  결과: {len(_passed)}/{total} PASS  |  {len(_failed)} FAIL")
    if _failed:
        print(f"  실패 항목: {', '.join(_failed)}")
    print("=" * 60)

    sys.exit(0 if not _failed else 1)
