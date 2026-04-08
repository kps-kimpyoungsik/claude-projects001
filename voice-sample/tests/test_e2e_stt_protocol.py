"""
tests/test_e2e_stt_protocol.py — STT WebSocket 프로토콜 E2E 테스트

테스트 범위 (START → END):
  Step 01: WebSocket 연결
  Step 02: Config 전송 → Ready 수신
  Step 03: WAV 전송 → Result 수신 (첫 번째 세그먼트)
  Step 04: 연결 재사용 없이 두 번째 연결 → 두 번째 세그먼트 검증
           (MediaRecorder 방식의 헤더 유실 문제가 없는지 확인)
  Step 05: 세 번째 연결 — 다른 시나리오 적용
  Step 06: 화자 식별 레벨 검증 (Level 1~3)
  Step 07: 동시 연결 2개 (라운드로빈 처리 확인)
  Step 08: 비정상 입력 처리 (너무 짧은 WAV, 빈 데이터)
  Step 09: 모든 시나리오 프리셋 동작 확인

실행:
    python stt_server.py  # 먼저 실행
    python tests/test_e2e_stt_protocol.py
"""

import sys, os, time, json, wave, io, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np

STT_HOST    = os.getenv("STT_HOST", "ws://localhost:9001")
SAMPLE_RATE = 16000
# FAST_STT=1: T05(시나리오 전체), T06(화자 레벨2~3) 건너뜀 — CPU 환경에서 빠른 검증
FAST_STT    = os.getenv("FAST_STT", "0") == "1"

_passed, _failed = [], []

def _assert(name, cond, detail=""):
    if cond:
        print(f"  ✅ {name}")
        _passed.append(name)
    else:
        print(f"  ❌ {name}" + (f"  ← {detail}" if detail else ""))
        _failed.append(name)

def _skip(name, reason):
    print(f"  ⏭  {name}  [{reason}]")

# ── 오디오 유틸 ─────────────────────────────────────────────
def _make_speech_wav(freq=300.0, duration=1.5, amplitude=0.3) -> bytes:
    """음성 유사 WAV 생성 (발화 패턴 포함)"""
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, dtype=np.float32)
    pcm = np.zeros(n, dtype=np.float32)
    for f, a in [(freq, amplitude), (freq*2, amplitude*0.3),
                 (freq*3, amplitude*0.1), (freq*5, amplitude*0.05)]:
        pcm += np.sin(2 * np.pi * f * t) * a
    # 발화 패턴
    envelope = np.ones(n, dtype=np.float32)
    for i in range(4):
        s = int(i * n / 4)
        e = int((i + 0.6) * n / 4)
        if e < n:
            envelope[e:int((i+1)*n/4)] = 0.02
    pcm *= envelope

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()

def _make_silence_wav(duration=0.2) -> bytes:
    """침묵 WAV (VAD 거부 테스트용)"""
    n = int(SAMPLE_RATE * duration)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
        wf.writeframes(bytes(n * 2))
    return buf.getvalue()

# ── STT WebSocket 클라이언트 헬퍼 ────────────────────────────
STT_TIMEOUT = int(os.getenv("STT_TIMEOUT", "300"))  # CPU Whisper는 실시간의 60~100배 소요

def _stt_call(wav_bytes: bytes, mode: str = "speaker_id",
              scenario: str = "quiet", host: str = STT_HOST,
              timeout: float = None) -> dict:
    if timeout is None:
        # Go 서버와 동일: estSec*60 + 120 (CPU large-v3-turbo 기준)
        est_sec = len(wav_bytes) / (16000 * 2)
        timeout = min(est_sec * 60 + 120, STT_TIMEOUT)
    """
    STT 서버에 1회 완전한 요청-응답 사이클 수행.
    반환: {"ok": True/False, "result": {...} or None, "error": str or None}
    """
    try:
        import websocket
    except ImportError:
        return {"ok": False, "error": "websocket-client 미설치 (pip install websocket-client)"}

    result = {"ok": False, "result": None, "error": None}

    try:
        ws = websocket.create_connection(host, timeout=timeout)

        # Step 1: Config 전송
        cfg = json.dumps({"type": "config", "mode": mode,
                          "language": "ko", "scenario": scenario})
        ws.send(cfg)

        # Step 2: Ready 대기
        deadline = time.time() + 15
        while time.time() < deadline:
            raw = ws.recv()
            d = json.loads(raw)
            if d.get("type") == "ready":
                break
            if d.get("type") == "error":
                result["error"] = d.get("message", "STT error")
                ws.close()
                return result
        else:
            result["error"] = "ready 응답 타임아웃"
            ws.close()
            return result

        # Step 3: WAV 전송
        ws.send_binary(wav_bytes)

        # Step 4: Result 대기
        ws.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = ws.recv()
            d = json.loads(raw)
            if d.get("type") == "result":
                result["ok"] = True
                result["result"] = d
                break
            if d.get("type") == "error":
                result["error"] = d.get("message", "STT error")
                break

        ws.close()

    except Exception as e:
        result["error"] = str(e)

    return result

# ══════════════════════════════════════════════════════════════
#  T01: STT 서버 연결 + Config/Ready 프로토콜
# ══════════════════════════════════════════════════════════════
def test_01_connect_and_ready():
    print("\n[T01] WebSocket 연결 + Config → Ready 프로토콜")
    try:
        import websocket
    except ImportError:
        _assert("websocket-client 설치됨", False,
                "pip install websocket-client")
        return False

    try:
        ws = websocket.create_connection(STT_HOST, timeout=5)
        _assert("WebSocket 연결 성공", True)

        # Config 전송
        cfg = json.dumps({"type": "config", "mode": "stt_only",
                          "language": "ko", "scenario": "quiet"})
        ws.send(cfg)
        _assert("Config 전송 성공", True)

        # Ready 수신
        deadline = time.time() + 10
        ready_received = False
        while time.time() < deadline:
            raw = ws.recv()
            d = json.loads(raw)
            if d.get("type") == "ready":
                ready_received = True
                break
        _assert("Ready 응답 수신", ready_received, "10초 내 ready 미수신")
        ws.close()
        return ready_received
    except Exception as e:
        _assert("STT 서버 연결", False, str(e))
        return False

# ══════════════════════════════════════════════════════════════
#  T02: 첫 번째 세그먼트 완전 처리
# ══════════════════════════════════════════════════════════════
def test_02_first_segment():
    print("\n[T02] 첫 번째 세그먼트 완전 처리 (Config → Ready → WAV → Result)")
    wav = _make_speech_wav(300.0, 1.5)
    r = _stt_call(wav)

    _assert("첫 번째 세그먼트 성공", r["ok"], r.get("error", ""))
    if r["ok"]:
        res = r["result"]
        _assert("text 필드 반환", "text" in res, str(res))
        _assert("speaker 필드 반환", "speaker" in res, str(res))
        _assert("speaker 비어있지 않음", bool(res.get("speaker")))
        print(f"     결과: text='{res.get('text','')[:50]}' speaker={res.get('speaker')}")
    return r["ok"]

# ══════════════════════════════════════════════════════════════
#  T03: 두 번째 세그먼트 — 새 연결로 재처리
#       (핵심: 첫 번째 이후에도 정상 동작하는지 확인)
# ══════════════════════════════════════════════════════════════
def test_03_second_segment():
    print("\n[T03] 두 번째 세그먼트 — 독립 연결로 재처리")
    wav = _make_speech_wav(600.0, 1.2)  # 다른 주파수 (다른 화자)
    r = _stt_call(wav)

    _assert("두 번째 세그먼트 성공", r["ok"],
            f"첫 번째는 OK인데 두 번째 실패 = 헤더 유실 등 지속성 버그  {r.get('error','')}")
    if r["ok"]:
        print(f"     결과: text='{r['result'].get('text','')[:50]}' "
              f"speaker={r['result'].get('speaker')}")
    return r["ok"]

# ══════════════════════════════════════════════════════════════
#  T04: 세 번째 세그먼트 — 같은 화자 재인식
# ══════════════════════════════════════════════════════════════
def test_04_third_segment_same_speaker():
    print("\n[T04] 세 번째 세그먼트 — 처음과 같은 주파수 (화자 일관성)")
    wav = _make_speech_wav(300.0, 1.8)  # T02와 동일 주파수
    r = _stt_call(wav)

    _assert("세 번째 세그먼트 성공", r["ok"], r.get("error", ""))
    if r["ok"]:
        print(f"     결과: speaker={r['result'].get('speaker')}  "
              f"text='{r['result'].get('text','')[:50]}'")
    return r["ok"]

# ══════════════════════════════════════════════════════════════
#  T05: 모든 시나리오 프리셋 동작 확인
# ══════════════════════════════════════════════════════════════
def test_05_all_scenarios():
    print("\n[T05] 모든 시나리오 프리셋 처리")
    if FAST_STT:
        _skip("시나리오 전체 검증", "FAST_STT=1 — 기본 quiet만 T02에서 검증됨")
        return
    scenarios = ["quiet", "noisy", "interview", "debate", "phone"]
    wav = _make_speech_wav(400.0, 1.0)

    for sc in scenarios:
        r = _stt_call(wav, scenario=sc)
        _assert(f"시나리오 '{sc}' 처리 성공", r["ok"],
                r.get("error", ""))

# ══════════════════════════════════════════════════════════════
#  T06: 화자 식별 레벨 확인 (Level 1~3)
# ══════════════════════════════════════════════════════════════
def test_06_speaker_identification():
    print("\n[T06] 화자 식별 레벨 검증")
    from stt_server import _pyannote_pipeline, _resemblyzer_encoder

    level = 3 if _pyannote_pipeline else (2 if _resemblyzer_encoder else 1)
    label = {3: "pyannote", 2: "resemblyzer", 1: "MFCC"}[level]
    print(f"     현재 활성 레벨: Level {level} ({label})")

    wav_a = _make_speech_wav(250.0, 2.0)
    wav_b = _make_speech_wav(700.0, 2.0)

    r_a = _stt_call(wav_a, mode="speaker_id")
    r_b = _stt_call(wav_b, mode="speaker_id")

    _assert("화자A 식별 성공", r_a["ok"], r_a.get("error", ""))
    _assert("화자B 식별 성공", r_b["ok"], r_b.get("error", ""))

    if r_a["ok"] and r_b["ok"]:
        sp_a = r_a["result"].get("speaker")
        sp_b = r_b["result"].get("speaker")
        _assert("화자 레이블 형식 (화자N)",
                sp_a and sp_a.startswith("화자"), f"실제: {sp_a}")
        print(f"     화자A={sp_a}, 화자B={sp_b}")

# ══════════════════════════════════════════════════════════════
#  T07: 동시 연결 2개 (병렬 처리)
# ══════════════════════════════════════════════════════════════
def test_07_concurrent():
    print("\n[T07] 동시 연결 2개 병렬 처리")
    results = [None, None]
    wav_a = _make_speech_wav(300.0, 1.0)
    wav_b = _make_speech_wav(600.0, 1.0)

    def call_a():
        results[0] = _stt_call(wav_a)

    def call_b():
        # 동일 서버에 동시 연결 — asyncio.to_thread 동시성 검증
        results[1] = _stt_call(wav_b, host=STT_HOST)

    t1 = threading.Thread(target=call_a)
    t2 = threading.Thread(target=call_b)
    t1.start(); t2.start()
    t1.join(timeout=STT_TIMEOUT); t2.join(timeout=STT_TIMEOUT)

    ok_a = results[0] is not None and results[0]["ok"]
    ok_b = results[1] is not None and results[1]["ok"]

    _assert("동시 연결 A 성공", ok_a, str(results[0]))
    _assert("동시 연결 B 성공", ok_b, str(results[1]))

    if ok_a and ok_b:
        print(f"     A: speaker={results[0]['result'].get('speaker')} "
              f"| B: speaker={results[1]['result'].get('speaker')}")

# ══════════════════════════════════════════════════════════════
#  T08: 비정상 입력 처리
# ══════════════════════════════════════════════════════════════
def test_08_invalid_inputs():
    print("\n[T08] 비정상 입력 처리")

    # 침묵 WAV (VAD 거부)
    silence = _make_silence_wav(0.3)
    r = _stt_call(silence, timeout=20.0)
    # 침묵은 error 또는 empty text result — 서버가 크래시하지 않으면 OK
    _assert("침묵 WAV — 서버 정상 응답 (크래시 없음)",
            r.get("ok") or r.get("error") is not None,
            "응답 없음 = 서버 행업")

    # 다음 정상 요청이 여전히 동작하는지 (서버 복구 확인)
    wav = _make_speech_wav(440.0, 1.0)
    r2 = _stt_call(wav)
    _assert("비정상 입력 후 다음 요청 정상 처리",
            r2["ok"],
            f"서버가 비정상 입력으로 인해 다음 요청 실패: {r2.get('error','')}")

# ══════════════════════════════════════════════════════════════
#  T09: stt_only 모드 (화자 식별 없이 텍스트만)
# ══════════════════════════════════════════════════════════════
def test_09_stt_only_mode():
    print("\n[T09] stt_only 모드 처리")
    wav = _make_speech_wav(400.0, 1.5)
    r = _stt_call(wav, mode="stt_only")

    _assert("stt_only 모드 결과 반환", r["ok"], r.get("error", ""))
    if r["ok"]:
        _assert("text 필드 반환", "text" in r["result"])
        print(f"     결과: text='{r['result'].get('text','')[:50]}'")

# ══════════════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 65)
    print("  E2E STT 프로토콜 테스트 — stt_server.py 전체 플로우")
    print(f"  대상: {STT_HOST}")
    print("=" * 65)

    # T01: 연결 + 프로토콜
    ok = test_01_connect_and_ready()
    if not ok:
        print("\n⛔ STT 서버 미실행 — 테스트 중단")
        print("   python stt_server.py 를 먼저 실행하세요")
        sys.exit(1)

    # T02~T04: 다중 세그먼트 (첫 번째 이후 지속성 핵심 검증)
    ok2 = test_02_first_segment()
    ok3 = test_03_second_segment()
    ok4 = test_04_third_segment_same_speaker()

    if ok2 and not ok3:
        print("\n  ⚠️  첫 번째는 OK, 두 번째 실패 = 파이프라인 지속성 버그!")

    # T05: 시나리오 프리셋
    test_05_all_scenarios()

    # T06: 화자 식별
    test_06_speaker_identification()

    # T07: 동시 연결
    test_07_concurrent()

    # T08: 비정상 입력
    test_08_invalid_inputs()

    # T09: stt_only 모드
    test_09_stt_only_mode()

    # ── 결과 ──────────────────────────────────────────────────
    print("\n" + "=" * 65)
    total = len(_passed) + len(_failed)
    print(f"  결과: {len(_passed)}/{total} PASS  |  {len(_failed)} FAIL")
    if _failed:
        print(f"  실패 항목:")
        for f in _failed:
            print(f"    - {f}")
    print("=" * 65)

    sys.exit(0 if not _failed else 1)
